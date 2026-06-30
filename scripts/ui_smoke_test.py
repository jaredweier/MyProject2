"""Headless UI smoke — build shell, visit every page, catch runtime errors."""

from __future__ import annotations

import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def run_ui_smoke() -> int:
    import customtkinter as ctk

    from logic import authenticate_user, list_all_users
    from ui.app import DodgevilleSchedulerApp
    from ui.theme import NAV_ITEMS

    errors: list[str] = []

    app = DodgevilleSchedulerApp()
    app.root.withdraw()

    # Prefer admin without forced password change for automation
    user = None
    for u in list_all_users():
        if u.get("role") == "Administration" and u.get("active") == 1:
            if not u.get("must_change_password"):
                auth = authenticate_user(u["username"], "admin")
                if auth.get("success"):
                    user = auth["user"]
                    break
    if not user:
        auth = authenticate_user("admin", "admin")
        if auth.get("success"):
            user = auth["user"]
            user["must_change_password"] = 0

    if not user:
        print("ui smoke: FAIL — no login user")
        app.root.destroy()
        return 1

    try:
        app.current_user = user
        if hasattr(app, "login_frame"):
            app.login_frame.destroy()
        app._build_shell()
        app._apply_dashboard_role_layout()
    except Exception:
        errors.append(f"build_shell:\n{traceback.format_exc()}")

    pages = [key for key, _, _ in NAV_ITEMS if key in app.pages]
    for key in pages:
        try:
            app.show_page(key)
            app.root.update_idletasks()
        except Exception:
            errors.append(f"show_page({key}):\n{traceback.format_exc()}")

    # Brand assets
    from ui.assets import load_brand_image

    for name, size, cover in (
        ("logo.png", (72, 72), False),
        ("team_photo.jpg", (320, 148), True),
    ):
        img = load_brand_image(name, size, cover=cover)
        if img is None:
            errors.append(f"load_brand_image({name}) returned None")

    # Department branding helpers
    try:
        from ui.branding import get_department_branding

        branding = get_department_branding()
        if not branding.get("name"):
            errors.append("department name empty")
    except Exception:
        errors.append(f"branding:\n{traceback.format_exc()}")

    app.root.destroy()

    print("Dodgeville PD Scheduler — UI smoke")
    print("-" * 40)
    if errors:
        for err in errors:
            print(f"  [FAIL] {err}")
        print("-" * 40)
        print(f"ui smoke: {len(errors)} FAILURE(S)")
        return 1

    print(f"  [ok] built shell for {user['username']} ({user['role']})")
    print(f"  [ok] visited {len(pages)} pages")
    print("  [ok] brand images loaded")
    print("-" * 40)
    print("ui smoke: ALL PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_ui_smoke())
