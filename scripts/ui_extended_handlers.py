"""
Additional UI handler steps — fills gaps not covered by the base exhaustive flow.

Invoked from scripts/ui_exhaustive_test.py after core tab tests.
"""

from __future__ import annotations

import os
from unittest.mock import patch

from scripts.ui_exhaustive_test import (
    _close_toplevels,
    _entries_in,
    _invoke_button,
    _open_dialog_without_wait,
    _shell_alive,
    _walk_widgets,
)


def _login_role(app, username: str, password: str) -> None:
    from logic import authenticate_user, set_department_setting

    auth = authenticate_user(username, password)
    if not auth.get("success"):
        raise RuntimeError(auth.get("message", f"login failed for {username}"))
    user = auth["user"]
    user["must_change_password"] = 0
    app.current_user = user
    if getattr(app, "login_frame", None):
        app.login_frame.destroy()
        app.login_frame = None
    app._gantt_spec = None
    app._monthly_spec = None
    if not _shell_alive(app):
        app._build_shell()
        app._bind_keyboard_shortcuts()
        app.root.bind("<F5>", lambda e: app._refresh_current_page())
    set_department_setting("setup_complete", "1")
    app._refresh_department_branding()
    app._apply_dashboard_role_layout()
    app.show_page("dashboard")
    app.root.update_idletasks()


def _buttons_in(widget):
    import customtkinter as ctk

    return [w for w in _walk_widgets(widget) if isinstance(w, ctk.CTkButton)]


