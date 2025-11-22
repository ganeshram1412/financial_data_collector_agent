import json
import math
import re
import logging  # Import the logging module
from typing import Dict, Any, List, Tuple, Optional

# --- Logging Setup ---
# The logger setup remains exactly as specified to ensure log continuity.
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------- Helpers ---------------- #

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
    # Pattern: [optional sign][zero or more digits][optional dot][zero or more digits] [optional k/K/m/M]
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
    Helper to parse complex inputs (EMI, Commitments, Investments, Assets, Dependents) 
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

# ---------------- Individual tools ---------------- #

def annual_income(input_str: str) -> Dict[str, str]:
    """Parse and validate annual gross income. Must be > 0."""
    logger.info("Tool called: annual_income. Raw input: '%s'", input_str)
    ok, val, err = _sanitize_and_parse_number_str(input_str)
    
    if not ok:
        logger.warning("annual_income failed validation: %s", err)
        return _error_dict(err)
        
    if val <= 0:
        logger.warning("annual_income rejected: Value %.2f must be > 0.", val)
        return _error_dict("Annual income must be greater than 0.")
        
    result = {"annual_income": val}
    logger.info("annual_income success. Parsed value: %.2f", val)
    return _success_dict(result)

def monthly_net_income(input_str: str) -> Dict[str, str]:
    """Parse and validate monthly net (take-home) income. Must be > 0."""
    logger.info("Tool called: monthly_net_income. Raw input: '%s'", input_str)
    ok, val, err = _sanitize_and_parse_number_str(input_str)
    
    if not ok:
        logger.warning("monthly_net_income failed validation: %s", err)
        return _error_dict(err)
        
    if val <= 0:
        logger.warning("monthly_net_income rejected: Value %.2f must be > 0.", val)
        return _error_dict("Monthly net income must be greater than 0.")
        
    result = {"monthly_net_income": val}
    logger.info("monthly_net_income success. Parsed value: %.2f", val)
    return _success_dict(result)

def bonus_variable_income(input_str: str) -> Dict[str, str]:
    """Parse bonus/variable income. Must be non-negative (>= 0)."""
    logger.info("Tool called: bonus_variable_income. Raw input: '%s'", input_str)
    ok, val, err = _sanitize_and_parse_number_str(input_str)
    
    if not ok:
        logger.warning("bonus_variable_income failed validation: %s", err)
        return _error_dict(err)
        
    if val < 0:
        logger.warning("bonus_variable_income rejected: Value %.2f must be non-negative.", val)
        return _error_dict("Bonus/variable income must be non-negative.")
        
    result = {"bonus_variable_income": val}
    logger.info("bonus_variable_income success. Parsed value: %.2f", val)
    return _success_dict(result)

def total_outstanding_debt(input_str: str) -> Dict[str, str]:
    """Parse total outstanding debt. Must be non-negative (>= 0)."""
    logger.info("Tool called: total_outstanding_debt. Raw input: '%s'", input_str)
    ok, val, err = _sanitize_and_parse_number_str(input_str)
    
    if not ok:
        logger.warning("total_outstanding_debt failed validation: %s", err)
        return _error_dict(err)
        
    if val < 0:
        logger.warning("total_outstanding_debt rejected: Value %.2f must be non-negative.", val)
        return _error_dict("Total outstanding debt must be non-negative.")
        
    result = {"total_outstanding_debt": val}
    logger.info("total_outstanding_debt success. Parsed value: %.2f", val)
    return _success_dict(result)

def monthly_emi_per_debt_type(input_str: str) -> Dict[str, str]:
    """Parse monthly EMI per debt type (JSON or pairs). Must be non-negative (>= 0)."""
    logger.info("Tool called: monthly_emi_per_debt_type. Raw input: '%s'", input_str)
    
    ok, items, total, err = _parse_multi_item_list(input_str, non_negative_check=True)
    
    if not ok:
        logger.warning("monthly_emi_per_debt_type failed validation: %s", err)
        return _error_dict(err)

    # Use 'type' for the name of the EMI debt
    result = {"emis": items, "total_emi": total}
    logger.info("monthly_emi_per_debt_type success. Total EMI: %.2f", total)
    return _success_dict(result)

