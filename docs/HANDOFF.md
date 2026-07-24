## 2026-07-24 (LATEST) — Phase 4 Postgres fixture verified, CI scanning added, draft PR #8

**Phase 4 step 5 (full suite vs real Postgres) — PARTIALLY VERIFIED:**
- Session-scoped ephemeral Postgres fixture (one initdb per pytest run,
  TRUNCATE between tests) committed and verified: `tests/test_logic.py` 22/22
  PASS against real Postgres (~5 min). Fixture works cleanly: conftest.py,
  tests/pg_session.py (new), tests/helpers.py (Postgres branch),
  seed_data.py/db_compat.py/logic/requests.py (guards for backend).
- Connection pooling (idle-connection reuse per DSN) fixed the 21/22
  timeout failures from prior session's unverified attempt.
- officer_time_banks added to _NON_ID_PK_TABLES (was causing "column id does not exist").
- Broader suite verification (`test_coverage_optimizer.py` et al.) deferred to CI
  rather than running locally; faster iteration on single-machine bottleneck.

**Master plan §12 (security) — CI dependency/container scanning:**
- Added `container-scan` CI job (aquasecurity/trivy-action) to
  `.github/workflows/ci.yml` — builds Dockerfile, fails on unfixed CRITICAL/HIGH CVEs.
- Extended `scripts/deps_audit.py` to also audit `requirements-dev.txt`
  (previously only `requirements.txt`).
- Draft PR #8 opened to trigger actual GitHub Actions run (can't verify
  CI jobs locally).

**Housekeeping:**
- Fixed recurring pre-commit failure: moved graphify-out/{KNOWLEDGE_HUB.md,GRAPH_REPORT.md}
  to .gitignore (they regenerated on every `verify --tier preflight` run,
  forcing every commit to need a retry).
- Added .claude/worktrees/ to token-scan ignore (mirrored files tripping large-file gate).

**Commits pushed to origin/agent/tier-a-scheduling-hardening:**
- `3e0cd54`: CI/deps/housekeeping
- `8b289eb`: Phase 4 Postgres fixture (test_logic.py verified)

**Next session:**
1. Check PR #8 — confirm `container-scan` job ran successfully, review any Trivy findings.
2. Broader Postgres suite verification can run in CI parallel to other work, or skip
   locally if tests pass in Actions.
3. Phase 4 is ~80% verified (test_logic.py yes, broader suite in CI). If broader
   suite passes remotely, Phase 4 can close out; otherwise debug the failures.
4. Phase 5 (leave/live-schedule UI) can unblock once Phase 4 is confirmed solid.

## 2026-07-24 PRIOR — Phase 3 closed out, Phase 4 (API + persistence) underway

