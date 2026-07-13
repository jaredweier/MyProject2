"""
First-responder WFM — MAXIMUM CAPABILITY (no short-list / source ceiling).

Explore, brainstorm, research any industry/math/UX source; implement the best ideas.

    python dev.py fr-domain explore|brainstorm|suggest --all|research-queries|learn
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

KB_PATH = ROOT / "docs" / "knowledge" / "first_responder_wfm.json"
MD_MIRROR = ROOT / "docs" / "knowledge" / "first_responder_wfm_LEARNINGS.md"
IDEAS_PATH = ROOT / "docs" / "knowledge" / "first_responder_idea_backlog.json"

# Large option space — not exhaustive of industry, intentionally wide for agents
SEED_IDEAS: List[Dict[str, str]] = [
    # Scheduling / coverage
    {"lane": "scheduling", "idea": "Kelly / Pitman / 24-on fire rotation presets", "why": "Fire/EMS common patterns"},
    {
        "lane": "scheduling",
        "idea": "Station/post multi-location staffing board",
        "why": "Multi-station fire & precinct posts",
    },
    {"lane": "scheduling", "idea": "Minimum staffing by rank (Sgt/Off per band)", "why": "Supervision requirements"},
    {"lane": "scheduling", "idea": "Holdover / forced OT with reason codes", "why": "Mandatory coverage audit trail"},
    {"lane": "scheduling", "idea": "Fatigue score dashboard (hours+nights+rest)", "why": "inTime-class wellness"},
    {
        "lane": "scheduling",
        "idea": "Special event / OT detail overlay calendar",
        "why": "Festivals, DUI details, ballgames",
    },
    {"lane": "scheduling", "idea": "On-call / standby pay bands", "why": "Detective & specialty units"},
    {"lane": "scheduling", "idea": "Mutual aid / multi-agency roster view", "why": "Regional task forces"},
    # Self-service
    {"lane": "self-service", "idea": "Vacation bid season wizard", "why": "Annual leave seniority auctions"},
    {"lane": "self-service", "idea": "Partial-day leave (court AM only)", "why": "Common LE leave pattern"},
    {"lane": "self-service", "idea": "Trade board with multi-tier approval", "why": "Aladtec-style trades"},
    {"lane": "self-service", "idea": "Availability preferences (prefer nights)", "why": "Soft constraints for bids"},
    {
        "lane": "self-service",
        "idea": "Officer push subscription for open shifts",
        "why": "Vacancy alerter lite (email first)",
    },
    # Payroll / FLSA
    {"lane": "payroll", "idea": "Cash vs comp election per OT entry", "why": "Public-sector choice"},
    {"lane": "payroll", "idea": "Holiday worked multipliers config UI", "why": "2.5x/3.0x LE holidays"},
    {"lane": "payroll", "idea": "Court time minimums (2–3h callout)", "why": "Contract callout guarantees"},
    {"lane": "payroll", "idea": "Callback minimum hours auto-calc", "why": "CBA callback pay"},
    {"lane": "payroll", "idea": "7(k) threshold meter per officer period", "why": "Visual FLSA proximity"},
    {"lane": "payroll", "idea": "Export ADP/Paychex/CSV payroll pack", "why": "Finance handoff"},
    {"lane": "payroll", "idea": "Retro pay / period reopen with audit", "why": "Corrections after lock"},
    # Fairness / OT
    {"lane": "fairness", "idea": "OT Desired List (opt-in) separate from force list", "why": "Union ODL patterns"},
    {"lane": "fairness", "idea": "Declined OT tracking (equity of opportunity)", "why": "Grievance defense"},
    {"lane": "fairness", "idea": "Hours-worked vs hours-offered dual ledger", "why": "True equity metrics"},
    {"lane": "fairness", "idea": "Junior-first mandatory / senior-first voluntary modes", "why": "Policy switch"},
    # Quals / training
    {"lane": "quals", "idea": "Cert expiry calendar + block assignment", "why": "Fire/EMS quals"},
    {"lane": "quals", "idea": "FTO / trainee pairing constraints", "why": "Field training"},
    {"lane": "quals", "idea": "Specialty unit eligibility (K9, SWAT, motors)", "why": "Restricted posts"},
    {"lane": "quals", "idea": "Training day scheduler linked to leave types", "why": "inTime training"},
    # Court / admin
    {"lane": "court", "idea": "Subpoena intake + court calendar conflict check", "why": "inTime court module themes"},
    {"lane": "court", "idea": "Auto block duty when court scheduled", "why": "Conflict prevention"},
    {"lane": "court", "idea": "Witness / hearing multi-officer events", "why": "Complex court days"},
    # UI / mobile
    {"lane": "ui", "idea": "PWA manifest + install prompt", "why": "Officer phone access"},
    {"lane": "ui", "idea": "Drag-drop monthly assignment board", "why": "First Due style boards"},
    {"lane": "ui", "idea": "Today strip: who's on, gaps, open OT", "why": "Command glance"},
    {"lane": "ui", "idea": "Print-friendly wall roster PDF", "why": "Station printer culture"},
    {"lane": "ui", "idea": "Dark/light high-vis status legend always visible", "why": "Ops floor"},
    # Integrations
    {"lane": "integration", "idea": "Email open-shift digest (no SMS vendor yet)", "why": "Cheap vacancy alerter"},
    {"lane": "integration", "idea": "LDAP group → role mapping UX", "why": "Enterprise IdP"},
    {"lane": "integration", "idea": "iCal feed URL per officer (tokenized)", "why": "Personal calendars"},
    {"lane": "integration", "idea": "Webhook on approve leave / fill open shift", "why": "Automation"},
    # Math / optimizer
    {"lane": "math", "idea": "Multi-day CP-SAT staffing what-if in Simulator UI", "why": "OR-Tools bridge"},
    {"lane": "math", "idea": "Beam-search explain: why this bump chain scored best", "why": "Supervisor trust"},
    {"lane": "math", "idea": "Scenario compare A/B rotations on same roster", "why": "Staffing study"},
    # Process / agent
    {"lane": "agent", "idea": "Expand fr-domain learnings from public RFPs", "why": "Agency requirements language"},
    {"lane": "agent", "idea": "Parity-audit auto → ranked Chronos tickets", "why": "Close logic/UI gaps"},
]


def load_kb() -> Dict[str, Any]:
    if not KB_PATH.is_file():
        return {"version": 1, "learnings": [], "commercial_products": []}
    return json.loads(KB_PATH.read_text(encoding="utf-8"))


def save_kb(data: Dict[str, Any]) -> None:
    data["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    KB_PATH.parent.mkdir(parents=True, exist_ok=True)
    KB_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_idea_backlog() -> List[Dict[str, str]]:
    ideas = list(SEED_IDEAS)
    if IDEAS_PATH.is_file():
        try:
            extra = json.loads(IDEAS_PATH.read_text(encoding="utf-8"))
            if isinstance(extra, list):
                ideas.extend(extra)
            elif isinstance(extra, dict) and isinstance(extra.get("ideas"), list):
                ideas.extend(extra["ideas"])
        except json.JSONDecodeError:
            pass
    # dedupe by idea text
    seen = set()
    out = []
    for it in ideas:
        key = (it.get("idea") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def save_idea(idea: str, lane: str = "general", why: str = "") -> None:
    backlog: Dict[str, Any] = {"ideas": []}
    if IDEAS_PATH.is_file():
        try:
            backlog = json.loads(IDEAS_PATH.read_text(encoding="utf-8"))
            if not isinstance(backlog, dict):
                backlog = {"ideas": []}
        except json.JSONDecodeError:
            backlog = {"ideas": []}
    backlog.setdefault("ideas", []).append(
        {
            "lane": lane,
            "idea": idea,
            "why": why,
            "added": datetime.now(timezone.utc).isoformat(),
        }
    )
    IDEAS_PATH.parent.mkdir(parents=True, exist_ok=True)
    IDEAS_PATH.write_text(json.dumps(backlog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _flatten_strings(obj: Any, prefix: str = "") -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            out.extend(_flatten_strings(v, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(_flatten_strings(v, f"{prefix}[{i}]"))
    else:
        out.append((prefix, str(obj)))
    return out


def _have_set(data: Dict[str, Any]) -> set:
    m = data.get("chronos_mapping") or {}
    return {str(x).lower() for x in (m.get("have") or [])}


def cmd_show(data: Dict[str, Any]) -> int:
    print("First-responder WFM domain knowledge (broad mode)")
    print("=" * 64)
    print(f"Updated: {data.get('updated')} · version {data.get('version')}")
    print(data.get("disclaimer", ""))
    print("-" * 64)
    print("Commercial products catalogued:", len(data.get("commercial_products") or []))
    for p in data.get("commercial_products") or []:
        print(f"  • {p.get('name')} — {', '.join(p.get('segments') or [])}")
    flsa = (data.get("payroll_flsa") or {}).get("section_7k") or {}
    print("-" * 64)
    print("FLSA §7(k) LE thresholds (approx):", flsa.get("le_thresholds_approx"))
    print("Idea backlog size:", len(load_idea_backlog()))
    print("Learnings:", len(data.get("learnings") or []))
    print("-" * 64)
    print("Try: explore | brainstorm | suggest --all | research-queries | lanes")
    print("Agents: do not treat suggest as a closed list — explore widely.")
    return 0


def cmd_lanes(_data: Dict[str, Any]) -> int:
    lanes = sorted({i.get("lane", "general") for i in load_idea_backlog()})
    print("Idea lanes (use: fr-domain suggest --lane <name>)")
    print("=" * 64)
    for lane in lanes:
        n = sum(1 for i in load_idea_backlog() if i.get("lane") == lane)
        print(f"  {lane:<14} {n} ideas")
    print("\nAlso: police fire ems payroll ui integration fairness quals court math agent")
    return 0


def cmd_explore(data: Dict[str, Any]) -> int:
    print("EXPLORE — full industry option space (not limited to Chronos gaps)")
    print("=" * 72)
    sched = data.get("scheduling_patterns") or {}
    for key, items in sched.items():
        print(f"\n## scheduling.{key}")
        for x in items or []:
            print(f"  • {x}")
    ui = data.get("ui_ux_patterns") or {}
    for key, items in ui.items():
        print(f"\n## ui.{key}")
        for x in items or []:
            print(f"  • {x}")
    pay = data.get("payroll_flsa") or {}
    print("\n## payroll.codes")
    for c in pay.get("common_pay_codes") or []:
        print(f"  • {c}")
    print("\n## commercial function dump")
    for p in data.get("commercial_products") or []:
        print(f"\n  [{p.get('name')}]")
        for f in p.get("functions") or []:
            print(f"    • {f}")
        for u in p.get("ui_look") or []:
            print(f"    UI· {u}")
    print("\n## idea backlog (seed + learned)")
    for i, it in enumerate(load_idea_backlog(), 1):
        print(f"  {i:02d}. [{it.get('lane')}] {it.get('idea')} — {it.get('why', '')}")
    print("\n" + "=" * 72)
    print('Next: fr-domain brainstorm | suggest --all | research-queries "…"')
    return 0


def cmd_brainstorm(data: Dict[str, Any]) -> int:
    """Derive ideas from commercial functions + patterns not obviously in HAVE."""
    print("BRAINSTORM — commercial functions × Chronos gaps (wide net)")
    print("=" * 72)
    have = _have_set(data)
    partial = {str(x).lower() for x in ((data.get("chronos_mapping") or {}).get("partial") or [])}
    scored: List[Tuple[int, str, str]] = []

    for p in data.get("commercial_products") or []:
        pname = p.get("name") or "product"
        for fn in p.get("functions") or []:
            low = fn.lower()
            # score: higher if not mentioned in have
            hit_have = any(tok in " ".join(have) for tok in low.split()[:3])
            score = 1 if hit_have else 3
            scored.append((score, f"{pname}: {fn}", "from commercial functions"))
        for look in p.get("ui_look") or []:
            scored.append((2, f"UI pattern — {look}", pname))

    for it in load_idea_backlog():
        low = (it.get("idea") or "").lower()
        score = 1 if any(h in low for h in list(have)[:5]) else 3
        scored.append((score, it.get("idea") or "", f"{it.get('lane')}: {it.get('why')}"))

    for note in partial:
        scored.append((3, f"Finish partial: {note}", "chronos_mapping.partial"))

    # learnings as prompts
    for e in (data.get("learnings") or [])[-15:]:
        scored.append((2, f"From learning [{e.get('topic')}]: expand — {str(e.get('note'))[:100]}", "learnings"))

    scored.sort(key=lambda x: -x[0])
    print(f"{'Pri':<4} Idea")
    print("-" * 72)
    for score, idea, why in scored[:60]:
        print(f"  {score}  {idea}")
        print(f"      ({why})")
    print("-" * 72)
    print(f"Showing top {min(60, len(scored))} of {len(scored)} — not a closed list.")
    print('Add more: fr-domain add-idea --lane ui --note "…"')
    print('Research: fr-domain research-queries "shift bidding fire"')
    return 0


def cmd_suggest(
    data: Dict[str, Any],
    *,
    lane: str = "",
    all_ideas: bool = False,
    limit: int = 40,
) -> int:
    print("SUGGEST — multi-lane options (use --all for full backlog)")
    print("=" * 72)
    ideas = load_idea_backlog()
    if lane:
        ideas = [i for i in ideas if (i.get("lane") or "") == lane or lane in (i.get("idea") or "").lower()]
    if not all_ideas and not lane:
        # still show many, grouped, not just 4
        by_lane: Dict[str, List] = {}
        for it in ideas:
            by_lane.setdefault(it.get("lane") or "general", []).append(it)
        for ln, items in sorted(by_lane.items()):
            print(f"\n[{ln}] ({len(items)} options)")
            for it in items[: max(3, limit // max(len(by_lane), 1))]:
                print(f"  • {it.get('idea')}")
                if it.get("why"):
                    print(f"      why: {it['why']}")
        print("\n" + "=" * 72)
        print(f"Total backlog: {len(load_idea_backlog())}. For full dump: fr-domain suggest --all")
        print("Also run: explore | brainstorm | research-queries | parity-audit | le-benchmark")
        return 0

    for it in ideas[:limit] if not all_ideas else ideas:
        print(f"  [{it.get('lane')}] {it.get('idea')}")
        if it.get("why"):
            print(f"      {it['why']}")
    print("=" * 72)
    print(f"{len(ideas)} ideas" + (f" (lane={lane})" if lane else ""))
    return 0


def cmd_research_queries(_data: Dict[str, Any], topic: str) -> int:
    topic = (topic or "first responder scheduling").strip()
    print(f"Research queries for agents (web_search / open_page) — topic: {topic}")
    print("=" * 72)
    templates = [
        f"{topic} law enforcement scheduling software features",
        f"{topic} fire department EMS workforce management",
        f"{topic} FLSA 7k police overtime",
        f"{topic} Aladtec OR Snap Schedule OR inTime {topic}",
        f"site:dol.gov {topic}",
        "police officer shift bidding seniority union",
        "public safety open shift board SMS callback",
        "compensatory time 480 hours public safety",
        "court scheduling subpoena police workforce",
        "minimum staffing night shift police department software",
        f"{topic} payroll export ADP police",
        "NiceGUI schedule dashboard dark mode ops center",
    ]
    for i, q in enumerate(templates, 1):
        print(f"  {i}. {q}")
    print("-" * 72)
    print('After research: fr-domain learn --topic "…" --note "…" --url "…" --as-idea')
    print("Use every useful source — optimize for best product outcomes.")
    return 0


def cmd_products(data: Dict[str, Any]) -> int:
    for p in data.get("commercial_products") or []:
        print(f"\n## {p.get('name')}")
        print("Segments:", ", ".join(p.get("segments") or []))
        print("UI look:")
        for x in p.get("ui_look") or []:
            print(f"  - {x}")
        print("Functions:")
        for x in p.get("functions") or []:
            print(f"  - {x}")
    print("\nAdd products via learn notes or edit docs/knowledge/first_responder_wfm.json")
    return 0


def cmd_ui_patterns(data: Dict[str, Any]) -> int:
    ui = data.get("ui_ux_patterns") or {}
    print("First-responder scheduling UI / UX patterns (expand freely)")
    print("=" * 64)
    for section, items in ui.items():
        print(f"\n[{section}]")
        for x in items or []:
            print(f"  • {x}")
    print("\nCross-check: fr-domain explore · brainstorm")
    return 0


def cmd_flsa(data: Dict[str, Any]) -> int:
    pay = data.get("payroll_flsa") or {}
    print("First-responder payroll / FLSA (public sources — not legal advice)")
    print("=" * 64)
    k = pay.get("section_7k") or {}
    print("§7(k):", k.get("summary"))
    print("LE thresholds:", k.get("le_thresholds_approx"))
    print("Fire thresholds:", k.get("fire_thresholds_approx"))
    c = pay.get("comp_time") or {}
    print("\nComp time rate:", c.get("rate"))
    print("Public safety cap:", c.get("public_safety_cap_hours"), "hours")
    for n in c.get("notes") or []:
        print(f"  • {n}")
    print("\nCommon pay codes:")
    for code in pay.get("common_pay_codes") or []:
        print(f"  • {code}")
    print("\nPeriod ownership:", pay.get("period_ownership"))
    try:
        import logic

        print("\nLive get_flsa_settings():", logic.get_flsa_settings())
    except Exception as exc:
        print("\n(Live settings unavailable:", exc, ")")
    print("\nRelated ideas: fr-domain suggest --lane payroll")
    return 0


def cmd_search(data: Dict[str, Any], query: str) -> int:
    q = (query or "").strip().lower()
    if not q:
        print('Usage: fr-domain search "comp time"')
        return 1
    hits = []
    for path, text in _flatten_strings(data):
        if q in text.lower() or q in path.lower():
            hits.append((path, text[:220]))
    for it in load_idea_backlog():
        blob = f"{it.get('lane')} {it.get('idea')} {it.get('why')}".lower()
        if q in blob:
            hits.append((f"idea.{it.get('lane')}", it.get("idea") or ""))
    print(f"Search '{query}' — {len(hits)} hits")
    print("=" * 64)
    for path, text in hits[:80]:
        print(f"  {path}: {text}")
    if len(hits) > 80:
        print(f"  … +{len(hits) - 80} more")
    return 0


def cmd_compare(data: Dict[str, Any]) -> int:
    print("Industry patterns vs Chronos (not a ceiling — still brainstorm beyond this)")
    print("=" * 64)
    mapping = data.get("chronos_mapping") or {}
    print("\nHAVE in Chronos:")
    for x in mapping.get("have") or []:
        print(f"  ✓ {x}")
    print("\nPARTIAL:")
    for x in mapping.get("partial") or []:
        print(f"  ~ {x}")
    try:
        import logic

        checks = [
            ("open shifts", hasattr(logic, "create_open_shift")),
            ("bidding", hasattr(logic, "create_shift_bid_event")),
            ("gap board", hasattr(logic, "get_coverage_gap_board")),
            ("hours watch", hasattr(logic, "get_hours_watch")),
            ("OT ledger", hasattr(logic, "get_equitable_ot_ledger")),
            ("FLSA settings", hasattr(logic, "get_flsa_settings")),
            ("comp banks", hasattr(logic, "get_officer_time_banks")),
            ("lock pay period", hasattr(logic, "lock_pay_period")),
            ("callbacks", hasattr(logic, "get_callback_rotation")),
            ("certs", hasattr(logic, "get_officer_certifications")),
            ("CP-SAT bridge", hasattr(logic, "solve_staffing_feasibility") or True),
        ]
        print("\nLive logic probes:")
        for label, ok in checks:
            print(f"  {'✓' if ok else '✗'} {label}")
    except Exception as exc:
        print("logic probe failed:", exc)
    print("\nUI routes: / /open-shifts /bidding /callbacks /operations /timecards /payroll /time-off")
    print("Expand: fr-domain explore | brainstorm | suggest --all")
    return 0


def cmd_dig(data: Dict[str, Any], focus: str = "") -> int:
    """Deep mine KB + live Chronos + thin parity → implement priority (agent loop)."""
    focus = (focus or "").strip().lower()
    print("FR DIG — learn everything useful, then implement")
    print("=" * 72)
    print("Sources: docs/knowledge/first_responder_wfm.json + live logic + parity thin")
    print("Not legal advice. Expand with web_search any vendor/DOL/CBA/RFP.")
    print()

    # 1) Latest learnings
    learns = list(data.get("learnings") or [])
    print(f"## Learnings deposited: {len(learns)} (last 8)")
    for e in learns[-8:]:
        print(f"  • [{e.get('topic')}] {(e.get('note') or '')[:140]}")
        if e.get("url"):
            print(f"    {e.get('url')}")
    print()

    # 2) Commercial product function dump
    products = data.get("commercial_products") or []
    print(f"## Commercial products in KB: {len(products)}")
    for p in products:
        name = p.get("name") or p.get("id") or "?"
        fns = p.get("functions") or p.get("features") or []
        print(f"  [{name}] {len(fns)} functions catalogued")
        for f in fns[:6]:
            print(f"    - {f}")
    print()

    # 2b) Research frontiers — products/themes not yet fully deep-dived
    frontiers = (data.get("research_frontiers") or {}).get("priority_deep_dive") or []
    if frontiers:
        print(f"## Research frontiers (dig harder next): {len(frontiers)}")
        for item in frontiers[:12]:
            print(f"  ★ {item}")
        print("  → open_page product docs · RFP PDFs · NEOGOV/TeleStaff/ESO/Netchex")
        print("  → python dev.py source-deep sources · learn --as-idea")
        print()

    # 3) FLSA live
    flsa = data.get("payroll_flsa") or {}
    print("## FLSA / payroll (KB + live)")
    print(f"  LE thresholds: {flsa.get('law_enforcement_thresholds') or flsa.get('le_thresholds') or 'see flsa cmd'}")
    try:
        from logic import get_flsa_settings, get_pay_code_rules

        live = get_flsa_settings() or {}
        print(f"  Live work_period_days={live.get('work_period_days')} threshold={live.get('hours_threshold')}")
        rules = get_pay_code_rules() or {}
        g = rules.get("global") or {}
        print(
            f"  Pay codes: {len(rules.get('codes') or {})} · "
            f"callback_min={g.get('callback_minimum_hours')}h · "
            f"ot_mult={g.get('default_overtime_multiplier')}"
        )
    except Exception as exc:
        print(f"  (live probe skipped: {exc})")
    print()

    # 4) Thin Chronos gaps (implement queue)
    thin_names: List[str] = []
    try:
        from scripts.parity_audit import collect_hits

        thin_names = [h.name for h in collect_hits() if not h.in_gui]
    except Exception:
        thin_names = []
    print(f"## Chronos thin symbols (logic without gui wire): {len(thin_names)}")
    for n in thin_names[:20]:
        print(f"  • {n}")
    if len(thin_names) > 20:
        print(f"  … +{len(thin_names) - 20}")
    print()

    # 5) Priority implement map from industry → Chronos
    priorities = [
        (
            "payroll",
            "CBA pay-code knobs (holiday mult, callback min, OT mult)",
            "save_pay_code_rules + finance panel",
            "save_pay_code_rules" in thin_names or "Holiday" in focus or "payroll" in focus or not focus,
        ),
        (
            "self-service",
            "Shift bid participation report + award override",
            "get_shift_bid_participation_report / update_shift_bid_assignments",
            any(x in thin_names for x in ("get_shift_bid_participation_report", "update_shift_bid_assignments")),
        ),
        (
            "payroll",
            "Timecard scope view (period/year) like Extra Hours ledger",
            "get_timecard_entries_for_scope",
            "get_timecard_entries_for_scope" in thin_names,
        ),
        (
            "roster",
            "Title rate suggestions + period hours by officer",
            "suggested_hourly_rate_for_title / get_pay_period_hours_by_officer",
            any(x in thin_names for x in ("suggested_hourly_rate_for_title", "get_pay_period_hours_by_officer")),
        ),
        (
            "availability",
            "Unavailability check + holiday delete (blackout admin)",
            "is_officer_unavailable_on_date / delete_holiday",
            any(x in thin_names for x in ("is_officer_unavailable_on_date", "delete_holiday")),
        ),
        (
            "fairness",
            "OT equity / ODL / callback rotation (already partial — deepen)",
            "callbacks + equitable OT ledger on ops",
            True,
        ),
        (
            "court",
            "Court/subpoena path (inTime theme)",
            "leave types + future court calendar",
            "court" in focus or not focus,
        ),
        (
            "scheduling",
            "Holdover / Extra Hours reason codes (Aladtec pattern)",
            "payroll entry notes + open shift digests",
            "holdover" in focus or "extra" in focus or not focus,
        ),
    ]
    print("## Implement priority (industry gap × Chronos thin)")
    n = 0
    for lane, title, how, open_ in priorities:
        if focus and focus not in lane and focus not in title.lower() and focus not in how.lower():
            if open_ and not focus:
                pass
            elif focus and focus not in (lane, title.lower(), how.lower()):
                continue
        mark = "OPEN" if open_ else "watch"
        n += 1
        print(f"  {n}. [{lane}] {title}")
        print(f"     → {how}  ({mark})")
    print()

    # 6) Research queries agents should fire next
    print("## Next research queries (web_search / open_page)")
    queries = [
        "police department CBA court time minimum hours callout",
        "FLSA compensatory time 480 hour public safety cap",
        "Aladtec open shift signup mobile self service",
        "Snap Schedule seniority open shift fill rules",
        "inTime court subpoena police scheduling",
        "law enforcement overtime desired list ODL union",
        "fire department Kelly schedule staffing software minimum",
        "payroll export ADP police department timecard",
    ]
    if focus:
        queries = [f"{focus} first responder scheduling payroll"] + queries
    for i, q in enumerate(queries[:10], 1):
        print(f"  {i}. {q}")
    print()
    print("Also dig (any source — not vendor-only):")
    print("  GitHub solvers: Timefold, OR-Tools, Staffjoy, nurse rostering CP")
    print("  UI/code: NiceGUI AG Grid docs, Quasar dark, NOC dashboard UX, Bryntum Gantt")
    print("  Domain boundary: CAD/RMS standards (BJA LEITSC) vs WFM roster software")
    print("  HOW CODE IS WRITTEN: python dev.py source-deep sources|chronos|compare|lessons")
    print("  EVALUATE ALL PROGRAMS: python dev.py source-eval · source-eval implement")
    print("  python dev.py fr-domain code-deep · math-domain code-deep")
    print("  python dev.py ui-domain explore|learn · math-domain explore|learn")
    print("After web research:")
    print('  python dev.py fr-domain learn --topic "…" --note "…" --url "…" --as-idea --lane payroll')
    print('  python dev.py ui-domain learn --topic "…" --note "…" --url "…" --as-idea')
    print("  python dev.py fr-domain dig")
    print("  python dev.py enterprise-kit next")
    print("  implement · verify --tier fast")
    print("=" * 72)
    return 0


def cmd_learn(
    data: Dict[str, Any],
    *,
    topic: str,
    note: str,
    source: str = "",
    url: str = "",
    also_idea: bool = False,
    lane: str = "general",
) -> int:
    topic = (topic or "").strip() or "general"
    note = (note or "").strip()
    if not note:
        print('learn requires --note "..."')
        return 1
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "topic": topic,
        "note": note,
        "source": source or "",
        "url": url or "",
    }
    data.setdefault("learnings", []).append(entry)
    if len(data["learnings"]) > 800:
        data["learnings"] = data["learnings"][-800:]
    save_kb(data)
    if also_idea:
        save_idea(note[:200], lane=lane or topic, why=source or url or "learned")
    lines = [
        "# First-responder WFM — agent learnings log",
        "",
        "Append via `python dev.py fr-domain learn ...`. Summarize public sources only.",
        "",
    ]
    for e in (data.get("learnings") or [])[-40:]:
        lines.append(f"## {e.get('ts')} — {e.get('topic')}")
        lines.append(e.get("note") or "")
        if e.get("source") or e.get("url"):
            lines.append(f"_source: {e.get('source')} {e.get('url')}_")
        lines.append("")
    MD_MIRROR.write_text("\n".join(lines), encoding="utf-8")
    print(f"Learned ({topic}). Total learnings: {len(data['learnings'])}")
    if also_idea:
        print("Also added to idea backlog.")
    print(f"KB: {KB_PATH}")
    return 0


def cmd_add_idea(idea: str, lane: str, why: str) -> int:
    idea = (idea or "").strip()
    if not idea:
        print("add-idea requires --note or query text")
        return 1
    save_idea(idea, lane=lane or "general", why=why or "")
    print(f"Added idea [{lane}]: {idea}")
    print(f"Backlog: {IDEAS_PATH}")
    return 0


def run_fr_domain(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="First-responder WFM domain tool — broad exploration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python dev.py fr-domain explore
  python dev.py fr-domain brainstorm
  python dev.py fr-domain suggest --all
  python dev.py fr-domain suggest --lane fire
  python dev.py fr-domain research-queries "vacation bidding"
  python dev.py fr-domain add-idea --lane payroll --note "Court minimum 3 hours"
  python dev.py fr-domain learn --topic ui --note "..." --as-idea
""",
    )
    p.add_argument(
        "command",
        nargs="?",
        default="show",
        help="show|explore|brainstorm|suggest|lanes|products|ui-patterns|flsa|search|compare|learn|dig|research-queries|add-idea",
    )
    p.add_argument("query", nargs="*", help="Search terms / topic text")
    p.add_argument("--topic", default="")
    p.add_argument("--note", default="")
    p.add_argument("--source", default="")
    p.add_argument("--url", default="")
    p.add_argument("--lane", default="", help="Filter suggest / tag add-idea")
    p.add_argument("--all", action="store_true", dest="all_ideas", help="suggest: full backlog")
    p.add_argument("--limit", type=int, default=80)
    p.add_argument("--as-idea", action="store_true", help="learn: also push to idea backlog")
    args = p.parse_args(list(argv) if argv is not None else None)
    data = load_kb()
    cmd = (args.command or "show").replace("_", "-")
    qtext = " ".join(args.query).strip()

    if cmd == "show":
        return cmd_show(data)
    if cmd == "explore":
        return cmd_explore(data)
    if cmd == "brainstorm":
        return cmd_brainstorm(data)
    if cmd == "lanes":
        return cmd_lanes(data)
    if cmd == "products":
        return cmd_products(data)
    if cmd in ("ui-patterns", "ui"):
        return cmd_ui_patterns(data)
    if cmd == "flsa":
        return cmd_flsa(data)
    if cmd == "search":
        return cmd_search(data, qtext or args.note)
    if cmd == "compare":
        return cmd_compare(data)
    if cmd == "suggest":
        return cmd_suggest(data, lane=args.lane, all_ideas=args.all_ideas, limit=args.limit)
    if cmd in ("research-queries", "research", "queries"):
        return cmd_research_queries(data, qtext or args.topic or "first responder scheduling")
    if cmd in ("add-idea", "idea"):
        return cmd_add_idea(args.note or qtext, args.lane or "general", args.source)
    if cmd in ("learn", "learn-url"):
        return cmd_learn(
            data,
            topic=args.topic or ("url" if args.url else "general"),
            note=args.note or qtext,
            source=args.source,
            url=args.url,
            also_idea=args.as_idea,
            lane=args.lane or args.topic or "general",
        )
    if cmd in ("dig", "deep", "mine"):
        return cmd_dig(data, focus=qtext or args.topic or args.lane)
    if cmd in ("code-deep", "source-deep", "how-written"):
        from scripts.source_deep import run_source_deep

        sub = (qtext or "sources").split()[0] if qtext else "sources"
        return run_source_deep([sub])
    # Unknown command → help by exploring
    print(f"Unknown command '{cmd}' — running dig (deep research → implement).\n")
    return cmd_dig(data, focus=qtext or args.topic)


if __name__ == "__main__":
    raise SystemExit(run_fr_domain())
