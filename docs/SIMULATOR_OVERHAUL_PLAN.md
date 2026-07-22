# SIMULATOR OVERHAUL — EVALUATION + ROADMAP (authoritative)

**Written:** 2026-07-22, after a live in-browser evaluation + code audit + market scan.
**Audience:** future agents. Read this WHOLE file before touching any simulator file.
**Status of findings:** every finding in §2 was PROVEN live on 2026-07-22 (repro steps included).
Do not re-litigate them; do not "re-discover" them; pick up the roadmap in §4 where the
checkboxes left off.

**Binding context you must also read first:**
- `AGENTS.md`, `CLAUDE.md` (rules: caveman output, proof-before-"fixed", process hygiene)
- `docs/HANDOFF.md` § NEXT SESSION
- `logs/NEXT_SESSION_BRIEF.md` (how the CP-SAT core landed and was verified)

---

## 1. Architecture map (what each file is, sizes as of 2026-07-22)

### Engines (logic layer — no UI imports allowed here)

| File | Lines | Role |
|------|-------|------|
| `simulator.py` | 1696 | The **evaluator**. `SimulatorConfig` (input dataclass) → `simulate_schedule()` → `SimulatorResult`. Minute-level coverage check via `logic/coverage_timeline.py` sweep-line. Has `officer_home_starts` field (per-officer fixed starts — NEVER drop it when replaying a result; see brief). |
| `logic/staffing_optimizer.py` | 2701 | The **OLD brute-force search**. `optimize_staffing_scenarios()` enumerates 5 axes: shift_length × start_packs × min_per_shift × rotation/variations × phase_and_pattern_assignment via `itertools`, with hand-rolled pruning (`_cheap_reject`, `_cheap_window_minute_fail`). `estimate_search_space()` lives here. This engine caused the documented false-impossible bug class. |
| `logic/staffing_cpsat.py` | 420 | The **NEW CP-SAT solver** (OR-Tools). `solve_phase_variant()` = sound relaxation (its `infeasible` is a real proof). `solve_full_assignment()` = minute-level 24/7 + weekday windows + annual band + per-officer starts (only its `feasible` is used; `infeasible`/`unsupported` falls through). Currently only an **additive fast-path** inside `optimize_staffing_scenarios` — heuristic first, CP-SAT on failure, exhaustive as final fallback. Order matters: heuristic-first was a deliberate latency fix (13s→33s regression when CP-SAT ran unconditionally — do not reorder). |
| `logic/scheduling_sim.py` | 536 | Thin wrappers the UI calls: `run_schedule_simulation()`, `run_staffing_optimizer()`. **Hazard:** explicit kwarg list + `**_compat` catch-all — a kwarg missing from the explicit list is SILENTLY swallowed (this already bit us twice: `min_rest_hours`, `max_consecutive_work_days`). When adding any new option, add it to the explicit signature AND forward it. |
| `logic/optimizer_features.py` | 1715 | ~60 bolt-on features: `suggest_relaxations`, `estimate`-adjacent helpers, pins, scenario slots, heatmaps (`shift_coverage_heatmap`, `coverage_heat_grid`), fairness, what-if, `find_min_officers_hard`, CSV/PNG/EML exports, form snapshots, search history. |
| `logic/coverage_timeline.py` | 217 | The ground-truth minute-level sweep-line coverage checker. CP-SAT results were verified against THIS, not against themselves. Any new solver output must also be verified against this. |

### UI layer (`gui/pages/simulator/`)

