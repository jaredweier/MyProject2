"""
Enterprise software acceleration kit for Chronos.

Surfaces patterns, scaffolds GUI pages that wire existing logic.*, recipes,
and implement queues so agents ship enterprise features faster.

    python dev.py enterprise-kit
    python dev.py enterprise-kit patterns
    python dev.py enterprise-kit thin          # parity thin → implement queue
    python dev.py enterprise-kit next          # top thin + recipe steps
    python dev.py enterprise-kit wire <symbol> # copy-paste import + call sketch
    python dev.py enterprise-kit scaffold --name court --title "Court calendar"
    python dev.py enterprise-kit recipe coverage-override
"""

from __future__ import annotations

import argparse
import inspect
import re
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PATTERNS: List[Dict[str, str]] = [
    {
        "id": "rbac-gate",
        "title": "Permission-gated page",
        "how": "session.can('perm') at top of render; hide nav via ROUTE_PERMS in gui/shell.py",
    },
    {
        "id": "logic-wire",
        "title": "Logic-first feature",
        "how": "enterprise-kit thin → wire SYMBOL → import from logic → form/panel → refreshable list",
    },
    {
        "id": "audit-trail",
        "title": "Audit every mutation",
        "how": "logic already logs many actions; UI should call logic mutators not raw SQL",
    },
    {
        "id": "notify",
        "title": "In-app notification on event",
        "how": "create_notification(officer_id, type, title, message) after approve/fill/post",
    },
    {
        "id": "export",
        "title": "One-click export",
        "how": "export_*_csv/pdf/ical with path in notify — Ops exports panel pattern",
    },
    {
        "id": "explain",
        "title": "Explainable decisions",
        "how": "logic.plan_explain / score dialogs before approve (supervisor trust)",
    },
    {
        "id": "grid",
        "title": "Enterprise data grid",
        "how": "gui.tables.aggrid_from_dicts(rows, prefer_columns=[...])",
    },
    {
        "id": "cmdk",
        "title": "Command palette jump",
        "how": "Add path to NAV + _install_command_palette extras in shell.py",
    },
    {
        "id": "digest",
        "title": "Batch notify / job",
        "how": "scripts/*_digest.py + dev.py command + optional UI button",
    },
    {
        "id": "scaffold",
        "title": "New Chronos page scaffold",
        "how": "python dev.py enterprise-kit scaffold --name foo --title 'Foo'",
    },
    {
        "id": "open-research",
        "title": "Research before invent",
        "how": "ui-domain|fr-domain|math-domain explore + research-queries + web_search any source",
    },
    {
        "id": "period-lock",
        "title": "Period close / lock",
        "how": "lock_pay_period after ledger review — finance panel pattern",
    },
    {
        "id": "self-service",
        "title": "Role-split UX",
        "how": "session.is_officer() thin home; supervisors get queues + bulk",
    },
    {
        "id": "certs-gate",
        "title": "Qualification gate",
        "how": "officer_meets_shift_cert_requirements before fill_open_shift",
    },
    {
        "id": "form-preview",
        "title": "Calc / impact preview before save",
        "how": "Call pure calc (calculate_pay_for_entry / plan_explain) → show result → then mutate",
    },
    {
        "id": "snapshot-diff",
        "title": "Base vs live compare",
        "how": "compare_base_updated_schedule(year, month) → AG Grid of diffs",
    },
    {
        "id": "manual-coverage",
        "title": "Supervisor override assign",
        "how": "create_manual_coverage_override(orig, repl, date, reason) + refresh matrix",
    },
    {
        "id": "ledger-crud",
        "title": "Period ledger list + add",
        "how": "get_*_entries(period) grid + create_* form with period lock guard",
    },
    {
        "id": "bank-activity",
        "title": "Bank balance + transaction drill-down",
        "how": "get_banked_time_summary + get_bank_transactions(bank_type, scope)",
    },
    {
        "id": "cli-parity",
        "title": "CLI for every supervisor mutation",
        "how": "cli.py thin wrapper over same logic.* used by GUI",
    },
    {
        "id": "verify-ladder",
        "title": "Ship with honest gates",
        "how": "verify --tier fast after edit · check before done (logic/ui/database)",
    },
]

