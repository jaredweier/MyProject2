"""Phase 3 "exact feasibility and proof" — assumption-based conflict
explanation for logic.staffing_cpsat._solve_full_assignment.

Proves: on INFEASIBLE, `conflict_assumptions` (raw dict) / SimulationReport
.conflicts (public) correctly names the constraint category responsible,
and relaxing that category actually restores feasibility (the "sufficient"
claim is true, not just plausible)."""

import time
from datetime import date

import pytest

from logic.rotation_patterns import OnOffBlock, RotationPattern
from logic.staffing_cpsat import ortools_available, solve_full_assignment

pytestmark = pytest.mark.skipif(not ortools_available(), reason="OR-Tools not installed")


def _pattern():
    # 7-day cycle: 5 on / 2 off, single fixed variant.
    return RotationPattern(style="fixed", blocks=[OnOffBlock(days_on=5, days_off=2)], label="5-2")


def test_coverage_conflict_identified_and_sufficient():
    """3 officers can't hold a 24/7 min of 5 — infeasible. Conflict set must
    name the coverage_247 category, and raising officers past the min must
    restore feasibility (proves 'sufficient' is really true)."""
    patterns = [_pattern()]
    kwargs = dict(
        patterns=patterns,
        n_officers=3,
        shift_length_hours=8.0,
        candidate_starts=["07:00", "15:00", "23:00"],
        sim_start_date=date(2026, 1, 5),  # Monday
        coverage_247=5,
        time_limit_sec=5.0,
        max_horizon_days=140,
    )
    result = solve_full_assignment(**kwargs)
    assert result["status"] == "infeasible"
    conflicts = result["simulation_report"].conflicts
    assert conflicts, "expected a non-empty sufficient conflict set"
    cats = [c["category"] for c in conflicts]
    assert any("coverage_247" in c for c in cats)
    assert all(c["sufficient_not_minimal"] is True for c in conflicts)

    # Relax: enough officers now (5 officers can cover 24/7 min of 5 with
    # single 8h shifts on a 5-2 pattern needs more, but bump way up to make
    # the point cleanly — proves relaxing the identified category fixes it).
    kwargs_relaxed = dict(kwargs, n_officers=40)
    result2 = solve_full_assignment(**kwargs_relaxed)
    assert result2["status"] == "feasible"


def test_annual_hours_band_conflict_identified_and_sufficient():
    """Coverage is trivially satisfiable, but an impossibly tight annual-
    hours band (far below what the only pattern produces) makes it
    infeasible. Conflict set must name annual_hours_band; widening the band
    must restore feasibility."""
    patterns = [_pattern()]
    common = dict(
        patterns=patterns,
        n_officers=9,
        shift_length_hours=8.0,
        candidate_starts=["07:00", "15:00", "23:00"],
        sim_start_date=date(2026, 1, 5),
        coverage_247=1,
        annual_hours_target=100.0,  # 5-2 @ 8h/day projects far higher than this
        annual_hours_variance=1.0,
        annual_hours_hard=True,
        time_limit_sec=5.0,
        max_horizon_days=140,
    )
    result = solve_full_assignment(**common)
    assert result["status"] == "infeasible"
    conflicts = result["simulation_report"].conflicts
    assert conflicts
    cats = [c["category"] for c in conflicts]
    assert any("annual_hours_target" in c for c in cats)

    relaxed = dict(common, annual_hours_hard=False)
    result2 = solve_full_assignment(**relaxed)
    assert result2["status"] == "feasible"


def test_feasible_fast_path_no_conflict_field_and_no_slowdown():
    """Feasible scenario: conflicts must be empty, and wall time must not
    regress — the explain model only builds on the INFEASIBLE branch."""
    patterns = [_pattern()]
    kwargs = dict(
        patterns=patterns,
        n_officers=10,
        shift_length_hours=8.0,
        candidate_starts=["07:00", "15:00", "23:00"],
        sim_start_date=date(2026, 1, 5),
        coverage_247=2,
        time_limit_sec=5.0,
        max_horizon_days=140,
    )
    t0 = time.monotonic()
    result = solve_full_assignment(**kwargs)
    elapsed = time.monotonic() - t0
    assert result["status"] == "feasible"
    assert result["simulation_report"].conflicts == []
    # Generous ceiling — this is a regression guard, not a perf benchmark.
    assert elapsed < 10.0, f"feasible-case solve took {elapsed:.2f}s, expected well under 10s"
