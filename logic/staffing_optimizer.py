"""
Staffing schedule optimizer — exhaustive search over the constraint-defined space.

NOT bump / leave-coverage logic (see coverage_optimizer / bump_optimizer).

Search size is determined only by free vs locked dimensions and multi-block
phase/pattern layouts — there is no max_total_evals cap that abandons remaining
candidates. Call estimate_search_space() before a run to warn operators when the
space (and wall time) is large.

Near-miss plans are retained when no layout meets every hard constraint, ranked
by user constraint_weights / constraint_priority.
"""

from __future__ import annotations

import itertools
import os
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple, TypedDict

import config
from logic.scheduling_contracts import (
    ScheduleCandidate,
    ScheduleStatus,
    SimulationReport,
    VerificationReport,
    compute_input_hash,
    compute_policy_hash,
    to_canonical_status,
)

InputRole = Literal["hard_constraint", "soft_preference", "open_variable"]


class SimulatorInputItem(TypedDict, total=False):
    key: str
    label: str
    role: InputRole
    value: Any
    domain: Any


class SimulatorInputRoles(TypedDict):
    hard_constraints: List[SimulatorInputItem]
    soft_preferences: List[SimulatorInputItem]
    open_variables: List[SimulatorInputItem]


def normalize_simulator_input_roles(payload: Optional[Dict[str, Any]]) -> SimulatorInputRoles:
    """Return the canonical, serializable Required/Preferred/Solver-decides payload."""
    result: SimulatorInputRoles = {
        "hard_constraints": [],
        "soft_preferences": [],
        "open_variables": [],
    }
    expected = {
        "hard_constraints": "hard_constraint",
        "soft_preferences": "soft_preference",
        "open_variables": "open_variable",
    }
    for group, role in expected.items():
        for raw in (payload or {}).get(group) or []:
            if not isinstance(raw, dict) or not raw.get("key"):
                continue
            item: SimulatorInputItem = {
                "key": str(raw["key"]),
                "label": str(raw.get("label") or raw["key"]),
                "role": role,
            }
            if "value" in raw:
                item["value"] = raw["value"]
            if "domain" in raw:
                item["domain"] = raw["domain"]
            result[group].append(item)
    return result


def simulator_understood_lines(payload: Optional[Dict[str, Any]]) -> List[str]:
    roles = normalize_simulator_input_roles(payload)

    def _labels(group: str) -> str:
        labels = [str(item.get("label") or item.get("key")) for item in roles[group]]
        return ", ".join(labels) if labels else "None"

    return [
        f"Required: {_labels('hard_constraints')}",
        f"Preferred: {_labels('soft_preferences')}",
        f"Simulator decides: {_labels('open_variables')}",
    ]


def _derive_search_status(
    *,
    cancelled: bool,
    has_verified_result: bool,
    search_exhaustive: bool,
) -> str:
    """Map search evidence to the canonical product status."""
    if cancelled:
        return "CANCELLED"
    if has_verified_result:
        return "FEASIBLE"
    if search_exhaustive:
        return "INFEASIBLE"
    return "UNKNOWN"


