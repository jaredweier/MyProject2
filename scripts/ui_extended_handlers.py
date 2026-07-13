"""
Additional UI handler steps for modular shell (post-rebuild).

Invoked from scripts/ui_exhaustive_test.py after core page walks.
"""

from __future__ import annotations

from scripts.ui_test_helpers import refresh_tk, shell_ready


def run_extended_handlers(app, ctx, run_step, *, mutating: bool) -> None:
    """Exercise page controllers + sidebar chrome without legacy monolith APIs."""

    def _sidebar_refresh_button():
        app.show_page("dashboard")
        # Secondary "Refresh all" is wired to app.refresh_all
        app.refresh_all()
        refresh_tk(app.root)

    run_step("extended: refresh_all from shell", _sidebar_refresh_button)

    def _subnav_hubs():
        # Hubs that expose subnav: finance (timecard/payroll), schedules
        for key in ("timecard", "payroll", "banked_time", "base_schedule", "live_schedule", "timeline"):
            if key in app.pages:
                app.show_page(key)
                refresh_tk(app.root)

    run_step("extended: finance + schedule hub pages", _subnav_hubs)

    def _status_and_toast():
        app.set_status("exhaustive status check", toast=False)
        if hasattr(app, "show_toast"):
            app.show_toast("exhaustive toast", level="info", ms=100)

    run_step("extended: status + toast", _status_and_toast)

    def _notification_badge():
        if hasattr(app, "_update_notification_badge"):
            app._update_notification_badge()
        if hasattr(app, "_update_user_badge"):
            app._update_user_badge()
        if hasattr(app, "_update_sidebar_date"):
            app._update_sidebar_date()

    run_step("extended: badges + sidebar date", _notification_badge)

    if mutating and ctx.get("officer_a"):

        def _roster_refresh():
            app.show_page("officers")
            ctrl = app.page_controllers.get("officers")
            if ctrl:
                ctrl.ensure_built()
                ctrl.refresh()

        run_step("extended: roster page refresh", _roster_refresh)

        def _simulator_refresh():
            if "simulator" in app.pages:
                app.show_page("simulator")
                ctrl = app.page_controllers.get("simulator")
                if ctrl:
                    ctrl.ensure_built()
                    ctrl.refresh()

        run_step("extended: simulator page refresh", _simulator_refresh)


def run_role_sessions(app, ctx, run_step, *, mutating: bool) -> None:
    """Light role re-check — full role walks live in ui_exhaustive_test."""

    def _assert_shell():
        if not shell_ready(app):
            raise RuntimeError("shell not ready at role-session checkpoint")
        if not app.current_user:
            raise RuntimeError("no current_user at role-session checkpoint")

    run_step("role-session: shell still ready", _assert_shell)
