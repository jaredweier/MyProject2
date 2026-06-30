---
name: ui-vision-review
description: >
  Observe Dodgeville PD Scheduler UI visually and statically — read ui-observe
  bundles, ui-live PNGs, and ui-review reports; produce prioritized recommendations
  and apply fixes. Use when improving GUI look/feel, reviewing screenshots, or
  asked to observe the UI and recommend fixes.
---

# UI Vision Review Agent

## Purpose

Close the loop: **see the UI → recommend changes → fix code → verify**.

Pairs with:
- **Static:** `python dev.py ui-review`
- **Visual:** `python dev.py ui-live` or `python dev.py ui-observe --live`
- **Runtime:** `python dev.py ui-smoke`

## Quick start

```bash
python dev.py ui-observe              # smoke + static review + agent brief
python dev.py ui-observe --live       # + screenshots for vision review
python dev.py ui-observe -v           # verbose static findings
```

Read the bundle:
- `logs/ui_observe/<latest>/observation_brief.md`
- `logs/ui_observe/<latest>/manifest.json`
- PNGs in `manifest["screenshot_dir"]`
- `logs/ui_review/<latest>/report.md`

## Agent workflow

### 1. Capture

```bash
python dev.py ui-observe --live
```

If headless or fast pass only: `python dev.py ui-observe` (uses latest screenshots if present).

### 2. Observe (vision)

Open PNGs from `manifest.json` → `screenshots` list. For each key screen, note:

| Lens | Look for |
|------|----------|
| **Layout** | Clutter, misalignment, truncated text, empty dead space |
| **Hierarchy** | Page title vs subtitle vs body; stat cards readable at glance |
| **Theme** | Navy/cyan/gold tactical palette consistent; no stray hex colors |
| **Density** | Monthly calendar cells — last name + shift readable; scroll fatigue |
| **LE tone** | Professional command-center feel; no demo/debug copy in production paths |
| **Accessibility** | Contrast (muted text on dark), button targets ≥ 32px height |
| **Photos** | Logo + team photo visible on login/dashboard |

### 3. Observe (static)

Read `report.md` / `report.json` from latest `ui-review`:
- **error** — spelling: fix immediately
- **warn** — wording mismatches (nav vs dialog labels)
- **info** — hardcoded colors, button size variance

### 4. Recommend

Produce a short prioritized list:

1. **P0** — broken layout, crashes (ui-smoke failures), unreadable text
2. **P1** — theme/copy inconsistencies, cluttered calendar/toolbar
3. **P2** — polish (spacing, icon alignment, empty states)

### 5. Fix (delegate)

| Finding | Skill / files |
|---------|----------------|
| Layout, widgets, nav, refresh | `ui-development` → `ui/*_pages.py`, `widgets.py` |
| Copy, colors, fonts, spelling | `ui-aesthetics-review` → `ui/theme.py`, whitelist |
| Card/grid pack conflicts | `ui/widgets.py` `Card.body`, avoid pack+grid on same parent |
| Permissions visible in UI | `security` — remove role labels from status bar |

### 6. Verify

```bash
python dev.py ui-smoke
python dev.py ui-review --strict
python dev.py check
```

Optional: `python dev.py ui-observe --live` to refresh screenshots.

## Key screens (checklist)

- [ ] Login — team photo, logo, no role/demo hints
- [ ] Command Post — hero, on-duty strip, stat cards, alerts
- [ ] Original Monthly Schedule — calendar grid, day detail panel
- [ ] Current Monthly Schedule — sync CTA, bump colors
- [ ] Duty Timeline — Gantt legend, covering color
- [ ] Time Off — queue + ledger
- [ ] Patrol Roster — sticky header combos (not in scroll)
- [ ] Payroll / Timecard — period nav, holiday markers
- [ ] Ops Reports — section headers
- [ ] Access Control — user list (admin only)

## Scope boundaries

- **Do** edit `ui/*.py`, `ui/theme.py`, `scripts/data/ui_review_whitelist.txt`
- **Do not** change scheduling rules or validators for visual-only work
- **Do not** weaken permission checks for cleaner UI

## Related skills

- `ui-aesthetics-review` — static scan tooling
- `ui-development` — implementation
- `qa-verify` — regression gates
- `check-work` — post-fix self-verify
