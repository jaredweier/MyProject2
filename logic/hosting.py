"""Online / desktop hosting configuration.

Supports two commercial modes:
  - On-prem / desktop: ``python main.py`` or portable build
  - Online (hosted): ``python main.py --web`` or Docker / reverse proxy

Environment (production online):
  SCHEDULER_UI_MODE=web
  SCHEDULER_HOST=0.0.0.0
  SCHEDULER_PORT=8080
  SCHEDULER_STORAGE_SECRET=<long random>
  SCHEDULER_PUBLIC_URL=https://chronos.example.gov
  SCHEDULER_TENANT_ID=optional-agency-slug
  SCHEDULER_TENANT_NAME=Agency display name
  SCHEDULER_TRUST_PROXY=1
"""

from __future__ import annotations

import os
from typing import Any, Dict


def _truthy(raw: str) -> bool:
    return (raw or "").strip().lower() in ("1", "true", "yes", "on")


def get_hosting_config() -> Dict[str, Any]:
    """Runtime hosting posture for UI + ops."""
    mode = (os.environ.get("SCHEDULER_UI_MODE") or "").strip().lower()
    host = (os.environ.get("SCHEDULER_HOST") or "").strip()
    try:
        port = int(os.environ.get("SCHEDULER_PORT") or "8080")
    except (TypeError, ValueError):
        port = 8080
    public_url = (os.environ.get("SCHEDULER_PUBLIC_URL") or "").strip().rstrip("/")
    tenant_id = (os.environ.get("SCHEDULER_TENANT_ID") or "").strip()
    tenant_name = (os.environ.get("SCHEDULER_TENANT_NAME") or "").strip()
    online = mode == "web" or host in ("0.0.0.0", "::")
    try:
        from logic.tenant import get_tenant_info, tenant_db_path

        tinfo = get_tenant_info()
        db_path = tinfo.get("db_path") or tenant_db_path()
    except Exception:
        tinfo = {}
        db_path = os.environ.get("SCHEDULER_DB_PATH") or ""

    return {
        "mode": mode or ("web" if online else "local"),
        "online": online,
        "host": host or ("0.0.0.0" if online else "127.0.0.1"),
        "port": port,
        "public_url": public_url,
        "tenant_id": tenant_id or tinfo.get("tenant_id") or "default",
        "tenant_name": tenant_name or tinfo.get("tenant_name") or "",
        "data_root": tinfo.get("data_root"),
        "db_path": db_path,
        "trust_proxy": _truthy(os.environ.get("SCHEDULER_TRUST_PROXY", "0")),
        "storage_secret_from_env": bool((os.environ.get("SCHEDULER_STORAGE_SECRET") or "").strip()),
        "license_mode": (os.environ.get("SCHEDULER_LICENSE_MODE") or "on_prem").strip().lower(),
        # on_prem | hosted_subscription — commercial packaging hint only
    }


def public_base_url() -> str:
    cfg = get_hosting_config()
    if cfg["public_url"]:
        return cfg["public_url"]
    return f"http://{cfg['host']}:{cfg['port']}"


def deployment_checklist() -> Dict[str, Any]:
    """Implementation kit: what must be set before agency go-live."""
    cfg = get_hosting_config()
    checks = []

    def add(key: str, ok: bool, hint: str) -> None:
        checks.append({"key": key, "ok": ok, "hint": hint})

    add(
        "storage_secret",
        cfg["storage_secret_from_env"] or not cfg["online"],
        "Set SCHEDULER_STORAGE_SECRET for multi-user online hosts",
    )
    add(
        "public_url",
        bool(cfg["public_url"]) or not cfg["online"],
        "Set SCHEDULER_PUBLIC_URL for SMS/email deep links",
    )
    add(
        "tls",
        True,  # cannot detect reverse proxy TLS from app
        "Terminate TLS at reverse proxy (nginx/Caddy/IIS) in production",
    )
    try:
        from logic.notify_channels import get_notify_channel_config

        ncfg = get_notify_channel_config()
        add(
            "email_channel",
            (not ncfg.get("email_enabled")) or bool(ncfg.get("smtp_host")),
            "Enable notify_email + SMTP host, or leave email off",
        )
        add(
            "sms_channel",
            (not ncfg.get("sms_enabled")) or bool(ncfg.get("twilio_ready")),
            "Enable notify_sms + Twilio SID/token/from, or leave SMS off",
        )
    except Exception:
        add("notify", False, "Notify config unavailable")

    ready = all(c["ok"] for c in checks if c["key"] != "tls")
    return {
        "success": True,
        "hosting": cfg,
        "checks": checks,
        "ready_for_online": ready and cfg["online"],
        "product": "Chronos Command",
        "vendor": "Weierworks Technologies, LLC",
    }
