"""One-shot: map theme.py + chronos.css to DESIGN.md Deep Chrome tokens."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / "gui" / "theme.py"
CSS = ROOT / "gui" / "static" / "chronos.css"

OLD_ROOT = """/* System fonts only — Google Fonts CDN was adding multi-second first paint on many networks */
:root {
  --bg: #05060b;
  --bg-deep: #03040a;
  --glass: rgba(14, 18, 32, 0.72);
  --glass-2: rgba(20, 26, 44, 0.85);
  --surface: #0e1422;
  --surface-2: #141b2e;
  --surface-3: #1a2340;
  --border: rgba(120, 160, 220, 0.12);
  --border-hi: rgba(100, 200, 255, 0.28);
  --text: #f0f4fc;
  --muted: #9aabc4;
  --dim: #5e6f8a;
  --cyan: #22d3ee;
  --cyan-dim: rgba(34, 211, 238, 0.15);
  --violet: #8b5cf6;
  --violet-dim: rgba(139, 92, 246, 0.18);
  --blue: #3b82f6;
  --gold: #eab308;
  --success: #22c55e;
  --warning: #f59e0b;
  --danger: #ef4444;
  --font: system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  --mono: ui-monospace, 'Cascadia Mono', Consolas, 'Courier New', monospace;
  --r: 16px;
  --r-sm: 12px;
  --shadow: 0 0 0 1px rgba(255,255,255,0.04), 0 24px 60px rgba(0,0,0,0.55);
  --glow-cyan: 0 0 40px rgba(34, 211, 238, 0.12);
  --glow-violet: 0 0 50px rgba(139, 92, 246, 0.1);
}"""

NEW_ROOT = """/* Blue Watch Deep Chrome — DESIGN.md (offline system fonts) */
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
  --font: 'Segoe UI', system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif;
  --font-display: 'Segoe UI', system-ui, sans-serif;
  --mono: ui-monospace, 'Cascadia Mono', Consolas, 'Courier New', monospace;
  --r: 10px;
  --r-sm: 6px;
  --shadow: 0 0 0 1px rgba(255,255,255,0.04), 0 16px 40px rgba(0,0,0,0.45);
  --glow-cyan: 0 0 28px var(--silver-glow);
  --glow-violet: 0 0 24px rgba(30, 90, 168, 0.15);
}"""


def main() -> int:
    t = THEME.read_text(encoding="utf-8")
    if "--blue-void" in t and "Deep Chrome" in t[:200]:
        print("theme already Deep Chrome-ish; still re-syncing CSS")
    else:
        if OLD_ROOT not in t:
            # maybe partial apply
            if ":root {" not in t:
                print("FATAL: no :root in theme")
                return 1
            print("WARN: exact old root missing — applying bulk hex swaps only")
        else:
            t = t.replace(OLD_ROOT, NEW_ROOT)
            t = t.replace(
                '"""Visual system — Option 1 SaaS glass + Option 2 SOC density + LE branding.\n\n'
                "Target: SHIFTVOID / PULSE COMMAND mockups — not flat Quasar / legacy CTk.\n"
                '"""',
                '"""Visual system — Blue Watch Deep Chrome (DESIGN.md B + D rail).\n\n'
                "Police navy chrome, silver CTAs — no violet glass.\n"
                '"""',
            )

    body_old = """body {
  background:
    radial-gradient(ellipse 80% 50% at 0% -10%, rgba(34, 211, 238, 0.14), transparent 55%),
    radial-gradient(ellipse 70% 45% at 100% 0%, rgba(139, 92, 246, 0.16), transparent 50%),
    radial-gradient(ellipse 50% 40% at 50% 100%, rgba(59, 130, 246, 0.06), transparent 50%),
    linear-gradient(180deg, #070812 0%, #05060b 40%, #03040a 100%) !important;"""
    body_new = """body {
  background:
    radial-gradient(ellipse 70% 40% at 0% 0%, rgba(30, 90, 168, 0.12), transparent 55%),
    radial-gradient(ellipse 50% 35% at 100% 0%, rgba(197, 206, 217, 0.06), transparent 50%),
    linear-gradient(180deg, var(--blue-chrome-deep) 0%, var(--blue-void) 45%, #061018 100%) !important;"""
    if body_old in t:
        t = t.replace(body_old, body_new)

    for a, b in (
        ("#22d3ee", "#C5CED9"),
        ("#6366f1", "#1E5AA8"),
        ("#8b5cf6", "#1E5AA8"),
        ("#a5f3fc", "#E8EDF4"),
        ("#67e8f9", "#C5CED9"),
        ("#a78bfa", "#8B95A5"),
        ("#c4b5fd", "#9AABC4"),
        ("#041016", "#060D18"),
        ("rgba(34, 211, 238,", "rgba(197, 206, 217,"),
        ("rgba(139, 92, 246,", "rgba(30, 90, 168,"),
        ("rgba(99, 102, 241,", "rgba(30, 90, 168,"),
        ("#4c1d95", "#0A1A2E"),
    ):
        t = t.replace(a, b)

    # Silver primary CTA
    t = re.sub(
        r"\.btn-primary \{[^}]+\}",
        ".btn-primary {\n"
        "  background: linear-gradient(180deg, var(--silver-bright), var(--silver-primary)) !important;\n"
        "  color: var(--blue-void) !important;\n"
        "  box-shadow: 0 4px 16px var(--silver-glow) !important;\n"
        "  border: 1px solid rgba(197, 206, 217, 0.35) !important;\n"
        "}",
        t,
        count=1,
    )

    # Sidebar solid chrome (drop heavy glass blur if present)
    t = t.replace(
        "background: linear-gradient(180deg, rgba(12, 16, 30, 0.92), rgba(6, 8, 16, 0.96));",
        "background: linear-gradient(180deg, var(--blue-chrome-deep) 0%, #061018 100%);",
    )
    t = t.replace(
        "backdrop-filter: blur(24px) saturate(1.3);\n  -webkit-backdrop-filter: blur(24px) saturate(1.3);\n  ",
        "",
    )

    # Active nav: silver inset bar only
    t = re.sub(
        r"\.nav-link\.active \{[^}]+\}",
        ".nav-link.active {\n"
        "  background: rgba(197, 206, 217, 0.08);\n"
        "  color: var(--text) !important;\n"
        "  border-color: rgba(197, 206, 217, 0.18);\n"
        "  box-shadow: inset 3px 0 0 var(--silver-primary);\n"
        "}",
        t,
        count=1,
    )

    if "font-family: var(--font-display)" not in t:
        t = t.replace(".page-title {", ".page-title {\n  font-family: var(--font-display);", 1)

    # Ensure root tokens present even if OLD_ROOT missed
    if "--blue-void" not in t:
        t = t.replace(":root {", NEW_ROOT.split(":root {", 1)[0] + ":root {", 1)
        # inject after :root {
        t = t.replace(
            ":root {\n  --bg:",
            ":root {\n  --blue-void: #060D18;\n  --blue-chrome-deep: #0A1A2E;\n"
            "  --blue-chrome: #0D2137;\n  --blue-surface: #132A45;\n"
            "  --blue-elevated: #1A3558;\n  --blue-accent-hi: #1E5AA8;\n"
            "  --silver-bright: #E8EDF4;\n  --silver-primary: #C5CED9;\n"
            "  --silver-dim: #8B95A5;\n  --silver-glow: rgba(197, 206, 217, 0.18);\n  --bg:",
            1,
        )

    THEME.write_text(t, encoding="utf-8")
    m = re.search(r"GLOBAL_CSS = r\"\"\"(.*?)\"\"\"", t, re.S)
    if not m:
        print("FATAL: GLOBAL_CSS extract failed")
        return 1
    CSS.parent.mkdir(parents=True, exist_ok=True)
    CSS.write_text(m.group(1), encoding="utf-8")
    css_txt = CSS.read_text(encoding="utf-8")
    print("ok theme", THEME.stat().st_size, "css", CSS.stat().st_size)
    print("blue-void", "--blue-void" in css_txt)
    print("old_cyan_hex", "#22d3ee" in css_txt.lower() or "#22D3EE" in css_txt)
    print("old_violet", "#8b5cf6" in css_txt.lower() or "#8B5CF6" in css_txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
