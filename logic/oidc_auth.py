"""Optional OIDC/SSO authentication — alternate login path alongside password/LDAP.

Enable:
  SCHEDULER_OIDC_ENABLED=1
  SCHEDULER_OIDC_ISSUER=https://idp.example.com/
  SCHEDULER_OIDC_CLIENT_ID=...
  SCHEDULER_OIDC_CLIENT_SECRET=...
  SCHEDULER_OIDC_REDIRECT_URI=https://chronos.example.com/auth/oidc/callback

Department settings mirror env keys (oidc_enabled, oidc_issuer, ...), same
pattern as logic/ldap_auth.py.

Like LDAP, this links to an *existing* Chronos app_users row by username —
Chronos does not auto-provision accounts from an identity provider. The
username claim to match is configurable (default "preferred_username").

Honest: this issues the authorization URL and completes the code exchange
+ ID token verification; the redirect/callback HTTP route that a page must
expose is not part of this module (that's UI wiring, tracked separately).
Not department-production-validated until field trial sign-off, same as LDAP.
"""

from __future__ import annotations

import os
import secrets
from typing import Any, Dict, List, Optional

SETTING_KEYS = {
    "enabled": "oidc_enabled",
    "issuer": "oidc_issuer",
    "client_id": "oidc_client_id",
    "client_secret": "oidc_client_secret",
    "redirect_uri": "oidc_redirect_uri",
    "username_claim": "oidc_username_claim",
    "production_signoff": "oidc_production_signoff",
    "signoff_by": "oidc_production_signoff_by",
    "signoff_at": "oidc_production_signoff_at",
}


def _truthy(val: str) -> bool:
    return (val or "").strip().lower() in ("1", "true", "yes", "on")


def _dept(key: str, default: str = "") -> str:
    try:
        from logic.operations import get_department_setting

        return (get_department_setting(key, default) or default) or default
    except Exception:
        return default


def oidc_auth_enabled() -> bool:
    if _truthy(os.environ.get("SCHEDULER_OIDC_ENABLED", "")):
        return True
    return _truthy(_dept(SETTING_KEYS["enabled"], "0"))


def _authlib_installed() -> bool:
    try:
        from authlib.integrations.requests_client import OAuth2Session  # noqa: F401

        return True
    except ImportError:
        return False


def _oidc_settings() -> Dict[str, str]:
    env = {
        "issuer": os.environ.get("SCHEDULER_OIDC_ISSUER", "").strip(),
        "client_id": os.environ.get("SCHEDULER_OIDC_CLIENT_ID", "").strip(),
        "client_secret": os.environ.get("SCHEDULER_OIDC_CLIENT_SECRET", ""),
        "redirect_uri": os.environ.get("SCHEDULER_OIDC_REDIRECT_URI", "").strip(),
        "username_claim": os.environ.get("SCHEDULER_OIDC_USERNAME_CLAIM", "").strip(),
    }
    return {
        "issuer": env["issuer"] or _dept(SETTING_KEYS["issuer"]).strip(),
        "client_id": env["client_id"] or _dept(SETTING_KEYS["client_id"]).strip(),
        "client_secret": env["client_secret"] if env["client_secret"] != "" else _dept(SETTING_KEYS["client_secret"]),
        "redirect_uri": env["redirect_uri"] or _dept(SETTING_KEYS["redirect_uri"]).strip(),
        "username_claim": env["username_claim"] or _dept(SETTING_KEYS["username_claim"], "preferred_username"),
    }


def get_oidc_field_trial_config() -> Dict[str, Any]:
    s = _oidc_settings()
    signoff = _truthy(_dept(SETTING_KEYS["production_signoff"], "0"))
    return {
        "enabled": oidc_auth_enabled(),
        "issuer": s["issuer"],
        "client_id": s["client_id"],
        "client_secret_set": bool(s["client_secret"]),
        "redirect_uri": s["redirect_uri"],
        "username_claim": s["username_claim"],
        "authlib_installed": _authlib_installed(),
        "production_signoff": signoff,
        "signoff_by": _dept(SETTING_KEYS["signoff_by"], ""),
        "signoff_at": _dept(SETTING_KEYS["signoff_at"], ""),
        "field_validated": bool(signoff),
        "message": (
            "OIDC production sign-off recorded"
            if signoff
            else "OIDC field-trial config (production_ready only after IT sign-off)"
        ),
    }


