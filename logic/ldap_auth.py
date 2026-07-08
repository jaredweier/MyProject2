"""Optional LDAP / Active Directory authentication scaffold.

Enable with environment variables:
  SCHEDULER_LDAP_ENABLED=1
  SCHEDULER_LDAP_SERVER=ldap://dc.example.com
  SCHEDULER_LDAP_BASE_DN=DC=example,DC=com
  SCHEDULER_LDAP_BIND_DN= (optional service account)
  SCHEDULER_LDAP_BIND_PASSWORD=
"""

from __future__ import annotations

import os
from typing import Dict


def ldap_auth_enabled() -> bool:
    return os.environ.get("SCHEDULER_LDAP_ENABLED", "").strip().lower() in ("1", "true", "yes")


def _ldap_settings() -> Dict[str, str]:
    return {
        "server": os.environ.get("SCHEDULER_LDAP_SERVER", "").strip(),
        "base_dn": os.environ.get("SCHEDULER_LDAP_BASE_DN", "").strip(),
        "bind_dn": os.environ.get("SCHEDULER_LDAP_BIND_DN", "").strip(),
        "bind_password": os.environ.get("SCHEDULER_LDAP_BIND_PASSWORD", ""),
        "user_filter": os.environ.get(
            "SCHEDULER_LDAP_USER_FILTER",
            "(sAMAccountName={username})",
        ),
    }


def try_ldap_authenticate(username: str, password: str) -> Dict:
    """
    Attempt LDAP bind for the user. Returns success dict with ldap_username on pass.
    When ldap3 is not installed or LDAP is misconfigured, returns a clear failure.
    """
    if not ldap_auth_enabled():
        return {"success": False, "message": "LDAP not enabled", "skipped": True}

    settings = _ldap_settings()
    if not settings["server"] or not settings["base_dn"]:
        return {"success": False, "message": "LDAP server or base DN not configured"}

    if not username.strip() or not password:
        return {"success": False, "message": "Username and password required"}

    try:
        import ldap3
    except ImportError:
        return {
            "success": False,
            "message": "LDAP enabled but ldap3 package is not installed (pip install ldap3)",
        }

    user_filter = settings["user_filter"].format(username=ldap3.utils.conv.escape_filter_chars(username.strip()))
    server = ldap3.Server(settings["server"], get_info=ldap3.NONE)
    conn = ldap3.Connection(
        server, user=settings["bind_dn"] or None, password=settings["bind_password"] or None, auto_bind=True
    )
    conn.search(settings["base_dn"], user_filter, attributes=["cn", "mail", "sAMAccountName"])
    if not conn.entries:
        return {"success": False, "message": "Invalid username or password"}

    entry = conn.entries[0]
    user_dn = entry.entry_dn
    user_conn = ldap3.Connection(server, user=user_dn, password=password, auto_bind=False)
    if not user_conn.bind():
        return {"success": False, "message": "Invalid username or password"}

    display = str(getattr(entry, "cn", username) or username)
    return {
        "success": True,
        "ldap_username": username.strip(),
        "display_name": display,
        "user_dn": user_dn,
    }
