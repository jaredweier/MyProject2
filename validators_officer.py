"""Officer roster / title / pay validators (validators split)."""

from __future__ import annotations

import re
from datetime import date
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
from validators_dates import parse_date

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[\d\s\-\(\)\+\.A-Za-z]+$")


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
    from logic.staffing_config import get_active_shift_time_values

    if (start, end) not in get_active_shift_time_values():
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
    from logic.roster_titles import get_officer_title_options

    for option in get_officer_title_options():
        if option.lower() == text.lower():
            return option
    return text


def is_command_staff_title(job_title: Optional[str]) -> bool:
    from config import COMMAND_STAFF_TITLES

    title = normalize_officer_job_title(job_title)
    return bool(title and title in COMMAND_STAFF_TITLES)


def officer_uses_command_staff_schedule(officer: Optional[dict]) -> bool:
    return bool(officer and is_command_staff_title(officer.get("job_title")))


def is_command_staff_weekday(target_date: date) -> bool:
    """Command staff work Monday–Friday (weekday 0–4)."""
    return target_date.weekday() < 5


def validate_officer_job_title(job_title: Optional[str]) -> ValidationResult:
    text = normalize_optional_text(job_title)
    if not text:
        return ValidationResult.pass_()
    from logic.roster_titles import is_assignable_officer_title

    normalized = normalize_officer_job_title(text)
    if not is_assignable_officer_title(normalized):
        return ValidationResult.fail("Title must be a standard rank or a supervisor-added custom title")
    return ValidationResult.pass_()


def format_officer_title_display(job_title: Optional[str]) -> str:
    return normalize_officer_job_title(job_title) or ""


def default_pay_basis_for_title(title: Optional[str]) -> str:
    from config import YEARLY_SALARY_TITLES

    if title in YEARLY_SALARY_TITLES:
        return "yearly"
    return "monthly"


def is_yearly_salary_title(title: Optional[str]) -> bool:
    from config import YEARLY_SALARY_TITLES

    return bool(title and title in YEARLY_SALARY_TITLES)


def default_annual_hours_for_title(title: Optional[str]) -> float:
    from config import DEFAULT_ANNUAL_HOURS, SALARY_ANNUAL_HOURS, YEARLY_SALARY_TITLES

    if title in YEARLY_SALARY_TITLES:
        return SALARY_ANNUAL_HOURS
    return DEFAULT_ANNUAL_HOURS


def normalize_position_pay_basis(value: Optional[str]) -> str:
    text = (value or "hourly").strip().lower()
    label_map = {label.lower(): key for key, label in POSITION_PAY_BASIS_LABELS.items()}
    if text in POSITION_PAY_BASIS_OPTIONS:
        return text
    if text in label_map:
        return label_map[text]
    return "hourly"


def position_amount_to_monthly(
    amount: float,
    pay_basis: str,
    annual_hours: float = DEFAULT_ANNUAL_HOURS,
) -> float:
    basis = normalize_position_pay_basis(pay_basis)
    if amount <= 0:
        return 0.0
    if basis == "monthly":
        return round(amount, 2)
    if basis == "yearly":
        return round(amount / 12, 2)
    return round((amount * annual_hours) / 12, 2)


def monthly_pay_to_hourly(
    monthly: float,
    annual_hours: float = DEFAULT_ANNUAL_HOURS,
) -> float:
    if monthly <= 0:
        return 0.0
    return round((monthly * 12) / annual_hours, 4)


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
        return monthly_pay_to_hourly(amount, annual_hours)
    return round(amount / annual_hours, 4)


def format_position_pay_summary(config: Optional[dict]) -> str:
    if not config:
        return "Not set"
    amount = float(config.get("amount") or 0)
    basis = normalize_position_pay_basis(config.get("pay_basis"))
    annual_hours = float(config.get("annual_hours") or default_annual_hours_for_title(config.get("title")))
    suffix = {"hourly": "/hr", "monthly": "/mo", "yearly": "/yr"}[basis]
    salary_note = " · Salary" if config.get("is_salary") else ""
    monthly = float(config.get("monthly_equivalent") or position_amount_to_monthly(amount, basis, annual_hours))
    hourly = float(config.get("hourly_equivalent") or position_amount_to_hourly(amount, basis, annual_hours))
    per_period = config.get("per_pay_period_amount")
    period_note = f"  (${per_period:,.2f}/pay period)" if per_period else ""
    return f"${amount:,.2f}{suffix}{salary_note}  (${monthly:,.2f}/mo → ${hourly:.2f}/hr){period_note}"


def validate_position_pay_entry(
    title: str,
    amount: float,
    pay_basis: str,
    is_salary: bool = False,
    annual_hours: Optional[float] = None,
) -> ValidationResult:
    from logic.roster_titles import is_assignable_officer_title

    if not is_assignable_officer_title(title):
        return ValidationResult.fail(f"Unknown position title: {title}")
    if amount < 0:
        return ValidationResult.fail(f"{title}: amount cannot be negative")
    if amount <= 0:
        return ValidationResult.fail(f"{title}: amount must be greater than zero")
    basis = normalize_position_pay_basis(pay_basis)
    if basis not in POSITION_PAY_BASIS_OPTIONS:
        allowed = ", ".join(POSITION_PAY_BASIS_LABELS.values())
        return ValidationResult.fail(f"{title}: pay basis must be {allowed}")
    hours = float(annual_hours if annual_hours is not None else default_annual_hours_for_title(title))
    hours_check = validate_annual_hours_target(hours)
    if not hours_check.ok:
        return ValidationResult.fail(f"{title}: {hours_check.message}")
    return ValidationResult.pass_()


def validate_annual_hours_target(hours: float) -> ValidationResult:
    if hours < 1000 or hours > 3000:
        return ValidationResult.fail("Annual hours target should be between 1000 and 3000")
    return ValidationResult.pass_()


def validate_overtime_multiplier(multiplier: float) -> ValidationResult:
    if multiplier < 1.0 or multiplier > 3.0:
        return ValidationResult.fail("Overtime multiplier should be between 1.0 and 3.0")
    return ValidationResult.pass_()


def validate_pay_code_rate_multiplier(multiplier: float, entry_type: str) -> ValidationResult:
    if multiplier < 0 or multiplier > 10.0:
        return ValidationResult.fail(f"{entry_type}: rate multiplier must be between 0 and 10")
    return ValidationResult.pass_()


def validate_pay_code_comp_ratio(ratio: float, entry_type: str) -> ValidationResult:
    if ratio < 0 or ratio > 5.0:
        return ValidationResult.fail(f"{entry_type}: comp credit ratio must be between 0 and 5")
    return ValidationResult.pass_()


def format_pay_code_formula(entry_type: str, rule: dict) -> str:
    if not rule.get("paid", True):
        return "Unpaid — $0"
    if rule.get("uses_callback_minimum"):
        return "max(hours, callback min) × base rate"
    multiplier = rule.get("rate_multiplier", 1.0)
    if entry_type == "Holiday Overtime" and rule.get("premium_multiplier"):
        premium = rule["premium_multiplier"]
        return f"hours × base rate × {multiplier} (premium × {premium})"
    if rule.get("counts_as_overtime"):
        return f"hours × base rate × {multiplier}"
    if rule.get("comp_bank_credit_ratio"):
        ratio = rule["comp_bank_credit_ratio"]
        return f"hours × base rate × {multiplier} · comp +{ratio}× hrs"
    return f"hours × base rate × {multiplier}"


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
