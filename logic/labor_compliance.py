"""FLSA and department labor-compliance rules for scheduling and payroll."""

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from config import (
    CALLBACK_MINIMUM_HOURS,
    FLSA_207K_BASE_DATE,
    FLSA_207K_ENABLED,
    FLSA_207K_HOURS_PER_DAY,
    FLSA_207K_WORK_PERIOD_DAYS,
    FLSA_COMP_TIME_MAX_HOURS,
    FLSA_HOURS_WARN_PCT,
    FLSA_LE_WEEKLY_THRESHOLD,
    MAX_CONSECUTIVE_WORK_DAYS,
)
from database import get_connection
from logic.officers import get_officers_by_seniority
from logic.scheduling import get_officer_day_status
from validators import format_date, is_officer_active, parse_date, storage_date_str

_WORKING_STATUSES = frozenset({"working", "covering", "swapped", "training"})


def get_flsa_work_period_days() -> int:
    """FLSA §207(k) work period length — from department setting, not pay period or rotation."""
    from logic.operations import get_department_setting

    raw = get_department_setting("flsa_work_period_days", "")
    if raw.strip():
        try:
            return max(7, min(int(raw), 28))
        except ValueError:
            pass
    return FLSA_207K_WORK_PERIOD_DAYS


def get_flsa_base_date() -> date:
    """Anchor date for FLSA work-period windows (independent of pay period and rotation)."""
    from logic.operations import get_department_setting

    raw = get_department_setting("flsa_207k_base_date", "").strip()
    if raw:
        try:
            return parse_date(raw)
        except ValueError:
            pass
    return FLSA_207K_BASE_DATE


def save_flsa_settings(
    work_period_days: int,
    base_date_text: Optional[str] = None,
    *,
    user_id: Optional[int] = None,
    dual_workforce: Optional[bool] = None,
    civilian_weekly_threshold: Optional[float] = None,
    sworn_comp_cap: Optional[float] = None,
    civilian_comp_cap: Optional[float] = None,
) -> Dict:
    """Persist FLSA §207(k) work-period length, anchor, and dual-workforce knobs (Netchex pattern)."""
    from logic.operations import set_department_setting
    from logic.users import log_audit_action

    try:
        days = max(7, min(int(work_period_days), 28))
    except (TypeError, ValueError):
        return {"success": False, "message": "FLSA work period must be 7–28 days"}

    base_date = get_flsa_base_date()
    if base_date_text and base_date_text.strip():
        try:
            base_date = parse_date(base_date_text.strip())
        except ValueError as exc:
            return {"success": False, "message": str(exc)}

    pairs = [
        ("flsa_work_period_days", str(days)),
        ("flsa_207k_base_date", storage_date_str(base_date.isoformat())),
    ]
    if dual_workforce is not None:
        pairs.append(("flsa_dual_workforce", "1" if dual_workforce else "0"))
    if civilian_weekly_threshold is not None:
        try:
            thr = max(1.0, min(float(civilian_weekly_threshold), 80.0))
        except (TypeError, ValueError):
            return {"success": False, "message": "Civilian weekly threshold must be numeric"}
        pairs.append(("flsa_civilian_weekly_threshold", str(thr)))
    if sworn_comp_cap is not None:
        try:
            pairs.append(("flsa_comp_cap_sworn", str(max(1.0, float(sworn_comp_cap)))))
        except (TypeError, ValueError):
            return {"success": False, "message": "Sworn comp cap must be numeric"}
    if civilian_comp_cap is not None:
        try:
            pairs.append(("flsa_comp_cap_civilian", str(max(1.0, float(civilian_comp_cap)))))
        except (TypeError, ValueError):
            return {"success": False, "message": "Civilian comp cap must be numeric"}

    for key, value in pairs:
        result = set_department_setting(key, value, user_id=user_id)
        if not result.get("success"):
            return result

    log_audit_action("labor.flsa_settings", "payroll", None, user_id, f"days={days}")
    return {
        "success": True,
        "message": "FLSA settings saved",
        "work_period_days": days,
        "base_date": base_date.isoformat(),
        "base_date_display": format_date(base_date),
    }


