"""Visual system — Blue Watch Deep Chrome (DESIGN.md B + D rail).

Police navy chrome, silver CTAs — no violet glass.
"""

from __future__ import annotations

GLOBAL_CSS = r"""
/* Blue Watch Deep Chrome — DESIGN.md (offline system fonts) */
:root {
  --blue-void: #060D18;
  --blue-chrome-deep: #0A1A2E;
  --blue-chrome: #0D2137;
  --blue-surface: #132A45;
  --blue-elevated: #1A3558;
  --blue-accent-hi: #1E5AA8;
  --silver-bright: #E8EDF4;
  --silver-primary: #C5CED9;
  --silver-dim: #8B95A5;
  --silver-glow: rgba(197, 206, 217, 0.18);
  --bg: var(--blue-void);
  --bg-deep: #061018;
  --glass: rgba(13, 33, 55, 0.88);
  --glass-2: rgba(19, 42, 69, 0.92);
  --surface: var(--blue-surface);
  --surface-2: var(--blue-elevated);
  --surface-3: #1E3A5F;
  --border: rgba(197, 206, 217, 0.12);
  --border-hi: rgba(197, 206, 217, 0.28);
  --text: var(--silver-bright);
  --muted: #9AABC4;
  --dim: #7A8FA8;
  --cyan: var(--silver-primary);
  --cyan-dim: var(--silver-glow);
  --violet: var(--blue-accent-hi);
  --violet-dim: rgba(30, 90, 168, 0.18);
  --blue: var(--blue-accent-hi);
  --gold: var(--silver-primary);
  --success: #2DD4A0;
  --warning: #F0B429;
  --danger: #E85D5D;
  --info: #5B8DEF;
  /* CTA system (locked 2026-07): primary = command blue; silver = chrome accent only */
  --cmd-blue: #3B7DD8;
  --cmd-blue-hi: #6BA3F5;
  --cmd-blue-deep: #1E5AA8;
  --font: 'IBM Plex Sans', 'Segoe UI', system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif;
  --font-display: 'Rajdhani', 'Segoe UI', system-ui, sans-serif;
  --mono: 'IBM Plex Mono', ui-monospace, 'Cascadia Mono', Consolas, 'Courier New', monospace;
  --r: 10px;
  --r-sm: 6px;
  --shadow: 0 0 0 1px rgba(255,255,255,0.04), 0 16px 40px rgba(0,0,0,0.45);
  --glow-accent: 0 0 28px var(--silver-glow);
  --glow-blue: 0 0 24px rgba(30, 90, 168, 0.15);
  /* legacy aliases (do not use in new CSS) */
  --glow-cyan: var(--glow-accent);
  --glow-violet: var(--glow-blue);
  --ease-ops: cubic-bezier(0.2, 0, 0, 1);
  --dur-micro: 120ms;
  --dur-short: 160ms;
  --dur-panel: 220ms;
}

/* ===== Base — kill Quasar flat defaults ===== */
html, body, #app, .q-page, .nicegui-content, .q-layout, .q-page-container {
  background: transparent !important;
  color: var(--text) !important;
  font-family: var(--font) !important;
  letter-spacing: -0.015em;
}

/* Title Case chrome (display-only CSS — never mutates form values or Python strings) */
.page-kicker,
.page-title,
.page-sub,
.panel-title,
.kpi-l,
.kpi-hint,
.kpi-v,
.nav-sec,
.nav-link,
.nav-link-label,
.action-tile strong,
.action-tile span,
.media-card-title,
.empty-state-title,
.empty-state-hint,
.dock-head-title,
.dock-sec-title,
.dock-card,
.shift-card-title,
.status-chip,
.login-form-sub,
.login-kicker,
.login-vendor,
.q-btn,
.q-btn .q-btn__content,
.q-btn .block,
.q-tab,
.q-tab__label,
.q-item__label,
.q-field__label,
.q-checkbox__label,
.q-toggle__label,
.q-radio__label,
.q-expansion-item .q-item__section--main,
.mobile-action-tile,
.dc-mobile-nav-item,
.top-bar .page-title,
.user-pill label {
  text-transform: capitalize !important;
}
/* Product brand — always CHRONOS COMMAND (all caps); config string stays "Chronos Command" */
.dc-brand-name,
.cmd-title,
.cmd-strip .cmd-title,
.status-bar .product,
.login-form-title,
.product-brand,
.page-kicker.product-brand {
  text-transform: uppercase !important;
  letter-spacing: 0.06em !important;
}
/* Never transform clocks, dates, mono codes, typed inputs (logic/auth safety) */
.page-sub.mono,
.cmd-strip,
.cmd-strip span:not(.cmd-title):not(.product-brand),
.cmd-strip strong,
.status-bar,
.status-bar span:not(.product):not(.product-brand),
.mono,
.sched-wrap,
.sched-wrap *,
.data-row .mono,
.data-row .text-xs.mono,
.date-ddmmyyyy,
.date-mdy,
.date-dmy,
strong.date-ddmmyyyy,
strong.date-mdy,
strong.date-dmy,
.login-foot,
input,
textarea,
select,
.q-field__native,
.q-field__input,
.q-placeholder,
.q-select__dropdown-icon {
  text-transform: none !important;
  font-variant-numeric: tabular-nums;
}
body {
  /* Restrained chrome — data wins over decoration (Linear / Esri ops) */
  background:
    linear-gradient(180deg, var(--blue-chrome-deep) 0%, var(--blue-void) 42%, #061018 100%) !important;
  min-height: 100vh !important;
  overflow-x: hidden;
}

/* Sleek custom scrollbars */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: rgba(6, 13, 24, 0.3);
}
::-webkit-scrollbar-thumb {
  background: rgba(197, 206, 217, 0.15);
  border-radius: 99px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(197, 206, 217, 0.3);
}

/* Keyboard focus — always visible for power users */
:focus-visible {
  outline: 2px solid var(--cmd-blue-hi) !important;
  outline-offset: 2px !important;
}
.nav-link:focus-visible,
.action-tile:focus-visible,
.dock-card:focus-visible,
.shift-card:focus-visible {
  outline: 2px solid var(--silver-primary) !important;
  outline-offset: 1px !important;
}
.q-dark { background: transparent !important; }

/* Premium active input fields */
.q-field--focused .q-field__control {
  border-color: var(--cmd-blue-hi) !important;
  box-shadow: 0 0 14px rgba(107, 163, 245, 0.25) !important;
}

/* ===== Shell layout (sidebar + main + bottom status) ===== */
.dc-shell {
  display: flex !important;
  flex-direction: column !important;
  min-height: 100vh !important;
  width: 100% !important;
  max-width: 100vw;
  overflow: hidden;
}
.dc-shell-body {
  display: flex !important;
  flex-direction: row !important;
  flex: 1 1 auto !important;
  min-height: 0 !important;
  width: 100%;
}
.dc-shell-body > .dc-sidebar {
  flex: 0 0 240px !important;
  width: 240px !important;
  max-width: 240px !important;
  transition: width var(--dur-panel) var(--ease-ops), flex-basis var(--dur-panel) var(--ease-ops);
  overflow-x: hidden;
  overflow-y: auto;
}
.dc-shell.rail-collapsed .dc-shell-body > .dc-sidebar {
  flex: 0 0 72px !important;
  width: 72px !important;
  max-width: 72px !important;
}
.dc-shell.rail-collapsed .dc-brand-name,
.dc-shell.rail-collapsed .dc-brand-vendor,
.dc-shell.rail-collapsed .nav-sec,
.dc-shell.rail-collapsed .nav-link-label,
.dc-shell.rail-collapsed .nav-foot .q-btn,
.dc-shell.rail-collapsed .nav-foot > *:not(.rail-toggle) {
  display: none !important;
}
.dc-shell.rail-collapsed .nav-link {
  justify-content: center;
  padding: 10px 8px;
}
.dc-shell.rail-collapsed .nav-badge {
  position: absolute;
  top: 4px;
  right: 4px;
}
.dc-shell-body > .dc-main {
  flex: 1 1 auto !important;
  min-width: 0 !important;
  display: flex !important;
  flex-direction: column !important;
}
.dc-shell-body > .dc-dock {
  flex: 0 0 300px !important;
  width: 300px !important;
  max-width: 300px !important;
  min-width: 0;
  display: flex !important;
  flex-direction: column !important;
  border-left: 1px solid var(--border);
  background: linear-gradient(180deg, #0A1A2E 0%, #061018 100%);
  overflow-y: auto;
  transition: width var(--dur-panel) var(--ease-ops), transform var(--dur-panel) var(--ease-ops), opacity var(--dur-short) var(--ease-ops);
  z-index: 25;
}
.dc-shell.dock-hidden .dc-shell-body > .dc-dock {
  display: none !important;
}
@media (max-width: 1280px) {
  .dc-shell-body > .dc-dock {
    position: fixed !important;
    top: 0;
    right: 0;
    bottom: 36px;
    width: min(320px, 92vw) !important;
    max-width: min(320px, 92vw) !important;
    flex: none !important;
    box-shadow: -12px 0 40px rgba(0,0,0,0.45);
    transform: translateX(0);
  }
  .dc-shell.dock-hidden .dc-shell-body > .dc-dock {
    display: none !important;
  }
}
.dc-shell > .status-bar {
  flex: 0 0 auto !important;
  width: 100% !important;
}

/* Bottom compliance / product status bar */
.status-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 20px;
  padding: 8px 18px;
  background: linear-gradient(180deg, rgba(8, 12, 22, 0.98), rgba(4, 6, 12, 0.99));
  border-top: 1px solid var(--border);
  font-family: var(--mono);
  font-size: 11px;
  color: var(--muted);
  z-index: 40;
}
.status-bar .product {
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  background: linear-gradient(120deg, #f8fafc, #C5CED9 50%, #9AABC4);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  border-radius: 999px;
  border: 1px solid rgba(34, 197, 94, 0.35);
  background: rgba(34, 197, 94, 0.08);
  color: #86efac;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: none !important;
}
.status-pill .glow-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 8px #22c55e, 0 0 16px rgba(34, 197, 94, 0.7);
  animation: pulse-live 1.6s ease infinite;
  flex-shrink: 0;
}

/* Department media gallery */
.media-card {
  background: linear-gradient(165deg, rgba(22, 28, 48, 0.95), rgba(12, 16, 28, 0.98));
  border: 1px solid var(--border);
  border-radius: var(--r);
  overflow: hidden;
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  min-height: 280px;
}
.media-card-hero {
  position: relative;
  height: 200px;
  background: var(--surface-2);
  overflow: hidden;
}
.media-card-hero img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.media-card-hero.logo-hero {
  height: 180px;
  display: grid;
  place-items: center;
  background:
    radial-gradient(circle at 50% 40%, rgba(197, 206, 217, 0.12), transparent 55%),
    var(--surface-2);
}
.media-card-hero.logo-hero img {
  width: auto;
  height: auto;
  max-height: 140px;
  max-width: 80%;
  object-fit: contain;
}
.media-card-body {
  padding: 16px 18px 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex: 1;
}
.media-card-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: -0.01em;
}
.media-card-meta {
  font-size: 12px;
  color: var(--dim);
  line-height: 1.4;
}
.media-empty {
  color: var(--dim);
  font-size: 13px;
  text-align: center;
  padding: 24px;
}
.officer-media-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}
.officer-media-tile {
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  background: var(--surface-2);
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.officer-media-tile:hover,
.officer-media-tile.active {
  border-color: rgba(197, 206, 217, 0.4);
  box-shadow: var(--glow-cyan);
}
.officer-media-tile .thumb {
  height: 100px;
  background: #0a0e18;
  display: grid;
  place-items: center;
  overflow: hidden;
}
.officer-media-tile .thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.officer-media-tile .cap {
  padding: 8px 10px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dc-sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  display: flex;
  flex-direction: column;
  padding: 20px 14px 16px;
  background: linear-gradient(180deg, var(--blue-chrome-deep) 0%, #061018 100%);
  border-right: 1px solid var(--border);
  box-shadow: inset -1px 0 0 rgba(197, 206, 217, 0.04);
  z-index: 30;
  overflow-y: auto;
}
.dc-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

/* ===== Brand (logo mark + product name only) ===== */
.dc-brand {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 10px 20px;
  margin-bottom: 6px;
  border-bottom: 1px solid var(--border);
}
.dc-logo-mark {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  flex-shrink: 0;
  overflow: hidden;
  border: 2px solid rgba(197, 206, 217, 0.45);
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.4),
    0 0 28px rgba(197, 206, 217, 0.35);
  background: #0a0e18;
  display: grid;
  place-items: center;
}
.dc-logo-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.dc-orb {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background:
    radial-gradient(circle at 32% 28%, #E8EDF4 0%, #C5CED9 28%, #1E5AA8 70%, #0A1A2E 100%);
  /* no PD monogram — empty mark only if no logo uploaded */
}
.dc-brand-name {
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 0.04em;
  line-height: 1.1;
  background: linear-gradient(120deg, #ffffff 10%, #E8EDF4 55%, #9AABC4 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  text-transform: uppercase !important;
  flex: 1;
  min-width: 0;
}
.dc-brand-vendor {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--dim, #8B9BB0);
  margin-top: 2px;
  text-transform: none;
}
/* Officer mobile bottom nav */
.dc-mobile-nav {
  display: none;
}
.mobile-action-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.mobile-action-tile {
  background: var(--panel, #0F1724);
  border: 1px solid var(--border, rgba(197,206,217,0.15));
  border-radius: 12px;
  padding: 14px 12px;
  min-height: 64px;
  cursor: pointer;
}
.mobile-action-tile:active {
  border-color: rgba(59, 125, 216, 0.6);
}
.mobile-day-row {
  padding: 10px 0;
}
@media (max-width: 900px) {
  .dc-sidebar {
    display: none !important;
  }
  .dc-shell-body {
    display: block !important;
  }
  .dc-main {
    padding-bottom: 72px;
  }
  .dc-mobile-nav {
    display: flex;
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 50;
    background: rgba(6, 13, 24, 0.96);
    border-top: 1px solid var(--border, rgba(197,206,217,0.2));
    padding: 6px 4px calc(6px + env(safe-area-inset-bottom));
    justify-content: space-around;
    gap: 2px;
  }
  .dc-mobile-nav-item {
    flex: 1;
    text-align: center;
    padding: 6px 2px;
    font-size: 10px;
    color: var(--dim, #8B9BB0);
    cursor: pointer;
    border-radius: 8px;
  }
  .dc-mobile-nav-item.active {
    color: #E8EDF4;
    background: rgba(59, 125, 216, 0.18);
  }
  .dc-mobile-nav-item .nav-ico {
    display: block;
    font-size: 16px;
    margin-bottom: 2px;
  }
  .status-bar {
    display: none;
  }
}
.cmd-title {
  font-weight: 800;
  /* letter-spacing / uppercase set by product-brand block above */
}

/* ===== Nav ===== */
.nav-sec {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: capitalize !important;
  color: var(--dim);
  padding: 16px 12px 6px;
}
.nav-link {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 14px;
  margin: 2px 0;
  border-radius: 12px;
  color: var(--muted) !important;
  font-size: 13.5px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid transparent;
  background: transparent;
  width: 100%;
  text-align: left;
  text-decoration: none !important;
  transition: all 0.18s ease;
}
.nav-link:hover {
  background: rgba(197, 206, 217, 0.05);
  color: var(--text) !important;
  border-color: rgba(197, 206, 217, 0.15);
}
.nav-link.active {
  background: rgba(197, 206, 217, 0.09);
  color: var(--text) !important;
  border-color: rgba(197, 206, 217, 0.22);
  box-shadow: inset 4px 0 0 var(--silver-primary);
}
.nav-ico {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--border);
  display: grid;
  place-items: center;
  font-size: 13px;
  flex-shrink: 0;
}
.nav-link.active .nav-ico {
  background: rgba(197, 206, 217, 0.15);
  border-color: rgba(197, 206, 217, 0.35);
  box-shadow: 0 0 12px rgba(197, 206, 217, 0.25);
}

/* ===== Command strip (look 2 PULSE) ===== */
.cmd-strip {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 14px;
  padding: 10px 22px;
  background: linear-gradient(180deg, rgba(10, 26, 46, 0.8), rgba(6, 13, 24, 0.7));
  border-bottom: 1px solid rgba(107, 163, 245, 0.15);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35);
  font-family: var(--mono);
  font-size: 11px;
  color: var(--muted);
  backdrop-filter: blur(24px);
  position: sticky;
  top: 0;
  z-index: 20;
}
.cmd-strip .sep {
  width: 1px;
  height: 14px;
  background: var(--border-hi);
  opacity: 0.5;
}
.cmd-title {
  font-weight: 700;
  letter-spacing: 0.12em;
  color: var(--cyan);
  text-transform: uppercase;
}
.cmd-strip strong { color: var(--text); font-weight: 600; }
.live-badge {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 4px 12px;
  border-radius: 999px;
  border: 1px solid rgba(34, 197, 94, 0.5);
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
  font-weight: 700;
  font-size: 10px;
  letter-spacing: 0.08em;
  box-shadow: 0 0 24px rgba(34, 197, 94, 0.25);
  text-shadow: 0 0 8px rgba(34, 197, 94, 0.5);
}
.live-badge::before {
  content: '';
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 10px #22c55e;
  animation: pulse-live 1.6s ease infinite;
}
@keyframes pulse-live {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.85); }
}

/* ===== Top bar ===== */
.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 24px 32px 16px;
  background: linear-gradient(180deg, rgba(10, 21, 37, 0.45) 0%, transparent 100%);
  border-bottom: 1px solid rgba(197, 206, 217, 0.08);
  margin-bottom: 16px;
}
.page-kicker {
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--cyan);
  margin-bottom: 6px;
}
.page-title {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.035em;
  margin: 0;
  line-height: 1.1;
  background: linear-gradient(120deg, #f8fafc 20%, #E8EDF4 55%, #9AABC4 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.page-sub {
  font-size: 13.5px;
  color: var(--muted);
  margin-top: 6px;
  font-weight: 450;
}
.dc-content { padding: 8px 28px 40px; flex: 1; }

.user-pill {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 5px 14px 5px 5px;
  border-radius: 999px;
  border: 1px solid var(--border-hi);
  background: var(--glass-2);
  box-shadow: var(--glow-violet);
  backdrop-filter: blur(12px);
}
.user-av {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #C5CED9, #1E5AA8);
  color: #060D18;
  font-size: 11px;
  font-weight: 800;
  display: grid;
  place-items: center;
  box-shadow: 0 0 16px rgba(197, 206, 217, 0.35);
}

/* ===== Panels / cards (glass) ===== */
.panel {
  background: linear-gradient(165deg, rgba(14, 22, 37, 0.9), rgba(8, 12, 22, 0.96));
  border: 1px solid rgba(197, 206, 217, 0.09);
  border-radius: var(--r);
  padding: 22px 24px;
  box-shadow: var(--shadow);
  position: relative;
  overflow: hidden;
  backdrop-filter: blur(20px);
  transition: border-color var(--dur-short) var(--ease-ops), box-shadow var(--dur-short) var(--ease-ops);
}
.panel::before {
  content: '';
  position: absolute;
  inset: 0 0 auto 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(197, 206, 217, 0.25), rgba(107, 163, 245, 0.35), transparent);
}
.panel-glow {
  box-shadow: var(--shadow), 0 0 30px rgba(107, 163, 245, 0.12);
  border-color: rgba(107, 163, 245, 0.28);
}
.panel-title {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: capitalize !important;
  color: var(--muted);
  margin-bottom: 14px;
}
/* ===== KPI cards (look 1) ===== */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 16px;
}
.kpi {
  position: relative;
  background: linear-gradient(160deg, rgba(20, 29, 47, 0.92), rgba(10, 15, 26, 0.96));
  border: 1px solid rgba(197, 206, 217, 0.08);
  border-radius: var(--r-sm);
  padding: 18px 20px;
  overflow: hidden;
  box-shadow: var(--shadow);
  transition: transform var(--dur-short) var(--ease-ops), border-color var(--dur-short) var(--ease-ops), box-shadow var(--dur-short) var(--ease-ops);
}
.kpi:hover {
  transform: translateY(-3px);
  border-color: rgba(197, 206, 217, 0.22);
  box-shadow: var(--shadow), 0 8px 24px rgba(0, 0, 0, 0.4), 0 0 16px rgba(197, 206, 217, 0.05);
}
.kpi::after {
  content: '';
  position: absolute;
  top: 0; right: 0;
  width: 80px; height: 80px;
  background: radial-gradient(circle, rgba(197, 206, 217, 0.12), transparent 70%);
  pointer-events: none;
}
.kpi.v::after { background: radial-gradient(circle, rgba(30, 90, 168, 0.15), transparent 70%); }
.kpi.w::after { background: radial-gradient(circle, rgba(245, 158, 11, 0.12), transparent 70%); }
.kpi.g::after { background: radial-gradient(circle, rgba(34, 197, 94, 0.12), transparent 70%); }
.kpi.d::after { background: radial-gradient(circle, rgba(239, 68, 68, 0.12), transparent 70%); }
.kpi-l {
  font-size: 11px;
  font-weight: 600;
  color: var(--dim);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.kpi-v {
  font-family: var(--font-display);
  font-size: clamp(40px, 5.5vw, 72px);
  font-weight: 800;
  letter-spacing: -0.04em;
  margin-top: 8px;
  color: var(--text);
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
.kpi-v.kpi-crit { color: var(--danger); }
.kpi-v.kpi-warn { color: var(--warning); }
.kpi-v.kpi-ok   { color: var(--success); }
.kpi-hint {
  font-size: 11px;
  color: var(--dim);
  margin-top: 8px;
  font-family: var(--mono);
}

/* ===== Alerts (SOC severity) ===== */
.alert {
  border-radius: 12px;
  padding: 14px 16px;
  font-size: 13px;
  margin-bottom: 8px;
  border: 1px solid var(--border);
  font-weight: 500;
}
.alert-ok {
  border-color: rgba(34, 197, 94, 0.4);
  background: linear-gradient(90deg, rgba(34, 197, 94, 0.12), rgba(34, 197, 94, 0.04));
  color: #4ade80;
  box-shadow: 0 0 30px rgba(34, 197, 94, 0.08);
}
.alert-warn {
  border-color: rgba(245, 158, 11, 0.4);
  background: linear-gradient(90deg, rgba(245, 158, 11, 0.12), transparent);
  color: #fbbf24;
}
.alert-crit {
  border-color: rgba(239, 68, 68, 0.5);
  background:
    repeating-linear-gradient(-45deg, rgba(239,68,68,0.08), rgba(239,68,68,0.08) 8px, transparent 8px, transparent 16px),
    rgba(239, 68, 68, 0.1);
  color: #fca5a5;
  font-family: var(--mono);
  font-size: 12px;
  letter-spacing: 0.04em;
}

/* ===== On-duty shift rows ===== */
.shift-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  margin-bottom: 8px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.02);
  transition: border-color 0.15s, background 0.15s;
}
.shift-row:hover {
  border-color: rgba(197, 206, 217, 0.3);
  background: rgba(197, 206, 217, 0.05);
}
.shift-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--success);
  box-shadow: 0 0 8px var(--success);
  flex-shrink: 0;
}
.shift-dot.off { background: var(--dim); box-shadow: none; }
.shift-dot.warn { background: var(--warning); box-shadow: 0 0 8px var(--warning); }

/* ===== Action tiles ===== */
.grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; }
.grid-actions {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 10px;
}
.action-tile {
  padding: 16px 18px;
  border-radius: var(--r-sm);
  border: 1px solid var(--border);
  background: linear-gradient(145deg, rgba(30, 40, 70, 0.5), rgba(14, 18, 32, 0.8));
  cursor: pointer;
  text-align: left;
  transition: all 0.18s ease;
  box-shadow: var(--shadow);
}
.action-tile:hover {
  border-color: rgba(197, 206, 217, 0.4);
  background: linear-gradient(145deg, rgba(197, 206, 217, 0.12), rgba(30, 90, 168, 0.08));
  transform: translateY(-2px);
  box-shadow: var(--glow-cyan);
}
.action-tile strong {
  display: block;
  font-size: 13.5px;
  font-weight: 650;
  color: var(--text);
  margin-bottom: 4px;
}
.action-tile span { font-size: 12px; color: var(--dim); }

.data-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.02);
  margin-bottom: 8px;
  transition: transform var(--dur-micro) var(--ease-ops), border-color var(--dur-micro) var(--ease-ops), background var(--dur-micro) var(--ease-ops), box-shadow var(--dur-micro) var(--ease-ops);
  border-left: 3px solid transparent;
}
.data-row:hover {
  border-color: rgba(107, 163, 245, 0.25);
  border-left: 3px solid var(--cmd-blue-hi);
  background: rgba(10, 26, 46, 0.45);
  transform: translateX(2px);
  box-shadow: -4px 0 12px rgba(107, 163, 245, 0.15);
}

/* ===== Buttons ===== */
.q-btn {
  font-family: var(--font) !important;
  font-weight: 600 !important;
  text-transform: none !important;
  border-radius: 10px !important;
  letter-spacing: -0.01em !important;
  transition: transform var(--dur-micro) var(--ease-ops), filter var(--dur-micro) var(--ease-ops), box-shadow var(--dur-micro) var(--ease-ops) !important;
}
.q-btn:hover {
  transform: translateY(-1.5px);
}
.q-btn:active {
  transform: translateY(0.5px);
}

/* Custom premium input field styling */
.q-field--outlined .q-field__control {
  border-radius: var(--r-sm) !important;
  border: 1px solid rgba(197, 206, 217, 0.15) !important;
  background: rgba(10, 21, 37, 0.35) !important;
  transition: border-color var(--dur-short) var(--ease-ops), box-shadow var(--dur-short) var(--ease-ops);
}
.q-field--outlined .q-field__control::before {
  border: none !important;
}
.q-field--outlined .q-field__control::after {
  border: none !important;
}
.q-field--outlined:hover .q-field__control {
  border-color: rgba(107, 163, 245, 0.35) !important;
}
.q-field--focused.q-field--outlined .q-field__control {
  border-color: var(--cmd-blue-hi) !important;
  box-shadow: 0 0 14px rgba(107, 163, 245, 0.25) !important;
  background: rgba(10, 21, 37, 0.5) !important;
}
/* Primary action = command blue (beat Quasar color=primary silver/white) */
.q-btn.btn-primary,
button.btn-primary,
.btn-primary.q-btn {
  background: linear-gradient(180deg, #6BA3F5 0%, #3B7DD8 45%, #1E5AA8 100%) !important;
  background-color: #3B7DD8 !important;
  color: #F0F7FF !important;
  box-shadow: 0 4px 18px rgba(30, 90, 168, 0.45) !important;
  border: 1px solid rgba(107, 163, 245, 0.55) !important;
}
.q-btn.btn-primary:hover,
button.btn-primary:hover {
  filter: brightness(1.08);
}
.q-btn.btn-primary .q-btn__content,
.q-btn.btn-primary .block,
.btn-primary .q-btn__content {
  color: #F0F7FF !important;
  opacity: 1 !important;
}
.q-btn.btn-ghost,
button.btn-ghost,
.btn-ghost.q-btn {
  background: rgba(30, 90, 168, 0.18) !important;
  background-color: rgba(30, 90, 168, 0.18) !important;
  border: 1px solid rgba(91, 141, 239, 0.55) !important;
  color: #E8F0FF !important;
}
.q-btn.btn-ghost .q-btn__content,
.btn-ghost .q-btn__content {
  color: #E8F0FF !important;
}
/* Checkboxes / radios — readable ticks on dark UI */
.q-checkbox__inner--truthy,
.q-checkbox__inner--indet {
  color: #6BA3F5 !important;
}
.q-checkbox__bg {
  border-color: rgba(107, 163, 245, 0.65) !important;
}
.q-checkbox__label,
.q-toggle__label {
  color: #E8EDF4 !important;
}
.btn-danger {
  background: rgba(239, 68, 68, 0.12) !important;
  color: #fca5a5 !important;
  border: 1px solid rgba(239, 68, 68, 0.35) !important;
}
.btn-gold {
  background: linear-gradient(180deg, #6BA3F5, #1E5AA8) !important;
  color: #F0F7FF !important;
}

/* Inputs */
.q-field__control {
  border-radius: 10px !important;
  background: rgba(14, 18, 32, 0.9) !important;
}
.q-field--outlined .q-field__control:before {
  border-color: var(--border) !important;
}
.q-field--outlined.q-field--focused .q-field__control:before {
  border-color: rgba(91, 141, 239, 0.65) !important;
}
.q-field__native,
.q-field__input,
.q-field__label,
.q-select__dropdown-icon {
  color: #E8EDF4 !important;
}

/* Dropdown menus — high contrast (global; was unreadable) */
.q-menu {
  background: #0C1A2E !important;
  color: #E8EDF4 !important;
  border: 1px solid rgba(91, 141, 239, 0.45) !important;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.55) !important;
}
.q-menu .q-item {
  color: #E8EDF4 !important;
  min-height: 40px !important;
  font-size: 14px !important;
}
.q-menu .q-item__label,
.q-menu .q-item__section {
  color: #E8EDF4 !important;
}
.q-menu .q-item:hover,
.q-menu .q-item--active,
.q-menu .q-manual-focusable--focused {
  background: rgba(30, 90, 168, 0.4) !important;
  color: #F8FAFC !important;
}
.q-menu .q-item.disabled,
.q-menu .q-item--disabled {
  color: #7A8FA8 !important;
}
/* Select popup list (Quasar virtual scroll) */
.q-virtual-scroll__content .q-item {
  color: #E8EDF4 !important;
  background: transparent !important;
}

/* ===== Schedule heat matrix ===== */
.sched-wrap {
  overflow-x: auto;
  font-family: var(--mono);
  font-size: 11px;
  padding: 4px 0;
}
.sched-cell {
  border-radius: 3px;
  box-shadow: inset 0 0 0 1px rgba(0,0,0,0.25);
}

/* ===== Login — centered card on viewport (always middle of window) ===== */
.login-center-shell {
  flex: 1 1 auto;
  min-height: 100vh;
  min-height: 100dvh;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  position: relative;
  background:
    radial-gradient(ellipse 70% 50% at 50% 30%, rgba(30, 90, 168, 0.22), transparent 60%),
    linear-gradient(165deg, #0A1A2E 0%, #060D18 55%, #04080f 100%);
  overflow: auto;
}
.login-center-bg {
  position: absolute !important;
  inset: 0 !important;
  width: 100% !important;
  height: 100% !important;
  object-fit: cover !important;
  opacity: 0.22;
  z-index: 0;
  filter: brightness(0.4) saturate(0.8);
}
.login-center-card {
  position: relative;
  z-index: 1;
  width: min(420px, 100%);
  margin: auto;
}
.login-shell {
  flex: 1 1 auto;
  min-height: 100vh;
  min-height: 100dvh;
  width: 100%;
  max-width: 100vw;
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr);
  place-items: stretch;
  background: #060D18;
  margin: 0 auto;
}
.login-hero {
  position: relative;
  overflow: hidden;
  min-height: 100%;
  padding: 48px 52px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background:
    radial-gradient(ellipse 80% 60% at 20% 10%, rgba(30, 90, 168, 0.28), transparent 55%),
    linear-gradient(165deg, #0A1A2E 0%, #060D18 55%, #04080f 100%);
  border-right: 1px solid rgba(197, 206, 217, 0.12);
}
.login-hero-photo {
  position: absolute !important;
  inset: 0 !important;
  width: 100% !important;
  height: 100% !important;
  object-fit: cover !important;
  z-index: 0 !important;
  filter: brightness(0.38) saturate(0.85);
}
.login-hero::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 0;
  background: linear-gradient(
    165deg,
    rgba(6, 13, 24, 0.55) 0%,
    rgba(6, 13, 24, 0.82) 55%,
    rgba(6, 13, 24, 0.92) 100%
  );
  pointer-events: none;
}
.login-hero-inner {
  position: relative;
  z-index: 1;
  max-width: 460px;
}
.login-brand-mark {
  margin-bottom: 22px;
}
.login-mark-img {
  width: 64px !important;
  height: 64px !important;
  object-fit: contain !important;
  border-radius: 14px !important;
  border: 1px solid rgba(197, 206, 217, 0.28) !important;
  background: rgba(10, 26, 46, 0.75) !important;
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.35) !important;
}
.login-mark-img--seal {
  border-radius: 50% !important;
}
.login-mark-fallback {
  width: 64px;
  height: 64px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 18px;
  letter-spacing: 0.04em;
  color: #060D18;
  background: linear-gradient(180deg, #E8EDF4, #C5CED9);
  border: 1px solid rgba(197, 206, 217, 0.4);
}
.login-kicker {
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #8B95A5;
  margin-bottom: 10px;
}
.login-title {
  margin: 0 0 14px !important;
  font-size: clamp(28px, 3.2vw, 40px) !important;
  font-weight: 700 !important;
  letter-spacing: -0.03em !important;
  line-height: 1.1 !important;
  color: #E8EDF4 !important;
  -webkit-text-fill-color: #E8EDF4 !important;
  background: none !important;
}
.login-lead {
  margin: 0 0 22px !important;
  color: #9AABC4 !important;
  font-size: 15px !important;
  max-width: 420px;
  line-height: 1.55 !important;
}
.login-chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 4px;
}
.login-chips .chip-live {
  border-color: rgba(45, 212, 160, 0.4) !important;
  color: #2DD4A0 !important;
}
.login-dept-seal {
  position: relative !important;
  z-index: 1 !important;
  width: 44px !important;
  height: 44px !important;
  object-fit: contain !important;
  border-radius: 50% !important;
  margin-top: 28px !important;
  border: 1px solid rgba(197, 206, 217, 0.3) !important;
  background: rgba(10, 26, 46, 0.5) !important;
}
.login-form-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 36px;
  background:
    linear-gradient(180deg, rgba(13, 33, 55, 0.55), rgba(6, 13, 24, 0.98));
}
.login-card {
  width: 100%;
  max-width: 400px;
  padding: 36px 36px 30px;
  border-radius: 18px;
  border: 1px solid rgba(107, 163, 245, 0.22);
  background: rgba(10, 21, 37, 0.72) !important;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.65), 0 0 40px rgba(30, 90, 168, 0.12) !important;
  backdrop-filter: blur(24px);
  position: relative;
}
.login-card::before {
  content: '';
  position: absolute;
  inset: 0 0 auto 0;
  height: 2px;
  border-radius: 18px 18px 0 0;
  background: linear-gradient(90deg, transparent, rgba(107, 163, 245, 0.55), var(--silver-primary), rgba(107, 163, 245, 0.55), transparent);
}
.login-form-title {
  margin: 0 0 6px !important;
  font-size: 26px !important;
  font-weight: 700 !important;
  letter-spacing: -0.02em !important;
  color: #E8EDF4 !important;
}
.login-form-sub {
  margin: 0 0 20px !important;
  color: #9AABC4 !important;
  font-size: 13.5px !important;
  line-height: 1.45 !important;
}
.login-field {
  margin-bottom: 4px;
}
.login-field .q-field__label {
  color: #9AABC4 !important;
}
.login-field .q-field__control {
  background: rgba(6, 13, 24, 0.75) !important;
}
.login-error {
  min-height: 1.25rem;
  margin-top: 8px;
  color: #fca5a5 !important;
  font-size: 13px !important;
}
.login-submit {
  margin-top: 16px !important;
  min-height: 44px !important;
  font-size: 15px !important;
}
.login-foot {
  margin-top: 18px;
  text-align: center;
  font-size: 11px;
  color: #7A8FA8;
  letter-spacing: 0.02em;
}

.nav-foot {
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px solid var(--border);
  font-family: var(--mono);
  font-size: 10px;
  color: var(--dim);
  line-height: 1.5;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid var(--border);
  background: rgba(255,255,255,0.03);
  color: var(--muted);
}

@media (max-width: 960px) {
  .dc-shell { grid-template-columns: 1fr; }
  .dc-sidebar { height: auto; position: relative; }
  .login-shell {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr;
  }
  .login-hero {
    min-height: 220px;
    padding: 28px 24px;
    border-right: none;
    border-bottom: 1px solid rgba(197, 206, 217, 0.12);
    justify-content: flex-end;
  }
  .login-hero-inner { max-width: none; }
  .login-title { font-size: 28px !important; }
  .login-form-wrap { padding: 28px 20px 40px; }
  .login-card { max-width: 440px; }
  .grid-2 { grid-template-columns: 1fr; }
  .page-title { font-size: 22px; }
}

/* Leave approve / plans dialogs — solid, readable, clickable above page chrome */
.q-dialog__backdrop {
  background: rgba(2, 6, 18, 0.78) !important;
}
.q-dialog__inner {
  z-index: 7000 !important;
  pointer-events: auto !important;
}
.leave-approve-dlg.q-card,
.q-dialog .leave-approve-dlg {
  background: #0c1220 !important;
  color: #e2e8f0 !important;
  opacity: 1 !important;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.65) !important;
  border: 1px solid rgba(197, 206, 217, 0.28) !important;
  pointer-events: auto !important;
}
.leave-approve-dlg .q-field__native,
.leave-approve-dlg .q-field__label,
.leave-approve-dlg .q-field__marginal {
  color: #e2e8f0 !important;
}
.leave-approve-dlg button {
  pointer-events: auto !important;
  cursor: pointer !important;
}


/* ===== 2026-07 residual visual redesign ===== */
:root {
  --cmd-blue: #3B7DD8;
  --cmd-blue-hi: #6BA3F5;
  --r: 12px;
  --shadow: 0 0 0 1px rgba(255,255,255,0.05), 0 20px 48px rgba(0,0,0,0.5);
}
.dc-sidebar {
  background: linear-gradient(180deg, #0c1a2e 0%, #081221 100%) !important;
  border-right: 1px solid rgba(197,206,217,0.14) !important;
  box-shadow: 8px 0 32px rgba(0,0,0,0.25);
}
.panel {
  border-radius: var(--r) !important;
  border: 1px solid rgba(197,206,217,0.16) !important;
  background: linear-gradient(165deg, rgba(19,42,69,0.94), rgba(10,22,40,0.98)) !important;
  box-shadow: var(--shadow) !important;
  backdrop-filter: blur(8px);
}
.panel-title {
  letter-spacing: 0.04em !important;
  font-weight: 750 !important;
  color: #F0F6FF !important;
}
.page-kicker {
  color: #6BA3F5 !important;
  letter-spacing: 0.14em !important;
  font-weight: 800 !important;
}
.page-title {
  font-weight: 800 !important;
  letter-spacing: -0.03em !important;
}
.q-btn.btn-primary, button.btn-primary {
  border-radius: 10px !important;
  font-weight: 700 !important;
  min-height: 2.4rem !important;
  transition: transform 0.12s ease, filter 0.12s ease !important;
}
.q-btn.btn-primary:active, button.btn-primary:active {
  transform: translateY(1px) scale(0.99);
}
.q-btn.btn-ghost, button.btn-ghost {
  border-radius: 10px !important;
  font-weight: 600 !important;
}
.q-field--outlined .q-field__control {
  border-radius: 10px !important;
  background: rgba(6,16,28,0.55) !important;
}
.q-field--outlined .q-field__control:before {
  border-color: rgba(197,206,217,0.22) !important;
}
.q-field--focused .q-field__control:before {
  border-color: rgba(107,163,245,0.75) !important;
  border-width: 2px !important;
}
.q-checkbox__label, .q-toggle__label {
  color: #E8EDF4 !important;
  font-weight: 600 !important;
}
.q-table, .q-markup-table {
  background: rgba(8,16,28,0.9) !important;
  color: #E8EDF4 !important;
  border-radius: 10px !important;
}
.q-table th {
  background: rgba(19,42,69,0.95) !important;
  color: #C5CED9 !important;
  font-weight: 700 !important;
}
.q-table tbody tr:hover {
  background: rgba(30,90,168,0.12) !important;
}
.offline-banner {
  position: sticky;
  top: 0;
  z-index: 9000;
  padding: 8px 14px;
  text-align: center;
  font-weight: 700;
  font-size: 0.85rem;
  background: linear-gradient(90deg, #7c2d12, #b45309);
  color: #fff7ed;
  border-bottom: 1px solid rgba(251,191,36,0.4);
}
.kpi-card, .action-tile {
  border-radius: 12px !important;
  border: 1px solid rgba(197,206,217,0.14) !important;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.12s ease;
}
.action-tile:hover, .kpi-card:hover {
  border-color: rgba(107,163,245,0.45) !important;
  box-shadow: 0 8px 28px rgba(0,0,0,0.35);
  transform: translateY(-1px);
}

/* ===== UI audit pack: dock, cards, skeleton, empty, table chrome ===== */
.nav-link { position: relative; }
.nav-badge {
  margin-left: auto;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: rgba(232, 93, 93, 0.22);
  border: 1px solid rgba(232, 93, 93, 0.45);
  color: #fca5a5;
  font-size: 10px;
  font-weight: 700;
  font-family: var(--mono);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  letter-spacing: 0;
}
.nav-link.active .nav-badge {
  background: rgba(197, 206, 217, 0.18);
  border-color: rgba(197, 206, 217, 0.4);
  color: var(--silver-bright);
}
.rail-toggle {
  width: 100%;
  margin: 4px 0 8px;
}
.dock-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 14px 14px 8px;
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  background: linear-gradient(180deg, #0A1A2E 0%, rgba(10,26,46,0.96) 100%);
  z-index: 2;
}
.dock-head-title {
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 15px;
  letter-spacing: 0.02em;
  color: var(--text);
}
.dock-body { padding: 10px 12px 24px; display: flex; flex-direction: column; gap: 8px; }
.dock-sec-title {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--dim);
  margin: 10px 0 4px;
  font-family: var(--mono);
}
.dock-card {
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(19, 42, 69, 0.55);
  border: 1px solid var(--border);
  transition: background var(--dur-micro) var(--ease-ops), border-color var(--dur-micro) var(--ease-ops);
}
.dock-card:hover {
  background: var(--blue-elevated);
  border-color: var(--border-hi);
}
.dock-card.dock-pulse {
  animation: dock-pulse 1.2s var(--ease-ops) 1;
}
@keyframes dock-pulse {
  0% { box-shadow: 0 0 0 0 rgba(197, 206, 217, 0.35); }
  100% { box-shadow: 0 0 0 8px rgba(197, 206, 217, 0); }
}
/* ===== Hero Staffing decision surface ===== */
.hero-decision {
  padding: 28px 32px !important;
  background: radial-gradient(circle at 100% 0%, rgba(107, 163, 245, 0.08), transparent 45%),
              linear-gradient(165deg, rgba(16, 28, 48, 0.95), rgba(8, 12, 22, 0.98)) !important;
  border-radius: var(--r) !important;
  border: 1px solid rgba(107, 163, 245, 0.15) !important;
  margin-bottom: 14px !important;
}
.hero-decision .kpi-v {
  font-size: 40px !important;
  font-family: var(--font-display) !important;
  font-weight: 800 !important;
  letter-spacing: 0.02em !important;
  text-shadow: 0 0 20px rgba(107, 163, 245, 0.25) !important;
}
.hero-decision .kpi-hint {
  font-size: 13px !important;
  margin-top: 12px !important;
  color: var(--muted) !important;
}
.empty-state {
  text-align: center;
  padding: 36px 24px;
  border: 1px dashed rgba(107, 163, 245, 0.22);
  border-radius: var(--r);
  background: radial-gradient(circle at center, rgba(107, 163, 245, 0.05), rgba(10, 22, 40, 0.25));
  box-shadow: inset 0 0 20px rgba(107, 163, 245, 0.02);
}
.empty-state-title {
  font-weight: 700;
  font-size: 15px;
  color: var(--text);
  margin-bottom: 6px;
}
.empty-state-hint {
  font-size: 13px;
  color: var(--muted);
  max-width: 36rem;
  margin: 0 auto;
  line-height: 1.45;
}
.skeleton-host { padding: 8px 0; }
.skeleton-label {
  font-size: 11px;
  color: var(--dim);
  font-family: var(--mono);
  margin-bottom: 8px;
}
.skeleton-row {
  height: 48px;
  border-radius: 8px;
  margin-bottom: 8px;
  background: linear-gradient(
    90deg,
    rgba(19, 42, 69, 0.5) 0%,
    rgba(30, 90, 168, 0.18) 50%,
    rgba(19, 42, 69, 0.5) 100%
  );
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.2s ease-in-out infinite;
}
@keyframes skeleton-shimmer {
  0% { background-position: 100% 0; }
  100% { background-position: -100% 0; }
}
.status-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 99px;
  font-size: 10px;
  font-weight: 750;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-family: var(--font);
  white-space: nowrap;
  border: 1px solid transparent;
}
.status-chip-ok { background: rgba(45, 212, 160, 0.12); border-color: rgba(45, 212, 160, 0.35); color: #2DD4A0; box-shadow: 0 0 12px rgba(45, 212, 160, 0.15); }
.status-chip-warn { background: rgba(240, 180, 41, 0.12); border-color: rgba(240, 180, 41, 0.35); color: #F0B429; box-shadow: 0 0 12px rgba(240, 180, 41, 0.15); }
.status-chip-crit { background: rgba(232, 93, 93, 0.12); border-color: rgba(232, 93, 93, 0.35); color: #E85D5D; box-shadow: 0 0 12px rgba(232, 93, 93, 0.15); }
.status-chip-info { background: rgba(91, 141, 239, 0.12); border-color: rgba(91, 141, 239, 0.35); color: #5B8DEF; box-shadow: 0 0 12px rgba(91, 141, 239, 0.15); }
.shift-card {
  padding: 16px 20px;
  border-radius: 12px;
  border: 1px solid rgba(197, 206, 217, 0.12);
  background: linear-gradient(165deg, rgba(14, 30, 50, 0.88), rgba(8, 16, 28, 0.95));
  backdrop-filter: blur(12px);
  margin-bottom: 12px;
  transition: border-color var(--dur-short) var(--ease-ops), transform var(--dur-micro) var(--ease-ops), box-shadow var(--dur-short) var(--ease-ops);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
}
.shift-card:hover {
  border-color: rgba(107, 163, 245, 0.35);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45), 0 0 16px rgba(107, 163, 245, 0.12);
}
.shift-card:active { transform: translateY(1px); }
.shift-card.claimed-optimistic {
  opacity: 0.55;
  pointer-events: none;
}
.mobile-day-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: rgba(19, 42, 69, 0.5);
  margin-bottom: 8px;
  min-height: 52px;
}
.mobile-day-card.today {
  border-color: rgba(197, 206, 217, 0.45);
  box-shadow: inset 3px 0 0 var(--silver-primary);
  background: rgba(26, 53, 88, 0.55);
}
/* Unified table chrome */
.data-row {
  min-height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(197, 206, 217, 0.08);
  border-radius: 0;
}
.data-row:hover {
  background: rgba(26, 53, 88, 0.35);
}
.data-row.selected,
.data-row:focus-within {
  background: var(--blue-elevated);
  box-shadow: inset 3px 0 0 var(--silver-primary);
}
.chronos-aggrid {
  --ag-background-color: transparent;
  --ag-header-background-color: rgba(10, 21, 37, 0.95);
  --ag-header-foreground-color: var(--silver-primary);
  --ag-border-color: rgba(197, 206, 217, 0.12);
  --ag-row-border-color: rgba(197, 206, 217, 0.08);
  --ag-odd-row-background-color: rgba(255, 255, 255, 0.015);
  --ag-row-hover-color: rgba(107, 163, 245, 0.12);
  --ag-font-family: var(--font);
  border-radius: var(--r);
  overflow: hidden;
  border: 1px solid rgba(197, 206, 217, 0.16);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.45);
}
.chronos-aggrid .ag-header-cell-label {
  font-size: 11px !important;
  font-weight: 700 !important;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--silver-bright) !important;
}
.chronos-aggrid .ag-row {
  min-height: 48px !important;
  transition: background-color 0.15s ease, transform 0.15s ease;
}
.chronos-aggrid .ag-row:hover {
  transform: translateX(1px);
}
.chronos-aggrid .ag-row-selected {
  background: rgba(30, 90, 168, 0.25) !important;
  box-shadow: inset 3px 0 0 var(--cmd-blue-hi);
}
.sched-cell.today-cell {
  box-shadow: 0 0 0 1px var(--silver-primary), 0 0 10px rgba(197, 206, 217, 0.28) !important;
}
.sched-col-today {
  color: var(--silver-bright) !important;
  text-shadow: 0 0 8px rgba(197, 206, 217, 0.35);
}
.drag-source {
  cursor: grab;
  user-select: none;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: rgba(19, 42, 69, 0.6);
  margin-bottom: 6px;
  font-size: 12px;
}
.drag-source:active { cursor: grabbing; }
.drop-zone {
  min-height: 44px;
  border: 1px dashed rgba(197, 206, 217, 0.28);
  border-radius: 8px;
  padding: 8px;
  transition: border-color var(--dur-micro) var(--ease-ops), background var(--dur-micro) var(--ease-ops);
}
.drop-zone.drag-over {
  border-color: var(--cmd-blue-hi);
  background: rgba(59, 125, 216, 0.12);
}
.nav-admin-more { margin-top: 4px; }
.btn-secondary-silver,
.q-btn.btn-secondary-silver {
  background: transparent !important;
  border: 1px solid rgba(197, 206, 217, 0.45) !important;
  color: var(--silver-bright) !important;
}
.cmd-palette-meta {
  font-size: 11px;
  color: var(--dim);
  font-family: var(--mono);
}

/* ===== Schedule Simulator — command-center surface (Deep Chrome) ===== */
.sim-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  width: 100%;
  max-width: 100%;
}
.sim-step-rail {
  display: flex;
  flex-wrap: wrap;
  align-items: stretch;
  gap: 8px;
  padding: 8px;
  border-radius: 99px;
  border: 1px solid rgba(197, 206, 217, 0.12);
  background: linear-gradient(180deg, rgba(14, 30, 50, 0.88), rgba(8, 16, 28, 0.96));
  box-shadow: inset 0 2px 4px rgba(255, 255, 255, 0.02), 0 4px 12px rgba(0, 0, 0, 0.25);
  backdrop-filter: blur(12px);
}
.sim-step {
  position: relative;
  display: flex;
  align-items: center;
  flex: 1 1 140px;
  min-height: 48px;
  padding: 8px 16px;
  margin: 0;
  border-radius: 99px;
  border: 1px solid transparent;
  cursor: pointer;
  user-select: none;
  color: var(--muted);
  background: transparent;
  transition:
    background var(--dur-short) var(--ease-ops),
    border-color var(--dur-short) var(--ease-ops),
    color var(--dur-micro) var(--ease-ops),
    box-shadow var(--dur-short) var(--ease-ops),
    transform var(--dur-micro) var(--ease-ops);
}
.sim-step:hover {
  background: rgba(26, 53, 88, 0.45);
  color: var(--silver-bright);
  border-color: rgba(107, 163, 245, 0.25);
}
.sim-step:focus-visible {
  outline: 2px solid var(--cmd-blue-hi);
  outline-offset: 2px;
}
.sim-step-on {
  color: #fff;
  background: linear-gradient(180deg, rgba(30, 90, 168, 0.4), rgba(10, 30, 60, 0.6));
  border-color: rgba(107, 163, 245, 0.45);
  box-shadow: inset 0 2px 4px rgba(255, 255, 255, 0.1), 0 4px 12px rgba(30, 90, 168, 0.35);
}
.sim-step-on .sim-step-num {
  background: var(--silver-bright);
  color: var(--blue-void);
  box-shadow: 0 0 10px rgba(255,255,255,0.25);
}
.sim-step-done {
  color: #a7f3d0;
  border-color: rgba(45, 212, 160, 0.2);
  background: rgba(45, 212, 160, 0.05);
}
.sim-step-done .sim-step-num {
  background: rgba(45, 212, 160, 0.22);
  color: #2DD4A0;
}
.sim-step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 700;
  background: rgba(91, 141, 239, 0.18);
  color: var(--text-secondary);
  flex-shrink: 0;
}
.sim-step .q-icon {
  opacity: 0.85;
}
.sim-step-on .q-icon {
  color: var(--silver-primary);
  opacity: 1;
}
.sim-step-connector {
  display: none;
  width: 18px;
  align-self: center;
  height: 2px;
  margin: 0 2px;
  background: linear-gradient(90deg, rgba(197,206,217,0.15), rgba(197,206,217,0.35));
  border-radius: 2px;
  flex: 0 0 auto;
}
@media (min-width: 900px) {
  .sim-step-connector { display: block; }
  .sim-step { flex: 1 1 0; }
}

/* Quickstart / preset band */
.sim-quickstart {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 14px;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid rgba(197, 206, 217, 0.18);
  background:
    linear-gradient(135deg, rgba(30, 90, 168, 0.14) 0%, rgba(12, 26, 46, 0.9) 55%, rgba(19, 42, 69, 0.75) 100%);
  box-shadow: inset 3px 0 0 var(--silver-primary);
}
.sim-quickstart-title {
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 15px;
  letter-spacing: 0.02em;
  color: var(--silver-bright);
}
.sim-quickstart-hint {
  flex: 1 1 220px;
  font-size: 12px;
  line-height: 1.45;
  color: var(--muted);
  max-width: 42rem;
}
.sim-progress-strip {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 16px;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid rgba(91, 141, 239, 0.18);
  background: rgba(10, 22, 40, 0.65);
  margin-bottom: 4px;
}
.sim-progress-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
  font-family: var(--font);
}
.sim-progress-value {
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 18px;
  color: var(--silver-bright);
  font-variant-numeric: tabular-nums;
}
.sim-progress-bar {
  flex: 1 1 160px;
  min-width: 120px;
  height: 6px;
  border-radius: 999px;
  background: rgba(19, 42, 69, 0.9);
  overflow: hidden;
  border: 1px solid rgba(197, 206, 217, 0.12);
}
.sim-progress-bar > i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--blue-accent-hi), var(--silver-primary));
  transition: width 0.35s var(--ease-ops);
}

/* Lock / constraint rows */
.sim-lock-row {
  display: grid;
  grid-template-columns: minmax(180px, 220px) 1fr;
  gap: 12px 16px;
  align-items: start;
  padding: 18px 24px;
  margin-bottom: 12px;
  border-radius: var(--r);
  border: 1px solid rgba(197, 206, 217, 0.1);
  background: rgba(14, 30, 50, 0.45);
  backdrop-filter: blur(16px);
  transition: transform var(--dur-micro) var(--ease-ops), background var(--dur-micro) var(--ease-ops), box-shadow var(--dur-short) var(--ease-ops);
}
.sim-lock-row:hover {
  background: rgba(19, 42, 69, 0.65);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
  border-color: rgba(107, 163, 245, 0.25);
}
.sim-lock-row:last-child {
  border-bottom: 1px solid rgba(197, 206, 217, 0.1);
}
.sim-lock-row.sim-locked {
  background: rgba(45, 212, 160, 0.08);
  border-color: rgba(45, 212, 160, 0.35);
  box-shadow: inset 3px 0 0 rgba(45, 212, 160, 0.8), 0 0 16px rgba(45, 212, 160, 0.15);
}
.sim-lock-row .q-field--disabled,
.sim-field-disabled {
  opacity: 0.48;
}
.sim-footer-actions {
  position: sticky;
  bottom: 0;
  z-index: 4;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 4px 4px;
  margin-top: 8px;
  background: linear-gradient(180deg, transparent 0%, rgba(6, 13, 24, 0.92) 28%, rgba(6, 13, 24, 0.98) 100%);
}

/* Find-best decision hero */
.sim-hero {
  padding: 22px 24px 18px;
  border-radius: 14px;
  border: 1px solid rgba(197, 206, 217, 0.2);
  background:
    linear-gradient(165deg, rgba(26, 53, 88, 0.55) 0%, rgba(10, 22, 40, 0.95) 48%, rgba(6, 13, 24, 0.98) 100%);
  box-shadow:
    inset 3px 0 0 var(--silver-primary),
    0 12px 32px rgba(0, 0, 0, 0.28);
  margin-bottom: 12px;
}
.sim-hero-title {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.01em;
  color: var(--silver-bright);
  line-height: 1.2;
  margin: 0 0 6px;
}
.sim-hero-sub {
  margin: 0 0 14px;
  max-width: 52rem;
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-secondary);
}
.sim-lock-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 14px;
  min-height: 28px;
}
.sim-hero-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 10px;
}
.sim-hero-secondary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(91, 141, 239, 0.14);
}
.sim-tool-group {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 4px 8px 4px 4px;
  border-radius: 10px;
  border: 1px solid rgba(91, 141, 239, 0.12);
  background: rgba(6, 13, 24, 0.35);
}
.sim-tool-group-label {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--dim);
  padding: 0 4px 0 6px;
  font-family: var(--font);
}
.sim-search-status {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 14px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(91, 141, 239, 0.16);
  background: rgba(12, 26, 46, 0.72);
  margin-bottom: 10px;
  min-height: 44px;
}
.sim-search-status.is-running {
  border-color: rgba(91, 141, 239, 0.45);
  box-shadow: 0 0 0 1px rgba(91, 141, 239, 0.12), 0 0 20px rgba(30, 90, 168, 0.18);
  animation: sim-pulse-border 1.6s ease-in-out infinite;
}
@keyframes sim-pulse-border {
  0%, 100% { box-shadow: 0 0 0 1px rgba(91, 141, 239, 0.12), 0 0 12px rgba(30, 90, 168, 0.12); }
  50% { box-shadow: 0 0 0 1px rgba(197, 206, 217, 0.22), 0 0 22px rgba(91, 141, 239, 0.22); }
}
.sim-space-warn {
  width: 100%;
  padding: 12px 14px;
  border-radius: 10px;
  margin-bottom: 10px;
  border: 1px solid rgba(234, 179, 8, 0.35);
  background: rgba(12, 26, 46, 0.75);
  font-size: 0.88rem;
  line-height: 1.45;
  white-space: pre-wrap;
}
.sim-space-warn.risk-low { border-color: rgba(45,212,160,0.35); color: #A7F3D0; }
.sim-space-warn.risk-medium { border-color: rgba(234,179,8,0.35); color: #FDE68A; }
.sim-space-warn.risk-high { border-color: rgba(251,146,60,0.4); color: #FDBA74; }
.sim-space-warn.risk-extreme { border-color: rgba(248,113,113,0.45); color: #FCA5A5; }

/* Result panels & option cards */
.sim-result-panel {
  width: 100%;
  min-height: 5rem;
  max-height: 16rem;
  overflow: auto;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid rgba(91, 141, 239, 0.28);
  background: rgba(12, 26, 46, 0.92);
  color: #E8EDF4;
  font-size: 0.94rem;
  line-height: 1.5;
  white-space: pre-wrap;
  content-visibility: auto;
}
.sim-section-title {
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 15px;
  letter-spacing: 0.02em;
  color: var(--silver-bright);
  margin: 0 0 6px;
}
.sim-split {
  min-height: 320px;
  border-radius: 12px;
  border: 1px solid rgba(91, 141, 239, 0.16);
  background: rgba(10, 22, 40, 0.4);
  overflow: hidden;
}
.sim-split .q-splitter__separator {
  background: rgba(91, 141, 239, 0.2) !important;
}
.sim-split .q-splitter__before,
.sim-split .q-splitter__after {
  padding: 12px 14px;
}
.sim-option-card {
  position: relative;
  padding: 16px 20px;
  margin-bottom: 12px;
  border-radius: var(--r);
  border: 1px solid rgba(197, 206, 217, 0.1);
  background: linear-gradient(165deg, rgba(14, 30, 50, 0.7), rgba(8, 16, 28, 0.85));
  backdrop-filter: blur(12px);
  cursor: pointer;
  transition:
    border-color var(--dur-short) var(--ease-ops),
    background var(--dur-short) var(--ease-ops),
    box-shadow var(--dur-short) var(--ease-ops),
    transform var(--dur-micro) var(--ease-ops);
}
.sim-option-card:hover {
  border-color: rgba(107, 163, 245, 0.35);
  background: linear-gradient(165deg, rgba(19, 42, 69, 0.85), rgba(12, 26, 46, 0.95));
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
}
.sim-option-card:focus-visible {
  outline: 2px solid var(--cmd-blue-hi);
  outline-offset: 2px;
}
.sim-option-card.active {
  border-color: rgba(107, 163, 245, 0.5);
  background: linear-gradient(165deg, rgba(26, 53, 88, 0.95), rgba(13, 33, 55, 0.98));
  box-shadow: inset 3px 0 0 var(--cmd-blue-hi), 0 8px 24px rgba(0, 0, 0, 0.45);
}
.sim-option-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 8px;
  margin-bottom: 8px;
}
.sim-option-title {
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 15px;
  color: var(--silver-bright);
  margin-right: 4px;
}
.sim-option-rank {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 22px;
  padding: 0 6px;
  border-radius: 6px;
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 600;
  background: rgba(91, 141, 239, 0.2);
  color: #9ec0f5;
  font-variant-numeric: tabular-nums;
}
.sim-option-card.active .sim-option-rank {
  background: linear-gradient(180deg, var(--silver-bright), var(--silver-primary));
  color: var(--blue-void);
}
.sim-option-body {
  font-size: 12.5px;
  line-height: 1.45;
  color: var(--text-secondary);
  white-space: pre-wrap;
  max-height: 7.5rem;
  overflow: auto;
}
.sim-option-actions {
  opacity: 0.92;
}
.sim-option-card:hover .sim-option-actions,
.sim-option-card.active .sim-option-actions {
  opacity: 1;
}
.sim-adv {
  border: 1px solid rgba(91, 141, 239, 0.14) !important;
  border-radius: 10px !important;
  background: rgba(10, 22, 40, 0.45) !important;
  margin-bottom: 8px;
}
.sim-adv .q-item__label {
  color: var(--text-secondary) !important;
  font-size: 13px !important;
}

/* Manual grid cells */
.sim-grid-host {
  width: 100%;
  min-height: 8rem;
  max-height: 22rem;
  overflow: auto;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid rgba(91, 141, 239, 0.28);
  background: rgba(12, 26, 46, 0.92);
}
.sim-grid-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  margin-bottom: 4px;
}
.sim-grid-label {
  width: 2.25rem;
  font-size: 11px;
  font-family: var(--mono);
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}
.sim-cell-btn,
.q-btn.sim-cell-btn {
  min-width: 3.4rem !important;
  padding: 2px 6px !important;
  font-family: var(--mono) !important;
  font-size: 11px !important;
  font-variant-numeric: tabular-nums;
  border-radius: 6px !important;
}
.sim-cell-on {
  border-color: rgba(91, 141, 239, 0.55) !important;
  background: rgba(30, 90, 168, 0.22) !important;
  color: #cfe0ff !important;
}
.sim-cell-off {
  border-color: rgba(122, 143, 168, 0.28) !important;
  color: var(--dim) !important;
  opacity: 0.85;
}
.sim-publish-hero {
  padding: 16px 18px;
  border-radius: 12px;
  border: 1px solid rgba(197, 206, 217, 0.18);
  background: linear-gradient(135deg, rgba(30, 90, 168, 0.12), rgba(12, 26, 46, 0.9));
  box-shadow: inset 3px 0 0 var(--silver-primary);
  margin-bottom: 12px;
}
.sim-publish-hero .sim-section-title { margin-bottom: 4px; }
.sim-micro {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--dim);
  font-family: var(--font);
}
.sim-ng-chip-on { font-weight: 600; }
.sim-ng-chip-free { opacity: 0.92; }

@media (max-width: 720px) {
  .sim-lock-row {
    grid-template-columns: 1fr;
    gap: 6px;
  }
  .sim-hero { padding: 16px; }
  .sim-hero-title { font-size: 18px; }
  .sim-step { flex: 1 1 46%; min-height: 48px; padding: 8px 10px; }
}
@media (prefers-reduced-motion: reduce) {
  .sim-search-status.is-running { animation: none; }
  .sim-option-card,
  .sim-step,
  .sim-progress-bar > i { transition: none; }
}
"""
