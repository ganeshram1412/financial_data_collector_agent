"""
validation_tools.py
-------------------

Numeric & Flag Validation Utilities for FSO Initialization

This module provides a **single, comprehensive validation tool** plus several
helper functions used by the `financial_data_collector_agent` to normalize and
validate raw user inputs into a clean, machine-friendly structure.

Core responsibilities:
    - Parse free-form numeric strings into floats (supports commas, currency
      symbols, and k/M suffixes).
    - Parse multi-item lists (for commitments, EMIs, and investments) provided
      in various user-entered formats (JSON, key:value, or delimited lists).
    - Parse Yes/No style flags into strict booleans.
    - Aggregate all essential data validation into one call:
        `validate_all_essential_data(...)`

Typical usage:
    - The LLM agent collects raw strings from the user for:
        * income
        * commitments
        * EMIs
        * investments
        * savings
        * emergency fund
        * life & health insurance flags
    - The agent passes those raw strings into
        `validate_all_essential_data(...)`.
    - On success:
        * Returns `{"status": "success", "data": "<json>"}`
          where `<json>` is a compact JSON-encoded object with validated fields.
    - On failure:
        * Returns `{"status": "error", "error_message": "...details..."}`

This module is **deterministic and side-effect free** (except for logging).
It is safe for reuse by multiple agents and tools.

Logging:
    - Uses the module logger (`__name__`).
    - Logs parsing issues and overall validation success/failure at INFO/WARN.
"""

import json
import math
import re
import logging
from typing import Dict, Any, List, Tuple, Optional

# --- Logging Setup ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------- Helpers (Kept Intact + Extended) ---------------- #

def _sanitize_and_parse_number_str(s: str) -> Tuple[bool, Optional[float], str]:
    """
    Parse a loosely formatted numeric string into a float.

    Supported formats:
        - Plain numbers:
            "5000", "12000.50", "-100"
        - With currency symbols:
            "₹5,000", "$12,000.50"
        - With thousands/millions suffixes:
            "5k"  ->  5000.0
            "1.2M" -> 1200000.0
        - With commas:
            "1,20,000", "100,000"

    Steps:
        1. Strip whitespace and remove common symbols (₹, $, commas, spaces).
        2. Match a numeric base and optional suffix: k/K or m/M.
        3. Convert numeric base to float.
        4. Apply multiplier based on suffix:
               k/K -> x1,000
               m/M -> x1,000,000
        5. Ensure result is finite.

    Parameters
    ----------
    s : str
        Raw user input string representing a numeric value.

    Returns
    -------
    (ok, value, err_msg) : Tuple[bool, Optional[float], str]
        ok :
            True if parsing succeeded and produced a finite float.
        value :
            Parsed float value if ok is True, otherwise None.
        err_msg :
            Empty string on success, or a human-readable error message on failure.
    """
    if s is None or not s.strip():
        logger.debug("Parser: Input is None or empty.")
        return False, None, "No value provided"
    
    raw = s.strip()
    
    # 1. Clean the string by removing common symbols and spaces
    cleaned = raw.replace(",", "").replace("₹", "").replace("$", "").replace(" ", "")
    
    # 2. Match the number part and an optional k/M suffix
    m = re.match(r"^([-+]?[0-9]*\.?[0-9]+)([kKmM])?$", cleaned)
    
    if not m:
        logger.warning("Parser: Unrecognized numeric format for raw input: '%s'", s)
        return False, None, f"Unrecognized numeric format: '{s}'"
        
    num_part = m.group(1)
    suffix = (m.group(2) or "").lower()
    
    try:
        val = float(num_part)
    except ValueError as e:
        logger.error("Parser: Could not parse number part '%s'. Error: %s", num_part, e)
        return False, None, f"Could not parse number part: {e}"
        
    # 3. Apply multiplier for suffixes
    if suffix == "k":
        val *= 1_000.0
    elif suffix == "m":
        val *= 1_000_000.0
        
    # 4. Final check for non-finite values
    if math.isnan(val) or math.isinf(val):
        logger.warning("Parser: Parsed value is not finite: %s", val)
        return False, None, "Parsed value is not finite"
        
    logger.debug("Parser: Input '%s' successfully parsed to %.2f", s, val)
    return True, val, ""


