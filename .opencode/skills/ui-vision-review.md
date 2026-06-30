# UI Vision Review

Mirror of `.grok/skills/ui-vision-review/SKILL.md` for OpenCode.

## Capture

```bash
python dev.py ui-observe --live
python dev.py ui-diff --update-baseline   # first time only
python dev.py ui-diff                     # after UI changes
```

## Observe

Read `logs/ui_observe/<latest>/observation_brief.md`, PNGs, and `ui-review` report.

Drag PNGs into OpenCode for vision analysis (layout, contrast, LE theme).

## Fix

`ui/*.py`, `ui/theme.py` — no scheduling logic changes for visual-only work.

## Verify

`python dev.py ui-observe && python dev.py check`
