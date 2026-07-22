## NEXT SESSION
- **Read `AGENTS.md` and `CLAUDE.md` in full before doing anything else.** All rules in them are binding for every session, not just this one.
- **SIMULATOR WORK → read [`docs/SIMULATOR_OVERHAUL_PLAN.md`](SIMULATOR_OVERHAUL_PLAN.md) FIRST (authoritative, 2026-07-22).** Deep live evaluation + phased roadmap with checkboxes. Five findings PROVEN live (search-space dialog dead-ends, dishonest hour-scale estimates vs 21s CP-SAT reality, suggestion-popup trap, exhaustive search freezing the whole app). Contains guardrails, repro/proof commands, and browser-tool survival notes. Work the roadmap top-down; update its checkboxes when items land. Do not re-diagnose what it already proves.
- **2026-07-22 later session: Phase 0 LANDED and live-proven** — P0.1 popup discipline (no lock/focus popups, explicit "Suggest values" button, single-dialog guard; residual: Esc-close broken app-wide, see plan), P0.2 honest CP-SAT-aware search estimate ("~1–2 minutes" where it said "31–78 hours"), P0.3 120s/300s time-boxed searches returning ranked best-so-far (live: 2 hard-OK options at exactly 120s; budget stop can never claim "impossible"). P0.4 partially verified (responsive during budgeted run; original-freeze root cause unattributed — see plan). Also: **solved the "unexplained chronos.css diff" mystery** — `gui/app.py::_ensure_static_css()` rewrites `gui/static/chronos.css` from `gui/theme.py::GLOBAL_CSS` on every app start, and 5c0ec6f updated the css file but not GLOBAL_CSS, so every launch reverted the dashboard KPI styling. Fixed by syncing GLOBAL_CSS to the committed css (now byte-identical; **rule: `gui/theme.py` GLOBAL_CSS is the source of truth — never edit `gui/static/chronos.css` directly**). Also fixed pre-existing `scripts/usage_brief.py` cp1252 UnicodeEncodeError that failed `verify --tier check`'s test step (same fix pattern as b084f11).
- **2026-07-22 (latest, UNCOMMITTED — see `logs/NEXT_SESSION_BRIEF.md` for full detail):** Replaced the core of the "not finding results" complaint — the optimizer was pure `itertools.combinations` brute force with heuristic pruning that had already caused a documented false-impossible bug. Added `logic/staffing_cpsat.py`: `solve_phase_variant` (sound relaxation — day-level 24/7 + annual band, its `infeasible` is a real proof) and `solve_full_assignment` (owns variant + phase + per-officer shift start together, minute-level 24/7 + weekday windows, verified independently against `logic/coverage_timeline.py`'s own sweep-line checker — 0 failures on the documented reference scenario). Both wired as additive fast-paths only — never make a result worse, only better/faster; old exhaustive search still runs whenever CP-SAT doesn't apply. Found and fixed a real integration gap before shipping: "Apply this option" didn't forward the CP-SAT-proven per-officer starts, so replaying a saved option could silently let the day-pool rebalancer reintroduce the exact window failures just solved — fixed via new `SimulatorConfig.officer_home_starts` field threaded through `run_schedule_simulation`/`_apply_ranked_option`. Also: fixed a real duplicate-rank bug in `suggest_relaxations` (the "weird suggestions" complaint), clarified the two confusingly-similar rotation-pattern UI controls, and did a **verified, low-risk stage-1** split of `gui/pages/simulator/page.py` (3626→3379 lines) — extracted 19 self-contained action handlers to new `actions.py`, caught two real hazards before shipping (a deleted call site, a late-bound-callback trap), proved live in-browser not just via unit tests. Deliberately **stopped** the page.py split there — remaining code is one tightly-coupled ~3000-line unit (form I/O + search execution + dialogs), not more loose threads; user agreed to stop rather than risk it. One latency regression (CP-SAT running unconditionally first) was found and fixed mid-session — don't reintroduce it (see brief for the heuristic-first ordering that matters). `verify --tier fast` + 28/28 tests pass; **`verify --tier check` / `honest_gate: true` not run** — do that before calling any of this shippable. One **unexplained, unattributed** diff in `gui/static/chronos.css` was found uncommitted at session end — no agent action this session touched that file; ask the user before assuming it's safe to keep or revert.
- **2026-07-21 late (committed `5c0ec6f`):** Fixed the root-cause optimizer bug — `early_impossible_proof` was proving multi-block scenarios "impossible" using a fake round-robin officer/pattern split, when the real search (`generate_pattern_maps`) tries every headcount split. This short-circuited the whole search before it ran on scenarios that were actually solvable. Also fixed a dead switch (`run_staffing_optimizer` silently dropped `min_rest_hours`/`max_consecutive_work_days`), added **multi-set rotation search** (Patterns field is now a multi-line textarea — one rotation set per line, solver tries all of them; wired end-to-end and live-tested), and merged in a `patched/` directory of UI fixes (login UAT-loopback-only gate + warning banner, shell CSS-mtime-thrash fix, dashboard KPI styling, clock.py unambiguous audit-date default) that was sitting untracked in the repo — audited its date-format default change against the other call sites it didn't touch (`dashboard.py`, `mobile_home.py`) and fixed those too so M/D/YY status-bar display wasn't silently lost. Full detail: `logs/NEXT_SESSION_BRIEF.md`.
- **Open question still unresolved:** user referenced `Chronos UI Evaluation.dc.html` (a Claude-Design overhaul spec) — not found anywhere searched, awaiting user reply on its location. The `patched/` directory found+merged this session was a **different, unrelated thing** (a set of already-applied UI file diffs, not that spec) — don't assume the open question is answered. Do not implement a redesign without it.
- **Verification note:** `python dev.py verify --tier fast` and the pre-commit `preflight` gate both passed (`logs/last_verify.json`, `honest_gate: false`). Full `verify --tier check` with `honest_gate: true` was **not** run this session — run it before treating this as shippable.
- **Process hygiene (binding):** any process you start for a task (dev server, test run, one-off script) must be terminated once it's no longer needed — do not leave it running after the task that needed it is done. Before starting a new one, check for stray/duplicate processes from earlier work (`Get-CimInstance Win32_Process -Filter "Name='python.exe'"` in PowerShell) and clean up anything abandoned. This session found and killed 2 more stray orphaned multiprocessing workers plus a duplicate `main.py` native-window process fighting its own web client over the same NiceGUI socket (caused a "Connection lost / message too large" false alarm — not a real bug, just two clients on one port; restart with `python main.py --web` when testing via the browser tool, not plain `python main.py`). Prior session found **20+ stray Python processes** (hung 3+ hours) plus 2 leftover `Chronos Command GPT` backend processes on port 8000 — all killed 2026-07-17 late evening — don't recreate this pile-up.
- **Repo-root clutter (not cleaned up, needs a human decision):** `"New Text Document.txt"` (empty, 0 bytes) and `"ChatGPT Image Jul 21, 2026, 10_18_53 PM (1).png"` (2.7MB) are untracked in the repo root — left out of the `5c0ec6f` commit intentionally, ask the user before deleting or committing them. The `patched/` directory is now redundant (its content is merged into `gui/`) but was left in place rather than deleted unilaterally.
- **THIS FOLDER (`C:\Users\Windows\Desktop\Claude Chronos Command`) is now the primary working copy — all future work happens here, not in `C:\Users\Windows\MyProject`.** Seeded from MyProject's working tree (incl. its uncommitted connection-leak refactor) on 2026-07-17 evening via a filtered copy (excluded build/dist/backups/__pycache__/.hypothesis/.nicegui/.claude/worktrees/exports/logs). Git history + `origin` (`github.com/jaredweier/MyProject2.git`) carried over, but **nothing from this copy has been pushed** — treat `origin` here as read-only provenance until told otherwise.
- **Simulator/UI needs a major overhaul, not point-patches.** 3 bugs were found+fixed this session (officer-count band, form-restore lock, WS buffer) but user considers this the start, not the fix — `gui/pages/simulator.py` (4300+ lines, one file) needs real scoping for redesign/rebuild, not more one-off patches.
- **Full brief:** `logs/NEXT_SESSION_BRIEF.md` — now covers the 2026-07-22 session (CP-SAT optimizer core, officer_home_starts fix, page.py split stage 1). Older per-session bullets below are historical context from earlier sessions, not current status. Read the brief before touching `gui/pages/simulator/*`, `logic/staffing_optimizer.py`, `logic/staffing_cpsat.py`, `simulator.py`, or `logic/optimizer_features.py` again.
- F1 `shift_coverage_heatmap` is wired to simulator UI (`do_heat()` button). F2 `suggest_relaxations` **is** wired (renders a "Suggested Relaxations" panel on near-miss/impossible results) — a prior handoff claiming it was unwired was stale; don't re-remove it.
- Simulator UI overhauled to remove Quickstart and Annual Live calculators, shifting to a clean dense grid layout.
- Folder boundaries enforced in agent_kit.py.
- **Other project folders on this machine — do not assume relevance without checking with the user:**
  - `C:\Users\Windows\MyProject` — original copy. Has an **uncommitted, mostly-finished SQLite connection-leak refactor**: 29 of 31 `logic/*.py` files converted from `get_connection()`/`conn.close()` to the leak-safe `with connection() as conn:` pattern (see `database.py`). **2 files still need the same fix**: `logic/stations.py` and `logic/time_punch.py` — both use `with get_connection() as conn:`, which only commits/rolls back and never actually closes the connection (same bug shape, different call pattern). Also has an unexplained commit `0858ed2 "Update handoff pointer for next session"` that landed during this session from an unknown source — not investigated.
  - `C:\Users\Windows\Desktop\Antigravity Chronos Command` — evaluated 2026-07-17, **not more current, nothing worth merging**. Diffed against the exact commit it forked from (`8c4e040`): ~95% of its changes are pure cosmetic reformatting (no behavior change), plus it **deleted the working "Suggested Relaxations" UI panel** and left 2 dead imports behind. Did not touch the actual bugs found this session.
  - `C:\Users\Windows\Desktop\Chronos Command GPT` — a separate FastAPI/uvicorn backend project (`chronos.main:app`). Was found running on port 8000 during this session and was killed per the process-hygiene note above (it had been left running with nothing actively using it). Relationship to this project is unknown — ask the user before assuming anything about it, and don't restart it without asking either.

# Session Handoff — Dodgeville PD Scheduler

**Purpose:** Living memory for agents (and humans) to resume work without re-reading full chat history.
**Human-readable mirror:** [`PROJECT_README.md`](PROJECT_README.md) — keep both in sync when updating.
**Update this file** when you finish a meaningful chunk of work (features, fixes, renames, perf passes).

**Last updated:** 2026-07-22 (CP-SAT optimizer core added — phase-variant + full minute-level assignment, both sound/proof-backed where used · officer_home_starts replay-consistency fix · suggest_relaxations rank-collision fix · rotation-control UI labeling fix · page.py split stage 1 (actions.py extracted, verified live) · latency regression found+fixed · UNCOMMITTED · full `verify --tier check` not yet run)
**Verification:** ship only → `verify --tier check` + `honest_gate: true`. Day-to-day → **one focused test** + human Chronos click. Logic green ≠ UI works.
**Next agent start pack (auto):** `logs/SESSION_CONTRACT.md` · `logs/NEXT_SESSION_BRIEF.md` · `logs/agent_pack/latest.md` · `docs/AGENT_TRUST_AND_MISTAKES.md` · this § NEXT SESSION · [`docs/NEXT_AGENT_PROMPT.md`](NEXT_AGENT_PROMPT.md)

---

## NEXT SESSION (read this first)

### Trust / criticism (binding)
Human called out **false "fixed" claims**, half-jobs, and late bug discovery. Full list: **`docs/AGENT_TRUST_AND_MISTAKES.md`**. Auto-injected into **`logs/SESSION_CONTRACT.md`** via `session_auto_bootstrap.py`.
**Prove user scenario first. Never claim fixed without residual honesty.**

### What the human is doing
Chronos Command **purchase / implement** + **supervisor testing** (esp. **simulator/optimizer**) + **remote UAT** when always-on is up.
Binding landings: **`logs/NEXT_SESSION_BRIEF.md`**.

### Brand (do not strip / do not re-break)
- Product string (config): **`Chronos Command`** — Title Case in `APP_NAME` / `PRODUCT_NAME`
- **Display:** **CHRONOS COMMAND** via CSS uppercase on brand classes only
- **Never** uppercase credentials or mutate `APP_NAME` to all-caps in Python
- **Agency-neutral UI:** no **Dodgeville** in user-facing defaults (dept `"Police Department"`, rotation **`2-2-3 (14-day)`**); legacy keys remapped on read
- Vendor: **Weierworks Technologies, LLC** · Logo: `/media`
- After CSS pulls: **Ctrl+F5**

### Real-world sim reference (user)
**8h** · **2008±20** annual · multi-block **6-2,5-3 | 6-3,5-2** · 24/7 min 1 · Fri+Sat 19:00–03:00 min 2 · **7** officers often thin weekend night → hard pack often needs **8**.
Hard eval **always 28-day** (do not ship 14-day hard as truth). Unit: `test_real_world_eight_hour_multiblock_annual_and_nights`.

### Verified at handoff (2026-07-17 simulator + brand + NiceGUI UX)
| Gate | Result |
|------|--------|
| Last ship `verify --tier check` | **PASS** · `honest_gate: true` (~06:07Z UTC) |
| Simulator UI | Command surface · Standard/Deep free-N · chips · KPI · splitter · refreshable options · throttle |
| NiceGUI | **3.14.0** (= latest) · patterns in `gui/ui_patterns.py` · skip-link · a11y CSS |
| Agency brand | Dodgeville stripped from Chronos UI defaults + export titles |
| Always-on UAT | Task still installed; **:8080 may be down** between sessions — start Chronos or always-on |
| Local URL | `http://127.0.0.1:8080` · admin/admin when UAT lab |
| Open residual | Supervisor **click** Find best · live SMS deferred · LDAP AD · tunnel URL stability |

### Always-on rules (do not re-break)
- User wants remote UAT when PC is on; code saves → restart Chronos; testers **Ctrl+F5**
- **One process on :8080**
- Doc: `docs/VIRTUAL_UAT.md` · Cloud VM: `docs/deploy/CLOUD_VM.md`

### Product rules (do not re-break)
**Simulator:** last-saved constraints only · OFF days OFF unless opt-in · multi-block in `staffing_optimizer` · user 8h/2008 first · **Standard free-N near hint; Deep 4–20; hard 28d**.
**Sensitivity:** cheap default; deep only if asked.
**Punch / tenant / notify / publish / CAD / LDAP / offline / stations / fatigue / UAT lab:** unchanged (see prior handoffs).

### Hot modules (2026-07-17 evening)
```
gui/pages/simulator.py · gui/ui_patterns.py · gui/shell.py · gui/static/chronos.css
config.py · seed_data.py · logic/operations.py · logic/rotation_config.py · logic/optimizer_features.py
tests/test_simulator_constraints.py · tests/test_feature_ui_static.py
logs/NEXT_SESSION_BRIEF.md · logs/remote_uat_url.txt
```

### Default work if user says "continue"
1. Simulator / supervisor test path if they care (prove browser Find best)
2. Keep always-on intact; one :8080; restart if down
3. Do **not** put Dodgeville back in UI
4. Live notify only if user escalates
5. Re-`check` after product edits

### Landed A→B→C (2026-07-13)

| Phase | What |
|-------|------|
| **A** | Leave smoke re-proved; chronos-e2e extended (payroll FLSA, callbacks, OT election chrome); officer nav slim (`OFFICER_NAV_PATHS`); read_guard tests match lean modules |
| **B** | **Deep Chrome** tokens in `gui/theme.py` + `chronos.css` (DESIGN.md B); silver CTAs, no violet; shell always syncs CSS; dashboard hero decision band |
| **C** | Cert-gate supervisor open-shift assign; callback call-down “Log OT offer to next”; OT cash/comp radio on timecards; FLSA base date M/D/YY display; notify channel hooks UI + `logic/notify_channels.py` on schedule publish |

### Agency-neutral branding (2026-07-14)

- Removed shipped `logo.png` / `team_photo.jpg` / `photos/dept_*` / static brand copies
- Runtime only: `photos/chronos_logo.png`, `dept_logo.png`, `dept_photo.jpg`
- UI **Branding & Media**: Chronos logo + department logo/photo + Clear
- Login/shell: product mark + **Chronos Command**; optional agency seal + hero photo
- Builds/probes no longer require root brand assets

### Landed this session (do not re-break)

**1) Manual-test UI repairs**

