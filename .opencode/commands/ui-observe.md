---
description: Capture UI observation bundle (smoke + static review + agent brief)
agent: build
---

Run the Dodgeville PD Scheduler UI observation pipeline and summarize findings.

1. Execute: `python dev.py ui-observe` (use `python dev.py ui-observe --live` only if a GUI display is available).
2. Read the latest `logs/ui_observe/*/observation_brief.md` and `manifest.json`.
3. If screenshots exist, review key PNGs (login, dashboard, monthly schedules, roster, timecard).
4. List prioritized recommendations: P0 broken layout, P1 theme/copy, P2 polish.
5. Ask before applying fixes unless the user said to fix immediately.
