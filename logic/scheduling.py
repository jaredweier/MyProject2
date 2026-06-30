"""Rotation, coverage, bumping, and schedule matrix."""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from config import (
    BUMP_RULES,
    MIN_REST_HOURS_BETWEEN_SHIFTS,
    NIGHT_MINIMUM_OFFICERS,
    ROTATION_BASE_DATE,
    ROTATION_CYCLE_LENGTH,
    SHIFT_TIMES,
    is_high_risk_night,
)
from database import get_connection
from logic import rust_bridge
from logic.officers import get_officer_by_id, get_officers_by_seniority
from models import BumpChainStep, BumpChainSuggestion, BumpSimulationResult
from validators import (
    applies_night_minimum,
    night_minimum_violation,
    parse_date,
)

_OFFICER_WORKING_STATUSES = frozenset({"working", "covering", "swapped", "training"})


def get_current_cycle_window(reference: Optional[date] = None) -> Tuple[date, date]:
    """Return start/end dates for the 14-day cycle containing reference (default today)."""
    ref = reference or date.today()
    cycle_day = get_cycle_day(ref)
    start = ref - timedelta(days=cycle_day - 1)
    end = start + timedelta(days=ROTATION_CYCLE_LENGTH - 1)
    return start, end


def get_cycle_day(target_date: date) -> int:
    return rust_bridge.get_cycle_day(target_date, ROTATION_BASE_DATE, ROTATION_CYCLE_LENGTH)


def get_squad_on_duty(cycle_day: int) -> str:
    return rust_bridge.get_squad_on_duty(cycle_day)


def is_officer_working_on_day(officer_id: int, target_date: date, squad: str = None) -> bool:
    officer = get_officer_by_id(officer_id)
    if not officer:
        return False
    from validators import officer_has_assignment

    if not officer_has_assignment(officer):
        return False
    effective_squad = squad or officer["squad"]
    cycle_day = get_cycle_day(target_date)
    squad_on_duty = get_squad_on_duty(cycle_day)
    return effective_squad == squad_on_duty


def count_officers_on_shift_on_date(target_date: date, squad: str, shift_start: str) -> int:
    date_str = target_date.strftime("%Y-%m-%d")
    counts = get_shift_coverage_counts_for_range(target_date, target_date)
    return counts.get((date_str, squad, shift_start), 0)