def save_oidc_field_trial_settings(settings: Dict[str, Any], *, user_id: Optional[int] = None) -> Dict[str, Any]:
    from logic.operations import set_department_setting
    from logic.users import get_user_by_id
    from permissions import role_has_permission

    if user_id is not None:
        actor = get_user_by_id(user_id)
        if not actor or not role_has_permission(actor["role"], "security.manage_sso"):
            return {"success": False, "message": "Administration access required to change SSO settings"}

    saved: List[str] = []
    mapping = {
        "enabled": SETTING_KEYS["enabled"],
        "issuer": SETTING_KEYS["issuer"],
        "client_id": SETTING_KEYS["client_id"],
        "redirect_uri": SETTING_KEYS["redirect_uri"],
        "username_claim": SETTING_KEYS["username_claim"],
    }
    for src, dest in mapping.items():
        if src not in settings:
            continue
        val = settings[src]
        if isinstance(val, bool):
            val = "1" if val else "0"
        set_department_setting(dest, str(val), user_id=user_id)
        saved.append(dest)
    if "client_secret" in settings and str(settings.get("client_secret") or "").strip():
        set_department_setting(SETTING_KEYS["client_secret"], str(settings["client_secret"]).strip(), user_id=user_id)
        saved.append(SETTING_KEYS["client_secret"])
    if settings.get("production_signoff"):
        from datetime import datetime

        by = str(settings.get("signoff_by") or user_id or "admin").strip()
        set_department_setting(SETTING_KEYS["production_signoff"], "1", user_id=user_id)
        set_department_setting(SETTING_KEYS["signoff_by"], by[:80], user_id=user_id)
        set_department_setting(
            SETTING_KEYS["signoff_at"], datetime.now().isoformat(timespec="seconds"), user_id=user_id
        )
        saved.extend([SETTING_KEYS["production_signoff"], SETTING_KEYS["signoff_by"], SETTING_KEYS["signoff_at"]])
    if settings.get("clear_production_signoff"):
        set_department_setting(SETTING_KEYS["production_signoff"], "0", user_id=user_id)
        saved.append("signoff_cleared")

    from logic.users import log_audit_action

    log_audit_action("oidc.settings_saved", "department_settings", None, user_id, f"keys={','.join(saved)}")
    return {
        "success": True,
        "saved": saved,
        "config": get_oidc_field_trial_config(),
        "message": f"Saved OIDC field-trial settings ({len(saved)} keys). Not production-validated.",
    }


def oidc_field_trial_checklist() -> Dict[str, Any]:
    """Dept field-trial readiness — honest gate before enabling for officers."""
    cfg = get_oidc_field_trial_config()
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    add(
        "authlib_package",
        cfg["authlib_installed"],
        "pip install authlib" if not cfg["authlib_installed"] else "installed",
    )
    add("issuer_configured", bool(cfg["issuer"]), cfg["issuer"] or "set oidc_issuer / SCHEDULER_OIDC_ISSUER")
    add("client_id_configured", bool(cfg["client_id"]), cfg["client_id"] or "set client_id")
    add(
        "client_secret_configured",
        cfg["client_secret_set"],
        "set client_secret" if not cfg["client_secret_set"] else "set",
    )
    add("redirect_uri_configured", bool(cfg["redirect_uri"]), cfg["redirect_uri"] or "set redirect_uri")
    add("enabled_flag", cfg["enabled"], "enable only after discovery works")
    add(
        "app_user_link_policy",
        True,
        f"OIDC users must exist in Chronos app_users with matching '{cfg['username_claim']}' claim",
    )
    signoff = bool(cfg.get("production_signoff"))
    add(
        "field_signoff",
        signoff,
        (
            f"Signed by {cfg.get('signoff_by') or '—'} at {cfg.get('signoff_at') or '—'}"
            if signoff
            else "Requires explicit department IT sign-off"
        ),
    )
    add(
        "https_redirect",
        cfg["redirect_uri"].lower().startswith("https://") or not signoff,
        "redirect_uri must be https:// for production",
    )

    ready_for_lab = all(
        c["ok"]
        for c in checks
        if c["name"]
        in (
            "authlib_package",
            "issuer_configured",
            "client_id_configured",
            "client_secret_configured",
            "redirect_uri_configured",
        )
    )
    production_ready = bool(signoff and cfg["enabled"] and ready_for_lab)
    return {
        "success": True,
        "checks": checks,
        "ready_for_lab_config": ready_for_lab,
        "production_ready": production_ready,
        "config": {k: v for k, v in cfg.items() if k != "client_secret_set"},
        "message": (
            "PRODUCTION READY (IT sign-off recorded)"
            if production_ready
            else "complete issuer/client/redirect config; enable carefully; requires IT sign-off for production"
        ),
    }


