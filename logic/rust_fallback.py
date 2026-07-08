"""
Emergency Python implementations for scheduling math.

Used only when scheduler_core is not built. Production and normal dev should
run `python dev.py build-rust` so logic/scheduling.py never hits these paths.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional, Set, Tuple

from validators import is_officer_active


def python_batch_day_status(
    officers: List[Dict],
    bumped_by_date: Dict[str, Set[int]],
    covering_by_date: Dict[str, Set[int]],
    swapped_by_date: Dict[str, Set[int]],
    bumped_status_by_date: Dict[str, Dict[int, str]],
    pair_keys: List[Tuple[int, str]],
    officer_day_status_fn,
) -> Dict[Tuple[int, str], str]:
    """Resolve statuses without Rust — mirrors scheduler_core batch_day_status."""
    officers_by_id = {o["id"]: o for o in officers}
    result: Dict[Tuple[int, str], str] = {}
    for officer_id, date_key in pair_keys:
        officer = officers_by_id.get(officer_id)
        if not officer:
            result[(officer_id, date_key)] = "off"
            continue
        y, m, d = (int(x) for x in date_key.split("-"))
        result[(officer_id, date_key)] = officer_day_status_fn(
            officer,
            date(y, m, d),
            bumped_by_date,
            covering_by_date,
            swapped_by_date,
            bumped_status_by_date,
        )
    return result


def python_compute_coverage_counts(
    officers: List[Dict],
    overrides: List[Tuple[str, int, Optional[int], Optional[str]]],
    start_date: date,
    end_date: date,
    shift_starts: List[str],
    *,
    get_cycle_day_fn,
    get_squad_on_duty_fn,
    normalize_shift_band_fn,
    officer_base_rotation_working_fn,
) -> Dict[Tuple[str, str, str], int]:
    """Shift headcount batch without Rust."""
    bumped_by_date: Dict[str, Set[int]] = {}
    replacements_by_date: Dict[str, List[Tuple[int, Optional[str]]]] = {}
    for day, orig, repl, covered in overrides:
        bumped_by_date.setdefault(day, set()).add(orig)
        if repl:
            replacements_by_date.setdefault(day, []).append((repl, covered))

    counts: Dict[Tuple[str, str, str], int] = {}
    current = start_date
    while current <= end_date:
        day_str = current.strftime("%Y-%m-%d")
        bumped = bumped_by_date.get(day_str, set())
        squad_on_duty = get_squad_on_duty_fn(get_cycle_day_fn(current))
        for squad in ("A", "B"):
            for shift_start in shift_starts:
                base = 0
                if squad == squad_on_duty:
                    base = sum(
                        1
                        for o in officers
                        if is_officer_active(o)
                        and o.get("squad") == squad
                        and normalize_shift_band_fn(o.get("shift_start") or "") == shift_start
                        and o["id"] not in bumped
                        and officer_base_rotation_working_fn(o, current)
                    )
                repl = 0
                seen: Set[int] = set()
                for rid, covered_start in replacements_by_date.get(day_str, []):
                    if not rid or rid in seen:
                        continue
                    off = next((o for o in officers if o["id"] == rid), None)
                    if not off or not is_officer_active(off) or off["squad"] != squad:
                        continue
                    effective = covered_start or off["shift_start"]
                    if normalize_shift_band_fn(effective or "") == shift_start:
                        seen.add(rid)
                        repl += 1
                counts[(day_str, squad, shift_start)] = base + repl
        current += timedelta(days=1)
    return counts


def python_build_schedule_matrix(
    officers: List[Dict],
    bumped_by_date: Dict[str, Set[int]],
    covering_by_date: Dict[str, Set[int]],
    swapped_by_date: Dict[str, Set[int]],
    bumped_status_by_date: Dict[str, Dict[int, str]],
    start_date: date,
    end_date: date,
    officer_day_status_fn,
) -> Tuple[List[Dict], List[date]]:
    """Build roster matrix without Rust."""
    days: List[date] = []
    current = start_date
    while current <= end_date:
        days.append(current)
        current += timedelta(days=1)

    matrix = []
    for officer in officers:
        day_status = {
            d: officer_day_status_fn(
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