def get_shift_coverage_counts_for_range(
    start_date: date,
    end_date: date,
) -> Dict[Tuple[str, str, str], int]:
    """Batch shift headcount: key (YYYY-MM-DD, squad, shift_start) -> count."""
    from validators import is_officer_active

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    shift_starts = [start for start, _ in SHIFT_TIMES.values()]

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, squad, shift_start, active FROM officers WHERE active = 1
    """)
    officers = [dict(row) for row in cursor.fetchall()]
    cursor.execute(
        """
        SELECT override_date, original_officer_id, replacement_officer_id, covered_shift_start
        FROM schedule_overrides
        WHERE override_date >= ? AND override_date <= ?
    """,
        (start_str, end_str),
    )
    overrides = [dict(row) for row in cursor.fetchall()]
    conn.close()

    override_rows = [
        (
            row["override_date"],
            row["original_officer_id"],
            row.get("replacement_officer_id"),
            row.get("covered_shift_start"),
        )
        for row in overrides
    ]
    rust_counts = rust_bridge.compute_coverage_counts_rust(
        officers,
        override_rows,
        start_date,
        end_date,
        shift_starts,
        ROTATION_BASE_DATE,
        ROTATION_CYCLE_LENGTH,
    )
    if rust_counts is not None:
        return rust_counts

    bumped_by_date: Dict[str, Set[int]] = {}
    replacements_by_date: Dict[str, List[Dict]] = {}
    for row in overrides:
        day = row["override_date"]
        bumped_by_date.setdefault(day, set()).add(row["original_officer_id"])
        if row["replacement_officer_id"]:
            replacements_by_date.setdefault(day, []).append(row)

    counts: Dict[Tuple[str, str, str], int] = {}
    current = start_date
    while current <= end_date:
        day_str = current.strftime("%Y-%m-%d")
        bumped = bumped_by_date.get(day_str, set())
        for squad in ("A", "B"):
            for shift_start in shift_starts:
                base = sum(
                    1
                    for o in officers
                    if is_officer_active(o)
                    and o.get("squad")
                    and o.get("shift_start")
                    and o["squad"] == squad
                    and o["shift_start"] == shift_start
                    and o["id"] not in bumped
                )
                repl = 0
                seen: Set[int] = set()
                for row in replacements_by_date.get(day_str, []):
                    rid = row["replacement_officer_id"]
                    if not rid or rid in seen:
                        continue
                    off = next((o for o in officers if o["id"] == rid), None)
                    if not off or not is_officer_active(off) or off["squad"] != squad:
                        continue
                    effective = row.get("covered_shift_start") or off["shift_start"]
                    if effective == shift_start:
                        seen.add(rid)
                        repl += 1
                counts[(day_str, squad, shift_start)] = base + repl
        current += timedelta(days=1)
    return counts


def get_shift_number(shift_start: str) -> int:
    for num, (start, _) in SHIFT_TIMES.items():
        if start == shift_start:
            return num
    try:
        hour = int(shift_start.split(":")[0])
        return (hour // 6) + 1
    except ValueError:
        return 0


def _shift_end_for_start(shift_start: str) -> str:
    for start, end in SHIFT_TIMES.values():
        if start == shift_start:
            return end
    return shift_start


def _shift_bounds(target_date: date, shift_start: str, shift_end: str) -> Tuple[datetime, datetime]:
    hour_s, min_s = map(int, shift_start.split(":"))
    hour_e, min_e = map(int, shift_end.split(":"))
    start_dt = datetime(target_date.year, target_date.month, target_date.day, hour_s, min_s)
    end_dt = datetime(target_date.year, target_date.month, target_date.day, hour_e, min_e)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return start_dt, end_dt


def get_officer_effective_shift_band(officer_id: int, target_date: date) -> Optional[Tuple[str, str]]:
    status = get_officer_day_status(officer_id, target_date)
    if status not in ("working", "covering", "swapped"):
        return None
    officer = get_officer_by_id(officer_id)
    if not officer:
        return None
    shift_start = officer["shift_start"]
    shift_end = officer["shift_end"]
    if status == "covering":
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT covered_shift_start FROM schedule_overrides
            WHERE override_date = ? AND replacement_officer_id = ?
            LIMIT 1
        """,
            (target_date.isoformat(), officer_id),
        )
        row = cursor.fetchone()
        conn.close()
        if row and row["covered_shift_start"]:
            shift_start = row["covered_shift_start"]
            shift_end = _shift_end_for_start(shift_start)
    return shift_start, shift_end


def compute_minimum_rest_gap(
    officer_id: int,
    assignment_date: date,
    new_shift_start: str,
    new_shift_end: str,
) -> Optional[float]:
    new_start_dt, new_end_dt = _shift_bounds(assignment_date, new_shift_start, new_shift_end)
    min_gap = None
    for delta in (-1, 1):
        adj_date = assignment_date + timedelta(days=delta)
        band = get_officer_effective_shift_band(officer_id, adj_date)
        if not band:
            continue
        adj_start_dt, adj_end_dt = _shift_bounds(adj_date, band[0], band[1])
        if delta == -1:
            gap = (new_start_dt - adj_end_dt).total_seconds() / 3600.0
        else:
            gap = (adj_start_dt - new_end_dt).total_seconds() / 3600.0
        if min_gap is None or gap < min_gap:
            min_gap = gap
    return min_gap


def officer_meets_minimum_rest(
    officer_id: int,
    assignment_date: date,
    shift_start: str,
    shift_end: str,
) -> bool:
    from config import MIN_REST_HOURS_BETWEEN_SHIFTS
    from validators import validate_minimum_rest_gap

    gap = compute_minimum_rest_gap(officer_id, assignment_date, shift_start, shift_end)
    return validate_minimum_rest_gap(gap, MIN_REST_HOURS_BETWEEN_SHIFTS).ok


