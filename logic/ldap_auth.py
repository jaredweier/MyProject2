"""Optional LDAP / Active Directory authentication + field-trial helpers.

Enable:
  SCHEDULER_LDAP_ENABLED=1
  SCHEDULER_LDAP_SERVER=ldap://dc.example.com
  SCHEDULER_LDAP_BASE_DN=DC=example,DC=com
  SCHEDULER_LDAP_BIND_DN= (optional service account)
  SCHEDULER_LDAP_BIND_PASSWORD=

Field trial:
  SCHEDULER_LDAP_SANDBOX=1 — accept local password when LDAP host unreachable
    (only for staged trial accounts; never production default)
  Department settings mirror env keys (ldap_enabled, ldap_server, …)

Honest: not department-production-validated until field trial sign-off.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

SETTING_KEYS = {
    "enabled": "ldap_enabled",
    "server": "ldap_server",
    "base_dn": "ldap_base_dn",
    "bind_dn": "ldap_bind_dn",
    "bind_password": "ldap_bind_password",
    "user_filter": "ldap_user_filter",
    "sandbox": "ldap_sandbox",
    "use_ssl": "ldap_use_ssl",
    "production_signoff": "ldap_production_signoff",
    "signoff_by": "ldap_production_signoff_by",
    "signoff_at": "ldap_production_signoff_at",
}


def _truthy(val: str) -> bool:
    return (val or "").strip().lower() in ("1", "true", "yes", "on")


def _dept(key: str, default: str = "") -> str:
    try:
        from logic.operations import get_department_setting

        return (get_department_setting(key, default) or default) or default
    except Exception:
        return default


def ldap_auth_enabled() -> bool:
    if _truthy(os.environ.get("SCHEDULER_LDAP_ENABLED", "")):
        return True
    return _truthy(_dept(SETTING_KEYS["enabled"], "0"))


def ldap_sandbox_enabled() -> bool:
    if _truthy(os.environ.get("SCHEDULER_LDAP_SANDBOX", "")):
        return True
    return _truthy(_dept(SETTING_KEYS["sandbox"], "0"))


def _ldap_settings() -> Dict[str, str]:
    env_server = os.environ.get("SCHEDULER_LDAP_SERVER", "").strip()
    env_base = os.environ.get("SCHEDULER_LDAP_BASE_DN", "").strip()
    env_bind = os.environ.get("SCHEDULER_LDAP_BIND_DN", "").strip()
    env_pw = os.environ.get("SCHEDULER_LDAP_BIND_PASSWORD", "")
    env_filter = os.environ.get("SCHEDULER_LDAP_USER_FILTER", "").strip()
    return {
        "server": env_server or _dept(SETTING_KEYS["server"], "").strip(),
        "base_dn": env_base or _dept(SETTING_KEYS["base_dn"], "").strip(),
        "bind_dn": env_bind or _dept(SETTING_KEYS["bind_dn"], "").strip(),
        "bind_password": env_pw if env_pw != "" else _dept(SETTING_KEYS["bind_password"], ""),
        "user_filter": env_filter
        or _dept(SETTING_KEYS["user_filter"], "(sAMAccountName={username})")
        or "(sAMAccountName={username})",
    }


def get_ldap_field_trial_config() -> Dict[str, Any]:
    s = _ldap_settings()
    signoff = _truthy(_dept(SETTING_KEYS["production_signoff"], "0"))
    use_ssl = _truthy(_dept(SETTING_KEYS["use_ssl"], "0")) or (s["server"] or "").lower().startswith("ldaps://")
    return {
        "enabled": ldap_auth_enabled(),
        "sandbox": ldap_sandbox_enabled(),
        "server": s["server"],
        "base_dn": s["base_dn"],
        "bind_dn": s["bind_dn"],
        "bind_password_set": bool(s["bind_password"]),
        "user_filter": s["user_filter"],
        "use_ssl": use_ssl,
        "ldap3_installed": _ldap3_installed(),
        "production_signoff": signoff,
        "signoff_by": _dept(SETTING_KEYS["signoff_by"], ""),
        "signoff_at": _dept(SETTING_KEYS["signoff_at"], ""),
        "field_validated": bool(signoff),
        "message": (
            "LDAP production sign-off recorded"
            if signoff
            else "LDAP field-trial config (production_ready only after IT sign-off)"
        ),
    }


def save_ldap_field_trial_settings(
    settings: Dict[str, Any],
    *,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    from logic.operations import set_department_setting

    saved = []
    mapping = {
        "enabled": SETTING_KEYS["enabled"],
        "ldap_enabled": SETTING_KEYS["enabled"],
        "server": SETTING_KEYS["server"],
        "ldap_server": SETTING_KEYS["server"],
        "base_dn": SETTING_KEYS["base_dn"],
        "ldap_base_dn": SETTING_KEYS["base_dn"],
        "bind_dn": SETTING_KEYS["bind_dn"],
        "ldap_bind_dn": SETTING_KEYS["bind_dn"],
        "user_filter": SETTING_KEYS["user_filter"],
        "ldap_user_filter": SETTING_KEYS["user_filter"],
        "sandbox": SETTING_KEYS["sandbox"],
        "ldap_sandbox": SETTING_KEYS["sandbox"],
        "use_ssl": SETTING_KEYS["use_ssl"],
        "ldap_use_ssl": SETTING_KEYS["use_ssl"],
    }
    for src, dest in mapping.items():
        if src not in settings:
            continue
        val = settings[src]
        if isinstance(val, bool):
            val = "1" if val else "0"
        set_department_setting(dest, str(val), user_id=user_id)
        saved.append(dest)
    if "bind_password" in settings and str(settings.get("bind_password") or "").strip():
        set_department_setting(
            SETTING_KEYS["bind_password"],
            str(settings["bind_password"]).strip(),
            user_id=user_id,
        )
        saved.append(SETTING_KEYS["bind_password"])
    # Explicit IT production sign-off (never auto)
    if settings.get("production_signoff") or settings.get("ldap_production_signoff"):
        from datetime import datetime

        by = str(settings.get("signoff_by") or settings.get("signed_by") or user_id or "admin").strip()
        set_department_setting(SETTING_KEYS["production_signoff"], "1", user_id=user_id)
        set_department_setting(SETTING_KEYS["signoff_by"], by[:80], user_id=user_id)
        set_department_setting(
            SETTING_KEYS["signoff_at"],
            datetime.now().isoformat(timespec="seconds"),
            user_id=user_id,
        )
        saved.extend([SETTING_KEYS["production_signoff"], SETTING_KEYS["signoff_by"], SETTING_KEYS["signoff_at"]])
    if settings.get("clear_production_signoff"):
        set_department_setting(SETTING_KEYS["production_signoff"], "0", user_id=user_id)
        set_department_setting(SETTING_KEYS["signoff_by"], "", user_id=user_id)
        set_department_setting(SETTING_KEYS["signoff_at"], "", user_id=user_id)
        saved.append("signoff_cleared")
    try:
        from logic.users import log_audit_action

        log_audit_action("ldap.settings_saved", "department_settings", None, user_id, f"keys={','.join(saved)}")
    except Exception:
        pass
    return {
        "success": True,
        "saved": saved,
        "config": get_ldap_field_trial_config(),
        "message": f"Saved LDAP field-trial settings ({len(saved)} keys). Not production-validated.",
    }


def _ldap3_installed() -> bool:
    try:
        import ldap3  # noqa: F401

        return True
    except ImportError:
        return False


def ldap_health_check(*, timeout: float = 5.0) -> Dict[str, Any]:
    """Connect + optional bind check for field trial (no user password)."""
    if not ldap_auth_enabled() and not _ldap_settings()["server"]:
        return {
            "success": False,
            "reachable": False,
            "message": "LDAP not enabled / no server configured",
            "skipped": True,
        }
    settings = _ldap_settings()
    if not settings["server"] or not settings["base_dn"]:
        return {
            "success": False,
            "reachable": False,
            "message": "LDAP server or base DN not configured",
        }
    if not _ldap3_installed():
        return {
            "success": False,
            "reachable": False,
            "message": "ldap3 package not installed (pip install ldap3)",
            "ldap3_installed": False,
        }
    try:
        import ldap3

        use_ssl = _truthy(_dept(SETTING_KEYS["use_ssl"], "0")) or settings["server"].lower().startswith("ldaps://")
        server = ldap3.Server(
            settings["server"],
            get_info=ldap3.NONE,
            connect_timeout=timeout,
            use_ssl=use_ssl,
        )
        conn = ldap3.Connection(
            server,
            user=settings["bind_dn"] or None,
            password=settings["bind_password"] or None,
            auto_bind=False,
            receive_timeout=timeout,
        )
        if not conn.open():
            return {"success": False, "reachable": False, "message": "LDAP open failed"}
        if settings["bind_dn"]:
            if not conn.bind():
                return {
                    "success": False,
                    "reachable": True,
                    "message": f"Server reachable but bind failed: {conn.result}",
                }
            msg = "LDAP reachable · service bind OK"
        else:
            msg = "LDAP reachable · anonymous/no bind DN (user bind at login)"
        conn.unbind()
        return {
            "success": True,
            "reachable": True,
            "bound": bool(settings["bind_dn"]),
            "message": msg,
            "field_validated": False,
        }
    except Exception as exc:
        return {
            "success": False,
            "reachable": False,
            "message": f"LDAP health check failed: {str(exc)[:200]}",
        }


def ldap_field_trial_checklist() -> Dict[str, Any]:
    """Dept field-trial readiness — honest gate before enabling for officers."""
    cfg = get_ldap_field_trial_config()
    health = ldap_health_check()
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    add("ldap3_package", cfg["ldap3_installed"], "pip install ldap3" if not cfg["ldap3_installed"] else "installed")
    add("server_configured", bool(cfg["server"]), cfg["server"] or "set ldap_server / SCHEDULER_LDAP_SERVER")
    add("base_dn_configured", bool(cfg["base_dn"]), cfg["base_dn"] or "set base DN")
    add("enabled_flag", cfg["enabled"], "enable only after health OK")
    add("health_reachable", bool(health.get("reachable")), health.get("message") or "")
    add(
        "app_user_link_policy",
        True,
        "LDAP users must exist in Chronos app_users with same username",
    )
    add(
        "sandbox_warning",
        not cfg["sandbox"] or (cfg["sandbox"] and not cfg["enabled"]),
        "Sandbox OK for lab only — disable before production",
    )
    signoff = bool(cfg.get("production_signoff"))
    add(
        "field_signoff",
        signoff,
        (
            f"Signed by {cfg.get('signoff_by') or '—'} at {cfg.get('signoff_at') or '—'}"
            if signoff
            else "Requires explicit department IT sign-off (Security page → record production sign-off)"
        ),
    )
    add(
        "not_sandbox_for_prod",
        not cfg["sandbox"] or not signoff,
        "Sandbox must be off when production sign-off is recorded",
    )
    add(
        "ssl_or_ldaps",
        bool(cfg.get("use_ssl") or (cfg.get("server") or "").lower().startswith("ldaps://")) or not signoff,
        "Prefer ldaps:// or ldap_use_ssl for production",
    )

    ready_for_lab = all(
        c["ok"] for c in checks if c["name"] in ("ldap3_package", "server_configured", "base_dn_configured")
    )
    ready_for_trial_login = ready_for_lab and health.get("reachable") and cfg["enabled"]
    # production_ready only with explicit sign-off + healthy + enabled + not sandbox
    production_ready = bool(
        signoff and cfg["enabled"] and not cfg["sandbox"] and health.get("reachable") and ready_for_lab
    )
    return {
        "success": True,
        "checks": checks,
        "ready_for_lab_config": ready_for_lab,
        "ready_for_trial_login": bool(ready_for_trial_login),
        "production_ready": production_ready,
        "sandbox": cfg["sandbox"],
        "health": health,
        "config": {k: v for k, v in cfg.items() if k != "bind_password"},
        "message": (
            "Field trial checklist: "
            + (
                "PRODUCTION READY (IT sign-off recorded)"
                if production_ready
                else (
                    "lab config OK · trial login path ready"
                    if ready_for_trial_login
                    else "complete server/base DN/ldap3; run health; enable carefully"
                )
            )
            + ("" if production_ready else " · production_ready=false until IT sign-off + health + not sandbox")
        ),
    }


def export_ldap_field_trial_report(*, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Write IT field-trial packet (JSON + short MD) — no live bind secrets.

    production_ready stays false until checklist gate; this is documentation for IT.
    """
    import json
    from datetime import datetime
    from pathlib import Path

    from paths import data_path

    checklist = ldap_field_trial_checklist()
    cfg = get_ldap_field_trial_config()
    health = checklist.get("health") or ldap_health_check()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(data_path("exports"))
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "product": "Chronos Command",
        "honest": (
            "Not production-validated until production_ready=true (IT sign-off + reachable AD + enabled + sandbox off)."
        ),
        "production_ready": bool(checklist.get("production_ready")),
        "ready_for_lab_config": bool(checklist.get("ready_for_lab_config")),
        "ready_for_trial_login": bool(checklist.get("ready_for_trial_login")),
        "checklist": checklist.get("checks") or [],
        "config": {k: v for k, v in cfg.items() if k not in ("bind_password",) and "password" not in k.lower()},
        "health": {
            k: health.get(k)
            for k in ("success", "reachable", "message", "skipped", "ldap3_installed")
            if k in health or True
        },
        "it_steps": [
            "Install ldap3 if missing: pip install ldap3",
            "Set server (prefer ldaps://) and base DN on Security → LDAP field trial",
            "Run Health check until reachable",
            "Map Chronos app_users.username to AD sAMAccountName",
            "Lab: sandbox on only while testing; disable before sign-off",
            "IT records production sign-off on Security page when validated",
            "Confirm production_ready=true on checklist before requiring LDAP for officers",
        ],
    }
    json_path = out_dir / f"ldap_field_trial_{stamp}.json"
    md_path = out_dir / f"ldap_field_trial_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = [
        "# LDAP field trial report — Chronos Command",
        "",
        f"Generated: {payload['generated_at']}",
        f"production_ready: **{payload['production_ready']}**",
        f"ready_for_lab_config: {payload['ready_for_lab_config']}",
        f"ready_for_trial_login: {payload['ready_for_trial_login']}",
        "",
        payload["honest"],
        "",
        "## Checklist",
    ]
    for c in payload["checklist"]:
        mark = "OK" if c.get("ok") else "—"
        lines.append(f"- [{mark}] {c.get('name')}: {c.get('detail')}")
    lines.extend(["", "## IT steps"])
    for i, s in enumerate(payload["it_steps"], 1):
        lines.append(f"{i}. {s}")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    try:
        from logic.users import log_audit_action

        log_audit_action(
            "ldap.field_trial_export",
            "export",
            None,
            user_id,
            f"json={json_path.name}",
        )
    except Exception:
        pass
    return {
        "success": True,
        "json_path": str(json_path),
        "md_path": str(md_path),
        "production_ready": payload["production_ready"],
        "message": f"LDAP field-trial report → {md_path.name} (production_ready={payload['production_ready']})",
    }


def try_ldap_authenticate(username: str, password: str) -> Dict:
    """
    Attempt LDAP bind for the user. Returns success dict with ldap_username on pass.
    When ldap3 is not installed or LDAP is misconfigured, returns a clear failure.
    Sandbox: if enabled and server unreachable, fall through with skipped so local auth may run
    only when caller allows — we return sandbox_fallback flag instead of success.
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

    try:
        user_filter = settings["user_filter"].format(username=ldap3.utils.conv.escape_filter_chars(username.strip()))
        server = ldap3.Server(settings["server"], get_info=ldap3.NONE, connect_timeout=8)
        conn = ldap3.Connection(
            server,
            user=settings["bind_dn"] or None,
            password=settings["bind_password"] or None,
            auto_bind=True,
            receive_timeout=8,
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
            "auth_source": "ldap",
        }
    except Exception as exc:
        if ldap_sandbox_enabled():
            return {
                "success": False,
                "skipped": True,
                "sandbox_fallback": True,
                "message": f"LDAP sandbox fallback (server error): {str(exc)[:120]}",
            }
        return {"success": False, "message": f"LDAP error: {str(exc)[:200]}"}
