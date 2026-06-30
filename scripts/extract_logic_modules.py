#!/usr/bin/env python3
"""Extract logic/_core.py functions into vertical-slice modules."""

from __future__ import annotations

import ast
import os
import textwrap
from typing import Dict, FrozenSet, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE_PATH = os.path.join(ROOT, "logic", "_core.py")
PKG = os.path.join(ROOT, "logic")

# Extraction order matters — later modules may import earlier ones in headers.
MODULES: List[Tuple[str, FrozenSet[str], str]] = [
    (
        "officers",
        frozenset(
            {
                "get_officers_by_seniority",
                "get_officer_by_id",
                "get_supervisors",
                "get_suggested_seniority_rank",
                "get_request_reviewer_officer_ids",
                "describe_day_off_request",
                "add_officer",
                "update_officer",
                "delete_officer",
                "import_roster_from_csv",
                "remove_officer_photo",
                "set_officer_photo",
                "get_pay_period_hours_by_officer",
            }
        ),
        textwrap.dedent('''
            """Officer roster CRUD, lookup, photos, and pay-period hour totals."""

            import csv
            import os
            from datetime import date
            from typing import Dict, List, Optional

            from database import get_connection
            from config import DATE_INPUT_HINT, logger
            from validators import (
                format_date,
                normalize_optional_text,
                parse_date,
                validate_officer_profile,
            )
        ''').strip()
        + "\n",
    ),
    (
        "scheduling",
        frozenset(
            {
                "get_current_cycle_window",
                "get_cycle_day",
                "get_squad_on_duty",
                "is_officer_working_on_day",
                "count_officers_on_shift_on_date",
                "get_shift_coverage_counts_for_range",
                "get_shift_number",
                "_shift_end_for_start",
                "_shift_bounds",
                "get_officer_effective_shift_band",
                "compute_minimum_rest_gap",
                "officer_meets_minimum_rest",
                "describe_minimum_rest_violation",
                "find_replacement_officer",
                "suggest_bump_chain",
                "plan_bump_chain",
                "format_bump_suggestion",
                "validate_bump_feasibility",
                "build_schedule_matrix",
                "get_officer_day_status",
                "batch_officer_day_status",
                "_officer_day_status",
                "_officer_history_reason",
                "_rotation_only_status",
                "_officer_shift_hours",
                "_officer_work_days_per_cycle",
                "_shift_hours",
                "_schedule_status_for_override_reason",
                "get_monthly_rotation_summary",
                "get_officer_work_dates_from_summary",
                "_get_monthly_rotation_base_only",
                "run_schedule_simulation",
                "get_simulator_defaults_from_roster",
                "get_schedule_conflicts",
                "_load_override_maps_for_range",
                "_officer_day_status",
                "_officer_history_reason",
            }
        ),
        textwrap.dedent('''
            """Rotation, coverage, bumping, and schedule matrix."""

            from datetime import date, datetime, timedelta
            from typing import Dict, List, Optional, Set, Tuple

            from database import get_connection
            from models import BumpChainStep, BumpChainSuggestion, BumpSimulationResult
            from config import (
                BUMP_RULES,
                NIGHT_MINIMUM_OFFICERS,
                ROTATION_BASE_DATE,
                ROTATION_CYCLE_LENGTH,
                SHIFT_TIMES,
                is_high_risk_night,
                logger,
            )
            from validators import (
                applies_night_minimum,
                format_date,
                is_overnight_shift,
                night_minimum_violation,
                parse_date,
                storage_date,
                validate_cycle_date,
            )
            from logic.officers import get_officer_by_id, get_officers_by_seniority

            _OFFICER_WORKING_STATUSES = frozenset({"working", "covering", "swapped", "training"})
        ''').strip()
        + "\n",
    ),
    (
        "users",
        frozenset(
            {
                "list_login_users",
                "authenticate_user",
                "create_app_user",
                "get_user_by_id",
                "list_all_users",
                "admin_reset_user_password",
                "change_own_password",
                "allowed_roles_for_actor",
                "set_app_user_active",
                "update_app_user",
                "complete_initial_setup",
                "is_setup_complete",
                "_upgrade_password_hash",
                "log_audit_action",
            }
        ),
        textwrap.dedent('''
            """App users, authentication, and audit logging."""

            import json
            from typing import Dict, List, Optional

            from database import get_connection
            from auth_password import hash_password, verify_password
            from config import logger
            from validators import normalize_optional_text, parse_date
            from logic.officers import get_officer_by_id
        ''').strip()
        + "\n",
    ),
    (
        "payroll",
        frozenset(
            {
                "calculate_pay_for_entry",
                "create_payroll_entry",
                "get_payroll_entries",
                "get_pay_period",
                "pay_period_for_shift_start",
                "get_adjacent_pay_period",
                "get_adjacent_cycle_window",
                "is_future_cycle_window",
                "is_future_pay_period",
                "lock_pay_period",
                "unlock_pay_period",
                "is_pay_period_locked",
                "get_pay_period_history",
                "save_timecard_entry",
                "get_timecard_period",
                "copy_timecard_from_previous_period",
                "import_timecard_to_payroll",
                "prefill_timecard_from_schedule",
                "_apply_night_differential",
                "_ensure_officer_time_banks",
                "_months_between",
                "get_pay_period_hours_summary",
                "_summarize_pay_period_hours",
                "get_payroll_period_timesheets",
                "get_pay_stub_preview",
                "bulk_adjust_pay_rates",
                "project_officer_annual_pay",
            }
        ),
        textwrap.dedent('''
            """Payroll entries, timecard, and pay-period management."""

            from datetime import date, timedelta
            from typing import Dict, List, Optional, Tuple

            from database import get_connection
            from models import PayCalculationResult
            from config import (
                DATE_INPUT_HINT,
                FLOAT_HOLIDAY_ANNUAL_HOURS,
                HOLIDAY_ANNUAL_HOURS,
                PAY_PERIOD_BASE_DATE,
                PAY_PERIOD_LENGTH,
                PAYROLL_ENTRY_TYPES,
                SICK_MONTHLY_ACCRUAL_HOURS,
                TIMECARD_ENTRY_TYPES,
                TIMECARD_REGULAR_TYPE,
                logger,
            )
            from validators import format_date, normalize_optional_text, parse_date
            from logic.officers import get_officer_by_id, get_officers_by_seniority
        ''').strip()
        + "\n",
    ),
    (
        "snapshots",
        frozenset(
            {
                "_insert_override_record",
                "_insert_snapshot_rows",
                "_month_date_range",
                "compare_base_updated_schedule",
                "create_manual_coverage_override",
                "create_override_record",
                "ensure_original_monthly_schedule",
                "publish_base_schedule",
                "sync_updated_schedule",
                "set_snapshot_assignment",
                "get_schedule_snapshot",
                "get_monthly_summary_from_snapshot",
                "build_monthly_roster_by_date",
                "get_snapshot_day_roster",
                "_roster_entry_from_snapshot_row",
                "_roster_from_snapshot_day_rows",
                "get_officer_schedule_window",
            }
        ),
        textwrap.dedent('''
            """Schedule snapshots, monthly calendars, sync, and overrides."""

            from datetime import date
            from typing import Dict, List, Optional, Tuple

            from database import get_connection
            from config import ROTATION_CYCLE_LENGTH, SCHEDULE_SNAPSHOT_TYPES, SNAPSHOT_STATUSES, logger
            from validators import format_date, normalize_optional_text, parse_date, storage_date_str
            from logic.officers import get_officer_by_id, get_officers_by_seniority
            from logic.scheduling import (
                _officer_day_status,
                build_schedule_matrix,
                get_cycle_day,
                get_squad_on_duty,
            )
        ''').strip()
        + "\n",
    ),
    (
        "operations",
        frozenset(
            {
                "add_holiday",
                "delete_holiday",
                "get_holidays",
                "get_upcoming_holidays",
                "add_officer_availability",
                "delete_officer_availability",
                "get_officer_availability",
                "is_officer_unavailable_on_date",
                "get_open_shifts",
                "create_open_shift",
                "fill_open_shift",
                "maybe_run_auto_backup",
                "get_department_setting",
                "set_department_setting",
                "get_all_department_settings",
                "get_position_pay_rates",
                "save_position_pay_rates",
                "apply_position_pay_rates_to_roster",
                "get_pending_manual_review_count",
                "get_officer_time_banks",
            }
        ),
        textwrap.dedent('''
            """Holidays, availability, open shifts, settings, and backup."""

            from datetime import date, timedelta
            from typing import Dict, List, Optional

            from database import get_connection, backup_database
            from config import DATE_INPUT_HINT, logger
            from validators import format_date, normalize_optional_text, parse_date, storage_date_str
            from logic.officers import get_officer_by_id, get_officers_by_seniority
            from logic.scheduling import get_officer_day_status
        ''').strip()
        + "\n",
    ),
]

