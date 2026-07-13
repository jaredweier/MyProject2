"""Browser/session state for multi-user web + desktop clients."""

from __future__ import annotations

from typing import Any, Optional

from nicegui import app

from permissions import role_has_permission


def current_user() -> Optional[dict[str, Any]]:
    return app.storage.user.get("user")


def set_user(user: dict[str, Any] | None) -> None:
    if user is None:
        app.storage.user.pop("user", None)
        return
    # JSON-serializable only
    clean: dict[str, Any] = {}
    for k, v in user.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            clean[k] = v
    app.storage.user["user"] = clean


def can(permission: str) -> bool:
    user = current_user()
    if not user:
        return False
    return role_has_permission(str(user.get("role") or ""), permission)


def is_officer() -> bool:
    user = current_user()
    return bool(user and user.get("role") == "Officer")


def linked_officer_id() -> Optional[int]:
    user = current_user()
    if not user or user.get("officer_id") is None:
        return None
    try:
        return int(user["officer_id"])
    except (TypeError, ValueError):
        return None


def display_name() -> str:
    user = current_user() or {}
    return str(user.get("officer_name") or user.get("username") or "User")


def initials() -> str:
    name = display_name()
    parts = [p for p in name.replace(".", " ").split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return (name[:2] or "U").upper()
