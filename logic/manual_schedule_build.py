"""Manual schedule builder for Chronos simulator.

User-owned grid: officers × days, each cell OFF or a start time.
Respects rotation ON/OFF when seeding; full manual override allowed.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from validators import format_date


def empty_grid(num_officers: int, num_days: int) -> List[List[Optional[str]]]:
    n = max(0, int(num_officers))
    d = max(1, int(num_days))
    return [[None for _ in range(d)] for _ in range(n)]


def _parse_starts(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [s.strip() for s in raw.replace(";", ",").split(",") if s.strip()]
    return [str(s).strip() for s in list(raw) if s is not None and str(s).strip()]


def _end_for_start(start: str, length_hours: float) -> str:
    try:
        parts = (start or "00:00").split(":")
        total = (int(parts[0]) * 60 + (int(parts[1]) if len(parts) > 1 else 0)) + int(round(float(length_hours) * 60))
        total %= 24 * 60
        return f"{total // 60:02d}:{total % 60:02d}"
    except (TypeError, ValueError, IndexError):
        return start or "00:00"


def seed_grid_from_rotation(
    *,
    num_officers: int,
    num_days: int,
    shift_starts: Sequence[str],
    rotation_type: str = "",
    rotation_style: str = "rotating",
    rotation_variations: Optional[Sequence[str]] = None,
    home_starts: Optional[Sequence[str]] = None,
    respect_off_days: bool = True,
) -> Dict[str, Any]:
    """Seed ON days with home starts; OFF days blank when respect_off_days."""
    from config import ROTATION_PRESETS
    from logic.rotation_patterns import build_pattern
    from simulator import _squad_working

    starts = _parse_starts(shift_starts)
    if not starts:
        starts = ["06:00", "14:00", "22:00"]
    grid = empty_grid(num_officers, num_days)
    homes = list(home_starts or [])
    while len(homes) < num_officers:
        homes.append(starts[len(homes) % len(starts)])

    patterns = []
    texts = [t for t in (rotation_variations or []) if (t or "").strip()]
    if texts:
        style = (rotation_style or "rotating").strip().lower() or None
        for t in texts:
            try:
                patterns.append(build_pattern(t, style=style if style in ("fixed", "rotating") else None))
            except ValueError:
                continue

    preset = ROTATION_PRESETS.get(rotation_type or "")
    on_count = 0
    off_count = 0
    for oi in range(num_officers):
        for day in range(num_days):
            working = True
            if respect_off_days:
                if patterns:
                    p = patterns[oi % len(patterns)]
                    cycle = max(p.cycle_length, 1)
                    phase = (oi * max(1, cycle // max(num_officers, 1))) % cycle
                    working = p.with_phase(phase).is_working((day % cycle) + 1)
                elif preset:
                    squad = "A" if oi % 2 == 0 else "B"
                    cycle = int(preset.get("cycle_length") or 14)
                    working = _squad_working(rotation_type, squad, (day % cycle) + 1, preset)
            if working:
                grid[oi][day] = homes[oi]
                on_count += 1
            else:
                grid[oi][day] = None
                off_count += 1

    return {
        "success": True,
        "grid": grid,
        "on_cells": on_count,
        "off_cells": off_count,
        "shift_starts": starts,
        "message": f"Seeded {on_count} on-duty cells, {off_count} off",
    }


def set_cell(
    grid: List[List[Optional[str]]],
    officer_index: int,
    day_index: int,
    start: Optional[str],
) -> Dict[str, Any]:
    if not grid:
        return {"success": False, "message": "Empty grid"}
    if officer_index < 0 or officer_index >= len(grid):
        return {"success": False, "message": "Bad officer index"}
    if day_index < 0 or day_index >= len(grid[0]):
        return {"success": False, "message": "Bad day index"}
    val = None if start in (None, "", "OFF", "Off", "off") else str(start).strip()
    grid[officer_index][day_index] = val
    return {"success": True, "grid": grid}


def evaluate_manual_grid(
    grid: List[List[Optional[str]]],
    *,
    shift_length_hours: float = 8.0,
    coverage_247: int = 0,
    use_extra_windows: bool = False,
    extra_windows: Optional[List[Dict]] = None,
    annual_hours_target: float = 2008.0,
    annual_hours_variance: float = 40.0,
    annual_hours_hard: bool = False,
    start_date: Optional[date] = None,
    rotation_type: str = "",
    rotation_style: str = "",
    rotation_variations: Optional[List[str]] = None,
    nearby_start_hops: int = 0,
    allow_offday_coverage: bool = False,
    min_rest_hours: float = 0.0,
    max_consecutive_work_days: int = 0,
) -> Dict[str, Any]:
    """Score a manual grid into a simulator-shaped result for publish / metrics."""
    if not grid or not grid[0]:
        return {"success": False, "message": "Grid is empty"}

    n_off = len(grid)
    n_days = len(grid[0])
    length = max(0.5, float(shift_length_hours))
    sim_start = start_date or date.today()

    day_assignments: List[Tuple[date, str, str]] = []
    officer_slots = []
    work_days = [0] * n_off
    rest_failures = 0
    consec_failures = 0
    min_rest = max(0.0, float(min_rest_hours or 0))
    max_consec = max(0, int(max_consecutive_work_days or 0))
    for oi in range(n_off):
        home = None
        prev_end_min = None
        streak = 0
        for day in range(n_days):
            st = grid[oi][day]
            if not st:
                streak = 0
                prev_end_min = None
                continue
            work_days[oi] += 1
            streak += 1
            if max_consec and streak > max_consec:
                consec_failures += 1
            if home is None:
                home = st
            en = _end_for_start(st, length)
            # Rest: previous end to this start (same calendar continuity simplified)
            try:
                parts = str(st).split(":")
                start_min = int(parts[0]) * 60 + (int(parts[1]) if len(parts) > 1 else 0)
            except (TypeError, ValueError, IndexError):
                start_min = 0
            if min_rest > 0 and prev_end_min is not None:
                # overnight: prev end may be next morning
                gap = (start_min + 24 * 60 - prev_end_min) % (24 * 60)
                if gap < min_rest * 60 - 1e-6:
                    rest_failures += 1
            try:
                ep = str(en).split(":")
                prev_end_min = int(ep[0]) * 60 + (int(ep[1]) if len(ep) > 1 else 0)
            except (TypeError, ValueError, IndexError):
                prev_end_min = None
            day_assignments.append((sim_start + timedelta(days=day), st, en))
        officer_slots.append(
            {
                "slot_id": oi + 1,
                "label": f"Officer {oi + 1}",
                "squad": "A" if oi % 2 == 0 else "B",
                "shift_start": home or "06:00",
                "shift_end": _end_for_start(home or "06:00", length),
                "projected_annual_hours": round(work_days[oi] * length * (365.0 / max(n_days, 1)), 1),
                "work_days_in_sim": work_days[oi],
            }
        )

    hard_ok = True
    if rest_failures or consec_failures:
        hard_ok = False
    coverage_247_failures = 0
    extra_window_failures = 0
    extra_window_checks = 0
    window_objs = []
    if use_extra_windows and extra_windows:
        from logic.coverage_windows_store import _parse_window_dict

        for item in extra_windows:
            if not isinstance(item, dict) or item.get("enabled") is False:
                continue
            w = _parse_window_dict(item)
            if w:
                window_objs.append(w)

    if (coverage_247 and coverage_247 > 0) or window_objs:
        from logic.coverage_timeline import evaluate_day_coverage

        for day_offset in range(n_days):
            day = sim_start + timedelta(days=day_offset)
            day_asg = [a for a in day_assignments if a[0] == day or a[0] == day - timedelta(days=1)]
            result = evaluate_day_coverage(
                day_asg,
                day,
                min_247=int(coverage_247 or 0),
                windows=window_objs or None,
            )
            for chk in result.get("checks") or []:
                if chk.get("skipped"):
                    continue
                is_window = "label" in chk or "range_start" in chk
                if is_window:
                    extra_window_checks += 1
                    if not chk.get("ok", True):
                        extra_window_failures += 1
                        hard_ok = False
                elif not chk.get("ok", True):
                    coverage_247_failures += 1
                    hard_ok = False

    hours_list = [s["projected_annual_hours"] for s in officer_slots]
    avg_hours = sum(hours_list) / len(hours_list) if hours_list else 0.0
    annual_band_outside = 0
    if annual_hours_hard and hours_list:
        band = max(float(annual_hours_variance or 0), 1.0)
        annual_band_outside = sum(1 for h in hours_list if abs(h - float(annual_hours_target)) > band)
        if annual_band_outside:
            hard_ok = False

    starts_used = sorted({st for row in grid for st in row if st})
    coverage_by_day = []
    for day_offset in range(n_days):
        day = sim_start + timedelta(days=day_offset)
        counts: Dict[str, int] = {}
        working = 0
        for oi in range(n_off):
            st = grid[oi][day_offset]
            if st:
                working += 1
                counts[st] = counts.get(st, 0) + 1
        coverage_by_day.append(
            {
                "date": format_date(day),
                "cycle_day": day_offset + 1,
                "shift_counts": counts,
                "working_officers": working,
                "min_shift_coverage": min(counts.values()) if counts else 0,
            }
        )

    metrics = {
        "hard_constraints_ok": hard_ok,
        "coverage_247_failures": coverage_247_failures,
        "coverage_247_ok": coverage_247_failures == 0,
        "extra_window_failures": extra_window_failures,
        "extra_window_checks": extra_window_checks,
        "avg_annual_hours": round(avg_hours, 1),
        "annual_band_outside": annual_band_outside,
        "min_officers_required": n_off,
        "gap_events": 0,
        "manual_build": True,
        "nearby_start_hops": int(nearby_start_hops or 0),
        "allow_offday_coverage": bool(allow_offday_coverage),
        "offday_coverage_assignments": 0,
        "rest_failures": int(rest_failures),
        "consecutive_work_failures": int(consec_failures),
        "min_rest_hours": float(min_rest),
        "max_consecutive_work_days": int(max_consec),
        "compute_backend": "manual",
    }

    return {
        "success": True,
        "message": ("Manual schedule evaluated" + (" · hard OK" if hard_ok else " · hard constraints not met")),
        "metrics": metrics,
        "officer_slots": officer_slots,
        "coverage_by_day": coverage_by_day,
        "shift_templates": [(s, _end_for_start(s, length)) for s in starts_used],
        "shift_starts": starts_used,
        "manual_grid": grid,
        "simulation_config": {
            "rotation_type": rotation_type,
            "num_officers": n_off,
            "shift_length_hours": length,
            "annual_hours_target": annual_hours_target,
            "shift_starts": starts_used,
            "min_per_shift": 1,
            "simulation_days": n_days,
            "coverage_247": coverage_247,
            "use_extra_windows": use_extra_windows,
            "extra_windows": list(extra_windows or []),
            "rotation_style": rotation_style,
            "rotation_variations": list(rotation_variations or []),
            "nearby_start_hops": int(nearby_start_hops or 0),
            "allow_offday_coverage": bool(allow_offday_coverage),
            "source": "manual_build",
        },
        "suggestions": [],
    }


def grid_to_text(grid: List[List[Optional[str]]], *, max_days: int = 14) -> str:
    if not grid:
        return "(empty)"
    n_days = min(len(grid[0]), max_days)
    lines = ["Day  " + " ".join(f"{d:>5}" for d in range(n_days))]
    for oi, row in enumerate(grid):
        cells = []
        for d in range(n_days):
            v = row[d]
            cells.append((v or "OFF")[:5].rjust(5))
        lines.append(f"O{oi + 1:<3}" + " ".join(cells))
    if len(grid[0]) > max_days:
        lines.append(f"… {len(grid[0]) - max_days} more day(s)")
    return "\n".join(lines)


def cycle_cell_start(
    grid: List[List[Optional[str]]],
    officer_index: int,
    day_index: int,
    pack: Sequence[str],
) -> Dict[str, Any]:
    """Cycle OFF → pack[0] → pack[1] … → OFF for interactive grid."""
    starts = [s for s in pack if s]
    if not starts:
        starts = ["06:00", "14:00", "22:00"]
    if not grid or officer_index < 0 or officer_index >= len(grid):
        return {"success": False, "message": "Bad officer"}
    if day_index < 0 or day_index >= len(grid[0]):
        return {"success": False, "message": "Bad day"}
    cur = grid[officer_index][day_index]
    if cur is None:
        nxt = starts[0]
    else:
        try:
            i = starts.index(str(cur))
            nxt = starts[i + 1] if i + 1 < len(starts) else None
        except ValueError:
            nxt = starts[0]
    grid[officer_index][day_index] = nxt
    return {"success": True, "grid": grid, "value": nxt or "OFF"}


def seed_grid_with_nearby_hops(
    *,
    num_officers: int,
    num_days: int,
    shift_starts: Sequence[str],
    rotation_type: str = "",
    rotation_style: str = "rotating",
    rotation_variations: Optional[Sequence[str]] = None,
    nearby_hops: int = 1,
    respect_off_days: bool = True,
) -> Dict[str, Any]:
    """Seed ON days then rebalance starts with home+nearby (matches Find Best model)."""
    from simulator import assign_pack_starts_for_coverage

    base = seed_grid_from_rotation(
        num_officers=num_officers,
        num_days=num_days,
        shift_starts=shift_starts,
        rotation_type=rotation_type,
        rotation_style=rotation_style,
        rotation_variations=rotation_variations,
        respect_off_days=respect_off_days,
    )
    if not base.get("success"):
        return base
    grid = base["grid"]
    starts = list(base.get("shift_starts") or shift_starts)
    hops = max(0, int(nearby_hops or 0))
    for day in range(num_days):
        working_idx = [oi for oi in range(num_officers) if grid[oi][day]]
        if not working_idx:
            continue
        homes = [grid[oi][day] for oi in working_idx]
        bands = assign_pack_starts_for_coverage(
            len(working_idx),
            starts,
            8.0,
            home_starts=homes,
            fri_sat_window=(day % 7) in (4, 5),
            nearby_hops=hops,
        )
        for j, oi in enumerate(working_idx):
            if j < len(bands):
                grid[oi][day] = bands[j][0]
    base["grid"] = grid
    base["message"] = (base.get("message") or "Seeded") + f" · nearby hops={hops}"
    return base