def _success_dict(data_obj: Any) -> Dict[str, str]:
    """
    Wrap structured data into a standardized success envelope.

    This is the expected output shape for tools consumed by LLM agents:

        {
          "status": "success",
          "data": "<json-string>"
        }

    Parameters
    ----------
    data_obj : Any
        A JSON-serializable Python object (typically a dict) representing
        validated and normalized data.

    Returns
    -------
    Dict[str, str]
        Dictionary with status and compact JSON string in the `data` field.
    """
    return {"status": "success", "data": json.dumps(data_obj, separators=(",", ":"))}


def _error_dict(msg: str) -> Dict[str, str]:
    """
    Create a standardized error envelope for tool responses.

    Shape:
        {
          "status": "error",
          "error_message": "<human-readable explanation>"
        }

    Parameters
    ----------
    msg : str
        Description of the validation or parsing error.

    Returns
    -------
    Dict[str, str]
        Dictionary containing an error status and message.
    """
    return {"status": "error", "error_message": str(msg)}


def _parse_multi_item_list(
    input_str: str,
    non_negative_check: bool = True
) -> Tuple[bool, List[Dict[str, float]], float, str]:
    """
    Parse a multi-item financial list into a normalized structure.

    This helper is used for complex inputs such as:
        - monthly_commitments
        - monthly_emi_per_debt_type
        - investment_contributions

    Supported formats:
        1. JSON object:
           "{ \"rent\": 15000, \"groceries\": 8000 }"

        2. Key-value pairs separated by commas/semicolons/newlines:
           "rent:15000, groceries:8000"
           "emi1:2500; emi2:4500"

        3. Plain list of amounts:
           "15000, 8000, 2000"
           (auto-labeled as item_0, item_1, ...)

    Validation rules:
        - Each value must be parseable as a number (via _sanitize_and_parse_number_str).
        - If non_negative_check is True, no value may be negative.

    Parameters
    ----------
    input_str : str
        Raw user-provided string containing one or more financial items.
    non_negative_check : bool, optional
        If True (default), negative values are rejected.

    Returns
    -------
    (ok, items, total, err_msg) : Tuple[bool, List[Dict[str, float]], float, str]
        ok :
            True if parsing succeeded for all items.
        items :
            List of dicts with structure: {"type": <label>, "amount": <float>}.
        total :
            Sum of all parsed amounts, rounded to 2 decimals.
        err_msg :
            Error message if ok is False, else "".
    """
    raw = input_str.strip()
    items: List[Dict[str, float]] = []
    total = 0.0

    if not raw:
        return True, [], 0.0, ""

    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
            if not isinstance(obj, dict):
                return False, [], 0.0, "JSON must be a key-value object."
            
            for k, v in obj.items():
                ok, amt, err = _sanitize_and_parse_number_str(str(v))
                if not ok:
                    return False, [], 0.0, f"Invalid amount for '{k}': {err}"
                if non_negative_check and amt < 0:
                    return False, [], 0.0, f"Value for '{k}' must be non-negative."
                
                items.append({"type": str(k), "amount": round(amt, 2)})
                total += amt
        except Exception as e:
            return False, [], 0.0, f"Invalid JSON format: {e}"
            
    else:
        # Handle comma/semicolon/newline separated list or key:value pairs
        parts = [p.strip() for p in re.split(r"[,\n;]+", raw) if p.strip()]
        if not parts:
            return False, [], 0.0, "No items provided."
        
        for idx, part in enumerate(parts):
            name = None
            amt_raw = part
            
            if ":" in part:
                name, amt_raw = part.split(":", 1)
                
            ok, amt, err = _sanitize_and_parse_number_str(amt_raw)
            
            if not ok:
                item_label = name.strip() if name else part
                return False, [], 0.0, f"Invalid value for '{item_label}': {err}"
                
            if non_negative_check and amt < 0:
                item_label = name.strip() if name else f"item_{idx}"
                return False, [], 0.0, f"Value for '{item_label}' must be non-negative."
                
            item_name = name.strip() if name else f"item_{len(items)}"
            items.append({"type": item_name, "amount": round(amt, 2)})
            total += amt

    return True, items, round(total, 2), ""