| File | Lines | Role |
|------|-------|------|
| `page.py` | 3379 | Still ONE closure (`render_simulator → body`) sharing ~35 widget variables. Contains: form I/O (`_form_payload`/`_apply_form_payload_inner`), search execution (`run_sim`, `_run_opt`, `_execute_opt`, `_apply_opt_result`), dialogs (`_show_no_match_dialog`, `_show_constraint_suggestions`), lock handlers (`_on_lock_with_suggest`, `_focus_suggest`), `_apply_ranked_option` (forwards `officer_home_starts` — do not break). |
| `actions.py` | 387 | 19 extracted button handlers. Uses a **callbacks-dict looked up at call time** — because `set_summary` is REDEFINED mid-`body()`; capturing it as a plain parameter silently keeps the stale version. Read its module docstring before extracting anything else. |
| `options_panel.py` | 551 | Requirements-form field panels incl. multi-line Patterns textarea (one rotation set per line; overrides the preset dropdown entirely once non-empty). |
| `results_panel.py` / `decision_table.py` / `publish_panel.py` / `manual_editor.py` | 168/151/106/303 | Ranked options render, decision table, publish step, manual grid builder. |
| `state.py`, `helpers.py`, `stepper_rail.py`, `styles.py` | small | Shared state dict, misc. |

### Split boundary (user-approved, do not blow past casually)
Stage-1 split stopped deliberately. The remaining `page.py` core is one interlocked unit.
Stage-2 is only justified **as part of the solver-first rewrite** (§4 Phase 1/2), not as a
standalone refactor.

---

## 2. PROVEN findings (2026-07-22 live session) — the "why" behind the roadmap

Repro base: `python main.py --web` (ONE process on :8080), login admin/admin, go to `/simulator`.
App used here via the browser tool; JS click-by-text is more reliable than ref-clicks (see §6).

**F1 — Default Find Best is a dead end.**
Fresh form → Find Best → dialog: "290,100,000 layouts … ~4,673.8–11,684.6 hours", options only
"Run Full Search Anyway" / "Cancel". A supervisor's first click hits a wall.

**F2 — The guided path dead-ends the same way.**
"Will N officers work?" → N=8 → Search → identical 290M dialog. The product's #1 question is
unanswerable via its own guided flow.

**F3 — The search-space estimate is dishonest (worst single bug).**
With officers=8 LOCKED, length=8h LOCKED, patterns `6-2,5-3 | 6-3,5-2` GIVEN, annual 2008±20,
24/7≥1: dialog says "1,934,000 layouts … ~31.2–77.9 hours". Reality: `solve_full_assignment`
solved that scenario **feasible in 21 seconds** (headless, same machine, command in §5).
Cause: `estimate_search_space()` counts raw enumeration; it knows nothing about the CP-SAT
fast path or the cheap-reject pruning. Bonus bug: the dialog text suggests "lock officer
count" even when officer count is already locked.

**F4 — Popup trap (the user's "weird popups" complaint, reproduced).**
Clicking a field's lock/Given control queues a "Suggestions" dialog via
`_on_lock_with_suggest` / `_focus_suggest` (`page.py`). Locking two fields then clicking Run
produced TWO stacked identical dialogs that appeared AFTER "Run Full Search Anyway".
"Enter My Own Value" re-focuses the field → re-triggers the suggestion dialog → loop.
Escape did not close it. User is trapped.

**F5 — A running exhaustive search takes the app down.**
"Run Full Search Anyway" on the 1.9M-layout space: server burned 486s CPU, page navigation
hung (300s timeout), dialogs froze, Cancel unreachable. Only recovery was killing the
process. Progress/cancel plumbing EXISTS in code (`_progress`, `cancel_check`,
`_full_sim_worker` multiprocessing) but was unreachable in the real flow. Root cause not yet
attributed — do NOT claim it fixed until a live search stays cancellable and the rest of the
app stays clickable during it.

**Market scan conclusion (for prioritization):** commercial police tools (InTime,
PowerTime/PlanIt, Aladtec) win on cert enforcement, OT **cost** management, court/subpoena
integration. Chronos already beats them on rotation math (multi-block, FLSA §207(k), annual
bands). The modern optimization standard (Timefold, OR-Tools) is ONE solver model with soft
constraints + **anytime search** (best answer in seconds, improves if you wait) — that is
the cure for F1/F2/F3/F5.

---

## 3. Non-negotiable guardrails (things past sessions broke or nearly broke)

1. **Never claim "fixed" without the live user scenario.** Unit tests ≠ Chronos working.
   For simulator work the user scenario is: open `/simulator`, real click path, real result.
2. **Heuristic-first ordering** in `optimize_staffing_scenarios` (cheap built-in stagger →
   CP-SAT only on failure → exhaustive fallback). Reordering re-introduces a 2.5× test-suite
   latency regression.
3. **`officer_home_starts` must survive replay.** `_apply_ranked_option` forwards it and sets
   `nearby_start_hops=0`. Dropping it silently reintroduces window failures CP-SAT proved away.
4. **`run_staffing_optimizer` kwarg trap** (`logic/scheduling_sim.py`): `**_compat` swallows
   anything not in the explicit signature. Every new UI option must be added explicitly.
5. **CP-SAT soundness rules:** `solve_phase_variant.infeasible` = real proof.
   `solve_full_assignment.infeasible`/`unsupported` = NOT a proof (stricter-than-real model);
   only its `feasible` may be used. Specific-date windows are `unsupported` by design
   (one-off ≠ periodic; a truncated horizon would make "infeasible" unsound).
6. **Verify any new solver output against `logic/coverage_timeline.py`'s sweep**, not against
   the solver's own constraint model. (First CP-SAT cut passed its own check and failed the
   real sweep with 22 failures.)
