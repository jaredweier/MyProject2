"""
Route trivial/low tasks to the **physical machine** (free local tools) — $0 LLM tokens.

Use instead of opening a cloud agent for:
  - verify, lint, outline, ui-review, math scenarios, feature-map, doctor

    python dev.py local-dispatch "fix typo"
    python dev.py local-dispatch "run tests"
    python dev.py local-dispatch "math cascade"
    python dev.py local-dispatch --list

Prints exact shell commands to run locally (or runs them with --exec).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@dataclass
class LocalPlan:
    task: str
    lane: str  # free-machine | local-llm-optional | need-agent
    cost: str  # $0 | local-ollama | cloud
    commands: List[str]
    rationale: str
    subagent_hint: str = ""


# (regex, lane, cost, commands, rationale, subagent)
RULES: List[Tuple[str, str, str, List[str], str, str]] = [
    (
        r"\b(verify|check|test|unittest|audit|preflight|scenarios|math.?scen)\b",
        "free-machine",
        "$0",
        [
            "python dev.py verify --tier fast",
            "python dev.py math-scenarios",
            "python dev.py scenarios",
        ],
        "Gates and math scenarios run on CPU — no LLM",
        "OpenCode qa-free / terminal only",
    ),
    (
        r"\b(lint|ruff|format|spell)\b",
        "free-machine",
        "$0",
        ["python dev.py lint", "python dev.py ui-review"],
        "Ruff + static UI copy on machine",
        "ui-static-reviewer",
    ),
    (
        r"\b(typo|title.?case|wording|label|copy)\b",
        "free-machine",
        "$0",
        ["python dev.py ui-review", "python dev.py ui-diff --quick"],
        "Static aesthetics before any agent",
        "ui-static-reviewer · Tab for one-char typos",
    ),
    (
        r"\b(outline|symbol|read.?budget|usage.?brief|structure)\b",
        "free-machine",
        "$0",
        ["python dev.py usage-brief day-off-requests", "python dev.py outline logic/scheduling.py"],
        "Token-min context tools — never full-file dump",
        "none",
    ),
    (
        r"\b(doctor|smoke|feature.?map|slice.?check|token.?audit)\b",
        "free-machine",
        "$0",
        ["python dev.py doctor", "python dev.py feature-map", "python dev.py token-audit"],
        "Health/map tooling on machine",
        "none",
    ),
    (
        r"\b(bump|cascade|night.?min|rest|rotation|coverage|cp.?sat|ortools|staffing|fuzz|math.?domain|beam.?search|ilp|rostering)\b",
        "free-machine",
        "$0",
        [
            "python dev.py math-domain explore",
            "python dev.py math-domain brainstorm",
            "python dev.py math-domain research-queries scheduling optimization",
            "python dev.py math-domain run-checks",
            "python dev.py math-scenarios --with-cpsat",
            "python dev.py fuzz-scheduling",
            "python dev.py scenarios",
        ],
        "Logic/math OPEN research + free CPU checks (any OR source after)",
        "skill scheduling-logic — web_search/arXiv unrestricted",
    ),
    (
        r"\b(parity|thin.?ui|feature.?gap|benchmark|aladtec|missing.?ui)\b",
        "free-machine",
        "$0",
        [
            "python dev.py parity-audit",
            "python dev.py le-benchmark",
            "python dev.py feature-map",
        ],
        "Honest product/UI gap discovery — no cloud agent needed",
        "none until you pick a gap to implement",
    ),
    (
        r"\b(first.?responder|flsa|comp.?time|7\(?k\)?|aladtec|snap.?schedule|intime|fire|ems|payroll.?period|wfm|brainstorm|explore)\b",
        "free-machine",
        "$0",
        [
            "python dev.py fr-domain explore",
            "python dev.py fr-domain brainstorm",
            "python dev.py fr-domain suggest --all",
            "python dev.py fr-domain research-queries first responder scheduling",
            "python dev.py fr-domain flsa",
            "python dev.py fr-domain compare",
        ],
        "FR WFM broad exploration (not a short restricted list)",
        "skill first-responder-wfm — then web_search freely",
    ),
    (
        r"\b(ui.?review|ui.?diff|ui.?smoke|chronos.?e2e|playwright|ui.?domain|nicegui|dashboard.?ui|theme)\b",
        "free-machine",
        "$0",
        [
            "python dev.py ui-domain explore",
            "python dev.py ui-domain brainstorm",
            "python dev.py ui-domain research-queries chronos dashboard",
            "python dev.py ui-review",
            "python dev.py ui-diff --quick",
            "python dev.py chronos-e2e --help",
        ],
        "UI open research + free static gates (any public UX source after)",
        "skill ui-development — web_search unrestricted",
    ),
    (
        r"\b(ollama|local.?model|aider|continue)\b",
        "local-llm-optional",
        "local-ollama",
        [
            "ollama pull qwen2.5-coder:7b",
            "aider --model ollama/qwen2.5-coder:7b",
            "# or: opencode  (auto-detects Ollama)",
        ],
        "Trivial multi-file edits on local model — $0 cloud",
        "Aider / OpenCode small_model / Continue.dev",
    ),
]


def plan_local(task: str) -> LocalPlan:
    text = (task or "").strip()
    if not text:
        return LocalPlan(
            task=text,
            lane="free-machine",
            cost="$0",
            commands=["python dev.py local-dispatch --list"],
            rationale="Empty task — show catalog",
        )
    for pattern, lane, cost, cmds, why, sub in RULES:
        if re.search(pattern, text, re.I):
            return LocalPlan(
                task=text,
                lane=lane,
                cost=cost,
                commands=list(cmds),
                rationale=why,
                subagent_hint=sub,
            )
    # Default: still prefer free route-task + cheap machine pack
    return LocalPlan(
        task=text,
        lane="need-agent",
        cost="cloud-if-edit",
        commands=[
            f'python dev.py route-task "{text}"',
            "python dev.py usage-brief day-off-requests",
            "python dev.py verify --tier fast",
        ],
        rationale="No free-only match — still start with route-task + machine context, then agent if needed",
        subagent_hint="Match cost_tier from route-task; trivial→Tab, low→Ask/Aider local",
    )


def list_catalog() -> int:
    print("Local dispatch catalog — run on your machine ($0 LLM when free-machine)")
    print("=" * 72)
    print(f"{'Lane':<22} {'Cost':<14} Pattern → first command")
    print("-" * 72)
    for pattern, lane, cost, cmds, why, sub in RULES:
        print(f"{lane:<22} {cost:<14} /{pattern[:40]}/")
        print(f"  → {cmds[0]}")
        print(f"  {why} · subagent: {sub}")
    print("-" * 72)
    print("Also: Ollama + Aider/Continue/OpenCode for local-llm-optional lane")
    print("Docs: docs/EXTERNAL_TOOL_STACK.md")
    return 0


def run_local_dispatch(
    task: str,
    *,
    execute: bool = False,
    list_only: bool = False,
) -> int:
    if list_only:
        return list_catalog()

    plan = plan_local(task)
    print("Dodgeville PD — local dispatch (save cloud tokens)")
    print("=" * 64)
    print(f"Task:     {plan.task}")
    print(f"Lane:     {plan.lane}")
    print(f"Cost:     {plan.cost}")
    print(f"Why:      {plan.rationale}")
    if plan.subagent_hint:
        print(f"Subagent: {plan.subagent_hint}")
    print("-" * 64)
    print("Commands (machine):")
    for i, cmd in enumerate(plan.commands, 1):
        print(f"  {i}. {cmd}")
    print("-" * 64)
    if plan.lane == "free-machine":
        print("Do NOT open a flagship cloud agent for this — run the commands above.")
    elif plan.lane == "local-llm-optional":
        print("Prefer Ollama/Aider/OpenCode local before cloud Sonnet/Opus.")
    else:
        print("May need agent — still run route-task + free gates first.")

    if execute and plan.lane == "free-machine":
        # Run first non-comment command only (safe)
        for cmd in plan.commands:
            if cmd.strip().startswith("#"):
                continue
            print(f"\n>>> exec: {cmd}")
            code = subprocess.call(cmd, shell=True, cwd=ROOT)
            if code != 0:
                return code
            break
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Route tasks to local machine tools")
    p.add_argument("task", nargs="*", help="Task description")
    p.add_argument("--list", action="store_true", help="Show catalog")
    p.add_argument("--exec", action="store_true", help="Execute first free-machine command")
    args = p.parse_args(argv)
    task = " ".join(args.task)
    return run_local_dispatch(task, execute=args.exec, list_only=args.list)


if __name__ == "__main__":
    raise SystemExit(main())