| Bug | Cause | Fix |
|-----|-------|-----|
| Time Off Order in / Volunteer | `make_order(False)` → `coid=False` | keyword-only `make_order(*, partial=, cover_id=)` |
| Simulator Run | `lines.append("", "Suggestions:")` | `lines.extend([...])` |
| Nav timer crash | parent_slot deleted after navigate | `timer._parent_slot = None` in `gui/shell.py` |
| Timecard Find period | notify only | `app.storage.user` + reload; **Current period** button |
| Stale live-schedule test | assumed no live snap after ensure_original | product seeds live; test updated |

Static guards: `tests/test_feature_ui_static.py` (no `make_order(True/False)`, no multi-arg append).

**2) Date contract — M/D/YY (mm-dd-yy) — user-corrected**

- **Display:** `validators.format_date` → `7/9/26` (July 9). Separators **`/` or `-`**. Year **2 or 4** digits.
- **Storage:** ISO `YYYY-MM-DD` only (`storage_date` / DB keys).
- **Parse:** month-first first (`config.DATE_PARSE_FORMATS`), then ISO, day-first last.
- **Sources:** `config.py` DATE_* · `validators_dates.py` · GUI defaults use `format_date()`, not raw `.isoformat()`.
- **Mistake avoided:** an interim day-first (D/M) attempt was **reverted** after user said **mm-dd-yy**. Do not re-apply D/M.