7. **Process hygiene:** one server on :8080; kill everything you start; check
   `Get-CimInstance Win32_Process -Filter "Name='python.exe'"` before and after.
8. **28-day hard eval** for multi-block truth; never ship 14-day hard as truth.
9. Reference scenario for all testing: 8h shifts · 2008±20 annual · `6-2,5-3 | 6-3,5-2` ·
   24/7 min 1 · Fri+Sat 19:00–03:00 min 2 · 7 officers thin → hard pack usually needs 8.
   Unit: `test_real_world_eight_hour_multiblock_annual_and_nights`.
10. Ship gate: `python dev.py verify --tier check` + `honest_gate: true` in
    `logs/last_verify.json`. Day-to-day: one focused test + live click.

---

## 4. ROADMAP (work top to bottom; update checkboxes + add date/commit when done)

### Phase 0 — stop the bleeding (small, independent fixes; do these first)

- [x] **P0.1 Popup discipline** (done 2026-07-22, proof: live — locked 2 fields, zero popups
  appeared (was 2 stacked); explicit "Suggest values" button in Requirements footer opens ONE
  dialog; closed via button and backdrop with no re-open loop.)
  - Implemented: removed all lock-toggle and focus-triggered `_show_constraint_suggestions`
    calls; single-dialog guard via `state["suggest_dialog"]`; explicit button wired to
    `_suggest_next_unlocked`.
  - **RESIDUAL (open):** Escape does NOT close these dialogs — verified it's not the popup
    loop (synthetic keydown on the dialog also fails). Looks like a NiceGUI/Quasar focus
    quirk affecting the app's dialogs generally. Backdrop + button close work. Worth a
    small dedicated fix later; do not confuse it with the (fixed) re-open trap.
- [x] **P0.2 Honest estimate** (done 2026-07-22, proof: live — same 1.9M-layout form that
  said "31–78 hours" now shows "Solver fast path applies: ~7 solver probe(s), expected
  ~1–2 minutes"; headless checks on 3 shapes incl. non-eligible fallback. Lock-hint now
  lists only actually-free dims incl. officer count.)
  - Implemented in `estimate_search_space`: `cpsat_eligible` mirror of `_cpsat_usable` +
    weekday-window check (KEEP IN SYNC with `optimize_staffing_scenarios`), `smart_units`,
    smart time range (1.5–25s/probe, measured), risk follows smart plan when eligible.
    Confirm dialog: "Search Plan" + "Run Smart Search (Recommended)" when eligible.
