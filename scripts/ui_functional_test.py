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

os.environ["SCHEDULER_UI_TEST"] = "1"


def _step(name: str, fn, results: list) -> None:
    try:
        fn()
        results.append((name, True, ""))
    except Exception:
        results.append((name, False, traceback.format_exc()))


def _login_admin(app):
    from scripts.ui_test_helpers import authenticate_role, headless_login

    user = authenticate_role("admin", "admin")
    if not user:
        raise RuntimeError("admin login failed")
    headless_login(app, user)
    app._refresh_department_branding()
    app._apply_dashboard_role_layout()
    app.root.update_idletasks()


def run_ui_functional() -> int:
    """Fast UI smoke — delegates to exhaustive suite."""
    from scripts.ui_exhaustive_test import run_ui_exhaustive

    return run_ui_exhaustive()


if __name__ == "__main__":
    raise SystemExit(run_ui_functional())
