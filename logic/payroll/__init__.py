"""Payroll entries, timecard, and pay-period management (package facade).

Stable import path: ``from logic.payroll import get_pay_period, ...``
Same star-export surface as the former monolith module.
"""

from __future__ import annotations

from logic.payroll.banks import *  # noqa: F403

# Explicit re-export of private helpers used by sibling modules / tests
from logic.payroll.banks import _ensure_officer_time_banks, _months_between  # noqa: F401
from logic.payroll.entries import *  # noqa: F403
from logic.payroll.pay_codes import *  # noqa: F403
from logic.payroll.period import *  # noqa: F403
from logic.payroll.timecard import *  # noqa: F403
from logic.payroll.timecard import (  # noqa: F401
    _TIMECARD_WORKING_STATUSES,
    _apply_night_differential,
    _approved_day_off_request_type,
    _summarize_pay_period_hours,
    _timecard_defaults_for_schedule_status,
    _upsert_timecard_approval,
)
from logic.payroll.withholding import *  # noqa: F403

# Public API = star-imports above (former monolith surface).
