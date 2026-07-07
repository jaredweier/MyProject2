# Session Handoff — Dodgeville PD Scheduler

**Purpose:** Living memory for agents (and humans) to resume work without re-reading full chat history.
**Human-readable mirror:** [`PROJECT_README.md`](PROJECT_README.md) — keep both in sync when updating.
**Update this file** when you finish a meaningful chunk of work (features, fixes, renames, perf passes).

**Last updated:** 2026-07-06
**Verification:** `python dev.py check` — **201+ tests**, audit 10/10 · `ui-diff` 78/78 baselines · pre-commit installed

---

## Quick resume

| Item | Value |
|------|--------|
| Run GUI | `python main.py` |
| Demo logins | `admin` / `admin`, `supervisor` / `supervisor`, `officer` / `officer` |
| Auto-login | **Off by default** — set `SCHEDULER_AUTO_LOGIN=1` for dev skip-login |
| Full verify | `python dev.py check` |
| Domain rules | `SCHEDULING_RULES.md`, `.grok/rules/known-issues.md` |

**User workflow lately:** iterative live GUI testing — launch app, fix feedback, re-run `dev.py check`, relaunch.

**UI hazard (2026-07-06):** Do **not** bind `<Map>` (or other show/configure events) to `apply_main_window_layout()` in `ui/window_layout.py`. That function toggles `state("normal")` → `state("zoomed")` and steals focus (`focus_force`, `-topmost`); a Map feedback loop froze Windows (rapid popups, Task Manager unusable). Layout runs **once** at login/bootstrap only; `_applied_for` guard in `window_layout.py`. Before `ui-live` / `ui-observe --live`, confirm the guard is still present.

---

## Recent session work (2026-07)

### Window layout freeze fix (2026-07-06)

| Change | Purpose |
|--------|---------|
| `ui/session_pages.py` | Removed `<Map>` → `apply_main_window_layout` binding (feedback loop) |
| `ui/window_layout.py` | `_applied_for` set — maximize/focus at most once per root window |

**Recovery if loop returns:** Admin CMD `taskkill /F /IM python.exe`; delete `logs/ui_live_test/.running.lock` if stale. Prefer `python dev.py ui-smoke` (headless) until fixed.

### Agent tooling, OSS integration, usage minimization (2026-07-06)

| Artifact | Purpose |
|----------|---------|
| `.gitignore` | Keep logs, db, dist, terminals out of git |
| `.pre-commit-config.yaml` | preflight on commit |
| `.github/workflows/ci.yml` | Free CI on push (needs `setup_github.ps1`) |
| `opencode.json` + `.opencode/` | OpenCode agents/commands; compaction + image limits |
| `docs/USAGE_MINIMIZATION.md` | Human/agent guide to reduce LLM spend |
| `.grok/skills/cost-efficient-workflow/` | Agent skill: free gates first |
| `python dev.py ui-diff --quick` | Nav/login PNGs only (01–15) |
| `tests/ui_snapshots/baseline/` | 78 UI regression baselines seeded |
| `scripts/install_opencode.ps1` | winget/npm/scoop/GitHub release download |
| `scripts/setup_github.ps1` | Link remote + stage CI paths |

**Usage ladder:** `preflight` → `verify-slice` → `ui-diff --quick` → `check` → `ui-observe` (no `--live`) → vision only if needed.

**Blocked (user action):** GitHub push (no `origin` remote); OpenCode install if no network/package manager.

### Vertical slice architecture (complete)

Brownfield VSA for all shipped features + future work. Strategy doc: [`docs/VERTICAL_SLICES.md`](VERTICAL_SLICES.md).

| Artifact | Purpose |
|----------|---------|
| `slices/registry.py` | 14 slices (`complete`), `SHARED_KERNEL`, optimized per-slice fields |
| `python dev.py slice-map -v` | Find slice by capability; see `touch_together` files |
| `python dev.py slice-check` | Resolve logic symbols, UI mixins, tests, scenarios |
| `tests/test_vertical_slices.py` | Registry integrity (5 tests) |

**Evaluation:** UI slice-aligned (9 page mixins + `ui/profile_dialog.py`). Logic package split complete — all `future_module` targets landed. `import logic` unchanged via `logic/__init__.py`.

**Logic package (2026-07):**

