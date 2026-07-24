"""Master plan §11 "Independent corpus" — brute-force ground truth for
solve_full_assignment's coverage_247 claim.

Enumerates every (variant, phase, start) triple per officer for a small
domain (pure Python, no CP-SAT, no rust) and checks true 24/7 coverage via
the same sweep-line verifier (`logic.coverage_timeline`) production code
uses independently of the solver. Compares the oracle's feasible/infeasible
verdict against solve_full_assignment's status — the solver must never
diverge from ground truth in either direction."""

import math
from datetime import date, timedelta
from itertools import product

import pytest

from logic.coverage_timeline import CoverageWindow, check_coverage_247, check_coverage_window
from logic.rotation_patterns import OnOffBlock, RotationPattern
from logic.staffing_cpsat import ortools_available, solve_cycle_day_starts, solve_full_assignment, solve_phase_variant

pytestmark = pytest.mark.skipif(not ortools_available(), reason="OR-Tools not installed")


def _oracle_feasible(
    *,
    patterns,
    n_officers: int,
    shift_length_hours: float,
    candidate_starts,
    sim_start_date: date,
    coverage_247: int,
    horizon: int,
    windows=None,
    annual_hours_target=None,
    annual_hours_variance: float = 0.0,
    annual_hours_hard: bool = False,
) -> bool:
    """True ground truth: does ANY fixed (variant, phase, start) assignment
    per officer satisfy 24/7 coverage, every named window, and the annual-
    hours band (if hard) every day of the horizon?

    Annual hours are computed directly from the brute-forced assignment
    (worked-days-in-horizon fraction × 365.25 × shift length) — independent
    arithmetic from the CP-SAT model's own total10/band computation, not a
    shared helper, so an encoding bug in either wouldn't cancel out."""
    cycle_len = patterns[0].cycle_length
    duty_vectors = [p.duty_vector() for p in patterns]
    choices = [(v, p, s) for v in range(len(patterns)) for p in range(cycle_len) for s in candidate_starts]
    end_hour = shift_length_hours
    days = [sim_start_date + timedelta(days=d) for d in range(horizon)]
    windows = windows or []

    for combo in product(choices, repeat=n_officers):
        assignments = []
        officer_hours = []
        for v, p, start in combo:
            duty = duty_vectors[v]
            worked_days = 0
            for day_idx, day in enumerate(days):
                if not duty[(day_idx - p) % cycle_len]:
                    continue
                worked_days += 1
                end_total = _hhmm_to_minutes(start) + end_hour * 60
                end_h, end_m = divmod(int(round(end_total)) % (24 * 60), 60)
                assignments.append((day, start, f"{end_h:02d}:{end_m:02d}"))
            officer_hours.append(worked_days / horizon * 365.25 * shift_length_hours)

        if not all(check_coverage_247(assignments, day, coverage_247)["ok"] for day in days):
            continue
        if not all(check_coverage_window(assignments, w, day)["ok"] for day in days for w in windows):
            continue
        if annual_hours_hard and annual_hours_target is not None:
            lo = annual_hours_target - annual_hours_variance
            hi = annual_hours_target + annual_hours_variance
            avg = sum(officer_hours) / len(officer_hours)
            if not (lo - 1e-6 <= avg <= hi + 1e-6):
                continue
        return True
    return False


def _oracle_feasible_phase_variant(
    *,
    patterns,
    n_officers: int,
    shift_length_hours: float,
    coverage_247: int,
    max_consecutive_work_days: int = 0,
) -> bool:
    """Ground truth for solve_phase_variant's NECESSARY (day-level headcount)
    condition: does any (variant, phase) assignment per officer put at least
    coverage_247 * ceil(24/shift_length_hours) officers on duty every cycle
    day, while respecting max_consecutive_work_days? Brute force, independent
    of the CP-SAT model's own boolean-sum encoding."""
    cycle_len = patterns[0].cycle_length
    duty_vectors = [p.duty_vector() for p in patterns]
    per_day_min = int(coverage_247) * math.ceil(24.0 / float(shift_length_hours))

    allowed = list(range(len(patterns)))
    if max_consecutive_work_days:
        allowed = [v for v in allowed if _max_cyclic_run(duty_vectors[v]) <= max_consecutive_work_days]
    if not allowed:
        return False

    choices = [(v, p) for v in allowed for p in range(cycle_len)]
    for combo in product(choices, repeat=n_officers):
        headcount = [0] * cycle_len
        for v, p in combo:
            duty = duty_vectors[v]
            for d in range(cycle_len):
                if duty[(d - p) % cycle_len]:
                    headcount[d] += 1
        if all(h >= per_day_min for h in headcount):
            return True
    return False


