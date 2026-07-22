# Dodgeville PD — Agent Rules
**Session auto** now. Auto-context off. Skills on demand. UI: `gui/` Chronos.
**Stable** `@docs/AGENT_STABLE.md` · **Pack** `@logs/agent_pack/latest.md` · **Contract** `@logs/SESSION_CONTRACT.md`
**Trust** `@docs/AGENT_TRUST_AND_MISTAKES.md` · `@logs/NEXT_SESSION_BRIEF.md`
## Trust
Never claim fixed/done without user scenario proof (or residual). Unit≠Chronos. Prove first.
## Caveman (ABSOLUTE)
Short bullets. No preamble, no recap, no "let me". Prose only if explain/docs asked. 2026-07-17: agent broke this all session — do not repeat.
## Route once
`python dev.py route-task "<task>"` → cost_tier. Max one skill body.
## Minimize (ABSOLUTE)
Fewest tool calls / tokens that still finish the task fully. No parallel/background spam without checking in. One thing at a time unless told otherwise.
usage-brief → outline/symbol → edit touch_together → `verify --tier fast`
Ship: `verify --tier check` + `logs/last_verify.json` → honest_gate true
## Hard bans
No explore/plan subagents; no subagents for gates. Max 1 skill/task.
Never open `docs/archived_skills/` unless user names that skill.
Optional only if asked: graphify · vision · OSS research.