def get_flsa_settings() -> Dict:
    """Current FLSA §207(k) configuration for payroll UI (+ dual workforce Netchex knobs)."""
    from config import FLSA_COMP_TIME_MAX_HOURS
    from logic.operations import get_department_setting

    days = get_flsa_work_period_days()
    base = get_flsa_base_date()
    start, end = get_flsa_work_period()
    dual_raw = get_department_setting("flsa_dual_workforce", "0").strip()
    dual = dual_raw in ("1", "true", "yes", "on")
    try:
        civ_thr = float(get_department_setting("flsa_civilian_weekly_threshold", "40") or 40)
    except ValueError:
        civ_thr = 40.0
    try:
        sworn_cap = float(
            get_department_setting("flsa_comp_cap_sworn", str(FLSA_COMP_TIME_MAX_HOURS)) or FLSA_COMP_TIME_MAX_HOURS
        )
    except ValueError:
        sworn_cap = float(FLSA_COMP_TIME_MAX_HOURS or 480)
    try:
        civ_cap = float(get_department_setting("flsa_comp_cap_civilian", "240") or 240)
    except ValueError:
        civ_cap = 240.0
    return {
        "success": True,
        "work_period_days": days,
        "base_date": base.isoformat(),
        "base_date_display": format_date(base),
        "current_period_start": format_date(start),
        "current_period_end": format_date(end),
        "hours_threshold": flsa_threshold_for_period_days(days),
        "dual_workforce": dual,
        "civilian_weekly_threshold": civ_thr,
        "sworn_comp_cap": sworn_cap,
        "civilian_comp_cap": civ_cap,
    }


def flsa_threshold_for_period_days(period_days: int) -> float:
    """DOL §207(k) hour cap scaled to work-period length (171h @ 28 days)."""
    from logic.operations import get_department_setting

    override = get_department_setting("flsa_207k_hours_threshold", "").strip()
    if override:
        try:
            return float(override)
        except ValueError:
            pass
    return round(FLSA_207K_HOURS_PER_DAY * period_days, 1)


def get_flsa_work_period(reference: Optional[date] = None) -> Tuple[date, date]:
    """Inclusive start/end of the FLSA §207(k) work period containing reference."""
    ref = reference or date.today()
    period_days = get_flsa_work_period_days()
    base_date = get_flsa_base_date()
    days_since = (ref - base_date).days
    if days_since < 0:
        periods_back = (-days_since // period_days) + 1
        period_index = -periods_back
    else:
        period_index = days_since // period_days
    start = base_date + timedelta(days=period_index * period_days)
    end = start + timedelta(days=period_days - 1)
    return start, end


def get_flsa_207k_work_period(reference: Optional[date] = None) -> Tuple[date, date]:
    """Alias for payroll and analytics callers."""
    return get_flsa_work_period(reference)


def sum_officer_work_hours(officer_id: int, start_date: date, end_date: date) -> float:
    """Sum hours worked from timecard entries in an inclusive date range."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COALESCE(SUM(hours_worked), 0) AS total
        FROM timecard_entries
        WHERE officer_id = ? AND entry_date >= ? AND entry_date <= ?
    """,
        (officer_id, start_date.isoformat(), end_date.isoformat()),
    )
    row = cursor.fetchone()
    conn.close()
    return float(row["total"] or 0.0)


