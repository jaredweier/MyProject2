# Zero / Minimal Agent Usage — Cursor & Grok

> **Superseded for routing policy by [`AGENT_ROUTING.md`](AGENT_ROUTING.md)** — auto-context is OFF; any agent/LLM is allowed. This doc remains optional budget tips.

How to **reduce** billed Agent/API usage while keeping the same quality on Dodgeville PD Scheduler.

## The 80/20 rule

**~80% of verification never needs an LLM.** This repo ships free local gates. Run them yourself (or via CI/pre-commit) so agents only edit code—not re-discover the project every turn.

## Tier 0: Zero Agent (you only)

| Action | Command | Billed? |
|--------|---------|---------|
| Fast smoke | `python dev.py cheap-check` | No |
| Commit gate | `pre-commit run` (preflight) | No |
| Full tests | `python dev.py check` | No |
| UI static | `python dev.py ui-review` | No |
| UI pixels | `python dev.py ui-diff --quick` | No |
| Remote CI | GitHub Actions on push | No |
| Typos / small edits | Cursor **Tab** | No (Pro) |
| Questions | Cursor **Ask** / Grok Ask | Lower than Agent |

**Workflow:** edit → `cheap-check` → commit. Only open Agent when implementing a feature or fixing a failed gate you cannot solve manually.

## Tier 1: Minimal Agent (scoped)

When you need Agent:

1. `python dev.py usage-brief day-off-requests` (or your slice)
2. Paste the brief into chat — **do not** ask "read the whole project"
3. Cursor: `/slice-fix day-off-requests` or Grok: cite slice id + symptom
4. Agent edits only `touch_together` files
5. You run `python dev.py verify-slice <id>` yourself before asking agent to continue

## Tier 2: Agent verify (last resort)

Only if Tier 0–1 failed:

```bash
python dev.py preflight
python dev.py check
python dev.py fix-hint   # free diagnosis
```

Then one Agent turn with the `fix-hint` output—not a multi-turn explore loop.

## Tier 3: Vision (expensive)

```
ui-review → ui-diff --quick → ui-diff (full) → ui-observe → ui-observe --live
```

Never skip to `--live`. Share **one** failed diff PNG, not 78 baselines.

---

## Cursor-specific (2026)

From [Cursor agent best practices](https://cursor.com/blog/agent-best-practices) and community billing guides:

| Tip | Why |
|-----|-----|
| **Auto model** | Routes to cheaper models for simple tasks (~10% discount) |
| **Ask vs Agent** | Ask for explanations; Agent only for multi-file edits |
| **Tab completion** | Unlimited on Pro—use for comments, boilerplate, renames |
| **Lean rules** | `.cursor/rules/token-minimization.mdc` is opt-in (`alwaysApply: false`) — long always-on rules tax every request |
| **New chat per task** | Long threads accumulate tokens via summarization |
| `@Past Chats` | Pull selective context instead of re-pasting |
| **Plan mode** (`Shift+Tab`) | Approve plan once—avoids wrong-direction Agent loops |
| `.cursorignore` | Excludes logs, dist, 78 PNG baselines from indexing |
| **Spending limit** | Set in Cursor Settings → avoid runaway Agent loops |
| **Slash commands** | `/preflight`, `/check-free`, `/usage-brief`, `/slice-fix` |

## Grok-specific

| Tip | Why |
|-----|-----|
| Load `cost-efficient-workflow` skill | Agents default to free gates |
| `session-start` / `usage-brief` | Replaces exploratory repo reads |
| One slice per session | Limits `touch_together` file reads |
| No subagents for QA | `cheap-check` + `preflight` are terminal-only |
| OpenCode `/check` | Free Python gates, not vision loops |

## OpenCode

`opencode.json` sets `compaction.prune`, image resize limits, and watcher ignores. Commands `/check` and `/ui-observe` (static) avoid PNG capture by default.

## In-repo artifacts

| Path | Role |
|------|------|
| `.cursor/rules/token-minimization.mdc` | Opt-in Cursor rules (@ mention) |
| `.cursor/commands/*.md` | Free slash workflows (`/preflight`, `/usage-brief`, …) |
| `.cursorignore` | Smaller index = fewer tokens (excludes 30MB code dump) |
| `.grok/rules/token-minimization.md` | Grok agent rules |
| `python dev.py token-audit` | Verify all minimization artifacts |
| `.grok/skills/cost-efficient-workflow/` | Skill for all agents |
| `python dev.py cheap-check` | ~5s free gate |
| `python dev.py usage-brief` | Scoped context printer |
| `python dev.py fix-hint` | Free failure diagnosis |

## GitHub CI = free Agent substitute

```powershell
.\scripts\setup_github.ps1 -RepoUrl "https://github.com/YOU/REPO.git"
git push
```

CI runs doctor, preflight, check, ui-smoke—no Cursor/Grok credits.

## Quick daily habit

```bash
python dev.py session-start          # once per session (free)
python dev.py cheap-check            # after each edit (free)
python dev.py usage-brief <slice>    # before Agent (free)
# Agent: one scoped task
python dev.py verify-slice <slice>   # you run (free)
python dev.py check                  # handoff only (free)
```

See also: [`USAGE_MINIMIZATION.md`](USAGE_MINIMIZATION.md)