| Module | Slice |
|--------|--------|
| `logic/officers.py` | roster |
| `logic/scheduling.py` | rotation, bumping, matrix |
| `logic/requests.py` | day-off, swaps, notifications |
| `logic/snapshots.py` | monthly calendars, sync, overrides |
| `logic/payroll.py` | payroll, timecard |
| `logic/users.py` | auth, app users |
| `logic/operations.py` | holidays, availability, open shifts, settings |
| `logic/exports.py` | PDF/CSV/iCal export wrappers |
| `logic/dashboard.py` | dashboard + analytics delegates |
| `logic/_core.py` | thin shim (re-exports exports + dashboard) |

Tooling: `scripts/extract_logic_requests.py`, `scripts/extract_logic_modules.py`, `scripts/extract_logic_core_trim.py`

**Agent rule:** When changing a feature, find its slice → edit only `touch_together` files (+ shared kernel if cross-cutting) → run slice `verify` + `python dev.py check`.

**UI fix during verify:** `ui/schedule_pages.py` `_refresh_monthly_sync_cta` — safe pack fallback (fixed `ui-smoke` on Current Monthly Schedule tab).

### Industry roadmap — Tier 1, Visual/UX, Phases A–C (complete)

Implemented the full backlog from the public-safety scheduling UX review (coverage-at-a-glance, LE rules, self-service polish).

**Tier 1 (logic + UI):**

| Feature | Key symbols |
|---------|-------------|
| Coverage gap board | `analytics.get_coverage_gap_board()`, dashboard card + alerts |
| FLSA / hours watch | `analytics.get_hours_watch()`, dashboard + My Profile |
| Minimum rest (8h) | `config.MIN_REST_HOURS_BETWEEN_SHIFTS`, `validators.validate_minimum_rest_gap()`, manual-review override path |
| Court / training types | `DAY_OFF_REQUEST_TYPES`, Gantt colors, `REQUEST_TYPE_SCHEDULE_STATUS` |
| Equitable OT ledger | `analytics.get_equitable_ot_ledger()`, Ops Reports section |
| Schedule-published notify | `_notify_schedule_published()` after `sync_updated_schedule()` |
| Officer My Week | `get_officer_schedule_window()`, dashboard card for officer role |

**Visual & UX:** on-duty-now strip, consolidated alert stack, clickable stat cards, approve confirmation modal with bump summary, ledger type + status filter chips, roster title badges + pay-period hours on rows, global `STATUS_COLORS`, monthly sync empty-state CTA, Gantt empty-state CTA, officer-simplified Command Post quick actions.

**Phases A–C** overlap the above (dashboard ops clarity, LE scheduling rules, self-service home + open-shift polish).

**Gotcha:** Minimum rest violations route to **Pending Manual Review**; supervisor approve uses override messaging (see `tests/test_regressions.py`).

---

## Recent session work (2026-06)

### Payroll — period totals and breakdown

- **Logic:** `get_pay_period_hours_summary()`, `_summarize_pay_period_hours()` in `logic.py`
- **UI:** Prominent pay-period hour total on Payroll tab; **More Details** expandable section (`ExpandableSection` in `ui/widgets.py`)
- **Tests:** `tests/test_payroll.py`

### Schedule naming and behavior

| Old label | Current label | Behavior |
|-----------|---------------|----------|
| Base Rotation | **Original Monthly Schedule** | Auto-generated from rotation/squad/shift on first view; **locked** after generation (`ensure_original_monthly_schedule()` in `logic.py`) |
| Live Duty Roster | **Current Monthly Schedule** | Reflects approved time off, bumps, swaps, manual edits; **Sync Current Monthly Schedule** action |

- **UI:** `ui/schedule_pages.py`, nav labels in `ui/theme.py`
- **Cell display:** Officer name + shift time prominent; squad shown as small `Sq A/B` badge (up to 4 officers per day; click day for full roster below)

### Time Off — day-off request ledger

- Bottom **Day Off Requests** ledger on Time Off tab
- Columns: Submitted (timestamp), Employee, Type, Date Off, Status
- **Officers:** own requests only; **Supervisor/Admin:** all employees
- **Logic:** `get_day_off_requests_for_viewer()`, `format_datetime()` in `validators.py`; `created_at` from DB
- **UI:** `ui/requests_pages.py`

### Officers roster — title / squad / shift fix

**Root cause:** `CTkComboBox` inside `CTkScrollableFrame` — dropdowns do not work reliably in CustomTkinter.

**Fix:** Moved **Title**, **Squad Assignment**, and **Shift Assignment** to a **sticky header bar** above the scrollable form:
- `StringVar` + `state="readonly"` combos
- Helpers: `_configure_job_title_combo`, `_configure_squad_combo`, `_configure_shift_combo`
- `load_officer(..., force_reload=True)` after save
- **Tests:** `tests/test_roster_import.py` — `test_update_officer_job_title`, `test_update_officer_squad_and_shift`

