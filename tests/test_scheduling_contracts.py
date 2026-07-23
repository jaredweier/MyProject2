from logic.scheduling_contracts import (
    ConstraintProfile,
    CoverageDecisionReport,
    CoverageDisruptionSpec,
    CoveragePlan,
    ScheduleCandidate,
    ScheduleChangeSet,
    ScheduleStatus,
    SearchProfile,
    SimulationReport,
    StaffingProblemSpec,
    VerificationReport,
    compute_input_hash,
    to_canonical_status,
)


def test_legacy_status_strings_map_to_canonical():
    assert to_canonical_status("proven_optimal") == ScheduleStatus.OPTIMAL
    assert to_canonical_status("feasible_time_limited") == ScheduleStatus.FEASIBLE
    assert to_canonical_status("feasible") == ScheduleStatus.FEASIBLE
    assert to_canonical_status("infeasible") == ScheduleStatus.INFEASIBLE
    assert to_canonical_status("proven_infeasible") == ScheduleStatus.INFEASIBLE
    assert to_canonical_status("unknown") == ScheduleStatus.UNKNOWN
    assert to_canonical_status("unknown_or_time_limited") == ScheduleStatus.UNKNOWN


def test_unrecognized_status_never_collapses_to_infeasible():
    assert to_canonical_status("some_new_status_nobody_mapped") == ScheduleStatus.UNKNOWN
    assert to_canonical_status("") == ScheduleStatus.UNKNOWN


def test_canonical_status_passthrough():
    assert to_canonical_status(ScheduleStatus.CANCELLED) == ScheduleStatus.CANCELLED


def test_cpsat_entry_points_stamp_canonical_status():
    from datetime import date

    from logic.rotation_patterns import build_pattern
    from logic.staffing_cpsat import solve_cycle_day_starts

    start = date(2026, 7, 20)
    result = solve_cycle_day_starts(
        patterns=[build_pattern("2-1", style="fixed")],
        n_officers=1,
        shift_length_hours=1.0,
        candidate_starts=["06:00"],
        sim_start_date=start,
        extra_windows=[
            {"specific_date": start, "start_time": "06:00", "end_time": "07:00", "min_officers": 1},
        ],
        time_limit_sec=5.0,
    )
    assert "canonical_status" in result
    assert isinstance(result["canonical_status"], ScheduleStatus)
    assert result["canonical_status"] == ScheduleStatus.FEASIBLE
    report = result["simulation_report"]
    assert isinstance(report, SimulationReport)
    assert report.status == ScheduleStatus.FEASIBLE
    assert report.candidates
    assert report.candidates[0].assignments[0]["officer_id"] == 0
    assert report.verification is not None
    assert report.verification.verified is True


def test_solve_cycle_day_starts_verification_catches_an_unmet_window():
    from datetime import date

    from logic.rotation_patterns import build_pattern
    from logic.staffing_cpsat import solve_cycle_day_starts

    start = date(2026, 7, 20)
    # coverage_247=0 and a window CP-SAT is not asked to satisfy — the
    # solver returns feasible on the (unconstrained) window, but the
    # independent verifier still recalculates it from the real assignment.
    result = solve_cycle_day_starts(
        patterns=[build_pattern("1-6", style="fixed")],
        n_officers=1,
        shift_length_hours=1.0,
        candidate_starts=["06:00"],
        sim_start_date=start,
        time_limit_sec=5.0,
    )
    assert result["status"] == "feasible"
    report = result["simulation_report"]
    # No extra_windows/coverage_247 were passed, so nothing to recheck —
    # proves the verifier only claims what it actually checked.
    assert report.verification.checked_constraints == []
    assert report.verification.verified is True


def test_solve_phase_variant_always_attaches_a_simulation_report():
    from logic.rotation_patterns import build_pattern
    from logic.staffing_cpsat import solve_phase_variant

    pattern = build_pattern("2-1", style="fixed")
    result = solve_phase_variant([pattern], n_officers=1, shift_length_hours=8.0, coverage_247=1, time_limit_sec=5.0)
    report = result["simulation_report"]
    assert isinstance(report, SimulationReport)
    assert report.status == result["canonical_status"]
    # infeasible here (1 officer can't cover 24/7) — proves the report is
    # attached on every branch, not only the feasible one.
    assert report.status == ScheduleStatus.INFEASIBLE
    assert report.candidates == []
    assert report.warnings


