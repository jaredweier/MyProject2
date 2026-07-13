# Dodgeville PD — Agent Rules

Auto-context off. Skills on demand. Primary UI: `gui/` Chronos.
**Bootstrap:** `python dev.py session-start` → `@logs/agent_kit/latest.md` · `@logs/agent_pack/latest.md`
**Stable:** `@docs/AGENT_STABLE.md`

## Caveman
Short bullets. No preamble. Prose only if user asks explain/docs.

## Route once
`python dev.py route-task "<task>"` → obey **cost_tier**. Load **one** skill if printed.

## Minimize
`usage-brief` → `outline`/`symbol` → edit **touch_together** → `verify --tier fast`
Ship: `verify --tier check` + `logs/last_verify.json` → `honest_gate: true`

## Edit
Rules in `validators` + `logic/*` only. No SQL in `gui/`. Dual-rate Logic vs Chronos.
Optional (user ask): graphify · vision · domain research · `_archive` skills
