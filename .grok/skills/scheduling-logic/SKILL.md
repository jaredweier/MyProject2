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
2. Day-off only when officer's squad is on duty that day
3. Night minimum only for **night** shifts on Fri/Sat
4. Bump replacements: same squad, allowed shift numbers, junior first (`seniority_rank DESC`)
5. Only `Pending` requests/swaps processed; no duplicate overrides
6. Manual overrides use `create_manual_coverage_override` + `validate_manual_override`

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