def monthly_commitments(input_str: str) -> Dict[str, str]:
    """Parse monthly commitments (expenses). Must be non-negative (>= 0)."""
    logger.info("Tool called: monthly_commitments. Raw input: '%s'", input_str)
    
    # We use 'type' for the parsing helper, but rename to 'item' in the final result 
    ok, items, total, err = _parse_multi_item_list(input_str, non_negative_check=True)

    if not ok:
        logger.warning("monthly_commitments failed validation: %s", err)
        return _error_dict(err)

    # Remap 'type' key from parser output to 'item' for final output structure
    commitment_items = [{"item": i['type'], "amount": i['amount']} for i in items]
    
    result = {"commitments": commitment_items, "total": total}
    logger.info("monthly_commitments success. Total commitments: %.2f", total)
    return _success_dict(result)

def savings_per_month(input_str: str) -> Dict[str, str]:
    """Parse monthly savings amount. Must be non-negative (>= 0)."""
    logger.info("Tool called: savings_per_month. Raw input: '%s'", input_str)
    ok, val, err = _sanitize_and_parse_number_str(input_str)
    
    if not ok:
        logger.warning("savings_per_month failed validation: %s", err)
        return _error_dict(err)
        
    if val < 0:
        logger.warning("savings_per_month rejected: Value %.2f must be non-negative.", val)
        return _error_dict("Savings per month cannot be negative.")
        
    result = {"savings_per_month": val}
    logger.info("savings_per_month success. Parsed value: %.2f", val)
    return _success_dict(result)

def emergency_fund_amount(input_str: str) -> Dict[str, str]:
    """Parse emergency fund amount (total saved). Must be non-negative (>= 0)."""
    logger.info("Tool called: emergency_fund_amount. Raw input: '%s'", input_str)
    ok, val, err = _sanitize_and_parse_number_str(input_str)
    
    if not ok:
        logger.warning("emergency_fund_amount failed validation: %s", err)
        return _error_dict(err)
        
    if val < 0:
        logger.warning("emergency_fund_amount rejected: Value %.2f must be non-negative.", val)
        return _error_dict("Emergency fund amount cannot be negative.")
        
    result = {"emergency_fund_amount": val}
    logger.info("emergency_fund_amount success. Parsed value: %.2f", val)
    return _success_dict(result)

def investment_contributions(input_str: str) -> Dict[str, str]:
    """Parse investment contributions (JSON or pairs). Must be non-negative (>= 0)."""
    logger.info("Tool called: investment_contributions. Raw input: '%s'", input_str)
    
    ok, items, total, err = _parse_multi_item_list(input_str, non_negative_check=True)
    
    if not ok:
        logger.warning("investment_contributions failed validation: %s", err)
        return _error_dict(err)

    result = {"investments": items, "total": total}
    logger.info("investment_contributions success. Total contributions: %.2f", total)
    return _success_dict(result)

def assets(input_str: str) -> Dict[str, str]:
    """Parse assets (JSON or pairs). Must be non-negative (>= 0)."""
    logger.info("Tool called: assets. Raw input: '%s'", input_str)
    
    ok, items, total, err = _parse_multi_item_list(input_str, non_negative_check=True)

    if not ok:
        logger.warning("assets failed validation: %s", err)
        return _error_dict(err)

    result = {"assets": items, "total": total}
    logger.info("assets success. Total assets: %.2f", total)
    return _success_dict(result)

def dependents_expense(input_str: str) -> Dict[str, str]:
    """Parse monthly expenses for dependents (JSON or pairs). Must be non-negative (>= 0)."""
    logger.info("Tool called: dependents_expense. Raw input: '%s'", input_str)

    # Use 'type' for the parsing helper, but rename to 'dependent' in the final result
    ok, items, total, err = _parse_multi_item_list(input_str, non_negative_check=True)
    
    if not ok:
        logger.warning("dependents_expense failed validation: %s", err)
        return _error_dict(err)
        
    # Remap 'type' key from parser output to 'dependent' for final output structure
    dependent_items = [{"dependent": i['type'], "amount": i['amount']} for i in items]

    result = {"dependents_expense": dependent_items, "total": total}
    logger.info("dependents_expense success. Total expense: %.2f", total)
    return _success_dict(result)

# ------------- End of module ------------- #