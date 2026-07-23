"""TOTP multi-factor authentication (RFC 6238) for app_users.

Per-user, opt-in-by-administration: a user has MFA enrolled once
``mfa_enabled=1`` and ``mfa_secret`` is set on their ``app_users`` row.
``authenticate_user`` in logic/users.py checks password first; when the
matched user has MFA enabled, it returns ``mfa_required`` instead of
completing login, and the caller must then call ``verify_mfa_login`` with
the 6-digit code from the user's authenticator app.

Mirrors the enable/verify/disable + audit-logging shape of logic/ldap_auth.py
and logic/certifications.py so this fits the codebase's existing patterns
rather than introducing a new one.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from database import connection


def mfa_available() -> bool:
    try:
        import pyotp  # noqa: F401

        return True
    except ImportError:
        return False


def _get_user_row(user_id: int) -> Optional[Dict[str, Any]]:
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, mfa_secret, mfa_enabled FROM app_users WHERE id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
    return dict(row) if row else None


def mfa_status(user_id: int) -> Dict[str, Any]:
    user = _get_user_row(user_id)
    if not user:
        return {"success": False, "message": "User not found"}
    return {
        "success": True,
        "mfa_enabled": bool(user.get("mfa_enabled")),
        "mfa_available": mfa_available(),
    }


def begin_mfa_enrollment(user_id: int, *, issuer: str = "Chronos Command") -> Dict[str, Any]:
    """Generate (but not yet activate) a new TOTP secret for the user.

    The secret is stored immediately so a page reload doesn't lose it, but
    ``mfa_enabled`` stays 0 until ``confirm_mfa_enrollment`` verifies a code
    generated from it — this prevents a user from locking themselves out
    with a secret they never actually loaded into an authenticator app.
    """
    if not mfa_available():
        return {"success": False, "message": "pyotp is not installed (pip install pyotp)"}
    user = _get_user_row(user_id)
    if not user:
        return {"success": False, "message": "User not found"}

    import pyotp

    secret = pyotp.random_base32()
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE app_users SET mfa_secret = ?, mfa_enabled = 0, mfa_enrolled_at = NULL WHERE id = ?",
            (secret, user_id),
        )
        conn.commit()

    provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user["username"], issuer_name=issuer)
    return {
        "success": True,
        "secret": secret,
        "provisioning_uri": provisioning_uri,
        "message": "Scan the QR/enter the secret in an authenticator app, then confirm with a code",
    }


def confirm_mfa_enrollment(user_id: int, code: str) -> Dict[str, Any]:
    """Verify the first code from a newly-enrolled authenticator and activate MFA."""
    if not mfa_available():
        return {"success": False, "message": "pyotp is not installed (pip install pyotp)"}
    user = _get_user_row(user_id)
    if not user:
        return {"success": False, "message": "User not found"}
    secret = user.get("mfa_secret")
    if not secret:
        return {"success": False, "message": "No pending MFA enrollment — start enrollment first"}

    import pyotp

    if not pyotp.TOTP(secret).verify(str(code).strip(), valid_window=1):
        return {"success": False, "message": "Invalid code"}

    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE app_users SET mfa_enabled = 1, mfa_enrolled_at = CURRENT_TIMESTAMP WHERE id = ?",
            (user_id,),
        )
        conn.commit()

    from logic.users import log_audit_action

    log_audit_action("user.mfa_enabled", "app_user", user_id, user_id)
    return {"success": True, "message": "MFA enabled"}


def verify_mfa_login(user_id: int, code: str) -> Dict[str, Any]:
    """Second factor for login — call after password auth returns mfa_required."""
    if not mfa_available():
        return {"success": False, "message": "pyotp is not installed (pip install pyotp)"}
    user = _get_user_row(user_id)
    if not user or not user.get("mfa_enabled") or not user.get("mfa_secret"):
        return {"success": False, "message": "MFA is not enabled for this user"}

    import pyotp

    if not pyotp.TOTP(user["mfa_secret"]).verify(str(code).strip(), valid_window=1):
        from logic.users import log_audit_action

        log_audit_action("user.mfa_failed", "app_user", user_id, user_id)
        return {"success": False, "message": "Invalid code"}
    return {"success": True}


def disable_mfa(user_id: int, actor_user_id: Optional[int] = None) -> Dict[str, Any]:
    """Turn off MFA for a user — self-service or Administration reset."""
    user = _get_user_row(user_id)
    if not user:
        return {"success": False, "message": "User not found"}

    if actor_user_id is not None and actor_user_id != user_id:
        from logic.users import get_user_by_id
        from permissions import role_has_permission

        actor = get_user_by_id(actor_user_id)
        if not actor or not role_has_permission(actor["role"], "security.manage_mfa"):
            return {"success": False, "message": "Administration access required to reset another user's MFA"}

    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE app_users SET mfa_secret = NULL, mfa_enabled = 0, mfa_enrolled_at = NULL WHERE id = ?",
            (user_id,),
        )
        conn.commit()

    from logic.users import log_audit_action

    log_audit_action("user.mfa_disabled", "app_user", user_id, actor_user_id or user_id)
    return {"success": True, "message": "MFA disabled"}
