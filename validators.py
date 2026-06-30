"""
Centralized validation for Dodgeville PD Scheduler.
All request/schedule checks live here — logic.py and UI call these helpers.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Tuple

from config import (
    DATE_DISPLAY_FORMAT,
    DATE_INPUT_HINT,
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
    ROTATION_BASE_DATE,
    SHIFT_TIMES,
)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[\d\s\-\(\)\+\.A-Za-z]+$")

NIGHT_SHIFT_STARTS = {SHIFT_TIMES[3][0], SHIFT_TIMES[4][0]}  # 15:00, 19:00
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


def format_date(value) -> str:
    """Format a date or date string for UI display (DD-MM-YYYY)."""
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime(DATE_DISPLAY_FORMAT)
    if value:
        return parse_date(str(value)).strftime(DATE_DISPLAY_FORMAT)
    return ""


def format_datetime(value) -> str:
    """Format a timestamp for UI display (DD-MM-YYYY HH:MM)."""
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime(DATETIME_DISPLAY_FORMAT)
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            parsed = datetime.strptime(text[:26], fmt)
            return parsed.strftime(DATETIME_DISPLAY_FORMAT)
        except ValueError:
            continue
    if len(text) >= 10:
        return f"{format_date(text[:10])} 00:00"
    return text


def format_row_dates(row: dict, *fields: str) -> dict:
    """Return a copy of row with named date fields formatted for display/export."""
    out = dict(row)
    for field in fields:
        if out.get(field):
            out[field] = format_date(out[field])
    return out


def storage_date(value: date) -> str:
    """ISO date string for SQLite storage and internal keys."""
    return value.strftime(DATE_STORAGE_FORMAT)


def storage_date_str(value: str) -> str:
    return storage_date(parse_date(value))


def parse_date_filter(value: Optional[str]) -> Optional[str]:
    """Parse optional user date filter to ISO storage string."""
    if not value or not str(value).strip():
        return None
    return storage_date(parse_date(value.strip()))


def _time_to_minutes(value: str) -> Optional[int]:
    text = (value or "").strip()
    if not text or ":" not in text:
        return None
    parts = text.split(":", 1)
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
    except ValueError:
        return None
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        return None
    return hours * 60 + minutes


def is_overnight_shift(time_in: str, time_out: str) -> bool:
    """True when time_out falls on the next calendar day (e.g. 19:00 → 06:00)."""
    start_mins = _time_to_minutes(time_in)
    end_mins = _time_to_minutes(time_out)
    if start_mins is None or end_mins is None:
        return False
    return end_mins <= start_mins


def parse_date(value: str) -> date:
    text = (value or "").strip()
    if not text:
        raise ValueError(f"Date must be {DATE_INPUT_HINT}")
    for fmt in (DATE_DISPLAY_FORMAT, DATE_STORAGE_FORMAT):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Date must be {DATE_INPUT_HINT}")


def is_officer_active(officer: dict) -> bool:
    return officer.get("active") == 1


def is_night_shift(shift_start: str) -> bool:
    return shift_start in NIGHT_SHIFT_STARTS


def applies_night_minimum(target_date: date, shift_start: str, is_high_risk_night) -> bool:
    """Night staffing rules apply only to night shifts on Fri/Sat."""
    return is_high_risk_night(target_date) and is_night_shift(shift_start)


def validate_cycle_date(target_date: date) -> ValidationResult:
    if target_date < ROTATION_BASE_DATE:
        return ValidationResult.fail(
            f"Date {format_date(target_date)} is before rotation base {format_date(ROTATION_BASE_DATE)}"
        )
    return ValidationResult.pass_()


def validate_officer_working(is_working: bool, request_date: date) -> ValidationResult:
    if not is_working:
        return ValidationResult.fail(f"Officer is not scheduled to work on {format_date(request_date)}")
    return ValidationResult.pass_()


def validate_request_status(status: str, action: str) -> ValidationResult:
    if action in ("approve", "reject") and status not in REQUESTABLE_STATUSES:
        allowed = ", ".join(REQUESTABLE_STATUSES)
        return ValidationResult.fail(f"Cannot {action} request with status '{status}' (only {allowed} allowed)")
    return ValidationResult.pass_()


def validate_no_duplicate_pending(has_pending: bool, officer_name: str, request_date: str) -> ValidationResult:
    if has_pending:
        return ValidationResult.fail(f"{officer_name} already has a pending request for {format_date(request_date)}")
    return ValidationResult.pass_()


def validate_day_off_request(
    officer: Optional[dict],
    request_date: str,
) -> ValidationResult:
    if not officer:
        return ValidationResult.fail("Officer not found")
    if not is_officer_active(officer):
        return ValidationResult.fail("Officer is inactive")

    try:
        parsed = parse_date(request_date)
    except ValueError:
        return ValidationResult.fail(f"Date must be {DATE_INPUT_HINT}")

    cycle_check = validate_cycle_date(parsed)
    if not cycle_check.ok:
        return cycle_check

    return ValidationResult.pass_()


def validate_request_type(request_type: str) -> ValidationResult:
    from config import DAY_OFF_REQUEST_TYPES

    normalized = (request_type or "").strip()
    if not normalized:
        return ValidationResult.fail("Request type is required")
    if normalized not in DAY_OFF_REQUEST_TYPES:
        allowed = ", ".join(DAY_OFF_REQUEST_TYPES)
        return ValidationResult.fail(f"Request type must be one of: {allowed}")
    return ValidationResult.pass_()


def _officer_unavailable_on_date(officer_id: int, target_date: date) -> bool:
    from database import get_connection

    date_str = target_date.isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 1 FROM officer_availability
        WHERE officer_id = ? AND unavailable_date = ?
    """,
        (officer_id, date_str),
    )
    found = cursor.fetchone() is not None
    conn.close()
    return found