def _parse_yes_no_flag(s: str, field_label: str) -> Tuple[bool, Optional[bool], str]:
    """
    Parse a Yes/No-style string into a strict boolean.

    Accepted (case-insensitive) values:
        True  →  "yes", "y", "true", "1"
        False →  "no",  "n", "false", "0"

    Parameters
    ----------
    s : str
        Raw user input string for a boolean-like field.
    field_label : str
        Human-readable field name used in error messages
        (e.g., "has_life_insurance").

    Returns
    -------
    (ok, value, err_msg) : Tuple[bool, Optional[bool], str]
        ok :
            True if the input string matched a known Yes/No variant.
        value :
            True or False if ok is True, otherwise None.
        err_msg :
            Explanation if parsing failed, empty string on success.
    """
    if s is None or not str(s).strip():
        return False, None, f"'{field_label}' is required and must be Yes or No."

    raw = str(s).strip().lower()

    true_vals = {"yes", "y", "true", "1"}
    false_vals = {"no", "n", "false", "0"}

    if raw in true_vals:
        return True, True, ""
    if raw in false_vals:
        return True, False, ""

    return (
        False,
        None,
        f"'{field_label}' must be Yes/No (accepted: yes/y/true/1 or no/n/false/0). Got: '{s}'",
    )

# ---------------- Single Comprehensive Tool ---------------- #

