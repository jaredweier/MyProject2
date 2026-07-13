"""View / recommend / implement optimized simulator plans as monthly schedules."""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, List, Optional

from logic.operations import get_department_setting, set_department_setting
from logic.users import log_audit_action
from validators import format_date, parse_date, storage_date_str

DEFAULTS_KEY = "schedule_builder_defaults_json"
LAST_PLAN_KEY = "last_optimized_plan_json"


def recommend_implement_dates(reference: Optional[date] = None) -> Dict:
    """Recommend implement dates from payroll pay periods."""
    from logic.payroll.period import format_pay_period_label, get_adjacent_pay_period, get_pay_period

    ref = reference or date.today()
    cur_start, cur_end = get_pay_period(ref)
    next_start, next_end = get_adjacent_pay_period(cur_start, direction=1)
    # Prefer next pay period start if we're past day 1 of current; else current start if not started
    if ref <= cur_start:
        recommended = cur_start
        reason = "Current pay period start"
    else:
        recommended = next_start
        reason = "Next pay period start (recommended for clean payroll alignment)"
    options = [
        {
            "date": cur_start.isoformat(),
            "label": format_pay_period_label(cur_start, cur_end),
            "kind": "current_pay_period",
            "recommended": recommended == cur_start,
        },
        {
            "date": next_start.isoformat(),
            "label": format_pay_period_label(next_start, next_end),
            "kind": "next_pay_period",
            "recommended": recommended == next_start,
        },
        {
            "date": date(ref.year, ref.month, 1).isoformat(),
            "label": f"First of month ({format_date(date(ref.year, ref.month, 1))})",
            "kind": "month_start",
            "recommended": False,
        },
    ]
    # Following month start
    if ref.month == 12:
        nm = date(ref.year + 1, 1, 1)
    else:
        nm = date(ref.year, ref.month + 1, 1)
    options.append(
        {
            "date": nm.isoformat(),
            "label": f"First of next month ({format_date(nm)})",
            "kind": "next_month_start",
            "recommended": False,
        }
    )
    return {
        "success": True,
        "recommended_date": recommended.isoformat(),
        "recommended_label": format_pay_period_label(*get_pay_period(recommended)),
        "reason": reason,
        "options": options,
    }


def format_optimized_plan_view(result: Dict, config: Optional[Dict] = None) -> Dict:
    """Build a screen-friendly grid from a simulation/optimizer result."""
    if not result or not result.get("success"):
        return {"success": False, "message": result.get("message") if result else "No plan"}

    slots = result.get("officer_slots") or []
    coverage = result.get("coverage_by_day") or []
    metrics = result.get("metrics") or {}
    cfg = config or result.get("simulation_config") or {}

    # Normalize slots (dataclass dicts or plain)
    slot_rows = []
    for s in slots:
        if isinstance(s, dict):
            slot_rows.append(s)
        else:
            slot_rows.append(getattr(s, "__dict__", {}))

    day_rows = []
    for day in coverage[:62]:
        if not isinstance(day, dict):
            continue
        day_rows.append(
            {
                "date": day.get("date"),
                "cycle_day": day.get("cycle_day"),
                "working_officers": day.get("working_officers"),
                "min_shift_coverage": day.get("min_shift_coverage"),
                "shift_counts": day.get("shift_counts") or {},
                "high_risk_night": day.get("high_risk_night"),
            }
        )

    lines = [
        f"Plan view · {len(slot_rows)} slots · {len(day_rows)} days shown",
        f"Coverage %: {metrics.get('coverage_percent', '—')} · "
        f"Min officers req: {metrics.get('min_officers_required', metrics.get('auto_sized') and 'auto' or '—')}",
        f"Hard constraints OK: {metrics.get('hard_constraints_ok', '—')}",
        "",
        "Officer slots:",
    ]
    for s in slot_rows[:40]:
        lines.append(
            f"  {s.get('label') or s.get('slot_id')}: squad {s.get('squad')} "
            f"{s.get('shift_start')}–{s.get('shift_end')} · ~{s.get('projected_annual_hours', '—')}h/yr"
        )
    if len(slot_rows) > 40:
        lines.append(f"  … +{len(slot_rows) - 40} more")
    lines.append("")
    lines.append("Daily coverage (first days):")
    for d in day_rows[:14]:
        counts = d.get("shift_counts") or {}
        cnt = ", ".join(f"{k}:{v}" for k, v in sorted(counts.items()))
        lines.append(f"  {d.get('date')} · working {d.get('working_officers')} · {cnt}")

    return {
        "success": True,
        "text": "\n".join(lines),
        "slots": slot_rows,
        "coverage_by_day": day_rows,
        "metrics": metrics,
        "config": cfg,
        "shift_templates": result.get("shift_templates") or [],
    }


