"""Application paths — works in development and PyInstaller bundles.

Multi-tenant: when SCHEDULER_TENANT_ID is set, writable data lives under
``tenants/<id>/`` so each agency subscription has isolated DB + media.
"""

import os
import sys


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def app_dir() -> str:
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(relative: str) -> str:
    """Resolve bundled assets (logo, team photo) in dev and frozen builds."""
    candidates = []
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            candidates.append(os.path.join(meipass, relative))
        candidates.append(os.path.join(app_dir(), "_internal", relative))
    candidates.append(os.path.join(app_dir(), relative))
    candidates.append(os.path.join(os.getcwd(), relative))
    candidates.append(os.path.join(os.getcwd(), "_internal", relative))
    for path in candidates:
        if os.path.isfile(path):
            return path
    return candidates[0] if candidates else os.path.join(app_dir(), relative)


def _tenant_root() -> str | None:
    """Return tenants/<id> when SCHEDULER_TENANT_ID is set; else None (legacy root)."""
    tid = (os.environ.get("SCHEDULER_TENANT_ID") or "").strip()
    if not tid:
        return None
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in tid).strip("-")[:64]
    if not safe:
        return None
    return os.path.join(app_dir(), "tenants", safe)


def data_path(relative: str) -> str:
    """Writable path: project root, or tenants/<id>/ when multi-tenant online."""
    root = _tenant_root() or app_dir()
    return os.path.join(root, relative)


def ensure_data_dirs():
    root = _tenant_root()
    if root and not os.path.exists(root):
        os.makedirs(root, exist_ok=True)
    for folder in ("photos", "logs", "backups", "exports"):
        path = data_path(folder)
        if not os.path.exists(path):
            os.makedirs(path)
