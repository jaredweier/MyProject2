"""Pay-code rules, pay calculation, OT→comp conversion."""

"""Payroll entries, timecard, and pay-period management."""

import json
from typing import Dict, Optional

from config import (
    CALLBACK_MINIMUM_HOURS,
    DEFAULT_PAY_CODE_RULES,
    PAY_CODE_SETTINGS_KEY,
)
from logic.operations import get_department_setting, set_department_setting
from logic.users import log_audit_action
from models import PayCalculationResult
from validators import (
    format_pay_code_formula,
    validate_pay_code_comp_ratio,
    validate_pay_code_rate_multiplier,
)


def get_pay_code_rules() -> Dict:
    """Return merged department pay-code calculation rules."""
    stored: Dict = {}
    raw = get_department_setting(PAY_CODE_SETTINGS_KEY, "")
    if raw:
        try:
            stored = json.loads(raw)
        except json.JSONDecodeError:
            stored = {}

    global_cfg = dict(DEFAULT_PAY_CODE_RULES.get("global") or {})
    global_cfg.update(stored.get("global") or {})
    try:
        global_cfg["callback_minimum_hours"] = float(global_cfg.get("callback_minimum_hours", CALLBACK_MINIMUM_HOURS))
        global_cfg["default_overtime_multiplier"] = float(global_cfg.get("default_overtime_multiplier", 1.5))
    except (TypeError, ValueError):
        global_cfg["callback_minimum_hours"] = CALLBACK_MINIMUM_HOURS
        global_cfg["default_overtime_multiplier"] = 1.5

    codes: Dict[str, Dict] = {}
    stored_codes = stored.get("codes") or {}
    for entry_type, default in (DEFAULT_PAY_CODE_RULES.get("codes") or {}).items():
        merged = dict(default)
        merged.update(stored_codes.get(entry_type) or {})
        merged["rate_multiplier"] = float(merged.get("rate_multiplier", 1.0))
        merged["comp_bank_credit_ratio"] = float(merged.get("comp_bank_credit_ratio", 0.0) or 0.0)
        merged["premium_multiplier"] = float(merged.get("premium_multiplier", 0.0) or 0.0)
        merged["paid"] = bool(merged.get("paid", True))
        merged["formula"] = format_pay_code_formula(entry_type, merged)
        codes[entry_type] = merged

    return {"success": True, "global": global_cfg, "codes": codes}


def save_pay_code_rules(rules: Dict, user_id: Optional[int] = None) -> Dict:
    """Persist pay-code multipliers and global payroll calculation settings."""
    incoming_global = rules.get("global") or {}
    incoming_codes = rules.get("codes") or {}
    current = get_pay_code_rules()

    global_cfg = dict(current.get("global") or {})
    try:
        if "callback_minimum_hours" in incoming_global:
            hours = float(incoming_global["callback_minimum_hours"])
            if hours < 0 or hours > 24:
                return {"success": False, "message": "Callback minimum must be between 0 and 24 hours"}
            global_cfg["callback_minimum_hours"] = hours
        if "default_overtime_multiplier" in incoming_global:
            mult = float(incoming_global["default_overtime_multiplier"])
            check = validate_pay_code_rate_multiplier(mult, "Default overtime")
            if not check.ok:
                return {"success": False, "message": check.message}
            global_cfg["default_overtime_multiplier"] = mult
    except (TypeError, ValueError):
        return {"success": False, "message": "Global pay settings must be numeric"}

    codes: Dict[str, Dict] = {}
    for entry_type, default in (DEFAULT_PAY_CODE_RULES.get("codes") or {}).items():
        merged = dict(current["codes"].get(entry_type) or default)
        if entry_type in incoming_codes:
            merged.update(incoming_codes[entry_type] or {})
        try:
            rate_mult = float(merged.get("rate_multiplier", 1.0))
            comp_ratio = float(merged.get("comp_bank_credit_ratio", 0.0) or 0.0)
            premium = float(merged.get("premium_multiplier", 0.0) or 0.0)
        except (TypeError, ValueError):
            return {"success": False, "message": f"{entry_type}: numeric fields required"}

        for check in (
            validate_pay_code_rate_multiplier(rate_mult, entry_type),
            validate_pay_code_comp_ratio(comp_ratio, entry_type),
        ):
            if not check.ok:
                return {"success": False, "message": check.message}
        if premium < 0 or premium > 10:
            return {"success": False, "message": f"{entry_type}: premium multiplier must be between 0 and 10"}

        codes[entry_type] = {
            "rate_multiplier": round(rate_mult, 3),
            "paid": bool(merged.get("paid", True)),
            "comp_bank_credit_ratio": round(comp_ratio, 3),
            "debit_comp_bank": bool(merged.get("debit_comp_bank")),
            "debit_sick_bank": bool(merged.get("debit_sick_bank")),
            "debit_float_holiday_bank": bool(merged.get("debit_float_holiday_bank")),
            "debit_holiday_bank": bool(merged.get("debit_holiday_bank")),
            "uses_callback_minimum": bool(merged.get("uses_callback_minimum")),
            "premium_multiplier": round(premium, 3),
            "counts_as_overtime": bool(merged.get("counts_as_overtime")),
        }

    payload = {"global": global_cfg, "codes": codes}
    result = set_department_setting(PAY_CODE_SETTINGS_KEY, json.dumps(payload), user_id=user_id)
    if not result.get("success"):
        return result
    log_audit_action("payroll.pay_code_rules", "payroll", None, user_id, "updated")
    return {"success": True, "message": "Pay code calculations saved", "rules": get_pay_code_rules()}


