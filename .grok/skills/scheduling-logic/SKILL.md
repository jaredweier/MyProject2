---
name: scheduling-logic
description: >
  Dodgeville PD scheduling domain specialist — rotation, bumping, day-off validation,
  night minimum, swap feasibility, and payroll-timecard schedule integration.
  Use for logic.py, validators.py, config.py scheduling rules, and scheduling tests.
---

# Scheduling Logic Subagent

## Scope

- `validators.py` — single source of truth for pre-checks
- `logic.py` — rotation, bumps, overrides, swaps, schedule windows
- `config.py` — `ROTATION_BASE_DATE`, `BUMP_RULES`, `NIGHT_MINIMUM_OFFICERS`
- `tests/test_logic.py`, `tests/test_validators.py`, `tests/test_regressions.py`
- `audit.py` regression checks

## Invariants (never break)

1. 14-day rotation; Squad A days 1,2,5,6,7,10,11
2. Off-rotation day-off requests allowed at submit; supervisor approves/denies
3. Command staff (Chief, Lieutenant): Mon–Fri base schedule; manual overrides allowed
4. Night minimum on Fri/Sat night shifts when **no replacement** found → manual review
5. Bump replacements: same squad, **on-duty only** (scheduled working), exclude command staff; allowed shift bands from active `get_active_bump_rules_by_start()` (custom shift count/starts/lengths). Cascade stops when another on-duty officer remains on the vacated **shift band** (multiple officers may share the same start time — each counted separately).
6. Only `Pending` requests/swaps processed; no duplicate overrides
7. Manual overrides use `create_manual_coverage_override` + `validate_manual_override`

## Workflow

1. Read `.grok/rules/known-issues.md` and `SCHEDULING_RULES.md` for scenario context
2. Reproduce with `python dev.py audit` or targeted unittest
3. Fix in `validators.py` first, then wire `logic.py`
4. Add regression in `tests/test_regressions.py` or `audit.py`
5. Run `python dev.py scenarios` then `python dev.py check`

## Key functions

| Area | Functions |
|------|-----------|
| Rotation | `get_cycle_day`, `get_squad_on_duty`, `is_officer_working_on_day` |
| Bump | `validate_bump_feasibility`, `find_replacement_officer`, `plan_bump_chain`, `suggest_bump_chain` |
| Day-off | `create_day_off_request`, `process_day_off_request` |
| Override | `create_manual_coverage_override`, `_insert_override_record` |
| Swap | `validate_swap_feasibility`, `process_shift_swap` |
| Counts | `count_officers_on_shift_on_date` (includes replacements + `covered_shift_start`) |

## Do not

- Put validation in UI or CLI
- Change bump seniority order without department sign-off
- Apply night minimum to day shifts