def describe_minimum_rest_violation(
    officer_id: int,
    assignment_date: date,
    shift_start: str,
    shift_end: str,
    officer_name: Optional[str] = None,
) -> Optional[str]:
    """Return a user-facing rest violation message, or None if rest is satisfied."""
    from config import MIN_REST_HOURS_BETWEEN_SHIFTS

    if officer_meets_minimum_rest(officer_id, assignment_date, shift_start, shift_end):
        return None
    gap = compute_minimum_rest_gap(officer_id, assignment_date, shift_start, shift_end)
    label = officer_name or "Officer"
    gap_text = f"{gap:.1f}h" if gap is not None else "insufficient rest"
    return (
        f"Minimum rest violation: {label} has {gap_text} between shifts "
        f"(minimum {MIN_REST_HOURS_BETWEEN_SHIFTS:.0f}h) — supervisor override required"
    )


def find_replacement_officer(
    original_officer_id: int,
    request_date: str,
    squad: str,
    shift_start: str,
    extra_busy: Optional[Set[int]] = None,
) -> Optional[Dict]:
    shift_num = get_shift_number(shift_start)
    allowed_shifts = BUMP_RULES.get(shift_num, (1, 2, 3, 4))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT DISTINCT original_officer_id, replacement_officer_id
        FROM schedule_overrides
        WHERE override_date = ?
    """,
        (request_date,),
    )

    busy_ids = set(extra_busy or ())
    for row in cursor.fetchall():
        busy_ids.add(row["original_officer_id"])
        if row["replacement_officer_id"]:
            busy_ids.add(row["replacement_officer_id"])

    cursor.execute(
        """
        SELECT * FROM officers
        WHERE squad = ? AND active = 1 AND id != ?
        ORDER BY id ASC
    """,
        (squad, original_officer_id),
    )

    coverage_end = _shift_end_for_start(shift_start)
    coverage_date = parse_date(request_date)
    on_duty_pick = None
    off_duty_rest_ok = None
    off_duty_rest_bad = None
    for row in cursor.fetchall():
        officer = dict(row)
        if officer["id"] in busy_ids:
            continue
        if get_shift_number(officer["shift_start"]) not in allowed_shifts:
            continue
        if is_officer_working_on_day(officer["id"], coverage_date):
            on_duty_pick = on_duty_pick or officer
        elif officer_meets_minimum_rest(
            officer["id"],
            coverage_date,
            shift_start,
            coverage_end,
        ):
            off_duty_rest_ok = off_duty_rest_ok or officer
        else:
            off_duty_rest_bad = off_duty_rest_bad or officer

    conn.close()
    return on_duty_pick or off_duty_rest_ok or off_duty_rest_bad


def _bump_suggestion_from_rust(data: Dict) -> BumpChainSuggestion:
    steps = [
        BumpChainStep(
            step_number=s["step_number"],
            original_officer_id=s["original_officer_id"],
            original_officer_name=s["original_officer_name"],
            original_shift=s["original_shift"],
            replacement_officer_id=s["replacement_officer_id"],
            replacement_officer_name=s["replacement_officer_name"],
            replacement_shift=s["replacement_shift"],
            replacement_on_duty=s["replacement_on_duty"],
        )
        for s in data.get("steps", [])
    ]
    chain = [(int(a), int(b)) for a, b in data.get("chain", [])]
    return BumpChainSuggestion(
        success=bool(data.get("success")),
        chain=chain,
        steps=steps,
        primary_replacement_name=data.get("primary_replacement_name"),
        message=data.get("message", ""),
        requires_manual=bool(data.get("requires_manual")),
        failure_reason=data.get("failure_reason"),
    )


def suggest_bump_chain(
    original_officer_id: int,
    request_date: str,
    squad: str,
    shift_start: str,
    max_depth: int = 8,
) -> BumpChainSuggestion:
    """Suggest a complete bump chain with step-by-step coverage detail."""
    req_date = parse_date(request_date)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM officers WHERE active = 1 ORDER BY id ASC",
    )
    officers = [dict(row) for row in cursor.fetchall()]
    cursor.execute(
        """
        SELECT original_officer_id, replacement_officer_id, reason
        FROM schedule_overrides WHERE override_date = ?
        """,
        (request_date,),
    )
    overrides_on_date = [
        (
            row["original_officer_id"],
            row["replacement_officer_id"],
            None,
            row["reason"] or "",
        )
        for row in cursor.fetchall()
    ]
    conn.close()

    shift_times = list(SHIFT_TIMES.values())
    rust_data = rust_bridge.suggest_bump_chain_rust(
        officers,
        overrides_on_date,
        original_officer_id,
        request_date,
        squad,
        shift_start,
        BUMP_RULES,
        shift_times,
        NIGHT_MINIMUM_OFFICERS,
        MIN_REST_HOURS_BETWEEN_SHIFTS,
        ROTATION_BASE_DATE,
        ROTATION_CYCLE_LENGTH,
        max_depth,
    )
    if rust_data is not None:
        return _bump_suggestion_from_rust(rust_data)

    if applies_night_minimum(req_date, shift_start, is_high_risk_night):
        current = count_officers_on_shift_on_date(req_date, squad, shift_start)
        if night_minimum_violation(current):
            return BumpChainSuggestion(
                success=False,
                message="Would drop night coverage below minimum on a high-risk night",
                requires_manual=True,
                failure_reason="night_minimum",
            )

    chain: List[Tuple[int, int]] = []
    steps: List[BumpChainStep] = []
    busy: Set[int] = {original_officer_id}
    current_id = original_officer_id
    current_squad = squad
    current_shift = shift_start

    while len(chain) < max_depth:
        current = get_officer_by_id(current_id)
        if not current:
            return BumpChainSuggestion(
                success=False,
                message="Officer not found while planning coverage",
                requires_manual=True,
                failure_reason="officer_missing",
            )

        replacement = find_replacement_officer(current_id, request_date, current_squad, current_shift, extra_busy=busy)
        if not replacement:
            if not chain:
                return BumpChainSuggestion(
                    success=False,
                    message="No replacement available on an allowed shift",
                    requires_manual=True,
                    failure_reason="no_replacement",
                    blocked_officer_name=current["name"],
                    blocked_shift=current_shift,
                )
            return BumpChainSuggestion(
                success=False,
                steps=steps,
                message=(
                    f"Cascade incomplete — no cover for {current['name']}'s "
                    f"{current_shift} shift after earlier assignments"
                ),
                requires_manual=True,
                failure_reason="cascade_incomplete",
                blocked_officer_name=current["name"],
                blocked_shift=current_shift,
            )

        on_duty = is_officer_working_on_day(replacement["id"], req_date)
        steps.append(
            BumpChainStep(
                step_number=len(steps) + 1,
                original_officer_id=current_id,
                original_officer_name=current["name"],
                original_shift=current_shift,
                replacement_officer_id=replacement["id"],
                replacement_officer_name=replacement["name"],
                replacement_shift=replacement["shift_start"],
                replacement_on_duty=on_duty,
            )
        )
        chain.append((current_id, replacement["id"]))
        busy.add(replacement["id"])

        if not on_duty:
            coverage_end = _shift_end_for_start(current_shift)
            rest_msg = describe_minimum_rest_violation(
                replacement["id"],
                req_date,
                current_shift,
                coverage_end,
                officer_name=replacement["name"],
            )
            primary = get_officer_by_id(chain[0][1])
            if rest_msg:
                return BumpChainSuggestion(
                    success=False,
                    chain=chain,
                    steps=steps,
                    primary_replacement_name=primary["name"] if primary else None,
                    requires_manual=True,
                    failure_reason="minimum_rest",
                    message=rest_msg,
                    blocked_officer_name=replacement["name"],
                    blocked_shift=current_shift,
                )
            return BumpChainSuggestion(
                success=True,
                chain=chain,
                steps=steps,
                primary_replacement_name=primary["name"] if primary else None,
                message=f"Auto-approve ready — {len(chain)} assignment(s)",
            )

        current_id = replacement["id"]
        current_squad = replacement["squad"]
        current_shift = replacement["shift_start"]

    last = steps[-1] if steps else None
    return BumpChainSuggestion(
        success=False,
        steps=steps,
        message="Coverage chain too deep — supervisor must assign manually",
        requires_manual=True,
        failure_reason="cascade_too_deep",
        blocked_officer_name=last.replacement_officer_name if last else None,
        blocked_shift=last.replacement_shift if last else shift_start,
    )


def plan_bump_chain(
    original_officer_id: int,
    request_date: str,
    squad: str,
    shift_start: str,
    max_depth: int = 8,
) -> Tuple[List[Tuple[int, int]], Optional[str]]:
    """Build a complete bump chain. Partial cascades are rejected for manual review."""
    suggestion = suggest_bump_chain(original_officer_id, request_date, squad, shift_start, max_depth=max_depth)
    if suggestion.success:
        return suggestion.chain, None
    return [], suggestion.message


def format_bump_suggestion(suggestion: BumpChainSuggestion) -> str:
    if suggestion.success:
        lines = [suggestion.message or "Coverage plan ready."]
        for step in suggestion.steps:
            lines.append(
                f"Step {step.step_number}: {step.replacement_officer_name} "
                f"covers {step.original_officer_name} ({step.original_shift})"
            )
        return "\n".join(lines)
    lines = [f"Supervisor required: {suggestion.message}"]
    if suggestion.blocked_officer_name and suggestion.blocked_shift:
        lines.append(f"Blocked at: {suggestion.blocked_officer_name} ({suggestion.blocked_shift})")
    for step in suggestion.steps:
        lines.append(
            f"Step {step.step_number}: {step.replacement_officer_name} → "
            f"{step.original_officer_name} ({step.original_shift})"
        )
    return "\n".join(lines)


def validate_bump_feasibility(officer_id: int, request_date: str, squad: str, shift_start: str) -> BumpSimulationResult:
    suggestion = suggest_bump_chain(officer_id, request_date, squad, shift_start)
    if suggestion.success:
        return BumpSimulationResult(
            success=True,
            replacement_name=suggestion.primary_replacement_name,
            message=suggestion.message,
            suggestion=suggestion,
        )
    return BumpSimulationResult(
        success=False,
        message=suggestion.message,
        requires_manual=True,
        reason=suggestion.failure_reason,
        suggestion=suggestion,
    )


def build_schedule_matrix(start_date: date, end_date: date) -> Tuple[List[Dict], List[date]]:
    officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]

    bumped_by_date, covering_by_date, swapped_by_date, bumped_status_by_date = _load_override_maps_for_range(
        start_date, end_date
    )
    rust_matrix = rust_bridge.build_schedule_matrix_rust(
        officers,
        bumped_by_date,
        covering_by_date,
        swapped_by_date,
        bumped_status_by_date,
        start_date,
        end_date,
        ROTATION_BASE_DATE,
        ROTATION_CYCLE_LENGTH,
    )
    if rust_matrix is not None:
        return rust_matrix

    days: List[date] = []
    current = start_date
    while current <= end_date:
        days.append(current)
        current += timedelta(days=1)

    matrix = []
    for officer in officers:
        day_status = {
            d: _officer_day_status(
                officer,
                d,
                bumped_by_date,
                covering_by_date,
                swapped_by_date,
                bumped_status_by_date,
            )
            for d in days
        }
        matrix.append({"officer": officer, "days": day_status})

    return matrix, days


def get_officer_day_status(officer_id: int, target_date: date) -> str:
    statuses = batch_officer_day_status([(officer_id, target_date)])
    return statuses.get((officer_id, target_date.strftime("%Y-%m-%d")), "off")


def batch_officer_day_status(
    pairs: List[Tuple[int, date]],
) -> Dict[Tuple[int, str], str]:
    """Resolve schedule status for many (officer_id, date) pairs with one override load."""
    if not pairs:
        return {}
    officers_by_id = {o["id"]: o for o in get_officers_by_seniority()}
    min_d = min(d for _, d in pairs)
    max_d = max(d for _, d in pairs)
    bumped_by_date, covering_by_date, swapped_by_date, bumped_status_by_date = _load_override_maps_for_range(
        min_d, max_d
    )
    result: Dict[Tuple[int, str], str] = {}
    for officer_id, target in pairs:
        officer = officers_by_id.get(officer_id)
        if not officer:
            result[(officer_id, target.strftime("%Y-%m-%d"))] = "off"
            continue
        result[(officer_id, target.strftime("%Y-%m-%d"))] = _officer_day_status(
            officer,
            target,
            bumped_by_date,
            covering_by_date,
            swapped_by_date,
            bumped_status_by_date,
        )
    return result


def _get_monthly_rotation_base_only(year: int, month: int) -> List[Dict]:
    from calendar import monthrange

    _, last_day = monthrange(year, month)
    officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
    summary = []
    for day_num in range(1, last_day + 1):
        target = date(year, month, day_num)
        cycle_day = get_cycle_day(target)
        squad = get_squad_on_duty(cycle_day)
        working_count = sum(1 for o in officers if _rotation_only_status(o, target) == "working")
        summary.append(
            {
                "date": target,
                "cycle_day": cycle_day,
                "squad_on_duty": squad,
                "working_officers": working_count,
                "high_risk_night": is_high_risk_night(target),
                "snapshot_rows": [],
            }
        )
    return summary


def _load_override_maps_for_range(
    start_date: date, end_date: date
) -> Tuple[
    Dict[str, Set[int]],
    Dict[str, Set[int]],
    Dict[str, Set[int]],
    Dict[str, Dict[int, str]],
]:
    """Return bumped/covering/swapped maps and per-day bumped schedule statuses."""
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT override_date, original_officer_id, replacement_officer_id, reason
        FROM schedule_overrides
        WHERE override_date >= ? AND override_date <= ?
    """,
        (start_str, end_str),
    )
    bumped_by_date: Dict[str, Set[int]] = {}
    covering_by_date: Dict[str, Set[int]] = {}
    swapped_by_date: Dict[str, Set[int]] = {}
    bumped_status_by_date: Dict[str, Dict[int, str]] = {}
    for row in cursor.fetchall():
        day_key = row["override_date"]
        original_id = row["original_officer_id"]
        replacement_id = row["replacement_officer_id"]
        if row["reason"] == "Shift Swap":
            swapped_by_date.setdefault(day_key, set()).add(original_id)
            if replacement_id:
                swapped_by_date.setdefault(day_key, set()).add(replacement_id)
            continue
        bumped_by_date.setdefault(day_key, set()).add(original_id)
        bumped_status_by_date.setdefault(day_key, {})[original_id] = _schedule_status_for_override_reason(row["reason"])
        if replacement_id:
            covering_by_date.setdefault(day_key, set()).add(replacement_id)
    conn.close()
    return bumped_by_date, covering_by_date, swapped_by_date, bumped_status_by_date