def validate_all_essential_data(
    monthly_net_income_str: str,
    monthly_commitments_str: str,
    monthly_emi_str: str,
    investment_contributions_str: str,
    savings_per_month_str: str,
    emergency_fund_amount_str: str,
    has_life_insurance_str: str,
    has_health_insurance_str: str,
) -> Dict[str, str]:
    """
    Validate and normalize all essential financial inputs in a single call.

    This is the main tool entrypoint used by the `financial_data_collector_agent`.
    It takes raw string inputs (as typically collected from user conversation)
    and converts them into a normalized, structured object.

    Inputs (raw strings)
    --------------------
    monthly_net_income_str : str
        User's net monthly income (supports commas, currency symbols, k/M suffix).
    monthly_commitments_str : str
        Fixed or recurring monthly obligations (rent, school fees, etc.).
        May be specified as JSON, key:value list, or delimited list.
    monthly_emi_str : str
        EMIs per debt type, similar flexible format as commitments.
    investment_contributions_str : str
        Monthly contributions into investments (SIPs, RDs, etc.).
    savings_per_month_str : str
        Amount actually saved per month (liquid savings).
    emergency_fund_amount_str : str
        Current total emergency fund corpus.
    has_life_insurance_str : str
        Yes/No style input indicating whether the user has life insurance.
    has_health_insurance_str : str
        Yes/No style input indicating whether the user has health insurance.

    Output Structure (on success)
    -----------------------------
    Returns:
        {
          "status": "success",
          "data": "<json-string>"
        }

    Where `<json-string>` encodes a dict of the form:
        {
          "monthly_net_income": float,
          "commitments": [
              {"type": "rent", "amount": 15000.0},
              ...
          ],
          "total_commitments": float,
          "emis": [
              {"type": "home_loan", "amount": 25000.0},
              ...
          ],
          "total_emi": float,
          "investments": [
              {"type": "sip_equity", "amount": 10000.0},
              ...
          ],
          "total_investment_contributions": float,
          "savings_per_month": float,
          "emergency_fund_amount": float,
          "has_life_insurance": bool,
          "has_health_insurance": bool
        }

    Output Structure (on error)
    ---------------------------
    Returns:
        {
          "status": "error",
          "error_message": "{...JSON of field-level errors...}"
        }

    The `error_message` field contains a JSON string mapping field names
    to human-readable error explanations. The calling agent should parse
    that JSON and ask the user only for the specific fields that failed.

    Notes
    -----
    - All numeric fields must be >= 0, except `monthly_net_income` which
      must be strictly > 0.
    - This function is intentionally strict to avoid propagating bad data
      into the FSO.
    """
    logger.info(
        "Tool called: validate_all_essential_data. Starting batch validation "
        "for income/commitments/emi/investments/savings/emergency_fund/insurance."
    )
    
    parsed_data: Dict[str, Any] = {}
    validation_errors: Dict[str, str] = {}
    
    # 1. monthly_net_income
    ok, val, err = _sanitize_and_parse_number_str(monthly_net_income_str)
    if not ok:
        validation_errors["monthly_net_income"] = err
    elif val <= 0:
        validation_errors["monthly_net_income"] = "Monthly net income must be greater than 0."
    else:
        parsed_data["monthly_net_income"] = val

    # 2. monthly_commitments
    ok, items, total, err = _parse_multi_item_list(monthly_commitments_str, non_negative_check=True)
    if not ok:
        validation_errors["monthly_commitments"] = err
    else:
        parsed_data["commitments"] = items
        parsed_data["total_commitments"] = total

    # 3. monthly_emi_per_debt_type
    ok, items, total, err = _parse_multi_item_list(monthly_emi_str, non_negative_check=True)
    if not ok:
        validation_errors["monthly_emi_per_debt_type"] = err
    else:
        parsed_data["emis"] = items
        parsed_data["total_emi"] = total
        
    # 4. investment_contributions
    ok, items, total, err = _parse_multi_item_list(investment_contributions_str, non_negative_check=True)
    if not ok:
        validation_errors["investment_contributions"] = err
    else:
        parsed_data["investments"] = items
        parsed_data["total_investment_contributions"] = total

    # 5. savings_per_month
    ok, val, err = _sanitize_and_parse_number_str(savings_per_month_str)
    if not ok:
        validation_errors["savings_per_month"] = err
    elif val < 0:
        validation_errors["savings_per_month"] = "Savings per month cannot be negative."
    else:
        parsed_data["savings_per_month"] = val

    # 6. emergency_fund_amount
    ok, val, err = _sanitize_and_parse_number_str(emergency_fund_amount_str)
    if not ok:
        validation_errors["emergency_fund_amount"] = err
    elif val < 0:
        validation_errors["emergency_fund_amount"] = "Emergency fund total cannot be negative."
    else:
        parsed_data["emergency_fund_amount"] = val

    # 7. has_life_insurance
    ok, life_flag, err = _parse_yes_no_flag(has_life_insurance_str, "has_life_insurance")
    if not ok:
        validation_errors["has_life_insurance"] = err
    else:
        parsed_data["has_life_insurance"] = life_flag

    # 8. has_health_insurance
    ok, health_flag, err = _parse_yes_no_flag(has_health_insurance_str, "has_health_insurance")
    if not ok:
        validation_errors["has_health_insurance"] = err
    else:
        parsed_data["has_health_insurance"] = health_flag
        
    # --- Final result ---
    if validation_errors:
        error_msg = json.dumps(validation_errors, indent=2)
        logger.warning("Batch validation failed. Errors: %s", error_msg)
        return _error_dict(f"Validation failed for some fields. Errors: {error_msg}")
    
    logger.info("Batch validation successful.")
    return _success_dict(parsed_data)

# ------------- End of module ------------- #