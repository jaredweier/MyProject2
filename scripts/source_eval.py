"""
Evaluate all catalogued FR scheduling/payroll *programs* against Chronos.

Maps product functions → Chronos capability (HAVE / PARTIAL / MISS) and
emits an implement queue of patterns that fit our architecture.

    python dev.py source-eval
    python dev.py source-eval --json
    python dev.py source-eval implement   # top implementable gaps
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

KB_PATH = ROOT / "docs" / "knowledge" / "first_responder_wfm.json"

# Keyword → Chronos capability probe (logic symbol or module hint)
CAPABILITY_MAP: List[Tuple[str, List[str], str]] = [
    # (capability_id, keywords in product function text, chronos_status_hint)
    ("rotation", ["rotation", "static schedule", "recurring", "pitman", "kelly"], "HAVE"),
    ("min_staffing", ["minimum staffing", "roster alarm", "min staffing", "coverage floor"], "HAVE"),
    ("vacancy_open_shift", ["open shift", "vacancy", "claim", "signup", "sign up"], "HAVE"),
    ("fatigue_rest", ["fatigue", "rest period", "hours between", "burnout"], "HAVE"),
    ("certs", ["certification", "credential", "qualification", "skill"], "HAVE"),
    ("bidding", ["shift bidding", "bid", "seniority award"], "HAVE"),
    ("trades", ["trade", "swap", "exchange", "giveaway"], "HAVE"),
    ("time_off", ["time-off", "time off", "leave", "pto"], "HAVE"),
    ("bulk_approve", ["auto-approve", "automatic approval", "bulk"], "HAVE"),
    ("flsa_7k", ["7(k)", "7k", "flsa", "work period", "171", "86h"], "HAVE"),
    ("comp_time", ["comp time", "compensatory", "comp bank"], "HAVE"),
    ("cash_vs_comp", ["cash", "convert overtime", "ot to comp", "election"], "HAVE"),
    ("payroll_export", ["payroll export", "export to payroll", "timesheet", "adp"], "PARTIAL"),
    ("ot_equity", ["ot equal", "fair ot", "overtime equity", "equalization", "odl"], "PARTIAL"),
    ("callback", ["callback", "call-out", "call out", "call-down", "mass call"], "PARTIAL"),
    ("notify_sms", ["text", "sms", "voice", "push notification", "phone tree"], "PARTIAL"),
    ("extra_duty", ["extra duty", "special detail", "off-duty", "special event", "invoice"], "HAVE"),
    ("court", ["court", "subpoena"], "PARTIAL"),
    ("mobile", ["mobile", "self-service", "phone"], "PARTIAL"),
    ("cad_rms", ["cad", "rms", "integration"], "PARTIAL"),
    ("dual_workforce", ["civilian", "dual", "sworn", "non-sworn", "40-hour", "40h"], "PARTIAL"),
    ("leave_donation", ["leave donation", "donate leave"], "HAVE"),
    ("station_post", ["station", "unit assignment", "multi-location", "post"], "PARTIAL"),
    ("immunization", ["immunization", "vaccine"], "HAVE"),
    ("geofence_clock", ["geofence", "geo-track", "clock-in", "punch"], "MISS"),
    ("blended_rate", ["blended rate", "regular rate"], "HAVE"),
    ("voice_notify", ["voice"], "MISS"),
]


def _load_kb() -> Dict[str, Any]:
    if not KB_PATH.is_file():
        return {}
    return json.loads(KB_PATH.read_text(encoding="utf-8"))


def _probe_chronos() -> Dict[str, str]:
    """Live probes where importable."""
    status: Dict[str, str] = {}
    try:
        from logic import (
            convert_overtime_to_comp,
            create_extra_duty_event,
            create_open_shift,
            create_shift_bid_event,
            get_equitable_ot_ledger,
            get_flsa_settings,
            list_extra_duty_events,
            officer_meets_shift_cert_requirements,
            preview_best_coverage_plans,
        )

        status["rotation"] = "HAVE"
        status["vacancy_open_shift"] = "HAVE"
        status["certs"] = "HAVE"
        status["bidding"] = "HAVE"
        status["flsa_7k"] = "HAVE"
        status["ot_equity"] = "HAVE"
        status["coverage_plans"] = "HAVE"
        status["extra_duty"] = "HAVE"
        status["cash_vs_comp"] = "HAVE"
        from logic import blended_regular_rate, donate_leave_hours, list_immunization_types

        status["leave_donation"] = "HAVE"
        status["blended_rate"] = "HAVE"
        status["immunization"] = "HAVE"
        status["station_post"] = "PARTIAL"
        status["payroll_export"] = "HAVE"
        flsa = get_flsa_settings() or {}
        status["dual_workforce"] = "PARTIAL" if "dual_workforce" in flsa else "MISS"
    except Exception as exc:
        status["_probe_error"] = str(exc)
    # Still need external vendors or deeper schema
    for miss in ("geofence_clock", "voice_notify"):
        status.setdefault(miss, "MISS")
    status.setdefault("notify_sms", "PARTIAL")
    status.setdefault("station_post", "PARTIAL")
    status.setdefault("dual_workforce", "PARTIAL")
    status.setdefault("court", "PARTIAL")
    return status


def evaluate_products(data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = data or _load_kb()
    products = data.get("commercial_products") or []
    live = _probe_chronos()
    rows: List[Dict[str, Any]] = []
    gap_counts: Dict[str, int] = {}

    for prod in products:
        name = prod.get("name") or "?"
        fns = prod.get("functions") or prod.get("features") or []
        text = " ".join(str(f) for f in fns).lower()
        hits: List[Dict[str, str]] = []
        for cap_id, keywords, default_status in CAPABILITY_MAP:
            if any(k in text for k in keywords):
                st = live.get(cap_id, default_status)
                hits.append({"capability": cap_id, "status": st})
                if st in ("MISS", "PARTIAL"):
                    gap_counts[cap_id] = gap_counts.get(cap_id, 0) + 1
        rows.append(
            {
                "product": name,
                "function_count": len(fns),
                "mapped": hits,
                "miss": [h["capability"] for h in hits if h["status"] == "MISS"],
                "partial": [h["capability"] for h in hits if h["status"] == "PARTIAL"],
            }
        )

    # Implement queue: capabilities that appear often as MISS/PARTIAL and fit Chronos
    IMPLEMENTABLE = {
        "extra_duty": {
            "priority": 1,
            "how": "logic extra_duty wrapper on open_shifts + ops panel; notes EXTRA_DUTY",
            "sources": "TeleStaff, Netchex, PowerTime",
        },
        "cash_vs_comp": {
            "priority": 2,
            "how": "convert_overtime_to_comp() + UI button (NEOGOV pattern)",
            "sources": "NEOGOV, public-sector payroll",
        },
        "dual_workforce": {
            "priority": 3,
            "how": "department settings civilian_work_period_days + dual threshold display",
            "sources": "Netchex, NEOGOV",
        },
        "notify_sms": {
            "priority": 4,
            "how": "keep open-shift-digest + create_notification; optional email webhook later",
            "sources": "TeleStaff, Vector, Snap",
        },
        "ot_equity": {
            "priority": 5,
            "how": "equitable OT ledger already — deepen UI export",
            "sources": "CrewSense, Snap, PowerTime",
        },
        "payroll_export": {
            "priority": 6,
            "how": "export_payroll_pdf + CSV already wired",
            "sources": "PowerTime, eSchedule, NEOGOV",
        },
        "leave_donation": {
            "priority": 8,
            "how": "needs new bank transfer ledger (schema)",
            "sources": "NEOGOV",
        },
        "court": {
            "priority": 7,
            "how": "leave types + court status colors exist — deepen calendar",
            "sources": "inTime",
        },
    }

    queue = []
    for cap, meta in sorted(IMPLEMENTABLE.items(), key=lambda kv: kv[1]["priority"]):
        queue.append(
            {
                "capability": cap,
                "gap_mentions": gap_counts.get(cap, 0),
                "live_status": live.get(cap, "UNKNOWN"),
                **meta,
            }
        )

    return {
        "product_count": len(products),
        "products": rows,
        "gap_counts": gap_counts,
        "implement_queue": queue,
        "live": live,
        "frontiers": (data.get("research_frontiers") or {}).get("priority_deep_dive") or [],
    }


def cmd_show(as_json: bool = False) -> int:
    result = evaluate_products()
    if as_json:
        print(json.dumps(result, indent=2)[:50000])
        return 0
    print("SOURCE EVAL — catalogued programs vs Chronos")
    print("=" * 72)
    print(f"Products evaluated: {result['product_count']}")
    print()
    print("## Per-product mapped capabilities (gaps only)")
    for p in result["products"]:
        miss = p.get("miss") or []
        part = p.get("partial") or []
        if not miss and not part:
            print(f"  [{p['product']}] mostly covered ({p['function_count']} fns)")
            continue
        print(f"  [{p['product']}]")
        if miss:
            print(f"      MISS: {', '.join(miss)}")
        if part:
            print(f"      PART: {', '.join(part)}")
    print()
    print("## Gap frequency (how many products mention it)")
    for cap, n in sorted(result["gap_counts"].items(), key=lambda kv: -kv[1]):
        print(f"  {cap}: {n}")
    print()
    print("## Implement queue (fits Chronos architecture)")
    for i, item in enumerate(result["implement_queue"], 1):
        print(f"  {i}. [{item['live_status']}] {item['capability']}  (mentions={item['gap_mentions']})")
        print(f"      {item['how']}")
        print(f"      from: {item['sources']}")
    if result.get("frontiers"):
        print()
        print("## Research frontiers still open")
        for f in result["frontiers"][:8]:
            print(f"  ★ {f}")
    print()
    print("Next: python dev.py source-eval implement")
    return 0


def cmd_implement() -> int:
    """Print concrete code targets for top gaps (agent checklist)."""
    result = evaluate_products()
    print("IMPLEMENT FROM EVALUATED PROGRAMS")
    print("=" * 72)
    for item in result["implement_queue"][:6]:
        if item["live_status"] == "HAVE":
            continue
        print(f"\n### {item['capability']}  [{item['live_status']}]")
        print(f"  how: {item['how']}")
        print(f"  sources: {item['sources']}")
        if item["capability"] == "extra_duty":
            print("  code: logic/extra_duty.py · gui/pages/operations.py panel")
            print("  pattern: TeleStaff plan/staff/track; use open_shifts + EXTRA_DUTY notes")
        elif item["capability"] == "cash_vs_comp":
            print("  code: logic/payroll.convert_overtime_to_comp · finance _add_entry")
        elif item["capability"] == "dual_workforce":
            print("  code: labor_compliance dual settings · finance _flsa_panel")
        elif item["capability"] == "ot_equity":
            print("  code: operations OT ledger CSV export")
    print("\nAfter edits: verify --tier fast · source-eval")
    return 0


def run_source_eval(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Evaluate catalogued FR programs vs Chronos")
    p.add_argument("command", nargs="?", default="show", help="show|implement")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(list(argv) if argv is not None else None)
    cmd = (args.command or "show").replace("_", "-")
    if cmd in ("show", "eval", "evaluate"):
        return cmd_show(as_json=args.json)
    if cmd in ("implement", "queue", "next"):
        return cmd_implement()
    return cmd_show(as_json=args.json)


if __name__ == "__main__":
    raise SystemExit(run_source_eval())