def _schedule_status_for_override_reason(reason: Optional[str]) -> str:
    from config import REQUEST_TYPE_SCHEDULE_STATUS

    if reason and reason.startswith("Day-off: "):
        req_type = reason[len("Day-off: ") :].strip()
        return REQUEST_TYPE_SCHEDULE_STATUS.get(req_type, "bumped")
    return "bumped"


def _officer_day_status(
    officer: Dict,
    target_date: date,
    bumped_by_date: Dict[str, Set[int]],
    covering_by_date: Dict[str, Set[int]],
    swapped_by_date: Optional[Dict[str, Set[int]]] = None,
    bumped_status_by_date: Optional[Dict[str, Dict[int, str]]] = None,
) -> str:
    date_str = target_date.strftime("%Y-%m-%d")
    officer_id = officer["id"]
    if swapped_by_date and officer_id in swapped_by_date.get(date_str, ()):
        return "swapped"
    if officer_id in bumped_by_date.get(date_str, ()):
        if bumped_status_by_date:
            return bumped_status_by_date.get(date_str, {}).get(officer_id, "bumped")
        return "bumped"
    if officer_id in covering_by_date.get(date_str, ()):
        return "covering"
    cycle_day = get_cycle_day(target_date)
    if officer["squad"] == get_squad_on_duty(cycle_day):
        return "working"
    return "off"


