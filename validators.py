"""
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

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[\d\s\-\(\)\+\.A-Za-z]+$")

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


from validators_auth import *  # noqa: E402,F403
from validators_dates import *  # noqa: E402,F403

# Private helpers used across logic/* (star-import skips leading underscore)
from validators_dates import (  # noqa: E402,F401
    _mdy_datetime,
    _mdy_short,
    _time_to_minutes,
)
from validators_officer import *  # noqa: E402,F403
from validators_ops import *  # noqa: E402,F403
from validators_rules import *  # noqa: E402,F403
from validators_rules import (  # noqa: E402,F401
    _night_shift_starts,
    _officer_unavailable_on_date,
)

# Lazy re-exports from validators_config (avoids circular import: config imports validators)
_CONFIG_EXPORTS = frozenset(
    {
        "can_officer_work_day_band",
        "validate_officer_certifications",
        "validate_shift_bid_eligibility",
        "validate_staffing_settings",
        "validate_rotation_settings",
        "parse_bids_due_datetime",
    }
)


def __getattr__(name: str):
    if name in _CONFIG_EXPORTS:
        import validators_config as _vc

        return getattr(_vc, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
