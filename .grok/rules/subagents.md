# Subagent Roles

**Auto-context OFF.** Any agent/LLM may handle any task — routing is advisory.

`@logs/agent_pack/latest.md` · `@docs/AGENT_STABLE.md` · **Sufficiency:** stop when confident; no extra reads unless contradictory or incomplete.

`python dev.py route-task "<task>"` · skills: `docs/AGENTS_REFERENCE.md`

| Role | Skill | Best for |
|------|-------|----------|
| Routing | agent-routing | pick agent/model |
| Scheduling | scheduling-logic | bump, rotation |
| UI | ui-development | tabs, widgets |
| UI polish | ui-aesthetics-review | copy, theme |
| UI vision | ui-vision-review | screenshots |
| CLI & Ops | cli-operations | cli.py, dev.py |
| Security | security | auth |
| QA | qa-verify | gates, audit |
| Payroll | payroll-timecard | pay periods |
| Build | build-deploy | .exe |
| Refactor | refactor | splits |

Verify: `docs/AGENT_STABLE.md` § Verify
