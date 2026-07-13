# Agent reference (load on demand — not auto-context)

Full tables moved from `AGENTS.md` to reduce per-turn tokens. @-mention this file only when needed.

## Subagents & skills

| Role | Skill | Focus |
|------|-------|-------|
| **Routing** | `.grok/skills/agent-routing/SKILL.md` | complexity → cost tier → multi UI agents (`docs/UI_AGENTS_CATALOG.md`) |
| Scheduling | `.grok/skills/scheduling-logic/SKILL.md` | validators, bumping, rotation |
| UI | `.grok/skills/ui-development/SKILL.md` | CustomTkinter tabs, permissions |
| UI polish | `.grok/skills/ui-aesthetics-review/SKILL.md` | Spelling, wording, theme |
| UI vision | `.grok/skills/ui-vision-review/SKILL.md` | PNGs + layout |
| CLI & Ops | `.grok/skills/cli-operations/SKILL.md` | cli.py, dev.py, scripts |
| Security | `.grok/skills/security/SKILL.md` | auth, permissions |
| QA | `.grok/skills/qa-verify/SKILL.md` | preflight, check, audit |
| Payroll | `.grok/skills/payroll-timecard/SKILL.md` | pay periods, timecard |
| Build | `.grok/skills/build-deploy/SKILL.md` | frozen .exe |
| Check work | `.grok/skills/check-work/SKILL.md` | self-verify |
| Cost | `.grok/skills/cost-efficient-workflow/SKILL.md` | budget verify |
| General | `.grok/skills/dodgeville-scheduler/SKILL.md` | entry point |

## Commands

```bash
pip install -r requirements.txt
python main.py
python dev.py route-task "task"
python dev.py agent-pack --slice <id>
python dev.py session-start
python dev.py cheap-check
python dev.py preflight
python dev.py verify-slice <id>
python dev.py check
python dev.py token-scan
python dev.py token-audit
python dev.py slice-map -v
```

## Architecture

| Layer | File | Responsibility |
|-------|------|----------------|
| Config | `config.py` | Constants, shift times, bump rules |
| Models | `models.py` | Dataclasses |
| Database | `database.py` | SQLite, schema, backup |
| Validators | `validators.py` | All validation |
| Logic | `logic/` | Business rules |
| UI | `ui/` | CustomTkinter — no SQL inline |
| Entry | `main.py` | GUI launch |
| CLI | `cli.py` | Thin wrapper over logic |

## Scheduling rules (summary)

- 14-day rotation; `config.ROTATION_BASE_DATE`
- Squad A: days 1,2,5,6,7,10,11; Squad B: others
- Bumps: same squad, junior first (`seniority_rank DESC`)
- Night minimum: Fri/Sat night shifts only
- Day-off: officer must be scheduled working; only `Pending` requests processable

Full rules: `SCHEDULING_RULES.md` (@-mention only)

## References

`docs/AGENT_ROUTING.md` · `docs/HANDOFF.md` · `docs/ZERO_AGENT_USAGE.md` · `.grok/rules/architecture.md`