### Landed 2026-07-14 (simulator + optimizer UX)

| Area | What |
|------|------|
| Simulator UI | Locks, extra DOW/time windows, readable ranked Option buttons, label **Minimum officers per shift** — `gui/pages/simulator.py` |
| Optimizer | Uses form constraints (not days=14 only); `logic/scheduling_sim.py` + `coverage_optimizer.optimize_staffing_scenarios` |
| Engine | `extra_windows` evaluated in `simulator.py` |
| Bump/plans | Scores internal; leave Plans = ranked options — `bump_optimizer` / `coverage_optimizer`, `plan_explain`, `leave.py` |
| Brand | Tiny root placeholders + chronos logo; readiness tests updated |

### Default work if user says “continue”
1. **Human retest simulator** (primary): locks → Find Best → click Option N → windows → Generate
2. Fix only reported click failures; **one focused test** per fix
3. Leave OT / order-in browser still unproven if they switch
4. Full check only if ship claim

### Do not waste tokens on
- Full `verify --tier check` every turn
- Re-reading full `docs/archived_skills/`
- Explore/plan subagents for gates
- Claiming complete without human click proof
- OSS / graphify / vision unless user asks

### Trust status (2026-07-14)

| Check | Status |
|-------|--------|
| Domain / unit | Strong for covered paths |
| Full check | Green earlier this day — not a substitute for UI |
| Chronos product | **Partial** |
| Simulator | Code landed; **manual retest open** |
| Leave / payroll browser | Still unproven |