def _oracle_feasible_cycle_day_starts(
    *,
    patterns,
    n_officers: int,
    shift_length_hours: float,
    candidate_starts,
    sim_start_date: date,
    coverage_247: int,
    horizon: int,
    windows=None,
) -> bool:
    """Ground truth for solve_cycle_day_starts: unlike solve_full_assignment
    (one fixed start for the whole horizon), here each officer independently
    picks a pattern/phase AND a start per working cycle-day. Brute force over
    every (variant, phase, per-on-day-start) choice per officer."""
    cycle_len = patterns[0].cycle_length
    duty_vectors = [p.duty_vector() for p in patterns]
    days = [sim_start_date + timedelta(days=d) for d in range(horizon)]
    windows = windows or []

    officer_choices = []
    for v, duty in enumerate(duty_vectors):
        on_positions = [d for d in range(cycle_len) if duty[d]]
        for p in range(cycle_len):
            for start_combo in product(candidate_starts, repeat=len(on_positions)):
                officer_choices.append((v, p, on_positions, start_combo))

    for combo in product(officer_choices, repeat=n_officers):
        assignments = []
        for v, p, on_positions, start_combo in combo:
            on_map = dict(zip(on_positions, start_combo))
            for day_idx, day in enumerate(days):
                pos = (day_idx - p) % cycle_len
                if pos not in on_map:
                    continue
                start = on_map[pos]
                end_total = _hhmm_to_minutes(start) + shift_length_hours * 60
                end_h, end_m = divmod(int(round(end_total)) % (24 * 60), 60)
                assignments.append((day, start, f"{end_h:02d}:{end_m:02d}"))

        if not all(check_coverage_247(assignments, day, coverage_247)["ok"] for day in days):
            continue
        if not all(check_coverage_window(assignments, w, day)["ok"] for day in days for w in windows):
            continue
        return True
    return False


def _max_cyclic_run(duty) -> int:
    n = len(duty)
    if all(duty):
        return n
    best = run = 0
    for v in list(duty) * 2:
        if v:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return min(best, n)


def _hhmm_to_minutes(value: str) -> float:
    h, m = value.split(":")
    return int(h) * 60 + int(m)


def _run_case(
    *,
    n_officers,
    coverage_247,
    candidate_starts,
    shift_length_hours=8.0,
    pattern=None,
    windows=None,
    annual_hours_target=None,
    annual_hours_variance=0.0,
    annual_hours_hard=False,
):
    pattern = pattern or RotationPattern(style="fixed", blocks=[OnOffBlock(days_on=7, days_off=0)], label="7-0")
    patterns = [pattern]
    sim_start = date(2026, 1, 5)  # Monday
    cycle_len = pattern.cycle_length
    horizon = math.lcm(cycle_len, 7)  # matches solve_full_assignment's own horizon

    oracle_ok = _oracle_feasible(
        patterns=patterns,
        n_officers=n_officers,
        shift_length_hours=shift_length_hours,
        candidate_starts=candidate_starts,
        sim_start_date=sim_start,
        coverage_247=coverage_247,
        horizon=horizon,
        windows=[CoverageWindow(**w) for w in (windows or [])],
        annual_hours_target=annual_hours_target,
        annual_hours_variance=annual_hours_variance,
        annual_hours_hard=annual_hours_hard,
    )

    result = solve_full_assignment(
        patterns,
        n_officers=n_officers,
        shift_length_hours=shift_length_hours,
        candidate_starts=candidate_starts,
        sim_start_date=sim_start,
        coverage_247=coverage_247,
        extra_windows=windows,
        annual_hours_target=annual_hours_target,
        annual_hours_variance=annual_hours_variance,
        annual_hours_hard=annual_hours_hard,
        time_limit_sec=5.0,
        max_horizon_days=140,
    )
    solver_ok = result["status"] == "feasible"
    assert solver_ok == oracle_ok, (
        f"solver status={result['status']!r} but brute-force oracle says "
        f"feasible={oracle_ok} for n_officers={n_officers}, "
        f"coverage_247={coverage_247}, starts={candidate_starts}, "
        f"windows={windows}, annual_hours_target={annual_hours_target}"
    )
    return result


