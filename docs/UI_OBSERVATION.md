# UI Observation Guide

How agents and developers **observe** the Dodgeville PD Scheduler GUI, **recommend** improvements, and **verify** fixes.

## One-command capture

```bash
python dev.py ui-observe              # fast: smoke + static review
python dev.py ui-observe --live       # + screenshots (watch your screen)
python dev.py ui-observe -v           # verbose findings
```

Output: `logs/ui_observe/<timestamp>/`
- `observation_brief.md` — agent handoff summary
- `manifest.json` — paths to PNGs and review reports

## Tool map

| Tool | Observes | Output |
|------|----------|--------|
| `ui-observe` | Orchestrates below | `logs/ui_observe/` |
| `ui-live` | Visual (every tab/step) | `logs/ui_live_test/<run>/*.png` |
| `ui-review` | Static copy/theme/code | `logs/ui_review/<run>/report.md` |
| `ui-smoke` | Runtime (14 pages, headless) | stdout |
| `ui-exhaustive` | All handlers (~78 steps) | optional PNGs |
| `main.py` | Human eye | — |

## Agent skills

| Skill | Role |
|-------|------|
| `.grok/skills/ui-vision-review/SKILL.md` | Read PNGs + reports → recommend → fix |
| `.grok/skills/ui-aesthetics-review/SKILL.md` | Static spelling/theme scan |
| `.grok/skills/ui-development/SKILL.md` | Implement layout and wiring |

## Typical session

1. `python dev.py ui-observe --live`
2. Agent reads `observation_brief.md` and PNGs
3. Agent applies fixes per vision-review skill
4. `python dev.py ui-observe` until clean
5. `python dev.py check`

## Visual regression

```bash
python dev.py ui-live
python dev.py ui-diff --update-baseline   # first time
python dev.py ui-diff                     # after changes
```

## OpenCode & GitHub

See [`OPEN_SOURCE_TOOLING.md`](OPEN_SOURCE_TOOLING.md) — OpenCode agents/commands, pre-commit, GitHub Actions, Pillow diff.

## Whitelist

Add police/scheduling terms to `scripts/data/ui_review_whitelist.txt` to reduce spell-check noise.