### Three brains (2026-07-16)

Contract: `docs/THREE_BRAINS_CONTRACT.md`. Boundary test: `tests/test_three_brains_boundary.py`.

| Brain | Modules |
|-------|---------|
| **Generator** | `scheduling.py`, `scheduling_matrix.py`, `rotation_*`, `shift_assignment`, `snapshots`, `rust_bridge` |
| **Optimizer** | `coverage_optimizer.py`, `bump_optimizer.py`, `scheduling_sim.py`, `staffing_optimizer.py`, `optimized_schedule_apply.py`, `ot_fill.py` |
| **Payroll** | `logic/payroll/*` |

`logic.scheduling` and package `import logic` do **not** re-export bump/sim.
Prefer: `from logic.coverage_optimizer import suggest_bump_chain` / `from logic.scheduling_sim import run_schedule_simulation`.
Tooling resolves symbols via `scripts/logic_resolve.py`.

**Validators split:** facade `validators.py` + `validators_dates|rules|officer|auth|ops.py`.

### Optimizer false-impossible fix + multi-set rotations + patched/ UI merge (2026-07-21 late, `5c0ec6f`)

**Root cause found via `/code-review` on the simulator:** `logic/optimizer_features.py::early_impossible_proof` estimated a multi-block scenario's mean annual hours using a fixed round-robin officer/pattern split (`i % len(patterns)`), then declared the whole search space impossible if that one assumed split missed the target band. The real search (`logic/staffing_optimizer.py::generate_pattern_maps`) tries **every** headcount split between patterns, so a target only reachable at an uneven split was wrongly proven impossible before the real search ever ran — likely the actual cause of "not finding correct answers" complaints. Fixed to check the true achievable `[min, max]` range across patterns instead of one assumed split. Companion fixes: the early-impossible gate now loops over every rotation variation set (not just one), and preset (squad A/B) rotations now get the same annual-hours cheap-reject pruning custom multi-block patterns already had (`_preset_avg_annual_hours` in `staffing_optimizer.py`).

