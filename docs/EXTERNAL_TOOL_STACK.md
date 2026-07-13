# External Tool Stack — Math · UI · Token-min · Local agents

**Purpose:** Catalog of tools found across the web that help Chronos / Dodgeville PD, what we **implemented in-repo**, and how to route work to your **physical machine** to save tokens.
**Last researched:** 2026-07-09
**Do not** add LLM frameworks to the product runtime (`logic/*`, `gui/*` stay free of agent SDKs).

---

## Quick commands (machine = $0 LLM)

| Need | Command |
|------|---------|
| Route task to free local tools | `python dev.py local-dispatch "your task"` |
| Catalog of local lanes | `python dev.py local-dispatch --list` |
| **Math/logic open research** | `python dev.py math-domain explore\|brainstorm\|research-queries` |
| All free math gates | `python dev.py math-domain run-checks` |
| Scheduling math stress | `python dev.py math-scenarios` |
| + optional CP-SAT | `pip install ortools` then `math-scenarios --with-cpsat` |
| Property/fuzz math | `python dev.py fuzz-scheduling` (`pip install hypothesis`) |
| Logic vs Chronos gaps | `python dev.py parity-audit` |
| LE commercial checklist | `python dev.py le-benchmark` |
| Chronos browser smoke | start `python main.py --browser` then `python dev.py chronos-e2e` |
| Cloud agent cost gate | `python dev.py route-task "…"` — obey cost_tier |
| Ship | `python dev.py verify --tier check` |

---

## 1. Sophisticated scheduling math

| Tool | URL | Cost | Status in this repo |
|------|-----|------|---------------------|
| **Our Rust core** | `rust/scheduler_core` | free | Production hot path |
| **coverage_optimizer** | `logic/coverage_optimizer.py` | free | Beam search multi-plan bumps |
| **math-scenarios** | `python dev.py math-scenarios` | free | **Implemented** — cycle, night min, rest, cascade, pay period |
| **OR-Tools CP-SAT** | https://developers.google.com/optimization/scheduling/employee_scheduling | free local | **Optional bridge** `logic/cp_sat_bridge.py` |
| OR-Tools shift example | https://github.com/google/or-tools/blob/main/examples/python/shift_scheduling_sat.py | free | Pattern source for CP-SAT |
| CP-SAT primer | https://github.com/d-krupke/cpsat-primer | free | Learning |
| Timefold (Python discontinued) | https://timefold.ai | commercial/history | Do not depend |
| SolverForge (Timefold fork) | https://github.com/SolverForge/solverforge-legacy | free | Watch; not wired (JVM/heavy) |
| PyJobShop | https://github.com/PyJobShop/PyJobShop | free | Job-shop CP — not LE bump rules |
| PuLP / CBC | https://coin-or.github.io/pulp/ | free | LP alternative; CP-SAT preferred for rostering |

**Rule:** Department bump/night/rest stay in `validators` + `logic`. CP-SAT is for **what-if / multi-day feasibility scenarios**, not silent replacement of policy.

```bash
pip install ortools
python -c "from logic.cp_sat_bridge import demo_week_instance, solve_staffing_feasibility as s; print(s(demo_week_instance()))"
python dev.py math-scenarios --with-cpsat
```

---

## 2. UI / GUI

| Tool | URL | Cost | Status |
|------|-----|------|--------|
| **NiceGUI** | https://nicegui.io/documentation | free | Primary Chronos UI |
| **Playwright** | https://github.com/microsoft/playwright | free | **Scaffold** `python dev.py chronos-e2e` |
| NiceGUI testing docs | https://nicegui.io/documentation/section_testing | free | Prefer before inventing |
| Quasar | https://quasar.dev | free | Underlying widgets |
| Schedule-X | https://github.com/schedule-x/schedule-x | free | Calendar UX patterns only |
| in-repo ui-review / ui-diff | `dev.py` | free | First UI lane |
| ui-exhaustive (Tk legacy) | `dev.py ui-exhaustive` | free | Legacy GUI gate |
| browser-use | https://github.com/browser-use/browser-use | vision $$ | Last resort exploratory |
| Skyvern | https://github.com/Skyvern-AI/skyvern | vision $$ | Complex multi-page |
| OmniParser | https://microsoft.github.io/OmniParser/ | vision↓ | Screenshot → elements |
| Stagehand | https://github.com/browserbase/stagehand | balanced | AI browser scripts |
| UI-TARS | https://github.com/bytedance/UI-TARS | vision | Native pywebview |

```bash
# Optional Playwright
pip install playwright
playwright install chromium
python main.py --browser   # terminal 1
python dev.py chronos-e2e  # terminal 2
```

---

## 3. Token minimization & local / subagents

