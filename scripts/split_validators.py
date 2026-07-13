"""Split validators.py into focused modules; keep validators.py as facade.

Creates:
  validators_dates.py   — parse/format/storage/time
  validators_rules.py   — night min, rest, consecutive, day-off/swap process
  validators_officer.py — roster/title/pay profile
  validators_auth.py    — password/username/roles
  validators_ops.py     — holiday, availability, manual override, settings

Idempotent if facade already re-exports.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "validators.py"

GROUPS: dict[str, tuple[str, ...]] = {
    "validators_dates.py": (
        "_mdy_short",
        "_mdy_datetime",
        "format_date",
        "format_datetime",
        "format_row_dates",
        "storage_date",
        "storage_date_str",
        "parse_date_filter",
        "_time_to_minutes",
        "is_overnight_shift",
        "parse_date",
    ),
    "validators_rules.py": (
        "_night_shift_starts",
        "is_officer_active",
        "is_night_shift",
        "applies_night_minimum",
        "validate_cycle_date",
        "validate_officer_working",
        "validate_request_status",
        "validate_no_duplicate_pending",
        "validate_day_off_request",
        "validate_request_type",
        "_officer_unavailable_on_date",
        "validate_process_day_off",
        "validate_swap_status",
        "validate_process_shift_swap",
        "night_minimum_violation",
        "validate_minimum_rest_gap",
        "validate_comp_time_cap",
        "validate_consecutive_work_days",
    ),
    "validators_officer.py": (
        "normalize_optional_text",
        "validate_officer_name",
        "validate_officer_email",
        "validate_officer_phone",
        "validate_officer_address",
        "validate_officer_start_date",
        "validate_seniority_rank",
        "normalize_officer_squad",
        "normalize_officer_shift",
        "officer_has_assignment",
        "format_officer_squad_display",
        "format_officer_shift_display",
        "parse_officer_shift_ui",
        "validate_officer_squad",
        "validate_officer_shift",
        "validate_officer_pay_rate",
        "normalize_officer_job_title",
        "is_command_staff_title",
        "officer_uses_command_staff_schedule",
        "is_command_staff_weekday",
        "validate_officer_job_title",
        "format_officer_title_display",
        "default_pay_basis_for_title",
        "is_yearly_salary_title",
        "default_annual_hours_for_title",
        "normalize_position_pay_basis",
        "position_amount_to_monthly",
        "monthly_pay_to_hourly",
        "position_amount_to_hourly",
        "format_position_pay_summary",
        "validate_position_pay_entry",
        "validate_annual_hours_target",
        "validate_overtime_multiplier",
        "validate_pay_code_rate_multiplier",
        "validate_pay_code_comp_ratio",
        "format_pay_code_formula",
        "validate_officer_profile",
    ),
    "validators_auth.py": (
        "validate_password",
        "validate_username",
        "validate_app_user_role",
        "validate_user_role_change",
    ),
    "validators_ops.py": (
        "validate_holiday",
        "validate_availability_entry",
        "validate_manual_override",
        "validate_setting_key",
    ),
}

COMMON_HEADER = '''"""{doc}

Part of the validators split; re-exported from ``validators``.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional, Tuple

from config import (
    DATE_DISPLAY_FORMAT,
    DATE_INPUT_HINT,
    DATE_PARSE_FORMATS,
    DATE_STORAGE_FORMAT,
    DATETIME_DISPLAY_FORMAT,
    DEFAULT_ANNUAL_HOURS,
    NIGHT_MINIMUM_OFFICERS,
    OFFICER_TITLE_ALIASES,
    OFFICER_TITLE_OPTIONS,
    OFFICER_UNASSIGNED_LABEL,
    POSITION_PAY_BASIS_LABELS,
    POSITION_PAY_BASIS_OPTIONS,
    REQUEST_STATUS,
)
from validators import (
    EMAIL_RE,
    PHONE_RE,
    REQUESTABLE_STATUSES,
    SWAP_REQUESTABLE_STATUSES,
    TERMINAL_STATUSES,
    ValidationResult,
)