**Second dead switch found:** `logic/scheduling_sim.py::run_staffing_optimizer` has an explicit kwarg list plus `**_compat` catch-all, but `min_rest_hours`/`max_consecutive_work_days` weren't in that explicit list — the UI sends them, but they were silently swallowed by `_compat` and never reached `optimize_staffing_scenarios`. Fatigue/rest constraints entered on the Requirements page had zero effect on Find Best results. Fixed by adding both to the wrapper's signature and forwarding them.

**New: multiple manually-entered rotation sets.** Previously locking a custom multi-block "Patterns" value pinned the search to exactly that one combo. Added `rotation_variation_sets` threaded through `_resolve_axes` → `estimate_search_space` → `optimize_staffing_scenarios` → `run_staffing_optimizer`; the simulator UI's Patterns field (`gui/pages/simulator/options_panel.py`) is now a multi-line `ui.textarea` — one rotation set per line, all tried in the same Find Best run. Verified backend (feasible set correctly found among an infeasible + feasible pair) and live in-browser (pre-flight space-estimate dialog correctly lists `rotation_variations` as a searched dimension once 2+ sets are entered; multi-line value persists across reload).

**Merged `patched/` — an untracked directory of already-drafted UI file diffs** (`clock.py`, `shell.py`, `login.py`, `dashboard.py`, `chronos.css`) found sitting in the repo root, unrelated to the missing `Chronos UI Evaluation.dc.html` spec. Real content once CRLF noise was stripped: login UAT mode now gated to loopback-only with a warning banner (was previously exposable on a public host); shell.py removed the CSS-sync-on-every-startup that used to restart always-on UAT on every health tick (a previously-documented bug); dashboard KPI hero styling (`kpi-crit`/`kpi-warn`/`kpi-ok`, matches `DESIGN.md` tokens); `clock.format_local_date()` gained a `style` param — default is now unambiguous `DD-MMM-YYYY` for audit/export contexts, `style="short"` preserves the existing M/D/YY for status-bar contexts. **The patch author only audited call sites in the 4 files they touched** — `dashboard.py`'s own status-bar line and both `mobile_home.py` week-card labels call `format_local_date()` without `style="short"` and would have silently flipped to the long format; fixed both to pass `style="short"` explicitly. Applied with CRLF conversion to match repo convention (diffs are clean, not CRLF noise).

