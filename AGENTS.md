# Dodgeville PD — Agent Rules
**Session auto** now. Auto-context off. Skills on demand. UI: `gui/` Chronos.
**Stable** `@docs/AGENT_STABLE.md` · **Pack** `@logs/agent_pack/latest.md` · **Contract** `@logs/SESSION_CONTRACT.md`
**Trust** `@docs/AGENT_TRUST_AND_MISTAKES.md` · `@logs/NEXT_SESSION_BRIEF.md`
## Trust
Never claim fixed/done without user scenario proof (or residual). Unit≠Chronos. Prove first.
## Caveman
Short bullets. No preamble. Prose only if explain/docs.
## Route once
`python dev.py route-task "<task>"` → cost_tier. Max one skill body.
## Minimize
usage-brief → outline/symbol → edit touch_together → `verify --tier fast`
Ship: `verify --tier check` + `logs/last_verify.json` → honest_gate true
## Hard bans
No explore/plan subagents; no subagents for gates. Max 1 skill/task.
Never open `docs/archived_skills/` unless user names that skill.
Optional only if asked: graphify · vision · OSS research.

## Simulator & Optimizer Logic
- **User Numbers First**: Strictly follow the constraint of shift length entered by a user if chosen to have on. If off, all shift lengths in range of 8 and 12.5 hours in .5 hour increments should be considered to meet whatever constraints the user has selected. Do not invent other defaults when overriding is requested.
- **Annual Math**: Compute annual hours using `projected_annual_hours(pattern, length)` based on the pattern cycle, not noisy 28-day extrapolations.
- **Deep Search**: The optimizer must evaluate multi-block variations, stagger, and rotation style. Never collapse daily bands during shift rebalancing.

## UI & Product Integrity
- **Quasar Primary**: `primary` color must be command blue (`#3B7DD8`), not silver (`#C5CED9`).
- **Layout Stability**: Use fixed grids and disabled states to prevent row jumping in the simulator.
- **Prove UI**: Do not claim UI is fixed without confirming the button colors, dropdown behaviors (e.g., DOW selection), and centering.