# C1 — opt-in process pool (Windows spawn-safe top-level worker)
_OPT_PROCESS_WORKERS = max(0, int(os.environ.get("SCHEDULER_OPT_PROCESS_WORKERS", "0") or 0))
# Default: half of cores (2–4) for full-sim batches — cancel still checked between batches
_OPT_THREAD_DEFAULT = min(4, max(2, (os.cpu_count() or 4) // 2))
_OPT_THREAD_WORKERS = max(
    1,
    int(os.environ.get("SCHEDULER_OPT_THREAD_WORKERS", str(_OPT_THREAD_DEFAULT)) or _OPT_THREAD_DEFAULT),
)


def _full_sim_worker(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Top-level picklable worker for process-pool full sims."""
    from simulator import SimulatorConfig, simulate_schedule

    ph = payload.get("ph")
    pm = payload.get("pm")
    cfg = SimulatorConfig(**payload["cfg"])
    sim = simulate_schedule(cfg)
    return {
        "ph": ph,
        "pm": pm,
        "success": bool(sim.success),
        "metrics": dict(sim.metrics or {}),
        "suggestions": [
            {
                "severity": s.severity,
                "title": s.title,
                "message": s.message,
                "recommendation": s.recommendation,
            }
            for s in (sim.suggestions or [])
        ],
        "officer_slots": [s.__dict__ if hasattr(s, "__dict__") else s for s in (sim.officer_slots or [])],
    }


# Full start-pack catalog size when starts are free (no artificial depth cap)
FREE_STARTS_MAX_PACKS = 64

MULTI_BLOCK_CATALOG: List[List[str]] = [
    ["6-2,5-3", "6-3,5-2"],
    ["5-2,6-3", "5-3,6-2"],
    ["5-2", "5-3"],
    ["4-3,3-4"],
    ["6-2,5-3"],
    ["5-3,6-2"],
]

# Default soft priority when ranking near-misses (higher = more important to satisfy)
DEFAULT_CONSTRAINT_WEIGHTS: Dict[str, float] = {
    "coverage_247": 100.0,
    "windows": 90.0,
    "gaps": 80.0,
    "flsa": 70.0,
    "annual": 40.0,  # year math is approximate — softest by default
    "annual_spread": 40.0,  # peer-hours fairness; independent of the annual-target weight
    "start_changes": 35.0,
    "duplicate_starts": 30.0,
    "overcoverage": 25.0,
    "headcount": 10.0,  # prefer fewer officers when equal quality
}

CONSTRAINT_LABELS: Dict[str, str] = {
    "coverage_247": "24/7 Minimum Coverage",
    "windows": "Extra Staffing Windows",
    "gaps": "Minimum Officers Per Shift Band",
    "flsa": "Avoid FLSA Overtime",
    "annual": "Annual Hours Target (Year-Average Fairness)",
    "start_changes": "Fewer Disruptive Start Changes",
    "duplicate_starts": "Fewer Same-Time Starts",
    "overcoverage": "Less Unnecessary Overcoverage",
    "headcount": "Prefer Fewer Officers",
}


def _format_hhmm(hour: int, minute: int = 0) -> str:
    """Clock label; minute must be 0 or 30 (half-hour grid only)."""
    m = 0 if int(minute) < 15 else (30 if int(minute) < 45 else 0)
    h = int(hour) % 24
    if int(minute) >= 45:
        h = (h + 1) % 24
    return f"{h:02d}:{m:02d}"


def _half_hour_starts() -> List[str]:
    """All legal start times on a 30-minute grid (00:00, 00:30, …, 23:30)."""
    out: List[str] = []
    for h in range(24):
        out.append(_format_hhmm(h, 0))
        out.append(_format_hhmm(h, 30))
    return out


def _snap_to_half_hour(label: str) -> str:
    """Snap a HH:MM string to the nearest half-hour slot."""
    try:
        parts = (label or "00:00").strip().split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
    except (TypeError, ValueError):
        return "00:00"
    total = (h * 60 + m + 15) // 30 * 30
    total %= 24 * 60
    return _format_hhmm(total // 60, total % 60)


def generate_start_packs(shift_length_hours: float, *, max_packs: int = 1000, num_officers: int = 6) -> List[List[str]]:
    import itertools

    packs: List[List[str]] = []
    seen = set()

    def _add(starts: Sequence[str]) -> None:
        cleaned = [_snap_to_half_hour(s) for s in starts if s]
        if len(cleaned) < 2:
            return
        uniq = []
        for s in cleaned:
            if s not in uniq:
                uniq.append(s)
        if len(uniq) < 2:
            return
        key = tuple(sorted(uniq))
        if key in seen:
            return
        seen.add(key)
        packs.append(list(uniq))

    # Base hours to select from
    core_starts = [
        "05:00",
        "06:00",
        "07:00",
        "08:00",  # Morning
        "13:00",
        "14:00",
        "15:00",
        "16:00",
        "17:00",  # Afternoon
        "18:00",
        "19:00",
        "20:00",
        "21:00",
        "22:00",
        "23:00",  # Night
        "00:00",
        "02:00",  # Midnight
    ]

    # Equal-spaced bands generated FIRST so they are never crowded out by the
    # combinatorial section hitting max_packs.  These are the most analytically
    # sound packs for coverage analysis.
    anchors = ["05:00", "06:00", "07:00", "18:00", "19:00"]
    for spacing_h in [6, 8, 12]:
        spacing_min = spacing_h * 60
        for a in anchors:
            try:
                ah, am = map(int, a.split(":"))
                base = ah * 60 + am
                combo = [
                    _format_hhmm((base + i * spacing_min) // 60, (base + i * spacing_min) % 60)
                    for i in range(24 // spacing_h)
                ]
                _add(combo)
            except Exception:
                pass

    # For larger departments allow more distinct bands (up to 6 for N>=8).
    max_combos = min(max(2, num_officers), 6)

    # Add 2-band through max_combos-band combinations from core_starts
    for k in range(2, max_combos + 1):
        for combo in itertools.combinations(core_starts, k):
            _add(combo)
            if len(packs) >= max_packs:
                break
        if len(packs) >= max_packs:
            break

    return packs[:max_packs]


def generate_length_options(*, lo: float = 8.0, hi: float = 12.5) -> List[float]:
    out: List[float] = []
    x = lo
    while x <= hi + 1e-9:
        out.append(round(x, 1))
        x += 0.5
    return out


def generate_officer_counts(
    *,
    explicit: Optional[List[int]] = None,
    free: bool = False,
    base: int = 8,
    lo: int = 4,
    hi: int = 20,
) -> List[int]:
    if explicit is not None:
        return sorted({max(1, int(n)) for n in explicit})
    if not free:
        return [max(1, int(base))]
    return list(range(max(1, lo), max(lo, hi) + 1))


def generate_phase_layouts(
    n_slots: int,
    cycle_length: int,
    *,
    mode: str = "full",
) -> List[List[int]]:
    """
    Phase model for multi-block stagger:
    - even spacing for every offset (priority + full)
    - arithmetic progressions step×offset (full; thinned when large)
    mode='priority' — even spacing + anchors only (fast first pass)
    mode='full' — denser finite model (no random sample)
    """
    if n_slots < 1 or cycle_length < 1:
        return [[0] * max(n_slots, 0)]
    layouts: List[List[int]] = []
    seen = set()
    priority_only = (mode or "full").strip().lower() == "priority"

    def _add(phases: List[int]) -> None:
        key = tuple(int(p) % cycle_length for p in phases)
        if key in seen:
            return
        seen.add(key)
        layouts.append(list(key))

    stride = max(1, cycle_length // max(n_slots, 1))
    for offset in range(cycle_length):
        _add([(i * stride + offset) % cycle_length for i in range(n_slots)])

    _add([0] * n_slots)
    _add([i % cycle_length for i in range(n_slots)])
    # Half-cycle stagger (common LE multi-block)
    half = max(1, cycle_length // 2)
    _add([(i * half) % cycle_length for i in range(n_slots)])

    if priority_only:
        return layouts

    # Arithmetic progressions — thin offsets when space is large
    max_step = max(2, min(cycle_length // 2, n_slots + 2))
    offset_stride = 1 if (cycle_length <= 14 and n_slots <= 7) else 2
    for step in range(1, max_step + 1):
        for offset in range(0, cycle_length, offset_stride):
            _add([((i * step) + offset) % cycle_length for i in range(n_slots)])

    return layouts


def generate_pattern_maps(n_slots: int, n_patterns: int) -> List[List[int]]:
    """Complete structured pattern↔slot maps (full 2^n when n_slots ≤ 10 and 2 patterns)."""
    if n_slots < 1 or n_patterns < 1:
        return [[0] * max(n_slots, 0)]
    if n_patterns == 1:
        return [[0] * n_slots]
    maps: List[List[int]] = []
    seen = set()

    def _add(m: List[int]) -> None:
        key = tuple(int(x) % n_patterns for x in m)
        if key in seen:
            return
        seen.add(key)
        maps.append(list(key))

    _add([i % n_patterns for i in range(n_slots)])
    _add([(n_patterns - 1 - (i % n_patterns)) for i in range(n_slots)])
    mid = n_slots // 2
    _add([0] * mid + [1 % n_patterns] * (n_slots - mid))
    _add([1 % n_patterns] * mid + [0] * (n_slots - mid))
    _add([(i // 2) % n_patterns for i in range(n_slots)])
    _add([0] * n_slots)
    if n_patterns > 1:
        _add([1 % n_patterns] * n_slots)

    if n_patterns == 2 and n_slots <= 6:
        # Full assignment space 2^n (complete for two multi-block variations)
        for k in range(0, n_slots + 1):
            for ones in itertools.combinations(range(n_slots), k):
                m = [0] * n_slots
                for i in ones:
                    m[i] = 1
                _add(m)
    elif n_patterns == 2:
        # Larger N: every headcount split + even/odd placements (finite model, no sample cap)
        for k in range(0, n_slots + 1):
            if k == 0:
                _add([0] * n_slots)
                continue
            step = n_slots / k
            for shift in range(max(1, n_slots // max(k, 1))):
                m = [0] * n_slots
                for j in range(k):
                    m[int(j * step + shift) % n_slots] = 1
                _add(m)
    return maps


def _day_body_counts(
    patterns,
    phases: List[int],
    pat_map: List[int],
    *,
    n_slots: int,
    simulation_days: int,
    sim_start: date,
) -> Tuple[List[int], List[int]]:
    """Fast body counts — precompute shifted duty rings (Python hot path; Rust full-sim separate)."""
    cycle = patterns[0].cycle_length
    n_days = max(simulation_days, cycle)
    # Precompute each slot's duty mask for day_offset 0..n_days-1
    slot_work: List[List[bool]] = []
    for i in range(n_slots):
        p = patterns[pat_map[i] % len(patterns)]
        vec = p.duty_vector()
        n = len(vec)
        phase = int(phases[i]) % max(cycle, 1)
        if not n:
            slot_work.append([False] * n_days)
            continue
        # rotated view: day d uses vec[(d+phase)%n]
        slot_work.append([bool(vec[(d + phase) % n]) for d in range(n_days)])
    day_counts: List[int] = [0] * n_days
    fri_sat: List[int] = []
    base_wd = sim_start.weekday()
    for d in range(n_days):
        c = 0
        for i in range(n_slots):
            if slot_work[i][d]:
                c += 1
        day_counts[d] = c
        if (base_wd + d) % 7 in (4, 5):
            fri_sat.append(c)
    return day_counts, fri_sat


_PRESET_BODY_CACHE: Dict[Tuple[str, int, int, int], Tuple[List[int], List[int]]] = {}


def _day_body_counts_preset(
    rot_key: str,
    n_slots: int,
    simulation_days: int,
    sim_start: date,
) -> Tuple[List[int], List[int]]:
    """Body counts for a fixed preset rotation (2-squad A/B pattern) — the cheap-reject
    equivalent of _day_body_counts for the (very common) no-custom-variations path."""
    from config import ROTATION_PRESETS
    from simulator import _squad_working

    cache_key = (rot_key, n_slots, simulation_days, sim_start.toordinal())
    cached = _PRESET_BODY_CACHE.get(cache_key)
    if cached is not None:
        return cached
    preset = ROTATION_PRESETS.get(rot_key) or {}
    squads = ["A", "B"] if preset.get("squads", 2) >= 2 else ["A"]
    slot_squads = [squads[i % len(squads)] for i in range(n_slots)]
    cycle = int(preset.get("cycle_length") or 14)
    day_counts: List[int] = [0] * simulation_days
    fri_sat: List[int] = []
    base_wd = sim_start.weekday()
    for d in range(simulation_days):
        cycle_day = (d % cycle) + 1
        c = sum(1 for sq in slot_squads if _squad_working(rot_key, sq, cycle_day, preset))
        day_counts[d] = c
        if (base_wd + d) % 7 in (4, 5):
            fri_sat.append(c)
    result = (day_counts, fri_sat)
    if len(_PRESET_BODY_CACHE) > 500:
        _PRESET_BODY_CACHE.clear()
    _PRESET_BODY_CACHE[cache_key] = result
    return result


def _preset_avg_annual_hours(rot_key: str, n_slots: int, shift_length: float) -> float:
    """Mean projected annual hours across a preset's squad slots — phase-independent,
    so (unlike custom multi-block patterns) it does not depend on the candidate's
    pat_map and can be computed once per (rotation, N, length)."""
    from config import ROTATION_PRESETS
    from simulator import _preset_annual_hours

    preset = ROTATION_PRESETS.get(rot_key) or {}
    squads = ["A", "B"] if preset.get("squads", 2) >= 2 else ["A"]
    hours = [_preset_annual_hours(rot_key, squads[i % len(squads)], preset, shift_length) for i in range(n_slots)]
    return sum(hours) / max(len(hours), 1)


def _preset_patterns_for_cpsat(rot_key: str):
    """Convert a preset duty cycle into an equivalent phase-search pattern.

    Presets normally assign officers to fixed A/B squads.  When rotation is an
    open search dimension, CP-SAT must be allowed to choose each officer's phase
    just as it does for custom multi-block patterns.  Previously presets yielded
    no parsed patterns, so every open preset fell back to the slow start-pack
    enumeration and could consume the whole UI time budget before reaching a
    known feasible length.
    """
    from config import ROTATION_PRESETS
    from logic.rotation_patterns import OnOffBlock, RotationPattern

    preset = ROTATION_PRESETS.get(rot_key) or {}
    cycle = int(preset.get("cycle_length") or 0)
    if cycle <= 0:
        return []

    raw = (preset.get("squad_patterns") or {}).get("A")
    if raw is None:
        a_days = {int(d) for d in (preset.get("squad_a_days") or [])}
        raw = [1 if day in a_days else 0 for day in range(1, cycle + 1)]
    vec = [bool(x) for x in list(raw)[:cycle]]
    if len(vec) != cycle or not any(vec) or all(vec):
        return []

    # Rotate to a false->true boundary so alternating work/off runs can be
    # represented exactly as OnOffBlock objects.  CP-SAT searches every phase,
    # so this normalization does not remove any preset assignment.
    boundary = next((i for i in range(cycle) if vec[i] and not vec[i - 1]), None)
    if boundary is None:
        return []
    ordered = vec[boundary:] + vec[:boundary]
    blocks = []
    i = 0
    while i < cycle:
        on = 0
        while i < cycle and ordered[i]:
            on += 1
            i += 1
        off = 0
        while i < cycle and not ordered[i]:
            off += 1
            i += 1
        if on <= 0:
            return []
        blocks.append(OnOffBlock(on, off))
    return [RotationPattern(style="rotating", blocks=blocks, label=rot_key)]


def _shift_end_hhmm(start: str, length_hours: float) -> str:
    sm = _hhmm_to_min(start)
    em = (sm + int(round(float(length_hours) * 60))) % (24 * 60)
    return f"{em // 60:02d}:{em % 60:02d}"


def _cheap_window_minute_fail(
    patterns,
    phases: List[int],
    pat_map: List[int],
    *,
    n_slots: int,
    shift_starts: Sequence[str],
    shift_length: float,
    simulation_days: int,
    sim_start: date,
    windows: List[Dict],
    nearby_hops: int = 1,
    allow_offday_coverage: bool = False,
) -> bool:
    """
    C3 minute-bin: home+nearby pack assign on rotation ON days only (unless
    allow_offday_coverage). Fail if any window min occupancy short.
    """
    if not windows or not shift_starts or not patterns:
        return False
    from logic.coverage_timeline import (
        CoverageWindow,
        check_coverage_window,
    )

    cycle = patterns[0].cycle_length
    n_days = max(simulation_days, cycle)
    starts = list(shift_starts)
    length = float(shift_length)
    win_objs: List[CoverageWindow] = []
    for w in windows:
        if not isinstance(w, dict) or not w.get("enabled", True):
            continue
        try:
            mn = int(w.get("min_officers") or 0)
        except (TypeError, ValueError):
            mn = 0
        if mn <= 0:
            continue
        win_objs.append(
            CoverageWindow(
                min_officers=mn,
                start_time=str(w.get("start_time") or "00:00"),
                end_time=str(w.get("end_time") or "23:59"),
                specific_date=None,
                weekday=w.get("weekday"),
                label=str(w.get("label") or "Window"),
            )
        )
    if not win_objs:
        return False

    slot_vecs = []
    slot_phase = []
    for i in range(n_slots):
        p = patterns[pat_map[i] % len(patterns)]
        slot_vecs.append(p.duty_vector())
        slot_phase.append(int(phases[i]) % max(cycle, 1))

    # Home+nearby on ON days only (matches simulator default).
    from simulator import assign_pack_starts_for_coverage

    hops = max(0, int(nearby_hops if nearby_hops is not None else 1))
    need_any_day = any(w.weekday is None and w.specific_date is None for w in win_objs)
    weekdays = {w.weekday for w in win_objs if w.weekday is not None}
    home_for_slot = [starts[i % len(starts)] for i in range(n_slots)]
    for day_offset in range(n_days):
        day = sim_start + timedelta(days=day_offset)
        wd = day.weekday()
        if not need_any_day and wd not in weekdays:
            continue
        working_idx = []
        off_idx = []
        for i in range(n_slots):
            vec = slot_vecs[i]
            n = len(vec)
            if n and vec[(day_offset + slot_phase[i]) % n]:
                working_idx.append(i)
            else:
                off_idx.append(i)
        fri_sat = wd in (4, 5)
        homes = [home_for_slot[i] for i in working_idx]
        bands = assign_pack_starts_for_coverage(
            len(working_idx),
            starts,
            length,
            home_starts=homes,
            min_per_shift=1,
            fri_sat_window=fri_sat,
            nearby_hops=hops,
        )
        asg = [(day, st, en) for st, en in bands]
        # Off-day call-in only when user opted in
        if allow_offday_coverage and fri_sat:
            win_need = max(
                (int(w.min_officers or 0) for w in win_objs if w.matches_date(day)),
                default=0,
            )
            if win_need > 0 and len(working_idx) < win_need:
                short = win_need - len(working_idx)
                for oi in off_idx:
                    if short <= 0:
                        break
                    home = home_for_slot[oi]
                    pick = home if home in starts else starts[0]
                    for cand in starts:
                        if abs(_hhmm_to_min(cand) - 19 * 60) <= 30:
                            hm = _hhmm_to_min(home)
                            if abs(hm - 19 * 60) <= 8 * 60 or hm >= 14 * 60:
                                pick = cand
                                break
                    asg.append((day, pick, _shift_end_hhmm(pick, length)))
                    short -= 1
        for wo in win_objs:
            if not wo.matches_date(day):
                continue
            chk = check_coverage_window(asg, wo, day, step_minutes=30)
            if not chk.get("skipped") and not chk.get("ok", True):
                return True
    return False


def _window_body_floor(windows: Optional[List[Dict]], *, use_windows: bool) -> int:
    """Min bodies that must work Fri/Sat days for extra windows to be possible."""
    if not use_windows or not windows:
        return 0
    need = 0
    for w in windows:
        if not isinstance(w, dict) or not w.get("enabled", True):
            continue
        try:
            need = max(need, int(w.get("min_officers") or 0))
        except (TypeError, ValueError):
            continue
    return max(0, need)


def _hhmm_to_min(label: str) -> int:
    try:
        parts = (label or "00:00").strip().split(":")
        return int(parts[0]) % 24 * 60 + (int(parts[1]) if len(parts) > 1 else 0)
    except (TypeError, ValueError, IndexError):
        return 0


def _shift_covers_minute(start_min: int, length_min: int, minute_of_day: int) -> bool:
    """Whether a shift starting at start_min for length_min covers minute_of_day (0..1439)."""
    if length_min <= 0:
        return False
    end = start_min + length_min
    if end <= 24 * 60:
        return start_min <= minute_of_day < end
    # Overnight
    return minute_of_day >= start_min or minute_of_day < (end % (24 * 60))


def pack_window_band_capacity(
    starts: Sequence[str],
    shift_length_hours: float,
    win_start: str,
    win_end: str,
    *,
    step_minutes: int = 30,
) -> int:
    """
    C3 — count of start *bands* that cover the thinnest sample in the window.

    Not a headcount ceiling (many officers may share one start). Use
    pack_meets_window_bands for impossible-pack pruning (needs ≥1 covering band).
    """
    if not starts:
        return 0
    length_min = max(30, int(round(float(shift_length_hours) * 60)))
    start_mins = [_hhmm_to_min(s) for s in starts]
    ws = _hhmm_to_min(win_start)
    we = _hhmm_to_min(win_end)
    samples: List[int] = []
    if we > ws:
        t = ws
        while t < we:
            samples.append(t)
            t += max(15, int(step_minutes))
    else:
        t = ws
        while t < 24 * 60:
            samples.append(t)
            t += max(15, int(step_minutes))
        t = 0
        while t < we:
            samples.append(t)
            t += max(15, int(step_minutes))
    if not samples:
        return 0
    mins: List[int] = []
    for m in samples:
        cover = sum(1 for sm in start_mins if _shift_covers_minute(sm, length_min, m))
        mins.append(cover)
    return min(mins) if mins else 0


def pack_meets_window_bands(
    starts: Sequence[str],
    shift_length_hours: float,
    windows: Optional[List[Dict]],
    *,
    num_officers: Optional[int] = None,
) -> bool:
    """
    True if start pack can *possibly* cover windows.

    Only rejects when some window sample has **zero** covering bands
    (no amount of stacking on starts can help), or need > num_officers.
    """
    if not windows:
        return True
    for w in windows:
        if not isinstance(w, dict) or not w.get("enabled", True):
            continue
        try:
            need = int(w.get("min_officers") or 0)
        except (TypeError, ValueError):
            need = 0
        if need <= 0:
            continue
        if num_officers is not None and need > int(num_officers):
            return False
        st = str(w.get("start_time") or "00:00")
        en = str(w.get("end_time") or "23:59")
        # Any covering band at the thinnest sample?
        if pack_window_band_capacity(starts, shift_length_hours, st, en) < 1:
            return False
    return True


def _cheap_reject(
    patterns,
    phases: List[int],
    pat_map: List[int],
    *,
    n_slots: int,
    shift_length: float,
    annual_target: float,
    annual_variance: float,
    annual_hard: bool,
    simulation_days: int,
    cov247: int,
    use_windows: bool,
    window_min: int = 0,
    n_bands: int = 1,
    min_ps: int,
    sim_start: date,
    shift_starts: Optional[Sequence[str]] = None,
    extra_windows: Optional[List[Dict]] = None,
    precomputed: Optional[Tuple[List[int], List[int]]] = None,
    nearby_hops: int = 1,
    allow_offday_coverage: bool = False,
    preset_avg_hours: Optional[float] = None,
) -> Optional[str]:
    """Prune layouts that cannot possibly meet hard floors (bodies / pattern annual mean)."""
    from logic.rotation_patterns import projected_annual_hours

    del n_bands  # kept for API compat; window floor uses window_min from extra_windows
    # Annual-hours mean floor: custom multi-block patterns use the candidate's own
    # phase/pattern-slot map; preset (squad A/B) rotations have a fixed, phase-
    # independent mean passed in as preset_avg_hours — previously this whole check
    # only ran when `patterns` was truthy, so preset-only candidates (the common
    # case) never got cheaply rejected on annual hours at all.
    avg: Optional[float] = None
    if patterns and annual_hard:
        # Pattern math is cycle-based year-average — phase does not change hours.
        # Reject only when *mean* projected is outside target band (not peer equality).
        hours = [projected_annual_hours(patterns[pat_map[i] % len(patterns)], shift_length) for i in range(n_slots)]
        avg = sum(hours) / max(len(hours), 1)
    elif preset_avg_hours is not None and annual_hard:
        avg = float(preset_avg_hours)
    if avg is not None:
        # B4 fix: only apply the 2% floor when variance is truly unset (<=0).
        # Never silently override a user-set tight variance (e.g. ±20h).
        if float(annual_variance or 0) > 0:
            band = float(annual_variance)
        else:
            band = abs(float(annual_target)) * 0.02
        if abs(avg - float(annual_target)) > band + 1e-6:
            return "annual"

    # Body-count floors (24/7, windows, min-per-shift) apply to ANY schedule shape —
    # preset rotations included — as long as day_counts is available (either passed
    # in precomputed, or derivable from patterns). Previously this whole block sat
    # under `if patterns:`, so preset-only candidates (no custom multi-block
    # variations) skipped every cheap check and always fell through to a full
    # simulate_schedule() call, even when the floor was trivially unreachable.
    if precomputed is not None:
        day_counts, fri_sat = precomputed
    elif patterns:
        day_counts, fri_sat = _day_body_counts(
            patterns,
            phases,
            pat_map,
            n_slots=n_slots,
            simulation_days=simulation_days,
            sim_start=sim_start,
        )
    else:
        return None

    if cov247 > 0 and day_counts and min(day_counts) < cov247:
        return "coverage_247"
    # Body floor for windows = max min_officers from windows (not n_bands heuristic).
    # When off-day coverage is OFF, body floor is hard: OFF officers do not work.
    if use_windows and fri_sat and window_min > 0:
        if min(fri_sat) < min(window_min, n_slots):
            return "window"
    if patterns:
        # C3 — pack shape: zero covering bands
        if use_windows and shift_starts and extra_windows:
            if not pack_meets_window_bands(shift_starts, shift_length, extra_windows):
                return "window"
        # C3 minute-bin occupancy with home+nearby ON-day starts (heavier; only if body OK)
        if use_windows and shift_starts and extra_windows and phases is not None and pat_map is not None:
            if _cheap_window_minute_fail(
                patterns,
                phases,
                pat_map,
                n_slots=n_slots,
                shift_starts=shift_starts,
                shift_length=shift_length,
                simulation_days=simulation_days,
                sim_start=sim_start,
                windows=list(extra_windows),
                nearby_hops=nearby_hops,
                allow_offday_coverage=allow_offday_coverage,
            ):
                return "window"
    if min_ps > 0 and day_counts and min(day_counts) < min_ps:
        return "gaps"
    return None


def _weights_from_priority(
    priority: Optional[List[str]] = None,
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    w = dict(DEFAULT_CONSTRAINT_WEIGHTS)
    if weights:
        for k, v in weights.items():
            if k in w:
                try:
                    w[k] = float(v)
                except (TypeError, ValueError):
                    pass
    if priority:
        # Earlier in list = higher priority → assign descending weights
        base = 100.0
        for i, key in enumerate(priority):
            if key in w and key != "headcount":
                w[key] = base - i * 12.0
    return w


def _violation_vector(m: Dict, *, annual: float, annual_variance: float) -> Dict[str, float]:
    """Non-negative violation magnitudes for near-miss scoring.

    B6 fix: split annual_band_outside and annual distance into separate terms
    with calibrated coefficients so a plan with 1 officer slightly out of band
    does not outscore a plan with genuine coverage gaps.
    """
    gaps = float(m.get("gap_events") or m.get("zero_staff_slots") or m.get("coverage_gap_count") or 0)
    # annual_band_outside: number of officers outside band (x15 per officer)
    # annual distance: how far mean is from target (normalized, x12 max per unit)
    annual_outside_count = float(m.get("annual_band_outside") or 0)
    annual_mean_dist = (
        abs(float(m.get("avg_annual_hours") or annual) - annual) * 12.0 / max(float(annual_variance) or 40.0, 1.0)
    )
    return {
        "coverage_247": float(m.get("coverage_247_failures") or 0),
        "windows": float(m.get("extra_window_failures") or 0),
        "gaps": gaps,
        "flsa": float(m.get("flsa_violations") or 0),
        "annual": annual_outside_count * 15.0 + annual_mean_dist,
        "annual_spread": float(m.get("annual_hours_spread") or 0),
    }


def _score_metrics(
    m: Dict,
    *,
    annual: float,
    annual_variance: float = 40.0,
    n_off: int,
    hard_ok: bool,
    weights: Dict[str, float],
    pattern_slot_map: Optional[List[int]] = None,
    multi_block: bool = False,
) -> float:
    var = float(annual_variance if annual_variance is not None else (m.get("annual_hours_variance") or 40))
    v = _violation_vector(m, annual=annual, annual_variance=var)
    penalty = 0.0
    for key in ("coverage_247", "windows", "gaps", "flsa", "annual"):
        penalty += v.get(key, 0) * float(weights.get(key, 1.0))
    # Peer spread (officers not identical — penalize large unfairness only)
    penalty += float(v.get("annual_spread") or 0) * float(weights.get("annual_spread", 40.0)) * 0.05
    # Clamp n_off to >=1 so a degenerate 0-officer config never escapes the headcount penalty
    penalty += max(1, n_off) * float(weights.get("headcount", 10.0)) * 0.05
    # Multi-block: prefer mixed pattern maps over all-officers-same-pattern
    if multi_block and pattern_slot_map and len(pattern_slot_map) > 1:
        uniq = len({int(x) for x in pattern_slot_map})
        if uniq < 2:
            penalty += 25.0
        else:
            # Mild bonus for balanced split (closer to 50/50)
            zeros = sum(1 for x in pattern_slot_map if int(x) % 2 == 0)
            bal = abs(zeros / len(pattern_slot_map) - 0.5)
            penalty += bal * 15.0
    # Correct metric key names from simulator:
    # "rest_failures" and "consecutive_work_failures" (not the old mismatched names)
    rest_hits = float(m.get("rest_failures") or m.get("rest_gap_violations") or m.get("min_rest_failures") or 0)
    consec = float(
        m.get("consecutive_work_failures")
        or m.get("consecutive_work_violations")
        or m.get("max_consecutive_failures")
        or 0
    )
    penalty += rest_hits * 8.0 + consec * 6.0
    return 100_000 - penalty - (0 if hard_ok else 5_000)


def _constraint_fail(
    m: Dict,
    *,
    require_hard_ok: bool,
    avoid_flsa_overtime: bool,
    cov247: int,
    use_extra_windows: bool,
    windows: list,
    annual_hours_hard: bool,
    min_ps: int,
    min_rest_hours: float = 0.0,
    max_consecutive_work_days: int = 0,
) -> bool:
    """Return True if this sim result fails any active hard constraint.

    B9 fix: always respect hard_constraints_ok from the simulator — even when
    min_ps=0, a plan with genuine coverage gaps has hard_ok=False already set
    by the simulator and should be rejected here.

    B1 fix: rest_failures and consecutive_work_failures now checked when the
    corresponding user constraints are active.
    """
    if not require_hard_ok:
        return False
    # B9: always gate on the simulator's own hard_constraints_ok flag
    if not bool(m.get("hard_constraints_ok", True)):
        return True
    if avoid_flsa_overtime and int(m.get("flsa_violations") or 0):
        return True
    if cov247 > 0 and int(m.get("coverage_247_failures") or 0):
        return True
    if use_extra_windows and windows and int(m.get("extra_window_failures") or 0):
        return True
    if annual_hours_hard:
        if int(m.get("annual_mean_outside") or 0) > 0:
            return True
        if int(m.get("annual_unfair") or 0) > 0:
            return True
    # Only check min_ps gaps independently when min_ps > 0 (redundant with hard_ok above
    # but kept for clarity when hard_ok key is absent from older sim results)
    gaps = m.get("gap_events")
    if gaps is None:
        gaps = m.get("zero_staff_slots") or m.get("coverage_gap_count") or 0
    if int(min_ps) > 0 and int(gaps or 0) > 0:
        return True
    # B1: rest and consecutive-day hard gates
    if min_rest_hours > 0 and int(m.get("rest_failures") or 0) > 0:
        return True
    if max_consecutive_work_days > 0 and int(m.get("consecutive_work_failures") or 0) > 0:
        return True
    return False


def _resolve_axes(
    *,
    rotation_types,
    officer_counts,
    min_per_shift_options,
    shift_length_hours,
    shift_length_options,
    shift_starts,
    shift_starts_options,
    free_officer_counts,
    free_starts,
    free_lengths,
    free_variations,
    rotation_variations,
    rotation_style,
    rotation_variation_sets=None,
):
    from logic.rotation_config import get_rotation_config
    from logic.staffing_config import get_staffing_config

    staffing = get_staffing_config()
    rot = get_rotation_config()
    if rotation_types is None:
        from config import SIMULATOR_ROTATION_TYPES

        rotation_types = list(SIMULATOR_ROTATION_TYPES)
        active = rot.get("preset_name") or rot.get("active_preset")
        if active and active not in rotation_types:
            rotation_types.insert(0, active)

    base_officers = int(staffing.get("active_officer_count") or staffing.get("target_officer_count") or 16)
    if officer_counts is None:
        if free_officer_counts:
            officer_counts = generate_officer_counts(free=True, base=base_officers, lo=4, hi=20)
        else:
            officer_counts = sorted(
                {
                    max(4, base_officers - 4),
                    base_officers,
                    base_officers + 2,
                    base_officers + 4,
                    staffing.get("target_officer_count") or base_officers,
                }
            )
    else:
        officer_counts = sorted({max(1, int(n)) for n in officer_counts})

    if min_per_shift_options is None:
        # Unlocked means no per-named-band floor. Continuous coverage and
        # extra windows are enforced independently; inventing a 1/2 officer
        # band minimum here rejects valid overlapping-shift solutions the
        # user explicitly allowed.
        min_per_shift_options = [0]
    else:
        min_per_shift_options = [max(0, int(x)) for x in min_per_shift_options]

    if shift_length_options:
        length_opts = [float(x) for x in shift_length_options]
    elif free_lengths:
        length_opts = generate_length_options()
    elif shift_length_hours is not None:
        length_opts = [float(shift_length_hours)]
    else:
        length_opts = [float(staffing["shift_length_hours"])]

    locked_starts_opts: Optional[List[List[str]]] = None
    if shift_starts_options:
        locked_starts_opts = [list(s) for s in shift_starts_options if s]
    elif shift_starts:
        locked_starts_opts = [list(shift_starts)]
    elif not free_starts:
        default_starts = [b["start"] for b in staffing.get("shift_times") or []]
        if not default_starts:
            default_starts = [config.SHIFT_TIMES[k][0] for k in sorted(config.SHIFT_TIMES)]
        locked_starts_opts = [default_starts]

    base_variations = [v for v in (rotation_variations or []) if (v or "").strip()]
    # Multiple manually-entered alternative sets — each is tried as its own
    # independent structural candidate (same as a locked single set, just more
    # than one). Falls back to the single base_variations set, then the
    # free-variations catalog, then plain (no custom variation).
    manual_sets = [[v for v in (s or []) if (v or "").strip()] for s in (rotation_variation_sets or [])]
    manual_sets = [s for s in manual_sets if s]
    style = (rotation_style or "").strip().lower()
    if manual_sets:
        variation_sets: List[List[str]] = manual_sets
        if not base_variations:
            base_variations = manual_sets[0]
    elif base_variations:
        variation_sets = [list(base_variations)]
    elif free_variations:
        # Include the "no custom variation" option so preset rotations are still
        # tried in their plain form — omitting it meant a locked preset rotation
        # combined with a free style/variations search was NEVER evaluated on its
        # own, only ever wrapped in a (mismatched) multi-block catalog pattern.
        variation_sets = [[]] + [list(v) for v in MULTI_BLOCK_CATALOG]
    else:
        variation_sets = [[]]
    any_comma = any("," in v for s in variation_sets for v in s)
    if (base_variations or manual_sets) and style not in ("fixed", "rotating"):
        style = "rotating" if any_comma else "fixed"
    elif free_variations and style not in ("fixed", "rotating"):
        style = "rotating"

    free_dims = []
    if free_officer_counts or (officer_counts is not None and len(officer_counts) > 1):
        free_dims.append("officer_count")
    if free_lengths or len(length_opts) > 1:
        free_dims.append("shift_length")
    if free_starts or (locked_starts_opts is None):
        free_dims.append("shift_starts")
    if len(min_per_shift_options) > 1:
        free_dims.append("min_per_shift")
    if len(rotation_types) > 1:
        free_dims.append("rotation")
    if free_variations or len(variation_sets) > 1:
        free_dims.append("rotation_variations")
    if base_variations or free_variations:
        free_dims.append("phase_and_pattern_assignment")

    return {
        "rotation_types": list(rotation_types),
        "officer_counts": list(officer_counts),
        "min_per_shift_options": list(min_per_shift_options),
        "length_opts": length_opts,
        "locked_starts_opts": locked_starts_opts,
        "free_starts": free_starts or locked_starts_opts is None,
        "variation_sets": variation_sets,
        "style": style,
        "base_variations": base_variations,
        "free_dims": free_dims,
        "staffing": staffing,
    }


def estimate_search_space(
    *,
    rotation_types: Optional[List[str]] = None,
    officer_counts: Optional[List[int]] = None,
    min_per_shift_options: Optional[List[int]] = None,
    shift_length_hours: Optional[float] = None,
    shift_starts: Optional[List[str]] = None,
    shift_starts_options: Optional[List[List[str]]] = None,
    shift_length_options: Optional[List[float]] = None,
    rotation_style: str = "",
    rotation_variations: Optional[List[str]] = None,
    rotation_variation_sets: Optional[List[List[str]]] = None,
    free_officer_counts: bool = False,
    free_starts: bool = False,
    free_lengths: bool = False,
    free_variations: bool = False,
    stagger_phases: bool = True,
    use_extra_windows: bool = False,
    extra_windows: Optional[List[Dict]] = None,
    **_ignored,
) -> Dict:
    """
    Count layouts in the constraint-defined search space and estimate wall time.
    Used by the UI to warn before Find Best.

    When the CP-SAT fast path applies (custom multi-block patterns, weekday-only
    windows, OR-Tools installed), the raw enumeration count is NOT the expected
    cost: the real search tries a cheap heuristic + one solver probe per
    (officer count x shift length) combo and only falls back to enumeration for
    combos the solver can't decide. The estimate must reflect that plan, or it
    scares users away from searches that finish in seconds (proven 2026-07-22:
    dialog said "31-78 hours" for a scenario CP-SAT solved in 21s).
    """
    from config import ROTATION_PRESETS
    from logic.rotation_patterns import build_pattern

    axes = _resolve_axes(
        rotation_types=rotation_types,
        officer_counts=officer_counts,
        min_per_shift_options=min_per_shift_options,
        shift_length_hours=shift_length_hours,
        shift_length_options=shift_length_options,
        shift_starts=shift_starts,
        shift_starts_options=shift_starts_options,
        free_officer_counts=free_officer_counts,
        free_starts=free_starts,
        free_lengths=free_lengths,
        free_variations=free_variations,
        rotation_variations=rotation_variations,
        rotation_variation_sets=rotation_variation_sets,
        rotation_style=rotation_style,
    )

    # Multiplicative estimate (avoid nested full enumeration when free dims explode)
    total = 0
    outer = 0
    sample_cycle = 14
    for variations in axes["variation_sets"]:
        if not variations:
            continue
        try:
            p0 = build_pattern(
                variations[0],
                style=axes["style"] if axes["style"] in ("fixed", "rotating") else None,
            )
            sample_cycle = max(sample_cycle, p0.cycle_length)
        except ValueError:
            pass

    # Cache phase/map counts by (n_off, cycle, n_pat)
    phase_map_cache: Dict[Tuple[int, int, int], int] = {}

    def _inner_count(n_off: int, cycle: int, n_pat: int, has_var: bool) -> int:
        if not has_var or not stagger_phases:
            return 1
        key = (n_off, cycle, n_pat)
        if key not in phase_map_cache:
            # Match real search: priority phases first (full expand only when needed)
            phase_map_cache[key] = len(generate_phase_layouts(n_off, cycle, mode="priority")) * len(
                generate_pattern_maps(n_off, n_pat)
            )
        return phase_map_cache[key]

    # Cache generate_start_packs length by shift length to avoid re-running the
    # combinatorial generator for every (n_off, length) pair in the estimate loop.
    _pack_len_cache: Dict[float, int] = {}

    def _pack_count(L: float) -> int:
        if L not in _pack_len_cache:
            _pack_len_cache[L] = len(generate_start_packs(float(L)))
        return _pack_len_cache[L]

    n_rot_valid = 0
    for rotation in axes["rotation_types"]:
        for variations in axes["variation_sets"]:
            if rotation not in ROTATION_PRESETS and not variations:
                continue
            n_rot_valid += 1
            cycle = sample_cycle
            n_pat = max(1, len(variations) if variations else 1)
            if variations:
                try:
                    cycle = build_pattern(
                        variations[0],
                        style=axes["style"] if axes["style"] in ("fixed", "rotating") else None,
                    ).cycle_length
                    n_pat = len(variations)
                except ValueError:
                    continue
            for n_off in axes["officer_counts"]:
                inner = _inner_count(int(n_off), cycle, n_pat, bool(variations))
                for length in axes["length_opts"]:
                    if axes["locked_starts_opts"] is not None:
                        n_starts = len(axes["locked_starts_opts"])
                    else:
                        n_starts = _pack_count(float(length))
                    for _min_ps in axes["min_per_shift_options"]:
                        outer += n_starts
                        total += n_starts * inner

    # ~3–8 ms cheap check, ~150–250 ms full sim; assume ~30% pass cheap
    est_cheap_sec = total * 0.004
    est_full_sec = total * 0.30 * 0.18
    est_sec = est_cheap_sec + est_full_sec
    est_sec_hi = est_sec * 2.5

    # CP-SAT fast-path eligibility — mirror the conditions in
    # optimize_staffing_scenarios (_cpsat_usable + solve_full_assignment's
    # weekday-only window support). Keep these in sync.
    has_variations = any(v for v in axes["variation_sets"] if v)
    windows_periodic = not use_extra_windows or all(not (w or {}).get("specific_date") for w in (extra_windows or []))
    cpsat_eligible = False
    if has_variations and stagger_phases and windows_periodic:
        try:
            from logic.staffing_cpsat import ortools_available

            cpsat_eligible = ortools_available()
        except Exception:
            cpsat_eligible = False

    # One heuristic sim + at most one solver probe per (rotation/variation combo
    # x officer count x shift length). Measured 2026-07-22: ~0.2s heuristic,
    # 1.5–21s per CP-SAT probe on the reference scenario.
    smart_units = max(1, n_rot_valid) * max(1, len(axes["officer_counts"])) * max(1, len(axes["length_opts"]))
    smart_sec_lo = smart_units * 1.5
    smart_sec_hi = smart_units * 25.0

    def _risk_for(sec_hi: float, layouts: int) -> str:
        if layouts >= 500_000 or sec_hi >= 3600:
            return "extreme"
        if layouts >= 80_000 or sec_hi >= 600:
            return "high"
        if layouts >= 15_000 or sec_hi >= 120:
            return "medium"
        return "low"

    if cpsat_eligible:
        # Risk follows the smart plan's time, not the enumeration count.
        risk = _risk_for(smart_sec_hi, 0)
    else:
        risk = _risk_for(est_sec_hi, total)

    def _fmt_time(sec: float) -> str:
        if sec < 60:
            return f"~{max(1, int(sec))} seconds"
        if sec < 3600:
            return f"~{sec / 60:.0f}–{sec * 2.5 / 60:.0f} minutes"
        return f"~{sec / 3600:.1f}–{sec * 2.5 / 3600:.1f} hours"

    def _fmt_range(lo: float, hi: float) -> str:
        if hi < 90:
            return f"~{max(1, int(lo))}–{max(1, int(hi))} seconds"
        if hi < 5400:
            return f"~{max(1, int(lo / 60))}–{max(1, int(hi / 60))} minutes"
        return f"~{lo / 3600:.1f}–{hi / 3600:.1f} hours"

    # Only suggest locking dimensions that are actually free.
    _lock_hints = {
        "shift_length": "shift length",
        "shift_starts": "shift starts",
        "min_per_shift": "min per shift",
        "rotation": "rotation",
        "rotation_variations": "rotation patterns",
    }
    lockable = [_lock_hints[d] for d in axes["free_dims"] if d in _lock_hints]
    if len(axes["officer_counts"]) > 1:
        lockable.insert(0, "officer count")
    lock_hint = f"Lock {', '.join(lockable)} to shrink the space." if lockable else ""

    warning = ""
    if cpsat_eligible:
        warning = (
            f"Solver fast path applies (multi-block patterns): about {smart_units:,} solver probe(s), "
            f"expected {_fmt_range(smart_sec_lo, smart_sec_hi)}. "
            f"(Exhaustive fallback space behind it: {total:,} layouts — only combos the solver "
            "can't decide fall back to it.)"
        )
        if risk in ("high", "extreme") and lock_hint:
            warning += " " + lock_hint
    elif risk in ("high", "extreme"):
        warning = (
            f"With current free dimensions ({', '.join(axes['free_dims']) or 'none'}), "
            f"about {total:,} layouts must be checked. "
            f"Expected time {_fmt_time(est_sec)}. " + (lock_hint or "")
        )
    elif risk == "medium":
        warning = (
            f"Search space ≈ {total:,} layouts ({_fmt_time(est_sec)}). Locking more requirements will shrink this."
        )
    else:
        warning = f"Search space ≈ {total:,} layouts ({_fmt_time(est_sec)})."

    return {
        "success": True,
        "total_layouts": total,
        "outer_structural": outer,
        "free_dimensions": list(axes["free_dims"]),
        "risk": risk,
        "warning": warning,
        "est_seconds_low": round(est_sec, 1),
        "est_seconds_high": round(est_sec_hi, 1),
        "time_label": _fmt_time(est_sec),
        "cpsat_eligible": cpsat_eligible,
        "smart_units": smart_units,
        "smart_seconds_low": round(smart_sec_lo, 1),
        "smart_seconds_high": round(smart_sec_hi, 1),
        "smart_time_label": _fmt_range(smart_sec_lo, smart_sec_hi),
        "requires_confirm": (risk in ("high", "extreme") or total >= 50_000)
        if not cpsat_eligible
        else risk in ("high", "extreme"),
        "officer_counts": axes["officer_counts"],
        "length_options": axes["length_opts"],
        "min_per_shift_options": axes["min_per_shift_options"],
        "rotation_types": axes["rotation_types"],
        "constraint_labels": dict(CONSTRAINT_LABELS),
        "default_weights": dict(DEFAULT_CONSTRAINT_WEIGHTS),
    }


def optimize_staffing_scenarios(*args, **kwargs) -> Dict:
    """Public entry — see `_optimize_staffing_scenarios` for the search; this
    wrapper attaches the canonical `ScheduleStatus` (master plan section 3)
    additively from `solver_status`, never overwriting the legacy fields.
    Also attaches `simulation_report`, a `SimulationReport` preview built
    from the ranked scenario rows."""
    result = _optimize_staffing_scenarios(*args, **kwargs)
    status = to_canonical_status(result.get("solver_status", "unknown"))
    result["canonical_status"] = status
    result["simulation_report"] = _ranked_result_to_report(result, status, kwargs)
    return result


def _candidate_from_ranked_row(row: Dict) -> ScheduleCandidate:
    n = int(row.get("num_officers") or 0)
    home_starts = row.get("officer_home_starts") or []
    cycle_starts = row.get("officer_cycle_starts") or []
    assignments = [
        {
            "officer_id": o,
            "home_start": home_starts[o] if o < len(home_starts) else None,
            "cycle_starts": cycle_starts[o] if o < len(cycle_starts) else None,
        }
        for o in range(n)
    ]
    metrics = row.get("metrics") or {}
    objective_values = {k: v for k, v in metrics.items() if isinstance(v, (int, float))}
    return ScheduleCandidate(
        assignments=assignments,
        objective_values=objective_values,
        applied_hard_constraints=[] if row.get("hard_constraints_ok") else list(row.get("failed_constraints") or []),
        relaxations=list(row.get("failed_constraints") or []),
    )


def _ranked_result_to_report(result: Dict, status, kwargs: Dict) -> SimulationReport:
    ranked = result.get("ranked") or []
    candidates = [_candidate_from_ranked_row(row) for row in ranked]
    return SimulationReport(
        status=status,
        candidates=candidates,
        solver="staffing_optimizer",
        verification=_verification_from_ranked_rows(ranked),
        input_hash=compute_input_hash(kwargs),
        policy_hash=compute_policy_hash(kwargs),
        runtime_sec=float(result.get("wall_time_ms") or 0) / 1000.0,
        search_statistics={
            "scenarios_evaluated": result.get("scenarios_evaluated"),
            "scenarios_kept": result.get("scenarios_kept"),
            "search_exhaustive": result.get("search_exhaustive"),
            "budget_exhausted": result.get("budget_exhausted"),
        },
        warnings=[result["message"]] if result.get("message") else [],
    )


def _verification_from_ranked_rows(ranked: List[Dict]):
    """Adapt each row's already-computed `hard_constraints_ok`/`violations`
    (from `simulate_schedule`'s own sweep-line check — see
    `logic/staffing_cpsat.py` module docstring) into a typed
    `VerificationReport`. Does not re-derive coverage from raw assignments —
    ranked rows don't carry per-minute assignment data, only the sweep-line
    check's already-computed verdict, so this wraps that verdict rather than
    risking a second, possibly-inconsistent time model."""
    if not ranked:
        return None
    violations: List[str] = []
    checked: set = set()
    verified = True
    for row in ranked:
        if not row.get("hard_constraints_ok"):
            verified = False
        # row["violations"] is the full checked-category vector (dict,
        # category -> count, present whether or not that category actually
        # failed) — row["failed_constraints"] is the already-filtered list
        # of categories that actually failed. Use the latter for both, or
        # every row would report every checked category as a "violation"
        # regardless of its count.
        failed = [str(c) for c in row.get("failed_constraints") or []]
        violations.extend(failed)
        checked.update(str(c) for c in (row.get("violations") or {}))
    return VerificationReport(
        verified=verified,
        status=ScheduleStatus.FEASIBLE if verified else ScheduleStatus.INFEASIBLE,
        violations=violations,
        checked_constraints=sorted(checked),
        notes="derived from simulate_schedule's own sweep-line check per ranked row",
    )


def _optimize_staffing_scenarios(
    *,
    rotation_types: Optional[List[str]] = None,
    officer_counts: Optional[List[int]] = None,
    min_per_shift_options: Optional[List[int]] = None,
    shift_length_hours: Optional[float] = None,
    annual_hours_target: Optional[float] = None,
    shift_starts: Optional[List[str]] = None,
    simulation_days: int = 56,
    sim_start_date: str = None,
    coverage_247: int = 0,
    avoid_flsa_overtime: bool = False,
    flsa_work_period_days: int = 28,
    annual_hours_variance: float = 40.0,
    annual_hours_hard: bool = False,
    use_extra_windows: bool = False,
    extra_windows: Optional[List[Dict]] = None,
    night_minimum: Optional[int] = None,
    require_hard_ok: bool = True,
    rotation_style: str = "",
    rotation_variations: Optional[List[str]] = None,
    rotation_variation_sets: Optional[List[List[str]]] = None,
    stagger_phases: bool = True,
    shift_starts_options: Optional[List[List[str]]] = None,
    shift_length_options: Optional[List[float]] = None,
    max_total_evals: Optional[int] = None,  # ignored — no artificial cap
    search_depth: str = "normal",  # ignored — exhaustive
    max_inner_trials: Optional[int] = None,  # ignored — exhaustive model
    free_officer_counts: bool = False,
    free_starts: bool = False,
    free_lengths: bool = False,
    free_variations: bool = False,
    constraint_weights: Optional[Dict[str, float]] = None,
    constraint_priority: Optional[List[str]] = None,
    nearby_start_hops: int = 1,
    allow_offday_coverage: bool = False,
    min_rest_hours: float = 0.0,
    max_consecutive_work_days: int = 0,
    max_start_variation_hours: Optional[float] = None,
    prefer_unique_daily_starts: bool = False,
    input_roles: Optional[Dict[str, Any]] = None,
    warm_start: Optional[Dict[str, Any]] = None,
    required_cert_codes: Optional[List[str]] = None,
    progress_callback=None,
    cancel_check=None,
    time_budget_seconds: Optional[float] = None,
) -> Dict:
    """
    Exhaustive sweep of the constraint-defined space (outer × phase × pattern).

    max_total_evals / search_depth / max_inner_trials are accepted for API
    compatibility but do not truncate the search.

    nearby_start_hops — work-day start "bumps" from home (± pack bands).
    allow_offday_coverage — only when user opts in; default respects rotation OFF.

    progress_callback(dict) — optional; receives done/total/full_sims/best_summary.
    cancel_check() — optional; when True, stop and return partial results.
    time_budget_seconds — optional hard wall-clock cap (P0.3): when exceeded the
    search stops gracefully and returns ranked best-so-far with
    budget_exhausted=True. None = uncapped (explicit opt-in only).
    """
    from config import ROTATION_PRESETS
    from logic.rotation_patterns import build_pattern
    from simulator import SimulatorConfig, simulate_schedule

    del max_total_evals, search_depth, max_inner_trials  # no caps

    nearby_hops = max(0, int(nearby_start_hops if nearby_start_hops is not None else 1))
    offday_ok = bool(allow_offday_coverage)

    t0 = time.perf_counter()
    weights = _weights_from_priority(constraint_priority, constraint_weights)
    normalized_input_roles = normalize_simulator_input_roles(input_roles)
    cancelled = False
    budget_exhausted = False
    _budget = float(time_budget_seconds) if time_budget_seconds else None

    def _cancelled() -> bool:
        nonlocal cancelled, budget_exhausted
        if cancelled:
            return True
        if _budget is not None and (time.perf_counter() - t0) > _budget:
            budget_exhausted = True
            cancelled = True
            return True
        if cancel_check is None:
            return cancelled
        try:
            if cancel_check():
                cancelled = True
                return True
        except Exception:
            pass
        return cancelled

    def _progress(**kwargs) -> None:
        if progress_callback is None:
            return
        try:
            progress_callback(kwargs)
        except Exception:
            pass

    space = estimate_search_space(
        rotation_types=rotation_types,
        officer_counts=officer_counts,
        min_per_shift_options=min_per_shift_options,
        shift_length_hours=shift_length_hours,
        shift_starts=shift_starts,
        shift_starts_options=shift_starts_options,
        shift_length_options=shift_length_options,
        rotation_style=rotation_style,
        rotation_variations=rotation_variations,
        rotation_variation_sets=rotation_variation_sets,
        free_officer_counts=free_officer_counts,
        free_starts=free_starts,
        free_lengths=free_lengths,
        free_variations=free_variations,
        stagger_phases=stagger_phases,
        use_extra_windows=use_extra_windows,
        extra_windows=extra_windows,
    )

    axes = _resolve_axes(
        rotation_types=rotation_types,
        officer_counts=officer_counts,
        min_per_shift_options=min_per_shift_options,
        shift_length_hours=shift_length_hours,
        shift_length_options=shift_length_options,
        shift_starts=shift_starts,
        shift_starts_options=shift_starts_options,
        free_officer_counts=free_officer_counts,
        free_starts=free_starts,
        free_lengths=free_lengths,
        free_variations=free_variations,
        rotation_variations=rotation_variations,
        rotation_variation_sets=rotation_variation_sets,
        rotation_style=rotation_style,
    )

    staffing = axes["staffing"]
    annual = float(annual_hours_target) if annual_hours_target is not None else float(staffing["annual_hours_target"])
    # UI passes None when the annual-hours requirement is off; every consumer
    # below expects a number (float() at the early-impossible gate crashed on
    # None — found live 2026-07-17). Coalesce to the signature default once.
    annual_hours_variance = float(annual_hours_variance) if annual_hours_variance is not None else 40.0
    night_min = int(night_minimum) if night_minimum is not None else int(config.NIGHT_MINIMUM_OFFICERS)
    windows = list(extra_windows or [])
    cov247 = max(0, int(coverage_247 or 0))
    style = axes["style"]
    sim_start = date.today()
    if sim_start_date:
        try:
            from datetime import date as _date

            sim_start = _date.fromisoformat(str(sim_start_date))
        except (ValueError, TypeError):
            sim_start = date.today()  # graceful fallback
    window_min = _window_body_floor(windows, use_windows=bool(use_extra_windows and windows))
    multi_block_mode = any((v and any("," in str(x) for x in v)) for v in axes.get("variation_sets") or []) or any(
        "," in str(x) for x in (axes.get("base_variations") or [])
    )

    # C5 — early impossible when every officer count fails pattern/body floors
    from logic.optimizer_features import diversify_ranked, early_impossible_proof
    from logic.staffing_cpsat import (
        ortools_available,
        solve_cycle_day_starts,
        solve_full_assignment,
        solve_phase_variant,
    )

    early_skip_all = True
    early_reasons: List[str] = []
    length0 = float(axes["length_opts"][0]) if axes["length_opts"] else float(shift_length_hours or 8)
    # Check every variation SET the real search will try (not just the first/
    # locked one) — a set is only truly impossible for this N if every set is.
    var_sets_to_check = axes.get("variation_sets") or [axes.get("base_variations") or []]
    for n_try in axes["officer_counts"]:
        n_reasons: List[str] = []
        n_possible = False
        if required_cert_codes:
            from logic.certifications import roster_cert_coverage_for_sim

            cert_check = roster_cert_coverage_for_sim(
                required_codes=list(required_cert_codes),
                shift_starts=list(shift_starts or []),
                num_officers=int(n_try),
            )
            if cert_check.get("thin_for_headcount"):
                early_reasons.append(
                    f"N={n_try}: certification gate has {cert_check.get('eligible', 0)} eligible active officers"
                )
                continue
        for vset in var_sets_to_check:
            reason = early_impossible_proof(
                num_officers=int(n_try),
                shift_length_hours=length0,
                annual_hours_target=float(annual),
                annual_hours_variance=float(annual_hours_variance),
                annual_hours_hard=bool(annual_hours_hard),
                rotation_variations=vset or None,
                coverage_247=cov247,
                window_min=window_min,
                rotation_style=style or "rotating",
            )
            if reason:
                n_reasons.append(reason)
            else:
                n_possible = True
                break
        if n_possible:
            early_skip_all = False
        else:
            early_reasons.append(f"N={n_try}: {n_reasons[0] if n_reasons else 'constraints'}")
    if early_skip_all and axes["officer_counts"] and require_hard_ok:
        # Still one soft full-sim so UI gets near-miss options (not empty silence).
        from simulator import SimulatorConfig, simulate_schedule

        n_try = max(int(x) for x in axes["officer_counts"])
        length_try = length0
        starts_try = (
            list(axes["locked_starts_opts"][0]) if axes.get("locked_starts_opts") else ["06:00", "14:00", "22:00"]
        )
        vars_try = list(axes.get("base_variations") or [])
        cfg = SimulatorConfig(
            rotation_type=(axes["rotation_types"][0] if axes["rotation_types"] else "2-2-3 (14-day)"),
            num_officers=n_try,
            shift_length_hours=float(length_try),
            annual_hours_target=float(annual),
            shift_starts=starts_try,
            apply_department_rules=False,
            min_per_shift=int(axes["min_per_shift_options"][0]),
            simulation_days=int(simulation_days),
            night_minimum=night_min,
            annual_hours_variance=float(annual_hours_variance),
            annual_hours_hard=bool(annual_hours_hard),
            coverage_247=cov247,
            avoid_flsa_overtime=bool(avoid_flsa_overtime),
            flsa_work_period_days=int(flsa_work_period_days or 28),
            use_extra_windows=bool(use_extra_windows and windows),
            extra_windows=windows,
            auto_min_officers=False,
            rotation_style=style or "rotating",
            rotation_variations=vars_try,
            stagger_phases=True,
        )
        sim = simulate_schedule(cfg)
        near: List[Dict] = []
        if sim.success:
            m = sim.metrics or {}
            v = _violation_vector(m, annual=annual, annual_variance=annual_hours_variance)
            failed = [k for k in ("coverage_247", "windows", "gaps", "flsa", "annual") if v.get(k, 0) > 0]
            near.append(
                {
                    "score": 0,
                    "rotation_type": cfg.rotation_type,
                    "num_officers": n_try,
                    "min_per_shift": cfg.min_per_shift,
                    "shift_length_hours": length_try,
                    "annual_hours_target": annual,
                    "shift_starts": starts_try,
                    "rotation_style": style,
                    "rotation_variations": vars_try,
                    "hard_constraints_ok": False,
                    "metrics": m,
                    "violations": v,
                    "failed_constraints": failed or ["windows"],
                    "summary": (
                        f"{n_try} Officers · Early impossible — "
                        + (early_reasons[0] if early_reasons else "constraints")
                    ),
                    "rank": 1,
                    "human_metrics": {
                        "extra_window_failures": int(m.get("extra_window_failures") or 0),
                        "coverage_247_failures": int(m.get("coverage_247_failures") or 0),
                        "failed_constraints": failed or ["windows"],
                        "hard_constraints_ok": False,
                    },
                }
            )
        wall_ms = int((time.perf_counter() - t0) * 1000)
        msg = "No Schedule Meets The Selected Hard Constraints (early proof)"
        if early_reasons:
            msg += " — " + early_reasons[0]
        return {
            "success": False,
            "cancelled": False,
            "scenarios_evaluated": 1,
            "scenarios_kept": 0,
            "rejected_hard_constraints": len(axes["officer_counts"]),
            "outer_configs": 1,
            "inner_trials": 1,
            "full_sims_run": 1,
            "pruned_cheap": 0,
            "search_exhaustive": True,
            "budget_exhausted": False,
            "wall_time_ms": wall_ms,
            "failure_histogram": {"early_impossible": len(early_reasons)},
            "space_estimate": space,
            "space_note": space.get("warning") or "",
            "constraint_weights": weights,
            "constraint_priority": list(constraint_priority or []),
            "input_roles": normalized_input_roles,
            "near_misses": near,
            "best": None,
            "ranked": [],
            "message": msg,
            "impossible": True,
            "solver_status": "proven_infeasible",
            "early_impossible": True,
            "early_reasons": early_reasons,
            "constraints_applied": {
                "coverage_247": cov247,
                "officer_counts": list(axes["officer_counts"]),
                "search_mode": "early_impossible",
            },
        }

    results: List[Dict] = []
    near_misses: List[Dict] = []
    rejected_hard = 0
    outer_configs = 0
    cheap_evals = 0
    full_sims = 0
    pruned_cheap = 0
    fail_hist: Dict[str, int] = {
        "hard_ok": 0,
        "flsa": 0,
        "window": 0,
        "coverage_247": 0,
        "annual": 0,
        "gaps": 0,
        "sim_fail": 0,
        "cheap_reject": 0,
    }

    ordered_n = sorted(axes["officer_counts"])
    space_total = int(space.get("total_layouts") or 0)
    _progress(
        phase="start",
        done=0,
        total=space_total,
        full_sims=0,
        message=f"Starting exhaustive search ({space_total:,} layouts)…",
    )

    def _record_fail(m: Optional[Dict]) -> None:
        if not m:
            fail_hist["sim_fail"] += 1
            return
        if not m.get("hard_constraints_ok", True):
            fail_hist["hard_ok"] += 1
        if int(m.get("flsa_violations") or 0):
            fail_hist["flsa"] += 1
        if int(m.get("extra_window_failures") or 0):
            fail_hist["window"] += 1
        if int(m.get("coverage_247_failures") or 0):
            fail_hist["coverage_247"] += 1
        if int(m.get("annual_mean_outside") or m.get("annual_band_outside") or 0):
            fail_hist["annual"] += 1
        gaps = m.get("gap_events")
        if gaps is None:
            gaps = m.get("zero_staff_slots") or 0
        if int(gaps or 0):
            fail_hist["gaps"] += 1

    def _row_from_sim(
        *,
        sim,
        rot_key,
        n_off,
        min_ps,
        length,
        starts,
        use_style,
        variations,
        ph,
        pm,
        hard_ok,
        home_starts=None,
        cycle_starts=None,
    ) -> Dict:
        m = sim.metrics or {}
        score = _score_metrics(
            m,
            annual=annual,
            annual_variance=float(annual_hours_variance),
            n_off=int(n_off),
            hard_ok=hard_ok,
            weights=weights,
            pattern_slot_map=list(pm) if isinstance(pm, (list, tuple)) else None,
            multi_block=bool(multi_block_mode or (variations and len(variations) > 1)),
        )
        v = _violation_vector(m, annual=annual, annual_variance=annual_hours_variance)
        failed = [k for k in ("coverage_247", "windows", "gaps", "flsa", "annual") if v.get(k, 0) > 0]
        return {
            "score": round(score, 2),
            "rotation_type": rot_key,
            "num_officers": n_off,
            "min_per_shift": min_ps,
            "shift_length_hours": length,
            "annual_hours_target": annual,
            "shift_starts": list(starts),
            "rotation_style": use_style,
            "rotation_variations": list(variations),
            "hard_constraints_ok": hard_ok,
            "metrics": m,
            "violations": v,
            "failed_constraints": failed,
            "phase_overrides": list(ph) if ph is not None else None,
            "pattern_slot_map": list(pm) if pm is not None else None,
            "officer_home_starts": list(home_starts) if home_starts else None,
            "officer_cycle_starts": [list(days) for days in cycle_starts] if cycle_starts else None,
            "suggestions": [
                {
                    "severity": s.severity,
                    "title": s.title,
                    "message": s.message,
                    "recommendation": s.recommendation,
                }
                for s in (sim.suggestions or [])
            ],
        }

    for rotation in axes["rotation_types"]:
        for variations in axes["variation_sets"]:
            if rotation not in ROTATION_PRESETS and not variations:
                continue
            rot_key = rotation if rotation in ROTATION_PRESETS else next(iter(ROTATION_PRESETS.keys()))
            use_style = style
            if variations and use_style not in ("fixed", "rotating"):
                use_style = "rotating" if any("," in v for v in variations) else "fixed"

            parsed_patterns = []
            cycle_len = 14
            if variations:
                try:
                    for t in variations:
                        parsed_patterns.append(
                            build_pattern(
                                t,
                                style=use_style if use_style in ("fixed", "rotating") else None,
                            )
                        )
                    cycle_len = parsed_patterns[0].cycle_length
                    from logic.rotation_patterns import expand_block_permutations

                    parsed_patterns = expand_block_permutations(parsed_patterns)
                except ValueError:
                    continue
            else:
                parsed_patterns = _preset_patterns_for_cpsat(rot_key)
                if parsed_patterns:
                    cycle_len = parsed_patterns[0].cycle_length

            # Pattern maps index the expanded permutation list. Replay must use
            # that exact list, not the shorter user-entered seed list.
            cpsat_variations = [p.to_text() for p in parsed_patterns]

            _cpsat_cache: Dict[Tuple[int, float], Dict] = {}
            _cpsat_usable = bool(parsed_patterns) and stagger_phases and ortools_available()
            _full_tried: set = set()
            _full_solved: set = set()

            for n_off in ordered_n:
                for min_ps in axes["min_per_shift_options"]:
                    for length in axes["length_opts"]:
                        cpsat_pv: Optional[Dict] = None
                        if _cpsat_usable:
                            ckey = (int(n_off), float(length))
                            if ckey not in _cpsat_cache:
                                _cpsat_cache[ckey] = solve_phase_variant(
                                    parsed_patterns,
                                    n_officers=int(n_off),
                                    shift_length_hours=float(length),
                                    coverage_247=cov247,
                                    annual_hours_target=float(annual),
                                    annual_hours_variance=float(annual_hours_variance),
                                    annual_hours_hard=bool(annual_hours_hard),
                                    max_consecutive_work_days=int(max_consecutive_work_days),
                                    min_rest_hours=float(min_rest_hours),
                                )
                            cpsat_pv = _cpsat_cache[ckey]

                        if axes["locked_starts_opts"] is not None:
                            starts_opts = axes["locked_starts_opts"]
                        else:
                            starts_opts = generate_start_packs(float(length), num_officers=n_off)

                        # Full CP-SAT (variant + phase + per-officer start together) —
                        # tried once per (n_off, length), independent of which starts
                        # pack the loop below is on. Owns minute-level 24/7 + window
                        # coverage itself, so a feasible hit here skips the entire
                        # phase x pattern x starts-pack search for this combo. NOT a
                        # relaxation (fixes one start per officer all cycle, unlike the
                        # real day-pool balancer) — infeasible/unsupported here does
                        # NOT prove the real problem is infeasible, so only the
                        # feasible branch short-circuits anything; everything else
                        # falls through to the unchanged pipeline below.
                        if (
                            _cpsat_usable
                            and (cpsat_pv is None or cpsat_pv.get("status") != "infeasible")
                            and (n_off, float(length)) not in _full_tried
                            and not _cancelled()
                        ):
                            _full_tried.add((n_off, float(length)))
                            # Hourly starts solve the broad cycle-day model much
                            # faster. Half-hour starts remain available in the
                            # exhaustive fallback when the solver does not find
                            # a result.
                            cand_starts = (
                                [f"{hour:02d}:00" for hour in range(24)]
                                if axes["free_starts"] and axes["locked_starts_opts"] is None
                                else sorted({s for pack in starts_opts for s in pack})
                            )

                            # Cheap heuristic pre-check first — simulator's own
                            # built-in stagger already solves the easy/common case
                            # instantly. Only pay for the (slower, exact) full
                            # CP-SAT solve when that quick attempt actually fails.
                            heuristic_hard_ok = False
                            if starts_opts:
                                try:
                                    quick_cfg = SimulatorConfig(
                                        rotation_type=rot_key,
                                        num_officers=int(n_off),
                                        shift_length_hours=float(length),
                                        annual_hours_target=float(annual),
                                        shift_starts=list(starts_opts[0]),
                                        apply_department_rules=False,
                                        min_per_shift=int(min_ps),
                                        simulation_days=int(simulation_days),
                                        night_minimum=night_min,
                                        annual_hours_variance=float(annual_hours_variance),
                                        annual_hours_hard=bool(annual_hours_hard),
                                        coverage_247=cov247,
                                        avoid_flsa_overtime=bool(avoid_flsa_overtime),
                                        flsa_work_period_days=int(flsa_work_period_days or 28),
                                        use_extra_windows=bool(use_extra_windows and windows),
                                        extra_windows=windows,
                                        auto_min_officers=False,
                                        rotation_style="rotating" if cpsat_variations else use_style,
                                        rotation_variations=cpsat_variations,
                                        stagger_phases=True,
                                        phase_overrides=None,
                                        pattern_slot_map=None,
                                        nearby_start_hops=nearby_hops,
                                        allow_offday_coverage=offday_ok,
                                        min_rest_hours=float(min_rest_hours),
                                        max_consecutive_work_days=int(max_consecutive_work_days),
                                        sim_start_date=sim_start,
                                    )
                                    quick_sim = simulate_schedule(quick_cfg)
                                    full_sims += 1
                                    if quick_sim.success:
                                        qm = quick_sim.metrics or {}
                                        if not _constraint_fail(
                                            qm,
                                            require_hard_ok=require_hard_ok,
                                            avoid_flsa_overtime=avoid_flsa_overtime,
                                            cov247=cov247,
                                            use_extra_windows=bool(use_extra_windows and windows),
                                            windows=windows,
                                            annual_hours_hard=annual_hours_hard,
                                            min_ps=int(min_ps),
                                            min_rest_hours=float(min_rest_hours),
                                            max_consecutive_work_days=int(max_consecutive_work_days),
                                        ):
                                            heuristic_hard_ok = True
                                            results.append(
                                                _row_from_sim(
                                                    sim=quick_sim,
                                                    rot_key=rot_key,
                                                    n_off=n_off,
                                                    min_ps=min_ps,
                                                    length=length,
                                                    starts=list(starts_opts[0]),
                                                    use_style=use_style,
                                                    variations=variations,
                                                    ph=None,
                                                    pm=None,
                                                    hard_ok=True,
                                                )
                                            )
                                            _full_solved.add((n_off, float(length)))
                                except Exception:
                                    heuristic_hard_ok = False

                            full = (
                                {"status": "skipped"}
                                if heuristic_hard_ok and not axes["free_starts"]
                                else (
                                    solve_cycle_day_starts(
                                        parsed_patterns,
                                        n_officers=int(n_off),
                                        shift_length_hours=float(length),
                                        candidate_starts=cand_starts,
                                        sim_start_date=sim_start,
                                        coverage_247=cov247,
                                        extra_windows=windows if use_extra_windows else None,
                                        annual_hours_target=float(annual),
                                        annual_hours_variance=float(annual_hours_variance),
                                        annual_hours_hard=bool(annual_hours_hard),
                                        max_consecutive_work_days=int(max_consecutive_work_days),
                                        min_rest_hours=float(min_rest_hours),
                                        max_start_variation_hours=max_start_variation_hours,
                                        prefer_unique_daily_starts=bool(prefer_unique_daily_starts),
                                        objective_order=constraint_priority,
                                        warm_start=warm_start,
                                        time_limit_sec=30.0,
                                    )
                                    if axes["free_starts"]
                                    else solve_full_assignment(
                                        parsed_patterns,
                                        n_officers=int(n_off),
                                        shift_length_hours=float(length),
                                        candidate_starts=cand_starts,
                                        sim_start_date=sim_start,
                                        coverage_247=cov247,
                                        extra_windows=windows if use_extra_windows else None,
                                        annual_hours_target=float(annual),
                                        annual_hours_variance=float(annual_hours_variance),
                                        annual_hours_hard=bool(annual_hours_hard),
                                        max_consecutive_work_days=int(max_consecutive_work_days),
                                        min_rest_hours=float(min_rest_hours),
                                        max_solutions=5,
                                        pool_time_limit_sec=15.0,
                                        warm_start=warm_start,
                                        progress_callback=progress_callback,
                                    )
                                )
                            )
                            if full.get("status") == "feasible":
                                cpsat_sols = full.get("solutions") or [full]
                                for sol in cpsat_sols:
                                    sol_phase = sol.get("phase", full.get("phase"))
                                    sol_pm = sol.get("pattern_map", full.get("pattern_map"))
                                    sol_starts = sol.get(
                                        "shift_starts_per_officer", full.get("shift_starts_per_officer")
                                    )
                                    sol_cycle_starts = sol.get(
                                        "cycle_starts_per_officer", full.get("cycle_starts_per_officer")
                                    )
                                    selected_starts = sorted(
                                        {
                                            start
                                            for officer_days in (sol_cycle_starts or [])
                                            for start in officer_days
                                            if start
                                        }
                                    ) or sorted(set(sol_starts))
                                    full_cfg = SimulatorConfig(
                                        rotation_type=rot_key,
                                        num_officers=int(n_off),
                                        shift_length_hours=float(length),
                                        annual_hours_target=float(annual),
                                        # Candidate starts are the solver's search
                                        # domain, not required shift bands. Replay
                                        # only the starts selected by this solution.
                                        shift_starts=selected_starts,
                                        apply_department_rules=False,
                                        min_per_shift=int(min_ps),
                                        simulation_days=int(simulation_days),
                                        night_minimum=night_min,
                                        annual_hours_variance=float(annual_hours_variance),
                                        annual_hours_hard=bool(annual_hours_hard),
                                        coverage_247=cov247,
                                        avoid_flsa_overtime=bool(avoid_flsa_overtime),
                                        flsa_work_period_days=int(flsa_work_period_days or 28),
                                        use_extra_windows=bool(use_extra_windows and windows),
                                        extra_windows=windows,
                                        auto_min_officers=False,
                                        rotation_style="rotating" if cpsat_variations else use_style,
                                        rotation_variations=cpsat_variations,
                                        stagger_phases=False,
                                        phase_overrides=sol_phase,
                                        pattern_slot_map=sol_pm,
                                        officer_home_starts=sol_starts,
                                        officer_cycle_starts=sol_cycle_starts,
                                        nearby_start_hops=0,
                                        allow_offday_coverage=offday_ok,
                                        min_rest_hours=float(min_rest_hours),
                                        max_consecutive_work_days=int(max_consecutive_work_days),
                                        sim_start_date=sim_start,
                                    )
                                    full_sim = simulate_schedule(full_cfg)
                                    full_sims += 1
                                    if full_sim.success:
                                        fm = full_sim.metrics or {}
                                        full_hard_ok = bool(fm.get("hard_constraints_ok", True))
                                        row = _row_from_sim(
                                            sim=full_sim,
                                            rot_key=rot_key,
                                            n_off=n_off,
                                            min_ps=min_ps,
                                            length=length,
                                            starts=selected_starts,
                                            use_style="rotating" if cpsat_variations else use_style,
                                            variations=cpsat_variations,
                                            ph=sol_phase,
                                            pm=sol_pm,
                                            hard_ok=full_hard_ok,
                                            home_starts=sol_starts,
                                            cycle_starts=sol_cycle_starts,
                                        )
                                        if not _constraint_fail(
                                            fm,
                                            require_hard_ok=require_hard_ok,
                                            avoid_flsa_overtime=avoid_flsa_overtime,
                                            cov247=cov247,
                                            use_extra_windows=bool(use_extra_windows and windows),
                                            windows=windows,
                                            annual_hours_hard=annual_hours_hard,
                                            min_ps=int(min_ps),
                                            min_rest_hours=float(min_rest_hours),
                                            max_consecutive_work_days=int(max_consecutive_work_days),
                                        ):
                                            results.append(row)
                                            _full_solved.add((n_off, float(length)))

                        if (n_off, float(length)) in _full_solved and require_hard_ok:
                            # Already have a proven-exact hard-OK result for this
                            # combo from the full CP-SAT solve — no need to also
                            # run the phase x pattern x starts-pack search below.
                            continue

                        if cpsat_pv is not None and cpsat_pv.get("status") == "infeasible":
                            # This is a sound necessary-condition proof for the
                            # entire N/length combination. Do not spend the UI
                            # budget running a heuristic once per start pack.
                            continue

                        # _starts_priority defined here (not inside loop) to avoid
                        # unnecessary per-iteration closure allocation.
                        def _starts_priority(st: Sequence[str]) -> Tuple[int, int, int, str]:
                            hours = []
                            for s in st:
                                try:
                                    hours.append(int(str(s).split(":")[0]))
                                except ValueError:
                                    hours.append(0)
                            has_19 = any(h == 19 for h in hours)
                            has_14 = any(12 <= h < 19 for h in hours)
                            has_22 = any(h >= 20 or h < 5 for h in hours)
                            has_am = any(5 <= h <= 9 for h in hours)
                            if has_19 and has_14 and has_22 and has_am:
                                score = 0
                            elif has_19 and has_14 and has_22:
                                score = 1
                            elif has_14 and has_22 and has_am and not has_19:
                                score = 2
                            elif has_19 and has_14:
                                score = 3
                            elif has_19:
                                score = 4
                            else:
                                score = 6
                            return (score, -len(st), min(hours) if hours else 99, ",".join(st))

                        if axes["locked_starts_opts"] is None and len(starts_opts) > 1:
                            starts_opts = sorted(starts_opts, key=_starts_priority)

                        # Explore multiple start packs (diverse options), not one pack only.
                        max_hard_results = 24
                        max_unique_start_packs = 8

                        def _unique_packs() -> int:
                            return len(
                                {tuple(r.get("shift_starts") or []) for r in results if r.get("hard_constraints_ok")}
                            )

                        for starts in starts_opts:
                            if require_hard_ok and (
                                len(results) >= max_hard_results or _unique_packs() >= max_unique_start_packs
                            ):
                                break
                            # C3 pack-level prune: only when zero bands cover a window
                            # sample (stacking officers cannot help). need>N still full-sims
                            # so soft mode can rank near-misses.
                            if (
                                use_extra_windows
                                and windows
                                and not pack_meets_window_bands(
                                    starts,
                                    float(length),
                                    windows,
                                    num_officers=None,
                                )
                            ):
                                pruned_cheap += 1
                                fail_hist["cheap_reject"] = fail_hist.get("cheap_reject", 0) + 1
                                fail_hist["window"] = fail_hist.get("window", 0) + 1
                                if require_hard_ok:
                                    rejected_hard += 1
                                continue
                            outer_configs += 1
                            n_bands = max(1, len(starts))

                            if cpsat_pv is not None and cpsat_pv.get("status") == "infeasible":
                                # CP-SAT proved no (variant, phase) assignment can meet
                                # 24/7 coverage + annual-hours band for this N/length —
                                # a real proof, not a heuristic. Skip the exhaustive
                                # phase x pattern enumeration entirely for this combo.
                                phase_layouts = []
                                pat_maps = []
                            elif parsed_patterns and stagger_phases:
                                # Priority phases first (fast); expand to full if no hard-OK.
                                phase_layouts = generate_phase_layouts(int(n_off), cycle_len, mode="priority")
                                pat_maps = generate_pattern_maps(int(n_off), len(parsed_patterns))
                            elif parsed_patterns:
                                phase_layouts = [[0] * int(n_off)]
                                pat_maps = generate_pattern_maps(int(n_off), len(parsed_patterns))
                            else:
                                phase_layouts = [None]
                                pat_maps = [None]

                            # Fast path: simulator built-in stagger (None overrides) before
                            # exhaustive phase×pattern cheap scan — finds 14/19 evening packs
                            # and good multi-block offsets without waiting on 2k+ cheap nodes.
                            _fast_layouts: List[Tuple[Optional[List[int]], Optional[List[int]]]] = []
                            if cpsat_pv is not None and cpsat_pv.get("status") == "feasible":
                                # CP-SAT-found (phase, variant) candidate — satisfies day-level
                                # 24/7 + annual-hours band exactly; windows/rest-pool balance
                                # still verified below by the real simulator. Tried before the
                                # heuristic and before exhaustive fallback.
                                _fast_layouts.append((cpsat_pv["phase"], cpsat_pv["pattern_map"]))
                            if parsed_patterns and stagger_phases:
                                _fast_layouts.append((None, None))
                            for _fph, _fpm in _fast_layouts:
                                if _cancelled():
                                    break
                                if require_hard_ok and len(results) >= max_hard_results:
                                    break
                                cfg = SimulatorConfig(
                                    rotation_type=rot_key,
                                    num_officers=int(n_off),
                                    shift_length_hours=float(length),
                                    annual_hours_target=float(annual),
                                    shift_starts=list(starts),
                                    apply_department_rules=False,
                                    min_per_shift=int(min_ps),
                                    simulation_days=int(simulation_days),
                                    night_minimum=night_min,
                                    annual_hours_variance=float(annual_hours_variance),
                                    annual_hours_hard=bool(annual_hours_hard),
                                    coverage_247=cov247,
                                    avoid_flsa_overtime=bool(avoid_flsa_overtime),
                                    flsa_work_period_days=int(flsa_work_period_days or 28),
                                    use_extra_windows=bool(use_extra_windows and windows),
                                    extra_windows=windows,
                                    auto_min_officers=False,
                                    rotation_style=use_style,
                                    rotation_variations=list(variations),
                                    stagger_phases=True,
                                    phase_overrides=None,
                                    pattern_slot_map=None,
                                    flexible_daily_starts=False,
                                    nearby_start_hops=nearby_hops,
                                    allow_offday_coverage=offday_ok,
                                    min_rest_hours=float(min_rest_hours),
                                    max_consecutive_work_days=int(max_consecutive_work_days),
                                    sim_start_date=sim_start,
                                )
                                sim = simulate_schedule(cfg)
                                full_sims += 1
                                cheap_evals += 1
                                _progress(
                                    phase="fast",
                                    done=cheap_evals,
                                    total=space_total or cheap_evals,
                                    full_sims=full_sims,
                                    message=f"Fast stagger try · starts {starts}",
                                )
                                if not sim.success:
                                    continue
                                m = sim.metrics or {}
                                hard_ok = bool(m.get("hard_constraints_ok", True))
                                row = _row_from_sim(
                                    sim=sim,
                                    rot_key=rot_key,
                                    n_off=n_off,
                                    min_ps=min_ps,
                                    length=length,
                                    starts=starts,
                                    use_style=use_style,
                                    variations=variations,
                                    ph=None,
                                    pm=None,
                                    hard_ok=hard_ok,
                                )
                                if not _constraint_fail(
                                    m,
                                    require_hard_ok=require_hard_ok,
                                    avoid_flsa_overtime=avoid_flsa_overtime,
                                    cov247=cov247,
                                    use_extra_windows=bool(use_extra_windows and windows),
                                    windows=windows,
                                    annual_hours_hard=annual_hours_hard,
                                    min_ps=int(min_ps),
                                    min_rest_hours=float(min_rest_hours),
                                    max_consecutive_work_days=int(max_consecutive_work_days),
                                ):
                                    results.append(row)
                                    # Keep scanning more packs/phases for alternate options
                                    if len(results) >= max_hard_results:
                                        break
                                    continue
                                rejected_hard += 1
                                _record_fail(m)
                                # keep as near-miss seed
                                near_misses.append(row)

                            if require_hard_ok and len(results) >= max_hard_results:
                                continue

                            # Exhaustive cheap scan of entire phase×pattern model (no eval cap).
                            # Full-sim: all cheap-pass in best-first order until hard-OK, then
                            # more survivors for ranked alternatives (rank pool). Cheap failures:
                            # only top few for near-miss metrics.
                            _cheap_penalty = {
                                "coverage_247": 50_000,
                                "window": 40_000,
                                "gaps": 30_000,
                                "annual": 20_000,
                            }
                            # C2 — cache body counts across start packs for same N/patterns
                            _body_cache: Dict[
                                Tuple[Tuple[int, ...], Tuple[int, ...]],
                                Tuple[List[int], List[int]],
                            ] = {}
                            # Preset annual mean is phase/pat_map-independent — compute once
                            # per (rotation, N, length) instead of per candidate.
                            preset_avg_hours = (
                                None
                                if parsed_patterns
                                else _preset_avg_annual_hours(rot_key, int(n_off), float(length))
                            )
                            candidates: List[Tuple[float, Optional[List[int]], Optional[List[int]], bool]] = []
                            for ph in phase_layouts:
                                if _cancelled():
                                    break
                                for pm in pat_maps:
                                    cheap_evals += 1
                                    if cheap_evals % 250 == 0 or cheap_evals == 1:
                                        _progress(
                                            phase="cheap",
                                            done=cheap_evals,
                                            total=space_total or cheap_evals,
                                            full_sims=full_sims,
                                            message=(
                                                f"Cheap filter {cheap_evals:,}"
                                                + (f" / {space_total:,}" if space_total else "")
                                            ),
                                        )
                                    if parsed_patterns and ph is not None and pm is not None:
                                        bkey = (tuple(ph), tuple(pm))
                                        if bkey in _body_cache:
                                            day_counts, fri_sat = _body_cache[bkey]
                                        else:
                                            day_counts, fri_sat = _day_body_counts(
                                                parsed_patterns,
                                                ph,
                                                pm,
                                                n_slots=int(n_off),
                                                simulation_days=int(simulation_days),
                                                sim_start=sim_start,
                                            )
                                            _body_cache[bkey] = (day_counts, fri_sat)
                                        body_score = (min(day_counts) if day_counts else 0) * 1000 + (
                                            min(fri_sat) if fri_sat else 0
                                        ) * 100
                                        reason = _cheap_reject(
                                            parsed_patterns,
                                            ph,
                                            pm,
                                            n_slots=int(n_off),
                                            shift_length=float(length),
                                            annual_target=float(annual),
                                            annual_variance=float(annual_hours_variance),
                                            annual_hard=bool(annual_hours_hard),
                                            simulation_days=int(simulation_days),
                                            cov247=cov247,
                                            use_windows=bool(use_extra_windows and windows),
                                            window_min=window_min,
                                            n_bands=n_bands,
                                            min_ps=int(min_ps),
                                            sim_start=sim_start,
                                            shift_starts=starts,
                                            extra_windows=windows,
                                            precomputed=(day_counts, fri_sat),
                                            nearby_hops=nearby_hops,
                                            allow_offday_coverage=offday_ok,
                                        )
                                        if reason:
                                            pruned_cheap += 1
                                            fail_hist["cheap_reject"] += 1
                                            fail_hist[reason] = fail_hist.get(reason, 0) + 1
                                            if require_hard_ok:
                                                rejected_hard += 1
                                            cheap_score = body_score - float(_cheap_penalty.get(reason, 25_000))
                                            candidates.append((cheap_score, ph, pm, False))
                                        else:
                                            candidates.append((float(body_score), ph, pm, True))
                                    else:
                                        day_counts, fri_sat = _day_body_counts_preset(
                                            rot_key, int(n_off), int(simulation_days), sim_start
                                        )
                                        body_score = (min(day_counts) if day_counts else 0) * 1000 + (
                                            min(fri_sat) if fri_sat else 0
                                        ) * 100
                                        reason = _cheap_reject(
                                            None,
                                            None,
                                            None,
                                            n_slots=int(n_off),
                                            shift_length=float(length),
                                            annual_target=float(annual),
                                            annual_variance=float(annual_hours_variance),
                                            annual_hard=bool(annual_hours_hard),
                                            simulation_days=int(simulation_days),
                                            cov247=cov247,
                                            use_windows=bool(use_extra_windows and windows),
                                            window_min=window_min,
                                            n_bands=n_bands,
                                            min_ps=int(min_ps),
                                            sim_start=sim_start,
                                            shift_starts=starts,
                                            extra_windows=windows,
                                            precomputed=(day_counts, fri_sat),
                                            nearby_hops=nearby_hops,
                                            allow_offday_coverage=offday_ok,
                                            preset_avg_hours=preset_avg_hours,
                                        )
                                        if reason:
                                            pruned_cheap += 1
                                            fail_hist["cheap_reject"] += 1
                                            fail_hist[reason] = fail_hist.get(reason, 0) + 1
                                            if require_hard_ok:
                                                rejected_hard += 1
                                            cheap_score = body_score - float(_cheap_penalty.get(reason, 25_000))
                                            candidates.append((cheap_score, ph, pm, False))
                                        else:
                                            candidates.append((float(body_score), ph, pm, True))
                            if _cancelled():
                                break

                            # Built-in multi-block stagger heuristic (None overrides) —
                            # often the strongest layout; always evaluated.
                            if parsed_patterns and stagger_phases:
                                candidates.append((1e12, None, None, True))
                            if not candidates:
                                candidates.append((0.0, None, None, True))

                            candidates.sort(key=lambda x: -x[0])
                            # Full-sim queue: top cheap-pass + top cheap-fail for near-miss
                            full_queue: List[Tuple[float, Optional[List[int]], Optional[List[int]]]] = []
                            cheap_pass_kept = 0
                            cheap_fail_kept = 0
                            max_cheap_pass = 48
                            for cheap_score, ph, pm, passed in candidates:
                                if passed:
                                    if cheap_pass_kept < max_cheap_pass:
                                        full_queue.append((cheap_score, ph, pm))
                                        cheap_pass_kept += 1
                                elif cheap_fail_kept < 5:
                                    full_queue.append((cheap_score, ph, pm))
                                    cheap_fail_kept += 1

                            found_hard_structural = False
                            best_miss_row = None
                            best_miss_score = -1e18
                            rank_pool_remaining = 4
                            full_this_struct = 0
                            max_full_per_struct = 24
                            # C1 — parallel full-sims: threads default; process pool via env
                            use_proc = _OPT_PROCESS_WORKERS > 0
                            parallel_workers = _OPT_PROCESS_WORKERS if use_proc else _OPT_THREAD_WORKERS

                            def _cfg_dict(ph, pm) -> Dict[str, Any]:
                                return {
                                    "rotation_type": rot_key,
                                    "num_officers": int(n_off),
                                    "shift_length_hours": float(length),
                                    "annual_hours_target": float(annual),
                                    "shift_starts": list(starts),
                                    "apply_department_rules": False,
                                    "min_per_shift": int(min_ps),
                                    "simulation_days": int(simulation_days),
                                    "night_minimum": night_min,
                                    "annual_hours_variance": float(annual_hours_variance),
                                    "annual_hours_hard": bool(annual_hours_hard),
                                    "coverage_247": cov247,
                                    "avoid_flsa_overtime": bool(avoid_flsa_overtime),
                                    "flsa_work_period_days": int(flsa_work_period_days or 28),
                                    "use_extra_windows": bool(use_extra_windows and windows),
                                    "extra_windows": windows,
                                    "auto_min_officers": False,
                                    "rotation_style": use_style,
                                    "rotation_variations": list(variations),
                                    "stagger_phases": bool(stagger_phases) if ph is None else False,
                                    "phase_overrides": list(ph) if ph is not None else None,
                                    "pattern_slot_map": list(pm) if pm is not None else None,
                                    "flexible_daily_starts": False,
                                    "nearby_start_hops": nearby_hops,
                                    "allow_offday_coverage": offday_ok,
                                    "min_rest_hours": float(min_rest_hours),
                                    "max_consecutive_work_days": int(max_consecutive_work_days),
                                    "sim_start_date": sim_start,
                                }

                            def _run_one_full(ph, pm):
                                cfg = SimulatorConfig(**_cfg_dict(ph, pm))
                                sim = simulate_schedule(cfg)
                                return ph, pm, sim

                            class _SimProxy:
                                __slots__ = ("success", "metrics", "suggestions", "officer_slots")

                                def __init__(self, d: Dict[str, Any]):
                                    self.success = d.get("success")
                                    self.metrics = d.get("metrics") or {}
                                    self.suggestions = []
                                    self.officer_slots = d.get("officer_slots") or []

                            q_idx = 0
                            while q_idx < len(full_queue):
                                if _cancelled():
                                    break
                                if full_this_struct >= max_full_per_struct:
                                    break
                                if found_hard_structural and rank_pool_remaining <= 0:
                                    break
                                batch_n = min(
                                    parallel_workers,
                                    max_full_per_struct - full_this_struct,
                                    len(full_queue) - q_idx,
                                )
                                if found_hard_structural:
                                    batch_n = min(batch_n, max(1, rank_pool_remaining))
                                batch = full_queue[q_idx : q_idx + batch_n]
                                q_idx += batch_n
                                batch_out = []
                                if batch_n <= 1 or (not use_proc and parallel_workers <= 1):
                                    for _cs, ph, pm in batch:
                                        batch_out.append(_run_one_full(ph, pm))
                                elif use_proc:
                                    payloads = [
                                        {
                                            "ph": ph,
                                            "pm": pm,
                                            "cfg": _cfg_dict(ph, pm),
                                        }
                                        for _cs, ph, pm in batch
                                    ]
                                    try:
                                        with ProcessPoolExecutor(max_workers=batch_n) as pool:
                                            for d in pool.map(_full_sim_worker, payloads):
                                                batch_out.append(
                                                    (
                                                        d.get("ph"),
                                                        d.get("pm"),
                                                        _SimProxy(d),
                                                    )
                                                )
                                    except Exception:
                                        # Fallback serial if process pool fails (Windows)
                                        for _cs, ph, pm in batch:
                                            batch_out.append(_run_one_full(ph, pm))
                                else:
                                    with ThreadPoolExecutor(max_workers=batch_n) as pool:
                                        futs = [pool.submit(_run_one_full, ph, pm) for _cs, ph, pm in batch]
                                        for fut in as_completed(futs):
                                            try:
                                                batch_out.append(fut.result())
                                            except Exception:
                                                fail_hist["sim_fail"] += 1
                                for ph, pm, sim in batch_out:
                                    full_sims += 1
                                    full_this_struct += 1
                                    if full_sims == 1 or full_sims % 10 == 0:
                                        _progress(
                                            phase="full_sim",
                                            done=cheap_evals,
                                            total=space_total or cheap_evals,
                                            full_sims=full_sims,
                                            message=(
                                                f"Full sim {full_sims:,} · "
                                                f"cheap {cheap_evals:,}"
                                                + (f"/{space_total:,}" if space_total else "")
                                                + (f" · hard-OK {len(results)}" if results else "")
                                            ),
                                        )
                                    if not sim.success:
                                        fail_hist["sim_fail"] += 1
                                        continue
                                    m = sim.metrics or {}
                                    hard_ok = bool(m.get("hard_constraints_ok", True))
                                    row = _row_from_sim(
                                        sim=sim,
                                        rot_key=rot_key,
                                        n_off=n_off,
                                        min_ps=min_ps,
                                        length=length,
                                        starts=starts,
                                        use_style=use_style,
                                        variations=variations,
                                        ph=ph,
                                        pm=pm,
                                        hard_ok=hard_ok,
                                    )
                                    if _constraint_fail(
                                        m,
                                        require_hard_ok=require_hard_ok,
                                        avoid_flsa_overtime=avoid_flsa_overtime,
                                        cov247=cov247,
                                        use_extra_windows=bool(use_extra_windows and windows),
                                        windows=windows,
                                        annual_hours_hard=annual_hours_hard,
                                        min_ps=int(min_ps),
                                        min_rest_hours=float(min_rest_hours),
                                        max_consecutive_work_days=int(max_consecutive_work_days),
                                    ):
                                        rejected_hard += 1
                                        _record_fail(m)
                                        sc = float(row.get("score") or 0)
                                        if sc > best_miss_score:
                                            best_miss_score = sc
                                            best_miss_row = row
                                        continue
                                    results.append(row)
                                    if found_hard_structural:
                                        rank_pool_remaining -= 1
                                    else:
                                        found_hard_structural = True
                                        rank_pool_remaining = 4
                            if best_miss_row is not None and not found_hard_structural:
                                near_misses.append(best_miss_row)

                            # Expand to full phase model only when priority pass missed hard-OK
                            if (
                                parsed_patterns
                                and stagger_phases
                                and not found_hard_structural
                                and not _cancelled()
                                and not (require_hard_ok and len(results) >= max_hard_results)
                            ):
                                full_phases = generate_phase_layouts(int(n_off), cycle_len, mode="full")
                                seen_ph = {tuple(p) for p in phase_layouts if p is not None}
                                extra_phases = [p for p in full_phases if p is not None and tuple(p) not in seen_ph]
                                if extra_phases:
                                    phase_layouts = extra_phases
                                    candidates = []
                                    for ph in phase_layouts:
                                        if _cancelled():
                                            break
                                        for pm in pat_maps:
                                            cheap_evals += 1
                                            if cheap_evals % 250 == 0:
                                                _progress(
                                                    phase="cheap_expand",
                                                    done=cheap_evals,
                                                    total=space_total or cheap_evals,
                                                    full_sims=full_sims,
                                                    message=(f"Expand phases {cheap_evals:,}"),
                                                )
                                            if ph is not None and pm is not None:
                                                day_counts, fri_sat = _day_body_counts(
                                                    parsed_patterns,
                                                    ph,
                                                    pm,
                                                    n_slots=int(n_off),
                                                    simulation_days=int(simulation_days),
                                                    sim_start=sim_start,
                                                )
                                                body_score = (min(day_counts) if day_counts else 0) * 1000 + (
                                                    min(fri_sat) if fri_sat else 0
                                                ) * 100
                                                reason = _cheap_reject(
                                                    parsed_patterns,
                                                    ph,
                                                    pm,
                                                    n_slots=int(n_off),
                                                    shift_length=float(length),
                                                    annual_target=float(annual),
                                                    annual_variance=float(annual_hours_variance),
                                                    annual_hard=bool(annual_hours_hard),
                                                    simulation_days=int(simulation_days),
                                                    cov247=cov247,
                                                    use_windows=bool(use_extra_windows and windows),
                                                    window_min=window_min,
                                                    n_bands=n_bands,
                                                    min_ps=int(min_ps),
                                                    sim_start=sim_start,
                                                    shift_starts=starts,
                                                    extra_windows=windows,
                                                    precomputed=(
                                                        day_counts,
                                                        fri_sat,
                                                    ),
                                                )
                                                if reason:
                                                    pruned_cheap += 1
                                                    fail_hist["cheap_reject"] += 1
                                                    fail_hist[reason] = fail_hist.get(reason, 0) + 1
                                                    if require_hard_ok:
                                                        rejected_hard += 1
                                                    cheap_score = body_score - float(_cheap_penalty.get(reason, 25_000))
                                                    candidates.append((cheap_score, ph, pm, False))
                                                else:
                                                    candidates.append(
                                                        (
                                                            float(body_score),
                                                            ph,
                                                            pm,
                                                            True,
                                                        )
                                                    )
                                    candidates.sort(key=lambda x: -x[0])
                                    full_queue = []
                                    cheap_pass_kept = 0
                                    cheap_fail_kept = 0
                                    for cheap_score, ph, pm, passed in candidates:
                                        if passed and cheap_pass_kept < max_cheap_pass:
                                            full_queue.append((cheap_score, ph, pm))
                                            cheap_pass_kept += 1
                                        elif not passed and cheap_fail_kept < 5:
                                            full_queue.append((cheap_score, ph, pm))
                                            cheap_fail_kept += 1
                                    rank_pool_remaining = 4
                                    full_this_struct = 0
                                    for cheap_score, ph, pm in full_queue:
                                        if _cancelled():
                                            break
                                        if full_this_struct >= max_full_per_struct:
                                            break
                                        if found_hard_structural and rank_pool_remaining <= 0:
                                            break
                                        cfg = SimulatorConfig(
                                            rotation_type=rot_key,
                                            num_officers=int(n_off),
                                            shift_length_hours=float(length),
                                            annual_hours_target=float(annual),
                                            shift_starts=list(starts),
                                            apply_department_rules=False,
                                            min_per_shift=int(min_ps),
                                            simulation_days=int(simulation_days),
                                            night_minimum=night_min,
                                            annual_hours_variance=float(annual_hours_variance),
                                            annual_hours_hard=bool(annual_hours_hard),
                                            coverage_247=cov247,
                                            avoid_flsa_overtime=bool(avoid_flsa_overtime),
                                            flsa_work_period_days=int(flsa_work_period_days or 28),
                                            use_extra_windows=bool(use_extra_windows and windows),
                                            extra_windows=windows,
                                            auto_min_officers=False,
                                            rotation_style=use_style,
                                            rotation_variations=list(variations),
                                            stagger_phases=False,
                                            phase_overrides=list(ph) if ph is not None else None,
                                            pattern_slot_map=list(pm) if pm is not None else None,
                                            flexible_daily_starts=False,
                                            nearby_start_hops=nearby_hops,
                                            allow_offday_coverage=offday_ok,
                                            min_rest_hours=float(min_rest_hours),
                                            max_consecutive_work_days=int(max_consecutive_work_days),
                                            sim_start_date=sim_start,
                                        )
                                        sim = simulate_schedule(cfg)
                                        full_sims += 1
                                        full_this_struct += 1
                                        if not sim.success:
                                            fail_hist["sim_fail"] += 1
                                            continue
                                        m = sim.metrics or {}
                                        hard_ok = bool(m.get("hard_constraints_ok", True))
                                        row = _row_from_sim(
                                            sim=sim,
                                            rot_key=rot_key,
                                            n_off=n_off,
                                            min_ps=min_ps,
                                            length=length,
                                            starts=starts,
                                            use_style=use_style,
                                            variations=variations,
                                            ph=ph,
                                            pm=pm,
                                            hard_ok=hard_ok,
                                        )
                                        if _constraint_fail(
                                            m,
                                            require_hard_ok=require_hard_ok,
                                            avoid_flsa_overtime=avoid_flsa_overtime,
                                            cov247=cov247,
                                            use_extra_windows=bool(use_extra_windows and windows),
                                            windows=windows,
                                            annual_hours_hard=annual_hours_hard,
                                            min_ps=int(min_ps),
                                            min_rest_hours=float(min_rest_hours),
                                            max_consecutive_work_days=int(max_consecutive_work_days),
                                        ):
                                            rejected_hard += 1
                                            _record_fail(m)
                                            sc = float(row.get("score") or 0)
                                            if sc > best_miss_score:
                                                best_miss_score = sc
                                                best_miss_row = row
                                            continue
                                        results.append(row)
                                        if found_hard_structural:
                                            rank_pool_remaining -= 1
                                        else:
                                            found_hard_structural = True
                                            rank_pool_remaining = 4
                                    if best_miss_row is not None and not found_hard_structural:
                                        near_misses.append(best_miss_row)
                    if _cancelled():
                        break
                if _cancelled():
                    break
            if _cancelled():
                break
        if _cancelled():
            break
    # rotation loop ends above

    results.sort(key=lambda r: (0 if r.get("hard_constraints_ok") else 1, -r["score"]))
    near_misses.sort(key=lambda r: -r["score"])

    def _dedupe(rows: List[Dict]) -> List[Dict]:
        out: List[Dict] = []
        seen = set()
        for row in rows:
            ph = row.get("phase_overrides")
            pm = row.get("pattern_slot_map")
            sk = (
                row["rotation_type"],
                row["num_officers"],
                row["min_per_shift"],
                row["shift_length_hours"],
                tuple(row.get("shift_starts") or []),
                tuple(row.get("rotation_variations") or []),
                tuple(ph) if isinstance(ph, (list, tuple)) else ph,
                tuple(pm) if isinstance(pm, (list, tuple)) else pm,
                tuple(row.get("failed_constraints") or []),
            )
            if sk in seen:
                continue
            seen.add(sk)
            out.append(row)
        return out

    results = diversify_ranked(_dedupe(results), limit=24)
    near_misses = _dedupe(near_misses)[:20]

    def _finalize(rows: List[Dict], *, near: bool = False) -> None:
        for i, row in enumerate(rows, 1):
            m = row.get("metrics") or {}
            zero_gaps = int(
                m.get("gap_events")
                if m.get("gap_events") is not None
                else (m.get("zero_staff_slots") or m.get("coverage_gap_count") or 0)
            )
            night_fails = int(m.get("night_minimum_failures") or m.get("night_risk_gaps") or 0)
            flsa_fails = int(m.get("flsa_violations") or 0)
            win_fails = int(m.get("extra_window_failures") or 0)
            c247_fails = int(m.get("coverage_247_failures") or 0)
            hours_delta = abs(float(m.get("avg_annual_hours") or annual) - annual)
            spread = float(m.get("annual_hours_spread") or 0)
            row["rank"] = i
            bits = [
                str(row["rotation_type"]),
                f"{row['num_officers']} Officers",
                f"Min {row['min_per_shift']} Per Shift",
            ]
            if near and row.get("failed_constraints"):
                labels = [CONSTRAINT_LABELS.get(k, k) for k in row["failed_constraints"]]
                bits.append("Misses: " + ", ".join(labels))
            if zero_gaps:
                bits.append(f"Coverage Gaps {zero_gaps}")
            if night_fails:
                bits.append(f"Night Short {night_fails}")
            if flsa_fails:
                bits.append(f"FLSA Over Cap {flsa_fails}")
            if win_fails:
                bits.append(f"Window Short {win_fails}")
            if c247_fails:
                bits.append(f"24/7 Short {c247_fails}")
            if hours_delta >= 1:
                bits.append(f"Annual Mean Off ~{hours_delta:.0f}h")
            if spread >= 1:
                bits.append(f"Officer Hours Spread ~{spread:.0f}h")
            if not near and not zero_gaps and row.get("hard_constraints_ok"):
                bits.append("Meets Selected Constraints")
            row["summary"] = " · ".join(bits)
            row["_internal_score"] = row.pop("score", None)
            row["human_metrics"] = {
                "zero_staff_gaps": zero_gaps,
                "night_minimum_failures": night_fails,
                "flsa_violations": flsa_fails,
                "extra_window_failures": win_fails,
                "coverage_247_failures": c247_fails,
                "annual_hours_delta": round(hours_delta, 1),
                "annual_hours_spread": round(spread, 1),
                "num_officers": row["num_officers"],
                "min_per_shift": row["min_per_shift"],
                "rotation_type": row["rotation_type"],
                "hard_constraints_ok": row.get("hard_constraints_ok"),
                "failed_constraints": list(row.get("failed_constraints") or []),
            }

    _finalize(results)
    _finalize(near_misses, near=True)

    # Cost / FLSA / fairness meters on ranked + near-miss cards
    try:
        from logic.staffing_insights import enrich_ranked_economics

        results = enrich_ranked_economics(results)
        near_misses = enrich_ranked_economics(near_misses)
    except Exception:
        pass

    wall_ms = int((time.perf_counter() - t0) * 1000)
    total_eval = cheap_evals
    best = results[0] if results else None
    search_exhaustive = bool(not cancelled and not budget_exhausted)
    search_status = _derive_search_status(
        cancelled=bool(cancelled),
        has_verified_result=bool(best),
        search_exhaustive=search_exhaustive,
    )

    if budget_exhausted:
        msg = f"Time Budget Reached ({int(_budget or 0)}s) · {total_eval:,} Cheap Checks · {full_sims:,} Full Sims"
        if best:
            msg += (
                f" — Best So Far: {best['rotation_type']} · "
                f"{best['num_officers']} Officers · Min {best['min_per_shift']} Per Shift"
            )
        else:
            msg += " — No Qualifying Option Found Yet (lock more constraints or raise the budget)"
    elif cancelled:
        msg = f"Search Cancelled After {total_eval:,} Cheap Checks · {full_sims:,} Full Sims"
        if best:
            msg += (
                f" — Best So Far: {best['rotation_type']} · "
                f"{best['num_officers']} Officers · Min {best['min_per_shift']} Per Shift"
            )
    elif best:
        msg = (
            f"Best Option: {best['rotation_type']} · {best['num_officers']} Officers · "
            f"Min {best['min_per_shift']} Per Shift"
        )
    elif near_misses:
        msg = (
            "No Schedule Meets Every Hard Constraint — "
            f"showing {len(near_misses)} closest alternative(s). "
            "Adjust constraint priorities and search again."
        )
    else:
        msg = "No Schedule Meets The Selected Hard Constraints"
    if rejected_hard and best and not cancelled:
        msg += f" · {rejected_hard} Ruled Out By Hard Constraints"
    elif rejected_hard and not best:
        msg += f" ({rejected_hard} Combinations Ruled Out)"

    if require_hard_ok:
        success = bool(results)
        grouped = {}
        for r in results:
            # Group by (rotation_type, num_officers, shift_length) so different N
            # values for the same rotation type both surface in the ranked list.
            gk = (r["rotation_type"], r["num_officers"], r["shift_length_hours"])
            if gk not in grouped:
                grouped[gk] = r
        ranked = list(grouped.values())[:15]
        best_out = best
    else:
        source_list = results if results else near_misses
        grouped = {}
        for r in source_list:
            gk = (r["rotation_type"], r["num_officers"], r["shift_length_hours"])
            if gk not in grouped:
                grouped[gk] = r
        ranked = list(grouped.values())[:15]
        best_out = ranked[0] if ranked else None
        success = bool(best_out)

    _progress(
        phase="done",
        done=total_eval,
        total=space_total or total_eval,
        full_sims=full_sims,
        message=msg,
        success=success,
        cancelled=cancelled,
    )

    return {
        "success": success,
        "cancelled": cancelled,
        "scenarios_evaluated": total_eval,
        "scenarios_kept": len(results),
        "rejected_hard_constraints": rejected_hard,
        "outer_configs": outer_configs,
        "inner_trials": total_eval,
        "full_sims_run": full_sims,
        "pruned_cheap": pruned_cheap,
        "status": search_status,
        "search_exhaustive": search_exhaustive,
        "budget_exhausted": budget_exhausted,
        "wall_time_ms": wall_ms,
        "failure_histogram": fail_hist,
        "space_estimate": space,
        "space_note": space.get("warning") or "",
        "constraint_weights": weights,
        "constraint_priority": list(constraint_priority or []),
        "input_roles": normalized_input_roles,
        "near_misses": near_misses,
        "best": best_out,
        "ranked": ranked,
        "message": msg,
        "solver_status": (
            "feasible_time_limited"
            if best and (cancelled or budget_exhausted)
            else "feasible_search_complete"
            if best
            else "unknown_time_limited"
            if budget_exhausted
            else "cancelled"
            if cancelled
            else "proven_infeasible"
            if require_hard_ok and not results
            else "unknown"
        ),
        # A cancelled/budget-stopped search proves nothing about infeasibility —
        # only a completed sweep may claim impossible (soundness rule).
        "impossible": require_hard_ok and search_status == "INFEASIBLE",
        "constraints_applied": {
            "coverage_247": cov247,
            "avoid_flsa_overtime": bool(avoid_flsa_overtime),
            "use_extra_windows": bool(use_extra_windows and windows),
            "extra_window_count": len(windows) if use_extra_windows else 0,
            "simulation_days": int(simulation_days),
            "rotation_types": list(axes["rotation_types"]),
            "officer_counts": list(axes["officer_counts"]),
            "min_per_shift_options": list(axes["min_per_shift_options"]),
            "shift_starts_options": axes["locked_starts_opts"]
            if axes["locked_starts_opts"] is not None
            else ["<all modeled packs for free starts>"],
            "shift_length_options": axes["length_opts"],
            "rotation_style": style,
            "rotation_variations": list(axes["base_variations"]),
            "variation_sets": len(axes["variation_sets"]),
            "annual_hours_target": annual,
            "search_mode": "exhaustive",
            "constraint_weights": weights,
            "input_roles": normalized_input_roles,
        },
    }
