import json
import math
import re
import logging
from typing import Dict, Any, List, Tuple, Optional

# --- Logging Setup ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------- Helpers (Kept Intact) ---------------- #

def _sanitize_and_parse_number_str(s: str) -> Tuple[bool, Optional[float], str]:
    """
    Cleans and parses a string into a float, handling currency, commas, 
    and 'k'/'M' suffixes.
    Returns (ok: bool, value: float or None, err_msg: str).
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
    """Wraps structured data as a JSON string for tool output."""
    return {"status": "success", "data": json.dumps(data_obj, separators=(",", ":"))}

def _error_dict(msg: str) -> Dict[str, str]:
    """Creates a standardized error dictionary."""
    return {"status": "error", "error_message": str(msg)}

def _parse_multi_item_list(input_str: str, non_negative_check: bool = True) -> Tuple[bool, List[Dict[str, float]], float, str]:
    """
    Helper to parse complex inputs (EMI, Commitments, Investments) 
    which can be JSON, key:value pairs, or a list of amounts.
    Returns (ok: bool, items: List[Dict], total: float, err_msg: str).
    """
    raw = input_str.strip()
    items = []
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
        # Handle comma/semicolon separated list or key:value pairs
        parts = [p.strip() for p in re.split(r'[,\n;]+', raw) if p.strip()]
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

# ---------------- Single Comprehensive Tool ---------------- #

def validate_all_essential_data(
    monthly_net_income_str: str,
    monthly_commitments_str: str,
    monthly_emi_str: str,
    investment_contributions_str: str,
    savings_per_month_str: str,
    emergency_fund_amount_str: str
) -> Dict[str, str]:
    """
    Validates and parses all 6 essential financial fields in a single call.
    """
    logger.info("Tool called: validate_all_essential_data. Starting batch validation.")
    
    parsed_data = {}
    validation_errors = {}
    
    # 1. monthly_net_income
    ok, val, err = _sanitize_and_parse_number_str(monthly_net_income_str)
    if not ok or val <= 0:
        validation_errors['monthly_net_income'] = err if ok else "Monthly net income must be greater than 0."
    else:
        parsed_data['monthly_net_income'] = val

    # 2. monthly_commitments
    ok, items, total, err = _parse_multi_item_list(monthly_commitments_str, non_negative_check=True)
    if not ok:
        validation_errors['monthly_commitments'] = err
    else:
        parsed_data['commitments'] = items
        parsed_data['total_commitments'] = total

    # 3. monthly_emi_per_debt_type
    ok, items, total, err = _parse_multi_item_list(monthly_emi_str, non_negative_check=True)
    if not ok:
        validation_errors['monthly_emi_per_debt_type'] = err
    else:
        parsed_data['emis'] = items
        parsed_data['total_emi'] = total
        
    # 4. investment_contributions
    ok, items, total, err = _parse_multi_item_list(investment_contributions_str, non_negative_check=True)
    if not ok:
        validation_errors['investment_contributions'] = err
    else:
        parsed_data['investments'] = items
        parsed_data['total_investment_contributions'] = total

    # 5. savings_per_month
    ok, val, err = _sanitize_and_parse_number_str(savings_per_month_str)
    if not ok or val < 0:
        validation_errors['savings_per_month'] = err if ok else "Savings per month cannot be negative."
    else:
        parsed_data['savings_per_month'] = val

    # 6. emergency_fund_amount
    ok, val, err = _sanitize_and_parse_number_str(emergency_fund_amount_str)
    if not ok or val < 0:
        validation_errors['emergency_fund_amount'] = err if ok else "Emergency fund total cannot be negative."
    else:
        parsed_data['emergency_fund_amount'] = val
        
    if validation_errors:
        error_msg = json.dumps(validation_errors, indent=2)
        logger.warning("Batch validation failed. Errors: %s", error_msg)
        return _error_dict(f"Validation failed for some fields. Errors: {error_msg}")
    
    logger.info("Batch validation successful.")
    return _success_dict(parsed_data)

# ------------- End of module ------------- #