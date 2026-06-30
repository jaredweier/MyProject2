# Known Issues Tracker

> Grok: `@logs/agent_pack/latest.md` · `@docs/AGENT_STABLE.md` · **Sufficiency:** stop when confident; no extra reads unless contradictory or incomplete.

Run `python dev.py audit` to verify fix status. Mark fixed items in this file when resolved.

## Critical

- [x] Approve day-off when officer not scheduled working → `validators.validate_day_off_request` + `process_day_off_request`
- [x] Re-approve same request creates duplicate overrides → guard status == `Pending`
- [x] Night minimum applied to day shifts on Fri/Sat → `validators.applies_night_minimum()`
- [x] No validation on `create_day_off_request` → use validators before insert

## High

- [x] `count_officers_on_shift_on_date` ignores replacements → count replacement_officer_id
- [x] Bump picks most senior (ASC) → DESC (junior first)
- [x] `get_cycle_day` wrong before `ROTATION_BASE_DATE` → reject via `validate_cycle_date`
- [x] Approve succeeds when override insert fails → single transaction in `process_day_off_request`
- [x] Duplicate day-off while manual review pending → `_has_pending_request` includes manual status
- [x] Cascading bump not modeled → `plan_bump_chain`; partial cascades route to manual review

## Medium (UI)

- [x] Requests officer dropdown stale after add officer
- [x] Dashboard stats never refresh
- [x] Gantt fixed to base date only (now uses current cycle window)
- [x] Manual review requests have working approve/reject (`REQUESTABLE_STATUSES` + supervisor override path)
- [x] Replacements show as `covering` in Gantt (distinct color)

## Low

- [x] `cli.py` duplicates `add_officer` SQL
- [x] CLI prints "Failed" for manual review
- [x] Notifications backend (`create_notification`, approve/reject hooks, read/mark-all)
- [x] Shift swap approval backend (`process_shift_swap`, dual overrides, manual review path)
- [x] PDF export backend (`export_schedule_pdf`, `export_payroll_pdf`, `export_requests_pdf`)
- [x] `build.bat` missing logo.png / team_photo.jpg → assets at project root