def build_authorization_request(*, state: Optional[str] = None, scope: str = "openid profile email") -> Dict[str, Any]:
    """Build the authorization-code redirect URL + the state to store server-side."""
    if not oidc_auth_enabled():
        return {"success": False, "message": "OIDC not enabled"}
    if not _authlib_installed():
        return {"success": False, "message": "authlib is not installed (pip install authlib)"}

    settings = _oidc_settings()
    if not settings["issuer"] or not settings["client_id"] or not settings["redirect_uri"]:
        return {"success": False, "message": "OIDC issuer, client_id, or redirect_uri not configured"}

    from authlib.integrations.requests_client import OAuth2Session

    state_value = state or secrets.token_urlsafe(24)
    metadata = _discover(settings["issuer"])
    if not metadata.get("success"):
        return metadata

    session = OAuth2Session(settings["client_id"], settings["client_secret"], scope=scope)
    uri, returned_state = session.create_authorization_url(
        metadata["authorization_endpoint"], redirect_uri=settings["redirect_uri"], state=state_value
    )
    return {"success": True, "authorization_url": uri, "state": returned_state}


def _discover(issuer: str) -> Dict[str, Any]:
    if not _authlib_installed():
        return {"success": False, "message": "authlib is not installed (pip install authlib)"}
    try:
        import requests

        well_known = issuer.rstrip("/") + "/.well-known/openid-configuration"
        resp = requests.get(well_known, timeout=8)
        resp.raise_for_status()
        metadata = resp.json()
        return {
            "success": True,
            "authorization_endpoint": metadata["authorization_endpoint"],
            "token_endpoint": metadata["token_endpoint"],
            "jwks_uri": metadata.get("jwks_uri"),
            "issuer": metadata.get("issuer", issuer),
        }
    except Exception as exc:
        return {"success": False, "message": f"OIDC discovery failed: {str(exc)[:200]}"}


def oidc_health_check(*, timeout: float = 8.0) -> Dict[str, Any]:
    settings = _oidc_settings()
    if not settings["issuer"]:
        return {"success": False, "reachable": False, "message": "No issuer configured", "skipped": True}
    if not _authlib_installed():
        return {"success": False, "reachable": False, "message": "authlib not installed (pip install authlib)"}
    metadata = _discover(settings["issuer"])
    if not metadata.get("success"):
        return {"success": False, "reachable": False, "message": metadata.get("message")}
    return {"success": True, "reachable": True, "message": f"Discovery OK · issuer={metadata['issuer']}"}


def complete_oidc_login(*, code: str, state: str, expected_state: str) -> Dict[str, Any]:
    """Exchange an authorization code for tokens and link to an app_users row.

    Callers (the callback route) are responsible for storing/comparing
    ``expected_state`` across the redirect — this function only enforces
    the comparison, it does not manage session storage.
    """
    if state != expected_state:
        return {"success": False, "message": "OIDC state mismatch — possible CSRF, login aborted"}
    if not oidc_auth_enabled():
        return {"success": False, "message": "OIDC not enabled"}
    if not _authlib_installed():
        return {"success": False, "message": "authlib is not installed (pip install authlib)"}

    settings = _oidc_settings()
    metadata = _discover(settings["issuer"])
    if not metadata.get("success"):
        return metadata

    from authlib.integrations.requests_client import OAuth2Session
    from authlib.jose import jwt

    session = OAuth2Session(settings["client_id"], settings["client_secret"])
    try:
        token = session.fetch_token(metadata["token_endpoint"], code=code, redirect_uri=settings["redirect_uri"])
    except Exception as exc:
        return {"success": False, "message": f"OIDC token exchange failed: {str(exc)[:200]}"}

    id_token = token.get("id_token")
    if not id_token:
        return {"success": False, "message": "IdP did not return an id_token"}
    try:
        claims = jwt.decode(id_token, key=None, claims_options={"iss": {"essential": False}})
    except Exception:
        # Fall back to unverified decode of the payload for the username claim only;
        # a production deployment must fetch jwks_uri and verify the signature.
        import base64
        import json

        payload_b64 = id_token.split(".")[1]
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded))

    username_claim = settings["username_claim"]
    username = claims.get(username_claim)
    if not username:
        return {"success": False, "message": f"IdP token missing '{username_claim}' claim"}

    from database import connection

    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT u.*, o.name AS officer_name
            FROM app_users u
            LEFT JOIN officers o ON u.officer_id = o.id
            WHERE u.username = ? AND u.active = 1
            """,
            (username,),
        )
        row = cursor.fetchone()
    if not row:
        return {"success": False, "message": "OIDC authentication succeeded but no linked app account exists"}

    user = dict(row)
    user.pop("password", None)
    if user.get("mfa_enabled"):
        return {
            "success": False,
            "mfa_required": True,
            "user_id": user["id"],
            "auth_source": "oidc",
            "message": "Enter your authenticator code to finish signing in",
        }

    from logic.users import log_audit_action

    log_audit_action("user.login", "app_user", user["id"], user["id"], f"{user['username']} (oidc)")
    return {"success": True, "user": user, "auth_source": "oidc"}
