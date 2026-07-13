# Subagent Roles

**Auto-context OFF.** Any agent/LLM may handle any task — routing is advisory.

`@logs/agent_pack/latest.md` · `@docs/AGENT_STABLE.md` · **Sufficiency:** stop when confident; no extra reads unless contradictory or incomplete.

`python dev.py route-task "<task>"` · skills: `docs/AGENTS_REFERENCE.md`

| Role | Skill / OpenCode | Cost | Best for |
|------|------------------|------|----------|
| Tokens | token-discipline | free/cheap | session start, minimize spend |
| Routing | agent-routing + `route-task` | free | pick agent/model/cost tier |
| Scheduling | scheduling-logic | balanced+ | bump, rotation |
| UI Chronos | ui-development / **ui-chronos** | balanced | NiceGUI `gui/*` |
| UI polish | ui-aesthetics / **ui-static-reviewer** | cheap | copy, theme (no PNG) |
| UI vision | ui-vision-review / **ui-vision-reviewer** | vision | screenshots after static gates |
| UI browser | UI_AGENTS_CATALOG | vision | Playwright → browser-use → Skyvern |
| CLI & Ops | cli-operations | cheap | cli.py, dev.py |
| Security | security | balanced | auth |
| QA | qa-verify / **qa-free** | free | gates, audit |
| Payroll | payroll-timecard | balanced | pay periods |
| Build | build-deploy | balanced | .exe |
| Refactor | refactor | flagship | splits |

**Escalate cost only when the lower tier fails.** Never vision for typo/copy.

Verify: `docs/AGENT_STABLE.md` § Verify
