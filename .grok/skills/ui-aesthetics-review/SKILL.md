---
name: ui-aesthetics-review
description: >
  Review Dodgeville PD Scheduler GUI for visual polish, theme consistency,
  spelling errors, and awkward wording. Run dev.py ui-review, read reports
  in logs/ui_review/, optionally pair with ui-live screenshots, and apply fixes
  in ui/*.py and ui/theme.py.
---

# UI Aesthetics Review Agent

## When to use

- User asks to improve GUI look and feel, copy, or spelling
- Before a demo, evaluation build, or department rollout
- After large UI changes — verify consistency across tabs

## Quick start

```bash
python dev.py ui-review              # static scan → logs/ui_review/<timestamp>/
python dev.py ui-review -v           # print every finding
python dev.py ui-live --delay 0.25   # optional visual pass + screenshots
python dev.py ui-review              # re-check after fixes
python dev.py check                  # full regression gate
```

Optional fuller spelling: `pip install pyspellchecker`

## What the tool checks

| Category | Examples |
|----------|----------|
| **Spelling** | Common typos; unknown words (with pyspellchecker) |
| **Wording** | Double spaces, filler phrases, mixed terminology (Time-Off vs Requests) |
| **Aesthetics** | Hardcoded hex colors, button height/radius variance, raw `CTkFont()` |

## Agent workflow

1. **Run review** — `python dev.py ui-review -v`
2. **Read report** — `logs/ui_review/<latest>/report.md` and `report.json`
3. **Visual pass** (recommended) — open latest `logs/ui_live_test/<run>/` PNGs
4. **Fix by priority**
   - `error` spelling → fix immediately
   - `warn` wording mismatches (nav vs profile shortcuts, inconsistent labels)
   - `info` aesthetics → align colors to `config`/`theme`, standardize button sizes
5. **Re-run** — `python dev.py ui-review --strict` until 0 errors/warnings
6. **Verify** — `python dev.py ui-exhaustive` and `python dev.py check`

## Fix guidelines

- **Colors**: use `DODGEVILLE_*`, `UI_*` from `config.py`; Gantt uses `GANTT_COLORS`
- **Fonts**: `font("body")`, `font("heading")` from `ui/theme.py` — not raw `CTkFont`
- **Buttons**: primary actions `height=36–38`, table row actions `height=28–32`, `corner_radius=8` toolbars / `CORNER_RADIUS` cards
- **Copy**: match `NAV_ITEMS` labels in profile shortcuts and dialogs; professional police-department tone
- **Whitelist**: add legitimate domain terms to `scripts/data/ui_review_whitelist.txt`

## Scope boundaries

- **Do** edit `ui/*.py`, `ui/theme.py`, whitelist file
- **Do not** change scheduling logic, validators, or SQL for aesthetics-only work
- **Do not** weaken permission messages for brevity

## Delegation

| Finding type | Skill |
|--------------|-------|
| Theme/layout/widgets | `ui-development` |
| Review tooling itself | `cli-operations` |
| Cross-cutting | `dodgeville-scheduler` |
