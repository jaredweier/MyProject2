# Dodgeville PD — Agent Rules

**Bootstrap (free):** `python dev.py agent-kit` → `@logs/agent_kit/latest.md`
**Dynamic:** `@logs/agent_pack/latest.md` · **Stable:** `@docs/AGENT_STABLE.md` · **Hub:** `@docs/AGENT_TOOLKIT.md`

Auto-context OFF. One skill: `.grok/skills/*/SKILL.md` (prefer `token-discipline` at start)

## Minimize (mandatory)
`usage-brief` → `read-budget` → `outline`/`symbol` → edit → `verify --tier fast` · ship: **`check`** · `token-improve` if index/prompts change

## Edit boundaries
`validators` + `logic/*` · `ui/*_pages` · slice `touch_together` · `import logic`
Domain: `AGENT_STABLE` · UI: `.grok/rules/ui-modern.md` · Math: `.grok/rules/scheduling-math.md`

## gstack (optional)
Process skills from [gstack](https://github.com/garrytan/gstack) — install notes in `CLAUDE.md`.
Global: `~/.claude/skills/gstack` · `/office-hours` `/review` `/qa` `/ship` `/browse` `/investigate`
**Does not replace** free Dodgeville gates (`dev.py verify`, token-discipline, slice `touch_together`).
Domain work stays on `.grok/skills/*` + `logic/*` / `validators`.

## stop-slop (optional prose)
Remove AI writing tells from user-facing copy / docs: `.grok/skills/stop-slop/SKILL.md`
(also `.claude/skills/stop-slop/`). Load when drafting or reviewing prose — not for code/logic.

## graphify (optional map)
Code knowledge graph: `graphify-out/` · skills `.claude/skills/graphify/` + `.grok/skills/graphify/` · CLI `graphify`
Prefer `graphify query "…"` / `path` / `explain` when `graphify-out/graph.json` exists.
Rebuild after code changes: `graphify extract . --code-only` (local AST, no API key).
Ship gate remains `python dev.py verify` — graphify does not replace it.