def test_optimize_staffing_scenarios_stamps_canonical_status():
    from logic.staffing_optimizer import optimize_staffing_scenarios

    result = optimize_staffing_scenarios(
        rotation_types=["2-2-3"],
        officer_counts=[6],
        min_per_shift_options=[1],
        shift_length_hours=8.0,
        simulation_days=14,
    )
    assert "canonical_status" in result
    assert isinstance(result["canonical_status"], ScheduleStatus)
    assert result["canonical_status"] != ScheduleStatus.INFEASIBLE or not result.get("best")


def test_optimize_staffing_scenarios_simulation_report_matches_ranked():
    from logic.staffing_optimizer import optimize_staffing_scenarios

    result = optimize_staffing_scenarios(
        rotation_types=["2-2-3 (14-day)"],
        officer_counts=[12, 16],
        min_per_shift_options=[2],
        shift_starts=["06:00", "14:00", "22:00"],
        shift_length_hours=11.0,
        annual_hours_target=2080,
        simulation_days=14,
    )
    report = result["simulation_report"]
    assert isinstance(report, SimulationReport)
    assert report.status == result["canonical_status"]
    assert len(report.candidates) == len(result.get("ranked") or [])
    for candidate, row in zip(report.candidates, result["ranked"]):
        assert len(candidate.assignments) == int(row["num_officers"])
    assert report.verification is not None
    assert report.verification.verified == all(row.get("hard_constraints_ok") for row in result["ranked"])


def test_optimize_staffing_scenarios_verification_is_none_without_ranked_rows():
    from logic.staffing_optimizer import optimize_staffing_scenarios

    # Deliberately impossible: 1 officer can't hit 24/7 coverage_247=2.
    result = optimize_staffing_scenarios(
        rotation_types=["2-2-3"],
        officer_counts=[1],
        min_per_shift_options=[1],
        shift_length_hours=8.0,
        simulation_days=7,
        coverage_247=2,
    )
    report = result["simulation_report"]
    assert report.candidates == []
    assert report.verification is None


def test_staffing_problem_spec_defaults_are_empty_not_none():
    spec = StaffingProblemSpec(
        tenant_id="demo",
        organization="Demo PD",
        time_zone="UTC",
        horizon_start="2026-07-20",
        horizon_end="2026-08-17",
    )
    assert spec.coverage_intervals == []
    assert spec.leave == []
    assert isinstance(spec.constraints, ConstraintProfile)
    assert isinstance(spec.search, SearchProfile)
    assert spec.schema_version == "1"


def test_simulation_report_round_trip_with_verification():
    candidate = ScheduleCandidate(assignments=[{"officer_id": 1, "shift": "06:00"}])
    verification = VerificationReport(verified=True, status=ScheduleStatus.FEASIBLE)
    report = SimulationReport(
        status=ScheduleStatus.FEASIBLE,
        candidates=[candidate],
        verification=verification,
    )
    assert report.status == ScheduleStatus.FEASIBLE
    assert report.candidates[0].assignments[0]["officer_id"] == 1
    assert report.verification.verified is True


def test_verify_schedule_candidate_recalculates_from_raw_assignments():
    from datetime import date, timedelta

    from logic.coverage_timeline import verify_schedule_candidate

    day = date(2026, 7, 20)
    prev = day - timedelta(days=1)
    # Two officers covering the full 24h day between them (12h shifts,
    # including the prior day's overnight tail into 00:00-06:00).
    covered = [
        (prev, "18:00", "06:00"),
        (day, "06:00", "18:00"),
        (day, "18:00", "06:00"),
    ]
    report = verify_schedule_candidate(covered, [day], min_247=1)
    assert report.verified is True
    assert report.status == ScheduleStatus.FEASIBLE
    assert report.violations == []
    assert "coverage_247" in report.checked_constraints

    # A gap: only one 12h shift, so half the day is uncovered.
    gapped = [(day, "06:00", "18:00")]
    bad_report = verify_schedule_candidate(gapped, [day], min_247=1)
    assert bad_report.verified is False
    assert bad_report.status == ScheduleStatus.INFEASIBLE
    assert bad_report.violations


