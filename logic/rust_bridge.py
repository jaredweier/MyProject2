"""
Rust-primary scheduling engine bridge (PyO3: scheduler_core).

POLICY — Rust is authoritative for:
  rotation math, officer day status, schedule matrix, coverage counts,
  bump chains (rest + consecutive compliance), minimum-rest gaps,
  consecutive-work streaks, and simulator metrics.

Python in logic/scheduling.py handles SQLite I/O, request workflow, and UI glue.
logic/rust_fallback.py holds emergency Python math when the extension is missing.

Build: python dev.py build-rust
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

_RUST = None
_RUST_ERROR: Optional[str] = None

try:
    import scheduler_core as _RUST
except ImportError as exc:
    _RUST_ERROR = str(exc)

RUST_PRIMARY_OPS = (
    "get_cycle_day",
    "get_squad_on_duty",
    "officer_rotation_working",
    "batch_day_status",
    "build_schedule_matrix",
    "compute_coverage_counts",
    "minimum_rest_gap",
    "consecutive_work_days",
    "suggest_bump_chain",
    "simulate_schedule",
)


def available() -> bool:
    return _RUST is not None


def backend_name() -> str:
    return "rust" if available() else "python-fallback"


def load_error() -> Optional[str]:
    return _RUST_ERROR


def prefer_rust() -> bool:
    """True unless SCHEDULER_ALLOW_PYTHON_MATH=1 (tests/CI without cargo)."""
    if os.environ.get("SCHEDULER_ALLOW_PYTHON_MATH", "").strip() in ("1", "true", "yes"):
        return False
    return available()


def _rotation_schedule() -> Dict[str, Any]:
    from logic.rotation_config import get_rust_rotation_schedule

    return get_rust_rotation_schedule()


def get_cycle_day(target_date: date, base_date: date, cycle_length: int) -> int:
    if _RUST:
        return int(
            _RUST.get_cycle_day(
                base_date.isoformat(),
                target_date.isoformat(),
                cycle_length,
            )
        )
    days_diff = (target_date - base_date).days
    if days_diff < 0:
        days_diff += (-(days_diff // cycle_length) + 1) * cycle_length
    return (days_diff % cycle_length) + 1


def get_squad_on_duty(cycle_day: int) -> str:
    from logic.rotation_config import get_squad_on_duty as active_squad_on_duty

    if _RUST:
        return str(_RUST.get_squad_on_duty(cycle_day, _rotation_schedule()))
    return active_squad_on_duty(cycle_day)


def _override_maps_for_rust(
    bumped_by_date: Dict[str, Set[int]],
    covering_by_date: Dict[str, Set[int]],
    swapped_by_date: Dict[str, Set[int]],
    bumped_status_by_date: Dict[str, Dict[int, str]],
) -> Tuple[Dict[str, List[int]], Dict[str, List[int]], Dict[str, List[int]], Dict[str, Dict[int, str]]]:
    return (
        {k: list(v) for k, v in bumped_by_date.items()},
        {k: list(v) for k, v in covering_by_date.items()},
        {k: list(v) for k, v in swapped_by_date.items()},
        bumped_status_by_date,
    )


def batch_day_status(
    officers: List[Dict],
    bumped_by_date: Dict[str, Set[int]],
    covering_by_date: Dict[str, Set[int]],
    swapped_by_date: Dict[str, Set[int]],
    bumped_status_by_date: Dict[str, Dict[int, str]],
    pairs: List[Tuple[int, str]],
    base_date: date,
    cycle_length: int,
) -> Optional[Dict[Tuple[int, str], str]]:
    """Resolve (officer_id, YYYY-MM-DD) statuses — Rust when built."""
    if not _RUST or not pairs:
        return None
    raw = _RUST.batch_day_status(
        officers,
        {k: list(v) for k, v in bumped_by_date.items()},
        {k: list(v) for k, v in covering_by_date.items()},
        {k: list(v) for k, v in swapped_by_date.items()},
        bumped_status_by_date,
        pairs,
        base_date.isoformat(),
        cycle_length,
        _rotation_schedule(),
    )
    return {(int(key[0]), str(key[1])): str(status) for key, status in raw.items()}


def officer_rotation_working(
    squad: str,
    shift_start: str,
    active: bool,
    job_title: str,
    target_date: date,
    base_date: date,
    cycle_length: int,
) -> Optional[bool]:
    if not _RUST:
        return None
    return bool(
        _RUST.officer_rotation_working(
            squad or "",
            shift_start or "",
            active,
            job_title or "",
            target_date.isoformat(),
            base_date.isoformat(),
            cycle_length,
            _rotation_schedule(),
        )
    )


def build_schedule_matrix(
    officers: List[Dict],
    bumped_by_date: Dict[str, Set[int]],
    covering_by_date: Dict[str, Set[int]],
    swapped_by_date: Dict[str, Set[int]],
    bumped_status_by_date: Dict[str, Dict[int, str]],
    start_date: date,
    end_date: date,
    base_date: date,
    cycle_length: int,
) -> Optional[Tuple[List[Dict], List[date]]]:
    if not _RUST:
        return None
    payload = _RUST.build_schedule_matrix(
        officers,
        {k: list(v) for k, v in bumped_by_date.items()},
        {k: list(v) for k, v in covering_by_date.items()},
        {k: list(v) for k, v in swapped_by_date.items()},
        bumped_status_by_date,
        start_date.isoformat(),
        end_date.isoformat(),
        base_date.isoformat(),
        cycle_length,
        _rotation_schedule(),
    )
    days: List[date] = []
    for iso in payload["days"]:
        y, m, d = (int(x) for x in iso.split("-"))
        days.append(date(y, m, d))
    officers_by_id = {o["id"]: o for o in officers}
    matrix = []
    for entry in payload["matrix"]:
        off = entry["officer"]
        if isinstance(off, dict):
            officer = off
        else:
            officer = officers_by_id.get(off["id"], off)
        day_status = {}
        for iso, status in entry["days"].items():
            y, m, d = (int(x) for x in iso.split("-"))
            day_status[date(y, m, d)] = status
        matrix.append({"officer": officer, "days": day_status})
    return matrix, days


def compute_coverage_counts(
    officers: List[Dict],
    overrides: List[Tuple[str, int, Optional[int], Optional[str]]],
    start_date: date,
    end_date: date,
    shift_starts: List[str],
    base_date: date,
    cycle_length: int,
) -> Optional[Dict[Tuple[str, str, str], int]]:
    if not _RUST:
        return None
    raw = _RUST.compute_coverage_counts(
        officers,
        overrides,
        start_date.isoformat(),
        end_date.isoformat(),
        shift_starts,
        base_date.isoformat(),
        cycle_length,
        _rotation_schedule(),
    )
    out: Dict[Tuple[str, str, str], int] = {}
    for key, count in raw.items():
        out[(key[0], key[1], key[2])] = int(count)
    return out


def minimum_rest_gap(
    officer_id: int,
    assignment_date: date,
    new_shift_start: str,
    new_shift_end: str,
    officer_shift_start: str,
    officer_shift_end: str,
    bumped_by_date: Dict[str, Set[int]],
    covering_by_date: Dict[str, Set[int]],
    swapped_by_date: Dict[str, Set[int]],
    bumped_status_by_date: Dict[str, Dict[int, str]],
    covering_shift_starts: Dict[str, Dict[int, str]],
    shift_times: List[Tuple[str, str]],
    base_date: date,
    cycle_length: int,
) -> Optional[float]:
    if not _RUST:
        return None
    bumped, covering, swapped, bumped_status = _override_maps_for_rust(
        bumped_by_date, covering_by_date, swapped_by_date, bumped_status_by_date
    )
    gap = _RUST.minimum_rest_gap(
        officer_id,
        assignment_date.isoformat(),
        new_shift_start,
        new_shift_end,
        bumped,
        covering,
        swapped,
        bumped_status,
        officer_shift_start,
        officer_shift_end,
        shift_times,
        base_date.isoformat(),
        cycle_length,
        _rotation_schedule(),
        covering_shift_starts or None,
    )
    return float(gap) if gap is not None else None


def consecutive_work_days(
    officer_id: int,
    squad: str,
    shift_start: str,
    active: bool,
    job_title: str,
    end_date: date,
    bumped_by_date: Dict[str, Set[int]],
    covering_by_date: Dict[str, Set[int]],
    swapped_by_date: Dict[str, Set[int]],
    bumped_status_by_date: Dict[str, Dict[int, str]],
    base_date: date,
    cycle_length: int,
    max_lookback: int = 20,
) -> Optional[int]:
    if not _RUST:
        return None
    bumped, covering, swapped, bumped_status = _override_maps_for_rust(
        bumped_by_date, covering_by_date, swapped_by_date, bumped_status_by_date
    )
    return int(
        _RUST.consecutive_work_days(
            officer_id,
            squad or "",
            shift_start or "",
            active,
            job_title or "",
            end_date.isoformat(),
            bumped,
            covering,
            swapped,
            bumped_status,
            base_date.isoformat(),
            cycle_length,
            _rotation_schedule(),
            max_lookback,
        )
    )


def suggest_bump_chain(
    officers: List[Dict],
    overrides_on_date: List[Tuple[int, Optional[int], Optional[str], str]],
    original_officer_id: int,
    request_date: str,
    squad: str,
    shift_start: str,
    bump_rules_by_start: Dict[str, Tuple[str, ...]],
    shift_times: List[Tuple[str, str]],
    schedule_context: Dict[int, Dict[str, str]],
    night_minimum: int,
    min_rest_hours: float,
    base_date: date,
    cycle_length: int,
    max_assignments_before_busy: int = 2,
    max_depth: int = 8,
    enforce_minimum_rest: bool = True,
    enforce_consecutive_work: bool = True,
    max_consecutive_work_days: int = 13,
    covering_shift_starts: Optional[Dict[str, Dict[int, str]]] = None,
) -> Optional[Dict[str, Any]]:
    if not _RUST:
        return None
    rules = {start: list(allowed) for start, allowed in bump_rules_by_start.items()}
    context = {
        officer_id: {
            "status": ctx.get("status", "off"),
            "shift_start": ctx.get("shift_start", ""),
        }
        for officer_id, ctx in schedule_context.items()
    }
    return dict(
        _RUST.suggest_bump_chain(
            officers,
            overrides_on_date,
            original_officer_id,
            request_date,
            squad,
            shift_start,
            rules,
            shift_times,
            context,
            night_minimum,
            min_rest_hours,
            max_consecutive_work_days,
            covering_shift_starts,
            base_date.isoformat(),
            cycle_length,
            _rotation_schedule(),
            max_assignments_before_busy,
            max_depth,
            enforce_minimum_rest,
            enforce_consecutive_work,
        )
    )


def simulate_schedule(
    config_dict: Dict[str, Any],
    preset_dict: Dict[str, Any],
    sim_start: date,
) -> Optional[Dict[str, Any]]:
    if not _RUST:
        return None
    return dict(
        _RUST.simulate_schedule(
            config_dict,
            preset_dict,
            sim_start.isoformat(),
        )
    )


# Backward-compatible aliases (prefer unprefixed names above)
batch_day_status_rust = batch_day_status
officer_rotation_working_rust = officer_rotation_working
build_schedule_matrix_rust = build_schedule_matrix
compute_coverage_counts_rust = compute_coverage_counts
minimum_rest_gap_rust = minimum_rest_gap
consecutive_work_days_rust = consecutive_work_days
suggest_bump_chain_rust = suggest_bump_chain
simulate_schedule_rust = simulate_schedule