def _officer_history_reason(cursor, officer_id: int) -> Optional[str]:
    history_checks = [
        ("day off requests", "SELECT 1 FROM day_off_requests WHERE officer_id = ? LIMIT 1", (officer_id,)),
        ("payroll entries", "SELECT 1 FROM payroll_entries WHERE officer_id = ? LIMIT 1", (officer_id,)),
        ("notifications", "SELECT 1 FROM notifications WHERE recipient_officer_id = ? LIMIT 1", (officer_id,)),
        (
            "schedule overrides",
            "SELECT 1 FROM schedule_overrides WHERE original_officer_id = ? OR replacement_officer_id = ? LIMIT 1",
            (officer_id, officer_id),
        ),
        (
            "shift swaps",
            "SELECT 1 FROM shift_swaps WHERE officer1_id = ? OR officer2_id = ? LIMIT 1",
            (officer_id, officer_id),
        ),
    ]
    for label, query, params in history_checks:
        cursor.execute(query, params)
        if cursor.fetchone():
            return label
    return None


def _officer_shift_hours(officer: Dict) -> float:
    start = officer["shift_start"].split(":")
    end = officer["shift_end"].split(":")
    start_m = int(start[0]) * 60 + int(start[1])
    end_m = int(end[0]) * 60 + int(end[1])
    if end_m <= start_m:
        end_m += 24 * 60
    return round((end_m - start_m) / 60, 2)


