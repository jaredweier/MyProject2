# Architecture Reference

> Grok: `@logs/agent_pack/latest.md` · `@docs/AGENT_STABLE.md` · **Sufficiency:** stop when confident; no extra reads unless contradictory or incomplete.

## Data flow

```
main.py / cli.py
    → logic.py (business rules)
        → validators.py (pre-checks)
        → database.py (SQLite)
    → config.py / models.py
```

## Key tables

- `officers` — roster
- `day_off_requests` — time-off workflow
- `schedule_overrides` — bump assignments (original → replacement)
- `shift_swaps` — swap requests (logic exists, no UI)
- `notifications` — schema only
- `payroll_entries` — schema only

## Request approval flow

1. Validate request is `Pending`
2. Validate officer active and working on `request_date`
3. `validate_bump_feasibility` (night min only if night shift + high-risk night)
4. `find_replacement_officer` (same squad, allowed shifts; seniority not used)
5. Insert `schedule_overrides`, update request status
6. (TODO) Notify replacement officer

## Test strategy

- `tests/test_logic.py` — rotation, bump, payroll
- `tests/test_validators.py` — validation rules
- `tests/test_regressions.py` — audit-backed bug regressions
- `tests/helpers.py` — `TestDatabase` context manager