RECIPES: Dict[str, Dict[str, Any]] = {
    "coverage-override": {
        "title": "Manual coverage assignment",
        "logic": ["create_manual_coverage_override", "get_officers_by_seniority"],
        "ui": "gui/pages/schedules.py · Live schedule panel",
        "perm": "schedule.updated.edit",
        "steps": [
            "Officer selects: original, replacement, date, reason",
            "Call create_manual_coverage_override(... , actor_user_id=session user)",
            "Refresh matrix + notify on success",
        ],
    },
    "schedule-diff": {
        "title": "Base vs live schedule diff",
        "logic": ["compare_base_updated_schedule", "get_schedule_snapshot"],
        "ui": "gui/pages/schedules.py · Monthly or Live",
        "perm": "schedule.updated.view",
        "steps": [
            "compare_base_updated_schedule(year, month)",
            "Show diff_count + AG Grid of diffs",
            "Optional: get_schedule_snapshot for publish status",
        ],
    },
    "payroll-ledger-crud": {
        "title": "Payroll entries + calc preview",
        "logic": ["create_payroll_entry", "get_payroll_entries", "calculate_pay_for_entry"],
        "ui": "gui/pages/finance · Payroll tab",
        "perm": "payroll.edit",
        "steps": [
            "List get_payroll_entries(period_start=...)",
            "Form + Preview via calculate_pay_for_entry",
            "Save create_payroll_entry (respects pay period lock)",
        ],
    },
    "bank-ledger": {
        "title": "Comp/sick bank transactions",
        "logic": ["get_banked_time_summary", "get_bank_transactions"],
        "ui": "gui/pages/finance · Timecards Banked Time",
        "perm": "timecard.view_own / view_all",
        "steps": ["Summary cards from get_banked_time_summary", "Transaction grid by bank_type"],
    },
    "notifications-inbox": {
        "title": "Alerts inbox",
        "logic": ["get_notifications", "mark_notification_read", "create_notification"],
        "ui": "/notifications",
        "steps": ["Already scaffolded — deepen filters/types"],
    },
    "open-shift-digest": {
        "title": "Vacancy broadcast",
        "logic": ["list open shifts", "create_notification"],
        "ui": "Ops / Open shifts + python dev.py open-shift-digest",
        "steps": ["Dry-run digest", "Post in-app notifications to active officers"],
    },
    "page-scaffold": {
        "title": "New enterprise page",
        "logic": [],
        "ui": "gui/pages/<name>.py",
        "steps": [
            "enterprise-kit scaffold --name X --title '…'",
            "Wire app.py route + shell NAV + ROUTE_PERMS",
            "Import logic.* and build form/list",
        ],
    },
}

# Thin symbols that unblock the most LE enterprise depth first
PRIORITY_SYMBOLS: List[str] = [
    "create_manual_coverage_override",
    "compare_base_updated_schedule",
    "get_schedule_snapshot",
    "create_payroll_entry",
    "get_payroll_entries",
    "calculate_pay_for_entry",
    "get_banked_time_summary",
    "get_bank_transactions",
    "get_monthly_summary_from_snapshot",
]


def cmd_patterns() -> int:
    print("Enterprise patterns (implement faster)")
    print("=" * 64)
    for p in PATTERNS:
        print(f"  [{p['id']}] {p['title']}")
        print(f"      {p['how']}")
    print("=" * 64)
    print("Recipes: python dev.py enterprise-kit recipe <name>")
    print("Names:", ", ".join(RECIPES))
    return 0


def _thin_hits():
    from scripts.parity_audit import collect_hits

    return [h for h in collect_hits() if not h.in_gui]


def cmd_thin() -> int:
    """Parity thin symbols → implement queue with recipe hints."""
    thin = _thin_hits()
    print("Enterprise implement queue (logic thin in Chronos gui/)")
    print("=" * 64)
    by: Dict[str, List[str]] = {}
    for h in thin:
        by.setdefault(h.slice_id, []).append(h.name)
    slice_recipe = {
        "schedules": "coverage-override / schedule-diff",
        "payroll-timecard": "payroll-ledger-crud / bank-ledger",
        "notifications": "notifications-inbox",
        "day-off-requests": "explain plans (plan_explain)",
        "exports-ical": "export pattern",
    }
    for sid, names in sorted(by.items(), key=lambda kv: -len(kv[1])):
        hint = slice_recipe.get(sid, "logic-wire pattern")
        print(f"\n[{sid}] → recipe hint: {hint}")
        for n in names[:15]:
            pri = " ★" if n in PRIORITY_SYMBOLS else ""
            print(f"  • {n}{pri}")
        if len(names) > 15:
            print(f"  … +{len(names) - 15}")
    print("\n" + "=" * 64)
    print(f"Thin count: {len(thin)}  ·  ★ = priority LE depth")
    print("Next batch:  python dev.py enterprise-kit next")
    print("Wire symbol: python dev.py enterprise-kit wire <name>")
    print("Scaffold:    python dev.py enterprise-kit scaffold --name X --title '…'")
    print("Research:    ui-domain|fr-domain|math-domain explore")
    return 0