def validate_process_day_off(
    request: dict,
    officer: Optional[dict],
    action: str,
) -> ValidationResult:
    if not request:
        return ValidationResult.fail("Request not found")

    status_check = validate_request_status(request.get("status", ""), action)
    if not status_check.ok:
        return status_check

    if action == "reject":
        return ValidationResult.pass_()

    if not officer:
        return ValidationResult.fail("Officer not found")

    return ValidationResult.pass_()


def validate_swap_status(status: str, action: str) -> ValidationResult:
    if action in ("approve", "reject") and status not in SWAP_REQUESTABLE_STATUSES:
        allowed = ", ".join(SWAP_REQUESTABLE_STATUSES)
        return ValidationResult.fail(f"Cannot {action} swap with status '{status}' (only {allowed} allowed)")
    return ValidationResult.pass_()


def validate_process_shift_swap(swap: Optional[dict], action: str) -> ValidationResult:
    if not swap:
        return ValidationResult.fail("Swap request not found")
    status_check = validate_swap_status(swap.get("status", ""), action)
    if not status_check.ok:
        return status_check
    return ValidationResult.pass_()


def night_minimum_violation(current_count: int) -> bool:
    """True if removing one officer would drop below minimum."""
    return current_count <= NIGHT_MINIMUM_OFFICERS


def validate_minimum_rest_gap(
    gap_hours: Optional[float],
    min_hours: float,
    context: str = "",
) -> ValidationResult:
    """True if gap_hours is None (no adjacent shift) or meets minimum rest."""
    if gap_hours is None:
        return ValidationResult.pass_()
    if gap_hours < min_hours:
        prefix = f"{context}: " if context else ""
        return ValidationResult.fail(f"{prefix}{gap_hours:.1f}h between shifts (minimum {min_hours:.0f}h required)")
    return ValidationResult.pass_()


def normalize_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def validate_officer_name(name: str) -> ValidationResult:
    if not name or not name.strip():
        return ValidationResult.fail("Name is required")
    if len(name.strip()) > 100:
        return ValidationResult.fail("Name must be 100 characters or fewer")
    return ValidationResult.pass_()


def validate_officer_email(email: Optional[str]) -> ValidationResult:
    email = normalize_optional_text(email)
    if email is None:
        return ValidationResult.pass_()
    if len(email) > 120:
        return ValidationResult.fail("Email must be 120 characters or fewer")
    if not EMAIL_RE.match(email):
        return ValidationResult.fail("Invalid email address")
    return ValidationResult.pass_()