def save_last_optimized_plan(result: Dict, config: Dict, *, user_id: Optional[int] = None) -> Dict:
    payload = {
        "result": result,
        "config": config,
        "saved_at": date.today().isoformat(),
    }
    r = set_department_setting(LAST_PLAN_KEY, json.dumps(payload), user_id=user_id)
    if not r.get("success"):
        return r
    return {"success": True, "message": "Optimized plan saved for review"}


def get_last_optimized_plan() -> Optional[Dict]:
    raw = get_department_setting(LAST_PLAN_KEY, "") or ""
    if not raw.strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def get_schedule_builder_defaults() -> Dict:
    raw = get_department_setting(DEFAULTS_KEY, "") or ""
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def set_schedule_builder_defaults(defaults: Dict, *, user_id: Optional[int] = None) -> Dict:
    r = set_department_setting(DEFAULTS_KEY, json.dumps(defaults or {}), user_id=user_id)
    if not r.get("success"):
        return r
    return {"success": True, "message": "Schedule builder defaults saved", "defaults": defaults}


def apply_schedule_builder_defaults_to_department(*, user_id: Optional[int] = None) -> Dict:
    """Push saved builder defaults into active staffing/rotation settings."""
    defaults = get_schedule_builder_defaults()
    if not defaults:
        return {"success": False, "message": "No schedule builder defaults saved"}

    from logic.staffing_config import save_staffing_settings

    starts = defaults.get("shift_starts") or []
    if isinstance(starts, str):
        starts_text = starts
    else:
        starts_text = ", ".join(str(s) for s in starts)

    staff = save_staffing_settings(
        shift_length_hours=float(defaults.get("shift_length_hours") or 11),
        annual_hours_target=float(defaults.get("annual_hours_target") or 2080),
        shift_count=int(defaults.get("shift_count") or max(len(starts) if isinstance(starts, list) else 4, 1)),
        target_officer_count=int(defaults.get("num_officers") or defaults.get("target_officer_count") or 16),
        shift_starts_text=starts_text,
        annual_hours_variance=float(defaults.get("annual_hours_variance") or 40),
        user_id=user_id,
    )
    if not staff.get("success"):
        return staff

    # Rotation variations / style
    if defaults.get("rotation_variations"):
        set_department_setting(
            "rotation_variations_json",
            json.dumps(defaults.get("rotation_variations")),
            user_id=user_id,
        )
    if defaults.get("rotation_style"):
        set_department_setting("rotation_style", str(defaults["rotation_style"]), user_id=user_id)
    if defaults.get("rotation_type"):
        set_department_setting("rotation_preset", str(defaults["rotation_type"]), user_id=user_id)
    if defaults.get("coverage_247") is not None:
        set_department_setting("coverage_247_minimum", str(int(defaults["coverage_247"])), user_id=user_id)

    return {
        "success": True,
        "message": "Department staffing defaults applied from optimized plan",
        "defaults": defaults,
    }