def run_extended_handlers(app, ctx, run_step, *, mutating: bool) -> None:
    """Exercise remaining UI handlers (filters, toolbar buttons, role layouts, etc.)."""
    officer_a = ctx["officer_a"]
    work_day_str = ctx["work_day_str"]
    work_day = ctx["work_day"]
    export_pdf = ctx["export_pdf"]
    off_day_str = ctx["off_day_str"]

    def _dashboard_stat_nav():
        app.show_page("dashboard")
        app._refresh_dashboard()
        for key in ("officers", "pending", "pending_swaps", "schedule_diff", "open_shifts", "manual"):
            card = app.stat_cards.get(key)
            if card:
                card.event_generate("<Button-1>")
        if _invoke_button(app.root, "View All"):
            pass
        app._build_dashboard_quick_actions()
        for btn in _buttons_in(app._dash_quick):
            cmd = btn.cget("command")
            if cmd:
                cmd()

    run_step("dashboard: stat cards + View All + quick-action clicks", _dashboard_stat_nav)

    def _shell_profile_full():
        from ui.profile_dialog import open_my_profile_dialog

        open_my_profile_dialog(app)
        app.root.update()
        tops = [w for w in app.root.winfo_children() if w.winfo_class() == "CTkToplevel"]
        if tops:
            dlg = tops[-1]
            for btn in _buttons_in(dlg):
                text = btn.cget("text")
                if text == "Update Password":
                    continue
                cmd = btn.cget("command")
                if cmd and text in (
                    "Timecard",
                    "Payroll",
                    "Time-Off",
                    "Shift Exchange",
                    "Dispatch Alerts",
                    "Duty Timeline",
                    "Blackout Dates",
                    "Current Monthly Schedule",
                ):
                    cmd()
                    app.root.update()
                    break
        _close_toplevels(app.root)

    run_step("shell: profile nav shortcut", _shell_profile_full)

    def _shell_refresh_each_page():
        refreshers = {
            "dashboard": app._refresh_dashboard,
            "base_schedule": lambda: app.refresh_monthly("base"),
            "live_schedule": lambda: app.refresh_monthly("updated"),
            "timecard": app.refresh_timecard,
            "timeline": app.refresh_gantt,
            "requests": app.refresh_requests,
            "swaps": app.refresh_swaps,
            "notifications": app.refresh_notifications,
            "officers": app.refresh_officer_list,
            "payroll": app.refresh_payroll,
            "simulator": lambda: None,
            "reports": app.refresh_reports,
            "availability": app.refresh_availability,
            "users": app.refresh_users,
        }
        for key, fn in refreshers.items():
            if key in app.pages:
                app.show_page(key)
                fn()

    run_step("shell: _refresh_page every tab", _shell_refresh_each_page)

    def _shell_all_shortcuts():
        app.show_page("dashboard")
        for i in range(10):
            app.root.event_generate(f"<Control-Key-{i}>")
            app.root.update()

    run_step("shell: Ctrl+0..9 shortcuts", _shell_all_shortcuts)

    def _requests_toolbar():
        app.show_page("requests")
        app.refresh_requests()
        if hasattr(app, "req_history_filter"):
            for val in app.req_history_filter.cget("values")[:2]:
                app.req_history_filter.set(val)
                app.refresh_requests()
        if hasattr(app, "req_date_from"):
            app.req_date_from.delete(0, "end")
            app.req_date_from.insert(0, work_day_str)
            app.req_date_to.delete(0, "end")
            app.req_date_to.insert(0, work_day_str)
            app.refresh_requests()
        if app.can("requests.approve"):
            app._bulk_approve_requests()
            app._bulk_reject_requests()
        app._export_requests_pdf()

    run_step("requests: toolbar filters + bulk + unfiltered PDF", _requests_toolbar)

    if mutating:

        def _requests_row_actions():
            from logic import create_day_off_request, get_pending_day_off_requests

            app.show_page("requests")
            app._set_request_view("queue")
            create_day_off_request(officer_a["id"], off_day_str, "Vacation", "UI row test")
            app.refresh_requests()
            pending = get_pending_day_off_requests()
            if pending:
                app.handle_request(pending[-1]["id"], "reject")

        run_step("requests: row reject via handle_request", _requests_row_actions)

    def _swaps_toolbar():
        app.show_page("swaps")
        if hasattr(app, "swap_filter"):
            for val in app.swap_filter.cget("values")[:2]:
                app.swap_filter.set(val)
                app.refresh_swaps()
        app._refresh_swap_officer_dropdowns()

    run_step("swaps: filter combo refresh", _swaps_toolbar)

    def _timeline_toolbar():
        app.show_page("timeline")
        _invoke_button(app.pages["timeline"], "Refresh")
        if hasattr(app, "_gantt_export_officer"):
            vals = app._gantt_export_officer.cget("values")
            if vals and vals[0] != "Select officer...":
                app._gantt_export_officer.set(vals[0])
        app._refresh_gantt_export_officers()

    run_step("timeline: Refresh + export officer combo", _timeline_toolbar)

    def _schedule_toolbars():
        import customtkinter as ctk

        for st in ("base", "updated"):
            key = "base_schedule" if st == "base" else "live_schedule"
            app.show_page(key)
            page = app.pages[key]
            _invoke_button(page, "Apply")
            if st == "updated":
                _invoke_button(page, "Compare to Base")
                _close_toplevels(app.root)
                with patch.object(ctk.CTkToplevel, "wait_window", lambda self: None):
                    _invoke_button(page, "Assign Coverage")
                _close_toplevels(app.root)
                with patch.object(ctk.CTkToplevel, "wait_window", lambda self: None):
                    state = app._schedule_pages.get("updated")
                    if state and state.get("selected_entry"):
                        _invoke_button(page, "Manual Edit")
                _close_toplevels(app.root)

    run_step("schedules: Apply + Compare/Coverage/Edit toolbar", _schedule_toolbars)

    def _timecard_officer_combo():
        app.show_page("timecard")
        if hasattr(app, "tc_officer_combo"):
            vals = app.tc_officer_combo.cget("values")
            if vals:
                app.tc_officer_combo.set(vals[0])
                app.refresh_timecard()
        if mutating and app._timecard_day_widgets:
            w = app._timecard_day_widgets[0]
            save_btns = [b for b in _buttons_in(app.pages["timecard"]) if b.cget("text") == "Save"]
            if save_btns and not w.get("imported"):
                save_btns[0].invoke()

    run_step("timecard: officer combo + Save Day button", _timecard_officer_combo)

    def _payroll_toolbar():
        app.show_page("payroll")
        _invoke_button(app.pages["payroll"], "Refresh Period")
        if hasattr(app, "pay_filter"):
            for val in app.pay_filter.cget("values")[:2]:
                app.pay_filter.set(val)
                app.refresh_payroll()
        app._refresh_pay_period_history()
        if _invoke_button(app.root, "Payroll"):
            app.show_page("payroll")

    run_step("payroll: filter + Refresh Period + history Payroll jump", _payroll_toolbar)

    def _payroll_flsa_position_pay():
        app.show_page("payroll")
        if hasattr(app, "refresh_flsa_settings"):
            app.refresh_flsa_settings()
        if hasattr(app, "refresh_position_pay_rates"):
            app.refresh_position_pay_rates()

    run_step("payroll: FLSA settings + position pay rates refresh", _payroll_flsa_position_pay)

    def _banked_time_scope():
        app.show_page("banked_time")
        app.refresh_banked_time()
        if hasattr(app, "bt_scope_combo"):
            for label in app.bt_scope_combo.cget("values")[:3]:
                app.bt_scope_combo.set(label)
                app._on_banked_time_scope_change(label)
        if hasattr(app, "_shift_banked_time_scope"):
            app._shift_banked_time_scope(-1)
            app._shift_banked_time_scope(1)
            app._reset_banked_time_reference()
        if hasattr(app, "bt_officer_combo") and app.bt_officer_combo:
            vals = app.bt_officer_combo.cget("values")
            if len(vals) > 1:
                app.bt_officer_combo.set(vals[1])
                app.refresh_banked_time()

    run_step("banked_time: scope nav + officer filter + FLSA card", _banked_time_scope)

    def _reports_filters_budget():
        app.show_page("reports")
        if hasattr(app, "_reports_month_year"):
            vals = app._reports_month_year.cget("values")
            if vals:
                app._reports_month_year.set(vals[0])
                app.refresh_reports()
        if hasattr(app, "_reports_audit_filter"):
            vals = app._reports_audit_filter.cget("values")
            if len(vals) > 1:
                app._reports_audit_filter.set(vals[1])
                app.refresh_reports()
        if mutating and hasattr(app, "_budget_entry"):
            app._budget_entry.delete(0, "end")
            app._budget_entry.insert(0, "500000")
            _invoke_button(app.root, "Save Budget")

    run_step("reports: month/audit filter + budget save", _reports_filters_budget)

    def _notifications_filters():
        app.show_page("dashboard")
        app._refresh_notification_officer_filter()
        if hasattr(app, "notif_read_filter"):
            app.notif_read_filter.set("Unread")
        if hasattr(app, "notif_type_filter"):
            vals = app.notif_type_filter.cget("values")
            if vals:
                app.notif_type_filter.set(vals[0])
        if hasattr(app, "notif_officer_filter"):
            vals = app.notif_officer_filter.cget("values")
            if vals:
                app.notif_officer_filter.set(vals[0])
        app.refresh_notifications()

    run_step("notifications: read/type/officer filters", _notifications_filters)

    if mutating and app.can("users.manage"):
        from logic import list_all_users

        def _users_simple_edit():
            app.show_page("users")
            target = next((u for u in list_all_users() if u["username"] == "officer"), None)
            if target:
                dlg = _open_dialog_without_wait(
                    app,
                    lambda: app._edit_app_user(target, full_edit=False),
                )
                if dlg:
                    _invoke_button(dlg, "Save Changes")
                _close_toplevels(app.root)

        run_step("users: simple role edit (officer account)", _users_simple_edit)

    def _simulator_slider():
        app.show_page("simulator")
        if hasattr(app, "sim_officers"):
            app.sim_officers.set(12)
            cmd = app.sim_officers.cget("command")
            if cmd:
                cmd(12)

    run_step("simulator: officer count slider", _simulator_slider)

    def _officers_roster_row_click():
        app.show_page("officers")
        app.refresh_officer_list()
        rows = _buttons_in(app.officer_list)
        if rows:
            rows[0].invoke()
        for combo_name in ("off_job_title", "off_squad", "off_shift"):
            combo = getattr(app, combo_name, None)
            if combo is None:
                continue
            vals = combo.cget("values")
            if len(vals) > 1:
                combo.set(vals[1])
                if combo_name == "off_job_title" and hasattr(app, "_on_job_title_selected"):
                    app._on_job_title_selected(vals[1])
                elif combo_name == "off_squad" and hasattr(app, "_on_squad_selected"):
                    app._on_squad_selected(vals[1])
                elif combo_name == "off_shift" and hasattr(app, "_on_shift_selected"):
                    app._on_shift_selected(vals[1])
        if hasattr(app, "_refresh_pay_rate_hint"):
            app._refresh_pay_rate_hint()

    run_step("officers: roster row + assignment combos", _officers_roster_row_click)

    if mutating:

        def _availability_focus():
            from logic import get_officer_availability

            app.show_page("availability")
            entries = get_officer_availability()
            if entries:
                app._focus_availability_row(entries[0]["id"])

        run_step("availability: focus row highlight", _availability_focus)


def run_role_sessions(app, ctx, run_step, *, mutating: bool) -> None:
    """Login as supervisor and officer to exercise role-scoped handlers."""
    roles = [
        ("supervisor", "supervisor", "supervisor: dashboard + requests export"),
        ("officer", "officer", "officer: scoped dashboard + timecard"),
    ]
    for username, password, label in roles:

        def _role_fn(u=username, p=password):
            app.sign_out()
            app.root.update()
            _login_role(app, u, p)
            app._refresh_dashboard()
            app._build_dashboard_quick_actions()
            app.show_page("requests")
            app.refresh_requests()
            if app._is_officer_role():
                app._export_requests_csv_filtered()
                app._export_requests_pdf_filtered()
            app.show_page("timecard")
            app.refresh_timecard()
            if not app._is_officer_role():
                app.show_page("timeline")
                app.refresh_gantt()
            app.show_page("requests")
            app.refresh_requests()

        run_step(label, _role_fn)

    app.sign_out()
    app.root.update()
    _login_role(app, "admin", "admin")
