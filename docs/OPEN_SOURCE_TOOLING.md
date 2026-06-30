# Open Source & GitHub Tooling

How external OSS tools complement Cursor/Grok agents, skills, and `dev.py` for this project.

## In-repo agent stack (already wired)

| Tool | Purpose |
|------|---------|
| `AGENTS.md` + `.grok/skills/` | Cursor/Grok skills and rules |
| `python dev.py ui-observe` | Observation bundle for vision agents |
| `python dev.py ui-diff` | Pillow visual regression vs baselines |
| `python dev.py preflight` / `check` | Fast and full verification |

## OpenCode ([anomalyco/opencode](https://github.com/anomalyco/opencode))

Open-source terminal/desktop coding agent. Reads this repo via:

| File | Role |
|------|------|
| `opencode.json` | Project config, `instructions` → AGENTS.md + UI docs |
| `.opencode/agents/ui-vision-reviewer.md` | Subagent for UI screenshot review |
| `.opencode/commands/ui-observe.md` | `/ui-observe` custom command |
| `.opencode/commands/check.md` | `/check` verification command |
| `.opencode/skills/ui-vision-review.md` | Skill mirror for OpenCode |

**Setup (Windows):**

```bash
npm install -g opencode-ai
# or: scoop install opencode
cd C:\Users\Windows\MyProject
opencode
# /ui-observe  or  /check
```

Drag `logs/ui_live_test/*.png` into OpenCode for vision review.

## pre-commit ([pre-commit/pre-commit](https://github.com/pre-commit/pre-commit))

```bash
pip install pre-commit
pre-commit install
```

Runs `python dev.py preflight` on every commit (see `.pre-commit-config.yaml`).

Alternative installer: `python scripts/install_pre_commit.py` (simple git hook only).

## GitHub Actions

`.github/workflows/ci.yml` runs on push/PR:

- `doctor`, `preflight`, `check`, `ui-smoke`, `ui-review`, `scenarios`

Push to GitHub to enable remote CI (optional if working locally only).

## Visual regression (Pillow — no extra deps)

```bash
python dev.py ui-live
python dev.py ui-diff --update-baseline   # seed baselines once
# after UI changes:
python dev.py ui-diff
```

Baselines: `tests/ui_snapshots/baseline/`
Diff images: `logs/ui_live_test/<run>/diff/`

## Dev dependencies (`requirements-dev.txt`)

Install once:

```bash
pip install -r requirements-dev.txt
```

| Package | Command | Use |
|---------|---------|-----|
| `ruff` | `python dev.py lint` | Fast Python lint/format (also in pre-commit on staged files) |
| `pyspellchecker` | `python dev.py ui-review` | Fuller UI spelling checks (auto-detected when installed) |
| `pip-audit` | `python dev.py deps-audit` | PyPI advisory DB scan for `requirements.txt` |
| `pre-commit` | `pre-commit install` | Full hook stack (auto via startup gates when installed) |
| `codespell` | pre-commit hook | Docs/markdown typo scan |

Pre-commit hooks (when `pre-commit` is installed): trailing whitespace, YAML, **ruff**, **codespell** (docs only), **preflight**.

Dependabot: `.github/dependabot.yml` — weekly pip + monthly GitHub Actions updates when pushed to GitHub.

## Usage minimization (zero Agent usage)

See [`docs/ZERO_AGENT_USAGE.md`](ZERO_AGENT_USAGE.md), [`docs/USAGE_MINIMIZATION.md`](USAGE_MINIMIZATION.md), `.cursor/rules/token-minimization.mdc`, and `.grok/skills/cost-efficient-workflow/SKILL.md`. Audit: `python dev.py token-audit`.

Free commands: `cheap-check`, `lint`, `deps-audit`, `usage-brief`, `fix-hint`, `preflight`, `check`, CI on push.

Cheapest UI path: `ui-review` → `ui-diff --quick` → `ui-diff` (full) → `ui-observe` → `ui-observe --live`.

## Recommended multi-agent workflow

1. **Cursor/Grok** — primary IDE agent with `.grok/skills/`
2. **OpenCode** — terminal agent with `/check` (free) or `/ui-observe` (static)
3. **GitHub Actions** — CI on push (no LLM)
4. **pre-commit** — local fast gate before commit

```bash
python dev.py preflight
python dev.py ui-diff --quick
python dev.py check
# vision only when needed:
python dev.py ui-observe --live
```
