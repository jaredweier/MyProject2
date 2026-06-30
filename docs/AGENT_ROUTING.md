# Agent & LLM Routing — Dodgeville PD Scheduler

**Auto-context: OFF.** Agents do not automatically load HANDOFF, all skills, or long docs. You or the agent loads context on demand (`@` mention, `route-task`, `usage-brief`).

**Any AI agent or LLM may be used for any task.** Recommendations below match **complexity** and **capability** — they are not restrictions.

## Quick route

```bash
python dev.py route-task "fix day-off bump cascade"
python dev.py route-task --complexity high "integrate rust scheduling core"
python dev.py route-task "why does approve button fail audit"
```

## Complexity matrix

| Tier | Task signals | Best Cursor mode | Model tier (advisory) | Grok / OpenCode |
|------|----------------|------------------|----------------------|-----------------|
| **trivial** | typo, comment, import, rename | **Tab** | mini / none | — |
| **low** | explain, where is, document | **Ask** | Auto, Haiku, Flash | quick chat |
| **medium** | one slice, single bug/feature | **Agent** | Sonnet, Grok, Composer | skill + agent |
| **high** | multi-file arch, refactor, rust | **Plan** then Agent | Opus, reasoning | parallel subagents |
| **vision** | UI looks wrong, layout | Agent + **screenshot** | vision-capable | ui-vision-reviewer |
| **verify** | run tests, audit, CI | **terminal** (or any agent) | any | qa-free, `/check` |

## Domain → skill → slice

| You are working on… | Load skill | Typical slice |
|---------------------|------------|---------------|
| Bumping, rotation, day-off | `scheduling-logic` | `day-off-requests` |
| Swaps | `scheduling-logic` | `shift-swaps` |
| Calendars, Gantt | `ui-development` + `scheduling-logic` | `schedules` |
| Payroll / timecard | `payroll-timecard` | `payroll-timecard` |
| Login, roles | `security` | `user-accounts` |
| UI copy/theme | `ui-aesthetics-review` | varies |
| UI layout/visual | `ui-vision-review` | varies |
| CLI / dev.py | `cli-operations` | varies |
| Frozen .exe | `build-deploy` | `build` |
| Logic/UI split | `refactor` | varies |
| Cost-conscious verify | `cost-efficient-workflow` | optional |

## Subagent pairing (high / vision)

| Primary task | Subagents (parallel OK) |
|--------------|-------------------------|
| Scheduling bug | scheduling-logic → qa-verify |
| UI feature | ui-development → ui-aesthetics-review |
| UI looks wrong | ui-vision-review → ui-development |
| Security change | security → qa-verify |
| Large refactor | refactor → code-reviewer + qa-verify |

## Disable auto-context (platform)

### Cursor

- Project rules use `alwaysApply: false` — only apply when **@-mentioned** (`.cursor/rules/agent-routing.mdc`).
- Do not rely on implicit codebase injection; tag files or run `usage-brief`.
- Settings: disable automatic full-repo context if your Cursor version exposes it; prefer explicit `@file` / `@folder`.

### Grok (this repo)

- `AGENTS.md` stays minimal at session start; load `agent-routing` skill when routing.
- `cost-efficient-workflow` is **optional** (budget), not mandatory.

### OpenCode

- `opencode.json` `instructions` is empty by default — add paths manually or per-command.
- Use `/route-task` custom command when added.

## Verification (any agent)

```bash
python dev.py cheap-check
python dev.py preflight
python dev.py verify-slice <id>
python dev.py check
```

## Related

- [`USAGE_MINIMIZATION.md`](USAGE_MINIMIZATION.md) — optional budget tips
- [`ZERO_AGENT_USAGE.md`](ZERO_AGENT_USAGE.md) — legacy free-first guide (optional)
