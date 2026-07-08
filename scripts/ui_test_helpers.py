"""Shared headless UI test bootstrap — mirrors real login, catches Tk callback errors."""

from __future__ import annotations

import os
import sys
import time
import traceback
from typing import Callable

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Must be set before ui.app / session_pages import during test runs.
os.environ.setdefault("SCHEDULER_UI_TEST", "1")


def enable_ui_test_mode() -> None:
    os.environ["SCHEDULER_UI_TEST"] = "1"


def install_callback_error_collector(root) -> list[str]:
    errors: list[str] = []

    def _report(exc, val, tb):
        errors.append("".join(traceback.format_exception(exc, val, tb)))

    try:
        root.report_callback_exception = _report
    except Exception:
        pass
    return errors


def pump_tk(root, *, seconds: float = 0.25) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            root.update()
        except Exception:
            break
        time.sleep(0.01)


def destroy_app(root) -> None:
    """Tear down Tk safely; pending after() callbacks can hang plain destroy() on Windows."""
    for w in list(root.winfo_children()):
        if w.winfo_class() == "CTkToplevel":
            try:
                w.destroy()
            except Exception:
                pass
    from ui.helpers import destroy_tk_root

    destroy_tk_root(root)


def shell_ready(app) -> bool:
    try:
        if getattr(app, "shell", None) is None or not app.shell.winfo_exists():
            return False
    except Exception:
        return False
    return len(getattr(app, "nav_buttons", {})) > 0 and len(getattr(app, "pages", {})) > 0


def wait_for(
    root,
    predicate: Callable[[], bool],
    *,
    timeout_s: float = 20.0,
    label: str = "condition",
) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        root.update()
        if predicate():
            return
        time.sleep(0.01)
    raise TimeoutError(f"Timed out waiting for {label}")


def headless_login(app, user: dict) -> None:
    """Use the same teardown path as interactive login (no login Configure handler storm)."""
    from ui.display import clear_login_window_layout
    from ui.window_layout import reset_main_window_layout_guard

    user = dict(user)
    user["must_change_password"] = 0

    if getattr(app, "shell", None):
        app._teardown_shell_state()
        reset_main_window_layout_guard(app.root)

    clear_login_window_layout(app.root)
    app.current_user = user
    if getattr(app, "login_frame", None):
        try:
            app.login_frame.destroy()
        except Exception:
            pass
        app.login_frame = None

    app._finish_login_shell()
    app.root.update_idletasks()
    app.root.update()
    wait_for(app.root, lambda: shell_ready(app), timeout_s=45.0, label="shell ready")
    wait_for(
        app.root,
        lambda: getattr(app, "current_page", None) == "dashboard",
        timeout_s=15.0,
        label="initial dashboard",
    )
    pump_tk(app.root, seconds=0.5)
    clear_login_window_layout(app.root)


def create_headless_app():
    """Create app with UI test mode (no login window / centering handlers)."""
    enable_ui_test_mode()
    from database import init_database
    from ui.app import DodgevilleSchedulerApp
    from ui.assets import reset_brand_image_cache

    init_database()
    reset_brand_image_cache()
    app = DodgevilleSchedulerApp()
    app.root.withdraw()
    callback_errors = install_callback_error_collector(app.root)
    return app, callback_errors


def assert_brand_assets(errors: list[str]) -> None:
    from paths import resource_path

    for filename in ("logo.png", "team_photo.jpg"):
        path = resource_path(filename)
        if not os.path.isfile(path):
            errors.append(f"brand asset missing on disk: {filename} ({path})")


def assert_login_handlers_cleared(root, errors: list[str]) -> None:
    if getattr(root, "_login_centering_active", False):
        errors.append("login centering still active after headless login")
    if getattr(root, "_login_configure_bind_id", None) is not None:
        errors.append("login <Configure> handler still bound after headless login")


def assert_nav_contains(app, key: str, errors: list[str], *, role: str) -> None:
    if key not in app.nav_buttons:
        errors.append(f"{role}: nav missing {key!r} (have {sorted(app.nav_buttons)})")


def assert_nav_excludes(app, key: str, errors: list[str], *, role: str) -> None:
    if key in app.nav_buttons:
        errors.append(f"{role}: nav should not include {key!r}")


def visit_all_pages(app, errors: list[str]) -> int:
    from ui.theme import NAV_ITEMS

    visited = 0
    for key, _, _ in NAV_ITEMS:
        if key not in app.pages:
            errors.append(f"page frame missing: {key}")
            continue
        try:
            app.show_page(key)
            app.root.update_idletasks()
            app.root.update()
            visited += 1
        except Exception:
            errors.append(f"show_page({key}):\n{traceback.format_exc()}")
    return visited


def authenticate_role(username: str, password: str) -> dict | None:
    from logic import authenticate_user

    auth = authenticate_user(username, password)
    if not auth.get("success"):
        return None
    user = auth["user"]
    user["must_change_password"] = 0
    return user