def _officer_work_days_per_cycle(officer: Dict) -> int:
    count = 0
    for day in range(1, ROTATION_CYCLE_LENGTH + 1):
        if get_squad_on_duty(day) == officer["squad"]:
            count += 1
    return count


def _rotation_only_status(officer: Dict, target_date: date) -> str:
    cycle_day = get_cycle_day(target_date)
    if officer["squad"] == get_squad_on_duty(cycle_day):
        return "working"
    return "off"


def _shift_hours(shift_start: str, shift_end: str) -> float:
    start_h, start_m = map(int, shift_start.split(":"))
    end_h, end_m = map(int, shift_end.split(":"))
    start_mins = start_h * 60 + start_m
    end_mins = end_h * 60 + end_m
    if end_mins <= start_mins:
        end_mins += 24 * 60
    return round((end_mins - start_mins) / 60, 2)


def get_monthly_rotation_summary(year: int, month: int) -> List[Dict]:
    return _get_monthly_rotation_base_only(year, month)


def get_officer_work_dates_from_summary(
    officer_id: int,
    summary: List[Dict],
) -> Set[str]:
    """ISO dates in a monthly summary where the officer is scheduled on duty."""
    if not officer_id or not summary:
        return set()
    officer = get_officer_by_id(officer_id)
    if not officer:
        return set()

    dates: Set[str] = set()
    for entry in summary:
        target = entry["date"]
        rows = entry.get("snapshot_rows")
        if rows:
            if any(r.get("officer_id") == officer_id and r.get("status") in _OFFICER_WORKING_STATUSES for r in rows):
                dates.add(target.isoformat())
        elif get_officer_day_status(officer_id, target) in _OFFICER_WORKING_STATUSES:
            dates.add(target.isoformat())
    return dates


