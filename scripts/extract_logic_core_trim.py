#!/usr/bin/env python3
"""Extract logic/_core.py into logic/exports.py and logic/dashboard.py."""

from __future__ import annotations

import ast
import os
import textwrap
from typing import Dict, FrozenSet, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE_PATH = os.path.join(ROOT, "logic", "_core.py")
PKG = os.path.join(ROOT, "logic")

EXPORT_FUNCS = frozenset(
    {
        "export_schedule_pdf",
        "export_audit_csv",
        "export_coverage_pdf",
        "export_officer_schedule_ical",
        "export_pay_period_history_csv",
        "export_pay_stub_pdf",
        "export_payroll_csv",
        "export_payroll_pdf",
        "export_requests_csv",
        "export_requests_pdf",
        "export_roster_csv",
        "export_schedule_diff_csv",
        "export_shift_swaps_csv",
        "export_shift_swaps_pdf",
        "export_simulation_csv",
        "export_timecard_csv",
    }
)

DASHBOARD_FUNCS = frozenset(
    {
        "get_audit_log",
        "get_coverage_report",
        "get_coverage_gap_board",
        "get_hours_watch",
        "get_equitable_ot_ledger",
        "get_dashboard_insights",
        "get_department_pay_summary",
        "get_labor_budget_status",
        "get_labor_cost_forecast",
        "get_overtime_alerts",
        "get_payroll_ytd",
    }
)

EXPORTS_HEADER = (
    textwrap.dedent('''
    """PDF, CSV, and iCal export wrappers (exports-ical slice)."""

    import os
    from datetime import date
    from typing import Dict, Optional

    from validators import format_date
    from logic.officers import get_officer_by_id
    from logic.scheduling import build_schedule_matrix, get_current_cycle_window
    from logic.snapshots import get_officer_schedule_window
    from logic.payroll import get_pay_period, get_payroll_entries, get_pay_stub_preview
''').strip()
    + "\n"
)

DASHBOARD_HEADER = (
    textwrap.dedent('''
    """Dashboard and analytics delegates (dashboard + reports slices)."""

    from datetime import date
    from typing import Dict, List, Optional

    from database import get_connection
    from logic.officers import get_officers_by_seniority
    from logic.payroll import project_officer_annual_pay
''').strip()
    + "\n"
)

CORE_SHIM = (
    textwrap.dedent('''
    """
    Backward-compat shim — exports and dashboard moved to slice modules.
    Prefer importing from logic.exports or logic.dashboard directly.
    """

    from logic.exports import *
    from logic.dashboard import *
''').strip()
    + "\n"
)

INIT_TEMPLATE = (
    textwrap.dedent('''
    """
    Dodgeville Police Department Scheduler — Core Business Logic (package).
    """

    from logic.officers import *
    from logic.scheduling import *
    from logic.users import *
    from logic.payroll import *
    from logic.snapshots import *
    from logic.operations import *
    from logic.exports import *
    from logic.dashboard import *
    from logic.requests import *
    from logic.snapshots import _insert_override_record
''').strip()
    + "\n"
)


def _function_ranges(source: str) -> Dict[str, Tuple[int, int]]:
    tree = ast.parse(source)
    return {
        node.name: (node.lineno, node.end_lineno or node.lineno)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def _extract_functions(
    lines: List[str],
    ranges: Dict[str, Tuple[int, int]],
    names: FrozenSet[str],
) -> str:
    bodies: List[str] = []
    for name, (start, end) in sorted(ranges.items(), key=lambda x: x[1][0]):
        if name in names:
            bodies.append("".join(lines[start - 1 : end]))
    return "\n".join(b.rstrip("\n") for b in bodies) + ("\n" if bodies else "")


def main() -> int:
    with open(CORE_PATH, encoding="utf-8") as fh:
        source = fh.read()
    lines = source.splitlines(keepends=True)
    ranges = _function_ranges(source)

    missing = (EXPORT_FUNCS | DASHBOARD_FUNCS) - set(ranges)
    if missing:
        raise SystemExit(f"Missing functions in _core.py: {sorted(missing)}")

    exports_body = _extract_functions(lines, ranges, EXPORT_FUNCS)
    dashboard_body = _extract_functions(lines, ranges, DASHBOARD_FUNCS)

    exports_path = os.path.join(PKG, "exports.py")
    dashboard_path = os.path.join(PKG, "dashboard.py")
    with open(exports_path, "w", encoding="utf-8") as fh:
        fh.write(EXPORTS_HEADER + "\n" + exports_body)
    with open(dashboard_path, "w", encoding="utf-8") as fh:
        fh.write(DASHBOARD_HEADER + "\n" + dashboard_body)
    with open(CORE_PATH, "w", encoding="utf-8") as fh:
        fh.write(CORE_SHIM)
    with open(os.path.join(PKG, "__init__.py"), "w", encoding="utf-8") as fh:
        fh.write(INIT_TEMPLATE)

    print(f"Wrote {exports_path} ({len(EXPORT_FUNCS)} symbols)")
    print(f"Wrote {dashboard_path} ({len(DASHBOARD_FUNCS)} symbols)")
    print(f"Trimmed {CORE_PATH} to shim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
