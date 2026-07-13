"""Headless smoke for Duty Console — imports pages + exercises logic paths (no browser).

Full interactive UI is validated by running: python main.py --browser
"""

from __future__ import annotations

import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("SCHEDULER_UI_TEST", "1")
os.environ.setdefault("SCHEDULER_SKIP_STARTUP_GATES", "1")


def run_ui_smoke() -> int:
    print("Duty Console — ui-smoke (NiceGUI stack)")
    print("=" * 60)
    errors: list[str] = []

    try:
        from database import init_database
        from logic import authenticate_user, build_schedule_matrix, get_current_cycle_window, get_dashboard_insights

        init_database()
        auth = authenticate_user("admin", "admin")
        if not auth.get("success"):
            errors.append("admin auth failed")
        else:
            print("  auth admin: OK")

        insights = get_dashboard_insights()
        print(f"  dashboard insights: {type(insights).__name__}")

        start, end = get_current_cycle_window()
        matrix, days = build_schedule_matrix(start, end)
        print(f"  schedule matrix: {len(matrix)} officers × {len(days)} days")

        # Import every page module + shell
        from gui.pages import (
            access,
            dashboard,
            finance,
            leave,
            login,
            media,
            operations,
            roster,
            schedules,
            security,
            simulator,
        )
        from gui.shell import NAV, ROUTE_PERMS, apply_theme, layout, page_header
        from gui.theme import GLOBAL_CSS

        assert "LIVE" in GLOBAL_CSS or "live-badge" in GLOBAL_CSS or "live-pip" in GLOBAL_CSS
        assert "dc-shell" in GLOBAL_CSS or "kpi-row" in GLOBAL_CSS
        assert any(x[0] == "/" or (isinstance(x, tuple) and len(x) >= 2) for x in NAV)
        labels = [x[1] for x in NAV if x[0] != "section"]
        for expected in (
            "My Schedule",
            "Monthly Schedule",
            "Live Schedule",
            "Time Off Requests",
            "Timecards",
            "Payroll",
            "Schedule Simulator",
            "Security & Governance",
            "Department Media",
        ):
            if expected not in labels:
                errors.append(f"nav missing: {expected}")
        print(f"  nav entries: {len(NAV)}")
        print(f"  route perms: {len(ROUTE_PERMS)}")
        print(f"  nav labels: {labels}")

        for name, fn in (
            ("login", login.render_login),
            ("dashboard", dashboard.render_dashboard),
            ("my_schedule", schedules.render_my_schedule),
            ("monthly", schedules.render_monthly_schedule),
            ("live", schedules.render_live_schedule),
            ("leave", leave.render_leave),
            ("roster", roster.render_roster),
            ("timecards", finance.render_timecards),
            ("payroll", finance.render_payroll),
            ("simulator", simulator.render_simulator),
            ("operations", operations.render_operations),
            ("security", security.render_security),
            ("media", media.render_media),
            ("access", access.render_access),
        ):
            if not callable(fn):
                errors.append(f"{name} not callable")
            else:
                print(f"  render {name}: OK")

        _ = apply_theme, layout, page_header  # keep imports live

    except Exception:
        errors.append(traceback.format_exc())

    print("=" * 60)
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        print("ui-smoke: FAILED")
        return 1
    print("ui-smoke: ALL PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_ui_smoke())
