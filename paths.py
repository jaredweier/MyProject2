"""Application paths — works in development and PyInstaller bundles."""

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
        candidates.append(os.path.join(getattr(sys, "_MEIPASS", app_dir()), relative))
    candidates.append(os.path.join(app_dir(), relative))
    candidates.append(os.path.join(os.getcwd(), relative))
    for path in candidates:
        if os.path.isfile(path):
            return path
    return candidates[0] if candidates else os.path.join(app_dir(), relative)


def data_path(relative: str) -> str:
    """Writable path next to the executable / project root."""
    return os.path.join(app_dir(), relative)


def ensure_data_dirs():
    for folder in ("photos", "logs", "backups", "exports"):
        path = data_path(folder)
        if not os.path.exists(path):
            os.makedirs(path)