def validate_officer_phone(phone: Optional[str]) -> ValidationResult:
    phone = normalize_optional_text(phone)
    if phone is None:
        return ValidationResult.pass_()
    if len(phone) > 30:
        return ValidationResult.fail("Phone number is too long")
    if not PHONE_RE.match(phone):
        return ValidationResult.fail("Phone number contains invalid characters")
    digits = sum(c.isdigit() for c in phone)
    if digits < 7:
        return ValidationResult.fail("Phone number must have at least 7 digits")
    return ValidationResult.pass_()


def validate_officer_address(address: Optional[str]) -> ValidationResult:
    address = normalize_optional_text(address)
    if address is None:
        return ValidationResult.pass_()
    if len(address) > 500:
        return ValidationResult.fail("Address must be 500 characters or fewer")
    return ValidationResult.pass_()


def validate_officer_start_date(start_date: Optional[str]) -> ValidationResult:
    start_date = normalize_optional_text(start_date)
    if start_date is None:
        return ValidationResult.pass_()
    try:
        parse_date(start_date)
    except ValueError:
        return ValidationResult.fail(f"Start date must be {DATE_INPUT_HINT}")
    return ValidationResult.pass_()


def validate_seniority_rank(rank: int) -> ValidationResult:
    if rank < 1:
        return ValidationResult.fail("Seniority rank must be at least 1")
    return ValidationResult.pass_()


def normalize_officer_squad(squad: Optional[str]) -> Optional[str]:
    if squad is None:
        return None
    value = squad.strip()
    if not value or value == OFFICER_UNASSIGNED_LABEL:
        return None
    return value


