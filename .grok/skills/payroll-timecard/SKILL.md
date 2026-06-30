---
name: payroll-timecard
description: >
  Dodgeville PD payroll and timecard domain — pay periods, locks, overnight
  shifts, holiday markers, period navigation. Use for logic/payroll.py,
  ui/payroll_pages.py, tests/test_payroll.py, tests/test_timecard_schedules.py.
---

# Payroll & Timecard Subagent

## Scope

- `logic/payroll.py` — pay periods, timecard CRUD, lock/unlock, imports
- `ui/payroll_pages.py` — Payroll tab, Timecard tab
- `logic/operations.py` — holidays (`get_holidays_in_range`)
- `tests/test_payroll.py`, `tests/test_timecard_schedules.py`
- Slice: `payroll-timecard` in `slices/registry.py`

## Pay period rules

- 14-day periods aligned to department calendar (`get_pay_period`)
- `lock_pay_period` blocks edits for that period only
- `is_future_pay_period` compares normalized period starts — pass explicit `reference=` in tests
- Overnight shifts: `time_in`/`time_out` span midnight; hours attach to shift **start** period

## Date-sensitive testing

Use fixed reference dates — never rely on `date.today()` in assertions:

```python
from datetime import date
ref = date(2026, 6, 30)
logic.lock_pay_period(ref)
logic.is_future_pay_period(next_start, reference=ref)
```

Use `tests.helpers.reference_today()` or `TEST_REFERENCE_DATE` instead of `date.today()` in assertions.

## Workflow

1. Find slice: `python dev.py slice-map -v` → `payroll-timecard`
2. Fix validators if input invalid; else `logic/payroll.py`
3. Wire UI refresh in `ui/payroll_pages.py` after mutations
4. `python dev.py verify-slice payroll-timecard`
5. `python dev.py check`

## Key symbols

| Area | Functions |
|------|-----------|
| Periods | `get_pay_period`, `get_adjacent_pay_period`, `is_future_pay_period` |
| Lock | `lock_pay_period`, `unlock_pay_period`, `is_pay_period_locked` |
| Timecard | `save_timecard_entry`, `prefill_timecard_from_schedule` |
| Summary | `get_pay_period_hours_summary`, `_summarize_pay_period_hours` |
| Holidays | `get_holidays_in_range`, `ui` ★ markers on timecard |

## Do not

- Lock payroll without supervisor/admin permission check
- Use `date.today()` in unit test expected values without `reference=`
- Put pay calculation rules in UI