**Pattern to reuse:** Never put editable combos inside scrollable frames; use sticky header or modal.

### Scroll performance (laggy screens)

Identified hot paths and optimized:

| Area | Problem | Fix |
|------|---------|-----|
| Monthly calendar | ~31 days × nested frames/labels; `get_snapshot_day_roster()` per day | `build_monthly_roster_by_date()` once per month; **one multiline label** per day cell (`.configure()` not destroy/recreate) |
| Time Off queue | `suggest_bump_chain()` on every pending row | Coverage badge only for `Pending Manual Review`; full bump plan on **Preview** only |
| Day-off ledger | Full destroy/rebuild on every `refresh_requests()` | Signature cache in `refresh_day_off_request_ledger()` — skip rebuild if data unchanged |
| Officer list | `get_officer_by_id()` per row on selection highlight | `_officer_cache` populated in `refresh_officer_list()` |
| Payroll period scroll | All timecard lines per officer | Show **3 lines** + `+N more entries` |

**Key files:** `logic.py`, `ui/schedule_pages.py`, `ui/requests_pages.py`, `ui/officers_pages.py`, `ui/payroll_pages.py`

If scroll is still slow on a specific tab, profile that tab first — Gantt and other scrollables were not changed in this pass.

### Documentation and code dump (2026-07)

- **`docs/HANDOFF.md`** — agent handoff (this file)
- **`docs/PROJECT_README.md`** — human-readable project status mirror
- **`docs/FULL_PROJECT_CODE.txt`** — full project in one text file (~29 MB)
- **`scripts/export_project_code.py`** — regenerates the dump
- **Dump includes:** all source, `dodgeville_scheduler.db`, `build/`, `__pycache__/` (binaries as base64)
- **Dump excludes:** `dist/` (rebuild locally), `logs/`, `exports/`, `backups/`, `terminals/`
- **`docs/PROJECT_README.md`** — **How to work with the agent** section (templates, tips, compression user rule)

### Production login default (2026-07)

- `AUTO_LOGIN_ENABLED` defaults to **off** (`SCHEDULER_AUTO_LOGIN` must be `1` to skip login)
- Demo accounts unchanged: `admin`/`admin`, etc.

### `ui/app.py` shell cleanup (2026-07)

- Page logic in mixins; shell trimmed to nav, login, and refresh orchestration
- **My Profile** dialog extracted to `ui/profile_dialog.py` (`open_my_profile_dialog`)

---

## Architecture reminders

- UI → `logic.*` only (no SQL in UI)
- Validators are single source of truth for pre-checks
- Page mixins: `ui/schedule_pages.py`, `ui/officers_pages.py`, `ui/requests_pages.py`, `ui/payroll_pages.py`, etc. (ongoing split from `ui/app.py`)

---

## Open / next priorities

From `AGENTS.md` and session context:

1. **Continue live UI feedback** — user may report tab-specific polish after Tier 1 / Visual rollout
2. **Production credential policy** — auto-login off by default (done); still TODO: force password change on demo accounts, optional LDAP
3. ~~**Evaluation build**~~ — frozen package replaced 2026-07-01 (`C:\Users\Windows\Dodgeville_PD_Scheduler_Frozen_2026-07-01`, `scripts/build_frozen_eval.py`)
4. **Tier 2 backlog** (deferred): shift bidding, callback list, certifications gating, fatigue score

---

## Key symbols (recent touch points)

```
logic.py
  ensure_original_monthly_schedule()
  build_monthly_roster_by_date()
  get_pay_period_hours_summary()
  get_day_off_requests_for_viewer()

ui/schedule_pages.py     — monthly calendars, Gantt
ui/officers_pages.py     — roster CRUD, sticky assignment header
ui/requests_pages.py     — time off queue + ledger
ui/payroll_pages.py      — payroll period, timecard
ui/widgets.py            — ExpandableSection, CoverageBadge, StatusBadge
validators.py            — format_datetime, title/squad/shift helpers
config.py                — OFFICER_TITLE_OPTIONS, OFFICER_SQUAD_OPTIONS, OFFICER_SHIFT_OPTIONS
```

---

## How to update this file

At end of a session or feature:

1. Bump **Last updated** date and verification command result
2. Add a subsection under **Recent session work** (or start a new dated section)
3. Move completed items out of **Open / next priorities**; add new follow-ups
4. Note any **gotchas** (UI patterns, env quirks) future agents must not re-learn

Do not duplicate full scheduling rules here — link to `SCHEDULING_RULES.md` and `.grok/rules/` instead.
