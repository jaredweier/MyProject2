# UI Agents Catalog — Chronos / Dodgeville

**Purpose:** Route UI work to a capable agent/tool; **sources are OPEN** (any public web/GitHub/product UX).
**Router:** `python dev.py route-task "<task>"`
**UI domain tool:** `python dev.py ui-domain explore|brainstorm|research-queries|learn`
**OSS loop:** find **anywhere public** → **implement** in `gui/*` → deposit URL via catalog or `ui-domain learn`
**Last researched:** 2026-07-09

Curated tables below are **starters**, not the only allowed tools or sites.

---

## Routing rule (advisory cost, open research)

```
complexity → cost_tier → agent chain (cheapest first for cost)
research → ANY public source (not limited to this catalog)
```

| Complexity | Cost | Default agents (first wins if enough) |
|------------|------|----------------------------------------|
| **verify** | free | `dev.py verify` · OpenCode `qa-free` |
| **trivial** | free | Cursor Tab · `ui-review` |
| **low** (explain/copy) | cheap | Ask + mini · aider · Continue.dev · `ui-static-reviewer` |
| **medium** | balanced | Cursor Agent · OpenCode primary · skill `ui-development` · Cline |
| **high** | flagship | Plan→Agent · Opus/reasoning · + qa-verify |
| **vision** | vision | `ui-review` first → ui-vision skill → OpenCode vision → OmniParser → browser-use |
| **browser** | vision | Playwright scripts → Stagehand → browser-use → Skyvern |

**Never skip free static UI gates for “looks wrong” until they fail.**

---

## In-repo agents & tools

| ID | Cost | Invoke | Best for |
|----|------|--------|----------|
| terminal-verify | free | `python dev.py verify --tier *` | tests, audit, imports |
| ui-static-free | free | `ui-review`, `ui-diff --quick` | spelling, theme, nav pixels |
| skill-ui-aesthetics | cheap | `.grok/skills/ui-aesthetics-review` | Title Case, copy, theme tokens |
| skill-ui-dev | balanced | `.grok/skills/ui-development` | tabs, widgets, Chronos pages |
| skill-ui-vision | vision | `.grok/skills/ui-vision-review` | screenshot QA |
| opencode-qa-free | free | `.opencode/agents/qa-free.md` | gate-only |
| opencode-ui-static | cheap | `.opencode/agents/ui-static-reviewer.md` | copy/theme without PNG |
| opencode-ui-chronos | balanced | `.opencode/agents/ui-chronos.md` | NiceGUI `gui/*` |
| opencode-ui-vision | vision | `.opencode/agents/ui-vision-reviewer.md` | live observe + PNG |
| opencode-local-cheap | free | `.opencode/agents/local-cheap.md` | machine-first token save |
| opencode-scheduling-math | balanced | `.opencode/agents/scheduling-math.md` | bumps/CP-SAT scenarios |
| local-dispatch | free | `python dev.py local-dispatch` | map task → $0 machine cmds |
| chronos-e2e | free* | `python dev.py chronos-e2e` | Playwright Chronos (*optional install) |
| math-scenarios | free | `python dev.py math-scenarios` | local CPU math stress |
| cursor-tab / ask / agent | free→flagship | Cursor modes | per complexity |

---

## External UI / browser agents (GitHub / OSS)

Use when in-repo tools are insufficient. Prefer **scripted** over **vision** when paths are known.

| Agent | URL | Cost class | When to route here |
|-------|-----|------------|--------------------|
| **Playwright** | https://github.com/microsoft/playwright | cheap | Repeatable Chronos E2E (login→tab→assert); first browser choice |
| **browser-use** | https://github.com/browser-use/browser-use | vision | LLM-driven browser for exploratory live UI on `:8080` |
| **browser-use web-ui** | https://github.com/browser-use/web-ui | vision | Gradio front-end for browser-use |
| **Skyvern** | https://github.com/Skyvern-AI/skyvern | vision | Complex multi-page flows; planner–actor–validator |
| **Stagehand** | https://github.com/browserbase/stagehand | balanced | AI-assisted browser scripts (often cheaper than full vision agent) |
| **UI-TARS** | https://github.com/bytedance/UI-TARS | vision | Native/desktop GUI (pywebview Chronos) |
| **OmniParser** | https://microsoft.github.io/OmniParser/ | vision | Parse screenshot → elements → cheap LLM (cuts vision tokens) |
| **Cline** | https://github.com/cline/cline | balanced | VS Code agent with permission gates |
| **Aider** | https://github.com/Aider-AI/aider | cheap | Terminal multi-file edits with cheap models |
| **Continue.dev** | https://github.com/continuedev/continue | cheap | IDE chat + local/cheap models |
| **OpenCode** | https://github.com/anomalyco/opencode | varies | Multi-provider BYOK; `small_model` for light steps |
| **awesome-web-agents** | https://github.com/steel-dev/awesome-web-agents | ref | Index of more web agents |
| **awesome-ai-agents-2026** | https://github.com/ARUNAGIRINATHAN-K/awesome-ai-agents-2026 | ref | Agent S2, Cline, OpenCode, browser agents list |

### Optional local cheap models (for low tier)

| Path | Notes |
|------|--------|
| Ollama + Continue/OpenCode | Free local for explain/rename |
| GLM / Flash / Haiku class | ~1/5 frontier cost for medium agentic (see GLM harness guides) |

---

## Chronos-specific map

| Symptom | Lane | First agent | Escalate to |
|---------|------|-------------|-------------|
| Typo / Title Case | copy | ui-review + aesthetics skill | Ask mini |
| Date shows wrong | layout/chronos | `format_date` + ui-dev (medium) | check |
| CSS / shell broken | chronos | ui-chronos + static CSS | — |
| “Looks wrong” no repro | vision | ui-review → ui-diff --quick | 1 PNG vision |
| Multi-step click bug | browser | Playwright | browser-use / Skyvern |
| Native window only | vision | UI-TARS / pywebview notes | — |

Sources for NiceGUI itself: `docs/CHRONOS_SOURCES.md`.

---

## Cost discipline

1. `route-task` prints **cost_tier** — do not upgrade model without need.
2. Vision/browser agents are **last**.
3. OmniParser-before-raw-vision when many screenshots.
4. New chat per task; see `docs/TOKEN_PERFORMANCE.md`.
5. Append new proven agents to this file + `AGENT_CATALOG` in `scripts/agent_route.py`.

---

## Commands

```bash
python dev.py route-task "fix Title Case on media page"
python dev.py route-task "screenshot shows broken logo"
python dev.py route-task "e2e click through login and requests"
python dev.py route-task --json "wire chronos payroll tab"
python dev.py route-task --complexity high "redesign nav IA"
```
