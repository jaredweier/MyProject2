"""Recommend agent, skill, and model tier for a task by complexity and domain."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

ROOT = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))


@dataclass
class RouteRecommendation:
    complexity: str
    slice_id: str
    skill: str
    cursor_mode: str
    opencode_agent: str
    model_tier: str
    subagents: List[str]
    verify: List[str]
    rationale: str


DOMAIN_KEYWORDS: List[Tuple[str, str, str]] = [
    (r"\b(bump|rotation|day.?off|swap|schedule|coverage|cascade|night.?min)", "scheduling", "scheduling-logic"),
    (r"\b(payroll|timecard|pay.?period|overtime)", "payroll-timecard", "payroll-timecard"),
    (r"\b(login|password|permission|auth|user.?account|ldap)", "security", "security"),
    (r"\b(ui|gui|tab|widget|theme|layout|gantt|customtkinter)", "ui", "ui-development"),
    (r"\b(screenshot|png|visual|look.?wrong|contrast|spacing)", "ui-vision", "ui-vision-review"),
    (r"\b(simulator|what.?if|staffing.?sim)", "simulator", "ui-development"),
    (r"\b(cli|dev\.py|script|export|backup)", "cli-ops", "cli-operations"),
    (r"\b(build|pyinstaller|\.exe|frozen|dist)", "build", "build-deploy"),
    (r"\b(rust|scheduler_core|pyo3)", "scheduling", "scheduling-logic"),
    (r"\b(refactor|split|monolith|mixin)", "refactor", "refactor"),
]

HIGH_COMPLEXITY = re.compile(
    r"\b(architect|refactor|multi.?slice|migrate|redesign|integrat|package.?split|rust)\b",
    re.I,
)
VISION_COMPLEXITY = re.compile(
    r"\b(screenshot|visual|png|observe|look.?and.?feel|layout.?bug|ui.?review)\b",
    re.I,
)
TRIVIAL = re.compile(
    r"\b(typo|spelling|comment|rename|format|whitespace|import)\b",
    re.I,
)
VERIFY_ONLY = re.compile(
    r"\b(verify|check|test|audit|preflight|did.+pass|run.+tests)\b",
    re.I,
)
LOW = re.compile(r"\b(explain|what does|how does|where is|document)\b", re.I)


def _match_domain(text: str) -> Tuple[str, str]:
    for pattern, slice_id, skill in DOMAIN_KEYWORDS:
        if re.search(pattern, text, re.I):
            return slice_id, skill
    return "general", "dodgeville-scheduler"


def _complexity(text: str, override: str = "") -> str:
    if override:
        return override.lower()
    if TRIVIAL.search(text):
        return "trivial"
    if VERIFY_ONLY.search(text) and not re.search(r"\b(fix|implement|add)\b", text, re.I):
        return "verify"
    if VISION_COMPLEXITY.search(text):
        return "vision"
    if HIGH_COMPLEXITY.search(text):
        return "high"
    if LOW.search(text):
        return "low"
    if len(text.split()) > 25 or text.count(",") >= 2:
        return "high"
    return "medium"


def _cursor_mode(complexity: str) -> str:
    return {
        "trivial": "Tab completion (or inline edit)",
        "low": "Ask",
        "medium": "Agent",
        "high": "Plan (Shift+Tab) then Agent",
        "vision": "Agent + image attach or Browser",
        "verify": "Terminal (any Agent optional)",
    }.get(complexity, "Agent")


def _model_tier(complexity: str) -> str:
    return {
        "trivial": "fast / mini (Haiku, GPT-4o-mini, Grok Fast) — or no LLM",
        "low": "Auto or fast chat model",
        "medium": "balanced (Sonnet, Grok, Composer)",
        "high": "reasoning / flagship (Opus, Sonnet 4, Grok reasoning)",
        "vision": "vision-capable (Sonnet vision, GPT-4o, Grok vision)",
        "verify": "any — terminal is free; fast model fine for interpreting output",
    }.get(complexity, "balanced")


def _opencode_agent(complexity: str, skill: str) -> str:
    if complexity == "vision":
        return "ui-vision-reviewer"
    if complexity == "verify":
        return "qa-free (or primary agent)"
    if complexity in ("high", "medium"):
        return f"primary + skill {skill}"
    return "primary"


def _subagents(complexity: str, skill: str) -> List[str]:
    if complexity == "high":
        return [skill, "qa-verify or code-reviewer"]
    if complexity == "vision":
        return ["ui-vision-review", "ui-development"]
    if complexity == "medium":
        return [skill]
    return []


def _verify_commands(complexity: str, slice_id: str) -> List[str]:
    base = ["python dev.py cheap-check", "python dev.py preflight"]
    if slice_id and slice_id != "general":
        base.append(f"python dev.py verify-slice {slice_id}")
    if complexity in ("medium", "high", "vision"):
        base.append("python dev.py check")
    return base


def route_task(
    task: str,
    *,
    complexity_override: str = "",
    slice_override: str = "",
) -> RouteRecommendation:
    text = (task or "").strip()
    complexity = _complexity(text, complexity_override)
    slice_id, skill = _match_domain(text)
    if slice_override:
        slice_id = slice_override

    if complexity == "vision":
        skill = "ui-vision-review"
        slice_id = slice_id if slice_id not in ("general", "cli-ops") else "ui-vision"

    rationale_parts = [
        f"Matched domain → slice `{slice_id}`, skill `{skill}`.",
        f"Complexity tier `{complexity}` from task wording",
    ]
    if complexity_override:
        rationale_parts.append(f"(override: {complexity_override})")

    return RouteRecommendation(
        complexity=complexity,
        slice_id=slice_id,
        skill=f".grok/skills/{skill}/SKILL.md",
        cursor_mode=_cursor_mode(complexity),
        opencode_agent=_opencode_agent(complexity, skill),
        model_tier=_model_tier(complexity),
        subagents=_subagents(complexity, skill),
        verify=_verify_commands(complexity, slice_id),
        rationale=" ".join(rationale_parts) + ".",
    )


def format_recommendation_compact(rec: RouteRecommendation) -> str:
    """Minimal route line for agent-pack (~30 tokens vs ~200)."""
    verify = rec.verify[0] if rec.verify else "python dev.py cheap-check"
    return (
        f"tier={rec.complexity} slice={rec.slice_id} cursor={rec.cursor_mode} "
        f"skill={rec.skill.split('/')[-2]} verify={verify}"
    )


def format_recommendation(rec: RouteRecommendation, task: str) -> str:
    lines = [
        "Dodgeville PD — agent route recommendation",
        "=" * 60,
        f"Task: {task[:200]}{'...' if len(task) > 200 else ''}",
        "",
        f"Complexity:  {rec.complexity}",
        f"Slice:       {rec.slice_id}",
        f"Skill:       {rec.skill}",
        f"Rationale:   {rec.rationale}",
        "",
        "--- Cursor ---",
        f"Mode:        {rec.cursor_mode}",
        f"Model tier:  {rec.model_tier}",
        "Context:     @docs/AGENT_STABLE.md · @logs/agent_pack/latest.md",
        "",
        "--- Grok / OpenCode ---",
        f"Agent:       {rec.opencode_agent}",
    ]
    if rec.subagents:
        lines.append(f"Subagents:   {', '.join(rec.subagents)}")
    lines.extend(["", "--- Verify ---"])
    for cmd in rec.verify:
        lines.append(f"  {cmd}")
    lines.extend(
        [
            "",
            "Policy: docs/AGENT_STABLE.md · Detail: docs/AGENT_ROUTING.md",
            "=" * 60,
        ]
    )
    return "\n".join(lines)


def run_agent_route(
    task: str,
    *,
    complexity: str = "",
    slice_id: str = "",
    as_json: bool = False,
) -> int:
    if not task.strip():
        print('Usage: python dev.py route-task "fix bump approval"')
        print('       python dev.py route-task --json "fix bump approval"')
        return 1
    rec = route_task(task, complexity_override=complexity, slice_override=slice_id)
    if as_json:
        from scripts.structured_output import dump_json, shape_route

        print(dump_json(shape_route(rec)))
        return 0
    print(format_recommendation(rec, task))
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    comp = ""
    slice_ov = ""
    as_json = False
    rest: List[str] = []
    i = 0
    while i < len(args):
        if args[i] == "--complexity" and i + 1 < len(args):
            comp = args[i + 1]
            i += 2
        elif args[i] == "--slice" and i + 1 < len(args):
            slice_ov = args[i + 1]
            i += 2
        elif args[i] == "--json":
            as_json = True
            i += 1
        else:
            rest.append(args[i])
            i += 1
    raise SystemExit(run_agent_route(" ".join(rest), complexity=comp, slice_id=slice_ov, as_json=as_json))