- [x] **P0.3 Time-box every search** (done 2026-07-22, proof: live — Find Best on the
  1.9M space stopped at exactly 120s, returned 2 ranked hard-OK options with "Time Budget
  Reached (120s)" summary; headless — 20s budget on huge space returns
  budget_exhausted=True, impossible=False.)
  - Implemented: `time_budget_seconds` in `optimize_staffing_scenarios` (budget trips the
    cancel rails, distinct `budget_exhausted` flag + message), threaded EXPLICITLY through
    `run_staffing_optimizer` (the `**_compat` trap), UI sends 120s standard / 300s deep.
    Soundness: a budget/cancel stop can never set `impossible` (engine) and never shows
    the no-match/impossible dialog (UI shows honest "not proof of impossibility" summary).
  - Not done: a true "Keep searching" resume button (engine has no resume state) — re-run
    with Deep for a longer budget. Revisit in Phase 1 (solver owns anytime search there).
- [x] **P0.4 App stays alive during a search** (done 2026-07-22 — root cause ATTRIBUTED,
  fixed, and re-proven live)
  - **Root cause (measured):** the search is pure-Python CPU work; on a thread it holds
    the GIL and starves NiceGUI's event loop — a plain page load took **84 seconds**
    during a thread-run search vs **7ms** right after cancel. That was the F5 freeze.
  - **Fix:** `run_staffing_optimizer_isolated` in `logic/scheduling_sim.py` — persistent
    single-worker spawn ProcessPoolExecutor + Manager queue/event; progress puts throttled
    to 0.4s and cancel polls to 0.25s in the child (unthrottled proxy roundtrips would
    dominate runtime); automatic in-process fallback if the pool breaks. `_execute_opt`
    now uses it; nothing else in `gui/` may call `run_staffing_optimizer` directly.
  - **Proof:** live — page loads 6–23ms WHILE the child process burned CPU on a 26.7M-layout
    search; progress % relayed to the UI over IPC; 120s budget stop returned through the
    pool with the honest "No Qualifying Option Found Yet" (not "impossible") summary.
    Cancel mid-run: server CPU 5.0s/5s → 0.00s/5s. Headless: cancel honored across the
    process boundary (latency bounded by one solver probe, ~10s worst case).
  - Note: process spawn adds ~5–8s to the FIRST search after server start (pool reused after).

### Phase 1 — solver-first core (the real fix; F1/F2/F3 die here)

- [ ] **P1.1 Objective function in CP-SAT** (`logic/staffing_cpsat.py`)
  - Extend `solve_full_assignment` from feasibility-only to optimization: weighted objective
    from the existing priority sliders (`_weights_from_priority` semantics) — coverage,
    fairness/annual-band tightness, headcount. Soft constraints with penalties where the UI
    marks a requirement non-hard.
- [ ] **P1.2 Solution pool → ranked options** — surface multiple diverse solutions from the
  solver (solution callback / repeated solves with exclusion cuts) so ranked options come
  from CP-SAT directly; keep `diversify_ranked` semantics. Exhaustive enumeration becomes
  fallback ONLY for shapes CP-SAT reports `unsupported` (e.g. specific-date windows).
- [ ] **P1.3 Specific-date windows in CP-SAT** — model the dated window over the concrete
  simulation horizon (it's an optimization over a fixed date range at that point, so
  soundness of "infeasible" is definable; document the semantics).
- [ ] **P1.4 Min-N + What-if on the solver** — binary search on N over `solve_phase_variant`
  (its infeasible is a proof → sound lower bound) + `solve_full_assignment` for the witness.
  Replaces the slow path in `find_min_officers_hard`. Same engine powers "What does +1 buy me"
  and Compare 8/10/12h.
- [ ] **P1.5 Live progress** — OR-Tools solution callback → `_progress` → UI best-so-far.
- **Proof for all of Phase 1:** every produced schedule re-verified through
  `logic/coverage_timeline.py`; reference scenario end-to-end in-browser: Find Best answers
  in seconds with ranked options; "Will 8 officers work?" answers in seconds; 28-day hard eval;
  28/28 `tests.test_simulator_constraints` + new solver tests; then `verify --tier check`.

### Phase 2 — UX rebuild