CORE_REEXPORTS = (
    textwrap.dedent("""
    # Re-import slice modules for functions still in _core (load order: slices before _core).
    from logic.officers import (
        get_officer_by_id,
        get_officers_by_seniority,
        get_supervisors,
        get_suggested_seniority_rank,
        describe_day_off_request,
        get_request_reviewer_officer_ids,
    )
    from logic.scheduling import (
        batch_officer_day_status,
        build_schedule_matrix,
        count_officers_on_shift_on_date,
        get_current_cycle_window,
        get_cycle_day,
        get_officer_day_status,
        get_shift_coverage_counts_for_range,
        is_officer_working_on_day,
        suggest_bump_chain,
    )
    from logic.payroll import get_pay_period, is_pay_period_locked
    from logic.snapshots import _insert_override_record, get_schedule_snapshot
    from logic.users import log_audit_action
""").strip()
    + "\n\n"
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

PAYROLL_LAZY = {
    "_notify_supervisors": ("lock_pay_period", "unlock_pay_period"),
}
OPERATIONS_LAZY = {
    "_notify_open_shift_posted": ("create_open_shift",),
    "_notify_open_shift_filled": ("fill_open_shift",),
    "_notify_availability_conflict": ("add_officer_availability",),
}
SNAPSHOTS_LAZY = {
    "create_notification": ("create_manual_coverage_override",),
    "_notify_schedule_published": ("sync_updated_schedule",),
}


def _function_ranges(source: str) -> Dict[str, Tuple[int, int]]:
    tree = ast.parse(source)
    return {
        node.name: (node.lineno, node.end_lineno or node.lineno)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def _extract_module(
    source: str,
    lines: List[str],
    ranges: Dict[str, Tuple[int, int]],
    names: FrozenSet[str],
) -> Tuple[str, List[str]]:
    extract_lines: set[int] = set()
    bodies: List[str] = []
    for name, (start, end) in sorted(ranges.items(), key=lambda x: x[1][0]):
        if name in names:
            extract_lines.update(range(start, end + 1))
            bodies.append("".join(lines[start - 1 : end]))
    remaining = [line for idx, line in enumerate(lines, 1) if idx not in extract_lines]
    return "\n".join(b.rstrip("\n") for b in bodies) + ("\n" if bodies else ""), remaining


def _inject_lazy_imports(
    source: str,
    lazy_map: Dict[str, Tuple[str, ...]],
    import_from: str = "logic.requests",
) -> str:
    tree = ast.parse(source)
    file_lines = source.splitlines(keepends=True)
    body_starts = {
        node.name: node.body[0].lineno for node in tree.body if isinstance(node, ast.FunctionDef) and node.body
    }
    inserts: List[Tuple[int, str]] = []
    for symbol, funcs in lazy_map.items():
        for func in funcs:
            if func in body_starts:
                inserts.append(
                    (
                        body_starts[func],
                        f"    from {import_from} import {symbol}\n",
                    )
                )
    for line_num, snippet in sorted(inserts, key=lambda x: -x[0]):
        file_lines.insert(line_num - 1, snippet)
    return "".join(file_lines)


def _inject_officers_lazy(source: str) -> str:
    source = _inject_lazy_imports(
        source,
        {
            "is_officer_working_on_day": ("describe_day_off_request",),
            "suggest_bump_chain": ("describe_day_off_request",),
        },
        "logic.scheduling",
    )
    source = _inject_lazy_imports(
        source,
        {
            "is_officer_unavailable_on_date": ("describe_day_off_request",),
        },
        "logic.operations",
    )
    return _inject_lazy_imports(
        source,
        {
            "get_payroll_period_timesheets": ("get_pay_period_hours_by_officer",),
        },
        "logic.payroll",
    )


def _inject_core_reexports(source: str) -> str:
    marker = "_OFFICER_WORKING_STATUSES = frozenset"
    lines = source.splitlines(keepends=True)
    for idx, line in enumerate(lines):
        if marker in line:
            return "".join(lines[:idx]) + CORE_REEXPORTS + "".join(lines[idx:])
    # fallback: after validator imports block
    for idx, line in enumerate(lines):
        if line.strip().startswith("from validators import"):
            end = idx
            while end + 1 < len(lines) and (
                lines[end + 1].strip().startswith("(")
                or lines[end + 1].strip().startswith(")")
                or "," in lines[end + 1]
                or lines[end + 1].strip() == ")"
            ):
                end += 1
            return "".join(lines[: end + 1]) + "\n\n" + CORE_REEXPORTS + "".join(lines[end + 1 :])
    return CORE_REEXPORTS + source


def main() -> int:
    with open(CORE_PATH, encoding="utf-8") as fh:
        source = fh.read()
    lines = source.splitlines(keepends=True)
    ranges = _function_ranges(source)

    all_assigned: set[str] = set()
    for mod_name, funcs, _header in MODULES:
        overlap = all_assigned & funcs
        if overlap:
            raise SystemExit(f"{mod_name}: duplicate functions {overlap}")
        all_assigned |= funcs

    remaining_lines = lines
    remaining_source = source

    for mod_name, funcs, header in MODULES:
        ranges = _function_ranges(remaining_source)
        body, remaining_lines = _extract_module(
            remaining_source,
            remaining_lines,
            ranges,
            funcs,
        )
        if not body.strip():
            print(f"skip {mod_name}: no functions found")
            continue
        out_path = os.path.join(PKG, f"{mod_name}.py")
        content = header + "\n" + body
        if mod_name == "officers":
            content = _inject_officers_lazy(content)
        if mod_name == "payroll":
            content = _inject_lazy_imports(content, PAYROLL_LAZY, "logic.requests")
        if mod_name == "operations":
            content = _inject_lazy_imports(content, OPERATIONS_LAZY, "logic.requests")
        if mod_name == "snapshots":
            content = _inject_lazy_imports(content, SNAPSHOTS_LAZY, "logic.requests")
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        remaining_source = "".join(remaining_lines)
        print(f"Wrote {out_path} ({len(funcs)} symbols)")

    remaining_source = _inject_core_reexports(remaining_source)
    with open(CORE_PATH, "w", encoding="utf-8") as fh:
        fh.write(remaining_source)

    init_path = os.path.join(PKG, "__init__.py")
    with open(init_path, "w", encoding="utf-8") as fh:
        fh.write(INIT_TEMPLATE)

    print(f"Updated {CORE_PATH} and {init_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