def _unlock_base_if_needed(year: int, month: int) -> None:
    from database import get_connection

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE schedule_snapshots SET locked = 0
            WHERE year = ? AND month = ? AND schedule_type = 'base'
            """,
            (year, month),
        )
        conn.commit()
    finally:
        conn.close()


def implement_optimized_plan(
    *,
    start_date: str,
    result: Optional[Dict] = None,
    config: Optional[Dict] = None,
    user_id: Optional[int] = None,
    apply_officer_assignments: bool = True,
    force_regenerate: bool = True,
    save_as_defaults: bool = True,
) -> Dict:
    """
    Apply optimized plan as department defaults and generate monthly schedule
    for the month containing start_date.
    """
    if result is None or config is None:
        last = get_last_optimized_plan()
        if not last:
            return {"success": False, "message": "No optimized plan to implement — run simulator first"}
        result = result or last.get("result") or {}
        config = config or last.get("config") or {}

    if not result.get("success"):
        return {"success": False, "message": "Plan is not a successful optimization result"}

    try:
        start = parse_date(start_date)
    except ValueError as exc:
        return {"success": False, "message": str(exc)}

    # Build defaults from config + result metrics
    starts = config.get("shift_starts") or []
    if isinstance(starts, str):
        start_list = [s.strip() for s in starts.replace(";", ",").split(",") if s.strip()]
    else:
        start_list = list(starts)

    templates = result.get("shift_templates") or []
    if not start_list and templates:
        start_list = [t[0] if isinstance(t, (list, tuple)) else t.get("start") for t in templates]

    defaults = {
        "shift_length_hours": float(config.get("shift_length_hours") or 11),
        "annual_hours_target": float(config.get("annual_hours_target") or 2080),
        "annual_hours_variance": float(config.get("annual_hours_variance") or 40),
        "shift_starts": start_list,
        "shift_count": len(start_list) or int(config.get("shift_count") or 4),
        "num_officers": int(
            (result.get("metrics") or {}).get("min_officers_required") or config.get("num_officers") or 0
        )
        or len(result.get("officer_slots") or []),
        "target_officer_count": int(config.get("num_officers") or 0) or len(result.get("officer_slots") or []),
        "min_per_shift": int(config.get("min_per_shift") or 1),
        "rotation_type": config.get("rotation_type") or "",
        "rotation_style": config.get("rotation_style") or "",
        "rotation_variations": config.get("rotation_variations") or [],
        "coverage_247": int(config.get("coverage_247") or 0),
        "avoid_flsa_overtime": bool(config.get("avoid_flsa_overtime")),
        "implemented_start_date": storage_date_str(start.isoformat()),
        "source": "optimized_plan",
    }

    if save_as_defaults:
        set_schedule_builder_defaults(defaults, user_id=user_id)

    applied = apply_schedule_builder_defaults_to_department(user_id=user_id)
    if not applied.get("success"):
        return applied

    officer_updates = 0
    if apply_officer_assignments:
        officer_updates = _apply_slots_to_officers(result.get("officer_slots") or [], user_id=user_id)

    year, month = start.year, start.month
    if force_regenerate:
        _unlock_base_if_needed(year, month)
        # Delete base rows so ensure_original rebuilds
        from database import get_connection

        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id FROM schedule_snapshots WHERE year=? AND month=? AND schedule_type='base'",
                (year, month),
            )
            row = cursor.fetchone()
            if row:
                cursor.execute("DELETE FROM schedule_snapshot_rows WHERE snapshot_id=?", (row["id"],))
                cursor.execute("DELETE FROM schedule_snapshots WHERE id=?", (row["id"],))
            cursor.execute(
                "SELECT id FROM schedule_snapshots WHERE year=? AND month=? AND schedule_type='updated'",
                (year, month),
            )
            row = cursor.fetchone()
            if row:
                cursor.execute("DELETE FROM schedule_snapshot_rows WHERE snapshot_id=?", (row["id"],))
                cursor.execute("DELETE FROM schedule_snapshots WHERE id=?", (row["id"],))
            conn.commit()
        finally:
            conn.close()

    from logic.snapshots import ensure_original_monthly_schedule

    gen = ensure_original_monthly_schedule(year, month, user_id)
    if not gen.get("success"):
        return gen

    log_audit_action(
        "schedule.implement_optimized",
        "schedule_snapshot",
        gen.get("snapshot_id"),
        user_id,
        f"start={start.isoformat()} officers_updated={officer_updates}",
    )
    return {
        "success": True,
        "message": (
            f"Implemented optimized plan from {format_date(start)}: "
            f"monthly {month}/{year} generated; {officer_updates} officer assignment(s) updated; "
            f"defaults saved for next generator run"
        ),
        "year": year,
        "month": month,
        "snapshot_id": gen.get("snapshot_id"),
        "live_snapshot_id": gen.get("live_snapshot_id"),
        "officer_updates": officer_updates,
        "defaults": defaults,
        "recommended": recommend_implement_dates(start),
    }


def _apply_slots_to_officers(slots: List[Any], *, user_id: Optional[int] = None) -> int:
    """Map simulation slots onto real officers when slot_id matches officer id."""
    from logic.officers import get_officer_by_id, update_officer

    updated = 0
    for raw in slots:
        s = raw if isinstance(raw, dict) else getattr(raw, "__dict__", {})
        oid = s.get("slot_id") or s.get("id")
        try:
            oid = int(oid)
        except (TypeError, ValueError):
            continue
        officer = get_officer_by_id(oid)
        if not officer:
            continue
        fields = {}
        if s.get("squad") in ("A", "B"):
            fields["squad"] = s["squad"]
        if s.get("shift_start"):
            fields["shift_start"] = s["shift_start"]
            fields["shift_end"] = s.get("shift_end") or officer.get("shift_end")
        # pattern fields if present on slot
        if s.get("rotation_pattern"):
            fields["rotation_pattern"] = s["rotation_pattern"]
        if s.get("rotation_phase") is not None:
            fields["rotation_phase"] = int(s["rotation_phase"])
        if not fields:
            continue
        r = update_officer(oid, **fields)
        if r.get("success"):
            updated += 1
    return updated


def next_generator_should_use_defaults() -> bool:
    d = get_schedule_builder_defaults()
    return bool(d.get("source") == "optimized_plan" or d.get("shift_starts"))
