"""Password / username / role validators (validators split)."""

from __future__ import annotations

import re
from typing import Optional

from config import REQUEST_STATUS  # noqa: F401 — kept for symmetry
from validators import ValidationResult
from validators_officer import normalize_optional_text


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