def normalize_officer_shift(
    shift_start: Optional[str],
    shift_end: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    start = (shift_start or "").strip() or None
    end = (shift_end or "").strip() or None
    if start is None and end is None:
        return None, None
    return start, end


def officer_has_assignment(officer: Optional[dict]) -> bool:
    if not officer:
        return False
    return bool(officer.get("squad")) and bool(officer.get("shift_start"))


def format_officer_squad_display(squad: Optional[str]) -> str:
    return OFFICER_UNASSIGNED_LABEL if not squad else squad


def format_officer_shift_display(
    shift_start: Optional[str],
    shift_end: Optional[str],
) -> str:
    if not shift_start or not shift_end:
        return OFFICER_UNASSIGNED_LABEL
    return f"{shift_start} - {shift_end}"


def parse_officer_shift_ui(selection: str) -> Tuple[Optional[str], Optional[str]]:
    if selection == OFFICER_UNASSIGNED_LABEL:
        return None, None
    parts = selection.split("-", 1)
    if len(parts) != 2:
        return None, None
    return parts[0].strip(), parts[1].strip()


def validate_officer_squad(squad: Optional[str]) -> ValidationResult:
    normalized = normalize_officer_squad(squad)
    if normalized is None:
        return ValidationResult.pass_()
    if normalized not in ("A", "B"):
        return ValidationResult.fail("Squad must be A, B, or Unassigned")
    return ValidationResult.pass_()


def validate_officer_shift(
    shift_start: Optional[str],
    shift_end: Optional[str],
) -> ValidationResult:
    start, end = normalize_officer_shift(shift_start, shift_end)
    if start is None and end is None:
        return ValidationResult.pass_()
    if not start or not end:
        return ValidationResult.fail("Shift requires both start and end times, or Unassigned")
    if (start, end) not in set(SHIFT_TIMES.values()):
        return ValidationResult.fail("Invalid shift time combination")
    return ValidationResult.pass_()


def validate_officer_pay_rate(pay_rate: float) -> ValidationResult:
    if pay_rate < 0:
        return ValidationResult.fail("Pay rate cannot be negative")
    return ValidationResult.pass_()


def normalize_officer_job_title(job_title: Optional[str]) -> Optional[str]:
    text = normalize_optional_text(job_title)
    if not text:
        return None
    if text in OFFICER_TITLE_OPTIONS:
        return text
    mapped = OFFICER_TITLE_ALIASES.get(text.lower())
    if mapped:
        return mapped
    return text


def validate_officer_job_title(job_title: Optional[str]) -> ValidationResult:
    text = normalize_optional_text(job_title)
    if not text:
        return ValidationResult.pass_()
    normalized = normalize_officer_job_title(text)
    if normalized not in OFFICER_TITLE_OPTIONS:
        allowed = ", ".join(OFFICER_TITLE_OPTIONS)
        return ValidationResult.fail(f"Title must be one of: {allowed}")
    return ValidationResult.pass_()


def format_officer_title_display(job_title: Optional[str]) -> str:
    return normalize_officer_job_title(job_title) or ""


def normalize_position_pay_basis(value: Optional[str]) -> str:
    text = (value or "hourly").strip().lower()
    label_map = {label.lower(): key for key, label in POSITION_PAY_BASIS_LABELS.items()}
    if text in POSITION_PAY_BASIS_OPTIONS:
        return text
    if text in label_map:
        return label_map[text]
    return "hourly"


def position_amount_to_hourly(
    amount: float,
    pay_basis: str,
    annual_hours: float = DEFAULT_ANNUAL_HOURS,
) -> float:
    basis = normalize_position_pay_basis(pay_basis)
    if amount <= 0:
        return 0.0
    if basis == "hourly":
        return round(amount, 4)
    if basis == "monthly":
        return round((amount * 12) / annual_hours, 4)
    return round(amount / annual_hours, 4)


def format_position_pay_summary(config: Optional[dict]) -> str:
    if not config:
        return "Not set"
    amount = float(config.get("amount") or 0)
    basis = normalize_position_pay_basis(config.get("pay_basis"))
    suffix = {"hourly": "/hr", "monthly": "/mo", "yearly": "/yr"}[basis]
    salary_note = " · Salary" if config.get("is_salary") else ""
    hourly = position_amount_to_hourly(amount, basis)
    return f"${amount:,.2f}{suffix}{salary_note}  (${hourly:.2f}/hr equiv.)"


def validate_position_pay_entry(
    title: str,
    amount: float,
    pay_basis: str,
    is_salary: bool = False,
) -> ValidationResult:
    if title not in OFFICER_TITLE_OPTIONS:
        return ValidationResult.fail(f"Unknown position title: {title}")
    if amount < 0:
        return ValidationResult.fail(f"{title}: amount cannot be negative")
    if amount <= 0:
        return ValidationResult.fail(f"{title}: amount must be greater than zero")
    basis = normalize_position_pay_basis(pay_basis)
    if basis not in POSITION_PAY_BASIS_OPTIONS:
        allowed = ", ".join(POSITION_PAY_BASIS_LABELS.values())
        return ValidationResult.fail(f"{title}: pay basis must be {allowed}")
    return ValidationResult.pass_()


def validate_annual_hours_target(hours: float) -> ValidationResult:
    if hours < 1000 or hours > 3000:
        return ValidationResult.fail("Annual hours target should be between 1000 and 3000")
    return ValidationResult.pass_()


def validate_overtime_multiplier(multiplier: float) -> ValidationResult:
    if multiplier < 1.0 or multiplier > 3.0:
        return ValidationResult.fail("Overtime multiplier should be between 1.0 and 3.0")
    return ValidationResult.pass_()


def validate_officer_profile(
    name: str,
    seniority_rank: int,
    squad: Optional[str],
    shift_start: Optional[str],
    shift_end: Optional[str],
    pay_rate: float,
    start_date: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    address: Optional[str] = None,
    job_title: Optional[str] = None,
    annual_hours_target: float = 2080.0,
    overtime_multiplier: float = 1.5,
) -> ValidationResult:
    checks = (
        validate_officer_name(name),
        validate_seniority_rank(seniority_rank),
        validate_officer_squad(squad),
        validate_officer_shift(shift_start, shift_end),
        validate_officer_pay_rate(pay_rate),
        validate_officer_start_date(start_date),
        validate_officer_email(email),
        validate_officer_phone(phone),
        validate_officer_address(address),
        validate_officer_job_title(job_title),
        validate_annual_hours_target(annual_hours_target),
        validate_overtime_multiplier(overtime_multiplier),
    )
    for check in checks:
        if not check.ok:
            return check
    return ValidationResult.pass_()


def validate_holiday(name: str, holiday_date: str) -> ValidationResult:
    name = normalize_optional_text(name)
    if not name:
        return ValidationResult.fail("Holiday name is required")
    try:
        parse_date(holiday_date)
    except ValueError:
        return ValidationResult.fail(f"Holiday date must be {DATE_INPUT_HINT}")
    return ValidationResult.pass_()


def validate_availability_entry(officer: Optional[dict], unavailable_date: str) -> ValidationResult:
    if not officer:
        return ValidationResult.fail("Officer not found")
    if not is_officer_active(officer):
        return ValidationResult.fail("Officer is inactive")
    try:
        parse_date(unavailable_date)
    except ValueError:
        return ValidationResult.fail(f"Date must be {DATE_INPUT_HINT}")
    return ValidationResult.pass_()


def validate_password(password: str) -> ValidationResult:
    if not password or len(password.strip()) < 4:
        return ValidationResult.fail("Password must be at least 4 characters")
    return ValidationResult.pass_()


def validate_username(username: str) -> ValidationResult:
    username = normalize_optional_text(username)
    if not username:
        return ValidationResult.fail("Username is required")
    if len(username) < 3 or len(username) > 32:
        return ValidationResult.fail("Username must be 3–32 characters")
    if not re.match(r"^[a-zA-Z0-9._-]+$", username):
        return ValidationResult.fail("Username may only contain letters, digits, . _ -")
    return ValidationResult.pass_()


def validate_app_user_role(role: str) -> ValidationResult:
    from permissions import USER_ROLES

    if role not in USER_ROLES:
        return ValidationResult.fail(f"Role must be one of: {', '.join(USER_ROLES)}")
    return ValidationResult.pass_()


def validate_user_role_change(
    actor: Optional[dict],
    target_user: dict,
    new_role: str,
) -> ValidationResult:
    from permissions import role_has_permission

    if not actor:
        return ValidationResult.fail("Signed-in user required")
    if actor.get("id") == target_user.get("id") and new_role != target_user.get("role"):
        return ValidationResult.fail("You cannot change your own role")
    if role_has_permission(actor["role"], "users.manage"):
        return ValidationResult.pass_()
    if not role_has_permission(actor["role"], "users.edit_role"):
        return ValidationResult.fail("You do not have permission to change user roles")
    if target_user.get("role") == "Administration":
        return ValidationResult.fail("Only administrators can modify Administration accounts")
    if new_role == "Administration":
        return ValidationResult.fail("Only administrators can assign the Administration role")
    return ValidationResult.pass_()


def validate_manual_override(
    original: Optional[dict],
    replacement: Optional[dict],
    override_date: str,
    reason: str = "",
) -> ValidationResult:
    if not original:
        return ValidationResult.fail("Original officer not found")
    if not replacement:
        return ValidationResult.fail("Replacement officer not found")
    if not is_officer_active(original):
        return ValidationResult.fail(f"{original['name']} is not active")
    if not is_officer_active(replacement):
        return ValidationResult.fail(f"{replacement['name']} is not active")
    if original["id"] == replacement["id"]:
        return ValidationResult.fail("Replacement must be a different officer")
    try:
        parsed = parse_date(override_date)
    except ValueError:
        return ValidationResult.fail(f"Date must be {DATE_INPUT_HINT}")
    cycle_check = validate_cycle_date(parsed)
    if not cycle_check.ok:
        return cycle_check
    reason = normalize_optional_text(reason) or "Manual Coverage"
    if len(reason) > 120:
        return ValidationResult.fail("Reason must be 120 characters or fewer")
    return ValidationResult.pass_()


def validate_setting_key(key: str) -> ValidationResult:
    key = normalize_optional_text(key)
    if not key:
        return ValidationResult.fail("Setting key is required")
    if not re.match(r"^[a-z][a-z0-9_]*$", key):
        return ValidationResult.fail("Setting key must be lowercase letters, digits, underscores")
    return ValidationResult.pass_()