def get_flsa_207k_status(officer_id: int, reference: Optional[date] = None) -> Dict:
    """Hours in current §207(k) work period vs threshold for configured FLSA period."""
    ref = reference or date.today()
    period_start, period_end = get_flsa_work_period(ref)
    period_days = get_flsa_work_period_days()
    threshold = flsa_threshold_for_period_days(period_days)

    hours = sum_officer_work_hours(officer_id, period_start, period_end)
    warn_at = threshold * FLSA_HOURS_WARN_PCT
    if hours >= threshold:
        severity = "critical"
        message = f"§207(k) {period_days}-day period {hours:.1f}h ≥ {threshold:.0f}h — overtime required"
    elif hours >= warn_at:
        severity = "warning"
        message = f"§207(k) {period_days}-day period {hours:.1f}h approaching {threshold:.0f}h limit"
    else:
        severity = None
        message = ""

    return {
        "officer_id": officer_id,
        "period_start": period_start,
        "period_end": period_end,
        "period_days": period_days,
        "hours": round(hours, 2),
        "threshold": threshold,
        "over_threshold_hours": round(max(0.0, hours - threshold), 2),
        "severity": severity,
        "message": message,
    }


def get_flsa_payroll_summary(officer_id: int, reference: Optional[date] = None) -> Dict:
    """FLSA work-period status for payroll tab and pay-period summaries."""
    if not FLSA_207K_ENABLED:
        return {"success": True, "enabled": False}
    status = get_flsa_207k_status(officer_id, reference)
    return {
        "success": True,
        "enabled": True,
        "period_days": status["period_days"],
        "period_start": status["period_start"].isoformat(),
        "period_end": status["period_end"].isoformat(),
        "period_start_display": format_date(status["period_start"]),
        "period_end_display": format_date(status["period_end"]),
        "hours_worked": status["hours"],
        "hours_threshold": status["threshold"],
        "over_threshold_hours": status["over_threshold_hours"],
        "severity": status["severity"],
        "message": status["message"],
        "flsa_base_date_display": format_date(get_flsa_base_date()),
    }


def count_consecutive_work_days_ending(officer_id: int, end_date: date, max_lookback: int = 20) -> int:
    """Count consecutive scheduled work days ending on end_date (inclusive)."""
    from logic import rust_bridge
    from logic.officers import get_officer_by_id
    from logic.rotation_config import get_active_rotation_base_date, get_active_rotation_cycle_length
    from logic.scheduling import _load_override_maps_for_range

    officer = get_officer_by_id(officer_id)
    if officer and rust_bridge.available():
        window_start = end_date - timedelta(days=max_lookback)
        bumped_by_date, covering_by_date, swapped_by_date, bumped_status_by_date = _load_override_maps_for_range(
            window_start, end_date
        )
        rust_count = rust_bridge.consecutive_work_days(
            officer_id,
            officer.get("squad") or "",
            officer.get("shift_start") or "",
            officer.get("active") == 1,
            officer.get("job_title") or "",
            end_date,
            bumped_by_date,
            covering_by_date,
            swapped_by_date,
            bumped_status_by_date,
            get_active_rotation_base_date(),
            get_active_rotation_cycle_length(),
            max_lookback,
        )
        if rust_count is not None:
            return rust_count

    count = 0
    current = end_date
    for _ in range(max_lookback):
        if get_officer_day_status(officer_id, current) in _WORKING_STATUSES:
            count += 1
            current -= timedelta(days=1)
        else:
            break
    return count


def get_max_consecutive_work_days() -> int:
    from logic.operations import get_department_setting

    try:
        return int(get_department_setting("max_consecutive_work_days", str(MAX_CONSECUTIVE_WORK_DAYS)))
    except ValueError:
        return MAX_CONSECUTIVE_WORK_DAYS


def would_exceed_consecutive_work_limit(
    officer_id: int,
    assignment_date: date,
    adding_work_day: bool,
    max_days: Optional[int] = None,
) -> bool:
    """True if assignment would exceed the consecutive-work-day cap."""
    limit = max_days if max_days is not None else get_max_consecutive_work_days()
    if adding_work_day:
        prior = count_consecutive_work_days_ending(officer_id, assignment_date - timedelta(days=1))
        return prior + 1 > limit
    return count_consecutive_work_days_ending(officer_id, assignment_date) > limit


