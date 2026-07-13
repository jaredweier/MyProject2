# Design System — Blue Watch (Workforce Command)

## Product Context

- **What this is:** Agency-neutral law enforcement workforce management — scheduling, leave, payroll, roster, notifications, ops dashboards. Stack-agnostic tokens; map to whatever UI ships (web, native, desktop).
- **Who it's for:** Officers, supervisors, watch commanders, admins on long shifts.
- **Space/industry:** LE WFM / command-center software (peers: Mark43, Motorola Flex, Deputy — not 2005 RMS).
- **Project type:** Internal ops dashboard (density-first, not marketing site).

## Approved Direction (2026-07-13 consultation)

**User verdict:** Variant **B** (Deep Chrome) is the visual base. Layout should use **D’s rail + hero composition**, re-skinned to B’s theme. Mockups v1 were directionally useful but **not final** — expect another visual pass before calling UI “done.”

### Hybrid summary

| Layer | Source | Rule |
|-------|--------|------|
| Color & chrome | **B** | Deep navy gradient shell, SOC density, police-blue surfaces |
| Accent | **Silver badge** | Metallic silver CTAs and active nav — not gold |
| Shell layout | **D** | Persistent left rail, hero decision band, full-width deck, right dock |
| Mood | **Modern LE tech** | Dark, fast, authoritative — not department-branded clipart |

## Aesthetic Direction

- **Direction:** Industrial command center — **Deep Chrome** (B)
- **Decoration level:** Intentional — 1px borders, left accent bars on selection, elevation over glow blobs
- **Mood:** Midnight watch floor: controlled urgency, readable at a glance, respects operator time
- **Anti-patterns:** Purple/violet gradients, glassmorphism blobs, rainbow KPI bars, centered marketing grids, Inter/Roboto/system-ui as primary type

### What disappointed in v1 mockups (fix next pass)

- Felt generic “AI dashboard” in places — needs sharper hierarchy and fewer competing panels
- Rail in D mockups did not match B’s darker chrome gradient — **merge explicitly**
- Typography not distinctive enough — lean harder into Rajdhani + Plex pairing
- Hero band should feel like a **decision surface**, not a banner ad

## Typography

