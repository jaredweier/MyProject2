"""
Optional Google OR-Tools CP-SAT bridge for multi-day staffing feasibility.

Does **not** replace department bump rules in logic/scheduling.py.
Use for sophisticated what-if / scenario math when `ortools` is installed:

    pip install ortools

Patterns ported from stable public code:
  - google/or-tools examples/python/shift_scheduling_sat.py
    (cover minima, soft excess staffing, transition penalties, named objectives)
  - Timefold EmployeeSchedulingConstraintProvider
    (load-balance unfairness as soft fairness term)

If ortools is missing, helpers return available=False and pure-Python
coverage_optimizer remains the production path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass
class StaffingInstance:
    """Compact multi-day multi-band staffing problem (scenario math only)."""

    officer_ids: List[int]
    days: List[str]  # ISO dates
    bands: List[str]  # shift starts e.g. 06:00
    min_per_band: Dict[str, int] = field(default_factory=dict)
    # officer_id -> day -> available True/False (default True if omitted)
    availability: Dict[int, Dict[str, bool]] = field(default_factory=dict)
    # officer_id -> allowed bands (empty = all)
    allowed_bands: Dict[int, List[str]] = field(default_factory=dict)
    max_days_worked: Optional[int] = None
    min_rest_band_gap: int = 0  # minimum band index distance between consecutive day assignments
    # Soft weights (OR-Tools style linear objective terms)
    w_assignment: int = 1  # lean roster
    w_excess_cover: int = 2  # penalize over-min coverage
    w_unfairness: int = 3  # Timefold-style load balance
    # Band index pairs forbidden day→next (e.g. night then early day)
    # Default: last band (night-ish) cannot be followed by first two bands next day
    forbid_band_transitions: Optional[List[Tuple[int, int]]] = None


@dataclass
class StaffingSolution:
    available: bool
    feasible: bool
    message: str
    # officer_id -> day -> band or None
    assignment: Dict[int, Dict[str, Optional[str]]] = field(default_factory=dict)
    solver: str = "none"
    wall_time_sec: float = 0.0
    # Named soft terms (OR-Tools penalty print pattern)
    objective: Optional[float] = None
    penalties: List[Dict] = field(default_factory=list)
    days_worked: Dict[int, int] = field(default_factory=dict)


def ortools_available() -> bool:
    try:
        from ortools.sat.python import cp_model  # noqa: F401

        return True
    except ImportError:
        return False


def solve_staffing_feasibility(
    instance: StaffingInstance,
    *,
    time_limit_sec: float = 5.0,
) -> StaffingSolution:
    """
    CP-SAT: assign each officer 0..1 band per day such that each (day, band)
    meets min_per_band. Soft: lean cover, excess, fairness, transitions.

    Ported concepts from shift_scheduling_sat.py + Timefold loadBalance.
    """
    if not ortools_available():
        return StaffingSolution(
            available=False,
            feasible=False,
            message="ortools not installed — pip install ortools (optional math engine)",
            solver="unavailable",
        )

    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    officers = list(instance.officer_ids)
    days = list(instance.days)
    bands = list(instance.bands)
    if not officers or not days or not bands:
        return StaffingSolution(
            available=True,
            feasible=True,
            message="empty instance",
            solver="cp-sat",
        )

    n_bands = len(bands)
    band_index = {b: i for i, b in enumerate(bands)}

    # Default night→day forbid: last band → first two bands next day
    forbid = instance.forbid_band_transitions
    if forbid is None and n_bands >= 2:
        night_i = n_bands - 1
        forbid = [(night_i, 0)]
        if n_bands >= 3:
            forbid.append((night_i, 1))

    # x[o,d,b] = 1 if officer o works band b on day d
    x: Dict[Tuple[int, str, str], cp_model.IntVar] = {}
    for o in officers:
        allowed = instance.allowed_bands.get(o) or bands
        for d in days:
            if instance.availability.get(o, {}).get(d, True) is False:
                continue
            for b in bands:
                if b not in allowed:
                    continue
                x[(o, d, b)] = model.NewBoolVar(f"x_{o}_{d}_{b}")

    # At most one band per officer per day
    for o in officers:
        for d in days:
            vars_od = [x[(o, d, b)] for b in bands if (o, d, b) in x]
            if vars_od:
                model.Add(sum(vars_od) <= 1)

    # Coverage minima (hard) + soft excess (OR-Tools weekly_cover + excess_cover_penalties)
    obj_terms: List[cp_model.LinearExprT] = []
    penalty_meta: List[Tuple[str, cp_model.IntVar, int]] = []

    for d in days:
        for b in bands:
            need = max(1, int(instance.min_per_band.get(b, 1)))
            cover = [x[(o, d, b)] for o in officers if (o, d, b) in x]
            if not cover:
                return StaffingSolution(
                    available=True,
                    feasible=False,
                    message=f"no eligible officers for {d} {b}",
                    solver="cp-sat",
                )
            # Avoid MODEL_INVALID: need must not exceed domain upper bound
            if need > len(cover):
                return StaffingSolution(
                    available=True,
                    feasible=False,
                    message=f"infeasible: need {need} on {d} {b} but only {len(cover)} eligible",
                    solver="cp-sat",
                )
            model.Add(sum(cover) >= need)
            # Soft: excess over minimum (domain [0, len(cover)-need])
            if instance.w_excess_cover > 0:
                worked = model.NewIntVar(0, len(cover), f"worked_{d}_{b}")
                model.Add(worked == sum(cover))
                excess = model.NewIntVar(0, len(cover), f"excess_{d}_{b}")
                model.Add(excess == worked - need)
                obj_terms.append(excess * instance.w_excess_cover)
                penalty_meta.append((f"excess_cover({d},{b})", excess, instance.w_excess_cover))

    # Days worked per officer + max days hard
    days_worked_vars: Dict[int, cp_model.IntVar] = {}
    for o in officers:
        day_worked = []
        for d in days:
            vars_od = [x[(o, d, b)] for b in bands if (o, d, b) in x]
            if not vars_od:
                continue
            w = model.NewBoolVar(f"worked_{o}_{d}")
            model.Add(sum(vars_od) >= 1).OnlyEnforceIf(w)
            model.Add(sum(vars_od) == 0).OnlyEnforceIf(w.Not())
            day_worked.append(w)
        if day_worked:
            dw = model.NewIntVar(0, len(days), f"days_worked_{o}")
            model.Add(dw == sum(day_worked))
            days_worked_vars[o] = dw
            if instance.max_days_worked is not None:
                model.Add(dw <= int(instance.max_days_worked))

    # Timefold-style unfairness: max_days - min_days soft
    if instance.w_unfairness > 0 and len(days_worked_vars) >= 2:
        max_dw = model.NewIntVar(0, len(days), "max_days_worked")
        min_dw = model.NewIntVar(0, len(days), "min_days_worked")
        model.AddMaxEquality(max_dw, list(days_worked_vars.values()))
        model.AddMinEquality(min_dw, list(days_worked_vars.values()))
        unfair = model.NewIntVar(0, len(days), "unfairness")
        model.Add(unfair == max_dw - min_dw)
        obj_terms.append(unfair * instance.w_unfairness)
        penalty_meta.append(("load_balance_unfairness", unfair, instance.w_unfairness))

    # Transition forbids day d → d+1 (OR-Tools penalized_transitions / hard ban)
    if forbid:
        for o in officers:
            for di in range(len(days) - 1):
                d0, d1 = days[di], days[di + 1]
                for bi, bj in forbid:
                    if bi >= n_bands or bj >= n_bands:
                        continue
                    b_i, b_j = bands[bi], bands[bj]
                    if (o, d0, b_i) not in x or (o, d1, b_j) not in x:
                        continue
                    # Cannot have both true
                    model.AddBoolOr([x[(o, d0, b_i)].Not(), x[(o, d1, b_j)].Not()])

    # Optional band-index rest gap between consecutive worked days
    # Same band allowed; different bands must be at least min_rest_band_gap indices apart.
    if instance.min_rest_band_gap > 0:
        for o in officers:
            for di in range(len(days) - 1):
                d0, d1 = days[di], days[di + 1]
                for b0 in bands:
                    for b1 in bands:
                        if (o, d0, b0) not in x or (o, d1, b1) not in x:
                            continue
                        if b0 == b1:
                            continue
                        if abs(band_index[b0] - band_index[b1]) < instance.min_rest_band_gap:
                            model.AddBoolOr([x[(o, d0, b0)].Not(), x[(o, d1, b1)].Not()])

    # Soft: minimize total assignments (lean)
    if instance.w_assignment > 0 and x:
        obj_terms.append(sum(x.values()) * instance.w_assignment)

    if obj_terms:
        model.Minimize(sum(obj_terms))
    elif x:
        model.Minimize(sum(x.values()))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_sec)
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return StaffingSolution(
            available=True,
            feasible=False,
            message=f"infeasible or timeout (status={solver.StatusName(status)})",
            solver="cp-sat",
            wall_time_sec=solver.WallTime(),
        )

    assignment: Dict[int, Dict[str, Optional[str]]] = {o: {d: None for d in days} for o in officers}
    for (o, d, b), var in x.items():
        if solver.Value(var) == 1:
            assignment[o][d] = b

    days_worked_out = {o: int(solver.Value(v)) for o, v in days_worked_vars.items()}
    penalties: List[Dict] = []
    for name, var, weight in penalty_meta:
        val = int(solver.Value(var))
        if val > 0:
            penalties.append(
                {
                    "name": name,
                    "value": val,
                    "weight": weight,
                    "contribution": val * weight,
                }
            )

    return StaffingSolution(
        available=True,
        feasible=True,
        message=(
            f"feasible · obj={solver.ObjectiveValue():.0f} · {len(penalties)} soft term(s) active"
            if penalties
            else "feasible"
        ),
        assignment=assignment,
        solver="cp-sat",
        wall_time_sec=solver.WallTime(),
        objective=float(solver.ObjectiveValue()) if obj_terms else None,
        penalties=penalties,
        days_worked=days_worked_out,
    )


def demo_week_instance(
    n_officers: int = 8,
    n_days: int = 7,
    bands: Optional[Sequence[str]] = None,
    min_per_band: Optional[Dict[str, int]] = None,
) -> StaffingInstance:
    """Synthetic week for free math demos (no DB)."""
    bands = list(bands or ["06:00", "10:00", "15:00", "19:00"])
    mins = dict(min_per_band or {b: 1 for b in bands})
    mins.setdefault("19:00", 2)  # night min flavor
    officers = list(range(1, n_officers + 1))
    days = [f"2026-07-{d:02d}" for d in range(1, n_days + 1)]
    return StaffingInstance(
        officer_ids=officers,
        days=days,
        bands=bands,
        min_per_band=mins,
        max_days_worked=5,
        w_assignment=1,
        w_excess_cover=2,
        w_unfairness=4,
    )


def format_solution_report(sol: StaffingSolution) -> str:
    """OR-Tools-style human report of feasibility + named soft penalties."""
    lines = [
        f"CP-SAT: available={sol.available} feasible={sol.feasible} solver={sol.solver}",
        f"  {sol.message}",
        f"  wall={sol.wall_time_sec:.3f}s",
    ]
    if sol.objective is not None:
        lines.append(f"  objective={sol.objective:.1f}")
    if sol.penalties:
        lines.append("  Soft penalties (name · value · weight · contrib):")
        for p in sol.penalties:
            lines.append(f"    • {p.get('name')}: {p.get('value')} × {p.get('weight')} = {p.get('contribution')}")
    elif sol.feasible:
        lines.append("  No soft penalties active (balanced lean cover).")
    if sol.days_worked:
        vals = list(sol.days_worked.values())
        lines.append(f"  Days worked range: min={min(vals)} max={max(vals)} (unfairness={max(vals) - min(vals)})")
    return "\n".join(lines)
