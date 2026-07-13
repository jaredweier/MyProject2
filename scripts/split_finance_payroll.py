"""One-shot architecture split: finance UI + logic/payroll packages.

Preserves public import paths:
  from gui.pages.finance import render_timecards, render_payroll
  from logic.payroll import get_pay_period, save_timecard_entry, ...
  import logic  (star-reexport unchanged)

Run once from repo root: python scripts/split_finance_payroll.py
"""

from __future__ import annotations

import ast
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines(keepends=True)


def _slice(lines: list[str], start: int, end: int) -> str:
    """1-indexed inclusive line slice."""
    return "".join(lines[start - 1 : end])


def _func_ranges(src: str) -> dict[str, tuple[int, int]]:
    tree = ast.parse(src)
    out: dict[str, tuple[int, int]] = {}
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[n.name] = (n.lineno, n.end_lineno or n.lineno)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    out[t.id] = (n.lineno, n.end_lineno or n.lineno)
    return out


def split_finance() -> None:
    src_path = ROOT / "gui" / "pages" / "finance.py"
    if not src_path.is_file():
        # already a package?
        if (ROOT / "gui" / "pages" / "finance" / "__init__.py").is_file():
            print("finance package already present — skip UI split")
            return
        raise SystemExit(f"missing {src_path}")

    lines = _lines(src_path)
    src = "".join(lines)
    ranges = _func_ranges(src)

    pkg = ROOT / "gui" / "pages" / "finance"
    if pkg.exists():
        shutil.rmtree(pkg)
    pkg.mkdir(parents=True)

    # Shared header for each module
    common_imports = '''"""Finance NiceGUI pages — split from monolith for maintainability."""
from __future__ import annotations

from nicegui import ui

from gui import session
from gui.shell import finance_subnav, layout, page_header, panel
from config import FLSA_COMP_TIME_MAX_HOURS
from logic import (
    calculate_pay_for_entry,
    count_pay_periods_in_year,
    convert_overtime_to_comp,
    create_payroll_entry,
    donate_leave_hours,
    export_adp_payroll_pack,
    export_payroll_pdf,
    format_pay_period_label,
    list_leave_donations,
    get_bank_transactions,
    get_banked_time_summary,
    get_flsa_settings,
    get_officer_by_id,
    get_officer_time_banks,
    get_officers_by_seniority,
    get_overtime_alerts,
    get_pay_code_rules,
    get_pay_period,
    get_pay_period_hours_summary,
    get_payroll_entries,
    get_payroll_period_timesheets,
    get_timecard_period,
    is_current_pay_period,
    list_pay_periods_catalog,
    lock_pay_period,
    prefill_timecard_from_schedule,
    get_timecard_entries_for_scope,
    save_flsa_settings,
    save_pay_code_rules,
    save_timecard_entry,
    search_pay_period_by_date,
)
from validators import format_date, parse_date

'''

    modules: dict[str, list[str]] = {
        "banks": ["_resolve_bank_officer_id", "_banks"],
        "ledger": ["_payroll_entries_panel", "_payroll_entry_form", "_ledger"],
        "timecards": [
            "render_timecards",
            "_period_catalog",
            "_timecard_scope_panel",
            "_add_entry",
            "_timecard",
            "render_finance",
        ],
        "payroll_page": [
            "render_payroll",
            "_pay_code_rules_panel",
            "_flsa_panel",
        ],
    }

    # banks first (no internal deps)
    banks_body = common_imports
    for name in modules["banks"]:
        s, e = ranges[name]
        banks_body += _slice(lines, s, e) + "\n\n"
    (pkg / "banks.py").write_text(banks_body.rstrip() + "\n", encoding="utf-8")

    ledger_body = common_imports
    for name in modules["ledger"]:
        s, e = ranges[name]
        ledger_body += _slice(lines, s, e) + "\n\n"
    (pkg / "ledger.py").write_text(ledger_body.rstrip() + "\n", encoding="utf-8")

    timecards_body = common_imports
    timecards_body += "from gui.pages.finance.banks import _banks\n\n"
    for name in modules["timecards"]:
        s, e = ranges[name]
        timecards_body += _slice(lines, s, e) + "\n\n"
    (pkg / "timecards.py").write_text(timecards_body.rstrip() + "\n", encoding="utf-8")

    payroll_body = common_imports
    payroll_body += "from gui.pages.finance.ledger import _ledger, _payroll_entries_panel, _payroll_entry_form\n\n"
    for name in modules["payroll_page"]:
        s, e = ranges[name]
        payroll_body += _slice(lines, s, e) + "\n\n"
    (pkg / "payroll_page.py").write_text(payroll_body.rstrip() + "\n", encoding="utf-8")

    init = '''"""Finance area — Timecards + Payroll (package facade).

Public API (stable):
  render_timecards, render_payroll, render_finance
"""
from __future__ import annotations

from gui.pages.finance.timecards import render_finance, render_timecards
from gui.pages.finance.payroll_page import render_payroll

__all__ = ["render_timecards", "render_payroll", "render_finance"]
'''
    (pkg / "__init__.py").write_text(init, encoding="utf-8")

    # Remove monolith file so package takes precedence
    backup = ROOT / "gui" / "pages" / "finance.py.bak"
    shutil.move(str(src_path), str(backup))
    print(f"finance: package written; monolith moved to {backup.relative_to(ROOT)}")