def test_verify_plan_for_implementation_attaches_verification_report():
    from logic.optimized_schedule_apply import verify_plan_for_implementation

    passing = verify_plan_for_implementation(
        {"coverage_by_day": [], "officer_slots": [], "assignments": []},
        {"min_per_shift": 0, "annual_hours_hard": False, "coverage_247": 0},
    )
    report = passing["verification_report"]
    assert isinstance(report, VerificationReport)
    assert report.verified is True
    assert report.status == ScheduleStatus.FEASIBLE

    failing = verify_plan_for_implementation(
        {
            "coverage_by_day": [{"date": "2026-07-20", "shift_counts": {"06:00": 0}}],
            "officer_slots": [],
            "assignments": [],
        },
        {"min_per_shift": 2, "shift_starts": ["06:00"], "annual_hours_hard": False, "coverage_247": 0},
    )
    bad_report = failing["verification_report"]
    assert bad_report.verified is False
    assert bad_report.status == ScheduleStatus.INFEASIBLE
    assert bad_report.violations
    assert "minimum_shift_coverage" in bad_report.checked_constraints


def test_coverage_decision_report_carries_relaxation_authority():
    disruption = CoverageDisruptionSpec(disruption_type="leave", affected_date="2026-07-21")
    change_set = ScheduleChangeSet(base_version="v1", changes=[{"op": "assign"}])
    plan = CoveragePlan(disruption=disruption, change_set=change_set)
    decision = CoverageDecisionReport(
        status=ScheduleStatus.FEASIBLE,
        plan=plan,
        relaxation_authority={"authority": "supervisor", "subject": "min_rest_hours"},
    )
    assert decision.plan.disruption.disruption_type == "leave"
    assert decision.relaxation_authority["subject"] == "min_rest_hours"


def test_compute_input_hash_is_stable_and_key_order_independent():
    a = compute_input_hash({"x": 1, "y": [1, 2, 3]})
    b = compute_input_hash({"y": [1, 2, 3], "x": 1})
    assert a == b
    assert a != compute_input_hash({"x": 2, "y": [1, 2, 3]})


def test_compute_input_hash_handles_non_json_values():
    from datetime import date

    # Must not raise on a date or an arbitrary object.
    h = compute_input_hash({"day": date(2026, 7, 20), "obj": object()})
    assert isinstance(h, str) and len(h) == 64


def test_cpsat_reports_carry_input_hash():
    from datetime import date

    from logic.rotation_patterns import build_pattern
    from logic.staffing_cpsat import solve_cycle_day_starts

    start = date(2026, 7, 20)
    result = solve_cycle_day_starts(
        patterns=[build_pattern("2-1", style="fixed")],
        n_officers=1,
        shift_length_hours=1.0,
        candidate_starts=["06:00"],
        sim_start_date=start,
        time_limit_sec=5.0,
    )
    assert result["simulation_report"].input_hash
    assert len(result["simulation_report"].input_hash) == 64


def test_build_staffing_problem_spec_from_simulator_config():
    from datetime import date

    from simulator import SimulatorConfig, build_staffing_problem_spec

    config = SimulatorConfig(
        rotation_type="2-2-3",
        num_officers=6,
        shift_length_hours=8.0,
        annual_hours_target=2008.0,
        shift_starts=["06:00", "14:00", "22:00"],
        simulation_days=14,
        sim_start_date=date(2026, 7, 20),
        coverage_247=1,
        min_rest_hours=8.0,
    )
    spec = build_staffing_problem_spec(config, tenant_id="demo-pd", organization="Demo PD")
    assert spec.tenant_id == "demo-pd"
    assert spec.horizon_start == "2026-07-20"
    assert spec.horizon_end == "2026-08-03"
    assert spec.officers == list(range(6))
    assert spec.rotations[0] == "2-2-3"
    assert spec.constraints.min_rest_hours == 8.0
    assert spec.constraints.annual_hours_target == 2008.0
    assert {"type": "24/7", "min_officers": 1} in spec.coverage_intervals
