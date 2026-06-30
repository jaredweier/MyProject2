#!/usr/bin/env python3
"""Split logic.py into logic/ package modules (run once from project root)."""

from __future__ import annotations

import os
import re
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGIC_PY = os.path.join(ROOT, "logic.py")
PKG = os.path.join(ROOT, "logic")

HEADER = '''"""
Dodgeville PD Scheduler — {title}
"""

from logic._shared import *
'''

SHARED_IMPORTS = (
    textwrap.dedent('''
    """Shared imports for logic package modules."""
    import os
    import sqlite3
    from datetime import datetime, date, timedelta
    from typing import Optional, Dict, List, Set, Tuple

    from database import get_connection, connection
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
''').strip()
    + "\n"
)

# (module_name, title, list of (start_line, end_line) 1-based inclusive from logic.py)
MODULE_RANGES = [
    ("officers", "Officer roster", [(51, 148), (1615, 1882)]),
    ("scheduling", "Rotation, bumping, schedule views", [(150, 444), (3285, 3462)]),
    ("requests", "Day-off, swaps, notifications", [(446, 1295), (3193, 3283)]),
    ("payroll", "Payroll and timecard", [(1297, 1613), (2290, 2793)]),
    ("users", "Users and authentication", [(1884, 2288)]),
    ("snapshots", "Schedule snapshots", [(2795, 3191)]),
    ("exports", "PDF exports, simulator, analytics wrappers", [(3464, 3743), (4015, 4169)]),
    ("operations", "Holidays, availability, open shifts", [(3745, 4014), (4171, 99999)]),
]

# Cross-module imports appended to each file (scheduling domain deps)
MODULE_EXTRA_IMPORTS = {
    "scheduling": "from logic.officers import get_officer_by_id, get_officers_by_seniority\n",
    "requests": (
        "from logic.officers import get_officer_by_id, get_officers_by_seniority\n"
        "from logic.scheduling import (\n"
        "    find_replacement_officer, suggest_bump_chain, plan_bump_chain,\n"
        "    get_shift_number, is_officer_working_on_day, count_officers_on_shift_on_date,\n"
        "    get_cycle_day, get_squad_on_duty, validate_bump_feasibility,\n"
        ")\n"
    ),
    "payroll": "from logic.officers import get_officer_by_id, get_officers_by_seniority\n",
    "users": "from logic.officers import get_officer_by_id\n",
    "snapshots": (
        "from logic.officers import get_officer_by_id, get_officers_by_seniority\n"
        "from logic.scheduling import (\n"
        "    build_schedule_matrix, get_cycle_day, get_squad_on_duty,\n"
        "    _load_override_maps_for_range, _officer_day_status,\n"
        ")\n"
    ),
    "exports": "from logic.officers import get_officer_by_id, get_officers_by_seniority\n",
    "operations": "from logic.officers import get_officer_by_id, get_officers_by_seniority\n",
}

INIT_TEMPLATE = '''"""
Dodgeville Police Department Scheduler — Core Business Logic (package).
"""

from logic.officers import *
from logic.scheduling import *
from logic.requests import *
from logic.payroll import *
from logic.users import *
from logic.snapshots import *
from logic.exports import *
from logic.operations import *
'''


def main():
    with open(LOGIC_PY, encoding="utf-8") as fh:
        lines = fh.readlines()

    os.makedirs(PKG, exist_ok=True)
    with open(os.path.join(PKG, "_shared.py"), "w", encoding="utf-8") as fh:
        fh.write(SHARED_IMPORTS)

    for mod, title, ranges in MODULE_RANGES:
        chunks = []
        for start, end in ranges:
            chunks.extend(lines[start - 1 : min(end, len(lines))])
        body = "".join(chunks)
        # Strip section banner comments for cleaner modules
        body = re.sub(r"# ={10,}.*?\n", "", body)
        extra = MODULE_EXTRA_IMPORTS.get(mod, "")
        content = HEADER.format(title=title) + "\n" + extra + "\n" + body
        path = os.path.join(PKG, f"{mod}.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        print(f"Wrote {path} ({len(content.splitlines())} lines)")

    with open(os.path.join(PKG, "__init__.py"), "w", encoding="utf-8") as fh:
        fh.write(INIT_TEMPLATE)

    print("Package created. Remove logic.py after verifying imports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
