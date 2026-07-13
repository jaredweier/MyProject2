# Math/logic learnings (any public OR/math source)

## 2026-07-09T08:49:50.435785+00:00 — improve-batch
Hours vs 7k-style threshold meter on timecards using work_period_days scaling 171*(days/28)

## 2026-07-09T08:52:26.093204+00:00 — plan-explain
logic/plan_explain.explain_coverage_plans formats multi-plan scores/steps for supervisors (OR explainability)
_  https://developers.google.com/optimization_

## 2026-07-09T09:08:26.433712+00:00 — timefold-hard-soft
Hard/soft constraint split is standard in modern roster solvers (Timefold, OR-Tools CP-SAT). Chronos: hard = night min, rest, squad duty; soft = junior-first bump score, plan ranking. Keep explain_coverage_plans for supervisor trust of soft scores.
_  https://docs.timefold.ai/_

## 2026-07-09T09:10:25.369101+00:00 — ortools-shift-scheduling-sat-code
Read google/or-tools shift_scheduling_sat.py: work[e,s,d] bools; exactly_one per day; soft sequence via negated_bounded_span + penalty literals; soft sum with IntVar excess; night→morning forbidden (cost 0); cover demand hard min + excess penalty; objective minimize weighted penalties; solution printer lists each violated penalty by name. Chronos should keep named soft components in plan_explain (done) and optional CP-SAT for multi-day cover.
_  https://github.com/google/or-tools/blob/stable/examples/python/shift_scheduling_sat.py_

## 2026-07-09T09:10:25.761946+00:00 — timefold-constraint-provider-java
Read EmployeeSchedulingConstraintProvider.java: defineConstraints returns HARD then SOFT array. HARD: requiredSkill, noOverlappingShifts, atLeast10HoursBetweenTwoShifts, oneShiftPerDay, unavailableEmployee. SOFT: undesiredDay (penalize minutes), desiredDay (reward), balanceEmployeeShiftAssignments via loadBalance unfairness. Planning entity Shift + employee variable. Chronos maps hard to filters in list_scored_replacements; soft to w_junior/w_spare/w_same; certs ≈ requiredSkill.
_  https://github.com/TimefoldAI/timefold-quickstarts/blob/stable/java/employee-scheduling/src/main/java/org/acme/employeescheduling/solver/EmployeeSchedulingConstraintProvider.java_

## 2026-07-09T09:20:30.881824+00:00 — ortools-cpsat-port-chronos
Ported shift_scheduling_sat patterns into logic/cp_sat_bridge: hard cover minima, soft excess cover, Timefold-style load_balance unfairness (max-min days), night→early transition forbids, named penalty report via format_solution_report. Simulator CP-SAT week button. Coverage optimizer now soft-scores low OT (fairness) + transition soft weight. Dual OT ledger hours_offered vs worked. TeleStaff rank_open_shift_candidates on open shifts UI.
_  https://github.com/google/or-tools/blob/stable/examples/python/shift_scheduling_sat.py_