def test_oracle_matches_solver_feasible_three_officers_three_starts_full_coverage():
    # 3 officers, 8h shifts starting 00:00/08:00/16:00 exactly tile 24h —
    # one officer per slot covers min 1 every hour of every day.
    _run_case(n_officers=3, coverage_247=1, candidate_starts=["00:00", "08:00", "16:00"])


def test_oracle_matches_solver_infeasible_two_officers_need_three_slots():
    # Same 3-slot geometry but only 2 officers — one slot is always uncovered
    # for the third of the day it needs someone, so min_occupancy never
    # reaches 1 across the whole day. Both oracle and solver must say
    # infeasible — a false "feasible" here would violate scheduling truth.
    _run_case(n_officers=2, coverage_247=1, candidate_starts=["00:00", "08:00", "16:00"])


def test_oracle_matches_solver_infeasible_coverage_exceeds_capacity():
    # 3 officers can hold min 1, but not min 2 (no start overlap available
    # from only 3 non-overlapping 8h slots) — proves the solver doesn't
    # over-claim feasibility when the domain truly can't support it.
    _run_case(n_officers=3, coverage_247=2, candidate_starts=["00:00", "08:00", "16:00"])


def test_oracle_matches_solver_feasible_with_overlap_slack():
    # 4 officers, only 2 starts 12h apart with 8h shifts — creates overlap
    # windows and gaps; oracle brute-forces the true answer independent of
    # any solver-side reasoning about which combination works.
    _run_case(n_officers=4, coverage_247=1, candidate_starts=["00:00", "12:00"])


def test_oracle_matches_solver_feasible_weekday_window_satisfiable():
    # 2 officers, 7-0 pattern (always on), 12h starts at 00:00/12:00 tile the
    # day with overlap — a Friday-night min-2 window is trivially satisfiable
    # since both officers are always on duty somewhere.
    _run_case(
        n_officers=2,
        coverage_247=1,
        candidate_starts=["00:00", "12:00"],
        shift_length_hours=12.0,
        windows=[{"weekday": 4, "start_time": "19:00", "end_time": "03:00", "min_officers": 2}],
    )


def test_oracle_matches_solver_infeasible_weekday_window_exceeds_capacity():
    # Only 1 officer total can never hold a Friday-night min-2 window no
    # matter which start/phase it picks — sound infeasible on both sides.
    _run_case(
        n_officers=1,
        coverage_247=0,
        candidate_starts=["00:00", "12:00"],
        shift_length_hours=12.0,
        windows=[{"weekday": 4, "start_time": "19:00", "end_time": "03:00", "min_officers": 2}],
    )


def test_oracle_matches_solver_feasible_annual_hours_band_wide():
    # 5-2 pattern, 8h shifts: work fraction 5/7 -> ~1043h/yr average per
    # officer. A generously wide band around that true value must be
    # feasible on both sides.
    pattern = RotationPattern(style="fixed", blocks=[OnOffBlock(days_on=5, days_off=2)], label="5-2")
    _run_case(
        n_officers=2,
        coverage_247=0,
        candidate_starts=["07:00"],
        shift_length_hours=8.0,
        pattern=pattern,
        annual_hours_target=1043.0,
        annual_hours_variance=50.0,
        annual_hours_hard=True,
    )


def test_oracle_matches_solver_infeasible_annual_hours_band_impossible():
    # Same 5-2/8h pattern (~1043h/yr, fixed — only one variant, no phase
    # choice changes the worked-day count) but a band nowhere near it must
    # be infeasible on both sides.
    pattern = RotationPattern(style="fixed", blocks=[OnOffBlock(days_on=5, days_off=2)], label="5-2")
    _run_case(
        n_officers=2,
        coverage_247=0,
        candidate_starts=["07:00"],
        shift_length_hours=8.0,
        pattern=pattern,
        annual_hours_target=200.0,
        annual_hours_variance=10.0,
        annual_hours_hard=True,
    )


