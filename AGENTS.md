# Dodgeville PD — Agent Rules

**Dynamic:** `@logs/agent_pack/latest.md` · **Stable:** `@docs/AGENT_STABLE.md`

Auto-context OFF. Load on demand: one `.grok/skills/*/SKILL.md` · `@docs/AGENTS_REFERENCE.md` · `@docs/HANDOFF.md`

State: `logs/last_agent_gate.json` · `logs/last_gate.json`

## Sufficiency
Stop reads/tools when confident. `python dev.py outline <file>` / `symbol <name>` before full reads.

## Verify
`cheap-check` → `preflight` → `verify-slice <id>` → `check`. Route: `route-task` (advisory).

## Edit boundaries
`validators.py` + `logic/*` · `ui/*_pages.py` · slice `touch_together` · `import logic`

Domain facts (payroll, scheduling): `docs/AGENT_STABLE.md`. Known fixes: `.grok/rules/known-issues.md`
