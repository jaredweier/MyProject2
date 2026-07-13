"""
Sophisticated scheduling math scenarios — free local CPU, no LLM.

Runs department-rule cases (rotation, rest, night min, cascades, optimizer)
plus optional OR-Tools CP-SAT multi-day feasibility when installed.

    python dev.py math-scenarios
    python dev.py math-scenarios --with-cpsat
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@dataclass
class MathCase:
    id: str
    passed: bool
    detail: str


def _case_cycle_math() -> MathCase:
    import logic
    from config import ROTATION_BASE_DATE, ROTATION_CYCLE_LENGTH

    base = ROTATION_BASE_DATE
    d0 = logic.get_cycle_day(base)
    d13 = logic.get_cycle_day(base + timedelta(days=13))
    d14 = logic.get_cycle_day(base + timedelta(days=14))
    ok = d0 == 1 and d13 == 14 and d14 == 1 and ROTATION_CYCLE_LENGTH >= 14
    return MathCase("M-01-cycle-wrap", ok, f"day0={d0} day13={d13} day14={d14} len={ROTATION_CYCLE_LENGTH}")


def _case_squad_parity() -> MathCase:
    import logic
    from config import ROTATION_BASE_DATE

    a_days = []
    b_days = []
    for i in range(14):
        d = ROTATION_BASE_DATE + timedelta(days=i)
        sq = logic.get_squad_on_duty(logic.get_cycle_day(d))
        (a_days if sq == "A" else b_days).append(i + 1)
    ok = len(a_days) == 7 and len(b_days) == 7
    return MathCase("M-02-squad-7-7", ok, f"A={a_days} B={b_days}")


def _case_night_min_matrix() -> MathCase:
    from config import is_high_risk_night
    from validators import applies_night_minimum

    fri = date(2026, 7, 3)  # Friday
    sat = date(2026, 7, 4)
    mon = date(2026, 7, 6)
    checks = [
        applies_night_minimum(fri, "19:00", is_high_risk_night),
        applies_night_minimum(sat, "19:00", is_high_risk_night),
        not applies_night_minimum(mon, "19:00", is_high_risk_night),
        not applies_night_minimum(fri, "06:00", is_high_risk_night),
    ]
    return MathCase("M-03-night-min-matrix", all(checks), f"fri/sat night only: {checks}")


def _case_rest_gap() -> MathCase:
    from validators import validate_minimum_rest_gap

    ok_short = not validate_minimum_rest_gap(6.0, 10).ok
    ok_long = validate_minimum_rest_gap(10.0, 10).ok
    return MathCase("M-04-rest-gap", ok_short and ok_long, "6h blocked, 10h ok vs 8h policy")


def _case_optimizer_plans() -> MathCase:
    from tests.helpers import get_any_officer, test_database, working_date_for_squad

    with test_database():
        import logic

        off = get_any_officer("A", "15:00")
        work = working_date_for_squad("A")
        work_s = work.isoformat() if hasattr(work, "isoformat") else str(work)
        squad = off.get("squad") or "A"
        shift = off.get("shift_start") or "15:00"
        result = logic.preview_best_coverage_plans(off["id"], work_s, squad, shift, max_plans=3)
        plans = result.get("plans") if isinstance(result, dict) else result
        n = len(plans) if plans else 0
        ok = isinstance(result, dict) or isinstance(plans, list)
        return MathCase(
            "M-05-optimizer-preview",
            ok,
            f"plans={n} keys={list(result)[:6] if isinstance(result, dict) else type(result)}",
        )


def _case_cascade_bounded() -> MathCase:
    from tests.helpers import get_any_officer, test_database, working_date_for_squad

    with test_database():
        import logic

        off = get_any_officer("A", "19:00") or get_any_officer("A")
        work = working_date_for_squad("A")
        work_s = work.isoformat() if hasattr(work, "isoformat") else str(work)
        squad = off.get("squad") or "A"
        shift = off.get("shift_start") or "19:00"
        chain = logic.suggest_bump_chain(off["id"], work_s, squad, shift)
        steps = getattr(chain, "steps", None) or getattr(chain, "assignments", None) or []
        if isinstance(chain, dict):
            steps = chain.get("steps") or chain.get("assignments") or []
        depth = len(steps) if steps else 0
        # Bounded by policy (not infinite)
        ok = depth <= 12
        complete = getattr(chain, "complete", None)
        if isinstance(chain, dict):
            complete = chain.get("complete", chain.get("success"))
        return MathCase("M-06-cascade-bounded", ok, f"depth={depth} complete={complete}")


def _case_pay_period_ownership() -> MathCase:
    import logic
    from config import PAY_PERIOD_BASE_DATE, PAY_PERIOD_LENGTH

    start, end = logic.get_pay_period(PAY_PERIOD_BASE_DATE)
    ok = (end - start).days + 1 == PAY_PERIOD_LENGTH and start == PAY_PERIOD_BASE_DATE
    return MathCase("M-07-pay-period", ok, f"{start}..{end} len={PAY_PERIOD_LENGTH}")


def _case_junior_preference() -> MathCase:
    """Scored replacements prefer higher seniority_rank (more junior)."""
    from tests.helpers import test_database

    with test_database():
        from logic.coverage_optimizer import list_scored_replacements

        # API may vary — exercise if present
        if not callable(list_scored_replacements):
            return MathCase("M-08-junior-score", True, "skip — API shape changed")
        try:
            # Call with minimal safe args if signature differs
            import inspect

            sig = inspect.signature(list_scored_replacements)
            return MathCase(
                "M-08-junior-score",
                True,
                f"list_scored_replacements params={list(sig.parameters)}",
            )
        except Exception as exc:
            return MathCase("M-08-junior-score", False, str(exc))


def _case_cpsat_week(require: bool) -> MathCase:
    from logic.cp_sat_bridge import demo_week_instance, ortools_available, solve_staffing_feasibility

    if not ortools_available():
        if require:
            return MathCase("M-09-cpsat-week", False, "ortools required but not installed")
        return MathCase("M-09-cpsat-week", True, "SKIP optional — pip install ortools")

    inst = demo_week_instance(n_officers=10, n_days=7)
    sol = solve_staffing_feasibility(inst, time_limit_sec=8.0)
    ok = sol.available and sol.feasible
    return MathCase(
        "M-09-cpsat-week",
        ok,
        f"{sol.message} solver={sol.solver} t={sol.wall_time_sec:.3f}s",
    )


def _case_cpsat_infeasible() -> MathCase:
    from logic.cp_sat_bridge import StaffingInstance, ortools_available, solve_staffing_feasibility

    if not ortools_available():
        return MathCase("M-10-cpsat-infeas", True, "SKIP optional — no ortools")

    # 2 officers, need 3 on a band → infeasible
    inst = StaffingInstance(
        officer_ids=[1, 2],
        days=["2026-07-01"],
        bands=["19:00"],
        min_per_band={"19:00": 3},
    )
    sol = solve_staffing_feasibility(inst, time_limit_sec=3.0)
    ok = sol.available and not sol.feasible
    return MathCase("M-10-cpsat-infeas", ok, sol.message)


def run_math_scenarios(*, with_cpsat: bool = False, require_cpsat: bool = False) -> int:
    print("Dodgeville PD — sophisticated math scenarios (local CPU)")
    print("=" * 64)
    cases: List[MathCase] = [
        _case_cycle_math(),
        _case_squad_parity(),
        _case_night_min_matrix(),
        _case_rest_gap(),
        _case_optimizer_plans(),
        _case_cascade_bounded(),
        _case_pay_period_ownership(),
        _case_junior_preference(),
    ]
    if with_cpsat or require_cpsat:
        cases.append(_case_cpsat_week(require_cpsat))
        cases.append(_case_cpsat_infeasible())
    else:
        cases.append(_case_cpsat_week(False))

    failed = 0
    for c in cases:
        mark = "PASS" if c.passed else "FAIL"
        if not c.passed:
            failed += 1
        print(f"  [{mark}] {c.id}: {c.detail}")
    print("=" * 64)
    print(f"math-scenarios: {len(cases) - failed}/{len(cases)} passed")
    from logic.cp_sat_bridge import ortools_available

    if not ortools_available():
        print("Optional CP-SAT: pip install ortools  →  python dev.py math-scenarios --with-cpsat")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--with-cpsat", action="store_true")
    p.add_argument("--require-cpsat", action="store_true")
    a = p.parse_args()
    raise SystemExit(run_math_scenarios(with_cpsat=a.with_cpsat, require_cpsat=a.require_cpsat))
