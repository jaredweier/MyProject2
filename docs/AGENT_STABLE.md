# Agent stable rules (reference only — never inline in prompts)

## Read order
1. `logs/agent_pack/latest.md` — dynamic (slice, route, outlines, git, gate)
2. This file — stable policy
3. `docs/AGENTS_REFERENCE.md` · `docs/HANDOFF.md` · one `.grok/skills/*/SKILL.md` — @ on demand

## Sufficiency
Stop gathering when confident to answer. No extra reads/tools unless info is contradictory or clearly incomplete.

## Blocked
`FULL_PROJECT_CODE.txt` · full `HANDOFF.md` · `.grok/skills/` tree · `tests/ui_snapshots/baseline/` · `logs/` · `.grok/sessions/` · whole-repo reads

## Verify (terminal, no subagents)
`cheap-check` → `preflight` → `verify-slice <id>` → `check` (handoff) · fail: `fix-hint`

## Before full file read
`python dev.py outline <file>` · `python dev.py symbol <name> [--slice id]`

## Routing tiers → Cursor
| tier | mode |
|------|------|
| trivial | Tab |
| low | Ask |
| medium | Agent |
| high | Plan→Agent |
| vision | Agent+1PNG |
| verify | terminal |

`python dev.py route-task "<task>"` for pick · edit `touch_together` only

## Edit boundaries
- Business rules → `validators.py` then `logic/*` — never SQL in UI, never duplicate logic in `cli.py`
- UI → `ui/*_pages.py`; refresh after mutations (`ui/helpers.py`)
- Slice `touch_together` only; registry: `slices/registry.py`
- Import: `import logic` (package re-exports)

## Conventions
`validators.is_officer_active()` · `validators.parse_date()` · `logic.get_shift_number()` · `PRAGMA foreign_keys=ON` · no SQL in UI · no rules in `cli.py`

## Payroll (stable facts)

| Topic | Rule |
|-------|------|
| Pay period | 14 days from `PAY_PERIOD_BASE_DATE` (6 Jul 2026); hours attach to shift-start period |
| Titles | Built-in: Officer, Sergeant, Investigator, Lieutenant, Chief · custom via `add_custom_officer_title` |
| Title pay | Monthly default; **Chief, Lieutenant** → yearly (`YEARLY_SALARY_TITLES`) · custom titles hourly/manual |
| Hourly base | `monthly × 12 ÷ hrs/yr` or `yearly ÷ hrs/yr` → officer `pay_rate` · defaults: 2008 (patrol ranks), **2080** (Chief/Lt) · editable per title on Position Pay Rates |
| Per-period salary | `annual ÷ count_pay_periods_in_year()` |
| FLSA §207(k) | Manual work-period **days** + anchor date — **not** pay period, **not** rotation cycle (`logic/labor_compliance.py`) |
| Banks | Timecard-driven earned/used; tab `banked_time` in payroll hub |

## Scheduling (stable facts)

Rotation/bump/day-off: `logic/scheduling.py`, `validators.py`. Night minimum Fri/Sat only. Known fixes: `.grok/rules/known-issues.md`

## Env
`SCHEDULER_SLICE` · `SCHEDULER_AGENT_TASK` · `SCHEDULER_SKIP_AGENT_GATES=1` · `SCHEDULER_SKIP_STARTUP_GATES=1`

## Context window
**Always keep:** system prompt · current task · latest tool results · explicit decisions
**Ephemeral:** mark tool output ephemeral by default; pruned after 2 turns unless `keep` or `referenced`
**Summarize @ 6000 tokens:** replace raw history with `logs/context_window/latest_summary.md`

```bash
python dev.py context-window task "…"      # set task (kept)
python dev.py context-window decision "…"   # record conclusion (kept)
python dev.py context-window tool <id> --tokens N --keep   # keep result
python dev.py context-window status
```

Cursor `stop` hook advances turn + prunes. File reads auto-register as ephemeral via read_guard.

## Batch (independent items only)
One JSON **array** output — `results[i]` matches `items[i]`. Parallel, no LLM.

```bash
python dev.py batch-process classification --items '["fix bump","ui tab"]'
python dev.py batch-process validation --input batch.json -o results.json
```

Tasks: `classification` · `extraction` · `summarization` · `scoring` · `validation`

## Structured output (default)
CLI tools emit **compact JSON** with fixed fields only — no prose. Schemas: `scripts/structured_output.py`

```bash
python dev.py route-task --json "fix bump"
python dev.py context-window status --json
python dev.py batch-process scoring --input items.json   # flat fields per index
```

`--full` on batch-process restores nested `result` blob.

## Expensive (user request only)
`ui-observe --live` · full `ui-diff` · `verify-features` · `ui-exhaustive`
