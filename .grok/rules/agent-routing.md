# Agent routing (Grok)

`python dev.py route-task "<task>"` · auto **cost_tier** + UI agent chain

Auto-context OFF · cheapest fit model · any LLM allowed
Skill: `.grok/skills/agent-routing/SKILL.md`
Catalog: `@docs/UI_AGENTS_CATALOG.md` · policy `@docs/AGENT_ROUTING.md`

**Sufficiency:** stop gathering when confident; no extra reads unless contradictory or incomplete.
Policy hub: `docs/AGENT_STABLE.md` · pack: `logs/agent_pack/latest.md` · trust: `docs/TRUST_REPAIR_CHECKLIST.md`

**UI design XOR:** visual UI tasks load **frontend-design** *or* **taste-skill** (one only). Never both unless the user says so. Defaults in `AGENTS.md` § UI design skills.