- [ ] **P2.1 Question-first Requirements** — the three quick-start questions become the real
  primary flow (they currently just open thin dialogs that fall into the same wall).
  Full ~4,300px form becomes "Advanced". Suggestions inline under fields, not modal.
- [ ] **P2.2 Results = decision surface** — per-option **$ OT cost estimate** (hours over
  target × configurable OT rate; the gap vs every commercial competitor), inline coverage
  heatmap (`shift_coverage_heatmap` exists), plain-language verdict lines (`why_best_lines`
  exists). Read `DESIGN.md` before any visual work; stop-slop for copy.
- [ ] **P2.3 page.py stage-2 split** — do it WITH the P1 rewrite of `run_sim`/
  `_apply_opt_result`/dialogs, using the `actions.py` callbacks-dict pattern. Re-read the
  two hazards in `logs/NEXT_SESSION_BRIEF.md` §6 first.

### Phase 3 — market parity (prioritize with the user, not unilaterally)

- [ ] Cert-aware staffing (UI gate exists, honestly disabled — wire real cert data from roster)
- [ ] Court/training board deep integration (a "Load From Operations" window template exists)
- [ ] Budget/OT cost reporting across options and published months
- [ ] Shift-bidding link-up (Create Bid Draft button exists on publish step)

---

## 5. Proof commands (copy-paste)

```bash
# From C:\Users\Windows\Desktop\Chronos Claude
python -m unittest tests.test_simulator_constraints tests.test_feature_ui_static -v   # 28/28, ~13s
python dev.py verify --tier fast
python dev.py verify --tier check   # ship gate; then read logs/last_verify.json honest_gate

# CP-SAT reference scenario (should print "feasible" in ~20s; this is the F3 evidence)
python -c "
from datetime import date
from logic.rotation_patterns import build_pattern
from logic.staffing_cpsat import solve_full_assignment
patterns = [build_pattern('6-2,5-3', style='rotating'), build_pattern('6-3,5-2', style='rotating')]
r = solve_full_assignment(patterns, n_officers=8, shift_length_hours=8.0,
    candidate_starts=['06:00','14:00','19:00','22:00'], sim_start_date=date(2026,7,20),
    coverage_247=1, annual_hours_target=2008.0, annual_hours_variance=20.0, annual_hours_hard=True,
    extra_windows=[{'weekday':4,'start_time':'19:00','end_time':'03:00','min_officers':2},
                   {'weekday':5,'start_time':'19:00','end_time':'03:00','min_officers':2}])
print(r['status'])
"
```

Live app: `python main.py --web` (NOT plain `python main.py` — that spawns a native window
fighting the browser client on one socket). ONE process on :8080. Kill it when done.

---

## 6. Browser-tool survival notes (saves you an hour)

- Ref-based clicks (`computer` + `ref`) go stale after any scroll/re-render. Reliable
  pattern: `javascript_tool` with `[...document.querySelectorAll('button')].find(b =>
  b.textContent.includes('...')).click()`.
- Each `javascript_exec` shares one scope per page — `const b=` twice errors. Wrap in `{}`
  blocks or use unique names.
- NiceGUI dialogs render in a Quasar portal OUTSIDE `<main>`: `get_page_text` won't see
  them; query `document.querySelectorAll('.q-dialog')`. `offsetParent` is null for them
  (position:fixed) — it is NOT a visibility signal.
- Button text from `read_page`/JS includes Material icon ligatures (e.g.
  `travel_exploreFind best`) — match with `includes`, not `===`.
- The Command Queue drawer overlays content on load — click its "Hide" first.
- A hung `navigate` (300s timeout) after starting a search = F5, not your tooling.

---

## 7. Keeping this file honest

- When you complete a roadmap item: check the box, append `(done YYYY-MM-DD, commit <sha>,
  proof: <one line>)`. If you consciously skip or reverse a decision, say so here with why.
- If you re-test a §2 finding and it's fixed, mark it `FIXED YYYY-MM-DD` in place — do not
  delete the finding (it's the rationale for the design).
- Update `docs/HANDOFF.md` § NEXT SESSION pointer if this file moves.
