import json
from typing import Dict, List, Any, Optional

from typing import Dict, Any

# tools_financial_strstr.py
import json
import math
import re
from typing import Dict, Any, List, Tuple, Optional

# ---------------- Helpers ---------------- #
_NUM_RE = re.compile(r"^[-+]?[0-9\,\.kKmM]+$")

def _sanitize_and_parse_number_str(s: str) -> Tuple[bool, Optional[float], str]:
    """
    Clean common formatting and parse into float.
    Returns (ok, value_or_none, err_msg_or_empty).
    Accepts suffixes: k (thousand), m (million) case-insensitive.
    """
    if s is None:
        return False, None, "No value provided"
    raw = s.strip()
    if raw == "":
        return False, None, "Empty input"

    # allow commas, currency symbols and suffixes
    cleaned = raw.replace(",", "").replace("₹", "").replace("$", "").replace(" ", "")
    # suffix handling
    m = re.match(r"^([-+]?[0-9]*\.?[0-9]+)([kKmM])?$", cleaned)
    if not m:
        return False, None, f"Unrecognized numeric format: '{s}'"
    num_part = m.group(1)
    suffix = (m.group(2) or "").lower()
    try:
        val = float(num_part)
    except Exception as e:
        return False, None, f"Could not parse number part: {e}"
    if suffix == "k":
        val *= 1_000.0
    elif suffix == "m":
        val *= 1_000_000.0
    if math.isnan(val) or math.isinf(val):
        return False, None, "Parsed value is not finite"
    return True, val, ""

def _success_dict(data_obj: Any) -> Dict[str, str]:
    """Wrap structured data as JSON string under 'data' key; both keys+values are strings."""
    return {"status": "success", "data": json.dumps(data_obj, separators=(",", ":"))}

def _error_dict(msg: str) -> Dict[str, str]:
    return {"status": "error", "error_message": str(msg)}

# ---------------- Individual tools ---------------- #
def annual_income(input_str: str) -> Dict[str, str]:
    """
    Parse and validate annual gross income.
    Input: string (e.g., "1200000", "12,00,000", "1.2M", "85k")
    Output (success): {"status":"success","data":"{\"annual_income\":1200000.0}"}
    """
    ok, val, err = _sanitize_and_parse_number_str(input_str)
    if not ok:
        return _error_dict(err)
    if val <= 0:
        return _error_dict("Annual income must be greater than 0.")
    return _success_dict({"annual_income": round(val, 2)})

def monthly_net_income(input_str: str) -> Dict[str, str]:
    """
    Parse and validate monthly net (take-home) income.
    """
    ok, val, err = _sanitize_and_parse_number_str(input_str)
    if not ok:
        return _error_dict(err)
    if val <= 0:
        return _error_dict("Monthly net income must be greater than 0.")
    return _success_dict({"monthly_net_income": round(val, 2)})

def bonus_variable_income(input_str: str) -> Dict[str, str]:
    """
    Parse bonus/variable income. Accepts annual or monthly bonus formats.
    Returns parsed value and a note about frequency if provided (optional).
    """
    # We'll accept same numeric formats; agent can ask frequency separately if needed.
    ok, val, err = _sanitize_and_parse_number_str(input_str)
    if not ok:
        return _error_dict(err)
    if val < 0:
        return _error_dict("Bonus/variable income must be non-negative.")
    return _success_dict({"bonus_variable_income": round(val, 2)})

def total_outstanding_debt(input_str: str) -> Dict[str, str]:
    """
    Parse total outstanding debt. Zero is allowed.
    """
    ok, val, err = _sanitize_and_parse_number_str(input_str)
    if not ok:
        return _error_dict(err)
    if val < 0:
        return _error_dict("Total outstanding debt must be non-negative.")
    return _success_dict({"total_outstanding_debt": round(val, 2)})

def monthly_emi_per_debt_type(input_str: str) -> Dict[str, str]:
    """
    Parse monthly EMI per debt type.
    Accepted input forms (as string):
      - JSON object: {"home_loan":15000,"personal_loan":5000}
      - Comma-separated pairs: "home_loan:15000, personal_loan:5000"
    Output 'data' is JSON string of {"emis":[{"type":"home_loan","amount":15000.0}, ...], "total_emi": ...}
    """
    raw = input_str.strip()
    items = []
    total = 0.0

    # Try JSON object
    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
            if not isinstance(obj, dict):
                return _error_dict("EMI JSON must be an object of type: amount pairs")
            for k, v in obj.items():
                ok, amt, err = _sanitize_and_parse_number_str(str(v))
                if not ok:
                    return _error_dict(f"Invalid amount for '{k}': {err}")
                if amt < 0:
                    return _error_dict(f"EMI for '{k}' must be non-negative")
                items.append({"type": str(k), "amount": round(amt, 2)})
                total += amt
        except Exception as e:
            return _error_dict(f"Invalid JSON for EMI: {e}")
    else:
        # comma-separated pairs
        parts = [p.strip() for p in re.split(r'[,\n;]+', raw) if p.strip()]
        if not parts:
            return _error_dict("No EMI items provided")
        for part in parts:
            if ":" in part:
                name, amt_raw = part.split(":", 1)
                ok, amt, err = _sanitize_and_parse_number_str(amt_raw)
                if not ok:
                    return _error_dict(f"Invalid amount for '{name}': {err}")
                if amt < 0:
                    return _error_dict(f"EMI for '{name}' must be non-negative")
                items.append({"type": name.strip(), "amount": round(amt, 2)})
                total += amt
            else:
                # unnamed EMI entry -> treat as item_n
                ok, amt, err = _sanitize_and_parse_number_str(part)
                if not ok:
                    return _error_dict(f"Invalid EMI value: {err}")
                items.append({"type": f"item_{len(items)}", "amount": round(amt, 2)})
                total += amt

    return _success_dict({"emis": items, "total_emi": round(total, 2)})

