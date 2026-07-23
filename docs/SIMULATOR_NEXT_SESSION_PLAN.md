# Simulator Learning Plan — Next Session Mandatory Read

**Written:** 2026-07-22

## User intent

- The six-officer exercise was a diagnostic test case, not department policy or a source of universal defaults.
- “Learning” means adding general modeling, optimization, explanation, and verification capabilities—not training a model or silently inferring future policy.
- Do not preserve these as defaults: six officers, eight-hour shifts, 2008±20 hours, tested start times, the 16-day patterns, an eight-hour bump span, duplicate-start avoidance, Officer 6 handling, or workbook dates.
- Scenario constraints and preferences apply only when explicitly entered for that simulation.

## Current workspace and proof

- Workspace: `C:\Users\Windows\Desktop\Chronos Command GPT`.
- Working tree is uncommitted.
- The session proved these general capabilities: exact shift lengths; continuous coverage; overlap credit; overnight windows; multiple same-cycle patterns and inverses; cycle-day officer starts; optional duplicate-start minimization; independent replay validation.
- Latest `python dev.py verify --tier fast`: PASS.
- Full ship gate was not run. Do not call this shipped.

## Immediate cleanup

- Audit `logic/staffing_cpsat.py::solve_cycle_day_starts` first.
- `max_start_variation_hours=8.0` came from the scenario and must not remain a hidden default. Make the default unrestricted (`None`) and enforce it only when explicitly supplied.
- Keep `prefer_unique_daily_starts=False` by default. It is an optional preference, not policy.
- Keep the six-officer case only as a named regression fixture with every input explicit.
- An explicitly entered start-span limit uses linear operational time: `abs(startA-startB)`. With limit 8, 06:00/14:00 is allowed and 06:00/22:00 is not. This defines the optional input’s math, not a universal limit.
- Temporary workbook/export logic under `C:\tmp` must never become product policy.

## Required product model

Every input needs one explicit role:

1. **Hard constraint** — every returned schedule must satisfy it.
2. **Soft preference** — improve it when possible; never report it as required.
3. **Open variable** — solver chooses it.

Never conflate roles:

- Allowed starts are a search domain, not required staffed bands.
- Preferred starts are not allowed-start restrictions.
- Coverage windows may be satisfied by any overlapping shift.
- Start consistency is not a rest rule.
- Duplicate-start avoidance is not minimum staffing.

## Accuracy architecture

- Use one canonical time model for starts, ends, midnight crossing, overlap, rest, coverage, and weekday anchoring.
- Validate every solver result independently through `logic/coverage_timeline.py`.
- Validate the full repeating horizon: `LCM(rotation cycle length, 7)` for weekday constraints.
- Preserve the explicit anchor date through every wrapper and replay path.
- Preserve solver-owned `officer_home_starts` and `officer_cycle_starts`; never silently rebalance a proven result.
- Return exact failure evidence: date, interval, requirement, required count, actual count, and implicated assumption.
- Distinguish: proven optimal; feasible/improving; feasible/time-limited; proven infeasible; unsupported; heuristic-only.
- Never present timeout, unknown, or unsupported as infeasible.

## Optimization architecture

- Use ordered/lexicographic objectives:
  1. satisfy hard constraints;
  2. minimize coverage shortfall only in diagnostic relaxation mode;
  3. meet annual-hour and fairness requirements;
  4. minimize disruptive start changes;
  5. minimize same-time starts when requested;
  6. minimize unnecessary staffing/overcoverage;
  7. apply remaining user-ranked preferences.
- Make the soft-priority order visible and editable.
- Separate optional start-stability controls:
  - maximum start-time span per officer;
  - maximum change between consecutive worked shifts;
  - maximum distinct starts per officer;
  - preferred/home start;
  - penalty per start change;
  - duplicate-start penalty by day.
- User limits are hard constraints; preferences are objective penalties.
- Add symmetry breaking so officer-renamed copies are not repeatedly solved.
- Support anytime solving: return the first independently verified feasible result, then continue improving while the UI remains responsive.

## Efficiency

- Run preflight math before CP-SAT: total capacity, minimum coverage-hours, shift-length bounds, duty fraction versus annual target, rest/start impossibilities, and common-cycle compatibility.
- Prune impossible officer-count, length, pattern, and start-domain combinations once—not once per start pack.
- Cache parsed rotations, duty vectors, overlap matrices, LCM horizons, and repeated feasibility results.
- Warm-start from the prior feasible schedule when one preference changes.
- Eliminate officer-label permutation duplicates.
- Keep Cancel reachable and the app responsive.
- Replace raw-enumeration time estimates with solver-aware status and bounded estimates.

## User experience

