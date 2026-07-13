"""
Logic & mathematics — MAXIMUM CAPABILITY (no solver/source allowlist).

Use any technique or paper that improves scheduling/payroll math quality or speed.
Starters in docs/knowledge/math_logic_sources.json are optional inspiration only.

    python dev.py math-domain explore|brainstorm|research-queries|engines|run-checks|learn
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

KB_PATH = ROOT / "docs" / "knowledge" / "math_logic_sources.json"
LEARN_MIRROR = ROOT / "docs" / "knowledge" / "math_logic_LEARNINGS.md"
IDEAS_PATH = ROOT / "docs" / "knowledge" / "math_idea_backlog.json"

SEED_IDEAS: List[Dict[str, str]] = [
    {"lane": "bump_cascade", "idea": "Explainable bump scores (why this junior won)", "why": "supervisor trust"},
    {"lane": "bump_cascade", "idea": "Multi-objective Pareto set of plans not single best", "why": "tradeoffs"},
    {"lane": "coverage_opt", "idea": "Per-band min staff ILP vs beam search bakeoff", "why": "quality"},
    {"lane": "coverage_opt", "idea": "Time-boxed optimizer with anytime best plan", "why": "UX latency"},
    {"lane": "rest_fatigue", "idea": "Rolling 7-day fatigue index in approve path", "why": "wellness"},
    {"lane": "rest_fatigue", "idea": "Configurable rest matrix by shift pair", "why": "CBA nuance"},
    {"lane": "night_min", "idea": "Night min by holiday calendar not only Fri/Sat", "why": "events"},
    {"lane": "rotation", "idea": "Kelly/Pitman/24-on generators + cycle math proofs", "why": "fire/EMS"},
    {"lane": "rotation", "idea": "Property tests: cycle wrap bijection forever", "why": "fuzz"},
    {"lane": "flsa_payroll", "idea": "Exact 7(k) table generator for 7–28 day periods", "why": "DOL ratios"},
    {"lane": "flsa_payroll", "idea": "Comp bank cap 480h enforcement + cash overflow", "why": "FLSA"},
    {"lane": "equity_ot", "idea": "Opportunity equity (offers) separate from hours equity", "why": "grievances"},
    {"lane": "bidding_award", "idea": "Seniority award with stable-matching options", "why": "fairness theory"},
    {"lane": "cp_sat_whatif", "idea": "Simulator panel: multi-day CP-SAT feasibility", "why": "ortools bridge"},
    {"lane": "cp_sat_whatif", "idea": "Export MiniZinc model of current roster constraints", "why": "interop"},
    {"lane": "rust_bridge", "idea": "Criterion benches + python parity harness", "why": "perf"},
    {"lane": "property_testing", "idea": "Hypothesis strategies for full bump chains", "why": "edge cases"},
    {"lane": "coverage_opt", "idea": "Soft skill weights without blocking hard night min", "why": "quals"},
    {"lane": "bump_cascade", "idea": "Detect infinite cascade graphs / max-depth proofs", "why": "safety"},
    {"lane": "flsa_payroll", "idea": "Overnight period ownership formalized + tested matrix", "why": "payroll bugs"},
]


def load_kb() -> Dict[str, Any]:
    if not KB_PATH.is_file():
        return {"policy": "OPEN RESEARCH", "learnings": []}
    return json.loads(KB_PATH.read_text(encoding="utf-8"))


def save_kb(data: Dict[str, Any]) -> None:
    data["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    KB_PATH.parent.mkdir(parents=True, exist_ok=True)
    KB_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_ideas() -> List[Dict[str, str]]:
    ideas = list(SEED_IDEAS)
    if IDEAS_PATH.is_file():
        try:
            raw = json.loads(IDEAS_PATH.read_text(encoding="utf-8"))
            extra = raw if isinstance(raw, list) else raw.get("ideas") or []
            ideas.extend(extra)
        except json.JSONDecodeError:
            pass
    seen = set()
    out = []
    for it in ideas:
        k = (it.get("idea") or "").lower().strip()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


def save_idea(idea: str, lane: str = "general", why: str = "") -> None:
    data: Dict[str, Any] = {"ideas": []}
    if IDEAS_PATH.is_file():
        try:
            data = json.loads(IDEAS_PATH.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {"ideas": []}
        except json.JSONDecodeError:
            data = {"ideas": []}
    data.setdefault("ideas", []).append(
        {
            "lane": lane,
            "idea": idea,
            "why": why,
            "added": datetime.now(timezone.utc).isoformat(),
        }
    )
    IDEAS_PATH.parent.mkdir(parents=True, exist_ok=True)
    IDEAS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def cmd_show(data: Dict[str, Any]) -> int:
    print("Logic/math domain — MAXIMUM CAPABILITY (no research bans)")
    print("=" * 64)
    print(data.get("policy", ""))
    print("-" * 64)
    tips = data.get("excellence_tips") or []
    if tips:
        print("Excellence:")
        for x in tips:
            print(f"  ★ {x}")
        print("-" * 64)
    eng = data.get("in_repo_engines") or {}
    for k, v in eng.items():
        if k != "free_checks":
            print(f"  {k}: {v}")
    print(f"\nIdea backlog: {len(load_ideas())} · learnings: {len(data.get('learnings') or [])}")
    print("Commands: explore | brainstorm | suggest --all | research-queries | engines | run-checks | learn")
    return 0


def cmd_engines(data: Dict[str, Any]) -> int:
    print("In-repo math engines + optional solvers")
    print("=" * 64)
    eng = data.get("in_repo_engines") or {}
    for k, v in eng.items():
        print(f"  {k}: {v}")
    print("\nOptional installs (not required for ship):")
    print("  pip install ortools hypothesis")
    try:
        from logic.cp_sat_bridge import ortools_available

        print(f"\nortools available: {ortools_available()}")
    except Exception as exc:
        print("ortools probe:", exc)
    try:
        import importlib.util as u

        print("hypothesis available:", u.find_spec("hypothesis") is not None)
    except Exception:
        pass
    print("\nStarter solvers (use any other too):")
    for s in data.get("starter_solvers_and_theory") or []:
        print(f"  • {s}")
    return 0


def cmd_explore(data: Dict[str, Any]) -> int:
    print("EXPLORE math/logic — open world")
    print("=" * 72)
    print(data.get("policy", ""))
    print("\n## Lanes")
    for lane in data.get("math_lanes") or []:
        print(f"  • {lane}")
    print("\n## Search templates (invent more freely)")
    for t in data.get("search_templates") or []:
        print(f"  • {t}")
    print("\n## Theory / solvers (starters ≠ exclusive)")
    for s in data.get("starter_solvers_and_theory") or []:
        print(f"  • {s}")
    print("\n## Idea backlog")
    for i, it in enumerate(load_ideas(), 1):
        print(f"  {i:02d}. [{it.get('lane')}] {it.get('idea')} — {it.get('why', '')}")
    print("=" * 72)
    print("web_search any OR paper, solver, or algorithm. Deposit: math-domain learn")
    return 0


def cmd_brainstorm(data: Dict[str, Any]) -> int:
    print("BRAINSTORM math — in-repo gaps × public OR techniques")
    print("=" * 72)
    # Live module sizes
    for rel in (
        "logic/scheduling.py",
        "logic/coverage_optimizer.py",
        "logic/cp_sat_bridge.py",
        "logic/rust_bridge.py",
        "validators.py",
        "logic/payroll",
        "logic/labor_compliance.py",
    ):
        p = ROOT / rel
        if p.is_dir():
            n = sum(
                len(f.read_text(encoding="utf-8", errors="replace").splitlines())
                for f in p.rglob("*.py")
                if f.is_file()
            )
            print(f"  {rel}/ ~{n} lines (package)")
        elif p.is_file():
            n = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
            print(f"  {rel}: {n} lines")
    print("\n## Public techniques to try (non-exclusive)")
    for tech in (
        "CP-SAT soft/hard constraints",
        "Column generation for rostering",
        "Local search / tabu for swaps",
        "Stable matching for bid awards",
        "Network flow for assignment",
        "Monte Carlo coverage stress",
        "Formal verification of cycle arithmetic",
        "Differential testing Rust vs Python",
    ):
        print(f"  • {tech}")
    print("\n## Backlog")
    for it in load_ideas():
        print(f"  [{it.get('lane')}] {it.get('idea')}")
    print("\n## Recent learnings")
    for e in (data.get("learnings") or [])[-10:]:
        print(f"  · [{e.get('topic')}] {str(e.get('note'))[:100]}")
    print("=" * 72)
    print("Not limited to this list — research-queries + any arXiv/GitHub solver")
    return 0


def cmd_research_queries(data: Dict[str, Any], topic: str) -> int:
    topic = (topic or "shift scheduling optimization").strip()
    print(f"OPEN math research queries — topic: {topic}")
    print("Use web_search / arXiv / GitHub / OR-Tools docs on ANY host.")
    print("=" * 72)
    queries = []
    for t in data.get("search_templates") or []:
        queries.append(t.replace("{error}", topic))
    queries.extend(
        [
            f"{topic} constraint programming",
            f"{topic} integer linear program formulation",
            f"{topic} nurse rostering benchmark",
            f"{topic} site:arxiv.org",
            f"{topic} site:or.stackexchange.com",
            f"{topic} python ortools cp_model",
            f"{topic} public safety staffing model",
            f"operations research {topic}",
        ]
    )
    for i, q in enumerate(queries, 1):
        print(f"  {i}. {q}")
    print("-" * 72)
    print('After research: python dev.py math-domain learn --topic "…" --note "…" --url "…" --as-idea')
    return 0


def cmd_suggest(*, lane: str = "", all_ideas: bool = False) -> int:
    ideas = load_ideas()
    if lane:
        ideas = [i for i in ideas if i.get("lane") == lane or lane in (i.get("idea") or "").lower()]
    print("MATH SUGGEST — open backlog")
    print("=" * 64)
    if not all_ideas and not lane:
        by: Dict[str, List] = {}
        for it in ideas:
            by.setdefault(it.get("lane") or "general", []).append(it)
        for ln, items in sorted(by.items()):
            print(f"\n[{ln}]")
            for it in items:
                print(f"  • {it.get('idea')}")
    else:
        for it in ideas:
            print(f"  [{it.get('lane')}] {it.get('idea')} — {it.get('why', '')}")
    print("=" * 64)
    print(f"{len(ideas)} ideas · invent more via research-queries")
    return 0


def cmd_run_checks() -> int:
    """Run free math batteries (machine CPU)."""
    print("Running free math/logic checks…")
    cmds = [
        [sys.executable, str(ROOT / "dev.py"), "math-scenarios", "--with-cpsat"],
        [sys.executable, str(ROOT / "dev.py"), "fuzz-scheduling", "--examples", "40"],
        [sys.executable, str(ROOT / "dev.py"), "scenarios"],
    ]
    worst = 0
    for cmd in cmds:
        print("\n>>>", " ".join(cmd))
        code = subprocess.call(cmd, cwd=str(ROOT))
        worst = max(worst, code)
    print("\nmath-domain run-checks done, worst exit:", worst)
    return worst


def cmd_learn(
    data: Dict[str, Any],
    *,
    topic: str,
    note: str,
    source: str = "",
    url: str = "",
    as_idea: bool = False,
    lane: str = "general",
) -> int:
    note = (note or "").strip()
    if not note:
        print("learn needs --note")
        return 1
    data.setdefault("learnings", []).append(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "topic": topic or "general",
            "note": note,
            "source": source,
            "url": url,
        }
    )
    if len(data["learnings"]) > 800:
        data["learnings"] = data["learnings"][-800:]
    if url:
        data.setdefault("deposited_urls", []).append(
            {"url": url, "topic": topic, "ts": datetime.now(timezone.utc).isoformat()}
        )
    save_kb(data)
    if as_idea:
        save_idea(note[:200], lane=lane or topic or "general", why=source or url)
    lines = ["# Math/logic learnings (any public OR/math source)", ""]
    for e in (data.get("learnings") or [])[-40:]:
        lines.append(f"## {e.get('ts')} — {e.get('topic')}")
        lines.append(e.get("note") or "")
        if e.get("url") or e.get("source"):
            lines.append(f"_ {e.get('source')} {e.get('url')}_")
        lines.append("")
    LEARN_MIRROR.write_text("\n".join(lines), encoding="utf-8")
    print(f"Learned. Total {len(data['learnings'])} · {KB_PATH}")
    return 0


def run_math_domain(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Logic/math open research tool")
    p.add_argument(
        "command",
        nargs="?",
        default="show",
        help="show|explore|brainstorm|suggest|research-queries|engines|run-checks|learn|add-idea|lanes|code-deep",
    )
    p.add_argument("query", nargs="*")
    p.add_argument("--topic", default="")
    p.add_argument("--note", default="")
    p.add_argument("--source", default="")
    p.add_argument("--url", default="")
    p.add_argument("--lane", default="")
    p.add_argument("--all", action="store_true", dest="all_ideas")
    p.add_argument("--as-idea", action="store_true")
    args = p.parse_args(list(argv) if argv is not None else None)
    data = load_kb()
    cmd = (args.command or "show").replace("_", "-")
    q = " ".join(args.query).strip()

    if cmd == "show":
        return cmd_show(data)
    if cmd == "explore":
        return cmd_explore(data)
    if cmd == "brainstorm":
        return cmd_brainstorm(data)
    if cmd == "engines":
        return cmd_engines(data)
    if cmd == "run-checks":
        return cmd_run_checks()
    if cmd in ("research-queries", "research", "queries"):
        return cmd_research_queries(data, q or args.topic)
    if cmd == "suggest":
        return cmd_suggest(lane=args.lane, all_ideas=args.all_ideas)
    if cmd == "lanes":
        for ln in sorted({i.get("lane", "x") for i in load_ideas()}):
            print(ln)
        return 0
    if cmd in ("add-idea", "idea"):
        if not (args.note or q):
            print("need --note")
            return 1
        save_idea(args.note or q, lane=args.lane or "general", why=args.source)
        print("Added idea")
        return 0
    if cmd == "learn":
        return cmd_learn(
            data,
            topic=args.topic or "general",
            note=args.note or q,
            source=args.source,
            url=args.url,
            as_idea=args.as_idea,
            lane=args.lane,
        )
    if cmd in ("code-deep", "source-deep", "deep"):
        from scripts.source_deep import run_source_deep

        return run_source_deep(["compare"] if not q else [q])
    print(f"Unknown '{cmd}' — explore\n")
    return cmd_explore(data)


if __name__ == "__main__":
    raise SystemExit(run_math_domain())