def monthly_commitments(input_str: str) -> Dict[str, str]:
    """
    Parse monthly commitments (expenses).
    Accepts JSON object or comma-separated name:amount pairs or plain amounts.
    Returns {'commitments':[...], 'total':...}
    """
    raw = input_str.strip()
    if raw == "":
        return _success_dict({"commitments": [], "total": 0.0})

    items = []
    total = 0.0

    # JSON object/array attempt
    if raw.startswith("{") or raw.startswith("["):
        try:
            obj = json.loads(raw)
        except Exception as e:
            return _error_dict(f"Invalid JSON for commitments: {e}")
        # dict form
        if isinstance(obj, dict):
            for k, v in obj.items():
                ok, amt, err = _sanitize_and_parse_number_str(str(v))
                if not ok:
                    return _error_dict(f"Invalid amount for '{k}': {err}")
                if amt < 0:
                    return _error_dict(f"Commitment '{k}' must be non-negative")
                items.append({"item": str(k), "amount": round(amt, 2)})
                total += amt
        elif isinstance(obj, list):
            for idx, entry in enumerate(obj):
                if isinstance(entry, (int, float)):
                    amt = float(entry)
                    if amt < 0:
                        return _error_dict(f"Commitment at index {idx} must be non-negative")
                    items.append({"item": f"item_{idx}", "amount": round(amt, 2)})
                    total += amt
                elif isinstance(entry, dict):
                    name = entry.get("name") or entry.get("item") or f"item_{idx}"
                    ok, amt, err = _sanitize_and_parse_number_str(str(entry.get("amount", "")))
                    if not ok:
                        return _error_dict(f"Invalid amount at index {idx}: {err}")
                    if amt < 0:
                        return _error_dict(f"Commitment at index {idx} must be non-negative")
                    items.append({"item": str(name), "amount": round(amt, 2)})
                    total += amt
                else:
                    return _error_dict("Unsupported commitment list entry type")
        else:
            return _error_dict("Commitments JSON must be an object or array")
    else:
        parts = [p.strip() for p in re.split(r'[,\n;]+', raw) if p.strip()]
        for idx, part in enumerate(parts):
            if ":" in part:
                name, amt_raw = part.split(":", 1)
                ok, amt, err = _sanitize_and_parse_number_str(amt_raw)
                if not ok:
                    return _error_dict(f"Invalid amount for '{name}': {err}")
                if amt < 0:
                    return _error_dict(f"Commitment '{name}' must be non-negative")
                items.append({"item": name.strip(), "amount": round(amt, 2)})
                total += amt
            else:
                ok, amt, err = _sanitize_and_parse_number_str(part)
                if not ok:
                    return _error_dict(f"Invalid commitment amount: {err}")
                items.append({"item": f"item_{idx}", "amount": round(amt, 2)})
                total += amt

    return _success_dict({"commitments": items, "total": round(total, 2)})

def savings_per_month(input_str: str) -> Dict[str, str]:
    """
    Parse monthly savings amount.
    """
    ok, val, err = _sanitize_and_parse_number_str(input_str)
    if not ok:
        return _error_dict(err)
    if val < 0:
        return _error_dict("Savings per month cannot be negative.")
    return _success_dict({"savings_per_month": round(val, 2)})

def emergency_fund_amount(input_str: str) -> Dict[str, str]:
    """
    Parse emergency fund amount (total saved).
    """
    ok, val, err = _sanitize_and_parse_number_str(input_str)
    if not ok:
        return _error_dict(err)
    if val < 0:
        return _error_dict("Emergency fund amount cannot be negative.")
    return _success_dict({"emergency_fund_amount": round(val, 2)})

