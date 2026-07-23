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
from typing import Dict, List, Optional, Sequence, Tuple

from logic.rotation_patterns import RotationPattern, projected_annual_hours


def lexicographic_coefficients(ordered_bounds: Sequence[Tuple[str, int]]) -> Dict[str, int]:
    """Make each earlier bounded integer objective dominate every later objective."""
    coefficients: Dict[str, int] = {}
    scale = 1
    for name, bound in reversed(list(ordered_bounds)):
        coefficients[name] = scale
        scale *= max(0, int(bound)) + 1
    return coefficients


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
    {"status": "unknown", "reason": str}           — timeout/unknown; fall back
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
        return {
            "status": "unknown",
            "solver_status": "unknown_or_time_limited",
            "reason": f"CP-SAT status={solver.StatusName(status)} (timeout or unknown)",
        }

    phase: List[int] = [0] * int(n_officers)
    pattern_map: List[int] = [0] * int(n_officers)
    for o in officers:
        for v in allowed_variants:
            for p in range(cycle_len):
                if solver.Value(x[(o, v, p)]) == 1:
                    # The model indexes duty as (day - p); RotationPattern
                    # replays it as (day + phase). Translate between the two
                    # conventions before handing the assignment downstream.
                    phase[o] = (-p) % cycle_len
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
    max_solutions: int = 1,
    pool_time_limit_sec: float = 45.0,
    progress_callback=None,
    warm_start: Optional[Dict] = None,
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

    Objective (P1.1): when annual_hours_target is set, minimizes total
    per-officer |projected annual - target| — the solver prefers the fairest
    variant mix, not just any feasible one. Without a target it's pure
    feasibility (unchanged).

    Solution pool (P1.2): max_solutions > 1 returns up to that many
    structurally distinct solutions in "solutions" (each later solution is
    the best remaining after excluding earlier aggregate assignment
    profiles — officer permutations of a known solution don't count as new).
    Soundness: only the FIRST solve's INFEASIBLE is a proof about the
    problem; infeasibility after exclusion cuts just means the pool is
    exhausted.
    """
    if not ortools_available():
        return {"status": "unavailable"}
    if not patterns or n_officers < 1 or not candidate_starts:
        return {"status": "unsupported", "reason": "no patterns, officers, or candidate starts"}

    windows = list(extra_windows or [])

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
        mn = int(w.get("min_officers") or w.get("min") or 0)
        if mn <= 0:
            continue
        try:
            w_start = round(_parse_hhmm(w.get("start_time") or w.get("start") or "0:00") / 30)
            w_end = round(_parse_hhmm(w.get("end_time") or w.get("end") or "0:00") / 30)
        except (ValueError, IndexError):
            continue
        span = (w_end - w_start) if w_end > w_start else (bins_per_day - w_start + w_end)
        specific = w.get("specific_date") or w.get("date")
        if specific:
            if isinstance(specific, str):
                try:
                    specific = date.fromisoformat(specific)
                except ValueError:
                    continue
            offset_days = (specific - sim_start_date).days
            if 0 <= offset_days < horizon:
                base = offset_days * bins_per_day + w_start
                for k in range(span):
                    b = (base + k) % total_bins
                    required[b] = max(required[b], mn)
            continue
        wd = w.get("weekday")
        if wd is None or wd == "":
            continue
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
    # Officers are interchangeable here. Canonical nondecreasing choice
    # indices remove officer-renamed copies without removing real schedules.
    chosen_index = []
    for o in officers:
        idx = model.NewIntVar(0, len(choice_keys) - 1, f"choice_index_{o}")
        model.Add(idx == sum(i * x[(o, *key)] for i, key in enumerate(choice_keys)))
        chosen_index.append(idx)
    for o in range(int(n_officers) - 1):
        model.Add(chosen_index[o] <= chosen_index[o + 1])
    hint_phases = (warm_start or {}).get("phase") or []
    hint_patterns = (warm_start or {}).get("pattern_map") or []
    hint_starts = (
        (warm_start or {}).get("shift_starts_per_officer") or (warm_start or {}).get("officer_home_starts") or []
    )
    for o in officers:
        if o >= len(hint_phases) or o >= len(hint_patterns) or o >= len(hint_starts):
            continue
        try:
            key = (int(hint_patterns[o]), (-int(hint_phases[o])) % cycle_len, starts.index(hint_starts[o]))
        except (ValueError, TypeError):
            continue
        if key in choice_keys:
            model.AddHint(x[(o, *key)], 1)
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

    y: Dict[tuple, "cp_model.IntVar"] = {}
    if annual_hours_target is not None:
        for o in officers:
            for v in allowed_variants:
                yv = model.NewIntVar(0, 1, f"y_{o}_{v}")
                model.Add(yv == sum(x[(o, v, p, si)] for p in range(cycle_len) for si in range(len(starts))))
                y[(o, v)] = yv
    if annual_hours_hard and annual_hours_target is not None:
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

    # P1.1 objective: fairest variant mix — minimize total per-officer
    # deviation from the annual target (deci-hours). Pure feasibility when
    # no target is set.
    if annual_hours_target is not None:
        target10 = round(float(annual_hours_target) * 10)
        dev10 = {v: abs(annual10[v] - target10) for v in allowed_variants}
        model.Minimize(sum(dev10[v] * y[(o, v)] for o in officers for v in allowed_variants))

    # P1.2 pool machinery: aggregate profile counts per (variant, phase,
    # start) key — exclusion cuts on these, not on per-officer assignments,
    # so officer permutations of a found solution don't come back as "new".
    n_int = int(n_officers)
    want_pool = int(max_solutions or 1) > 1
    count_vars: Dict[tuple, "cp_model.IntVar"] = {}
    if want_pool:
        for key in choice_keys:
            cv = model.NewIntVar(0, n_int, f"cnt_{key[0]}_{key[1]}_{key[2]}")
            model.Add(cv == sum(x[(o, *key)] for o in officers))
            count_vars[key] = cv

    import time as _time

    class _ProgressCb(cp_model.CpSolverSolutionCallback):
        def __init__(self, cb, sol_idx):
            super().__init__()
            self._cb = cb
            self._idx = sol_idx
            self._count = 0

        def on_solution_callback(self):
            self._count += 1
            if self._cb:
                try:
                    self._cb(
                        {
                            "message": f"Solver found solution #{self._count} (pool {self._idx + 1})",
                            "solver_solutions": self._count,
                            "pool_index": self._idx,
                            "objective": self.ObjectiveValue() if self.HasObjective() else None,
                        }
                    )
                except Exception:
                    pass

    deadline = _time.monotonic() + float(pool_time_limit_sec if want_pool else time_limit_sec)
    solutions: List[Dict] = []
    cut_idx = 0
    first_solver_status = None
    while len(solutions) < max(1, int(max_solutions or 1)):
        remaining = deadline - _time.monotonic()
        if solutions and remaining <= 0.5:
            break
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = max(0.5, min(float(time_limit_sec), remaining))
        solver.parameters.num_search_workers = 8
        cb = _ProgressCb(progress_callback, len(solutions)) if progress_callback else None
        status = solver.Solve(model, cb) if cb else solver.Solve(model)

        if status == cp_model.INFEASIBLE:
            if solutions:
                break  # pool exhausted — NOT a proof about the problem
            return {
                "status": "infeasible",
                "solver_status": "proven_infeasible",
                "reason": (
                    "CP-SAT proved no (variant, phase, start) assignment satisfies 24/7 + window "
                    "coverage + annual-hours band together, over a full LCM(cycle,7)-day horizon"
                ),
            }
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            if solutions:
                break
            return {
                "status": "unknown",
                "solver_status": "unknown_or_time_limited",
                "reason": f"CP-SAT status={solver.StatusName(status)} (timeout or unknown)",
            }

        if first_solver_status is None:
            first_solver_status = "proven_optimal" if status == cp_model.OPTIMAL else "feasible_time_limited"

        phase: List[int] = [0] * n_int
        pattern_map: List[int] = [0] * n_int
        shift_starts_out: List[str] = [""] * n_int
        for o in officers:
            for key in choice_keys:
                if solver.Value(x[(o, *key)]) == 1:
                    v, p, si = key
                    # Model convention is duty[day - p], while simulator
                    # convention is duty[day + phase].
                    phase[o] = (-p) % cycle_len
                    pattern_map[o] = v
                    shift_starts_out[o] = starts[si]
                    break
        solutions.append(
            {
                "phase": phase,
                "pattern_map": pattern_map,
                "shift_starts_per_officer": shift_starts_out,
                "objective10": int(solver.ObjectiveValue()) if annual_hours_target is not None else 0,
                "solver_status": "proven_optimal" if status == cp_model.OPTIMAL else "feasible_time_limited",
            }
        )

        if want_pool and len(solutions) < int(max_solutions):
            # Exclude this aggregate profile: at least one key count differs.
            profile = {key: 0 for key in choice_keys}
            for o in officers:
                for key in choice_keys:
                    if solver.Value(x[(o, *key)]) == 1:
                        profile[key] += 1
                        break
            diff_lits = []
            for key, c in profile.items():
                cv = count_vars[key]
                if c > 0:
                    lo = model.NewBoolVar(f"cut{cut_idx}_lo_{key[0]}_{key[1]}_{key[2]}")
                    model.Add(cv <= c - 1).OnlyEnforceIf(lo)
                    model.Add(cv >= c).OnlyEnforceIf(lo.Not())
                    diff_lits.append(lo)
                if c < n_int:
                    hi = model.NewBoolVar(f"cut{cut_idx}_hi_{key[0]}_{key[1]}_{key[2]}")
                    model.Add(cv >= c + 1).OnlyEnforceIf(hi)
                    model.Add(cv <= c).OnlyEnforceIf(hi.Not())
                    diff_lits.append(hi)
            model.AddBoolOr(diff_lits)
            cut_idx += 1

    first = solutions[0]
    return {
        "status": "feasible",
        "phase": first["phase"],
        "pattern_map": first["pattern_map"],
        "shift_starts_per_officer": first["shift_starts_per_officer"],
        "objective10": first["objective10"],
        "solver_status": first_solver_status or "feasible",
        "solutions": solutions,
    }


def solve_cycle_day_starts(
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
    max_start_variation_hours: Optional[float] = None,
    prefer_unique_daily_starts: bool = False,
    objective_order: Optional[Sequence[str]] = None,
    warm_start: Optional[Dict] = None,
    max_horizon_days: int = 140,
    time_limit_sec: float = 45.0,
) -> Dict:
    """Choose pattern/phase plus a start on every working cycle day.

    Unlike ``solve_full_assignment``, an officer is not pinned to one start
    for the whole rotation. OFF days remain OFF, and every selected pattern
    has the same cycle length.
    """
    if not ortools_available() or not patterns or n_officers < 1 or not candidate_starts:
        return {"status": "unsupported"}
    cycle_len = patterns[0].cycle_length
    if cycle_len < 1 or any(p.cycle_length != cycle_len for p in patterns):
        return {"status": "unsupported", "reason": "variation set cycle-length mismatch"}
    horizon = math.lcm(cycle_len, 7)
    if horizon > max_horizon_days:
        return {"status": "unsupported", "reason": f"LCM horizon {horizon} exceeds {max_horizon_days}"}
    if min_rest_hours and float(min_rest_hours) > 24.0 - float(shift_length_hours) + 1e-9:
        return {"status": "unsupported", "reason": "variable starts with this rest floor are not modeled"}

    duty_vectors = [p.duty_vector() for p in patterns]
    allowed = [
        v
        for v, duty in enumerate(duty_vectors)
        if not max_consecutive_work_days or _max_cyclic_run(duty) <= int(max_consecutive_work_days)
    ]
    if not allowed:
        return {"status": "infeasible", "reason": "all patterns exceed consecutive-day limit"}

    starts = list(dict.fromkeys(s for s in candidate_starts if s))
    start_bins = [round(_parse_hhmm(s) / 30) for s in starts]
    shift_bins = round(float(shift_length_hours) * 2)
    bins_per_day = 48
    total_bins = horizon * bins_per_day
    required = [int(coverage_247 or 0)] * total_bins
    for window in extra_windows or []:
        if not isinstance(window, dict) or window.get("enabled") is False:
            continue
        minimum = int(window.get("min_officers") or window.get("min") or 0)
        if minimum <= 0:
            continue
        start_bin = round(_parse_hhmm(window.get("start_time") or window.get("start") or "00:00") / 30)
        end_bin = round(_parse_hhmm(window.get("end_time") or window.get("end") or "00:00") / 30)
        span = end_bin - start_bin if end_bin > start_bin else bins_per_day - start_bin + end_bin
        weekday = window.get("weekday")
        specific = window.get("specific_date") or window.get("date")
        days = []
        if specific:
            if isinstance(specific, str):
                try:
                    specific = date.fromisoformat(specific)
                except ValueError:
                    continue
            offset = (specific - sim_start_date).days
            if 0 <= offset < horizon:
                days = [offset]
        elif weekday is not None and weekday != "":
            days = [d for d in range(horizon) if (sim_start_date + timedelta(days=d)).weekday() == int(weekday)]
        for day in days:
            base = day * bins_per_day + start_bin
            for k in range(span):
                required[(base + k) % total_bins] = max(required[(base + k) % total_bins], minimum)

    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    officers = range(int(n_officers))
    z = {}
    for o in officers:
        for v in allowed:
            for p in range(cycle_len):
                z[(o, v, p)] = model.NewBoolVar(f"z_{o}_{v}_{p}")
        model.Add(sum(z[(o, v, p)] for v in allowed for p in range(cycle_len)) == 1)
    z_keys = [(v, p) for v in allowed for p in range(cycle_len)]
    z_index = []
    for o in officers:
        idx = model.NewIntVar(0, len(z_keys) - 1, f"z_index_{o}")
        model.Add(idx == sum(i * z[(o, v, p)] for i, (v, p) in enumerate(z_keys)))
        z_index.append(idx)
    for o in range(int(n_officers) - 1):
        model.Add(z_index[o] <= z_index[o + 1])
    hint_phases = (warm_start or {}).get("phase") or []
    hint_patterns = (warm_start or {}).get("pattern_map") or []
    for o in officers:
        if o >= len(hint_phases) or o >= len(hint_patterns):
            continue
        key = (int(hint_patterns[o]), (-int(hint_phases[o])) % cycle_len)
        if key in z_keys:
            model.AddHint(z[(o, *key)], 1)

    work_start = {}
    start_used = {}
    start_bump_costs = []
    for o in officers:
        for si in range(len(starts)):
            start_used[(o, si)] = model.NewBoolVar(f"used_{o}_{si}")
        # Keep an officer's rotation within one operational start-time band.
        # Circular clock distance treats late-night/early-morning starts fairly,
        # while still rejecting large jumps such as 06:00 versus 22:00.
        for left in range(len(starts)):
            for right in range(left + 1, len(starts)):
                delta = abs(start_bins[left] - start_bins[right]) / 2.0
                # Start-time bumping is operational, not circular clock math:
                # 06:00 versus 22:00 is a 16-hour rotation change, not 8 hours.
                clock_delta = delta
                if max_start_variation_hours is not None and clock_delta > float(max_start_variation_hours) + 1e-9:
                    model.Add(start_used[(o, left)] + start_used[(o, right)] <= 1)
                else:
                    pair_used = model.NewBoolVar(f"pair_used_{o}_{left}_{right}")
                    model.Add(pair_used <= start_used[(o, left)])
                    model.Add(pair_used <= start_used[(o, right)])
                    model.Add(pair_used >= start_used[(o, left)] + start_used[(o, right)] - 1)
                    start_bump_costs.append(round(clock_delta * 2) * pair_used)
        for d in range(cycle_len):
            for si in range(len(starts)):
                work_start[(o, d, si)] = model.NewBoolVar(f"w_{o}_{d}_{si}")
                model.Add(work_start[(o, d, si)] <= start_used[(o, si)])
            on_terms = [z[(o, v, p)] for v in allowed for p in range(cycle_len) if duty_vectors[v][(d - p) % cycle_len]]
            model.Add(sum(work_start[(o, d, si)] for si in range(len(starts))) == sum(on_terms))
    hint_cycles = (
        (warm_start or {}).get("cycle_starts_per_officer") or (warm_start or {}).get("officer_cycle_starts") or []
    )
    for o in officers:
        if o >= len(hint_cycles):
            continue
        for d, label in enumerate(hint_cycles[o][:cycle_len]):
            if label in starts:
                model.AddHint(work_start[(o, d, starts.index(label))], 1)

    contributors = [[] for _ in range(total_bins)]
    for o in officers:
        for day in range(horizon):
            d = day % cycle_len
            for si, sb in enumerate(start_bins):
                var = work_start[(o, d, si)]
                base = day * bins_per_day + sb
                for k in range(shift_bins):
                    contributors[(base + k) % total_bins].append(var)
    for b, minimum in enumerate(required):
        if minimum > 0:
            model.Add(sum(contributors[b]) >= minimum)

    duplicate_start_costs = []
    if prefer_unique_daily_starts:
        for d in range(cycle_len):
            for si in range(len(starts)):
                excess = model.NewIntVar(0, max(0, n_officers - 1), f"duplicate_{d}_{si}")
                model.Add(excess >= sum(work_start[(o, d, si)] for o in officers) - 1)
                duplicate_start_costs.append(excess)

    annual10 = {v: round(projected_annual_hours(patterns[v], shift_length_hours) * 10) for v in allowed}
    y = {}
    objective_parts = {}
    objective_bounds = {}
    if annual_hours_target is not None:
        for o in officers:
            for v in allowed:
                y[(o, v)] = model.NewBoolVar(f"y_{o}_{v}")
                model.Add(y[(o, v)] == sum(z[(o, v, p)] for p in range(cycle_len)))
        target10 = round(float(annual_hours_target) * 10)
        objective_parts["annual"] = sum(abs(annual10[v] - target10) * y[(o, v)] for o in officers for v in allowed)
        objective_bounds["annual"] = n_officers * max(abs(annual10[v] - target10) for v in allowed)
    if duplicate_start_costs:
        objective_parts["duplicate_starts"] = sum(duplicate_start_costs)
        objective_bounds["duplicate_starts"] = cycle_len * len(starts) * max(0, n_officers - 1)
    objective_parts["distinct_starts"] = sum(start_used[(o, si)] for o in officers for si in range(len(starts)))
    objective_bounds["distinct_starts"] = n_officers * len(starts)
    if start_bump_costs:
        objective_parts["start_changes"] = sum(start_bump_costs)
        objective_bounds["start_changes"] = n_officers * sum(
            round(abs(start_bins[left] - start_bins[right]))
            for left in range(len(starts))
            for right in range(left + 1, len(starts))
        )
    default_order = ["annual", "start_changes", "duplicate_starts", "distinct_starts"]
    requested = [str(key) for key in (objective_order or []) if str(key) in objective_parts]
    ordered = requested + [key for key in default_order if key in objective_parts and key not in requested]
    if ordered:
        coefficients = lexicographic_coefficients([(key, objective_bounds[key]) for key in ordered])
        model.Minimize(sum(coefficients[key] * objective_parts[key] for key in ordered))
    if annual_hours_hard and annual_hours_target is not None:
        band = float(annual_hours_variance or 0.0)
        total = sum(annual10[v] * y[(o, v)] for o in officers for v in allowed)
        model.Add(total >= math.ceil(n_officers * (float(annual_hours_target) - band) * 10 - 1e-6))
        model.Add(total <= math.floor(n_officers * (float(annual_hours_target) + band) * 10 + 1e-6))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_sec)
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)
    if status == cp_model.INFEASIBLE:
        return {
            "status": "infeasible",
            "solver_status": "proven_infeasible",
            "reason": "no cycle-day start assignment satisfies all constraints",
        }
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "status": "unknown",
            "solver_status": "unknown_or_time_limited",
            "reason": f"CP-SAT status={solver.StatusName(status)}",
        }

    phases = [0] * n_officers
    pattern_map = [0] * n_officers
    cycle_starts = [[""] * cycle_len for _ in officers]
    for o in officers:
        for v in allowed:
            for p in range(cycle_len):
                if solver.Value(z[(o, v, p)]):
                    phases[o] = (-p) % cycle_len
                    pattern_map[o] = v
        for d in range(cycle_len):
            for si, label in enumerate(starts):
                if solver.Value(work_start[(o, d, si)]):
                    cycle_starts[o][d] = label
                    break
    homes = [next((s for s in days if s), starts[0]) for days in cycle_starts]
    return {
        "status": "feasible",
        "phase": phases,
        "pattern_map": pattern_map,
        "shift_starts_per_officer": homes,
        "cycle_starts_per_officer": cycle_starts,
        "solver_status": "proven_optimal" if status == cp_model.OPTIMAL else "feasible_time_limited",
    }