def get_schedule_conflicts(
    start_date: date,
    end_date: date,
    officer_id: Optional[int] = None,
) -> Dict:
    from analytics import get_schedule_conflicts as _conflicts

    return _conflicts(start_date, end_date, officer_id=officer_id)


def run_schedule_simulation(
    rotation_type: str,
    num_officers: int,
    shift_length_hours: float,
    annual_hours_target: float,
    shift_starts: List[str],
    apply_department_rules: bool = True,
    min_per_shift: int = 1,
    simulation_days: int = 28,
) -> Dict:
    from simulator import SimulatorConfig, simulate_schedule

    config = SimulatorConfig(
        rotation_type=rotation_type,
        num_officers=num_officers,
        shift_length_hours=shift_length_hours,
        annual_hours_target=annual_hours_target,
        shift_starts=shift_starts,
        apply_department_rules=apply_department_rules,
        min_per_shift=min_per_shift,
        simulation_days=simulation_days,
    )
    result = simulate_schedule(config)
    if not result.success:
        return {"success": False, "message": result.message or "Simulation failed"}
    return {
        "success": True,
        "metrics": result.metrics,
        "officer_slots": [slot.__dict__ for slot in result.officer_slots],
        "suggestions": [
            {"severity": s.severity, "title": s.title, "message": s.message, "recommendation": s.recommendation}
            for s in result.suggestions
        ],
        "shift_templates": result.shift_templates,
    }


def get_simulator_defaults_from_roster() -> Dict:
    from simulator import config_from_current_roster

    cfg = config_from_current_roster()
    return {
        "success": True,
        "rotation_type": cfg.rotation_type,
        "num_officers": cfg.num_officers,
        "shift_length_hours": cfg.shift_length_hours,
        "annual_hours_target": cfg.annual_hours_target,
        "shift_starts": ", ".join(cfg.shift_starts),
        "apply_department_rules": cfg.apply_department_rules,
        "min_per_shift": cfg.min_per_shift,
    }