def cmd_next(limit: int = 8) -> int:
    """Top priority thin symbols with recipe steps — agent implement order."""
    thin_names = {h.name for h in _thin_hits()}
    print("Enterprise next implement batch (priority thin still open)")
    print("=" * 64)
    shown = 0
    for name in PRIORITY_SYMBOLS:
        if name not in thin_names:
            continue
        recipe_id = None
        for rid, r in RECIPES.items():
            if name in (r.get("logic") or []):
                recipe_id = rid
                break
        print(f"\n{shown + 1}. {name}")
        if recipe_id:
            r = RECIPES[recipe_id]
            print(f"   recipe: {recipe_id} — {r['title']}")
            print(f"   ui: {r.get('ui')}")
            for s in (r.get("steps") or [])[:4]:
                print(f"   • {s}")
        else:
            print("   pattern: logic-wire")
        print(f"   sketch: python dev.py enterprise-kit wire {name}")
        shown += 1
        if shown >= limit:
            break
    # Fill with other thin if priority exhausted
    if shown < limit:
        for h in _thin_hits():
            if h.name in PRIORITY_SYMBOLS:
                continue
            print(f"\n{shown + 1}. {h.name}  [{h.slice_id}]")
            print(f"   sketch: python dev.py enterprise-kit wire {h.name}")
            shown += 1
            if shown >= limit:
                break
    if shown == 0:
        print("No priority thin left — run enterprise-kit thin for remainder.")
    else:
        print("\n" + "=" * 64)
        print(f"Implement {shown} above · verify --tier fast after batch")
    return 0


def cmd_wire(symbol: str) -> int:
    """Print import + call sketch for a logic symbol (speeds GUI wiring)."""
    name = (symbol or "").strip()
    if not name:
        print("Usage: enterprise-kit wire <symbol>")
        return 1
    try:
        import logic as logic_pkg

        fn = getattr(logic_pkg, name, None)
    except Exception as exc:
        print(f"Cannot import logic: {exc}")
        return 1
    if fn is None or not callable(fn):
        # try nested modules via symbol tool path
        print(f"Not on logic package surface: {name}")
        print("Try: python dev.py symbol", name)
        return 1
    try:
        sig = str(inspect.signature(fn))
    except (TypeError, ValueError):
        sig = "(...)"
    doc = (inspect.getdoc(fn) or "").splitlines()
    doc1 = doc[0] if doc else ""
    print(f"Wire: {name}{sig}")
    if doc1:
        print(f"  # {doc1}")
    print()
    print("from logic import (")
    print(f"    {name},")
    print(")")
    print()
    # Heuristic form sketch
    params = []
    try:
        for p in inspect.signature(fn).parameters.values():
            if p.name in ("self", "cls"):
                continue
            if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
                continue
            params.append(p)
    except (TypeError, ValueError):
        params = []
    print("# NiceGUI sketch")
    print("def do_action():")
    args_parts = []
    for p in params:
        if p.default is inspect.Parameter.empty:
            args_parts.append(f"    {p.name}=...,  # required")
        else:
            args_parts.append(f"    # {p.name}={p.default!r}")
    if args_parts:
        print(f"    r = {name}(")
        for a in args_parts:
            print(a)
        print("    )")
    else:
        print(f"    r = {name}()")
    print("    if isinstance(r, dict) and r.get('success') is False:")
    print("        ui.notify(r.get('message', 'Failed'), type='negative')")
    print("        return")
    print("    ui.notify(r.get('message', 'Done') if isinstance(r, dict) else 'Done', type='positive')")
    print("    refresh()")
    print()
    # Recipe link
    for rid, r in RECIPES.items():
        if name in (r.get("logic") or []):
            print(f"Recipe: enterprise-kit recipe {rid}")
            break
    return 0