def describe_consecutive_work_violation(
    officer_id: int,
    assignment_date: date,
    adding_work_day: bool,
    officer_name: Optional[str] = None,
    max_days: Optional[int] = None,
) -> Optional[str]:
    """Return user-facing consecutive-day violation message, or None if within limit."""
    if not would_exceed_consecutive_work_limit(officer_id, assignment_date, adding_work_day, max_days):
        return None
    limit = max_days if max_days is not None else get_max_consecutive_work_days()
    label = officer_name or "Officer"
    if adding_work_day:
        prior = count_consecutive_work_days_ending(officer_id, assignment_date - timedelta(days=1))
        streak = prior + 1
    else:
        streak = count_consecutive_work_days_ending(officer_id, assignment_date)
    return (
        f"Consecutive work day limit: {label} would reach {streak} days "
        f"(maximum {limit}) — supervisor override required"
    )


def callback_payable_hours(actual_hours: float, minimum: Optional[float] = None) -> float:
    """Minimum paid hours for call-back / call-in (FLSA hours worked)."""
    floor = minimum if minimum is not None else CALLBACK_MINIMUM_HOURS
    try:
        from logic.operations import get_department_setting

        floor = float(get_department_setting("callback_minimum_hours", str(floor)))
    except ValueError:
        pass
    return max(actual_hours, floor)


def get_labor_compliance_report(officer_id: Optional[int] = None) -> Dict:
    """Department labor-law compliance summary for dashboard and CLI."""
    issues: List[Dict] = []
    comp_warnings = 0
    consecutive_warnings = 0
    flsa_207k_warnings = 0
    period_days = get_flsa_work_period_days()
    threshold = flsa_threshold_for_period_days(period_days)
    max_consecutive = get_max_consecutive_work_days()

    for officer in get_officers_by_seniority():
        if not is_officer_active(officer):
            continue
        oid = officer["id"]
        if officer_id is not None and oid != officer_id:
            continue

        flsa = get_flsa_207k_status(oid)
        if flsa["severity"]:
            flsa_207k_warnings += 1
            issues.append(
                {
                    "officer_id": oid,
                    "officer_name": officer["name"],
                    "category": "flsa_207k",
                    "severity": flsa["severity"],
                    "message": flsa["message"],
                }
            )

        banks = _officer_comp_hours(oid)
        comp_hours = banks.get("comp_hours", 0.0)
        if comp_hours >= FLSA_COMP_TIME_MAX_HOURS:
            comp_warnings += 1
            issues.append(
                {
                    "officer_id": oid,
                    "officer_name": officer["name"],
                    "category": "comp_cap",
                    "severity": "critical",
                    "message": (
                        f"Comp bank {comp_hours:.1f}h at FLSA cap ({FLSA_COMP_TIME_MAX_HOURS:.0f}h) "
                        "— cash overtime required"
                    ),
                }
            )
        elif comp_hours >= FLSA_COMP_TIME_MAX_HOURS * FLSA_HOURS_WARN_PCT:
            comp_warnings += 1
            issues.append(
                {
                    "officer_id": oid,
                    "officer_name": officer["name"],
                    "category": "comp_cap",
                    "severity": "warning",
                    "message": (f"Comp bank {comp_hours:.1f}h approaching FLSA cap ({FLSA_COMP_TIME_MAX_HOURS:.0f}h)"),
                }
            )

        today = date.today()
        streak = count_consecutive_work_days_ending(oid, today)
        if streak >= max_consecutive:
            consecutive_warnings += 1
            issues.append(
                {
                    "officer_id": oid,
                    "officer_name": officer["name"],
                    "category": "consecutive_days",
                    "severity": "critical" if streak > max_consecutive else "warning",
                    "message": f"{streak} consecutive work day(s) (limit {max_consecutive})",
                }
            )

    issues.sort(key=lambda i: (0 if i["severity"] == "critical" else 1, i["officer_name"]))
    period_start, period_end = get_flsa_work_period()
    return {
        "success": True,
        "officer_scoped": officer_id is not None,
        "flsa_207k_period_start": format_date(period_start),
        "flsa_207k_period_end": format_date(period_end),
        "flsa_207k_period_days": period_days,
        "flsa_207k_threshold": threshold,
        "flsa_le_weekly_threshold": FLSA_LE_WEEKLY_THRESHOLD,
        "comp_cap_hours": FLSA_COMP_TIME_MAX_HOURS,
        "max_consecutive_work_days": max_consecutive,
        "callback_minimum_hours": CALLBACK_MINIMUM_HOURS,
        "issue_count": len(issues),
        "flsa_207k_warning_count": flsa_207k_warnings,
        "comp_warning_count": comp_warnings,
        "consecutive_warning_count": consecutive_warnings,
        "issues": issues,
    }


