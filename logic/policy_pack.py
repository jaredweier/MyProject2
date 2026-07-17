"""CBA / department policy pack — versioned export/import for union review.

Collects scheduling, bump, OT fill, rest, night min, cascade, FLSA dual, and
coverage window knobs into one JSON document. Does not invent new defaults:
reads live department settings and config.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from logic.operations import get_department_setting, set_department_setting
from logic.users import log_audit_action

POLICY_PACK_VERSION = 1
PACK_SETTING_KEY = "cba_policy_pack_json"

# Keys we treat as policy (safe round-trip via department_settings).
POLICY_SETTING_KEYS = (
    "ot_fill_mode",
    "coverage_247_minimum",
    "min_staffing_by_band",
    "night_minimum_officers",
    "min_rest_hours_between_shifts",
    "bump_assignments_before_busy",
    "max_cascade_depth",
    "max_consecutive_work_days",
    "flsa_work_period_days",
    "flsa_base_date",
    "flsa_dual_workforce",
    "flsa_sworn_period_days",
    "flsa_civilian_ot_hours",
    "comp_cap_sworn_hours",
    "comp_cap_civilian_hours",
    "punch_required",
    "rest_fatigue_hard_stops",
    "rotation_style",
    "rotation_variations_json",
    "rotation_preset",
    "schedule_builder_defaults_json",
    "off_duty_bump_policy_json",
    "ot_equity_sort_on_callout",
    "publish_block_on_manual_review",
    "leave_accrual_deduct_on_approve",
)


def _config_policy_slice() -> Dict[str, Any]:
    import config

    return {
        "rotation_base_date": str(getattr(config, "ROTATION_BASE_DATE", "")),
        "rotation_cycle_length": int(getattr(config, "ROTATION_CYCLE_LENGTH", 14) or 14),
        "pay_period_base_date": str(getattr(config, "PAY_PERIOD_BASE_DATE", "")),
        "pay_period_length": int(getattr(config, "PAY_PERIOD_LENGTH", 14) or 14),
        "night_minimum_officers": int(getattr(config, "NIGHT_MINIMUM_OFFICERS", 2) or 2),
        "min_rest_hours_between_shifts": float(getattr(config, "MIN_REST_HOURS_BETWEEN_SHIFTS", 8.0) or 8.0),
        "bump_assignments_before_busy": int(getattr(config, "BUMP_ASSIGNMENTS_BEFORE_BUSY", 2) or 2),
        "bump_rules": getattr(config, "BUMP_RULES", None),
        "shift_times": getattr(config, "SHIFT_TIMES", None),
        "sick_monthly_accrual_hours": float(getattr(config, "SICK_MONTHLY_ACCRUAL_HOURS", 0) or 0),
        "float_holiday_annual_hours": float(getattr(config, "FLOAT_HOLIDAY_ANNUAL_HOURS", 0) or 0),
        "holiday_annual_hours": float(getattr(config, "HOLIDAY_ANNUAL_HOURS", 0) or 0),
    }


def _staffing_slice() -> Dict[str, Any]:
    try:
        from logic.staffing_config import get_staffing_settings

        return dict(get_staffing_settings() or {})
    except Exception as exc:
        return {"error": str(exc)}


def _ot_fill_slice() -> Dict[str, Any]:
    try:
        from logic.ot_fill import get_ot_fill_modes_for_ui

        return get_ot_fill_modes_for_ui()
    except Exception as exc:
        return {"error": str(exc)}


def _coverage_windows_slice() -> Dict[str, Any]:
    try:
        from logic.coverage_windows_store import get_active_coverage_windows, get_coverage_247_minimum

        return {
            "coverage_247_minimum": get_coverage_247_minimum(),
            "windows": get_active_coverage_windows() or [],
        }
    except Exception as exc:
        return {"error": str(exc)}


def collect_policy_pack(*, label: str = "") -> Dict[str, Any]:
    """Build full CBA/policy document from live config + settings."""
    settings: Dict[str, str] = {}
    for key in POLICY_SETTING_KEYS:
        val = get_department_setting(key, "")
        if val is not None and str(val) != "":
            settings[key] = str(val)

    pack = {
        "version": POLICY_PACK_VERSION,
        "product": "Chronos Command",
        "vendor": "Weierworks Technologies, LLC",
        "label": (label or "department-policy").strip() or "department-policy",
        "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "settings": settings,
        "config_defaults": _config_policy_slice(),
        "staffing": _staffing_slice(),
        "ot_fill": _ot_fill_slice(),
        "coverage": _coverage_windows_slice(),
        "selection_rules": {
            "bump_pick": "junior_first (higher seniority_rank = more junior)",
            "vacation_grant_sort": "senior_first for Vacation; date for other types",
            "partial_cascade": "routes to Pending Manual Review (product policy)",
            "ot_equity_sort_on_callout": settings.get("ot_equity_sort_on_callout", "0"),
        },
    }
    return pack


def export_policy_pack(
    *,
    label: str = "",
    path: Optional[str] = None,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    pack = collect_policy_pack(label=label)
    root = Path(__file__).resolve().parent.parent
    out_dir = root / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    if path:
        out = Path(path)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in pack["label"])[:40]
        out = out_dir / f"cba_policy_pack_{safe}_{stamp}.json"
    out.write_text(json.dumps(pack, indent=2, default=str), encoding="utf-8")
    # Keep last pack in settings for quick re-import
    set_department_setting(PACK_SETTING_KEY, json.dumps(pack, default=str), user_id=user_id)
    if user_id is not None:
        log_audit_action(
            user_id,
            "policy_pack_export",
            "department_settings",
            None,
            f"Exported policy pack to {out}",
        )
    return {
        "success": True,
        "path": str(out),
        "message": f"Policy pack exported ({len(pack.get('settings') or {})} settings)",
        "pack": pack,
    }


def import_policy_pack(
    source: Any,
    *,
    user_id: Optional[int] = None,
    apply_staffing: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Import policy pack from dict, JSON string, or file path."""
    pack: Dict[str, Any]
    if isinstance(source, dict):
        pack = source
    elif isinstance(source, (str, Path)):
        text = str(source).strip()
        p = Path(text)
        if p.is_file():
            pack = json.loads(p.read_text(encoding="utf-8"))
        else:
            pack = json.loads(text)
    else:
        return {"success": False, "message": "Invalid policy pack source"}

    if not isinstance(pack, dict):
        return {"success": False, "message": "Policy pack must be a JSON object"}
    settings = pack.get("settings") or {}
    if not isinstance(settings, dict):
        return {"success": False, "message": "Policy pack.settings must be an object"}

    applied: List[str] = []
    skipped: List[str] = []
    for key, value in settings.items():
        key_s = str(key).strip().lower()
        if key_s not in POLICY_SETTING_KEYS and not key_s.replace("_", "").isalnum():
            skipped.append(key_s)
            continue
        if dry_run:
            applied.append(key_s)
            continue
        r = set_department_setting(key_s, str(value), user_id=user_id)
        if r.get("success"):
            applied.append(key_s)
        else:
            skipped.append(f"{key_s}:{r.get('message')}")

    staffing_msg = ""
    if apply_staffing and not dry_run:
        staff = pack.get("staffing") or {}
        if isinstance(staff, dict) and staff and "error" not in staff:
            try:
                from logic.staffing_config import save_staffing_settings

                starts = staff.get("shift_starts") or staff.get("starts") or []
                if isinstance(starts, (list, tuple)):
                    starts_text = ", ".join(str(s) for s in starts)
                else:
                    starts_text = str(starts or "")
                n_off = int(staff.get("target_officer_count") or staff.get("num_officers") or 0)
                sr = save_staffing_settings(
                    shift_length_hours=float(staff.get("shift_length_hours") or staff.get("shift_length") or 8),
                    annual_hours_target=float(staff.get("annual_hours_target") or 2008),
                    shift_count=int(staff.get("shift_count") or max(len(starts) if isinstance(starts, list) else 3, 1)),
                    target_officer_count=max(1, n_off),
                    shift_starts_text=starts_text or "",
                    annual_hours_variance=float(staff.get("annual_hours_variance") or 20),
                    user_id=user_id,
                )
                staffing_msg = sr.get("message") or ("staffing applied" if sr.get("success") else "staffing skipped")
            except Exception as exc:
                staffing_msg = f"staffing error: {exc}"

    if not dry_run and user_id is not None:
        log_audit_action(
            user_id,
            "policy_pack_import",
            "department_settings",
            None,
            f"Imported policy pack keys={len(applied)} skipped={len(skipped)}",
        )

    return {
        "success": True,
        "dry_run": dry_run,
        "applied_keys": applied,
        "skipped": skipped,
        "staffing_message": staffing_msg,
        "message": (
            f"{'Would apply' if dry_run else 'Applied'} {len(applied)} setting(s)"
            + (f"; staffing: {staffing_msg}" if staffing_msg else "")
        ),
    }


def get_last_exported_policy_pack() -> Optional[Dict[str, Any]]:
    raw = get_department_setting(PACK_SETTING_KEY, "") or ""
    if not raw.strip():
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None