**Lint-gate fallout (pre-existing, not introduced this session):** the pre-commit `ruff` hook caught `_parse_starts()` called 4× in `gui/pages/simulator/page.py` but never defined there — a real bug dropped during the earlier module split (a 6th one, beyond the 5 already documented). Restored it (mirrors the same-named local helper already in `manual_editor.py`). Also removed 3 unrelated dead local-variable assignments (`hist` in `optimizer_features.py`, `length` and `found_hard_for_n` — write-only, never read anywhere — in `staffing_optimizer.py`) that ruff's F841 flagged.

**Verified:** 28/28 targeted tests (`tests.test_simulator_constraints`, `tests.test_feature_ui_static`), `verify --tier fast` + pre-commit `preflight` gate, live browser click-through of the multi-set Patterns field and the pre-flight search-space dialog. **Not verified:** an actual multi-hour Find Best run to completion in the browser (space was ~141M layouts unconstrained — backed out rather than run it; the fast headless smoke test covers the same code path with a scoped search). Full `verify --tier check` / `honest_gate: true` not run.

---

## Quick resume

| Item | Value |
|------|--------|
| Product | **Chronos Command** (NiceGUI primary UI in `gui/`) |
| Run GUI | `python main.py` → `gui.app` |
| Legacy UI | `ui/pages/*` CustomTkinter — not primary; **old root `ui/*_pages.py` mixins removed** |
| Demo logins | `admin` / `admin`, `supervisor` / `supervisor`, `officer` / `officer` |
| Auto-login | **Off by default** — set `SCHEDULER_AUTO_LOGIN=1` for dev skip-login |
| Full verify | `python dev.py verify --tier check` + read `logs/last_verify.json` |
| Domain rules | `SCHEDULING_RULES.md`, `.grok/rules/known-issues.md` |
| Display dates | **M/D/YY** (mm-dd-yy) e.g. `7/9/26` via `validators.format_date`; `/` or `-`; year 2 or 4 digits; storage ISO |

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