def investment_contributions(input_str: str) -> Dict[str, str]:
    """
    Parse investment contributions. Accepts:
      - JSON object: {"SIP":5000,"NPS":2000}
      - comma pairs: "SIP:5000, NPS:2000"
    """
    raw = input_str.strip()
    items = []
    total = 0.0

    if raw == "":
        return _success_dict({"investments": [], "total": 0.0})

    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
            if not isinstance(obj, dict):
                return _error_dict("Investments JSON must be an object")
            for k, v in obj.items():
                ok, amt, err = _sanitize_and_parse_number_str(str(v))
                if not ok:
                    return _error_dict(f"Invalid amount for '{k}': {err}")
                if amt < 0:
                    return _error_dict(f"Investment '{k}' must be non-negative")
                items.append({"type": str(k), "amount": round(amt, 2)})
                total += amt
        except Exception as e:
            return _error_dict(f"Invalid JSON for investments: {e}")
    else:
        parts = [p.strip() for p in re.split(r'[,\n;]+', raw) if p.strip()]
        for part in parts:
            if ":" in part:
                name, amt_raw = part.split(":", 1)
                ok, amt, err = _sanitize_and_parse_number_str(amt_raw)
                if not ok:
                    return _error_dict(f"Invalid amount for '{name}': {err}")
                items.append({"type": name.strip(), "amount": round(amt, 2)})
                total += amt
            else:
                ok, amt, err = _sanitize_and_parse_number_str(part)
                if not ok:
                    return _error_dict(err)
                items.append({"type": f"item_{len(items)}", "amount": round(amt, 2)})
                total += amt

    return _success_dict({"investments": items, "total": round(total, 2)})

def assets(input_str: str) -> Dict[str, str]:
    """
    Parse assets (cash, FD, MF, equity, gold). Accept JSON or pairs.
    """
    # reuse parse logic similar to investments/commitments
    raw = input_str.strip()
    if raw == "":
        return _success_dict({"assets": [], "total": 0.0})

    items = []
    total = 0.0
    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
            if not isinstance(obj, dict):
                return _error_dict("Assets JSON must be an object")
            for k, v in obj.items():
                ok, amt, err = _sanitize_and_parse_number_str(str(v))
                if not ok:
                    return _error_dict(f"Invalid amount for '{k}': {err}")
                if amt < 0:
                    return _error_dict(f"Asset value for '{k}' must be non-negative")
                items.append({"type": str(k), "amount": round(amt, 2)})
                total += amt
        except Exception as e:
            return _error_dict(f"Invalid JSON for assets: {e}")
    else:
        parts = [p.strip() for p in re.split(r'[,\n;]+', raw) if p.strip()]
        for idx, part in enumerate(parts):
            if ":" in part:
                name, amt_raw = part.split(":", 1)
                ok, amt, err = _sanitize_and_parse_number_str(amt_raw)
                if not ok:
                    return _error_dict(f"Invalid amount for '{name}': {err}")
                items.append({"type": name.strip(), "amount": round(amt, 2)})
                total += amt
            else:
                ok, amt, err = _sanitize_and_parse_number_str(part)
                if not ok:
                    return _error_dict(err)
                items.append({"type": f"item_{idx}", "amount": round(amt, 2)})
                total += amt

    return _success_dict({"assets": items, "total": round(total, 2)})

def dependents_expense(input_str: str) -> Dict[str, str]:
    """
    Parse monthly expenses for dependents (parents/children). Accept JSON or pairs.
    """
    raw = input_str.strip()
    if raw == "":
        return _success_dict({"dependents_expense": [], "total": 0.0})

    items = []
    total = 0.0
    # JSON or pairs similar to commitments
    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
            if not isinstance(obj, dict):
                return _error_dict("Dependents JSON must be an object")
            for k, v in obj.items():
                ok, amt, err = _sanitize_and_parse_number_str(str(v))
                if not ok:
                    return _error_dict(f"Invalid amount for '{k}': {err}")
                if amt < 0:
                    return _error_dict(f"Dependents expense for '{k}' must be non-negative")
                items.append({"dependent": str(k), "amount": round(amt, 2)})
                total += amt
        except Exception as e:
            return _error_dict(f"Invalid JSON for dependents: {e}")
    else:
        parts = [p.strip() for p in re.split(r'[,\n;]+', raw) if p.strip()]
        for idx, part in enumerate(parts):
            if ":" in part:
                name, amt_raw = part.split(":", 1)
                ok, amt, err = _sanitize_and_parse_number_str(amt_raw)
                if not ok:
                    return _error_dict(f"Invalid amount for '{name}': {err}")
                items.append({"dependent": name.strip(), "amount": round(amt, 2)})
                total += amt
            else:
                ok, amt, err = _sanitize_and_parse_number_str(part)
                if not ok:
                    return _error_dict(err)
                items.append({"dependent": f"dependent_{idx}", "amount": round(amt, 2)})
                total += amt

    return _success_dict({"dependents_expense": items, "total": round(total, 2)})

# ------------- End of module ------------- #