- **Display/Hero:** [Rajdhani](https://fonts.google.com/specimen/Rajdhani) 600–700 — screen titles, KPI values, alert headers. One display headline per viewport.
- **Body/UI:** [IBM Plex Sans](https://fonts.google.com/specimen/IBM+Plex+Sans) 400/500/600 — 14px base, 13px dense tables, 15px primary buttons.
- **Data/Tables:** [IBM Plex Mono](https://fonts.google.com/specimen/IBM+Plex+Mono) 400/500 — shift codes, badge numbers, timestamps. Always `font-variant-numeric: tabular-nums`.
- **Micro chips:** Plex Sans 600, 11px, uppercase, `letter-spacing: 0.06em` — ON DUTY, PTO, GAP.
- **Loading:** Google Fonts CDN for web; bundle Plex for offline/native if CDN blocked.

### Scale

| Token | Size | Use |
|-------|------|-----|
| display | 28px / 1.75rem | Hero question, coverage % |
| title | 20px | Section headers |
| body | 14px | Default UI |
| small | 13px | Table cells |
| micro | 11px | Chips, column headers |

## Color

- **Approach:** Restrained — police blue owns chrome; silver owns action; semantics only for status

### Core palette

```css
:root {
  /* B — Deep Chrome shell */
  --blue-void:        #060D18;
  --blue-chrome-deep: #0A1A2E;   /* sidebar/topbar gradient start */
  --blue-chrome:      #0D2137;   /* primary chrome */
  --blue-surface:     #132A45;   /* cards, panels */
  --blue-elevated:    #1A3558;   /* hover, selected row */
  --blue-accent-hi:   #1E5AA8;   /* secondary chrome highlights, links */

  /* Silver badge — primary action (not gold) */
  --silver-bright:    #E8EDF4;
  --silver-primary:   #C5CED9;
  --silver-dim:       #8B95A5;
  --silver-glow:      rgba(197, 206, 217, 0.18);

  /* Text */
  --text-primary:     #E8EDF4;
  --text-secondary:   #9AABC4;
  --text-muted:       #7A8FA8;

  /* Semantic only */
  --success:          #2DD4A0;
  --warning:          #F0B429;
  --danger:           #E85D5D;
  --info:             #5B8DEF;   /* links only — never sidebar chrome */
}
```

### Usage rules

- **Chrome gradient (B):** `linear-gradient(180deg, var(--blue-chrome-deep) 0%, #061018 100%)` on rail + topbar
- **Primary CTA:** silver gradient `linear-gradient(180deg, var(--silver-bright), var(--silver-primary))` on `--blue-void` text
- **Active nav (D rail, B skin):** 3px left bar `--silver-primary`, background `rgba(197,206,217,0.08)`
- **Selected table row:** inset 3px left `--silver-primary`, background `var(--blue-elevated)`

## Spacing

- **Base unit:** 4px
- **Density:** Operational — loose hero, tight scan zones
- **Scale:** 2xs(4) xs(8) sm(12) md(16) lg(24) xl(32) 2xl(40) 3xl(48)

| Zone | Padding / gap |
|------|----------------|
| Hero band | 32–40px padding, 16–24px between elements |
| Nav rail | 12px item padding, 16px section gaps |
| Table rows | min 48px height, 12–16px cell padding |
| Dock panel | 16px padding, 8px between queue cards |

## Layout

- **Approach:** Hybrid — **D composition** on **B chrome**

### Shell (from D, styled as B)

```
┌──────────┬────────────────────────────────────┬─────────┐
│  Rail    │  Topbar (unit context, LIVE pill)  │         │
│  240px   ├────────────────────────────────────┤  Dock   │
│  icon+   │  HERO — one staffing question      │  320px  │
│  label   ├────────────────────────────────────┤  slide  │
│          │  DECK — roster / schedule artifact │         │
└──────────┴────────────────────────────────────┴─────────┘
```

- **Rail:** Persistent left nav (240px expanded / 72px collapsed). Deep chrome gradient, silver active indicator. Never hide critical status when collapsed — badge counts stay visible.
- **Hero:** Top 28–35% viewport — answers *“Are we staffed for the next 24h?”* Single dominant metric + gap callouts. Not a marketing banner.
- **Deck:** Schedule/roster edge-to-edge. No competing center columns.
- **Dock:** Leave queue, alerts, notifications — slides over on narrow widths.
- **Max content width:** Full viewport minus rail/dock (fluid)
- **Border radius:** sm 6px, md 10px, lg 12px — not uniform bubbles

## Motion

- **Approach:** Minimal-functional
- **Easing:** `cubic-bezier(0.2, 0, 0, 1)` enter/exit
- **Duration:** micro 120ms, short 160ms, panel dock 220ms
- **Forbidden:** Spinners on primary roster, confetti, >400ms fades, parallax

## Components

| Component | Spec |
|-----------|------|
| Status chip | Uppercase micro, semantic bg at 15% opacity |
| Primary button | Silver gradient, dark text |
| Secondary button | Silver outline on chrome |
| KPI tile | B surface, Rajdhani value, muted label |
| Table row | 48px min, mono shift column, chip status right |

## Implementation mapping (non-binding)

| Surface | Current path | Notes |
|---------|--------------|-------|
| Primary web/native | `gui/theme.py`, `gui/static/` | Migrate tokens from cyan/violet glass → Blue Watch |
| Legacy desktop | `ui/theme.py` | Map `UI_*` constants to this palette |
| CLI | Terminal semantic colors | Silver warning, green success |

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-13 | Blue Watch system created | `/design-consultation` |
| 2026-07-13 | Base visual = Variant B (Deep Chrome) | User preference |
| 2026-07-13 | Layout = D rail + hero + dock on B chrome | User wants D structure, B styling |
| 2026-07-13 | Silver badge accent, not gold | User preference |
| 2026-07-13 | Agency-neutral LE identity | User: modern LE, not Dodgeville-specific branding |
| 2026-07-13 | v1 mockups not final | User not satisfied — schedule refined mockup pass |

## Next visual pass (before implementation sprint)

1. Single mockup: **B chrome + D rail** side-by-side proof
2. Reduce panel count — one hero metric, one primary table, one dock
3. Verify silver CTAs on deep navy (contrast check)
4. Optional: re-run Codex outside voice after `OPENAI_API_KEY` or `codex login`
