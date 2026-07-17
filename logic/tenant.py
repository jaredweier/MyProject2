"""Multi-tenant data roots — one SQLite DB + media per agency (subscription).

Env:
  SCHEDULER_TENANT_ID=agency-slug   → data under tenants/<slug>/
  SCHEDULER_DB_PATH=...             → explicit DB (wins over tenant default)
  SCHEDULER_TENANT_NAME=Display

Not shared-schema multi-tenant: each agency is isolated files (safer for LE).
Online hosts run one process per tenant or set TENANT_ID per container.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def _slug(raw: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", (raw or "").strip().lower()).strip("-")
    return s[:64] or "default"


def current_tenant_id() -> str:
    return _slug(os.environ.get("SCHEDULER_TENANT_ID", "") or "default")


def current_tenant_name() -> str:
    return (os.environ.get("SCHEDULER_TENANT_NAME") or "").strip() or current_tenant_id()


def tenant_data_root(tenant_id: Optional[str] = None) -> Path:
    """Writable root for one agency: <app>/tenants/<id>/ or <app>/ when default + no flag."""
    from paths import app_dir

    tid = _slug(tenant_id or current_tenant_id())
    # default tenant without explicit SCHEDULER_TENANT_ID keeps legacy layout
    explicit = bool((os.environ.get("SCHEDULER_TENANT_ID") or "").strip())
    if tid == "default" and not explicit:
        return Path(app_dir())
    root = Path(app_dir()) / "tenants" / tid
    return root


def ensure_tenant_dirs(tenant_id: Optional[str] = None) -> Path:
    root = tenant_data_root(tenant_id)
    for sub in ("photos", "logs", "backups", "exports", "data"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def tenant_db_path(tenant_id: Optional[str] = None) -> str:
    env = (os.environ.get("SCHEDULER_DB_PATH") or "").strip()
    if env and tenant_id is None:
        return env
    root = ensure_tenant_dirs(tenant_id)
    # Prefer tenants/<id>/dodgeville_scheduler.db (or data/ subfolder)
    db = root / "dodgeville_scheduler.db"
    return str(db)


def list_local_tenants() -> List[Dict[str, Any]]:
    from paths import app_dir

    base = Path(app_dir()) / "tenants"
    out: List[Dict[str, Any]] = []
    # Always include default / legacy
    legacy_db = Path(app_dir()) / "dodgeville_scheduler.db"
    out.append(
        {
            "tenant_id": "default",
            "path": str(Path(app_dir())),
            "db_exists": legacy_db.is_file(),
            "active": current_tenant_id() == "default"
            and not bool((os.environ.get("SCHEDULER_TENANT_ID") or "").strip()),
        }
    )
    if base.is_dir():
        for child in sorted(base.iterdir()):
            if not child.is_dir():
                continue
            db = child / "dodgeville_scheduler.db"
            out.append(
                {
                    "tenant_id": child.name,
                    "path": str(child),
                    "db_exists": db.is_file(),
                    "active": current_tenant_id() == child.name,
                }
            )
    return out


def create_tenant(tenant_id: str, *, display_name: str = "") -> Dict[str, Any]:
    tid = _slug(tenant_id)
    if tid == "default":
        return {"success": False, "message": "Use a non-default tenant id"}
    root = ensure_tenant_dirs(tid)
    if display_name:
        (root / "tenant_name.txt").write_text(display_name.strip()[:120], encoding="utf-8")
    return {
        "success": True,
        "tenant_id": tid,
        "path": str(root),
        "db_path": tenant_db_path(tid),
        "message": (
            f"Tenant '{tid}' ready. Start with SCHEDULER_TENANT_ID={tid} (and optional SCHEDULER_TENANT_NAME=...)."
        ),
    }


def get_tenant_info() -> Dict[str, Any]:
    root = tenant_data_root()
    return {
        "tenant_id": current_tenant_id(),
        "tenant_name": current_tenant_name(),
        "data_root": str(root),
        "db_path": tenant_db_path(),
        "explicit_tenant": bool((os.environ.get("SCHEDULER_TENANT_ID") or "").strip()),
        "isolation": "per_directory_sqlite",
        "tenants": list_local_tenants(),
    }
