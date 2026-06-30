---
name: agent-routing
description: >
  Route Dodgeville PD tasks to the right AI agent, subagent, and model tier by
  complexity and domain. Auto-context is OFF — load skills on demand. Any agent
  or LLM may be used for any task; routing is advisory.
---

# Agent Routing

## Policy

1. **Auto-context OFF** — do not preload HANDOFF, all skills, or full docs unless user @-mentions them or runs `python dev.py route-task`.
2. **Any agent/LLM allowed** for any task — pick by fit, not restriction.
3. **Route first** — `python dev.py route-task "<task>"` → complexity, skill, Cursor mode, model tier.

## Complexity tiers

| Tier | When | Cursor | Model tier | Subagents |
|------|------|--------|------------|-----------|
| trivial | typo, format, import | Tab | fast / none | none |
| low | explain, locate symbol | Ask | Auto / mini | optional |
| medium | one slice bug/feature | Agent | Sonnet / Grok | domain skill |
| high | arch, multi-slice, rust | Plan → Agent | Opus / reasoning | 2+ skills |
| vision | UI wrong visually | Agent + images | vision model | ui-vision + ui-dev |
| verify | tests/audit pass? | terminal or Agent | any | qa-free optional |

## Domain → skill

| Domain | Skill |
|--------|-------|
| bump, rotation, day-off | `scheduling-logic` |
| payroll, timecard | `payroll-timecard` |
| auth, permissions | `security` |
| UI tabs/widgets | `ui-development` |
| look/feel, PNGs | `ui-vision-review` |
| cli, dev.py | `cli-operations` |
| build, .exe | `build-deploy` |
| refactor, split | `refactor` |
| unsure | `dodgeville-scheduler` |

## Context

`logs/agent_pack/latest.md` (dynamic) · `docs/AGENT_STABLE.md` (policy) · `python dev.py route-task "<task>"`

Detail: `docs/AGENT_ROUTING.md`