def cmd_recipe(name: str) -> int:
    r = RECIPES.get(name)
    if not r:
        print("Unknown recipe. Choose:")
        for k, v in RECIPES.items():
            print(f"  {k}: {v['title']}")
        return 1
    print(f"Recipe: {name} — {r['title']}")
    print("=" * 64)
    print("Logic APIs:", ", ".join(r.get("logic") or []))
    print("UI target:", r.get("ui"))
    if r.get("perm"):
        print("Permission:", r["perm"])
    print("Steps:")
    for s in r.get("steps") or []:
        print(f"  • {s}")
    for sym in r.get("logic") or []:
        print(f"\nSketch: python dev.py enterprise-kit wire {sym}")
        break
    print("\nAfter implement: python dev.py enterprise-kit thin · verify --tier fast")
    return 0


def cmd_scaffold(name: str, title: str, route: str = "") -> int:
    """Generate gui/pages/<name>.py stub + print wiring instructions."""
    slug = re.sub(r"[^a-z0-9_]+", "_", (name or "").lower()).strip("_")
    if not slug:
        print("scaffold needs --name")
        return 1
    title = title or slug.replace("_", " ").title()
    route = route or f"/{slug.replace('_', '-')}"
    path = ROOT / "gui" / "pages" / f"{slug}.py"
    if path.exists():
        print(f"Exists: {path} — not overwriting")
        return 1
    fn = f"render_{slug}"
    content = textwrap.dedent(
        f'''\
        """{title} — Chronos page (enterprise-kit scaffold)."""

        from __future__ import annotations

        from nicegui import ui

        from gui import session
        from gui.shell import layout, page_header, panel


        def {fn}() -> None:
            def body() -> None:
                page_header(
                    "{title}",
                    "Wire logic.* APIs here · permission-gate as needed",
                    kicker="Enterprise",
                )
                # if not session.can("…"):
                #     ui.html('<div class="alert alert-warn">Permission required.</div>', sanitize=False)
                #     return
                with panel("{title}", glow=True):
                    ui.label("TODO: import logic functions and build form/list.").classes(
                        "text-sm text-gray-400"
                    )
                    ui.button("Refresh", on_click=lambda: ui.notify("wire me")).classes(
                        "btn-ghost"
                    ).props("no-caps outline dense")

            layout("{slug}", body)
        '''
    )
    path.write_text(content, encoding="utf-8")
    print(f"Wrote {path}")
    print("Wire next:")
    print(f"  1. gui/app.py: from gui.pages.{slug} import {fn}")
    print(f'  2. @ui.page("{route}") def page_{slug}(): {fn}()')
    print("  3. gui/shell.py NAV + optional ROUTE_PERMS + command palette")
    print("  4. Implement body with logic.* — see enterprise-kit thin / recipe")
    return 0


def cmd_show() -> int:
    print("Enterprise kit — accelerate Chronos to enterprise depth")
    print("=" * 64)
    print("patterns     — reusable implementation patterns")
    print("thin         — parity-audit thin symbols as implement queue")
    print("next         — priority LE thin batch + recipe steps")
    print("wire SYM     — copy-paste import + NiceGUI call sketch")
    print("recipe X     — step-by-step for common enterprise features")
    print("scaffold     — generate gui/pages/<name>.py stub")
    print()
    print("Also open research:")
    print("  python dev.py ui-domain|fr-domain|math-domain explore")
    print("  python dev.py parity-audit")
    print("  python dev.py le-benchmark")
    print()
    print("Loop: thin → next → wire → edit → verify --tier fast → thin")
    return 0


def run_enterprise_kit(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Enterprise acceleration kit")
    p.add_argument(
        "command",
        nargs="?",
        default="show",
        help="show|patterns|thin|next|wire|recipe|scaffold",
    )
    p.add_argument("recipe_name", nargs="?", default="", help="recipe name or wire symbol")
    p.add_argument("--name", default="")
    p.add_argument("--title", default="")
    p.add_argument("--route", default="")
    p.add_argument("--limit", type=int, default=8)
    args = p.parse_args(list(argv) if argv is not None else None)
    cmd = (args.command or "show").replace("_", "-")
    if cmd == "show":
        return cmd_show()
    if cmd == "patterns":
        return cmd_patterns()
    if cmd == "thin":
        return cmd_thin()
    if cmd == "next":
        return cmd_next(limit=args.limit or 8)
    if cmd == "wire":
        return cmd_wire(args.recipe_name or args.name or "")
    if cmd == "recipe":
        return cmd_recipe(args.recipe_name or args.name or "")
    if cmd == "scaffold":
        return cmd_scaffold(args.name or args.recipe_name, args.title, args.route)
    print("Unknown command — try patterns|thin|next|wire|recipe|scaffold")
    return cmd_show()


if __name__ == "__main__":
    raise SystemExit(run_enterprise_kit())