def _officer_comp_hours(officer_id: int) -> Dict:
    from logic.operations import get_officer_time_banks

    return get_officer_time_banks(officer_id)


def get_fatigue_score_threshold() -> float:
    from logic.operations import get_department_setting

    try:
        return float(get_department_setting("fatigue_score_threshold", "70"))
    except ValueError:
        return 70.0


def compute_fatigue_score(officer_id: int, *, as_of: Optional[date] = None) -> Dict:
    """
    Composite fatigue index 0–100 (higher = more fatigued).
    Weights: consecutive work days 40%, weekly hours 35%, FLSA period hours 25%.
    """
    from logic.analytics import get_hours_watch

    today = as_of or date.today()
    max_consecutive = get_max_consecutive_work_days()
    streak = count_consecutive_work_days_ending(officer_id, today)
    streak_pct = min(100.0, (streak / max(max_consecutive, 1)) * 100.0)

    hours_watch = get_hours_watch(officer_id=officer_id)
    weekly_top = hours_watch.get("warnings", [{}])[0] if hours_watch.get("warnings") else {}
    weekly_hours = weekly_top.get("week_hours") or 0.0
    weekly_threshold = weekly_top.get("le_weekly_threshold") or FLSA_LE_WEEKLY_THRESHOLD
    weekly_pct = min(100.0, (weekly_hours / max(weekly_threshold, 1)) * 100.0)

    flsa = get_flsa_207k_status(officer_id, reference=today)
    period_hours = flsa.get("hours") or 0.0
    period_threshold = flsa.get("threshold") or flsa_threshold_for_period_days(get_flsa_work_period_days())
    period_pct = min(100.0, (period_hours / max(period_threshold, 1)) * 100.0)

    score = round(streak_pct * 0.4 + weekly_pct * 0.35 + period_pct * 0.25, 1)
    threshold = get_fatigue_score_threshold()
    severity = None
    if score >= threshold:
        severity = "critical" if score >= min(100.0, threshold + 15) else "warning"

    return {
        "success": True,
        "officer_id": officer_id,
        "score": score,
        "threshold": threshold,
        "severity": severity,
        "factors": {
            "consecutive_days": streak,
            "consecutive_pct": round(streak_pct, 1),
            "weekly_hours": weekly_hours,
            "weekly_pct": round(weekly_pct, 1),
            "period_hours": period_hours,
            "period_pct": round(period_pct, 1),
        },
        "message": (f"Fatigue score {score:.0f}/100" + (f" — above {threshold:.0f} threshold" if severity else "")),
    }


def get_fatigue_scoreboard(*, limit: int = 10) -> Dict:
    """Top fatigued officers for dashboard and reports."""
    rows = []
    for officer in get_officers_by_seniority():
        if not is_officer_active(officer):
            continue
        row = compute_fatigue_score(officer["id"])
        rows.append(
            {
                "officer_id": officer["id"],
                "officer_name": officer["name"],
                "squad": officer.get("squad"),
                "score": row["score"],
                "severity": row["severity"],
                "message": row["message"],
            }
        )
    rows.sort(key=lambda r: r["score"], reverse=True)
    elevated = [r for r in rows if r.get("severity")]
    return {
        "success": True,
        "threshold": get_fatigue_score_threshold(),
        "officers": rows[:limit],
        "elevated_count": len(elevated),
        "top": rows[0] if rows else None,
    }
