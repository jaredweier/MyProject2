"""Probe Duty Console (NiceGUI) stack + assets + auth (subprocess readiness gate)."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> int:
    os.environ.setdefault("SCHEDULER_UI_TEST", "1")
    errors: list[str] = []

    # --- Brand APIs (optional uploads — must not require shipped logo/team) ---
    try:
        from photos import chronos_logo_path, department_logo_path, department_photo_path

        # Paths may be None when no agency has uploaded branding (expected)
        _ = chronos_logo_path()
        _ = department_logo_path()
        _ = department_photo_path()
        from gui.brand_assets import sync_brand_files

        sync_brand_files()
    except Exception as exc:
        errors.append(f"brand_apis: {exc}")

    # --- NiceGUI stack import ---
    try:
        import nicegui  # noqa: F401

        from gui import session, shell, theme
        from gui.app import run as _run  # noqa: F401
        from gui.pages import access, dashboard, finance, leave, login, operations, roster, schedules, simulator

        for mod in (
            login,
            dashboard,
            schedules,
            leave,
            roster,
            finance,
            simulator,
            operations,
            access,
            session,
            shell,
            theme,
        ):
            if mod is None:
                errors.append("module missing")
        # CSS / nav present
        if "dc-shell" not in theme.GLOBAL_CSS and "soc-shell" not in theme.GLOBAL_CSS:
            errors.append("theme missing shell layout class")
        if "cmd-strip" not in theme.GLOBAL_CSS and "kpi-row" not in theme.GLOBAL_CSS:
            errors.append("theme missing mockup classes")
        if not shell.NAV:
            errors.append("shell NAV empty")
    except Exception as exc:
        errors.append(f"gui import: {exc}")

    # --- Auth + permissions path ---
    try:
        from database import init_database
        from logic import authenticate_user
        from permissions import role_has_permission

        init_database()
        auth = authenticate_user("admin", "admin")
        if not auth.get("success"):
            errors.append(f"admin login failed: {auth.get('message')}")
        else:
            user = auth["user"]
            if not role_has_permission(user.get("role") or "", "officers.manage"):
                errors.append("admin missing officers.manage")
        # Officer demo
        auth_o = authenticate_user("officer", "officer")
        if not auth_o.get("success"):
            # non-fatal if demo password rotated
            pass
    except Exception as exc:
        errors.append(f"auth: {exc}")

    # --- Core schedule API (live view dependency) ---
    try:
        from datetime import date

        from logic import build_schedule_matrix, get_current_cycle_window

        start, end = get_current_cycle_window()
        matrix, days = build_schedule_matrix(start, end)
        if not isinstance(matrix, list) or not days:
            errors.append("schedule matrix empty or invalid")
        _ = date.today()
    except Exception as exc:
        errors.append(f"schedule: {exc}")

    if errors:
        for err in errors:
            print(f"FAIL: {err}", file=sys.stderr)
        print(f"ui_login_probe: {len(errors)} error(s)", file=sys.stderr)
        return 1

    print("OK: Duty Console probe passed (NiceGUI + auth + schedule)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