- Guided order: staffing/hours → coverage → allowed lengths/starts → rotations → preferences.
- Use `Required`, `Preferred`, and `Let simulator decide` where meaningful.
- Explicitly label Allowed / Required / Preferred starts in both UI and payloads.
- Before solving, show a concise **Simulator understood** summary.
- During solving, show phase, elapsed time, verified best result, improvements, and Cancel.
- Offer verified alternatives: most consistent starts, fewest duplicates, simplest rotation, closest annual match, least overcoverage.
- Add **Why this schedule?**: rotations/phases, officer start sets, coverage explanation, compromised preferences, and optimality status.
- For infeasible inputs, identify a minimal relaxation instead of generic suggestions.
- Retain the date-across Shift Grid concept: assignments, shift totals, applicable constraint rows, and officers OFF. Green=applicable pass; red=applicable failure; white=not required.

## Regression suite

- Convert the six-officer exercise into a named fixture; do not assert exact officer labels unless identity is constrained.
- Cover:
  - shifts starting before and overlapping a required window;
  - overnight windows using next-day assignments;
  - CP-SAT/replay phase translation;
  - allowed starts not becoming required bands;
  - unlocked per-band minimum remaining zero;
  - cycle-day starts surviving replay;
  - multiple patterns/inverses with one cycle length;
  - optional start-span enforcement, including 06:00/22:00 rejection at limit 8;
  - duplicate-start preference enabled and disabled;
  - no hidden bump limit when omitted;
  - infeasible versus timeout/unsupported status;
  - `LCM(cycle,7)` coverage;
  - independent replay matching solver claims.

## Implementation order

1. **COMPLETE 2026-07-22:** Remove hidden scenario defaults; expose optional preference fields end-to-end.
   - `max_start_variation_hours` now defaults to unrestricted (`None`) and is enforced only when entered.
   - Chronos exposes the limit as an optional hard constraint using linear operational time.
   - Duplicate-start minimization is an explicit soft preference and remains off by default.
   - Proof: focused omitted-vs-explicit regression, static UI tests, `verify --tier fast`, and live `/simulator` control interaction.
2. **COMPLETE 2026-07-22:** Add typed constraint/preference/open-variable payloads and **Simulator understood**.
   - Canonical typed payload is normalized in the optimizer and preserved in results.
   - Chronos builds roles from actual form state; allowed starts remain an open-variable domain.
   - Search Plan and active-search summary show Required / Preferred / Simulator decides.
   - Proof: focused role-contract test, static UI tests, `verify --tier fast`, live Search Plan interaction.
3. **COMPLETE 2026-07-22:** Implemented bounded lexicographic objectives and visible preference ordering.
4. **COMPLETE 2026-07-22:** Added officer symmetry breaking and prior-result warm starts; retained preflight feasibility and parsed/model-result caches.
5. **COMPLETE 2026-07-22:** Added honest optimal/feasible-time-limited/infeasible/unknown/cancelled statuses on the existing responsive process-isolated anytime path.
6. **COMPLETE 2026-07-22:** Preserved exact coverage-failure evidence and used measured shortfalls for minimal-relaxation suggestions.
7. **COMPLETE 2026-07-22:** Made quick questions primary, moved the full form under Advanced requirements, and added verified alternatives, OT estimates, heatmaps, and plain-language reasons.
8. **COMPLETE 2026-07-22:** Expanded regressions through the canonical typed payload, status, cert, court/training, and six-officer scenarios; live Chronos proofs covered the primary controls and Search Plan/result flow. Final ship gate recorded in `logs/last_verify.json`.

### Tier A audit progress — 2026-07-23

- Apply preview and implementation no longer trust `success` or stored metrics alone.
- Python simulator results retain raw assignment evidence for independent replay.
- Apply-time verification recalculates daily-band, annual-hours, 24/7, and extra-window
  hard claims and fails closed when proof evidence is absent.
- Forged hard-coverage evidence is rejected before defaults, officers, or snapshots mutate.
- Focused apply/status/math tests and `verify --tier fast` passed.
- Monthly publish verification remains open. Full ship gate was not run.

## Trust and next action

- Unit tests do not prove the Chronos UI works. Test the actual `/simulator` path and inspect the produced schedule.
- Verify solver output with the independent timeline evaluator.
- Use `python dev.py verify --tier fast` during work.
- Before shipped/done: `python dev.py verify --tier check` and confirm `logs/last_verify.json` has `honest_gate: true`.
- Update this file, `logs/NEXT_SESSION_BRIEF.md`, and `docs/SIMULATOR_OVERHAUL_PLAN.md` after each phase.
- If the next user says **continue**, begin the Tier A independent-verifier and status-translation audit recorded in `logs/NEXT_SESSION_BRIEF.md`. Hidden scenario defaults are already removed; do not redo that completed work or revive Officer 6/workbook-specific behavior.
