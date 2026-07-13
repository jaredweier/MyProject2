# Vertical Slice Strategy — Dodgeville PD Scheduler

**Purpose:** Organize brownfield and future work by **user-facing capability** (end-to-end slices), not by technical layer alone.

**Registry:** `slices/registry.py` — single source of truth
**Commands:** `python dev.py slice-map` · `python dev.py slice-check`

---

## Research summary (brownfield / completed projects)

Industry guidance (Vertical Slice Architecture, legacy Python monoliths) converges on:

| Principle | Application here |
|-----------|------------------|
| **Slice by feature, not layer** | Each slice = UI + logic + CLI + tests for one capability |
| **Incremental strangler** | Do not big-bang rewrite `logic.py`; migrate one slice at a time |
| **What changes together belongs together** | `touch_together` in registry lists files agents must co-edit |
| **Shared kernel stays thin** | `config`, `validators`, `database`, `permissions`, app shell — not duplicated per slice |
| **Verify per slice** | Each slice lists `verify` commands (`smoke`, `scenarios`, `ui-smoke`) |
| **Integration tests at boundaries** | Keep `dev.py check`, `audit`, and cross-slice scenarios |

---

## Current project evaluation

| Area | State | Slice readiness |
|------|--------|-----------------|
| **UI** | 9 page mixins, thin `ui/app.py` (~650 lines) | **Strong** — already feature-aligned |
| **Logic** | `logic/` package (9 slice modules + shim) | **Strong** — domain split complete; `import logic` stable |
| **CLI** | Thin wrapper over `logic.*` | **Strong** |
| **Tests** | 190 tests, per-domain files | **Good** — map to slices in registry |
| **Tooling** | `feature-map`, `refactor-check`, `scenarios`, UI smoke | **Ready** — extended with `slice-map` / `slice-check` |

**Verdict:** UI, logic package, CLI, and registry are slice-aligned. New work: add slice entry first; edit `touch_together` files only.

---

## What belongs in each slice (optimized)

Keep slices **small and actionable** for agents and humans:

| Field | Include | Omit |
|-------|---------|------|
| `id`, `name`, `summary` | Always — how to find and describe the slice | Long prose, history |
| `status` | `complete` / `partial` / `planned` | — |
| `ui_pages`, `ui_mixin` | Nav keys and primary UI file | Every widget name |
| `logic`, `logic_extra` | Public symbols callers use | Private helpers |
| `validators` | Only slice-specific pre-checks | All of `validators.py` |
| `cli` | Representative commands | Every flag variant |
| `permissions` | Gates for this feature | Full role matrix |
| `tables` | SQLite tables this slice owns | Entire schema |
| `tests` | Test **files** covering the slice | Every test method |
| `scenarios` | `S-XX` ids from `SCHEDULING_RULES.md` | — |
| `verify` | `dev.py` commands to run after changes | — |
| `touch_together` | Files to edit in one PR/session | Unrelated modules |
| `future_module` | Target under `logic/` when split | — |

**Shared kernel** (`slices/registry.py` → `SHARED_KERNEL`): cross-cutting infrastructure only.

---

## Strategy: previous work

Slices were registered as **`status: complete`**, but as of 2026-07-09 many UI paths are **stale** (deleted `ui/*_pages.py`). Treat status as **untrusted** until `docs/TRUST_REPAIR_CHECKLIST.md` P0 passes and `python dev.py slice-check` is clean. Prefer dual status: logic vs Chronos UI.

1. **Agents** — When fixing or extending a feature, read the slice entry first; edit only `touch_together` files (+ shared kernel if truly cross-cutting).
2. **Humans** — Use `slice-map` to see coverage; use `slice-check` before merge.
3. **Regression** — Slice `verify` commands are subsets of `dev.py check` + UI smoke.

---

## Strategy: future work

### Rule 1 — New features

1. Add a slice to `slices/registry.py` (`status: planned` → `complete` when done).
2. Implement validators → logic → UI/CLI in one vertical pass.
3. Add tests under the slice’s `tests` list.
4. Run slice `verify` + `python dev.py check`.

### Rule 2 — Logic package migration (when touching a slice)

Order from `.grok/skills/refactor/SKILL.md`, **one slice at a time**:

1. Extract slice functions to `logic/<module>.py`.
2. Re-export from `logic/__init__.py` so `import logic` unchanged.
3. Run `logic-imports`, `slice-check`, `check`.
4. Update slice `touch_together` to include new module path.

Suggested order (highest churn / clearest boundaries first):

1. `day-off-requests` + `shift-swaps` → `logic/requests.py`
2. `roster` → `logic/officers.py`
3. `schedules` → `logic/snapshots.py`
4. `payroll-timecard` → `logic/payroll/` (package)
5. `user-accounts` → `logic/users.py`
6. `reports-analytics` + `exports-ical` → `logic/exports.py`
7. `availability` + `open-shifts` + `simulator` + `database-backup` → `logic/operations.py`
8. `dashboard` analytics glue → `logic/dashboard.py` or keep in `analytics.py`

### Rule 3 — UI

Mixins already match slices. Further splits only when a mixin exceeds ~1,000 lines **and** contains multiple slice IDs (e.g. split `feature_pages.py` into reports vs availability).

---

## Verification gate

After any slice or registry change:

```bash
python dev.py slice-check
python dev.py check
python dev.py smoke
python dev.py ui-smoke
```

For UI-heavy slices: `python dev.py ui-functional`

---

## Anti-patterns

- Editing `logic.py` without identifying the slice
- Duplicating validation in UI or CLI
- Adding features without a registry entry
- Splitting shared validators into slice folders (keep `validators.py` central)
- Microservices or separate repos — out of scope for this desktop app
