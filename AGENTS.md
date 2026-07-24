# Dodgeville PD — Agent Rules
## Rule 1 (ABSOLUTE, overrides all else) — Caveman + Silence
Always speak in caveman: short bullets, no preamble, no recap, no "let me", no filler. Prose only if user asks to explain/docs. Do not talk to user unless blocked, user input is required, or material risk needs warning — otherwise work silently, send only final result.
**Active workspace (ALL reads/writes/commands):** `C:\Users\Windows\Desktop\Chronos Command GPT` — never edit `C:\Users\Windows\Chronos Workspace`
**Canonical product master plan (MANDATORY before product planning or implementation):** `C:\Users\Windows\Chronos Workspace\docs\PRODUCT_MASTER_PLAN.md`
**Simulator next-session plan (MANDATORY before simulator work):** `@docs/SIMULATOR_NEXT_SESSION_PLAN.md`
**Session auto** now. Auto-context off. Skills on demand. UI: `gui/` Chronos.
**Stable** `@docs/AGENT_STABLE.md` · **Pack** `@logs/agent_pack/latest.md` · **Contract** `@logs/SESSION_CONTRACT.md`
**Trust** `@docs/AGENT_TRUST_AND_MISTAKES.md` · `@logs/NEXT_SESSION_BRIEF.md`
## Trust — Never claim fixed/done without user scenario proof (or residual). Unit≠Chronos. Prove first.
2026-07-17: agent broke Rule 1 all session — do not repeat.
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
