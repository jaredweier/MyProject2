"""Holiday / availability / override / settings validators (validators split)."""

from __future__ import annotations

import re
from typing import Optional

from config import DATE_INPUT_HINT
from validators import ValidationResult
from validators_dates import parse_date
from validators_officer import normalize_optional_text


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
    from validators_rules import is_officer_active

    if not officer:
        return ValidationResult.fail("Officer not found")
    if not is_officer_active(officer):
        return ValidationResult.fail("Officer is inactive")
    try:
        parse_date(unavailable_date)
    except ValueError:
        return ValidationResult.fail(f"Date must be {DATE_INPUT_HINT}")
    return ValidationResult.pass_()


def validate_manual_override(
    original: Optional[dict],
    replacement: Optional[dict],
    override_date: str,
    reason: str = "",
) -> ValidationResult:
    from validators_rules import is_officer_active, validate_cycle_date

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
