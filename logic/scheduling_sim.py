"""Schedule simulation and coverage-plan preview helpers.

Extracted from ``logic.scheduling`` to keep the rotation/bump core smaller.
Public names remain available via ``logic.scheduling`` re-exports.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from validators import parse_date


def run_schedule_simulation(
    rotation_type: str,
    num_officers: int,
    shift_length_hours: float,
    annual_hours_target: float,
    shift_starts: List[str],
    apply_department_rules: bool = True,
    min_per_shift: int = 1,
    simulation_days: int = 28,
    night_minimum: int | None = None,
) -> Dict:
    from config import NIGHT_MINIMUM_OFFICERS
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
        night_minimum=night_minimum if night_minimum is not None else NIGHT_MINIMUM_OFFICERS,
    )
    result = simulate_schedule(config)
    if not result.success:
        return {"success": False, "message": result.message or "Simulation failed"}
    coverage = result.coverage_by_day
    start_label = coverage[0]["date"] if coverage else None
    return {
        "success": True,
        "compute_backend": result.compute_backend,
        "metrics": result.metrics,
        "officer_slots": [slot.__dict__ for slot in result.officer_slots],
        "coverage_by_day": coverage,
        "suggestions": [
            {"severity": s.severity, "title": s.title, "message": s.message, "recommendation": s.recommendation}
            for s in result.suggestions
        ],
        "shift_templates": result.shift_templates,
        "simulation_start_date": start_label,
        "simulation_config": {
            "rotation_type": rotation_type,
            "num_officers": num_officers,
            "shift_length_hours": shift_length_hours,
            "annual_hours_target": annual_hours_target,
            "shift_starts": shift_starts,
            "apply_department_rules": apply_department_rules,
            "min_per_shift": min_per_shift,
            "simulation_days": simulation_days,
        },
    }


def run_staffing_optimizer(
    *,
    rotation_types: Optional[List[str]] = None,
    officer_counts: Optional[List[int]] = None,
    min_per_shift_options: Optional[List[int]] = None,
    shift_length_hours: Optional[float] = None,
    annual_hours_target: Optional[float] = None,
    shift_starts: Optional[List[str]] = None,
    simulation_days: int = 28,
) -> Dict:
    """Find best rotation/officer-count/min-staffing combination via scenario sweep."""
    from logic.coverage_optimizer import optimize_staffing_scenarios

    return optimize_staffing_scenarios(
        rotation_types=rotation_types,
        officer_counts=officer_counts,
        min_per_shift_options=min_per_shift_options,
        shift_length_hours=shift_length_hours,
        annual_hours_target=annual_hours_target,
        shift_starts=shift_starts,
        simulation_days=simulation_days,
    )


def preview_best_coverage_plans(
    original_officer_id: int,
    request_date: str,
    squad: str,
    shift_start: str,
    *,
    max_plans: int = 5,
) -> Dict:
    """List ranked coverage plans for UI / supervisor review."""
    from logic.coverage_optimizer import load_coverage_policy, search_best_coverage_plans

    policy = load_coverage_policy()
    policy.max_plans = max_plans
    from logic.scheduling import _get_generated_schedule_day_context

    ctx = _get_generated_schedule_day_context(parse_date(request_date))
    plans = search_best_coverage_plans(
        original_officer_id,
        request_date,
        squad,
        shift_start,
        ctx,
        policy=policy,
    )
    return {
        "success": True,
        "count": len(plans),
        "plans": [
            {
                "success": p.success,
                "message": p.message,
                "plan_score": p.plan_score,
                "chain": p.chain,
                "score_components": getattr(p, "score_components", None) or [],
                "steps": [
                    {
                        "step": s.step_number,
                        "original": s.original_officer_name,
                        "replacement": s.replacement_officer_name,
                        "from_shift": s.replacement_shift,
                        "to_shift": s.original_shift,
                    }
                    for s in p.steps
                ],
                "requires_manual": p.requires_manual,
                "failure_reason": p.failure_reason,
            }
            for p in plans
        ],
        "policy": {
            "min_per_shift": policy.min_per_shift,
            "min_by_band": dict(policy.min_by_band),
            "night_minimum": policy.night_minimum,
            "max_cascade_depth": policy.max_cascade_depth,
            "beam_width": policy.beam_width,
            "w_junior": policy.w_junior,
            "w_spare_capacity": policy.w_spare_capacity,
            "w_same_start": policy.w_same_start,
            "w_shallow_chain": policy.w_shallow_chain,
        },
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