'''

# Cross-module imports injected after extract (module -> imports from sibling)
CROSS = {
    "validators_rules.py": "from validators_dates import format_date, parse_date, storage_date, storage_date_str\n",
    "validators_officer.py": "from validators_dates import format_date, parse_date, storage_date_str\n",
    "validators_ops.py": "from validators_dates import format_date, parse_date, storage_date_str\nfrom validators_officer import normalize_optional_text, officer_has_assignment\n",
    "validators_auth.py": "",
    "validators_dates.py": "",
}


def main() -> None:
    src = SRC.read_text(encoding="utf-8")
    if "from validators_dates import" in src and (ROOT / "validators_dates.py").exists():
        print("already split (facade has dates import)")
        return

    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)
    ranges: dict[str, tuple[int, int]] = {}
    for n in tree.body:
        if isinstance(n, ast.FunctionDef):
            ranges[n.name] = (n.lineno, n.end_lineno or n.lineno)

    all_names = [n for names in GROUPS.values() for n in names]
    missing = [n for n in all_names if n not in ranges]
    if missing:
        raise SystemExit(f"missing functions: {missing}")

    # Write modules
    for filename, names in GROUPS.items():
        parts = []
        for name in names:
            s, e = ranges[name]
            parts.append("".join(lines[s - 1 : e]))
        doc = filename.replace(".py", "").replace("_", " ")
        header = COMMON_HEADER.format(doc=doc)
        cross = CROSS.get(filename, "")
        out = ROOT / filename
        # dates module should not import ValidationResult-heavy extras if unused — keep simple
        if filename == "validators_dates.py":
            header = '''"""Date parse/format/storage helpers (validators split)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Tuple

from config import (
    DATE_DISPLAY_FORMAT,
    DATE_INPUT_HINT,
    DATE_PARSE_FORMATS,
    DATE_STORAGE_FORMAT,
    DATETIME_DISPLAY_FORMAT,
)

'''
        if filename == "validators_auth.py":
            header = '''"""Password / username / role validators (validators split)."""
from __future__ import annotations

import re
from typing import Optional

from config import REQUEST_STATUS  # noqa: F401 — kept for symmetry
from validators import ValidationResult

'''
        body = "\n\n".join(parts) + "\n"
        # Officer module uses EMAIL_RE PHONE_RE from validators facade — circular if facade imports officer.
        # Define regexes locally in officer module instead.
        if filename == "validators_officer.py":
            header = '''"""Officer roster / title / pay validators (validators split)."""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional, Tuple

from config import (
    DATE_INPUT_HINT,
    DEFAULT_ANNUAL_HOURS,
    OFFICER_TITLE_ALIASES,
    OFFICER_TITLE_OPTIONS,
    OFFICER_UNASSIGNED_LABEL,
    POSITION_PAY_BASIS_LABELS,
    POSITION_PAY_BASIS_OPTIONS,
)
from validators import ValidationResult
from validators_dates import format_date, parse_date, storage_date_str

EMAIL_RE = re.compile(r"^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$")
PHONE_RE = re.compile(r"^[\\d\\s\\-\\(\\)\\+\\.A-Za-z]+$")

'''
            cross = ""
        if filename == "validators_rules.py":
            header = '''"""Schedule / day-off / rest / night-min validators (validators split)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Tuple

from config import NIGHT_MINIMUM_OFFICERS, REQUEST_STATUS
from validators import (
    REQUESTABLE_STATUSES,
    SWAP_REQUESTABLE_STATUSES,
    TERMINAL_STATUSES,
    ValidationResult,
)
from validators_dates import format_date, parse_date, storage_date, storage_date_str

'''
            cross = ""
        if filename == "validators_ops.py":
            header = '''"""Holiday / availability / override / settings validators (validators split)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from config import DATE_INPUT_HINT
from validators import ValidationResult
from validators_dates import format_date, parse_date, storage_date_str
from validators_officer import normalize_optional_text, officer_has_assignment

'''
            cross = ""

        out.write_text(header + cross + body, encoding="utf-8")
        print(f"wrote {filename} ({out.read_text(encoding='utf-8').count(chr(10)) + 1} lines)")

    # Build facade validators.py
    facade = '''"""
Centralized validation for Dodgeville PD Scheduler.
All request/schedule checks live here — logic and UI call these helpers.

Split modules (implementation):
  validators_dates · validators_rules · validators_officer · validators_auth · validators_ops
This file is the stable import surface: ``from validators import …``
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from config import REQUEST_STATUS

EMAIL_RE = re.compile(r"^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$")
PHONE_RE = re.compile(r"^[\\d\\s\\-\\(\\)\\+\\.A-Za-z]+$")

REQUESTABLE_STATUSES = (
    REQUEST_STATUS["pending"],
    REQUEST_STATUS["pending_manual"],
)
SWAP_REQUESTABLE_STATUSES = REQUESTABLE_STATUSES
TERMINAL_STATUSES = ("Approved", "Rejected")


@dataclass
class ValidationResult:
    ok: bool
    message: str = ""

    @classmethod
    def pass_(cls) -> "ValidationResult":
        return cls(ok=True)

    @classmethod
    def fail(cls, message: str) -> "ValidationResult":
        return cls(ok=False, message=message)


from validators_dates import *  # noqa: E402,F403
from validators_rules import *  # noqa: E402,F403
from validators_officer import *  # noqa: E402,F403
from validators_auth import *  # noqa: E402,F403
from validators_ops import *  # noqa: E402,F403
'''
    SRC.write_text(facade, encoding="utf-8")
    print(f"facade validators.py ({facade.count(chr(10)) + 1} lines)")


if __name__ == "__main__":
    main()
