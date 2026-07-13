"""One-shot: extract cli.py handlers into cli/*_cmds.py; thin cli.py keeps main().

Idempotent enough to re-run only if cli.py still has handler bodies (not re-run after split).
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = ROOT / "cli.py"

DOMAIN = {
    "request_cmds": [
        "_print_requests_table",
        "list_pending_requests",
        "list_requests",
        "approve_request",
        "reject_request",
        "submit_request_cmd",
    ],
    "swap_cmds": [
        "create_swap_cmd",
        "_print_swaps_table",
        "list_pending_swaps",
        "list_swaps",
        "approve_swap",
        "reject_swap",
    ],
    "notification_cmds": [
        "list_notifications",
        "read_notification",
        "read_all_notifications",
    ],
    "export_cmds": [
        "export_coverage",
        "export_schedule",
        "export_payroll",
        "export_requests",
        "export_swaps_pdf_cmd",
        "export_roster",
        "schedule_diff_cmd",
        "export_payroll_csv_cmd",
        "export_requests_csv_cmd",
        "export_pay_period_history_csv_cmd",
        "export_timecard_csv_cmd",
        "export_shift_swaps_csv_cmd",
        "export_ical_cmd",
    ],
    "user_cmds": [
        "list_users_cmd",
        "create_user_cmd",
        "update_user_cmd",
        "reset_user_password_cmd",
        "set_user_active_cmd",
    ],
    "ops_cmds": [
        "delete_holiday_cmd",
        "delete_availability_cmd",
        "get_setting_cmd",
        "set_setting_cmd",
        "staffing_settings_cmd",
        "rotation_settings_cmd",
        "backup_create",
        "backup_list_cmd",
        "backup_restore_cmd",
        "list_holidays",
        "add_holiday_cmd",
        "list_open_shifts",
        "post_open_shift",
        "fill_open_shift_cmd",
        "list_availability",
        "add_availability_cmd",
        "availability_conflicts_cmd",
        "assign_override_cmd",
    ],
    "payroll_cmds": [
        "pay_period_status",
        "pay_period_lock",
        "pay_period_unlock",
        "pay_period_history_cmd",
    ],
    "bid_cmds": [
        "list_shift_bids_cmd",
        "post_shift_bid_event_cmd",
        "submit_shift_bid_cmd",
        "reassign_shift_bid_cmd",
        "finalize_shift_bid_cmd",
        "show_shift_bid_cmd",
        "preview_shift_bid_cmd",
        "participation_shift_bid_cmd",
        "assignments_shift_bid_cmd",
        "import_sim_shift_bid_cmd",
    ],
    "callback_cmds": [
        "list_callbacks_cmd",
        "next_callback_cmd",
        "record_callback_cmd",
        "fatigue_report_cmd",
    ],
    "report_cmds": [
        "reports_labor_compliance",
        "reports_summary",
        "reports_coverage",
    ],
}

SKIP = {
    "args",
    "result",
    "data",
    "print",
    "getattr",
    "list",
    "dict",
    "str",
    "int",
    "float",
    "bool",
    "None",
    "True",
    "False",
    "range",
    "len",
    "min",
    "max",
    "sum",
    "enumerate",
    "zip",
    "sorted",
    "set",
    "tuple",
    "type",
    "Exception",
    "ValueError",
    "KeyError",
    "isinstance",
    "hasattr",
    "open",
    "super",
    "object",
    "property",
}


def names_loaded(fn_node: ast.AST) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(fn_node):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            out.add(node.id)
    return out


def main() -> int:
    src = SRC_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)

    funcs: dict[str, tuple[int, int]] = {}
    fn_nodes: dict[str, ast.FunctionDef] = {}
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name != "main":
            funcs[n.name] = (n.lineno, n.end_lineno or n.lineno)
            fn_nodes[n.name] = n

    if "list_pending_requests" not in funcs:
        print("cli.py already split (no handler bodies) — abort")
        return 1

    name_to_mod: dict[str, str] = {}
    for mod, names in DOMAIN.items():
        for n in names:
            name_to_mod[n] = mod

    missing = set(funcs) - set(name_to_mod)
    if missing:
        # ignore roster (already extracted)
        missing -= set()
        if missing:
            raise SystemExit(f"unmapped funcs: {sorted(missing)}")

    import_nodes = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    all_fn_names = set(funcs)

    for mod, names in DOMAIN.items():
        ordered = sorted(names, key=lambda n: funcs[n][0])
        used: set[str] = set()
        for name in ordered:
            used |= names_loaded(fn_nodes[name])
        local = set(names)

        needs_date = "date" in used
        from_logic: list[str] = []
        other_imports: list[str] = []
        cross: list[str] = []

        for n in import_nodes:
            if isinstance(n, ast.ImportFrom) and n.module == "logic":
                for a in n.names:
                    nm = a.asname or a.name
                    if nm in used and nm not in local:
                        from_logic.append(f"{a.name} as {a.asname}" if a.asname else a.name)
            elif isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("cli."):
                continue
            elif isinstance(n, ast.ImportFrom) and n.module:
                kept = []
                for a in n.names:
                    nm = a.asname or a.name
                    if nm in used and nm not in local:
                        kept.append(f"{a.name} as {a.asname}" if a.asname else a.name)
                if kept:
                    other_imports.append(f"from {n.module} import {', '.join(kept)}\n")
            elif isinstance(n, ast.Import):
                for a in n.names:
                    nm = a.asname or a.name
                    if nm in used:
                        other_imports.append(ast.get_source_segment(src, n) + "\n")

        # database import used by backup
        for n in import_nodes:
            if isinstance(n, ast.ImportFrom) and n.module == "database":
                kept = []
                for a in n.names:
                    nm = a.asname or a.name
                    if nm in used:
                        kept.append(a.name)
                if kept:
                    line = f"from database import {', '.join(kept)}\n"
                    if line not in other_imports:
                        other_imports.append(line)

        for sym in sorted(used):
            if sym in all_fn_names and name_to_mod.get(sym) != mod and sym not in local:
                cross.append(f"from cli.{name_to_mod[sym]} import {sym}\n")

        header = [
            f'"""CLI handlers — {mod.replace("_", " ")}."""\n',
            "\n",
            "from __future__ import annotations\n",
            "\n",
        ]
        out = "".join(header)
        if needs_date:
            out += "from datetime import date\n"
        for line in other_imports:
            out += line if line.endswith("\n") else line + "\n"
        if from_logic:
            # de-dupe preserve order
            seen = set()
            uniq = []
            for item in from_logic:
                if item not in seen:
                    seen.add(item)
                    uniq.append(item)
            out += "from logic import (\n"
            for item in uniq:
                out += f"    {item},\n"
            out += ")\n"
        for line in cross:
            out += line
        out += "\n"

        for name in ordered:
            s, e = funcs[name]
            chunk = "".join(lines[s - 1 : e])
            if not chunk.endswith("\n"):
                chunk += "\n"
            out += chunk + "\n\n"

        path = ROOT / "cli" / f"{mod}.py"
        path.write_text(out.rstrip() + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} funcs={len(ordered)} lines={len(out.splitlines())}")

    main_node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    main_src = "".join(lines[main_node.lineno - 1 : main_node.end_lineno])
    if_main_start = next(i for i, line in enumerate(lines) if line.startswith("if __name__"))
    if_main = "".join(lines[if_main_start:])

    new_cli = '''#!/usr/bin/env python3
"""
Dodgeville Police Department Scheduler - Admin CLI