### Vertical slice architecture (logic split done; **registry honest as of 2026-07-09**)

Brownfield VSA: [`docs/VERTICAL_SLICES.md`](VERTICAL_SLICES.md).
**P0 repaired:** `python dev.py slice-check` → all bindings resolve; slice status is mostly **`partial`** (not complete). Primary UI paths are `gui/pages/*` (+ legacy `ui/pages/*` where listed).

| Artifact | Purpose |
|----------|---------|
| `slices/registry.py` | Slice defs — Chronos `gui/pages/*` + logic touch sets |
| `python dev.py slice-map -v` | Find slice by capability; see `touch_together` files |
| `python dev.py slice-check` | Path existence / integrity |
| `tests/test_vertical_slices.py` | Registry integrity tests |

**Logic package split:** under `logic/*.py`; `import logic` via `logic/__init__.py`.
**UI:** primary Chronos `gui/pages/*`; legacy `ui/pages/*` secondary (freeze except bugs unless task says otherwise).

### Chronos depth inventory (P2 — 2026-07-09)

Dual-rate only. **Logic strong ≠ Chronos complete.** Re-prove with browser smoke before `"complete"`.

| Feature | Logic | Chronos page(s) | User can… | Status |
|---------|-------|-----------------|-----------|--------|
| Dashboard / KPIs | strong | `gui/pages/dashboard.py` | KPIs, gap board, hours watch, quick actions | **partial** |
| Roster | strong | `roster.py` | CRUD-ish personnel | **partial** |
| Day-off + swaps | strong | `leave.py` | Submit, preview, plans, confirm plan pick, reject notes, bulk, swaps | **partial** (logic smoke OK; browser click-approve unproven) |
| Schedules | strong | `schedules.py` | My / monthly / live matrix | **partial** |
| Payroll / timecard | strong | `finance/*` | Entry, prefill, **lock/unlock**, banks, ledger | **partial** (logic lock smoke OK; browser lock unproven) |
| Notifications | strong | `notifications.py` | Inbox, mark read, compose, Open→route map | **partial** (path smoke OK) |
| Ops reports | strong | `operations.py` | Gaps, hours, OT equity, full insights | **partial** |
| Open shifts | strong | `self_service.py` | Board, post, claim/assign | **partial** |
| Shift bidding | exists | `bidding.py` | Events + officer bid form | **partial** |
| Availability | strong | `availability.py` | Blackouts / holidays | **partial** |
| Simulator | yes | `simulator.py` | Scenario trainer | OK (UI-only by design) |
| Security / users | strong | `security.py`, `access.py` | RBAC chrome / access | **partial** |
| Multi-user deploy | NiceGUI | — | Hostable; hardening open | **partial** |

