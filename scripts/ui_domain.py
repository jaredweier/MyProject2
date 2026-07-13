"""
UI domain tool — OPEN research mode (not a closed catalog).

MAXIMUM CAPABILITY UI tool — no research allowlists, no “safe only” caps.
Use ANY source that improves Chronos: docs, GitHub, competitors, design systems,
demos, papers, RFPs, paid UI kits if available. Optimize for best product quality.

    python dev.py ui-domain explore|brainstorm|research-queries|suggest --all|learn
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

KB_PATH = ROOT / "docs" / "knowledge" / "ui_sources.json"
LEARN_MIRROR = ROOT / "docs" / "knowledge" / "ui_sources_LEARNINGS.md"
IDEAS_PATH = ROOT / "docs" / "knowledge" / "ui_idea_backlog.json"

SEED_IDEAS: List[Dict[str, str]] = [
    {"lane": "dashboard_kpis", "idea": "Real-time duty strip with pulse for understaffed bands", "why": "ops floor"},
    {
        "lane": "dashboard_kpis",
        "idea": "Clickable KPI → deep-link filtered queue",
        "why": "Mark43/Linear jump patterns",
    },
    {"lane": "schedule_matrix", "idea": "Heatmap intensity by headcount shortfall", "why": "coverage at a glance"},
    {"lane": "schedule_matrix", "idea": "Pin today column + sticky officer names", "why": "Gantt UX"},
    {
        "lane": "gantt_timeline",
        "idea": "Thin bars + court/training color legend always visible",
        "why": "LE status language",
    },
    {"lane": "forms_dialogs", "idea": "Approve leave modal with bump plan summary cards", "why": "supervisor trust"},
    {
        "lane": "data_grids",
        "idea": "AG Grid on all ledgers (OT, payroll, requests, audit)",
        "why": "enterprise density",
    },
    {"lane": "data_grids", "idea": "Export visible grid to CSV from UI", "why": "supervisor reports"},
    {"lane": "self_service", "idea": "Officer home: My Week + open shifts + banks only", "why": "mobile-first role"},
    {"lane": "mobile_responsive", "idea": "Bottom tab bar for officer role on phone", "why": "PWA path"},
    {"lane": "mobile_responsive", "idea": "PWA manifest + icons + install prompt", "why": "first responder phones"},
    {"lane": "theme_tokens", "idea": "High-contrast status tokens WCAG AA on dark", "why": "a11y"},
    {"lane": "theme_tokens", "idea": "Print stylesheet for wall roster", "why": "station printers"},
    {"lane": "charts", "idea": "OT equity bar chart next to ledger", "why": "fairness viz"},
    {"lane": "charts", "idea": "Hours-to-7k-threshold meter per officer", "why": "FLSA visual"},
    {"lane": "e2e_testing", "idea": "Playwright smoke for every nav route", "why": "Chronos regression"},
    {"lane": "shell_nav", "idea": "Command palette Ctrl+K jump to page", "why": "Linear/power user"},
    {"lane": "shell_nav", "idea": "Collapse sidebar to icons with tooltips", "why": "desktop density"},
    {"lane": "self_service", "idea": "Empty states with one primary CTA each page", "why": "product polish"},
    {"lane": "forms_dialogs", "idea": "Inline validation toast + field errors (no silent fail)", "why": "trust"},
    {"lane": "schedule_matrix", "idea": "Drag-assign open shift onto officer (optional)", "why": "First Due boards"},
    {"lane": "dashboard_kpis", "idea": "Severity stack: critical → warn → ok collapsible", "why": "alert hygiene"},
    {"lane": "data_grids", "idea": "Saved filter presets (My squad / Tonight / Pending)", "why": "power supervisors"},
    {"lane": "a11y", "idea": "Focus rings + keyboard approve/reject shortcuts", "why": "speed + a11y"},
    {"lane": "charts", "idea": "Labor budget burn-up chart YTD", "why": "finance ops"},
]


def load_kb() -> Dict[str, Any]:
    if not KB_PATH.is_file():
        return {"policy": "OPEN RESEARCH", "learnings": [], "search_templates": []}
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
        k = (it.get("idea") or "").strip().lower()
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
    print("UI domain tool — MAXIMUM CAPABILITY (no source restrictions)")
    print("=" * 64)
    print(data.get("policy", ""))
    print("-" * 64)
    tips = data.get("excellence_tips") or []
    if tips:
        print("Excellence:")
        for x in tips:
            print(f"  ★ {x}")
        print("-" * 64)
    print("Starter stacks (optional inspiration):")
    for k, v in (data.get("starter_stacks") or {}).items():
        print(f"  {k}: {', '.join(v)}")
    print(f"\nIdea backlog: {len(load_ideas())} · learnings: {len(data.get('learnings') or [])}")
    print("Commands: explore | brainstorm | suggest --all | research-queries | learn | chronos-map")
    return 0


def cmd_explore(data: Dict[str, Any]) -> int:
    print("EXPLORE UI — sources + lanes + backlog (open world)")
    print("=" * 72)
    print(data.get("policy", ""))
    print("\n## Search templates (substitute freely; invent more)")
    for t in data.get("search_templates") or []:
        print(f"  • {t}")
    print("\n## UI lanes")
    for lane in data.get("ui_lanes") or []:
        print(f"  • {lane}")
    print("\n## Idea backlog")
    for i, it in enumerate(load_ideas(), 1):
        print(f"  {i:02d}. [{it.get('lane')}] {it.get('idea')} — {it.get('why', '')}")
    print("\n## Chronos files")
    print("  gui/app.py · gui/shell.py · gui/pages/* · gui/static/chronos.css · gui/tables.py · gui/theme.py")
    print("=" * 72)
    print("Use every useful source. Optimize for best UI — no catalog ceiling.")
    print("Deposit: ui-domain learn --url … --note …")
    return 0


def cmd_brainstorm(data: Dict[str, Any]) -> int:
    print("BRAINSTORM UI — mix Chronos pages × industry patterns × backlog")
    print("=" * 72)
    pages = sorted((ROOT / "gui" / "pages").glob("*.py")) if (ROOT / "gui" / "pages").is_dir() else []
    print("## Current Chronos pages")
    for p in pages:
        if p.name.startswith("_"):
            continue
        print(f"  • gui/pages/{p.name} ({p.stat().st_size // 1024}KB)")
    print("\n## Cross-product inspiration (search these freely)")
    for name in (
        "Aladtec schedule board",
        "Snap Schedule fill open shift UX",
        "inTime court calendar UI",
        "First Due drag-drop shiftboard",
        "Linear command palette",
        "Mark43 LE dashboard",
        "Deputy roster mobile",
        "Quasar dark dashboard examples",
        "NiceGUI aggrid + plotly side by side",
        "Schedule-X week view",
    ):
        print(f"  • {name}")
    print("\n## Ranked backlog (all options — pick many)")
    for it in load_ideas():
        print(f"  [{it.get('lane')}] {it.get('idea')}")
        if it.get("why"):
            print(f"      → {it['why']}")
    print("\n## Recent learnings")
    for e in (data.get("learnings") or [])[-12:]:
        print(f"  · [{e.get('topic')}] {str(e.get('note'))[:120]}")
    print("=" * 72)
    print("Not restricted to this list — invent more, then learn --as-idea")
    return 0


def cmd_research_queries(_data: Dict[str, Any], topic: str) -> int:
    topic = (topic or "schedule dashboard").strip()
    data = load_kb()
    print(f"OPEN research queries — topic: {topic}")
    print("Use web_search / open_page / GitHub on ANY public host.")
    print("=" * 72)
    templates = list(data.get("search_templates") or [])
    # Expand with topic
    queries = [
        t.replace("{component}", topic).replace("{keyword}", topic).replace("{error message}", topic) for t in templates
    ]
    queries.extend(
        [
            f"{topic} UX best practices 2026",
            f"{topic} open source alternative GitHub",
            f"{topic} police OR fire OR EMS software UI",
            f"{topic} NiceGUI OR Quasar OR Playwright",
            f"site:reddit.com {topic} dashboard",
            f"{topic} accessibility dark mode",
            f"{topic} mobile first responsive",
        ]
    )
    for i, q in enumerate(queries, 1):
        print(f"  {i}. {q}")
    print("-" * 72)
    print('After research: python dev.py ui-domain learn --topic "…" --note "…" --url "…" --as-idea')
    return 0


def cmd_suggest(*, lane: str = "", all_ideas: bool = False) -> int:
    ideas = load_ideas()
    if lane:
        ideas = [i for i in ideas if i.get("lane") == lane or lane in (i.get("idea") or "").lower()]
    print("UI SUGGEST — open backlog (not exclusive)")
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
    print(f"{len(ideas)} ideas · invent more via research-queries + learn --as-idea")
    return 0


def cmd_chronos_map() -> int:
    print("Chronos UI map (edit freely; patterns from any source)")
    print("=" * 64)
    root = ROOT / "gui"
    if not root.is_dir():
        print("gui/ missing")
        return 1
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(ROOT).as_posix()
        n = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        print(f"  {rel:<40} {n:>5} lines")
    css = ROOT / "gui" / "static" / "chronos.css"
    if css.is_file():
        print(f"  gui/static/chronos.css                     {css.stat().st_size // 1024:>4} KB")
    print("\nFree gates: ui-review · ui-diff --quick · chronos-e2e · ui-smoke")
    return 0


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
    # Optionally append URL to starter if provided
    if url and url not in json.dumps(data):
        data.setdefault("deposited_urls", []).append(
            {"url": url, "topic": topic, "note": note[:120], "ts": datetime.now(timezone.utc).isoformat()}
        )
    save_kb(data)
    if as_idea:
        save_idea(note[:200], lane=lane or topic or "general", why=source or url)
    lines = ["# UI sources learnings (any public source)", ""]
    for e in (data.get("learnings") or [])[-40:]:
        lines.append(f"## {e.get('ts')} — {e.get('topic')}")
        lines.append(e.get("note") or "")
        if e.get("url") or e.get("source"):
            lines.append(f"_ {e.get('source')} {e.get('url')}_")
        lines.append("")
    LEARN_MIRROR.write_text("\n".join(lines), encoding="utf-8")
    print(f"Learned. Total: {len(data['learnings'])} · KB {KB_PATH}")
    return 0


def run_ui_domain(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="UI domain — open research any public source")
    p.add_argument(
        "command",
        nargs="?",
        default="show",
        help="show|explore|brainstorm|suggest|research-queries|chronos-map|learn|add-idea|lanes",
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
    if cmd in ("research-queries", "research", "queries"):
        return cmd_research_queries(data, q or args.topic)
    if cmd == "suggest":
        return cmd_suggest(lane=args.lane, all_ideas=args.all_ideas)
    if cmd in ("chronos-map", "map"):
        return cmd_chronos_map()
    if cmd == "lanes":
        lanes = sorted({i.get("lane", "x") for i in load_ideas()})
        for ln in lanes:
            print(ln)
        return 0
    if cmd in ("add-idea", "idea"):
        idea = args.note or q
        if not idea:
            print("need --note")
            return 1
        save_idea(idea, lane=args.lane or "general", why=args.source)
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
    print(f"Unknown '{cmd}' — explore\n")
    return cmd_explore(data)


if __name__ == "__main__":
    raise SystemExit(run_ui_domain())