def calculate_pay_for_entry(
    entry_type: str,
    hours: float,
    base_rate: float,
    night_differential_hours: float = 0.0,
    night_differential_rate: float = 1.0,
    is_holiday_overtime: bool = False,
    banks: Optional[Dict] = None,
) -> PayCalculationResult:
    from validators import validate_comp_time_cap

    result = PayCalculationResult(entry_type=entry_type)
    banks = banks or {}
    rules = get_pay_code_rules()
    code = rules.get("codes", {}).get(entry_type)
    if not code:
        result.message = f"Unknown payroll entry type: {entry_type}"
        return result

    global_cfg = rules.get("global") or {}
    calc_hours = hours
    if code.get("uses_callback_minimum"):
        from logic.labor_compliance import callback_payable_hours

        calc_hours = callback_payable_hours(
            hours,
            float(global_cfg.get("callback_minimum_hours", CALLBACK_MINIMUM_HOURS)),
        )

    if code.get("debit_comp_bank") and banks.get("comp_hours", 0) < calc_hours:
        result.message = f"Insufficient comp bank ({banks.get('comp_hours', 0):.1f}h available)"
        return result
    if code.get("debit_sick_bank") and banks.get("sick_hours", 0) < calc_hours:
        result.message = f"Insufficient sick bank ({banks.get('sick_hours', 0):.1f}h available)"
        return result
    if code.get("debit_float_holiday_bank") and banks.get("float_holiday_hours", 0) < calc_hours:
        result.message = f"Insufficient float holiday bank ({banks.get('float_holiday_hours', 0):.1f}h available)"
        return result
    if code.get("debit_holiday_bank") and banks.get("holiday_hours", 0) < calc_hours:
        result.message = f"Insufficient holiday bank ({banks.get('holiday_hours', 0):.1f}h available)"
        return result

    rate_mult = float(code.get("rate_multiplier", 1.0))
    if entry_type == "Holiday Overtime" and is_holiday_overtime:
        premium = float(code.get("premium_multiplier") or 0.0)
        if premium > 0:
            rate_mult = premium

    if code.get("paid", True) and rate_mult > 0:
        # Optional blended rate for OT (department setting flsa_use_blended_rate)
        rate_for_pay = base_rate
        if code.get("counts_as_overtime"):
            try:
                from logic.operations import get_department_setting

                if get_department_setting("flsa_use_blended_rate", "0").strip() in (
                    "1",
                    "true",
                    "yes",
                    "on",
                ):
                    rate_for_pay = blended_regular_rate(
                        base_rate,
                        night_differential_hours=night_differential_hours,
                        total_hours=max(hours, calc_hours, 1.0),
                        night_differential_rate=night_differential_rate,
                    )
            except Exception:
                rate_for_pay = base_rate
        pay_amount = round(calc_hours * rate_for_pay * rate_mult, 2)
        if code.get("counts_as_overtime"):
            result.overtime_hours = calc_hours
            result.overtime_pay = pay_amount
            result.total_pay = pay_amount
        else:
            result.regular_hours = calc_hours
            result.base_pay = pay_amount
            result.total_pay = pay_amount
    else:
        result.regular_hours = calc_hours
        result.total_pay = 0.0

    credit_ratio = float(code.get("comp_bank_credit_ratio", 0.0) or 0.0)
    if credit_ratio > 0:
        comp_delta = round(calc_hours * credit_ratio, 2)
        cap_check = validate_comp_time_cap(banks.get("comp_hours", 0), comp_delta)
        if not cap_check.ok:
            result.message = cap_check.message
            return result
        result.comp_bank_delta = comp_delta

    if code.get("debit_comp_bank"):
        result.comp_bank_delta = -calc_hours
    if code.get("debit_sick_bank"):
        result.sick_bank_delta = -calc_hours
    if code.get("debit_float_holiday_bank"):
        result.float_holiday_bank_delta = -calc_hours
    if code.get("debit_holiday_bank"):
        result.holiday_bank_delta = -calc_hours

    from logic.payroll.timecard import _apply_night_differential

    _apply_night_differential(result, night_differential_hours, base_rate, night_differential_rate)
    return result