def test_oracle_matches_solver_phase_variant_feasible():
    pattern = RotationPattern(style="fixed", blocks=[OnOffBlock(days_on=5, days_off=2)], label="5-2")
    patterns = [pattern]
    oracle_ok = _oracle_feasible_phase_variant(patterns=patterns, n_officers=2, shift_length_hours=8.0, coverage_247=1)
    result = solve_phase_variant(patterns, n_officers=2, shift_length_hours=8.0, coverage_247=1, time_limit_sec=5.0)
    assert (result["status"] == "feasible") == oracle_ok


def test_oracle_matches_solver_phase_variant_infeasible_max_consecutive():
    # 7-0 (always on) is the only variant — max_consecutive_work_days=3
    # rules it out entirely, so no phase/variant choice can satisfy it.
    pattern = RotationPattern(style="fixed", blocks=[OnOffBlock(days_on=7, days_off=0)], label="7-0")
    patterns = [pattern]
    oracle_ok = _oracle_feasible_phase_variant(
        patterns=patterns,
        n_officers=2,
        shift_length_hours=8.0,
        coverage_247=1,
        max_consecutive_work_days=3,
    )
    result = solve_phase_variant(
        patterns,
        n_officers=2,
        shift_length_hours=8.0,
        coverage_247=1,
        max_consecutive_work_days=3,
        time_limit_sec=5.0,
    )
    assert (result["status"] == "feasible") == oracle_ok


def test_oracle_matches_solver_cycle_day_starts_feasible_complementary_daily_starts():
    # 2 officers, always-on (7-0), 12h shifts, 2 non-overlapping daily
    # starts. Unlike solve_full_assignment (one fixed start for the whole
    # horizon), cycle_day_starts lets each officer pick a start per working
    # day — one officer at 00:00 and the other at 12:00 every day covers
    # 24/7. Exercises the per-day-start feature the oracle above targets.
    pattern = RotationPattern(style="fixed", blocks=[OnOffBlock(days_on=7, days_off=0)], label="7-0")
    patterns = [pattern]
    sim_start = date(2026, 1, 5)
    horizon = math.lcm(pattern.cycle_length, 7)
    candidate_starts = ["00:00", "12:00"]

    oracle_ok = _oracle_feasible_cycle_day_starts(
        patterns=patterns,
        n_officers=2,
        shift_length_hours=12.0,
        candidate_starts=candidate_starts,
        sim_start_date=sim_start,
        coverage_247=1,
        horizon=horizon,
    )
    result = solve_cycle_day_starts(
        patterns,
        n_officers=2,
        shift_length_hours=12.0,
        candidate_starts=candidate_starts,
        sim_start_date=sim_start,
        coverage_247=1,
        time_limit_sec=5.0,
    )
    assert (result["status"] == "feasible") == oracle_ok


def test_oracle_matches_solver_cycle_day_starts_infeasible_single_officer_half_day():
    # 1 officer can never cover 24/7 with a single 12h shift no matter which
    # daily start is picked — sound infeasible regardless of per-day choice.
    pattern = RotationPattern(style="fixed", blocks=[OnOffBlock(days_on=7, days_off=0)], label="7-0")
    patterns = [pattern]
    sim_start = date(2026, 1, 5)
    horizon = math.lcm(pattern.cycle_length, 7)
    candidate_starts = ["00:00", "12:00"]

    oracle_ok = _oracle_feasible_cycle_day_starts(
        patterns=patterns,
        n_officers=1,
        shift_length_hours=12.0,
        candidate_starts=candidate_starts,
        sim_start_date=sim_start,
        coverage_247=1,
        horizon=horizon,
    )
    result = solve_cycle_day_starts(
        patterns,
        n_officers=1,
        shift_length_hours=12.0,
        candidate_starts=candidate_starts,
        sim_start_date=sim_start,
        coverage_247=1,
        time_limit_sec=5.0,
    )
    assert (result["status"] == "feasible") == oracle_ok
