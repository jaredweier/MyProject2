# Usage Minimization — Dodgeville PD Scheduler

How to get the same quality with **less LLM/API spend** (Cursor, Grok, OpenCode, vision models).

**Master guide (zero Agent usage):** [`ZERO_AGENT_USAGE.md`](ZERO_AGENT_USAGE.md)
**Research findings + agent ladder (2026-07-09):** [`TOKEN_PERFORMANCE.md`](TOKEN_PERFORMANCE.md) — **agents: read this**
**Session prompt:** [`NEXT_AGENT_PROMPT.md`](NEXT_AGENT_PROMPT.md)

## Free tools already in the repo

| Tool | What it does | LLM cost |
|------|----------------|----------|
| `python dev.py cheap-check` | imports + audit (~5s) | **$0** |
| `python dev.py usage-brief <id>` | scoped touch_together + verify | **$0** |
| `python dev.py fix-hint` | free failure diagnosis | **$0** |
| `python dev.py preflight` | imports, slice-check, audit | **$0** |
| `python dev.py verify-slice <id>` | One feature's tests | **$0** |
| `python dev.py check` | Full suite + audit | **$0** |
| `python dev.py ui-smoke` | Headless all pages | **$0** |
| `python dev.py ui-review` | Spelling, wording, theme scan | **$0** |
| `python dev.py ui-diff --quick` | 15 nav/login PNGs vs baseline | **$0** |
| `python dev.py ui-diff` | 78 PNG visual regression | **$0** |
| pre-commit hook | preflight on every commit | **$0** |
| GitHub Actions CI | Same gates on push | **$0** |

Run these yourself (or let CI run them) **before** asking an agent to debug.

## Recommended workflow

### Small fix (one slice)

```bash
python dev.py slice-map -v          # find slice id
# edit touch_together files only
python dev.py verify-slice <id>
python dev.py preflight
```

### UI copy / theme tweak

```bash
python dev.py ui-review
python dev.py preflight
```

### UI layout change

```bash
python dev.py ui-smoke
python dev.py ui-diff --quick       # fast nav check
python dev.py ui-diff               # before release only
```

### Agent session (Cursor / Grok)

1. Start: `python dev.py session-start` (reads HANDOFF + doctor — no LLM).
2. Tell the agent the **slice id** and symptom.
3. Ask it to run **preflight** before **check**.
4. Use **Ask mode** for questions; Agent mode for edits.
5. Point agents at `docs/HANDOFF.md`, not whole-repo dumps.

### Vision / screenshots (expensive)

Only when static tools are insufficient:

```bash
python dev.py ui-observe              # smoke + review text (no PNG capture)
python dev.py ui-observe --live       # + screenshots — use sparingly
```

Share **failed** images from `logs/ui_live_test/<run>/diff/`, not all 78 baselines.

## OpenCode cost settings

`opencode.json` includes:

- `compaction.prune: true` — drop old tool output from context
- `small_model` — cheaper model for titles/light tasks (set your provider's haiku/flash tier)
- `attachment.image` limits — resize before vision requests
- `watcher.ignore` — skip logs, dist, db

Install: `.\scripts\install_opencode.ps1` (or GitHub release binary).

## GitHub CI (free verification)

```powershell
.\scripts\setup_github.ps1 -RepoUrl "https://github.com/YOU/REPO.git"
git add -A
git commit -m "chore: tooling and baselines"
git push -u origin master
```

CI runs tests without consuming Cursor/OpenCode credits.

## What costs money

| Action | Why |
|--------|-----|
| Long agent threads with full file reads | Input tokens |
| `ui-observe --live` + vision analysis | Image + context tokens |
| Re-running agent after avoidable test failure | Retry loops |
| Subagents for verify-only work | Duplicate context |
| Reading 78 PNGs into chat | Vision pricing |

## Agent skill

Cursor/Grok agents should load `.grok/skills/cost-efficient-workflow/SKILL.md` when minimizing usage.

## Quick reference

```bash
python dev.py preflight                    # always first
python dev.py verify-slice day-off-requests
python dev.py ui-diff --quick
python dev.py check                        # before done
pre-commit run --all-files                 # optional local hook dry-run
```