def blended_regular_rate(
    base_rate: float,
    *,
    night_differential_hours: float = 0.0,
    total_hours: float = 0.0,
    night_differential_rate: float = 1.0,
    specialty_premium: float = 0.0,
) -> float:
    """
    FLSA-style blended regular rate (Netchex / public-sector pattern).

    Approximate: (straight pay + night premium pay + specialty) / hours.
    Not legal advice — agencies must validate against counsel/CBA.
    """
    try:
        base = float(base_rate or 0)
        th = float(total_hours or 0)
        ndh = float(night_differential_hours or 0)
        ndr = float(night_differential_rate or 1.0)
        spec = float(specialty_premium or 0)
    except (TypeError, ValueError):
        return float(base_rate or 0)
    if th <= 0:
        return round(base, 4)
    # Night diff often paid as extra fraction of base on night hours
    night_premium = max(0.0, ndh) * base * max(0.0, ndr - 1.0)
    straight = th * base
    blended = (straight + night_premium + max(0.0, spec)) / th
    return round(blended, 4)


def convert_overtime_to_comp(
    officer_id: int,
    entry_date: str,
    hours: float,
    *,
    notes: str = "OT converted to comp (NEOGOV-style election)",
    night_differential_hours: float = 0.0,
) -> Dict:
    """
    Public-sector cash→comp election: bank OT hours as Comp Earned instead of cash OT.

    Mirrors NEOGOV timesheet 'convert overtime to compensation time' control.
    Uses existing pay-code rules (Comp Earned / Comp Time Earned).
    """
    if hours <= 0:
        return {"success": False, "message": "Hours must be greater than zero"}
    rules = get_pay_code_rules() or {}
    codes = rules.get("codes") or {}
    entry_type = "Comp Earned" if "Comp Earned" in codes else "Comp Time Earned"
    if entry_type not in codes and "Comp Earned" not in codes:
        # Fall back to any code with positive comp credit
        for name, cfg in codes.items():
            if float((cfg or {}).get("comp_bank_credit_ratio") or 0) > 0:
                entry_type = name
                break
        else:
            return {"success": False, "message": "No Comp Earned pay code configured"}
    note = (notes or "").strip() or "OT converted to comp"
    from logic.payroll.entries import create_payroll_entry

    result = create_payroll_entry(
        officer_id,
        entry_date,
        entry_type,
        hours,
        night_differential_hours=night_differential_hours,
        notes=note,
    )
    if result.get("success"):
        result["converted"] = True
        result["entry_type"] = entry_type
        result["message"] = result.get("message") or f"Converted {hours}h OT → {entry_type}"
    return result
