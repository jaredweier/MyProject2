# Known Issues Tracker

> Run `python dev.py audit` for historical regressions. **Open items below are real — not all fixed.**

## Open (product / design)

- [ ] **Bump pick ignores seniority** — `find_replacement_officer` takes first eligible same-squad officer; seniority only orders vacation bulk approve (`logic/scheduling.py`)
- [ ] **Partial bump cascades** — incomplete chains route to manual review instead of auto-complete (`plan_bump_chain`)
- [x] **Legacy bid tables** — empty `shift_bid_slots` / `shift_bids` dropped on init; new DBs skip creation (`database.py`)
- [ ] **analytics.py outside logic package** — reports slice split across `analytics.py` and `logic/dashboard.py` (move planned)
- [ ] **Monolith pages** — `ui/feature_pages.py`, `ui/schedule_pages.py` still large; `cli/roster_cmds.py`, `ui/payroll_stub_mixin.py` split started
- [ ] **LDAP optional** — `logic/ldap_auth.py` works when configured; not department-tested by default

## Open (agent / process) — fixed 2026-07-08

- [x] Stale `architecture.md` claimed swaps/notifications/payroll unimplemented
- [x] `known-issues.md` all `[x]` masked open design gaps
- [x] Layered gates (`preflight` green, `check` red) — unified `scripts/verify.py`
- [x] Demo `must_change_password` cleared on existing DBs — `_migrate_demo_password_policy`
- [x] Portable/CI could skip ship gate — `verify --tier full` + rust assert

## Critical (fixed — audit AUD-001..010)

- [x] Approve day-off when officer not scheduled working
- [x] Re-approve duplicate overrides
- [x] Night minimum on day shifts Fri/Sat
- [x] No validation on `create_day_off_request`
- [x] Replacement count in coverage
- [x] `get_cycle_day` before base date
- [x] Approve when override insert fails (transaction)
- [x] Duplicate during manual review
- [x] Cascading bump modeled (`plan_bump_chain`)

## Medium UI (fixed)

- [x] Requests officer dropdown stale
- [x] Dashboard stats refresh
- [x] Gantt cycle window
- [x] Manual review approve/reject
- [x] Replacements show as covering in Gantt