**Legacy `ui/`:** frozen except bugs unless explicitly tasked.
**Logic package (2026-07):**

| Module | Slice |
|--------|--------|
| `logic/officers.py` | roster |
| `logic/scheduling.py` | rotation, bumping, matrix |
| `logic/requests.py` | day-off, swaps, notifications |
| `logic/snapshots.py` | monthly calendars, sync, overrides |
| `logic/payroll/` | payroll, timecard (package: period, pay_codes, timecard, entries, banks) |
| `logic/users.py` | auth, app users |
| `logic/operations.py` | holidays, availability, open shifts, settings |
| `logic/exports.py` | PDF/CSV/iCal export wrappers |
| `logic/dashboard.py` | dashboard + analytics delegates |
| `logic/_core.py` | thin shim (re-exports exports + dashboard) |

Tooling: `scripts/extract_logic_requests.py`, `scripts/extract_logic_modules.py`, `scripts/extract_logic_core_trim.py`

**Agent rule:** When changing a feature, find its slice → edit only `touch_together` files (+ shared kernel if cross-cutting) → run slice `verify` + `python dev.py check`.

**UI note:** monthly schedule CTAs live under Chronos `gui/pages/schedules.py` / legacy `ui/pages/*` (root `ui/*_pages.py` mixins removed).

### Industry roadmap — Tier 1, Visual/UX, Phases A–C (**logic largely done; Chronos UI partial — do not call complete**)

Much of the public-safety scheduling UX backlog exists in **logic** and/or **legacy UI**. Chronos `gui/` has KPIs and key flows but **not full parity**. Rate Logic vs Chronos separately.

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

- Chronos UI → `logic.*` only (no SQL in `gui/`)
- Validators are single source of truth for pre-checks
- Primary pages: `gui/pages/*` · Legacy: `ui/pages/*` · Registry must match disk (see trust checklist)

---

## Open / next priorities

1. **Chronos depth (P2)** — dual-rate features; browser-prove leave approve / payroll lock before `"complete"`
2. **Continue live UI feedback** on `gui/`
3. **Production credential / LDAP** — one true story for `must_change_password` + optional LDAP
4. ~~**Evaluation build**~~ — frozen package tooling exists (`scripts/build_frozen_eval.py`)
5. **Tier 2 logic** — bidding/callbacks/certs; do not claim Chronos shipped without page proof
6. ~~Token prune~~ — done 2026-07-12 (caveman, lean route, skills `_archive`)

---

## Key symbols (current — verify paths exist before editing)

```
gui/app.py, gui/shell.py, gui/pages/*   — Chronos primary UI
logic/scheduling*.py, logic/requests.py, logic/payroll/*, …
validators.py (+ validators_*.py), database.py, config.py, cli.py
slices/registry.py                      — paths OK (slice-check clean 2026-07-12)
ui/pages/*                              — legacy CTk pages (secondary)
ui/widgets.py, ui/theme.py              — legacy helpers may still be referenced by tests

DELETED / do not cite as current:
  logic.py (monolith)
  ui/dashboard_pages.py, ui/requests_pages.py, ui/payroll_pages.py,
  ui/schedule_pages.py, ui/officers_pages.py, ui/feature_pages.py, …
```

---

## How to update this file

At end of a session or feature:

1. Bump **Last updated** date and verification command result
2. Add a subsection under **Recent session work** (or start a new dated section)
3. Move completed items out of **Open / next priorities**; add new follow-ups
4. Note any **gotchas** (UI patterns, env quirks) future agents must not re-learn

Do not duplicate full scheduling rules here — link to `SCHEDULING_RULES.md` and `.grok/rules/` instead.
