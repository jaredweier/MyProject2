"""Exercise UI handlers against an isolated test database (headless CTk)."""

from __future__ import annotations

import os
import sys
import tempfile
import traceback
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _step(name: str, fn, results: list) -> None:
    try:
        fn()
        results.append((name, True, ""))
    except Exception:
        results.append((name, False, traceback.format_exc()))


def _login_admin(app):
    from logic import authenticate_user

    auth = authenticate_user("admin", "admin")
    if not auth.get("success"):
        raise RuntimeError(auth.get("message", "admin login failed"))
    user = auth["user"]
    user["must_change_password"] = 0
    app.current_user = user
    if hasattr(app, "login_frame"):
        app.login_frame.destroy()
    app._build_shell()
    app._refresh_department_branding()
    app._apply_dashboard_role_layout()
    app.root.update_idletasks()


def run_ui_functional() -> int:
    """Fast UI smoke — delegates to exhaustive suite."""
    from scripts.ui_exhaustive_test import run_ui_exhaustive

    return run_ui_exhaustive()


if __name__ == "__main__":
    raise SystemExit(run_ui_functional())
