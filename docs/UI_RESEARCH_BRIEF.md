# UI research brief — LE + scheduling + payroll + 2026 design

Sources: Mark43 CAD, Spillman/Motorola Flex, Aladtec, Deputy, When I Work, Gusto/ADP reviews, COPS/SEARCH LE dashboards, Linear/SaaS 2026 trends.

## What to steal (and what we already ship)

| Source | Pattern | Our mapping |
|--------|---------|-------------|
| **Mark43 CAD** | Low cognitive load, configurable, dark default, “built for people” | Dark ops floor, lit nav rail, plain subtitles |
| **COPS LE dashboards** | Actionable at a glance; severity must read without prose | Green / amber / red AlertBanner + KPI rails |
| **Command centers** | One-screen ops; 3-color aviation model | Dashboard hero + on-duty chips; SYSTEM LIVE pill |
| **Deputy / When I Work** | Status-first schedule, clear CTAs, shift cards | Gantt status legend; action tiles not rainbow bars |
| **Gusto** | Plain English > HR jargon; pay period obvious | Sentence case; period pills; toast success |
| **Linear 2026** | Density with calm chrome; command palette; progressive disclosure | Compact type scale; jump box; ExpandableSection |
| **Enterprise SaaS 2026** | Role-based home; progressive disclosure; restrained accent | Officer vs admin dashboard; hubs + subnav |

## Principles (enforce in UI code)

1. **Severity before decoration** — critical / warning / ok only; no decorative rainbow.
2. **One primary action per region** — accent fill once; secondary outline.
3. **Status is a chip or bar, not a wall of text.**
4. **Outcome-first labels** — “Submit time off” not “New Request Form Module”.
5. **Density with hierarchy** — more data, less chrome; micro labels for context.
6. **Role-based first screen** — officer home ≠ supervisor ops floor.
7. **Progressive disclosure** — advanced filters collapsed; core path always visible.
8. **Dark slate, not pure black** — reduce eye strain on long watches.

## Open source / OSS to study (not to embed)

**Full curated list (with URLs for agents):** [`CHRONOS_SOURCES.md`](CHRONOS_SOURCES.md)

- [NiceGUI](https://github.com/zauberzeug/nicegui) + [docs](https://nicegui.io/documentation) — **primary Chronos shell** (`gui/`)
- [Quasar dark mode](https://quasar.dev/style/dark-mode/) — CSS variables under NiceGUI
- [Schedule-X](https://github.com/schedule-x/schedule-x) — calendar/grid UX patterns only
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) — legacy `ui/` reference
- Shift-planning / OR-Tools CP-SAT — optimizer ideas; domain rules stay in `logic/*`
- HRIS demos (OrangeHRM, etc.) — leave request queues

## Do not

- Copy consumer “playful” Gusto pastels for LE ops floor
- Recreate full CAD maps in this desktop app
- Add LLM frameworks into the product UI runtime

## Coverage optimizer (product)

See `logic/coverage_optimizer.py` + `.grok/rules/scheduling-math.md`:
- Multi-plan beam search for day-off bumps
- Per-band min staffing via `min_staffing_by_band`
- Supervisor plan picker on approve (UI)
- Simulator “Find best staffing combination”