Master plan §14 Phase 3 exit ("zero false feasible/infeasible in the
independent corpus") and Phase 4 start (§9 API/persistence). All commits
below are pushed to `origin/agent/tier-a-scheduling-hardening` and
verified landed (local SHA == remote SHA checked after each push).

**Phase 3 closed:**
- Oracle corpus extended to `solve_cycle_day_starts` (the one solver path
  not yet covered) — 12/12 passing. All three solver paths now have
  brute-force ground-truth coverage.
- Garbled infeasibility-dialog sentence fix (from the entry below) committed.
- Alternatives pool dedup, cancellation, caching/replay were already built
  in prior sessions — confirmed present, not re-done.

**Phase 4 — typed API layer (additive, NiceGUI's `app` IS already a
FastAPI instance, no new process):**
- `GET /api/v1/officers`, `POST`/`GET /api/v1/jobs/simulations` +
  `.../cancel`, `POST /api/v1/coverage/preview`, `GET /api/v1/swaps/preview`
  — all typed Pydantic, all additive, all tested (`api/`, `logic/optimizer_jobs.py`).
- Async job registry backed by a new `optimizer_jobs` SQLite table
  (existing DB — see `database.py`). Single-process, in-memory cancel
  events, not durable across restart (documented in `logic/optimizer_jobs.py`).

**Phase 4 — PostgreSQL move (§9), infra layer only, verified against a
real live Postgres, business SQL not yet ported:**
- `db_engine.py` / `db_compat.py` / `database.py`: SQLAlchemy engine
  resolution + a psycopg connection adapter that lets the existing ~41
  sqlite3 call sites work unchanged against Postgres (`?`→`%s` translation,
  transparent `RETURNING id`→`cursor.lastrowid`, dict-row access).
  `SCHEDULER_DB_BACKEND=sqlite` (default, unchanged) | `postgres` (needs
  `SCHEDULER_PG_DSN`); `init_database()` now fails loudly on postgres
  instead of running wrong DDL.
- Baseline Alembic migration (`migrations/versions/8286dcadb953_*.py`)
  reflected directly off the live SQLite schema (not hand-typed — avoids
  drift). **Verified for real**, not mocked: `tests/pg_fixture.py` spins
  up an ephemeral Postgres via the `postgresql-binaries` pip package (real
  server binary, no Docker/system install/admin — this was the answer to
  "can't we just test it for real"). Confirmed live: migration creates all
  36 tables, adapter lastrowid/row-access round-trips, and
  `logic/officers.py` (unmodified) reads/writes correctly through
  `database.get_connection()`.
  - Run it yourself: `CHRONOS_TEST_POSTGRES=1 python -m pytest tests/test_postgres_integration.py`
  - Gotcha hit and fixed: `pg_ctl start`'s child `postgres.exe` keeps
    stdout/stderr open past `pg_ctl`'s own return on Windows —
    `subprocess.run(capture_output=True)` hangs forever even though the
    server already started; use `stdout=DEVNULL` instead. Also: bare
    `postgresql://` DSNs make SQLAlchemy default to the (uninstalled)
    `psycopg2` driver — `db_engine.database_url()` rewrites to
    `postgresql+psycopg://` for SQLAlchemy specifically, while
    `db_compat.py`'s raw `psycopg.connect()` keeps using the plain DSN.
- **Not done, real work, not mechanical:** `docs/POSTGRES_PORT_INVENTORY.md`
  lists every file still needing a dialect-specific rewrite before the
  postgres backend is production-usable — 10 files' SQL `strftime()`
  calls (→ `to_char()`), 3 `PRAGMA` sites (no-op on postgres), 1
  `INSERT OR IGNORE` (→ `ON CONFLICT DO NOTHING`), plus real-Postgres
  verification of the 15 `.lastrowid` call sites the adapter should cover
  transparently. Suggested order is in that doc. SQLite remains the only
  backend any live code path actually uses — nothing here is wired into
  the running app yet.

`python dev.py verify --tier fast` — ALL PASSED after every commit in
this session. `verify --tier check` not run — no ship claim.

## 2026-07-24 — live browser proof of CP-SAT dialog found a real rendering bug, fixed

Master plan §2 "engine failures are never shown as normal no-results" — closing
the one gap the 2026-07-24 infeasibility-conflicts landing left open ("the
rendered dialog itself was not screenshot-verified this session").

- Drove the actual `/simulator` UI end to end (10 officers, 8h shift, custom
  `5-2` pattern, 24/7 min 5, annual 2008±20 hard) via `javascript_tool`
  full pointer-event dispatch (`pointerdown/mousedown/pointerup/mouseup/click`
  — plain `.click()` doesn't register on these Quasar buttons/checkboxes;
  their state lives in `aria-pressed`/`aria-checked` on a wrapper element, not
  the native input's `.checked`). Confirmed the "Simulator understood" plan
  dialog, then the actual no-match result panel.
- **Found a real bug live, not in a unit test:** the rendered proof sentence
  read "no assignment satisfies CP-SAT proved no phase/variant assignment
  satisfies 24/7 coverage + annual-hours band together **together**" — a
  duplicated/garbled sentence. Root cause: `solve_phase_variant`'s conflict
  entries store an already-complete sentence in `categories[0]` (the honest
  reason string, see the 2026-07-24 conflicts-accumulator entry above), but
  `gui/pages/simulator/page.py`'s renderer unconditionally wrapped every
  entry's `categories` in a `"no assignment satisfies {...} together"`
  template built for `solve_full_assignment`'s short category tokens
  (`coverage_247`, `annual_hours_band`, etc.) — never designed for a
  full-assignment vs. phase-variant distinction in the render layer.
- Fix: `logic/staffing_optimizer.py` phase_variant conflict entries now carry
  `"full_reason": True`; `page.py`'s renderer checks that flag and renders
  `categories[0]` verbatim instead of wrapping it, leaving the
  `solve_full_assignment` short-token path unchanged.
- Verified the exact fixed string composition directly in Python for both
  branches (full_reason=True and short-token) — both read cleanly. Full
  re-navigation through the restarted dev server to re-screenshot the exact
  dialog was abandoned after repeated NiceGUI nav-state flakiness (same class
  of issue documented in the 2026-07-23 brief's "Browser automation notes");
  the string-composition fix itself is pure formatting logic covered by the
  direct verification, not something CP-SAT timing affects.
- `python dev.py verify --tier fast` — ALL PASSED after the fix.
  **Committed and pushed** (see the entry above — this session got
  explicit ask-before-commit confirmation). Full `verify --tier check`
  not run.

## 2026-07-24 — independent oracle corpus + Deep Proof strengthens CP-SAT itself

Master plan §11 "Independent corpus" + §4 "Deep Proof: extended exact search
and stronger proof."

- `tests/test_cpsat_independent_oracle.py` (new): pure-Python brute-force
  ground truth (no CP-SAT, no rust) comparing `solve_full_assignment` and
  `solve_phase_variant` against independently computed feasibility for 24/7
  coverage, weekday-anchored windows, annual-hours band, and
  max-consecutive-work-days — 10 cases, zero false feasible/infeasible.
  Annual-hours ground truth is computed directly from brute-forced
  worked-day counts, not via the shared `projected_annual_hours` helper, so
  an encoding bug shared between solver and oracle wouldn't cancel out.
- Found the real gap behind "Deep Proof" (2026-07-23 profile-selector
  entry's own "Not done" note): it only extended `time_budget_seconds` (the
  outer search loop's wall-clock cap on how many combos get tried) — the
  per-candidate CP-SAT `time_limit_sec` itself was still hardcoded
  (30s/20s/8s) regardless of profile, so Deep Proof never actually gave the
  solver more time to resolve a single hard combo to a proven verdict
  instead of timing out to "unknown".
- `logic/staffing_optimizer.py::optimize_staffing_scenarios`: new
  `cpsat_time_limit_sec: Optional[float] = None` param threaded to all 3
  per-candidate CP-SAT calls (`solve_phase_variant`, `solve_cycle_day_starts`,
  `solve_full_assignment`); `None` preserves prior hardcoded defaults exactly.
- `logic/scheduling_sim.py::run_staffing_optimizer`: threads it through
  (auto-included in the existing cache key since it hashes `call_kwargs`).
- `gui/pages/simulator/state.py`: `SEARCH_PROFILES["deep_proof"]` gains
  `cpsat_time_limit_sec: 60.0`; quick/balanced omit it (byte-identical).
- `gui/pages/simulator/page.py::_optimizer_kwargs`: passes the profile's
  `cpsat_time_limit_sec` through; `estimate_search_space`'s `**_ignored`
  catch-all absorbs it harmlessly for the pre-flight estimate call.

**Proof:** `test_search_profiles.py` 6/6, `test_cpsat_conflict_explanation.py`
+ `test_cpsat_independent_oracle.py` 14/14, `verify --tier fast` ALL PASSED.
One flaky failure seen in a long sequential run
(`test_open_search_uses_preset_cpsat_for_six_officer_solution` missed its 60s
budget) — reproduced passing in 8.3s isolated, confirming this is the
already-documented 2026-07-23 CPU-load-variance flake, not a regression from
this change. Not committed yet at time of writing; ask before committing.
Full `verify --tier check` not run — no ship claim.

## 2026-07-24 — surface CP-SAT infeasibility proofs to the UI

Master plan §2 "Engine failures are never shown as normal no-results
outcomes" / §4 "sound conflicts." Prior audit was right: `optimize_staffing_scenarios`
called `solve_full_assignment` per (officer-count, shift-length) combo but
only ever checked `full.get("status") == "feasible"` — the `conflict_assumptions`
proof from an infeasible combo (built in the prior landing) was silently
discarded once the loop moved to the next combo. The simulator's "No Perfect
Schedule" dialog had no way to show a real proof, only a reject-reason
histogram (heuristic, not sound).

- `logic/staffing_optimizer.py`: new `infeasibility_conflicts` accumulator
  (~1906) captures up to 5 deduped (by category-set) CP-SAT proofs at the
  `full.get("status") == "infeasible"` site (~2218) — `{num_officers,
  shift_length_hours, categories, proven_minimal}` per combo. Exposed as
  `result["infeasibility_conflicts"]` on both the exhaustive-search failure
  return (~3206) and the early-impossible-proof return (~1865, always `[]`
  there — that path proves impossibility a different way, pre-CP-SAT).
- `gui/pages/simulator/page.py` `_apply_opt_result`: when showing the no-match
  dialog, appends the first CP-SAT proof as a sentence — "CP-SAT proof (N
  officers, Xh shift): no assignment satisfies <categories> together" (plus
  "(sufficient, not proven minimal)" when shrinking didn't converge) — into
  the same `note` string already passed to `_show_no_match_dialog`.
- Not built (per scope): `cpsat_pv`'s own infeasible signal (a separate,
  earlier proof pass used to skip redundant search, ~2333/2405) isn't
  wired into this accumulator — it doesn't carry `conflict_assumptions`
  today, only a status flag; out of scope for this slice.

**Proof:** `tests/test_scheduling_contracts.py::test_optimize_staffing_scenarios_verification_is_none_without_ranked_rows`
now asserts `infeasibility_conflicts` is present as a list on the failure
result. `-k "cpsat or staffing or scheduling_contracts"` (57 tests) — no
regression. `python dev.py verify --tier fast` — ALL PASSED (14s).

**Live verification (2026-07-24, follow-up):** browser click-through on the
Simulator's Requirements form was attempted but abandoned — the form
re-renders aggressively enough (NiceGUI toggle buttons) that automated clicks
landed without reliably flipping the Given/Solve-for state, confirmed by
"Active locks"/"Layouts in space" staying unchanged across repeated attempts.
Rather than keep fighting that, verified the real path directly:
`optimize_staffing_scenarios(officer_counts=[10], shift_length_hours=8.0,
rotation_variations=['5-2'], coverage_247=5, ...)` — a case where the raw
headcount (10) clears the naive officer-count check but the CP-SAT
`solve_phase_variant` proof still finds it infeasible — returns
`infeasibility_conflicts: [{'num_officers': 10, 'shift_length_hours': 8.0,
'categories': ['CP-SAT proved no phase/variant assignment satisfies 24/7
coverage + annual-hours band together'], 'proven_minimal': False}]`. Confirms
both new wiring points (the `full`/full-assignment capture AND the
`cpsat_pv`/phase-variant capture) are live through the real entry point, not
just reachable in isolation. Separately confirmed a 2-officers/coverage=30
case hits the cheaper "early proof" arithmetic short-circuit instead (officers
< coverage_247) — correct per master plan stage-1 "use only mathematically
sound lower bounds" and consistent with why that path always reports
`infeasibility_conflicts: []` (no CP-SAT ever runs there). The GUI's
`_apply_opt_result` note-string construction was code-reviewed against this
exact shape (`categories`, `num_officers`, `shift_length_hours`,
`proven_minimal` keys all match) but the rendered dialog itself was not
screenshot-verified this session.

## 2026-07-23 — conflict-set minimality (deletion-based shrinking)

Master plan §4 Phase 3 "distinguish a sufficient conflict set from a proven
minimal one." Prior landing (`_explain_full_assignment_infeasibility`)
returned OR-Tools' sufficient set only, explicitly disclaimed as not minimal.

- `logic/staffing_cpsat.py` `_explain_full_assignment_infeasibility`
  (~268-465): after `SufficientAssumptionsForInfeasibility()`, deletion-shrinks
  the set — for each category, retries the explain model with that one
  category's assumption dropped (others still enforced); INFEASIBLE means it
  was redundant (drop for good), FEASIBLE means it's necessary (keep).
  Inconclusive (timeout) keeps the category but marks the whole result
  `proven_minimal=False`. New `shrink_time_limit_sec` param (default 5.0),
  budget shared across all shrink attempts. Returns `(labels, proven_minimal)`
  tuple instead of a bare list.
- `_solve_full_assignment` unpacks the tuple into `conflict_assumptions` +
  new `conflict_proven_minimal` key on the infeasible-branch result dict.
- `_cpsat_result_to_report`: `sufficient_not_minimal` per category is now
  `not conflict_proven_minimal` (was a hardcoded `True`) — categories that
  survive shrinking are honestly reported as proven minimal, not just
  sufficient.
- Not built (per scope): no change to the pool/diversity path, cache,
  objective, or UI. `shrink_time_limit_sec` is not yet surfaced to callers
  (uses the 5s default everywhere).

**Proof:** `tests/test_cpsat_conflict_explanation.py` updated — coverage and
annual-hours single-category tests now assert `sufficient_not_minimal is
False` (shrink proves the single-element set is minimal, correctly). New
`test_dominant_conflict_shrinks_out_the_redundant_category`: coverage_247=5
alone is already infeasible for 3 officers (independent of the hours band);
asserts the reported conflict set drops the redundant `annual_hours_target`
category and keeps only `coverage_247`, still proven minimal. All 4 tests
PASS. `-k "cpsat or staffing"` (46 tests) — no regression.
`python dev.py verify --tier fast` — ALL PASSED (15s).

## 2026-07-23 — token-scan allowlist fix (unblocked the commit below)

The CP-SAT conflict-explanation work below was implemented and fully proven
but couldn't commit: `logic/staffing_cpsat.py` grew to 52.6 KB, crossing the
`dodgeville-token-scan` pre-commit hook's 50 KB gate. Root cause found:
`scripts/token_audit.py`'s `check_token_hygiene` has an `allowed_large`
allowlist (~line 277-306) of known-large editable source files (siblings
`logic/staffing_optimizer.py`, `logic/coverage_optimizer.py`,
`logic/bump_optimizer.py` are already on it) — `logic/staffing_cpsat.py` was
just never added when it crossed the threshold. This is NOT a
`.cursorignore` issue (that list is for files to *hide* from indexing, which
was never the intent here). Fixed by adding `"logic/staffing_cpsat.py"` to
`allowed_large` — one line, matches existing precedent for sibling optimizer
files, no gate weakened (still flags genuinely new/unexpected large files).
**There are two separate, duplicate allowlists** — `check_token_hygiene`'s
`allowed_large` in `scripts/token_audit.py` (~line 277) AND
`ALLOWED_LARGE_SOURCE` in `scripts/token_scan.py` (~line 34). The actual
pre-commit hook (`dodgeville-token-scan`) reads `token_scan.py`'s set, not
`token_audit.py`'s — the first fix attempt only updated `token_audit.py` and
still failed at commit. Both are now updated. If a future file trips this
hook, update BOTH allowlists together before reaching for `--no-verify` or
`.cursorignore`. Worth a follow-up someday to de-duplicate these two lists
into one shared source of truth — not done here, out of scope.

## 2026-07-23 — CP-SAT infeasibility conflict explanation (assumptions)

Master plan §4/§14 Phase 3 "exact feasibility and proof." Prior audit was
right: `staffing_cpsat.py` had proven-infeasible reason strings but zero use
of OR-Tools `AddAssumptions`/`SufficientAssumptionsForInfeasibility` — no way
to say WHICH constraint category, if relaxed, would fix an infeasible model.

- `logic/staffing_cpsat.py` new `_explain_full_assignment_infeasibility()`
  (~257-425): builds a SEPARATE model (never touches the caller's proof
  model/solver) where each hard-constraint category — fatigue cap
  (`max_consecutive_work_days`), each coverage source (24/7 floor kept
  separate from each extra window, not merged via `max()` like the main
  model does) and the annual-hours band — is guarded by its own
  `NewBoolVar()` assumption, wired via `.OnlyEnforceIf(assumption)`.
  `model2.AddAssumptions([...])` + `solver2.SufficientAssumptionsForInfeasibility()`
  on INFEASIBLE returns the SUFFICIENT (not proven minimal — no
  QuickXplain-style shrinking attempted, said explicitly in the docstring)
  conflict set, mapped back to human labels.
- Wired only into `_solve_full_assignment`'s first-solve INFEASIBLE branch
  (~549-579) — the one that's already a sound proof (pool-exhausted
  INFEASIBLE is untouched). Wrapped in try/except: explain path is
  best-effort, never fatal to the caller. New `"conflict_assumptions"` key
  on that result dict (`None` = explain solve inconclusive, distinct from
  `[]` = no assumptions modeled for this scenario).
- `_cpsat_result_to_report()` (~710) maps it onto the EXISTING (previously
  unused) `SimulationReport.conflicts: list[dict]` field —
  `[{"category": label, "sufficient_not_minimal": True}, ...]`. No new
  models.py field needed; reused what was already there.
- Zero cost on the feasible fast path by construction: the explain model is
  only built inside the INFEASIBLE return branch, after the caller's own
  solve already proved infeasibility — no code executes on the feasible
  path that didn't before.
- Not touched (per scope): objective function, pool/diversity, cache, UI.
  Rest-hours (`min_rest_hours`) isn't modeled as its own assumption — it's
  a pre-solve structural precheck (`rest_floor`), not a `model.Add`
  constraint in this slice, so there's nothing to relax as an assumption.

**Proof:** new `tests/test_cpsat_conflict_explanation.py` (3 tests, all
PASS) — coverage-shortage scenario (3 officers vs 24/7 min 5) correctly
names `coverage_247` in the conflict set AND relaxing it (40 officers)
actually turns feasible; annual-hours-band scenario (9 officers, trivially
coverable, but `annual_hours_target=100±1` vs a pattern that projects far
higher, `annual_hours_hard=True`) correctly names `annual_hours_target=...`
AND relaxing it (`annual_hours_hard=False`) turns feasible; feasible-case
test asserts `conflicts == []` and elapsed time stays low. Existing
`tests/test_coverage_optimizer.py` (17) and `-k "cpsat or staffing"` (45)
all still pass — no regression. Feasible-case timing (12 officers, 3
starts, coverage_247=2, 3 runs): 1.19s / 0.32s / 0.28s — unaffected, as
expected since the explain branch never executes on this path.
`python dev.py verify --tier fast` — ALL PASSED (12s).

## 2026-07-23 — Optimizer wall-time p95 rollup (perf instrumentation)

Master plan §4 latency targets (25/100/500 officers, p95). Prior audit was
right: `wall_time_ms` was recorded per search but no p95 rollup existed.
Purely additive, reuses `logs/optimizer_search_history.json` — no second
logging path, no solver behavior touched.

- `logic/optimizer_features.py` (~1013): new `wall_time_p95(rows=None,
  officer_bucket=None, min_samples=5)` — nearest-rank percentile
  (`ceil(0.95*n)-1`, documented in docstring) over `wall_time_ms` from
  search-history rows (defaults to `list_search_history`). Refuses below
  `min_samples=5` with `ok:False` + honest message instead of a
  false-precision number off 1-4 samples. `_bucket_for_officers()` snaps
  `num_officers` to the master-plan 25/100/500 tiers for `officer_bucket`
  filtering. `wall_time_p95_report()` composes overall + per-bucket text.
- `dev.py`: new `perf-p95` subcommand (`cmd_perf_p95`, dispatch table entry)
  prints `wall_time_p95_report()`.
- `gui/pages/simulator/results_panel.py` `show_search_history()`: one line
  under the dialog title, `"p95: Xs (n=N)"` or the honest refusal message,
  via `wall_time_p95(rows)` on the same rows already loaded for the panel.
- Not built (per scope): reference-hardware benchmark corpus, CI
  enforcement gate — both need infra decisions beyond this slice.

**Proof:** new `tests/test_perf_p95.py` (9 tests) — empty/single/below-
threshold refuse honestly, known-input nearest-rank matches manual calc
(order-independent), min_samples override, non-numeric/missing
`wall_time_ms` rows dropped, officer-bucket filter separates buckets,
report text includes overall + all 3 bucket lines. All PASS.
`python dev.py verify --tier fast` — ALL PASSED.
`python dev.py perf-p95` run against the real (this-session-generated)
history file: `overall: p95=4725.54s (n=20)`, `<=25 officers: p95=12857.93s
(n=8)`, 100/500 buckets honestly report "Not enough data" (no real data in
those tiers yet).

**UI verified live** (chronos-web preview): navigated Simulator → Find Best
→ Search History, screenshot-confirmed `p95: 123.79s (n=12)` line renders
under "Recent Optimizer Searches" title, above the row list.

## 2026-07-23 — Search-history replay (Phase 3 "replay" slice)

Master plan §14 Phase 3 "replay." Prior audit was right: `append_search_history`
only logged 6 summary fields, no config snapshot, no re-run path.

- `logic/optimizer_features.py` (~1013-1105): `append_search_history` now
  also stores `entry["config_snapshot"]` (JSON round-tripped via
  `default=str`, same convention as `export_form_config_json`) and
  `search_exhaustive`. `search_history_path()` file is a flat JSON list
  (`logs/optimizer_search_history.json`) — **not a DB table**, contrary to
  the task brief's assumption; no schema/migration needed, this store never
  went through `database.py`. New `replay_search_history(entry)`: pulls
  `config_snapshot`, calls `run_staffing_optimizer(**snapshot)`
  (logic/scheduling_sim.py, unchanged) — naturally hits the aa5ac88
  deterministic cache when the snapshot matches a still-warm
  exhaustive-complete run. Reports `replay_original_exhaustive` +
  `replay_note` honestly (same spirit as `search_exhaustive`/
  `search_complete`) rather than claiming every replay is guaranteed-identical.
- `gui/pages/simulator/page.py` (~2846): `append_search_history` call now
  passes `config_snapshot=job_kw` (the exact kwargs already sent to
  `run_staffing_optimizer_isolated`) and `search_exhaustive=result.get(...)`.
- `gui/pages/simulator/results_panel.py` `show_search_history()`: each row
  gets a **Rerun** button — calls `replay_search_history(row)`, applies
  `best` via existing `_apply_ranked_option`, closes dialog, notifies with
  `replay_note`. Rows with no `config_snapshot` (pre-existing history from
  before this change) notify a warning and leave the dialog open instead of
  crashing.

**Proof:** new `tests/test_search_history_replay.py` (4 tests): config
snapshot round-trips through the JSON store; replay of a mocked
exhaustive-complete original hits the cache (solver called once total, not
twice) and reports `replay_original_exhaustive=True`; replay of a
budget-truncated original is a real second solve
(`replay_original_exhaustive=False`, note says "fresh re-solve"); replay with
no stored snapshot fails honestly instead of guessing. All PASS.
`tests/test_optimizer_cache.py` + related (11 total) — no regression.
`python dev.py verify --tier fast` — ALL PASSED.

**UI verified live** (chronos-web preview, logged-in admin session): ran a
real Find Best search (hard-fail case, "No Perfect Schedule"), opened Search
History, confirmed the new **Rerun** buttons render per row including old
pre-change rows. Clicked Rerun on the just-created row — toast progressed
"Rerunning search…" → "Rerun failed: No Schedule Meets The Selected Hard
Constraints" (correctly honest — same outcome as the original, not a false
"fixed" claim). Clicked Rerun on an old 2026-07-22 row lacking
`config_snapshot` — no crash, dialog stayed open (graceful, as coded).
Screenshot-verified, not just DOM-inspected.

Not touched (per scope): solver search behavior/objective/pool logic, the
cache mechanism itself beyond calling `run_staffing_optimizer`, performance
p95 rollups, conflict-explanation work.

## 2026-07-23 — Deterministic optimizer job cache (in-process)

Master plan §4 "identical deterministic jobs use reproducible cache keys."
Audit was right: prior caches (`_score_metrics`/etc micro-memoization) speed
up search internals, not whole-job reuse.

- `logic/scheduling_sim.py` (~9-45, new): `_OPT_CACHE` module dict + sha256
  `_optimizer_cache_key()` over the canonicalized (sorted-keys JSON,
  `default=str`) deterministic inputs. `clear_optimizer_cache()` test hook.
- `run_staffing_optimizer()` (~118-...): builds `call_kwargs` (every
  deterministic param — excludes `progress_callback`/`cancel_check`,
  callables aren't part of a job's identity), hashes it, returns the cached
  result on hit with zero solver work, else calls
  `optimize_staffing_scenarios` and stores the result **only if
  `result["search_exhaustive"]` is True**.
- **In-process, not SQLite** — chosen deliberately: results embed nested
  dict/list rows plus a `SimulationReport` dataclass; safe JSON/pickle
  round-tripping of that is a separately-scoped effort. Worst case on a miss
  is a cold re-solve, never a stale/malformed schedule. Not durable across
  process restarts or across `run_staffing_optimizer_isolated`'s child
  processes (each child gets its own empty cache) — acceptable for this
  slice, flagged as a residual.
- **Time-limit honesty (step 3 of the task):** `staffing_optimizer.py` already
  computes `search_exhaustive = not cancelled and not budget_exhausted`
  (~3127) — reused as-is rather than inventing a new flag. A budget-truncated
  or cancelled "best so far" is solved fresh every call, never cached —
  same spirit as `BumpChainSuggestion.search_complete`'s honest
  incomplete-vs-complete tagging.
- Confirmed no RNG in the search path (`grep random` in
  `staffing_optimizer.py` — no hits), so a completed (`search_exhaustive`)
  run really is reproducible for identical inputs.

**Proof:** `tests/test_optimizer_cache.py` (6 new, mocks
`staffing_optimizer.optimize_staffing_scenarios`): identical job → solver
called once, second call is a cache hit (`assertIs` same object); changing
`officer_counts` → solver called twice (miss); cache key changes when
`shift_starts` changes; `budget_exhausted=True` result never cached (2 calls,
2 solves); `cancelled=True` result never cached (2 calls, 2 solves);
progress_callback/cancel_check don't affect the key (still a hit). All PASS.
`tests/test_coverage_optimizer.py` + `test_staffing_config.py` +
`test_staffing_insights.py` + `test_staffing_search_status.py` +
`test_staffing_stress_fatigue.py` — 43 passed, no regression.
`python dev.py verify --tier fast` — ALL PASSED.

Not done (out of scope): no durable/SQLite persistence; no UI cache-hit
indicator; `run_staffing_optimizer_isolated` child processes don't share the
cache with the parent or each other.

## 2026-07-23 — P1.2 pool: real outcome-based diversity check + max_solutions 5→15

Master plan §4 stage 4 ("diverse alternatives... compare coverage, overtime,
fairness, fatigue, preferences, stability"). Audit was right: the CP-SAT pool
loop in `staffing_cpsat.py` (~496-614, unchanged this session — see why below)
only excludes on aggregate `(variant,phase,start)` profile counts, not actual
outcome distance. Fix landed one layer up, at the pool's only call site:

- **Why not inside staffing_cpsat.py:** the CP-SAT solve has no access to
  coverage/overtime/fairness/fatigue numbers — those only exist after
  `simulate_schedule()` replays each pool candidate, which happens in
  `staffing_optimizer.py` (~2190 `full_sim = simulate_schedule(full_cfg)`).
  So the real per-candidate metrics (`fm = full_sim.metrics`) are only
  available at the `cpsat_sols` consumption loop, not inside the solver.
- `logic/staffing_optimizer.py` (~986-1050, after `_score_metrics`): added
  `_outcome_vector(m, ...)` (reuses the existing `_violation_vector`
  coverage/windows/gaps/flsa/annual/annual_spread fields + the same
  rest_failures/consecutive_work_failures fatigue fields `_score_metrics`
  already reads — no new metrics invented), `_assignment_overlap_frac(a, b)`
  (fraction of officer-day cells with identical assigned start between two
  `officer_cycle_starts`), `_is_near_duplicate_candidate(...)` (reject only
  if outcome-vector L1 distance ≤1.5 tolerance AND assignment overlap >90%
  — both signals required, matches the task's minimal-bar spec).
- Wired into the `cpsat_sols` loop (~2139-2247): each pool solution's
  `(vec, officer_cycle_starts)` checked against a per-batch `_pool_kept`
  list before `results.append(row)`; near-dup candidates are skipped (first
  candidate in a batch is always kept, so `_full_solved` bookkeeping is
  unaffected).
- `max_solutions=5`/`pool_time_limit_sec=15.0` hardcoded at the one caller
  → new module constants `POOL_MAX_SOLUTIONS = 15` /
  `POOL_TIME_LIMIT_SEC = 30.0` (top of `staffing_optimizer.py`, ~159-166).
  Not UI-plumbed (explicitly out of scope, same boundary as the prior
  search-profile-selector entry below).

**Timing evidence** (`solve_full_assignment` direct, 24 officers, 12h shifts,
2-start pattern, coverage_247=2, 45s pool budget so no truncation):
max_solutions=5 → 5.15s; =10 → 6.14s; =15 → 10.12s. 15 stays well under the
new 30s `POOL_TIME_LIMIT_SEC` ceiling, so raising to 15 doesn't blow up
search time on a representative scenario.

**Proof:**
- `tests/test_pool_diversity.py` (9 new tests): outcome-vector equality/
  inequality, assignment-overlap (identical/disjoint/empty), and the core
  claim — `test_old_profile_only_dedup_would_have_kept_this_but_new_check_rejects`
  proves a candidate pair with >90% overlapping rosters + identical outcome
  metrics (the exact case the old aggregate-count dedup would miss, since a
  differently-permuted or nearly-identical roster can still land on a
  different `(variant,phase,start)` count profile) is now rejected, while
  same-roster-different-outcome and different-roster-same-outcome pairs are
  both correctly kept as diverse. All PASS.
- `tests/test_coverage_optimizer.py` full run — 17 passed, no regression.
- `python dev.py verify --tier fast` — ALL PASSED.

Not done (out of scope per task): no lexicographic/Pareto soft-goal objective
layer (single scalar `Minimize(annual-hours deviation)` unchanged); no
conflict-explanation/assumptions work; `POOL_MAX_SOLUTIONS`/
`POOL_TIME_LIMIT_SEC` still not user-configurable from the UI (same reason
as the search-profile entry below — nothing upstream threads it through
`run_staffing_optimizer`).

## 2026-07-23 — Search profile selector (Quick/Balanced/Deep Proof/Custom)

Master plan §4 slice. Audit's assumption was wrong: `staffing_cpsat.py`'s
`time_limit_sec`/`max_solutions`/`pool_time_limit_sec` are NOT reachable from
the UI — they're hardcoded internal to `staffing_optimizer.py`'s per-candidate
CP-SAT calls (line ~2114/2131), several layers below what the simulator UI
controls. The only knob actually wired end-to-end from UI → `run_staffing_optimizer`
→ `optimize_staffing_scenarios` is `time_budget_seconds`, plus the existing
`search_depth` ("standard"/"deep") toggle that changes free-length grid density.
Built profiles on top of that real surface instead:

- `gui/pages/simulator/state.py`: added `SEARCH_PROFILES` dict (quick=30s/standard,
  balanced=120s/standard — matches prior unconditional default, deep_proof=300s/deep
  — matches prior "deep" toggle behavior) and `SimulatorState.search_profile: str = "custom"`.
- `gui/pages/simulator/page.py`: new "Profile" toggle (Custom/Quick/Balanced/Deep
  Proof) next to the existing Depth toggle. Non-custom profile sets Depth's value
  and greys it out (`.props("disable")`, the same pattern already used for
  btn_gen/btn_compare during a running search); Custom removes the disable and
  leaves Depth manual. `_optimizer_kwargs`'s `time_budget_seconds` line now checks
  `state["search_profile"] in SEARCH_PROFILES` first, else falls back to the
  original depth-based 120/300 calc unchanged — so default ("custom") behavior
  is byte-identical to before this change.

**Proof:**
- `tests/test_search_profiles.py` (6 new tests): quick < deep_proof budget,
  deep_proof > balanced budget + depth="deep", balanced == prior hardcoded
  120.0/standard, "custom" not a preset key (no-op guard), default state is
  "custom", static check that page.py wires SEARCH_PROFILES + the disable/
  remove-disable pattern. All PASS.
- `python dev.py verify --tier fast` — ALL PASSED.
- `tests/test_simulator_constraints.py` full run — 31 passed (no regression).
- UI verified live: started `chronos-web` (`main.py --web`) via browser preview,
  navigated to Simulator. Confirmed via JS DOM inspection (click on Profile
  toggle buttons didn't register through ref-coordinate click — used
  `button.click()` DOM dispatch instead, which Quasar/Vue does pick up):
  clicking "Quick" selects Standard depth + disables both Depth buttons;
  clicking "Deep Proof" selects Deep depth + still disabled; clicking "Custom"
  re-enables Depth (previous Deep selection stays but is now editable). All
  three states confirmed by reading `button.className`/`.disabled` directly.

Not done (out of scope per task): no UI exposes `max_solutions`/`pool_time_limit_sec`
since nothing upstream threads them from the simulator page — wiring those would
mean adding new params through `run_staffing_optimizer`/`optimize_staffing_scenarios`
down into the per-candidate CP-SAT calls, which is a bigger, riskier change than
this thin-layer task scoped for. Flagging for whoever picks up the next slice of
Phase 3: if "Deep Proof" needs true stronger-proof CP-SAT settings (not just a
longer wall-clock budget), that's the follow-on work.

## 2026-07-23 — Phase 2 items 2 & 5 landed (batch bump-chain staleness fixed)

User approved the thread-local conn-scoping approach (option 2) after the
prior session's naive fix hit the SQLite lock dead end. Implemented:

- `database.py`: added `threading.local()` (`_scoped_local`) + new
  `scoped_write_connection()` context manager (reentrant/nestable — a
  nested call on the same thread reuses the existing connection instead of
  opening a second one). Modified `connection()` so that when a scoped
  connection is active on the thread, nested `with connection() as conn:`
  calls transparently reuse it instead of opening a fresh
  `sqlite3.connect()` (and don't close it — only the outermost
  `scoped_write_connection()` owns close). `connection()` outside any scope
  is byte-for-byte unchanged (opens fresh, closes on exit).
- `logic/requests.py::bulk_approve_auto_ok_requests` (~1231-1251): batch
  transaction now opens via `scoped_write_connection()` instead of bare
  `connection()`. Per-candidate loop no longer passes the stale
  pre-transaction `_verified_suggestion`/`coverage_verified=True` shortcut —
  it calls `process_day_off_request` the same way the single-request path
  does with no suggestion override, so each candidate's bump chain is
  computed fresh against current state (mutated by earlier candidates
  already applied this batch) via `suggest_bump_chain` → `search_best_coverage_plans`
  → `get_generated_schedule_day_context`, all of which now reuse the scoped
  connection instead of deadlocking on the write lock. (Tried
  `preferred_chain=` with exact-chain matching first — wrong: it requires
  the recompute to reproduce the identical stale chain, so it fails closed
  instead of picking a corrected one. Dropped in favor of a plain recompute,
  matching the existing non-manual else-branch.)

**Proof:**
- New `tests/test_coverage_optimizer.py::test_bulk_approval_recomputes_chain_for_later_candidates`:
  two officers (ids 3, 4) are the only two non-command staff on the 10:00
  squad-A shift; their independent pre-batch `suggest_bump_chain` calls both
  target the same replacement (officer 6) — the real staleness condition.
  After batch approval, asserts both requests are approved with **different**
  replacement officers (no double-booking) — PASS.
- New `tests/test_database_backup.py::ScopedWriteConnectionTests` (4 tests):
  nested `connection()` calls inside `scoped_write_connection()` return the
  identical connection object (`id()` equal); nested `scoped_write_connection()`
  calls also reuse the same connection; after the scoped block exits
  (normally or via exception) the thread-local is cleared and a fresh
  `connection()` call opens a genuinely new connection — all PASS.
- `test_bulk_approval_rolls_back_every_request_when_second_outbox_fails`
  (the test the naive fix broke last session) — still PASS, no
  `database table is locked` error, rollback still atomic.
- `python dev.py verify --tier fast` — ALL PASSED (imports, audit 10/10,
  readiness 10/10).
- Full `tests/test_coverage_optimizer.py`, `tests/test_logic.py`,
  `tests/test_regressions.py`, `tests/test_notifications_swaps_exports.py`,
  `tests/test_override_authority.py`, `tests/test_database_backup.py` — 32+28
  tests, all green (repo has no `tests/test_requests*.py`; bulk-approval
  coverage lives in `test_coverage_optimizer.py`/`test_logic.py`, both run).
- Grepped `logic/*.py` for other `_transaction_conn`/manual `with
  connection() as conn:` usage (38 files) — all use the plain pattern, none
  conflict; `scoped_write_connection()` is currently only entered from
  `bulk_approve_auto_ok_requests`, so behavior elsewhere is unchanged.

Master plan §14 Phase 2 items 2 and 5 are now **DONE**. Phase 2 status:
items 1, 2, 3, 4, 5, 6 all done — Phase 2 audit list is fully closed.

## 2026-07-23 — Phase 2 item 6 landed (shift-swap CAS guard)

`2a27b3e`: `logic/requests.py::process_shift_swap` approve path had no
optimistic-concurrency guard on its `UPDATE shift_swaps` — unlike
`process_day_off_request`'s approve path, which already does
`WHERE id = ? AND status = ?` + rowcount check. A retry (crash mid-tx) or a
genuine race (two approvals of the same swap) could re-run
`_insert_override_record` twice and double-apply. Fixed by adding the same
`AND status = ?` + `rowcount != 1` → rollback + "changed after preview"
pattern used on the day-off path. Two new regression tests in
`tests/test_notifications_swaps_exports.py`
(`test_process_shift_swap_retry_does_not_double_apply`,
`test_process_shift_swap_race_guarded_by_status_cas`) prove the double-apply
is blocked. `verify --tier fast` green (23/23 in that test file, audit
10/10, readiness 10/10).

Master plan §14 Phase 2 status now: items 1, 3, 4, 6 done. Item 2 (batch
bump-chain staleness) confirmed-but-reverted, high risk, skip until user
verifies — do not re-attempt the conn-threading fix without user sign-off
(known SQLite lock dead end, see entry below). Item 5 (joint batch solving)
still PARTIAL, shares item 2's staleness gap — likely blocked on the same
fix. Day-off/shift-swap **reject** paths still lack a CAS guard too, but
rejection has no side effects beyond a possible duplicate notification —
left alone as out of scope for item 6's "smallest safe fix."

**Next Phase 2 slice (not started):** item 2/5 both need the `conn`-threading
fix through `search_best_coverage_plans`/`get_generated_schedule_day_context`
— that's the only remaining non-trivial item, and it's explicitly gated on
user verification before re-attempting. Absent that, Phase 2's low-risk
additive items are exhausted; next session should check master plan §14 for
whether other sections have unstarted low-risk items, or get user sign-off
to tackle item 2/5 properly (thread conn as an optional param, not a
refactor of the call chain).

## 2026-07-23 — Phase 2 item 3 landed (capped search → honest incomplete, not silent failure)

`ba6b10e`: `logic/coverage_optimizer.py::search_best_coverage_plans` has a
hard `max_nodes = 400` cap (line ~423) in addition to beam width/depth
limits. When that cap cut the search off before the beam ran empty, the
returned "no complete plan" result was indistinguishable from a real proof —
same message, same `failure_reason`. Added `BumpChainSuggestion.search_complete:
Optional[bool]` (models.py, purely additive) — `False` when node-budget-capped
with candidates still unexplored, `True` when the beam genuinely ran empty,
`None` for untouched call sites. `failure_reason` intentionally kept as
`"no_replacement"` in both cases (changing it would break
`override_authority.py`'s `CONSTRAINT_ALIASES` mapping to
`"coverage_minimum"`). 82 tests pass, `verify --tier fast` green. Nothing
downstream reads `search_complete` yet — it's there for a future UI/decision
report to surface, same "define first, wire consumer later" pattern as
`logic/scheduling_contracts.py`.

This is master plan §14 Phase 2 item 3 (of the 6 audited below). Items 1 and
3 are now done this session; item 2 (batch bump-chain staleness) is
confirmed-but-reverted (SQLite lock issue, high risk, skip until verified);
items 4/5/6 status unchanged from the audit below.

## 2026-07-23 NEWEST — Master plan Phase 2 started (bumping/leave correctness)

Committed the prior session's large uncommitted diff (was sitting across 3
areas for multiple sessions — see entries below, now landed as 3 commits:
`1f60a37` scheduling contracts/Tier A, `a83f3c0` MFA/OIDC/audit/withholding,
`86d368b` this doc). Also fixed a real gap: `CLAUDE.md` (auto-loaded every
Claude Code session) had no pointer to `AGENTS.md`/`docs/HANDOFF.md`/the
master plan — that bootstrap only existed for Grok/Cursor via
`scripts/session_auto_bootstrap.py`'s SessionStart hook, which Claude Code
doesn't have wired. Fixed in commit `533b377`.

**Then began master plan §14 Phase 2** ("bumping and leave correctness").
Audited the 6 Phase 2 requirements against real code (not just trusting this
doc's own prior "already correct" claims — 2 of them turned out to be
overstated):

1. **Typed constraint-specific relaxation — was PARTIAL, now DONE** (`7d4aba4`).
   `logic/override_authority.py` already built a typed relaxation record
   (constraint_code/reason/expiry) for the audit trail, but enforcement at
   `suggest_bump_chain`/`optimize_day_off_coverage` still collapsed any
   `supervisor_override=True` into relaxing BOTH minimum-rest and
   consecutive-work together — a manual-review override approved for one
   violation silently also permitted the other, unapproved. Added
   `relaxed_constraint: Optional[str]` to both functions (bump_optimizer.py,
   coverage_optimizer.py); `requests.py::process_day_off_request` now passes
   the actual failed constraint instead of a bare boolean. Both the rust
   search and python fallback get the same value so they can't disagree.
   Legacy callers (e.g. `ops_desk.py` preview) that don't pass it keep old
   blanket-relax behavior — unchanged. Verified: 56+4 targeted tests +
   `verify --tier fast` (including AUD-007 which exercises this exact path).
2. **Whole-plan bump verification in batch approval — CONFIRMED PARTIAL, NOT
   FIXED, high risk, needs a follow-up session.** In
   `bulk_approve_auto_ok_requests` (`logic/requests.py` ~1130-1250), each
   candidate's bump chain/coverage check is computed once *before* the batch
   write transaction opens, then applied via `_verified_suggestion` inside
   the transaction **without recomputing against schedule state as mutated
   by earlier candidates in the same batch** — unlike the single-request
   `preferred_chain` path (lines 845-872), which does recompute.
   **Attempted the obvious fix** (swap `_verified_suggestion=suggestion` for
   `preferred_chain=list(suggestion.chain)` + drop the stale
   `coverage_verified=True` shortcut, reusing the already-tested
   recomputation path) — **it broke a real test**
   (`test_bulk_approval_rolls_back_every_request_when_second_outbox_fails`)
   with `database table is locked: schedule_overrides`: the recomputation
   path (`search_best_coverage_plans` / `get_generated_schedule_day_context`)
   opens its own connection instead of accepting the batch's open write
   transaction's `conn`, and SQLite's single-writer model rejects the nested
   read while the batch transaction holds the write lock. **Reverted in the
   same session** (working tree confirmed byte-identical to before the
   attempt). Real fix needs the recomputation call chain threaded to accept
   an existing `conn` instead of always opening `connection()` fresh — a
   bigger, more invasive change than a one-line swap. Flagged as **high
   risk, skip until user verifies** per this session's instruction. Do not
   re-attempt the naive swap — it's a known dead end that will reproduce the
   same lock error.
3. Capped-search → `UNKNOWN` reporting in bump chain search — **NOT DONE**,
   not attempted this session. `coverage_optimizer.py` tracks
   `alternatives_considered` but no cap/timeout path returns an explicit
   incomplete/UNKNOWN status distinct from a proven-impossible failure.
4. Leave lifecycle atomicity (single-request path) — confirmed **DONE**,
   already correct: one transaction, commits once, rolls back on exception
   (`tests/test_regressions.py::test_approve_not_committed_when_override_insert_fails`).
5. Joint batch solving — confirmed **PARTIAL**: priority-ordered greedy
   application, not a joint solve; shares the staleness gap from item 2.
6. Optimistic concurrency / idempotent retries — **NOT VERIFIED, likely
   missing.** No `row_version`/`ETag`/`ON CONFLICT` guard found in
   `requests.py`. HANDOFF's prior claim ("already correct, tested" — see
   "ALL TIER A CLOSED" item 8 below) is **not supported by any matching
   test** — no `stale_preview`/`idempoten`/`outbox`-named test exists beyond
   one unrelated Twilio-outbox test. Correcting the record here; don't cite
   item 8 below as proof of concurrency safety without adding that test
   first.

**Next Phase 2 slice (not started):** either (a) thread a real `conn`
parameter through `search_best_coverage_plans`/
`get_generated_schedule_day_context` so batch approval can safely recompute
mid-transaction (fixes item 2, unblocks the real correctness gap), or (b) add
capped-search UNKNOWN reporting (item 3, no concurrency risk, purely additive
status field) — (b) is the lower-risk starting point if picking up cold.

Still uncommitted after this entry: nothing — working tree clean except
untracked `toolguide.md` (intentional, reference doc not code).

## 2026-07-23 NEWEST — first real UI consumer of canonical_status/simulation_report

- `gui/pages/simulator/page.py` (Find Best result summary, right after the
  existing "Solver status:" line) now renders `result["canonical_status"]`
  and, when present, `simulation_report.verification`'s verdict
  ("Independent verification: PASSED/FAILED (violations...)"). Purely
  additive display — does not change search control flow, ranking, or any
  existing field.
- **Found and fixed a real pre-existing bug this surfaced**:
  `logic/staffing_optimizer.py::_verification_from_ranked_rows` and
  `_candidate_from_ranked_row` were reading `row["violations"]` (the full
  checked-category *vector dict*, e.g. `{"annual": 0, "windows": 0, ...}`,
  present regardless of whether that category actually failed) as if it
  were a list of actual failures — so every `VerificationReport.violations`
  and `ScheduleCandidate.relaxations` listed **every checked category**,
  pass or fail. `row["failed_constraints"]` was the already-correctly
  filtered list and was being used backwards for `checked_constraints`
  instead. Swapped both: `violations`/`relaxations` now come from
  `failed_constraints` (actual failures only), `checked_constraints` from
  the full vector's keys (everything evaluated). This directly serves the
  master-plan "soft preferences never silently redefine hard feasibility /
  honest verification" law — previously a passing (`verified=True`) result
  would still list every constraint category as a "violation" if a UI ever
  read the field, which nothing did until this session.
- Verified: repro before/after (`violations` went from
  `['annual','annual_spread','coverage_247','flsa','gaps','windows']` on a
  passing result to just `['annual']`, matching the one soft-metric that
  was actually slightly off). `pytest tests/test_scheduling_contracts.py
  tests/test_coverage_optimizer.py tests/test_simulator_constraints.py
  tests/test_feature_ui_static.py`: 71 passed. `verify --tier check` not
  run this pass — not browser-verified in the live UI this session either
  (text-only change to an existing summary block; recommend a Find Best
  click-through before calling this fully proven).
- Still uncommitted — ask before committing.

## 2026-07-23 NEWEST — policy_hash fix + callable input_hash instability fix

- Root-cause fix in `logic/scheduling_contracts.py::_json_default`: a
  non-JSON-serializable callable (e.g. `progress_callback`) used to fall
  back to `str(obj)`, which embeds the object's runtime memory address —
  two calls with logically identical kwargs but a freshly-built closure
  (or the same callback rebound each process run) hashed differently. Now
  callables hash by stable `__qualname__` instead. Fixes the exact
  instability named in the prior brief for `optimize_staffing_scenarios`'s
  `input_hash`.
- New `POLICY_KEYS` + `compute_policy_hash()` in `scheduling_contracts.py` —
  hashes only the constraint/policy subset of kwargs (rest hours, annual
  hours target/variance/hard, max consecutive days, coverage_247,
  extra_windows, constraint_weights/priority, require_hard_ok), excluding
  instance data (officer count, dates, patterns) and search-only knobs
  (time limits, solution-pool size, callbacks). Two runs against the same
  rule set now hash identically regardless of problem instance or budget.
- Wired `policy_hash=compute_policy_hash(kwargs)` into all 4
  `SimulationReport` builders: `logic/staffing_cpsat.py::_cpsat_result_to_report`
  (covers `solve_phase_variant`/`solve_full_assignment`/`solve_cycle_day_starts`)
  and `logic/staffing_optimizer.py::_ranked_result_to_report`
  (`optimize_staffing_scenarios`). Previously always `""`.
- `seed` was investigated and left `None` — no CP-SAT call site sets
  `random_seed`/uses randomized search, so there is no seed to record yet;
  not a bug to fix, just genuinely unset. Revisit if randomized search is
  ever added.
- Verified: inline repro (`compute_input_hash` now stable across two
  distinct closures with equal logical kwargs; `compute_policy_hash` proven
  to ignore a changed `time_limit_sec`). `pytest
  tests/test_scheduling_contracts.py tests/test_simulator_constraints.py`:
  49 passed. `tests/test_coverage_optimizer.py`: 16 passed. `verify --tier
  check` not run this pass.
- Still uncommitted — ask before committing.

## 2026-07-23 NEWEST — toolguide.md AUDIT + 4 SCOPED ACTIONS (A–D), all verified

- Source: user supplied `toolguide.md` (untracked, repo root — ~50 third-party
  scheduling/HR/security tools + a CJIS/enterprise wishlist). Full analysis +
  plan at `C:\Users\Windows\.claude\plans\read-toolguide-md-they-are-luminous-bunny.md`.
  Verdict on ~46 of the ~50 rows: **reject** — either redundant with existing
  CP-SAT/payroll/timecard/cert code, or a different stack (PHP/Laravel,
  JVM, Rust binary, Flutter/SwiftUI, Next.js/Supabase) than the committed
  Python/NiceGUI→React migration path. Full per-row reasoning is in the plan
  file, not repeated here — read it before re-litigating any specific tool.
  4 concrete gaps were real and got built this session (below). One
  architecture conflict was **flagged, not resolved**: `logic/tenant.py`
  (file-per-tenant) vs. master plan §9 ("PostgreSQL 17... row-level
  security") describe two different multi-tenancy models — needs an explicit
  user decision before Phase 4, not a default pick.

- **A — `ortools` pinned as a real core dependency.** Was completely absent
  from `requirements.txt` (only a commented-out dev optional in
  `requirements-dev.txt`) despite CP-SAT being the completed Phase 1
  scheduling core. Now `ortools>=9.10,<10.0` in `requirements.txt`.

- **B — federal income tax withholding.** New `logic/payroll/withholding.py`
  — table-driven IRS Pub 15-T (2026) percentage-method calculator (Worksheet
  4: Steps 1–4, W-4 2020+ format, Step 2 checkbox schedules, all 3 filing
  statuses × weekly/biweekly/semimonthly/monthly). Tables were fetched and
  extracted directly from irs.gov (pdfplumber), not from memory — this was a
  real gap; `logic/payroll/pay_codes.py` only ever computed gross pay, no
  withholding existed anywhere. Wired into the `logic.payroll` package
  facade. 15 tests in `tests/test_federal_withholding.py`, all passing,
  checked against the published bracket tables by hand. Only 2026 tables are
  loaded — add a new tax year to `_WITHHOLDING_TABLES` when needed, don't
  extrapolate.

- **C — MFA (TOTP) + OIDC/SSO, backend + UI, browser-verified.**
  - New `logic/mfa_auth.py`: per-user TOTP, secret stays inactive
    (`mfa_enabled=0`) until a real code confirms it (no self-lockout).
    New `app_users` columns `mfa_secret`/`mfa_enabled`/`mfa_enrolled_at` via
    the existing pre-migration `ALTER TABLE` pattern in `database.py`.
  - `logic/users.py::authenticate_user` (both password and LDAP branches)
    now returns `{"mfa_required": True, "user_id": ...}` instead of
    completing login when the matched user has MFA enabled; new
    `complete_mfa_login(user_id, code)` finishes it.
  - New `logic/oidc_auth.py`: mirrors `logic/ldap_auth.py`'s field-trial /
    health-check / production-sign-off shape exactly. Links to *existing*
    `app_users` rows by username claim — does not auto-provision. The
    HTTP callback route itself is NOT built (UI/routing wiring only, out of
    scope this session) — `complete_oidc_login()` is ready for a route to
    call once one exists.
  - New permissions `security.manage_mfa` / `security.manage_sso`
    (Administration-only) in `permissions.py`, enforced in
    `save_oidc_field_trial_settings` and cross-user `disable_mfa`.
  - New deps: `pyotp>=2.9`, `authlib>=1.3` in `requirements.txt` (real, not
    optional — `ldap3` stays optional in `requirements-dev.txt`, unchanged).
  - UI: `gui/pages/login.py` now has a second-step authenticator-code field
    (hides username/password, shows code input, `data-testid="login-mfa-code"`
    / `"login-mfa-submit"`) that only appears when `mfa_required` comes back.
    `gui/pages/security.py` got two new panels: "Multi-Factor Authentication"
    (self-service enroll/confirm/disable) and "OIDC / SSO Field Trial" (same
    button layout as the existing LDAP panel).
  - **Verified live in browser, not just unit tests**: started `chronos-web`
    preview, logged in as admin, enrolled MFA (captured the real TOTP secret
    from the page, generated a code with `pyotp` CLI), confirmed enrollment,
    signed out, signed back in — correctly gated on the code field, entered
    the real code, landed on the dashboard — then disabled MFA again to
    leave the seeded admin account clean. OIDC panel confirmed rendering
    with checklist/health-check UI (no live IdP to test the actual redirect
    against — that needs the not-yet-built callback route).
  - Tests: `tests/test_mfa_auth.py` (8), `tests/test_oidc_auth.py` (9), all
    passing.

- **D — hash-chained (tamper-evident) audit log**, instead of toolguide's
  "blockchain audit trail" idea (rejected as needless complexity for a
  single-tenant-per-agency system). `logic/users.py::log_audit_action` now
  computes `row_hash = sha256(prev_hash|action|entity_type|entity_id|user_id|details|created_at)`
  and chains it to the previous row (`audit_log.prev_hash`/`row_hash`
  columns, added via the same pre-migration pattern). Uses `BEGIN IMMEDIATE`
  around the read-prev/insert to serialize concurrent writers — under
  SQLite's single-writer model this is enough; it is not a distributed-
  ledger guarantee and doesn't try to be. New `verify_audit_chain()`
  recomputes every hash from stored fields (doesn't trust the stored hash),
  returns the first broken row on tamper/delete. Tests:
  `tests/test_audit_chain.py` (4), all passing — covers tamper, delete,
  and correct-chain-linkage cases.

- **Regression proof this session:** every new test file passes standalone;
  existing `tests/test_users_security.py` (12), `tests/test_payroll.py` +
  `test_pay_code_rules.py` + `test_payroll_flow_smoke.py` (17) unaffected.
  A full sequential `unittest discover` run showed `ERROR` on 4
  `test_simulator_constraints.py` cases under full-suite CPU load; re-ran
  that file alone → 30/30 pass in 132s. This matches the **already-
  documented** CP-SAT CPU-load nondeterminism from the Tier-A-closed entry
  below (isolated-run vs full-sequential-run timing variance) — not a
  regression from this session's changes, which never touched
  `staffing_cpsat.py` or the simulator. `verify --tier check` (ship gate)
  **NOT run this session** — don't claim shippable off this entry alone.

- **Still uncommitted** — ortools/pyotp/authlib pins, `mfa_auth.py`,
  `oidc_auth.py`, `withholding.py`, `database.py`/`users.py`/`permissions.py`
  edits, `login.py`/`security.py` UI, and all 4 new test files. Ask before
  committing. Concurrent session (see entries below) touched
  `coverage_timeline.py`/`optimized_schedule_apply.py`/`simulator.py` at the
  same time — confirmed with user as expected (parallel session), not a
  conflict to resolve.

- **What's NOT done from the toolguide plan**: the OIDC redirect/callback
  HTTP route (UI/routing only — `complete_oidc_login()` is ready and tested,
  nothing calls it yet), and Shadcn Calendar (explicitly deferred until the
  React/Vite migration actually starts — no action expected before then).

## 2026-07-23 LATEST — FIRST StaffingProblemSpec CONSUMER

- `simulator.py::simulate_schedule` (both the rust fast-path and the python
  `_simulate_schedule_fixed_n` success returns) now calls
  `build_staffing_problem_spec(config)` and stamps `SimulatorResult.problem_spec`
  (dict) + `.input_hash` (`compute_input_hash`) on every successful result.
  Additive — 2 new optional fields, all existing `SimulatorResult` fields
  unchanged, no caller's existing field reads affected.
- Verified: `python -c` smoke on both the rust and python code paths (both
  populate non-empty `problem_spec`/`input_hash`, differing hashes for
  differing configs). `pytest tests/test_simulator_constraints.py
  tests/test_scheduling_contracts.py`: 49 passed. `verify --tier check` not
  run this pass.
- Still nothing reads `problem_spec`/`input_hash` downstream (UI, other
  logic) — this closes "no caller builds/consumes StaffingProblemSpec yet",
  not the full consumer-wiring gap from the item-1 option in the prior list.
- Still uncommitted — ask before committing.

## 2026-07-23 LATER — PHASE 1 CANONICAL CONTRACTS (master plan §3), additive only

- Work only in `C:\Users\Windows\Desktop\Chronos Command GPT`. Repo-root clutter
  (`New Text Document.txt`, a stray `ChatGPT Image...png`) deleted this session
  — both untracked/unused, confirmed with user first.
- Master plan Tier A/B/C is a routing classification (see
  `docs/PRODUCT_MASTER_PLAN.md` §13), not a task backlog — don't look for a
  "Tier B list" like the Tier A one below; there isn't one.
- New file **`logic/scheduling_contracts.py`** — canonical `ScheduleStatus`
  enum, `to_canonical_status()` (legacy string → enum, unknown never
  collapses to INFEASIBLE), `compute_input_hash()`, and the master-plan §3
  typed dataclasses: `StaffingProblemSpec`, `CoverageDisruptionSpec`,
  `ConstraintProfile`, `SearchProfile`, `ScheduleCandidate`, `CoveragePlan`,
  `ScheduleChangeSet`, `SimulationReport`, `CoverageDecisionReport`,
  `VerificationReport`. **Definitions only where unwired** — read each
  producer below before assuming a call site emits/consumes one.
- **4 search entry points now stamp `canonical_status` + `simulation_report`
  additively** (legacy dict keys untouched, nothing's behavior changed):
  `logic/staffing_cpsat.py::solve_phase_variant`, `solve_full_assignment`,
  `solve_cycle_day_starts`; `logic/staffing_optimizer.py::optimize_staffing_scenarios`
  (also reached via `logic/scheduling_sim.py::run_staffing_optimizer(_isolated)`,
  confirmed pure passthrough).
- **Real independent verification wired in 3 places:**
  1. `logic/coverage_timeline.py::verify_schedule_candidate` — new canonical
     verifier entry point (recalculates occupancy from raw assignments,
     returns `VerificationReport`). Not yet called by any production path
     except item 2 below.
  2. `solve_cycle_day_starts` — its `simulation_report.verification` is a
     **real recheck** via `verify_schedule_candidate`, replaying the exact
     `cycle_starts_per_officer` starts (no duty-vector reconstruction, so no
     risk of a second inconsistent time model).
  3. `logic/optimized_schedule_apply.py::verify_plan_for_implementation` (the
     real production apply-time verifier, already Tier-A-correct) now also
     attaches `verification_report` built from its existing `ok`/`status`/
     `failures`/`unknown` output.
  4. `optimize_staffing_scenarios`'s `simulation_report.verification` is
     **adapted, not re-derived** — `logic/staffing_optimizer.py::_verification_from_ranked_rows`
     wraps each ranked row's already-computed `hard_constraints_ok`/`violations`
     (from `simulate_schedule()`'s own sweep-line check per
     `logic/staffing_cpsat.py` module docstring), because ranked rows don't
     carry per-minute assignment data to re-check from scratch.
  - **`solve_phase_variant` and `solve_full_assignment` deliberately do NOT
    get a `verification`** — investigated, not skipped by omission.
    `solve_phase_variant` never decides shift-start times at all (day-level
    only); minute-level verification of both already happens downstream in
    `simulator.py::simulate_schedule()`. Do not add a second reconstruction
    of that math inside `staffing_cpsat.py` — that's exactly the "one
    canonical time model" rule the master plan bans breaking.
- **First real producer of `StaffingProblemSpec`:**
  `simulator.py::build_staffing_problem_spec(config, ...)` builds one from a
  real `SimulatorConfig`. No consumer yet.
- **Nothing consumes any of this yet** — no UI, no downstream logic branches
  on `canonical_status`/`simulation_report`/`verification_report`/
  `input_hash`. This is the single biggest remaining gap before any of this
  is more than documentation-with-tests.
- Tests: `tests/test_scheduling_contracts.py` (new file, 18 tests). Full
  touched-suite regression run in slices this session, always green (latest
  combined run: 72 passed — `test_simulator_constraints.py`,
  `test_scheduling_contracts.py`, `test_coverage_optimizer.py`,
  `test_optimized_schedule_apply.py`). `verify --tier fast`: ALL PASSED
  (13s), run once mid-session. **`verify --tier check` (ship gate) NOT run
  this session** — don't claim shippable.
- **Still not committed.** All 2026-07-22/23 prior work plus this session's
  `logic/scheduling_contracts.py`, `simulator.py`, `logic/staffing_cpsat.py`,
  `logic/staffing_optimizer.py`, `logic/coverage_timeline.py`,
  `logic/optimized_schedule_apply.py`, `tests/test_scheduling_contracts.py`
  changes remain uncommitted. Ask before committing.
- **Next slice options, not yet done (pick one, don't guess which the user
  wants without asking — scope/risk vary a lot):**
  1. Wire a real consumer to branch on `canonical_status`/`simulation_report`
     (bigger — touches control flow, must not change existing behavior).
  2. `policy_hash`/`seed` still unset everywhere; `input_hash` on the
     `optimize_staffing_scenarios` path can go unstable if a callback/closure
     is in kwargs (falls back to `str()`).
  3. No caller builds/consumes `StaffingProblemSpec` yet.
  4. Bumping/leave/vacancy/overtime/live-schedule paths (Phase 2+) untouched
     by this pass — only simulator/CP-SAT + one apply-verifier were touched.

## 2026-07-23 NEWEST — ALL TIER A CLOSED, SHIP GATE GREEN

- Work only in `C:\Users\Windows\Desktop\Chronos Command GPT`.
- Preserve the extensive uncommitted 2026-07-22/23 simulator work — still uncommitted.
- **All 10 remaining Tier A items are closed** (diagnosis + audit + proof; most were
  already correctly implemented and only needed verification, not new code):
  1. CP-SAT six-officer 30s budget miss diagnosed as CPU-load nondeterminism in a
     long sequential single-process run (isolated 13.22s; full 569/569 suite passes
     at 371s) — not a routing/logic regression. Budget raised 30s→60s with the
     diagnosis recorded inline as a test comment. Do not re-diagnose.
  2. Typed relaxed-constraint override authority — already correct in
     `logic/requests.py::process_day_off_request` + `logic/override_authority.py`.
  3. Independent timeline verification — already wired to `logic/coverage_timeline.py`
     across solver/apply/bump/publish paths.
  4. Status translation (timeout/cancelled/unknown never reported as infeasible) —
     already correct, tested.
  5. CP-SAT lexicographic objectives + UI exposure — already fully wired end-to-end,
     including a live reorderable priority list in `gui/pages/simulator/page.py:588-610`.
  6. Atomic leave/batch approval — already correct, rollback-tested.
  7. Tenant isolation — audited (file-per-tenant, not shared-schema; no cross-tenant
     query surface). Added 2 new regression tests for `_slug()` path-traversal
     sanitization to `tests/test_residuals_dual_geo_tenant.py`.
  8. Stale preview / concurrency / idempotency — already correct, tested.
  9. OT-fill verified coverage chain — already correct, tested.
  10. Monthly publish verification + atomicity — already correct, tested.
- **`python dev.py verify --tier check` passed: `honest_gate: true`, 428s, all 8
  steps green.** See `logs/last_verify.json` (`2026-07-23T09:00:38Z`).
- Net new code this pass: one test-budget fix + 2 new tenant-isolation regression
  tests. Everything else in the list above was audit-only.
- Full detail: newest section of `logs/NEXT_SESSION_BRIEF.md`.
- **If starting new Tier A work:** open a fresh numbered list; the 10 above are done.
- Still not committed — ask the user before committing.

## NEXT SESSION
- **Read `AGENTS.md` and `CLAUDE.md` in full before doing anything else.** All rules in them are binding for every session, not just this one.
- **SIMULATOR WORK → read [`docs/SIMULATOR_OVERHAUL_PLAN.md`](SIMULATOR_OVERHAUL_PLAN.md) FIRST (authoritative, 2026-07-22).** Deep live evaluation + phased roadmap with checkboxes. Five findings PROVEN live (search-space dialog dead-ends, dishonest hour-scale estimates vs 21s CP-SAT reality, suggestion-popup trap, exhaustive search freezing the whole app). Contains guardrails, repro/proof commands, and browser-tool survival notes. Work the roadmap top-down; update its checkboxes when items land. Do not re-diagnose what it already proves.
- **2026-07-22 Phase 1 LANDED (solver-first core):** P1.1 objective function (minimize annual-hours deviation per officer), P1.2 solution pool (max_solutions=5 with aggregate-profile exclusion cuts, wired through optimizer → simulate_schedule verification), P1.3 specific-date windows in CP-SAT (no longer falls back to exhaustive), P1.4 Min-N binary search accelerated with CP-SAT infeasibility proofs (skip expensive full optimizer when proven impossible), P1.5 live progress callback from solver via CpSolverSolutionCallback. All 581 tests pass (0 fail). Live browser proof: 8 officers, 2-2-3 14-day, coverage 100%, 2008.9h avg, search 3.9s (vs 912k exhaustive layouts). See `docs/SIMULATOR_OVERHAUL_PLAN.md` for updated checkboxes.
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

**Last updated:** 2026-07-23 later (Phase 1 canonical scheduling contracts added — `logic/scheduling_contracts.py`, 4 search entry points stamp `canonical_status`/`simulation_report`, 3 real verification wirings, first `StaffingProblemSpec` producer — all additive, nothing consumes it yet · UNCOMMITTED · full `verify --tier check` not run this pass, only `--tier fast`)
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

- Simulator overhaul Phases 0–3 and the mandatory next-session learning plan were completed 2026-07-22. See `docs/SIMULATOR_OVERHAUL_PLAN.md` and `logs/last_verify.json` for scope and gate evidence.

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
