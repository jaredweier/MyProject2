---
name: qa-verify
description: >
  Dodgeville PD verification and regression workflow — dev.py gates, audit,
  scenarios, UI smoke/exhaustive, slice verify. Use after any change or when
  asked to verify, check work, or confirm nothing broke.
---

# QA / Verify Subagent

**Load `.grok/skills/cost-efficient-workflow/SKILL.md` first.** Do not use a subagent for gates below—run terminal commands (free).

## Verification ladder (fast → thorough)

| Step | Command | When |
|------|---------|------|
| 0 | `python dev.py cheap-check` | Every edit — ~5s |
| 1 | `python dev.py preflight` | Before commit — ~15s |
| 2 | `python dev.py verify-slice <id>` | After touching one slice |
| 3 | `python dev.py check` | Before marking work done — ~70s |
| 4 | `python dev.py verify-features` | Release / large UI change |

## Slice-targeted verify

```bash
python dev.py slice-map -v              # find slice id
python dev.py verify-slice payroll-timecard
python dev.py verify-slice day-off-requests
```

Runs only the `verify` commands listed in `slices/registry.py` for that slice.

## Regression sources

- `audit.py` — 10 AUD-* checks (`python dev.py audit`)
- `scripts/scenarios.py` — S-01..S-11 (`python dev.py scenarios`)
- `tests/test_regressions.py` — bug-specific unit tests
- `tests/test_permissions.py` — role matrix

## UI verification

```bash
python dev.py ui-smoke          # headless, all pages
python dev.py ui-functional     # handler exercise on test DB
python dev.py ui-exhaustive     # full tab coverage
python dev.py ui-review         # spelling, wording, theme
python dev.py ui-live           # visible screenshots (optional)
```

## Workflow after a fix

1. Reproduce failure with smallest command (unittest or `dev.py audit`)
2. Fix in correct layer (validators → logic → UI)
3. Add regression test or audit entry if user-reported
4. `python dev.py preflight`
5. `python dev.py verify-slice <id>` if slice known
6. `python dev.py check`

## Do not

- Mark complete on `imports` alone
- Skip `audit` after scheduling logic changes
- Run `ui-exhaustive` for typo-only fixes (use `ui-review` or `check`)