def split_payroll() -> None:
    src_path = ROOT / "logic" / "payroll.py"
    if not src_path.is_file():
        if (ROOT / "logic" / "payroll" / "__init__.py").is_file():
            print("payroll package already present — skip logic split")
            return
        raise SystemExit(f"missing {src_path}")

    lines = _lines(src_path)
    src = "".join(lines)
    ranges = _func_ranges(src)
    tree = ast.parse(src)

    # Header: all imports from original module
    import_end = 1
    for n in tree.body:
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            import_end = max(import_end, n.end_lineno or n.lineno)
        elif isinstance(n, ast.Expr) and isinstance(getattr(n, "value", None), ast.Constant):
            # module docstring
            import_end = max(import_end, n.end_lineno or n.lineno)
        else:
            break
    # also include docstring + blank after imports
    header_lines = lines[:import_end]
    # ensure we captured through last import block
    header = "".join(header_lines)
    if not header.rstrip().endswith("\n"):
        header += "\n"
    header = header.rstrip() + "\n\n"

    pkg = ROOT / "logic" / "payroll"
    if pkg.exists():
        shutil.rmtree(pkg)
    pkg.mkdir(parents=True)

    # Symbol clusters (order matters within file for readability only)
    clusters: dict[str, list[str]] = {
        "pay_codes": [
            "get_pay_code_rules",
            "save_pay_code_rules",
            "calculate_pay_for_entry",
            "blended_regular_rate",
            "convert_overtime_to_comp",
        ],
        "period": [
            "get_pay_period",
            "normalize_pay_period_start",
            "format_pay_period_label",
            "is_current_pay_period",
            "pay_period_for_shift_start",
            "search_pay_period_by_date",
            "list_pay_periods_catalog",
            "get_adjacent_pay_period",
            "count_pay_periods_in_year",
            "annual_salary_to_per_pay_period",
            "monthly_pay_to_per_pay_period",
            "suggested_hourly_rate_for_title",
            "get_adjacent_cycle_window",
            "is_future_cycle_window",
            "is_future_pay_period",
            "lock_pay_period",
            "unlock_pay_period",
            "is_pay_period_locked",
            "get_pay_period_lock_reminder",
            "get_pay_period_history",
        ],
        "banks": [
            "_ensure_officer_time_banks",
            "_months_between",
            "bulk_adjust_pay_rates",
        ],
        "entries": [
            "create_payroll_entry",
            "get_payroll_entries",
            "get_pay_stub_preview",
            "import_timecard_to_payroll",
            "project_officer_annual_pay",
        ],
        "timecard": [
            "_TIMECARD_WORKING_STATUSES",
            "_approved_day_off_request_type",
            "_timecard_defaults_for_schedule_status",
            "get_officer_live_schedule_day",
            "get_timecard_approval",
            "list_timecard_approvals_for_period",
            "_upsert_timecard_approval",
            "submit_timecard_for_approval",
            "approve_timecard_period",
            "reject_timecard_period",
            "is_timecard_period_approved",
            "save_timecard_entry",
            "delete_timecard_entry",
            "_apply_night_differential",
            "copy_timecard_from_previous_period",
            "_summarize_pay_period_hours",
            "get_pay_period_hours_summary",
            "get_payroll_period_timesheets",
            "get_timecard_period",
            "prefill_timecard_from_schedule",
            "auto_prefill_timecard_from_live_schedule",
        ],
    }

    # Relative import bridges for cross-cluster private helpers
    bridges = {
        "pay_codes": "from logic.payroll.period import get_pay_period, is_pay_period_locked\n"
        "from logic.payroll.banks import _ensure_officer_time_banks\n",
        "period": "",
        "banks": "from logic.payroll.period import get_pay_period\n",
        "entries": (
            "from logic.payroll.pay_codes import calculate_pay_for_entry, get_pay_code_rules\n"
            "from logic.payroll.period import (\n"
            "    get_pay_period,\n"
            "    is_pay_period_locked,\n"
            "    count_pay_periods_in_year,\n"
            "    format_pay_period_label,\n"
            "    get_adjacent_pay_period,\n"
            ")\n"
            "from logic.payroll.banks import _ensure_officer_time_banks\n"
            "from logic.payroll.timecard import get_timecard_period, get_pay_period_hours_summary\n"
        ),
        "timecard": (
            "from logic.payroll.pay_codes import get_pay_code_rules, calculate_pay_for_entry\n"
            "from logic.payroll.period import (\n"
            "    get_pay_period,\n"
            "    is_pay_period_locked,\n"
            "    format_pay_period_label,\n"
            "    get_adjacent_pay_period,\n"
            "    normalize_pay_period_start,\n"
            "    pay_period_for_shift_start,\n"
            ")\n"
            "from logic.payroll.banks import _ensure_officer_time_banks\n"
        ),
    }

    docstrings = {
        "pay_codes": '"""Pay-code rules, pay calculation, OT→comp conversion."""\n\n',
        "period": '"""Pay-period calendar, locks, and period helpers."""\n\n',
        "banks": '"""Officer time-bank accrual bootstrap and bulk rate tools."""\n\n',
        "entries": '"""Payroll ledger entries and annual pay projection."""\n\n',
        "timecard": '"""Timecard entries, approvals, prefill, period summaries."""\n\n',
    }

    # Write leaf modules first (period, banks) — circular import soft via lazy in some cases
    write_order = ["period", "banks", "pay_codes", "timecard", "entries"]

    all_exported: list[str] = []
    for mod in write_order:
        names = clusters[mod]
        missing = [n for n in names if n not in ranges]
        if missing:
            raise SystemExit(f"payroll split: missing symbols in {mod}: {missing}")
        body = docstrings[mod] + header + bridges[mod]
        if bridges[mod] and not bridges[mod].endswith("\n"):
            body += "\n"
        body += "\n"
        for name in names:
            s, e = ranges[name]
            body += _slice(lines, s, e) + "\n\n"
        (pkg / f"{mod}.py").write_text(body.rstrip() + "\n", encoding="utf-8")
        all_exported.extend(names)
        nlines = body.count("\n") + 1
        print(f"  payroll/{mod}.py ~{nlines} lines ({len(names)} symbols)")

    # Verify all functions assigned
    all_funcs = set(ranges.keys())
    assigned = set(all_exported)
    leftover = all_funcs - assigned
    if leftover:
        print(f"WARNING leftover symbols not assigned: {sorted(leftover)}")

    # Public __init__ re-exports (star from each submodule)
    init = '''"""Payroll entries, timecard, and pay-period management (package facade).

Stable import path: ``from logic.payroll import get_pay_period, ...``
Same star-export surface as the former monolith module.
"""
from __future__ import annotations

from logic.payroll.pay_codes import *  # noqa: F403
from logic.payroll.period import *  # noqa: F403
from logic.payroll.banks import *  # noqa: F403
from logic.payroll.timecard import *  # noqa: F403
from logic.payroll.entries import *  # noqa: F403

# Explicit re-export of private helpers used by sibling modules / tests
from logic.payroll.banks import _ensure_officer_time_banks, _months_between  # noqa: F401
from logic.payroll.timecard import (  # noqa: F401
    _TIMECARD_WORKING_STATUSES,
    _approved_day_off_request_type,
    _timecard_defaults_for_schedule_status,
    _upsert_timecard_approval,
    _apply_night_differential,
    _summarize_pay_period_hours,
)

__all__ = [  # public surface for star-importers / docs
    "get_pay_code_rules",
    "save_pay_code_rules",
    "calculate_pay_for_entry",
    "blended_regular_rate",
    "convert_overtime_to_comp",
    "create_payroll_entry",
    "get_payroll_entries",
    "get_pay_period",
    "normalize_pay_period_start",
    "format_pay_period_label",
    "is_current_pay_period",
    "pay_period_for_shift_start",
    "search_pay_period_by_date",
    "list_pay_periods_catalog",
    "get_adjacent_pay_period",
    "count_pay_periods_in_year",
    "annual_salary_to_per_pay_period",
    "monthly_pay_to_per_pay_period",
    "suggested_hourly_rate_for_title",
    "get_adjacent_cycle_window",
    "is_future_cycle_window",
    "is_future_pay_period",
    "lock_pay_period",
    "unlock_pay_period",
    "is_pay_period_locked",
    "get_pay_period_lock_reminder",
    "get_pay_period_history",
    "get_officer_live_schedule_day",
    "get_timecard_approval",
    "list_timecard_approvals_for_period",
    "submit_timecard_for_approval",
    "approve_timecard_period",
    "reject_timecard_period",
    "is_timecard_period_approved",
    "save_timecard_entry",
    "delete_timecard_entry",
    "bulk_adjust_pay_rates",
    "copy_timecard_from_previous_period",
    "get_pay_stub_preview",
    "get_pay_period_hours_summary",
    "get_payroll_period_timesheets",
    "get_timecard_period",
    "import_timecard_to_payroll",
    "prefill_timecard_from_schedule",
    "auto_prefill_timecard_from_live_schedule",
    "project_officer_annual_pay",
    "_ensure_officer_time_banks",
]
'''
    (pkg / "__init__.py").write_text(init, encoding="utf-8")

    backup = ROOT / "logic" / "payroll.py.bak"
    shutil.move(str(src_path), str(backup))
    print(f"payroll: package written; monolith moved to {backup.relative_to(ROOT)}")


def main() -> None:
    print("=== split finance UI ===")
    split_finance()
    print("=== split logic/payroll ===")
    split_payroll()
    print("done")


if __name__ == "__main__":
    main()