| Tool | URL | Cost | How we use |
|------|-----|------|------------|
| **local-dispatch** | `python dev.py local-dispatch` | $0 | **Implemented** — map tasks → machine commands |
| route-task | `python dev.py route-task` | $0 classify | Binding cost_tier |
| OpenCode | https://github.com/anomalyco/opencode | free tool + model | `.opencode/` agents; Ollama |
| Aider | https://github.com/Aider-AI/aider | free + model | Trivial multi-file on Ollama |
| Continue.dev | https://github.com/continuedev/continue | free + model | IDE + local models |
| Ollama | https://ollama.com | $0 local | `ollama pull qwen2.5-coder:7b` |
| Cline | https://github.com/cline/cline | balanced | VS Code permission-gated |
| ruff / pre-commit | requirements-dev | free | Machine lint |
| LiteLLM (optional) | https://github.com/BerriAI/litellm | ops | Proxy/cache — not in product |

### Token routing policy (enforce)

```text
1. local-dispatch "<task>"     → if free-machine, STOP (no cloud agent)
2. route-task "<task>"         → obey cost_tier
3. trivial/verify              → Tab / terminal / OpenCode qa-free only
4. low                         → Ask mini OR Aider+Ollama OR Continue local
5. medium+                     → cloud agent only after free gates fail or code design needed
6. vision/browser              → after ui-review + ui-diff --quick
```

### Suggested local stack (your PC)

```text
# One-time
pip install -r requirements-dev.txt
pip install ortools          # optional math
pip install playwright && playwright install chromium   # optional Chronos E2E
# Optional local LLM
# install Ollama from https://ollama.com then:
ollama pull qwen2.5-coder:7b
# Aider: pip install aider-chat
# aider --model ollama/qwen2.5-coder:7b
```

OpenCode agents (in-repo):
- `.opencode/agents/qa-free.md` — gates only
- `.opencode/agents/ui-static-reviewer.md` — copy/theme
- `.opencode/agents/ui-chronos.md` — NiceGUI
- `.opencode/agents/local-cheap.md` — **new** local/token-min lane
- `.opencode/agents/scheduling-math.md` — **new** math scenarios lane

---

## 4. What was implemented (wave 1 + wave 2)

| Artifact | Role |
|----------|------|
| `logic/cp_sat_bridge.py` | Optional OR-Tools staffing feasibility |
| `scripts/math_scenarios.py` | Free sophisticated math cases M-01..M-10 |
| `scripts/fuzz_scheduling.py` | Property/fuzz invariants (+ Hypothesis) |
| `scripts/parity_audit.py` | Logic symbols vs `gui/` wiring gaps |
| `scripts/le_benchmark.py` | Commercial LE feature checklist (honest) |
| `scripts/local_dispatch.py` | Task → machine commands ($0) |
| `scripts/chronos_e2e.py` | Playwright Chronos smoke (optional) |
| `gui/tables.py` | NiceGUI AG Grid helper for dense tables |
| Roster grid toggle | `gui/pages/roster.py` list/grid modes |
| OpenCode agents | local-cheap, scheduling-math |

### Wave 2–3 research finds

| Find | URL / note | Action |
|------|------------|--------|
| Hypothesis | https://hypothesis.works | **Wired** in fuzz-scheduling |
| NiceGUI AG Grid | https://nicegui.io/documentation/aggrid | **Wired** gui/tables.py + payroll/OT |
| Commercial LE features | Aladtec, Snap, inTime, First Due (public lists) | **Wired** le-benchmark + **product pages** |
| LE playbook | `docs/LE_PRODUCT_PLAYBOOK.md` | Open shifts, bidding, gap board, OT equity, My Week |
| Open shifts board | `/open-shifts` | Self-service vacancy marketplace |
| Shift bidding UI | `/bidding` | Draft → publish → preview → finalize |
| FLSA hours watch UI | Dashboard + Ops | `get_hours_watch` |
| Equitable OT ledger UI | Ops AG Grid | `get_equitable_ot_ledger` |
| Anthropic PBT agent paper | property-based testing + agents | Pattern: auto-write Hypothesis props |
| coverage.py | https://coverage.readthedocs.io | Optional |
| SMS / mobile / CAD | commercial only | Documented next bets — not wired |

---

## 5. Explicit non-goals

- Do not put LangChain/CrewAI into the scheduler app
- Do not replace bump policy with a generic nurse rostering model
- Do not require ortools/playwright for ship gate (optional enhancers)
- Do not run vision agents for typos

---

## OSS report line (agents)

```text
OSS: searched scheduling CP-SAT + local coding agents + Playwright
  → used OR-Tools docs, Playwright intro, OpenCode/Aider/Ollama guides
  → implemented logic/cp_sat_bridge.py, math_scenarios, local_dispatch, chronos_e2e
  → deposited: docs/EXTERNAL_TOOL_STACK.md + catalog rows
```