Handlers live under cli/*_cmds.py. This module owns argparse + dispatch.
"""

from __future__ import annotations

import argparse

from cli.bid_cmds import (
    assignments_shift_bid_cmd,
    finalize_shift_bid_cmd,
    import_sim_shift_bid_cmd,
    list_shift_bids_cmd,
    participation_shift_bid_cmd,
    post_shift_bid_event_cmd,
    preview_shift_bid_cmd,
    reassign_shift_bid_cmd,
    show_shift_bid_cmd,
    submit_shift_bid_cmd,
)
from cli.callback_cmds import (
    fatigue_report_cmd,
    list_callbacks_cmd,
    next_callback_cmd,
    record_callback_cmd,
)
from cli.export_cmds import (
    export_coverage,
    export_ical_cmd,
    export_pay_period_history_csv_cmd,
    export_payroll,
    export_payroll_csv_cmd,
    export_requests,
    export_requests_csv_cmd,
    export_roster,
    export_schedule,
    export_shift_swaps_csv_cmd,
    export_swaps_pdf_cmd,
    export_timecard_csv_cmd,
    schedule_diff_cmd,
)
from cli.notification_cmds import (
    list_notifications,
    read_all_notifications,
    read_notification,
)
from cli.ops_cmds import (
    add_availability_cmd,
    add_holiday_cmd,
    assign_override_cmd,
    availability_conflicts_cmd,
    backup_create,
    backup_list_cmd,
    backup_restore_cmd,
    delete_availability_cmd,
    delete_holiday_cmd,
    fill_open_shift_cmd,
    get_setting_cmd,
    list_availability,
    list_holidays,
    list_open_shifts,
    post_open_shift,
    rotation_settings_cmd,
    set_setting_cmd,
    staffing_settings_cmd,
)
from cli.payroll_cmds import (
    pay_period_history_cmd,
    pay_period_lock,
    pay_period_status,
    pay_period_unlock,
)
from cli.report_cmds import reports_coverage, reports_labor_compliance, reports_summary
from cli.request_cmds import (
    approve_request,
    list_pending_requests,
    list_requests,
    reject_request,
    submit_request_cmd,
)
from cli.roster_cmds import dispatch_officers, register_officers_parser
from cli.swap_cmds import (
    approve_swap,
    create_swap_cmd,
    list_pending_swaps,
    list_swaps,
    reject_swap,
)
from cli.user_cmds import (
    create_user_cmd,
    list_users_cmd,
    reset_user_password_cmd,
    set_user_active_cmd,
    update_user_cmd,
)
from config import DAY_OFF_REQUEST_TYPES
from logic import (
    bulk_approve_auto_ok_requests,
    bulk_reject_pending_requests,
    export_audit_csv,
    get_audit_log,
    get_current_cycle_window,
    get_overtime_alerts,
    get_schedule_conflicts,
    sync_callback_rotation_from_roster,
)
from permissions import USER_ROLES
from validators import parse_date


'''
    new_cli += main_src + "\n\n\n" + if_main
    SRC_PATH.write_text(new_cli, encoding="utf-8")
    print(f"rewrote cli.py lines={len(new_cli.splitlines())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
