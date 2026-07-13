# Agent toolkit hub

**Bootstrap:** `python dev.py session-start` → paste `@logs/agent_kit/latest.md` · `@logs/agent_pack/latest.md`

## What to use when

| Goal | Command / artifact |
|------|--------------------|
| **Route** | `python dev.py route-task "…"` (obey cost_tier) |
| **Token min** | `agent-kit` · `usage-brief` · `outline` · `token-improve` · skill `token-discipline` |
| **Rules** | `AGENTS.md` · `docs/AGENT_STABLE.md` · `.grok/rules/*` |
| **Ship** | `verify --tier check` + `honest_gate` |
| **UI Chronos** | skill `ui-development` · `gui/pages/*` |
| **Optional research** | `ui-domain` / `fr-domain` / `math-domain` **if user asks** |
| **Optional graph** | `graphify` / `graphify-gate` **if user asks** (`SCHEDULER_GRAPHIFY=1`) |
| **Archived design skills** | `.grok/skills/_archive/` (load only if user asks redesign) |

## Lean session

```bash
python dev.py agent-kit --slice day-off-requests --task "fix bump edge case"
python dev.py usage-brief day-off-requests
python dev.py outline logic/scheduling.py
# edit touch_together only
python dev.py verify --tier fast
python dev.py verify --tier check
```

## Caveman
Short bullets. No OSS/graphify tax by default.
