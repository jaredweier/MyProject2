#!/usr/bin/env python3
"""Rebuild logic.py from logic/ package function definitions."""

from __future__ import annotations

import ast
import os
import re
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "logic")
OUT = os.path.join(ROOT, "logic.py")

HEADER = textwrap.dedent('''
    """
    Dodgeville Police Department Scheduler
    Core Business Logic
    """

    import os
    import sqlite3
    from datetime import datetime, date, timedelta
    from typing import Optional, Dict, List, Set, Tuple
    from database import get_connection
    from models import (
        BumpChainStep,
        BumpChainSuggestion,
        ProcessRequestResult,
        ProcessSwapResult,
        BumpSimulationResult,
        SwapValidationResult,
        PayCalculationResult,
    )
    from config import (
        PAYROLL_ENTRY_TYPES,
        ROTATION_BASE_DATE,
        ROTATION_CYCLE_LENGTH,
        REQUEST_STATUS,
        BUMP_RULES,
        FLOAT_HOLIDAY_ANNUAL_HOURS,
        HOLIDAY_ANNUAL_HOURS,
        NIGHT_MINIMUM_OFFICERS,
        SCHEDULE_SNAPSHOT_TYPES,
        SICK_MONTHLY_ACCRUAL_HOURS,
        SHIFT_TIMES,
        SNAPSHOT_STATUSES,
        TIMECARD_ENTRY_TYPES,
        TIMECARD_REGULAR_TYPE,
        is_high_risk_night,
        logger,
    )
    from validators import (
        applies_night_minimum,
        night_minimum_violation,
        normalize_optional_text,
        parse_date,
        validate_day_off_request,
        validate_officer_profile,
        validate_process_day_off,
        validate_process_shift_swap,
    )

''').lstrip()

# Preferred order (approximate original logic.py layout)
ORDER = [
    "get_officers_by_seniority",
    "get_officer_by_id",
    "get_supervisors",
    "get_suggested_seniority_rank",
    "get_request_reviewer_officer_ids",
    "describe_day_off_request",
    "get_current_cycle_window",
    "get_cycle_day",
    "get_squad_on_duty",
    "is_officer_working_on_day",
    "count_officers_on_shift_on_date",
    "get_shift_coverage_counts_for_range",
    "get_shift_number",
    "find_replacement_officer",
    "suggest_bump_chain",
    "plan_bump_chain",
    "format_bump_suggestion",
    "validate_bump_feasibility",
    "validate_swap_feasibility",
    "create_shift_swap_request",
    "process_shift_swap",
    "get_shift_swap_requests",
    "get_pending_shift_swap_requests",
    "create_notification",
    "get_notifications",
    "mark_notification_read",
    "mark_all_notifications_read",
    "resolve_notification_navigation",
    "process_day_off_request",
    "bulk_approve_auto_ok_requests",
    "bulk_reject_pending_requests",
    "calculate_pay_for_entry",
    "create_payroll_entry",
    "get_payroll_entries",
    "get_pay_period",
    "get_adjacent_pay_period",
    "is_future_pay_period",
    "lock_pay_period",
    "unlock_pay_period",
    "is_pay_period_locked",
    "get_pay_period_history",
    "add_officer",
    "update_officer",
    "delete_officer",
    "import_roster_from_csv",
    "list_login_users",
    "authenticate_user",
    "create_app_user",
    "save_timecard_entry",
    "get_timecard_entries",
    "build_schedule_matrix",
    "get_officer_day_status",
    "batch_officer_day_status",
    "export_schedule_pdf",
    "get_department_setting",
    "set_department_setting",
    "get_open_shifts",
    "create_open_shift",
    "fill_open_shift",
    "create_day_off_request",
    "get_day_off_requests",
    "get_pending_day_off_requests",
]


def _extract_defs(source: str) -> dict[str, str]:
    lines = source.splitlines()
    defs: dict[str, list[str]] = {}
    current_name = None
    current_lines: list[str] = []
    for line in lines:
        m = re.match(r"^def ([a-zA-Z_][a-zA-Z0-9_]*)", line)
        if m:
            if current_name:
                defs[current_name] = current_lines
            current_name = m.group(1)
            current_lines = [line]
        elif m := re.match(r"^([A-Z_][A-Z0-9_]*)\s*=", line):
            if current_name:
                defs[current_name] = current_lines
                current_name = None
                current_lines = []
            defs.setdefault(f"__const_{m.group(1)}", []).append(line)
        elif current_name:
            current_lines.append(line)
    if current_name:
        defs[current_name] = current_lines
    return {k: "\n".join(v).rstrip() + "\n\n" for k, v in defs.items() if v}


def main():
    combined: dict[str, str] = {}
    for fname in sorted(os.listdir(PKG)):
        if not fname.endswith(".py") or fname in ("__init__.py", "_shared.py"):
            continue
        path = os.path.join(PKG, fname)
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        # Drop imports and module docstring
        src = re.sub(r'^""".*?"""\s*', "", src, count=1, flags=re.S)
        src = re.sub(r"^from logic\._shared import \*\s*", "", src)
        src = re.sub(r"^from logic\..*?\n", "", src, flags=re.M)
        for name, body in _extract_defs(src).items():
            if name.startswith("__const_"):
                combined.setdefault(name, body)
            elif name not in combined or len(body) > len(combined[name]):
                combined[name] = body

    # Validate syntax per function
    valid: dict[str, str] = {}
    for name, body in combined.items():
        if name.startswith("__const_"):
            valid[name] = body
            continue
        try:
            ast.parse(body)
            valid[name] = body
        except SyntaxError:
            print(f"skip invalid: {name}")

    ordered_names = [n for n in ORDER if n in valid]
    ordered_names += sorted(set(valid) - set(ORDER) - {k for k in valid if k.startswith("__const_")})

    parts = [HEADER]
    for name in ordered_names:
        if name.startswith("__const_"):
            continue
        parts.append(valid[name])

    for name, body in sorted(valid.items()):
        if name.startswith("__const_"):
            parts.insert(1, body + "\n")

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("".join(parts))

    print(f"Rebuilt {OUT} with {len(ordered_names)} functions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
