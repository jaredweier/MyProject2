#!/usr/bin/env python3
"""Extract day-off, swap, and notification functions into logic/requests.py."""

from __future__ import annotations

import ast
import os
import shutil
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGIC_PY = os.path.join(ROOT, "logic.py")
PKG = os.path.join(ROOT, "logic")

REQUESTS_FUNCTIONS = frozenset(
    {
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
        "create_day_off_request",
        "get_pending_day_off_requests",
        "get_day_off_requests",
        "get_day_off_request_created_at",
        "get_day_off_requests_for_viewer",
        "_notify_availability_conflict",
        "_notify_day_off_processed",
        "_notify_day_off_submitted",
        "_notify_open_shift_filled",
        "_notify_open_shift_posted",
        "_notify_shift_swap_processed",
        "_notify_schedule_published",
        "_notify_shift_swap_submitted",
        "_notify_supervisors",
        "get_notification_types",
        "get_unread_notification_count",
    }
)

CORE_LAZY_IMPORTS: dict[str, tuple[str, ...]] = {
    "create_notification": ("create_manual_coverage_override",),
    "_notify_supervisors": ("lock_pay_period", "unlock_pay_period"),
    "_notify_open_shift_posted": ("create_open_shift",),
    "_notify_open_shift_filled": ("fill_open_shift",),
    "_notify_availability_conflict": ("add_officer_availability",),
    "_notify_schedule_published": ("sync_updated_schedule",),
}

REQUESTS_HEADER = (
    textwrap.dedent('''
    """
    Day-off requests, shift swaps, and in-app notifications.
    """

    from datetime import date
    from typing import Dict, List, Optional, Set

    from database import get_connection
    from models import ProcessRequestResult, ProcessSwapResult, SwapValidationResult
    from config import REQUEST_STATUS, is_high_risk_night, logger
    from validators import (
        applies_night_minimum,
        format_date,
        night_minimum_violation,
        parse_date,
        parse_date_filter,
        storage_date,
        storage_date_str,
        validate_day_off_request,
        validate_process_day_off,
        validate_process_shift_swap,
    )

    from logic._core import (
        _insert_override_record,
        count_officers_on_shift_on_date,
        describe_day_off_request,
        get_officer_by_id,
        get_officers_by_seniority,
        get_request_reviewer_officer_ids,
        is_officer_working_on_day,
        officer_meets_minimum_rest,
        suggest_bump_chain,
    )
''').strip()
    + "\n\n"
)

INIT_PY = (
    textwrap.dedent('''
    """
    Dodgeville Police Department Scheduler — Core Business Logic (package).
    """

    from logic._core import *
    from logic.requests import *
''').strip()
    + "\n"
)

SKIP_LINES = set(range(156, 171))


def _function_ranges(source: str) -> dict[str, tuple[int, int]]:
    tree = ast.parse(source)
    ranges: dict[str, tuple[int, int]] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            ranges[node.name] = (node.lineno, node.end_lineno or node.lineno)
    return ranges


def _inject_lazy_imports(core_source: str) -> str:
    tree = ast.parse(core_source)
    lines = core_source.splitlines(keepends=True)
    body_starts: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.body:
            body_starts[node.name] = node.body[0].lineno

    inserts: list[tuple[int, str]] = []
    for symbol, func_names in CORE_LAZY_IMPORTS.items():
        for func_name in func_names:
            if func_name not in body_starts:
                continue
            inserts.append((body_starts[func_name], f"    from logic.requests import {symbol}\n"))

    for line_num, snippet in sorted(inserts, key=lambda x: -x[0]):
        lines.insert(line_num - 1, snippet)
    return "".join(lines)


def main() -> int:
    with open(LOGIC_PY, encoding="utf-8") as fh:
        source = fh.read()
    lines = source.splitlines(keepends=True)
    ranges = _function_ranges(source)

    request_line_nums: set[int] = set()
    for name, (start, end) in ranges.items():
        if name in REQUESTS_FUNCTIONS:
            request_line_nums.update(range(start, end + 1))

    request_bodies: list[str] = []
    for name, (start, end) in sorted(ranges.items(), key=lambda item: item[1][0]):
        if name in REQUESTS_FUNCTIONS:
            request_bodies.append("".join(lines[start - 1 : end]))

    core_lines = [line for idx, line in enumerate(lines, 1) if idx not in request_line_nums and idx not in SKIP_LINES]

    os.makedirs(PKG, exist_ok=True)
    core_path = os.path.join(PKG, "_core.py")
    with open(core_path, "w", encoding="utf-8") as fh:
        fh.write("".join(core_lines))
    with open(core_path, encoding="utf-8") as fh:
        core_fixed = _inject_lazy_imports(fh.read())
    with open(core_path, "w", encoding="utf-8") as fh:
        fh.write(core_fixed)

    requests_path = os.path.join(PKG, "requests.py")
    with open(requests_path, "w", encoding="utf-8") as fh:
        fh.write(REQUESTS_HEADER)
        fh.write("\n".join(body.rstrip("\n") for body in request_bodies))
        fh.write("\n")

    init_path = os.path.join(PKG, "__init__.py")
    with open(init_path, "w", encoding="utf-8") as fh:
        fh.write(INIT_PY)

    backup = LOGIC_PY + ".bak"
    shutil.move(LOGIC_PY, backup)
    print(f"Wrote {requests_path} ({len(request_bodies)} functions)")
    print(f"Wrote {core_path}")
    print(f"Moved logic.py -> {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
