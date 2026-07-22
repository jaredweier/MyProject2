"""
CP-SAT replacement for the phase-offset x pattern-variant search inside
logic.staffing_optimizer.optimize_staffing_scenarios.

Scope (first slice — see docs/NEXT_SESSION_BRIEF.md "start with 1"):
  Decides, per officer, which rotation variant (e.g. "6-2,5-3" vs "6-3,5-2")
  and which cycle phase offset they use, to satisfy:
    - day-level 24/7 minimum coverage (coverage_247)
    - annual-hours target/variance, checked as roster average (matches
      existing optimize_staffing_scenarios semantics)
    - max consecutive on-duty days (fatigue cap), if set
  This replaces logic.staffing_optimizer.generate_phase_layouts() x
  generate_pattern_maps() — the itertools.combinations enumeration that
  caused the false-impossible bug and multi-hour brute-force runs.

  NOT modeled here (falls back to the old exhaustive path when present):
    - minute-level extra windows (Fri/Sat 19-03 etc.) — still verified by
      simulate_schedule()'s exact sweep-line check after CP-SAT hands back
      a candidate, same as today.
    - shift-start pool balancing — untouched, still simulator.py's job.
    - min_rest_hours tighter than the fixed daily rest floor (24 - shift
      length) — that needs per-day start-pool awareness this slice doesn't
      have. Returns status="unsupported" so the caller falls back safely
      instead of silently approving something unverified.

  Infeasible here is a mathematical proof (CP-SAT), not a heuristic guess —
  the caller can trust it and skip the exhaustive fallback entirely.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence

from logic.rotation_patterns import RotationPattern, projected_annual_hours


def ortools_available() -> bool:
    try:
        from ortools.sat.python import cp_model  # noqa: F401

        return True
    except ImportError:
        return False


def _max_cyclic_run(duty: Sequence[bool]) -> int:
    """Longest run of True in duty, allowing wraparound (cyclic)."""
    n = len(duty)
    if n == 0:
        return 0
    if all(duty):
        return n
    doubled = list(duty) + list(duty)
    best = 0
    run = 0
    for v in doubled[: n + max(1, n - 1)]:
        if v:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return min(best, n)


def solve_phase_variant(
    patterns: Sequence[RotationPattern],
    *,
    n_officers: int,
    shift_length_hours: float,
    coverage_247: int = 0,
    annual_hours_target: Optional[float] = None,
    annual_hours_variance: float = 40.0,
    annual_hours_hard: bool = False,
    max_consecutive_work_days: int = 0,
    min_rest_hours: float = 0.0,
    time_limit_sec: float = 8.0,
) -> Dict:
    """Return one of:
    {"status": "unavailable"}                     — ortools not installed
    {"status": "unsupported", "reason": str}       — outside this slice's model
    {"status": "infeasible", "reason": str}        — proven, no fallback needed
    {"status": "feasible", "phase": [...], "pattern_map": [...]}
    {"status": "error", "reason": str}             — model build failed; fall back
    """
    if not ortools_available():
        return {"status": "unavailable"}
    if not patterns or n_officers < 1:
        return {"status": "unsupported", "reason": "no patterns or officers"}

    cycle_len = patterns[0].cycle_length
    if cycle_len < 1 or any(p.cycle_length != cycle_len for p in patterns):
        return {"status": "unsupported", "reason": "variation set cycle-length mismatch"}
    if cycle_len > 60:
        # Model size (n_officers * n_variants * cycle_len bools) grows with
        # this; the old exhaustive path is already the fallback for exotic
        # long cycles that rarely occur in practice.
        return {"status": "unsupported", "reason": f"cycle length {cycle_len} too large for this slice"}

    rest_floor = 24.0 - float(shift_length_hours)
    if min_rest_hours and float(min_rest_hours) > rest_floor + 1e-9:
        return {
            "status": "unsupported",
            "reason": (
                f"min_rest_hours={min_rest_hours} exceeds fixed daily rest floor "
                f"({rest_floor}h) — needs start-pool awareness this slice doesn't model"
            ),
        }

    duty_vectors = [p.duty_vector() for p in patterns]

    allowed_variants: List[int] = []
    for vi, duty in enumerate(duty_vectors):
        if max_consecutive_work_days and max_consecutive_work_days > 0:
            if _max_cyclic_run(duty) > int(max_consecutive_work_days):
                continue
        allowed_variants.append(vi)
    if not allowed_variants:
        return {
            "status": "infeasible",
            "reason": f"every rotation variant exceeds max_consecutive_work_days={max_consecutive_work_days}",
        }

    annual10 = {vi: round(projected_annual_hours(patterns[vi], shift_length_hours) * 10) for vi in allowed_variants}

    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    officers = range(int(n_officers))

    # x[o, v, p] = 1 if officer o uses variant v at phase p
    x: Dict[tuple, "cp_model.IntVar"] = {}
    for o in officers:
        for v in allowed_variants:
            for p in range(cycle_len):
                x[(o, v, p)] = model.NewBoolVar(f"x_{o}_{v}_{p}")
        model.Add(sum(x[(o, v, p)] for v in allowed_variants for p in range(cycle_len)) == 1)

    # Day-level 24/7 coverage (periodic over one cycle)
    if coverage_247 and coverage_247 > 0:
        # A calendar-day headcount of coverage_247 does NOT imply minute-level
        # continuous coverage — an officer's fixed-length shift only spans
        # shift_length_hours of the day. The real necessary minimum to have
        # coverage_247 people simultaneously on duty at every instant, using
        # fixed shift_length_hours blocks, is coverage_247 * ceil(24/L)
        # distinct on-duty officers that day (a lower bound; sufficiency
        # still depends on the shift-start pool stagger simulate_schedule
        # does downstream — verified there, not here).
        per_day_min = int(coverage_247) * math.ceil(24.0 / float(shift_length_hours))
        for d in range(cycle_len):
            terms = []
            for o in officers:
                for v in allowed_variants:
                    duty = duty_vectors[v]
                    for p in range(cycle_len):
                        if duty[(d - p) % cycle_len]:
                            terms.append(x[(o, v, p)])
            if not terms:
                return {
                    "status": "infeasible",
                    "reason": f"no variant/phase combination covers cycle-day {d}",
                }
            model.Add(sum(terms) >= per_day_min)

    # Annual-hours roster average, hard band
    if annual_hours_hard and annual_hours_target is not None:
        y: Dict[tuple, "cp_model.IntVar"] = {}
        for o in officers:
            for v in allowed_variants:
                yv = model.NewIntVar(0, 1, f"y_{o}_{v}")
                model.Add(yv == sum(x[(o, v, p)] for p in range(cycle_len)))
                y[(o, v)] = yv
        total10 = sum(annual10[v] * y[(o, v)] for o in officers for v in allowed_variants)
        n = int(n_officers)
        band = float(annual_hours_variance or 0.0)
        target = float(annual_hours_target)
        lo10 = math.ceil(n * (target - band) * 10 - 1e-6)
        hi10 = math.floor(n * (target + band) * 10 + 1e-6)
        if lo10 > hi10:
            return {"status": "infeasible", "reason": "annual-hours band is empty (variance too tight)"}
        model.Add(total10 >= lo10)
        model.Add(total10 <= hi10)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_sec)
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)

    if status == cp_model.INFEASIBLE:
        return {
            "status": "infeasible",
            "reason": "CP-SAT proved no phase/variant assignment satisfies 24/7 coverage + annual-hours band together",
        }
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"status": "error", "reason": f"CP-SAT status={solver.StatusName(status)} (timeout or unknown)"}

    phase: List[int] = [0] * int(n_officers)
    pattern_map: List[int] = [0] * int(n_officers)
    for o in officers:
        for v in allowed_variants:
            for p in range(cycle_len):
                if solver.Value(x[(o, v, p)]) == 1:
                    phase[o] = p
                    pattern_map[o] = v
                    break
            else:
                continue
            break

    return {"status": "feasible", "phase": phase, "pattern_map": pattern_map}


def _parse_hhmm(value: str) -> int:
    parts = (value or "").strip().split(":")
    return int(parts[0]) * 60 + int(parts[1])


def solve_full_assignment(
    patterns: Sequence[RotationPattern],
    *,
    n_officers: int,
    shift_length_hours: float,
    candidate_starts: Sequence[str],
    sim_start_date: date,
    coverage_247: int = 0,
    extra_windows: Optional[List[Dict]] = None,
    annual_hours_target: Optional[float] = None,
    annual_hours_variance: float = 40.0,
    annual_hours_hard: bool = False,
    max_consecutive_work_days: int = 0,
    min_rest_hours: float = 0.0,
    max_horizon_days: int = 140,
    time_limit_sec: float = 20.0,
) -> Dict:
    """Owns variant + phase + shift-start together, so it can verify minute-
    level 24/7 and extra-window coverage itself (30-minute bins) instead of
    handing a candidate to simulate_schedule() and hoping. Replaces the
    phase x pattern-map x start-pack search entirely for scenarios it
    supports.

    Horizon: one full LCM(cycle_length, 7) days so the periodic pattern and
    the 7-day weekday cycle both close exactly — required for infeasible to
    be a sound proof (a window tied to "Friday" needs every phase's Friday
    represented, not just an arbitrary truncated slice). If that LCM exceeds
    max_horizon_days, returns status="unsupported" rather than truncating
    and silently weakening the proof.

    Only weekday-anchored extra_windows are modeled (the documented
    Fri/Sat-night case). A window pinned to one specific_date is a one-off,
    not periodic, and doesn't fit this model — status="unsupported" if any
    are present, so the caller falls back to the exact-but-slower path.
    """
    if not ortools_available():
        return {"status": "unavailable"}
    if not patterns or n_officers < 1 or not candidate_starts:
        return {"status": "unsupported", "reason": "no patterns, officers, or candidate starts"}

    windows = list(extra_windows or [])
    for w in windows:
        if isinstance(w, dict) and (w.get("specific_date") or w.get("date")):
            return {"status": "unsupported", "reason": "specific-date window — not periodic, needs exact-path check"}

    cycle_len = patterns[0].cycle_length
    if cycle_len < 1 or any(p.cycle_length != cycle_len for p in patterns):
        return {"status": "unsupported", "reason": "variation set cycle-length mismatch"}

    horizon = cycle_len * 7 // math.gcd(cycle_len, 7)
    if horizon > max_horizon_days:
        return {"status": "unsupported", "reason": f"LCM({cycle_len},7)={horizon}d exceeds cap {max_horizon_days}d"}

    rest_floor = 24.0 - float(shift_length_hours)
    if min_rest_hours and float(min_rest_hours) > rest_floor + 1e-9:
        return {
            "status": "unsupported",
            "reason": f"min_rest_hours={min_rest_hours} exceeds fixed daily rest floor ({rest_floor}h)",
        }

    duty_vectors = [p.duty_vector() for p in patterns]
    allowed_variants: List[int] = []
    for vi, duty in enumerate(duty_vectors):
        if max_consecutive_work_days and max_consecutive_work_days > 0:
            if _max_cyclic_run(duty) > int(max_consecutive_work_days):
                continue
        allowed_variants.append(vi)
    if not allowed_variants:
        return {
            "status": "infeasible",
            "reason": f"every rotation variant exceeds max_consecutive_work_days={max_consecutive_work_days}",
        }

    annual10 = {vi: round(projected_annual_hours(patterns[vi], shift_length_hours) * 10) for vi in allowed_variants}

    bins_per_day = 48  # 30-minute grid
    total_bins = horizon * bins_per_day
    shift_bins = round(float(shift_length_hours) * 2)
    starts = [s for s in candidate_starts if s]
    start_bins = [round(_parse_hhmm(s) / 30) for s in starts]

    # required[bin] = max hard-minimum headcount at that instant
    required = [0] * total_bins
    if coverage_247 and coverage_247 > 0:
        for b in range(total_bins):
            required[b] = int(coverage_247)
    for w in windows:
        if not isinstance(w, dict) or not w.get("enabled", True):
            continue
        wd = w.get("weekday")
        if wd is None or wd == "":
            continue
        mn = int(w.get("min_officers") or w.get("min") or 0)
        if mn <= 0:
            continue
        try:
            w_start = round(_parse_hhmm(w.get("start_time") or w.get("start") or "0:00") / 30)
            w_end = round(_parse_hhmm(w.get("end_time") or w.get("end") or "0:00") / 30)
        except (ValueError, IndexError):
            continue
        span = (w_end - w_start) if w_end > w_start else (bins_per_day - w_start + w_end)
        for day in range(horizon):
            if (sim_start_date + timedelta(days=day)).weekday() != int(wd):
                continue
            base = day * bins_per_day + w_start
            for k in range(span):
                b = (base + k) % total_bins
                required[b] = max(required[b], mn)

    if not any(required):
        return {"status": "unsupported", "reason": "no hard coverage requirement to model (nothing to solve)"}

    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    officers = range(int(n_officers))

    # Per-officer choice keys and the bins each (v, p, s) combo covers.
    choice_keys = [(v, p, si) for v in allowed_variants for p in range(cycle_len) for si in range(len(starts))]
    covers: Dict[tuple, List[int]] = {}
    for v, p, si in choice_keys:
        duty = duty_vectors[v]
        sb = start_bins[si]
        bins: List[int] = []
        for day in range(horizon):
            if not duty[(day - p) % cycle_len]:
                continue
            base = day * bins_per_day + sb
            for k in range(shift_bins):
                bins.append((base + k) % total_bins)
        covers[(v, p, si)] = bins

    x: Dict[tuple, "cp_model.IntVar"] = {}
    bin_contributors: List[List[tuple]] = [[] for _ in range(total_bins)]
    for o in officers:
        for key in choice_keys:
            x[(o, *key)] = model.NewBoolVar(f"x_{o}_{key[0]}_{key[1]}_{key[2]}")
        model.Add(sum(x[(o, *key)] for key in choice_keys) == 1)
    for key in choice_keys:
        for b in covers[key]:
            bin_contributors[b].append(key)

    for b in range(total_bins):
        if required[b] <= 0:
            continue
        terms = [x[(o, *key)] for o in officers for key in bin_contributors[b]]
        if not terms:
            return {"status": "infeasible", "reason": f"no (variant, phase, start) combination covers bin {b}"}
        model.Add(sum(terms) >= required[b])

    if annual_hours_hard and annual_hours_target is not None:
        y: Dict[tuple, "cp_model.IntVar"] = {}
        for o in officers:
            for v in allowed_variants:
                yv = model.NewIntVar(0, 1, f"y_{o}_{v}")
                model.Add(yv == sum(x[(o, v, p, si)] for p in range(cycle_len) for si in range(len(starts))))
                y[(o, v)] = yv
        total10 = sum(annual10[v] * y[(o, v)] for o in officers for v in allowed_variants)
        n = int(n_officers)
        band = float(annual_hours_variance or 0.0)
        target = float(annual_hours_target)
        lo10 = math.ceil(n * (target - band) * 10 - 1e-6)
        hi10 = math.floor(n * (target + band) * 10 + 1e-6)
        if lo10 > hi10:
            return {"status": "infeasible", "reason": "annual-hours band is empty (variance too tight)"}
        model.Add(total10 >= lo10)
        model.Add(total10 <= hi10)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_sec)
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)

    if status == cp_model.INFEASIBLE:
        return {
            "status": "infeasible",
            "reason": (
                "CP-SAT proved no (variant, phase, start) assignment satisfies 24/7 + window "
                "coverage + annual-hours band together, over a full LCM(cycle,7)-day horizon"
            ),
        }
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"status": "error", "reason": f"CP-SAT status={solver.StatusName(status)} (timeout or unknown)"}

    phase: List[int] = [0] * int(n_officers)
    pattern_map: List[int] = [0] * int(n_officers)
    shift_starts_out: List[str] = [""] * int(n_officers)
    for o in officers:
        for key in choice_keys:
            if solver.Value(x[(o, *key)]) == 1:
                v, p, si = key
                phase[o] = p
                pattern_map[o] = v
                shift_starts_out[o] = starts[si]
                break

    return {
        "status": "feasible",
        "phase": phase,
        "pattern_map": pattern_map,
        "shift_starts_per_officer": shift_starts_out,
    }
