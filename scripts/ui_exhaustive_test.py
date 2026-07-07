"""
Headless exhaustive UI test — every tab and major handler.

Run: python dev.py ui-exhaustive
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
import traceback
import uuid
from contextlib import nullcontext
from datetime import datetime, timezone
from unittest.mock import patch


def _safe_filename(name: str) -> str:
    return re.sub(r"[^\w\-.]+", "_", name).strip("_")[:120] or "step"


def _screenshot_window(root, path: str) -> None:
    from PIL import ImageGrab

    root.update_idletasks()
    root.update()
    x = root.winfo_rootx()
    y = root.winfo_rooty()
    w = max(root.winfo_width(), 1)
    h = max(root.winfo_height(), 1)
    ImageGrab.grab((x, y, x + w, y + h)).save(path)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _step(
    name: str,
    fn,
    results: list,
    *,
    app=None,
    step_delay: float = 0,
    screenshot_dir: str | None = None,
) -> None:
    try:
        fn()
        results.append((name, True, ""))
        if app is not None and step_delay > 0:
            app.root.update()
            time.sleep(step_delay)
        if app is not None and screenshot_dir:
            path = os.path.join(screenshot_dir, f"{len(results):02d}_{_safe_filename(name)}.png")
            _screenshot_window(app.root, path)
        if screenshot_dir or step_delay > 0:
            print(f"  [ok] {name}", flush=True)
    except Exception:
        results.append((name, False, traceback.format_exc()))
        print(f"  [FAIL] {name}", flush=True)


def _close_toplevels(root) -> None:
    for w in list(root.winfo_children()):
        if w.winfo_class() == "CTkToplevel":
            try:
                w.destroy()
            except Exception:
                pass


def _destroy_app(root) -> None:
    """Tear down Tk safely; pending after() callbacks can hang plain destroy() on Windows."""
    _close_toplevels(root)
    try:
        pending = root.tk.call("after", "info")
        if pending:
            for after_id in pending:
                try:
                    root.after_cancel(after_id)
                except Exception:
                    pass
    except Exception:
        pass
    try:
        root.update()
        root.quit()
    except Exception:
        pass
    try:
        root.destroy()
    except Exception:
        pass


def _write_ui_report(
    results: list[tuple[str, bool, str]],
    *,
    visible: bool,
    mutating: bool,
    isolated: bool,
    screenshot_dir: str | None,
) -> str | None:
    if not screenshot_dir:
        return None
    failures = [r for r in results if not r[1]]
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "live" if visible else "headless",
        "mutating": mutating,
        "isolated": isolated,
        "passed": len(results) - len(failures),
        "failed": len(failures),
        "total": len(results),
        "screenshot_dir": screenshot_dir,
        "steps": [
            {
                "index": i,
                "name": name,
                "ok": ok,
                "screenshot": os.path.join(
                    screenshot_dir,
                    f"{i:02d}_{_safe_filename(name)}.png",
                )
                if ok
                else None,
                "error": detail.strip() if detail else None,
            }
            for i, (name, ok, detail) in enumerate(results, start=1)
        ],
    }
    report_path = os.path.join(screenshot_dir, "report.json")
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    return report_path


def _confirm_yesno(title="", message="", **kwargs) -> bool:
    combined = f"{title} {message}".lower()
    if any(word in combined for word in ("confirm", "delete", "deactivate", "reactivate", "permanently")):
        return True
    return False


def _walk_widgets(widget):
    yield widget
    try:
        children = widget.winfo_children()
    except Exception:
        return
    for child in children:
        try:
            yield from _walk_widgets(child)
        except Exception:
            continue


def _invoke_button(root, text: str) -> bool:
    import customtkinter as ctk

    for widget in _walk_widgets(root):
        if isinstance(widget, ctk.CTkButton) and widget.cget("text") == text:
            cmd = widget.cget("command")
            if cmd:
                cmd()
                return True
    return False


def _open_dialog_without_wait(app, opener) -> object | None:
    import customtkinter as ctk

    with patch.object(ctk.CTkToplevel, "wait_window", lambda self: None):
        opener()
    app.root.update()
    tops = [w for w in app.root.winfo_children() if w.winfo_class() == "CTkToplevel"]
    return tops[-1] if tops else None


def _entries_in(widget):
    import customtkinter as ctk

    return [w for w in _walk_widgets(widget) if isinstance(w, ctk.CTkEntry)]


def _shell_alive(app) -> bool:
    try:
        return getattr(app, "shell", None) is not None and app.shell.winfo_exists()
    except Exception:
        return False


def _login_admin(app) -> None:
    from logic import authenticate_user

    auth = authenticate_user("admin", "admin")
    if not auth.get("success"):
        raise RuntimeError(auth.get("message", "admin login failed"))
    user = auth["user"]
    user["must_change_password"] = 0
    app.current_user = user
    if getattr(app, "login_frame", None):
        app.login_frame.destroy()
        app.login_frame = None
    if not _shell_alive(app):
        app._build_shell()
        app._bind_keyboard_shortcuts()
        app.root.bind("<F5>", lambda e: app._refresh_current_page())
        app.show_page("dashboard")
    from logic import set_department_setting

    set_department_setting("setup_complete", "1")
    app._refresh_department_branding()
    app._apply_dashboard_role_layout()
    app.root.update_idletasks()


def run_ui_exhaustive(
    *,
    visible: bool = False,
    step_delay: float = 0,
    screenshot_dir: str | None = None,
    isolated: bool = True,
    auto_login: bool = False,
    mutating: bool = True,
    hold_seconds: float = 0,
) -> int:
    from logic import (
        get_holidays,
        get_monthly_summary_from_snapshot,
        get_notifications,
        get_officer_availability,
        get_open_shifts,
        get_pending_day_off_requests,
        get_pending_shift_swap_requests,
        list_all_users,
    )
    from tests.helpers import get_any_officer, off_date_for_squad, test_database, working_date_for_squad

    results: list[tuple[str, bool, str]] = []
    tmp = tempfile.gettempdir()
    export_csv = os.path.join(tmp, "ui_exhaustive.csv")
    export_pdf = os.path.join(tmp, "ui_exhaustive.pdf")

    def _run_step(name: str, fn) -> None:
        _step(
            name,
            fn,
            results,
            app=app,
            step_delay=step_delay if visible else 0,
            screenshot_dir=screenshot_dir if visible else None,
        )

    db_ctx = test_database() if isolated else nullcontext()

    with db_ctx:
        login_patch = patch("ui.session_pages.AUTO_LOGIN_ENABLED", auto_login)
        with login_patch:
            from ui.app import DodgevilleSchedulerApp
            from ui.theme import NAV_ITEMS
            from ui.window_layout import apply_main_window_layout

            if visible:
                print("  Starting visible UI session…", flush=True)
            app = DodgevilleSchedulerApp()
            if visible:
                print("  App window created.", flush=True)
            if visible:
                app.root.deiconify()
                app.root.lift()
                app.root.attributes("-topmost", True)
                app.root.after(300, lambda: app.root.attributes("-topmost", False))
                app.root.focus_force()
                apply_main_window_layout(app.root)
            else:
                app.root.withdraw()

            patches = [
                patch("tkinter.messagebox.showinfo"),
                patch("tkinter.messagebox.showwarning"),
                patch("tkinter.messagebox.showerror"),
                patch("tkinter.messagebox.askyesno", side_effect=_confirm_yesno),
                patch("tkinter.filedialog.asksaveasfilename", return_value=export_csv),
                patch("tkinter.filedialog.askopenfilename", return_value=""),
            ]
            for p in patches:
                p.start()
            try:
                if not auto_login:
                    _run_step("shell: admin login", lambda: _login_admin(app))
                else:
                    from logic import set_department_setting

                    if app.current_user:
                        app.current_user["must_change_password"] = 0
                    set_department_setting("setup_complete", "1")

                for key, _, _ in NAV_ITEMS:
                    if key in app.pages:
                        _run_step(f"nav: show_page({key})", lambda k=key: app.show_page(k))

                _run_step("shell: refresh_all", app.refresh_all)
                _run_step("shell: _refresh_current_page (F5)", app._refresh_current_page)
                _run_step("shell: profile dialog", lambda: _show_profile(app))

                officer_a = get_any_officer("A", "06:00")
                officer_a2 = get_any_officer("A", "10:00")
                work_day = working_date_for_squad("A")
                work_day_str = work_day.strftime("%Y-%m-%d")
                off_day_str = off_date_for_squad("A").strftime("%Y-%m-%d")
                logo_path = os.path.join(ROOT, "logo.png")
                test_officer_id: int | None = None
                created_username: str | None = None

                def _dashboard_refresh():
                    app.show_page("dashboard")
                    app._refresh_dashboard()
                    app._refresh_dashboard_data()

                _run_step("dashboard: refresh data", _dashboard_refresh)

                def _dashboard_quick_actions():
                    app.show_page("dashboard")
                    app._build_dashboard_quick_actions()

                _run_step("dashboard: quick actions", _dashboard_quick_actions)

                if mutating and app.can("requests.approve"):

                    def _dashboard_bulk():
                        app.show_page("dashboard")
                        app._bulk_approve_requests()
                        app._bulk_reject_requests()

                    _run_step("dashboard: bulk approve/reject", _dashboard_bulk)

                def _officers_search_picker():
                    app.show_page("officers")
                    app.officer_search.delete(0, "end")
                    app.officer_search.insert(0, "Squad A")
                    app.refresh_officer_list()
                    app.off_show_inactive.select()
                    app.refresh_officer_list()
                    if app.off_picker.cget("values") and app.off_picker.cget("values")[0] != "—":
                        app.off_picker.set(app.off_picker.cget("values")[0])
                        app._on_officer_picker(app.off_picker.get())

                _run_step("officers: search + picker + inactive", _officers_search_picker)

                def _officers_save_existing():
                    app.show_page("officers")
                    app.refresh_officer_list()
                    app.load_officer(officer_a["id"])
                    original = app.off_name.get()
                    app.off_name.delete(0, "end")
                    app.off_name.insert(0, original)
                    app.save_officer()

                if mutating:
                    _run_step("officers: save existing", _officers_save_existing)

                    def _officers_create():
                        nonlocal test_officer_id
                        app.show_page("officers")
                        app.new_officer_form()
                        unique = f"UI Test {uuid.uuid4().hex[:6]}"
                        app.off_name.insert(0, unique)
                        app.off_seniority.delete(0, "end")
                        app.off_seniority.insert(0, "99")
                        app.save_officer()
                        test_officer_id = app.selected_officer_id

                    _run_step("officers: create new", _officers_create)

                    def _officers_bulk_pay():
                        app.show_page("officers")
                        dlg = _open_dialog_without_wait(app, app.bulk_pay_rate_dialog)
                        if dlg:
                            entries = _entries_in(dlg)
                            if entries:
                                entries[0].insert(0, "0")
                                if len(entries) > 1:
                                    entries[1].insert(0, "0")
                            _invoke_button(dlg, "Apply to Roster")
                        _close_toplevels(app.root)

                    _run_step("officers: bulk pay rate", _officers_bulk_pay)

                    def _officers_photo():
                        app.show_page("officers")
                        target_id = test_officer_id or officer_a["id"]
                        app.load_officer(target_id)
                        with patch("tkinter.filedialog.askopenfilename", return_value=logo_path):
                            app.upload_officer_photo()
                        app.remove_officer_photo()

                    _run_step("officers: upload/remove photo", _officers_photo)

                    def _officers_deactivate():
                        if test_officer_id:
                            app.show_page("officers")
                            app.load_officer(test_officer_id)
                            app.deactivate_officer()

                    _run_step("officers: deactivate test officer", _officers_deactivate)

                    def _officers_delete():
                        app.show_page("officers")
                        app.new_officer_form()
                        unique = f"UI Del {uuid.uuid4().hex[:6]}"
                        app.off_name.insert(0, unique)
                        app.off_seniority.delete(0, "end")
                        app.off_seniority.insert(0, "98")
                        app.save_officer()
                        del_id = app.selected_officer_id
                        if del_id:
                            app.load_officer(del_id)
                            app.delete_officer_profile()

                    _run_step("officers: delete new officer", _officers_delete)

                    def _officers_import():
                        app.show_page("officers")
                        app.import_roster_csv()

                    _run_step("officers: import roster csv", _officers_import)
                else:

                    def _officers_readonly():
                        app.show_page("officers")
                        app.refresh_officer_list()
                        app.load_officer(officer_a["id"])

                    _run_step("officers: view roster", _officers_readonly)

                def _requests_views():
                    app.show_page("requests")
                    for view in ("queue", "history", "review"):
                        if view == "review" and not app.can("requests.approve"):
                            continue
                        app._set_request_view(view)

                _run_step("requests: view switches", _requests_views)

                def _requests_preview():
                    app.show_page("requests")
                    app.req_officer.set(officer_a["name"])
                    app.req_date.delete(0, "end")
                    app.req_date.insert(0, work_day_str)
                    app.preview_request_coverage()

                _run_step("requests: coverage preview", _requests_preview)

                if mutating:

                    def _requests_submit_approve():
                        app.show_page("requests")
                        app.req_officer.set(officer_a["name"])
                        app.req_date.delete(0, "end")
                        app.req_date.insert(0, off_day_str)
                        app.submit_request()
                        app.refresh_requests()
                        pending = get_pending_day_off_requests()
                        if pending:
                            req = pending[0]
                            app.handle_request(req["id"], "approve")
                            app._show_request_bump_preview(req)

                    _run_step("requests: submit + approve", _requests_submit_approve)

                    def _requests_reject():
                        app.show_page("requests")
                        app.req_officer.set(officer_a2["name"])
                        app.req_date.delete(0, "end")
                        app.req_date.insert(0, off_date_for_squad("A").strftime("%Y-%m-%d"))
                        app.submit_request()
                        pending = get_pending_day_off_requests()
                        if pending:
                            app.handle_request(pending[-1]["id"], "reject")

                    _run_step("requests: submit + reject", _requests_reject)

                    def _requests_exports():
                        app.show_page("requests")
                        app._export_requests_csv_filtered()
                        app._export_requests_pdf_filtered()

                    _run_step("requests: filtered exports", _requests_exports)
                else:
                    _run_step("requests: refresh", lambda: (app.show_page("requests"), app.refresh_requests()))

                def _swaps_preview_submit():
                    app.show_page("swaps")
                    app._refresh_swap_officer_dropdowns()
                    labels = list(app.swap_officer_map.keys())
                    if len(labels) >= 2:
                        app.swap_officer1.set(labels[0])
                        app.swap_officer2.set(labels[1])
                        app.swap_date.delete(0, "end")
                        app.swap_date.insert(0, work_day_str)
                        app.preview_swap()
                        if mutating:
                            app.submit_swap()

                _run_step("swaps: preview" + (" + submit" if mutating else ""), _swaps_preview_submit)

                if mutating:

                    def _swaps_approve():
                        app.show_page("swaps")
                        app.refresh_swaps()
                        pending = get_pending_shift_swap_requests()
                        if pending:
                            app.handle_swap(pending[0]["id"], "approve")

                    _run_step("swaps: approve", _swaps_approve)

                    def _swaps_reject():
                        app.show_page("swaps")
                        labels = list(app.swap_officer_map.keys())
                        if len(labels) >= 2:
                            app.swap_officer1.set(labels[0])
                            app.swap_officer2.set(labels[1])
                            app.swap_date.delete(0, "end")
                            app.swap_date.insert(0, work_day_str)
                            app.submit_swap()
                        pending = get_pending_shift_swap_requests()
                        if pending:
                            app.handle_swap(pending[-1]["id"], "reject")

                    _run_step("swaps: submit + reject", _swaps_reject)

                    def _swaps_exports():
                        app.show_page("swaps")
                        app._export_swaps_csv_filtered()
                        app._export_swaps_pdf_filtered()

                    _run_step("swaps: filtered exports", _swaps_exports)
                else:
                    _run_step("swaps: refresh", lambda: (app.show_page("swaps"), app.refresh_swaps()))

                def _timeline_gantt():
                    app.show_page("timeline")
                    app.refresh_gantt()
                    app._shift_gantt_cycle(-1)
                    app._shift_gantt_cycle(1)
                    app._reset_gantt_cycle()
                    app._export_gantt_ical()
                    with patch("tkinter.filedialog.asksaveasfilename", return_value=export_pdf):
                        app._export_gantt_pdf()

                _run_step("timeline: gantt cycle + exports", _timeline_gantt)

                def _base_schedule():
                    app.show_page("base_schedule")
                    app.refresh_monthly("base")
                    app._schedule_action("base")
                    base_state = app._schedule_pages["base"]
                    base_summary = get_monthly_summary_from_snapshot(
                        base_state.get("snapshot"),
                        work_day.year,
                        work_day.month,
                        "base",
                    )
                    for entry in base_summary:
                        if entry.get("date") == work_day:
                            app._select_monthly_day("base", work_day.day, entry)
                            break
                    with patch("tkinter.filedialog.asksaveasfilename", return_value=export_pdf):
                        app._export_monthly_pdf("base")

                _run_step("base_schedule: publish + day + pdf", _base_schedule)

                def _live_schedule():
                    app.show_page("live_schedule")
                    state = app._schedule_pages["updated"]
                    state["month_year"].set(f"{work_day.year}-{work_day.month:02d}")
                    app.refresh_monthly("updated")
                    app._schedule_action("updated")
                    summary = get_monthly_summary_from_snapshot(
                        state.get("snapshot"),
                        work_day.year,
                        work_day.month,
                        "updated",
                    )
                    for entry in summary:
                        if entry.get("date") == work_day:
                            app._select_monthly_day("updated", work_day.day, entry)
                            break
                    app._show_schedule_diff()
                    if _invoke_button(app.root, "Export CSV"):
                        pass
                    _close_toplevels(app.root)
                    dlg = _open_dialog_without_wait(app, app._show_manual_coverage_dialog)
                    if dlg:
                        entries = _entries_in(dlg)
                        if entries:
                            entries[0].delete(0, "end")
                            entries[0].insert(0, work_day_str)
                        _invoke_button(dlg, "Assign Coverage")
                    _close_toplevels(app.root)
                    if state.get("selected_entry"):
                        edit_dlg = _open_dialog_without_wait(
                            app,
                            lambda: app._manual_schedule_edit("updated"),
                        )
                        if edit_dlg:
                            _invoke_button(edit_dlg, "Save Assignment")
                    _close_toplevels(app.root)
                    app._export_updated_diff_csv_from_toolbar()
                    with patch("tkinter.filedialog.asksaveasfilename", return_value=export_pdf):
                        app._export_monthly_pdf("updated")

                _run_step("live_schedule: sync/diff/coverage/edit", _live_schedule)

                def _timecard_periods():
                    app.show_page("timecard")
                    app.refresh_timecard()
                    app._shift_timecard_period(-1)
                    app._shift_timecard_period(1)
                    app._reset_timecard_period()

                _run_step("timecard: period navigation", _timecard_periods)

                if mutating:

                    def _timecard_save_flow():
                        app.show_page("timecard")
                        app.prefill_timecard()
                        app.copy_previous_timecard()
                        if app._timecard_day_widgets:
                            w = app._timecard_day_widgets[0]
                            if not w.get("imported"):
                                app._save_timecard_day(
                                    w["date"],
                                    w["time_in"],
                                    w["time_out"],
                                    w["hours"],
                                    w["pay_type"],
                                    w["night"],
                                    w["notes"],
                                )
                        app.save_all_timecard()
                        app.import_timecard_payroll()
                        app._export_timecard_csv()

                    _run_step("timecard: prefill/save/import/export", _timecard_save_flow)
                else:
                    _run_step("timecard: refresh", lambda: (app.show_page("timecard"), app.refresh_timecard()))

                def _payroll_periods():
                    app.show_page("payroll")
                    app.refresh_payroll_period()
                    app.refresh_payroll()
                    app._shift_payroll_period(-1)
                    app._shift_payroll_period(1)
                    app._reset_payroll_period()

                _run_step("payroll: period navigation", _payroll_periods)

                if mutating:

                    def _payroll_entry():
                        app.show_page("payroll")
                        if app.pay_officer_map:
                            first = next(iter(app.pay_officer_map))
                            app.pay_officer.set(first)
                            app._on_pay_officer_change()
                            app._on_pay_type_change()
                            app.pay_hours.delete(0, "end")
                            app.pay_hours.insert(0, "8")
                            app.pay_date.delete(0, "end")
                            app.pay_date.insert(0, work_day_str)
                            app.preview_payroll()
                            app.save_payroll_entry()
                        app._preview_payroll_stub()
                        app._toggle_pay_period_lock()
                        app._toggle_pay_period_lock()
                        with patch("tkinter.filedialog.asksaveasfilename", return_value=export_pdf):
                            app._export_payroll_stub()
                            app._export_payroll_pdf()
                        app._export_payroll_csv_from_tab()
                        app._export_pay_period_history_csv()
                        app._refresh_pay_period_history()
                        if _invoke_button(app.root, "Timecard"):
                            app.show_page("payroll")

                    _run_step("payroll: entry/lock/exports/history jump", _payroll_entry)
                else:

                    def _payroll_readonly():
                        app.show_page("payroll")
                        app.preview_payroll()

                    _run_step("payroll: preview", _payroll_readonly)

                def _reports_exports():
                    app.show_page("reports")
                    app.refresh_reports()
                    for fn in (
                        app._export_roster_csv,
                        app._export_payroll_csv,
                        app._export_timecard_csv,
                        app._export_requests_csv,
                        app._export_swaps_csv,
                        app._export_audit_csv,
                        app._export_pay_period_history_csv,
                    ):
                        fn()
                    with patch("tkinter.filedialog.asksaveasfilename", return_value=export_pdf):
                        app._export_coverage_pdf()
                        app._export_pay_stub_pdf()
                    app._export_schedule_diff_from_reports(work_day.year, work_day.month)
                    app._show_pay_stub_preview()

                _run_step("reports: exports + pay stub preview", _reports_exports)

                if mutating and hasattr(app, "_dept_name_entry"):

                    def _reports_dept_settings():
                        from logic import get_department_setting, set_department_setting

                        app.show_page("reports")
                        uid = app.current_user.get("id")
                        updates = {
                            "department_name": "Dodgeville Police Department",
                            "department_mission": (
                                "To protect and serve, in partnership with our community, "
                                "through integrity and compassion"
                            ),
                            "department_tagline": "Est. 1859",
                            "overtime_threshold": "80",
                        }
                        for key, value in updates.items():
                            result = set_department_setting(key, value, user_id=uid)
                            if not result.get("success"):
                                raise RuntimeError(result.get("message", f"Failed to save {key}"))
                        app._refresh_department_branding()
                        app.refresh_reports()
                        for key, value in updates.items():
                            if get_department_setting(key) != value:
                                raise RuntimeError(f"Setting {key} did not persist")

                    _run_step("reports: department settings save", _reports_dept_settings)

                def _availability_base():
                    app.show_page("availability")
                    app.refresh_availability()

                _run_step("availability: refresh", _availability_base)

                if mutating:

                    def _availability_crud():
                        app.show_page("availability")
                        app._avail_date_entry.delete(0, "end")
                        app._avail_date_entry.insert(0, "2026-12-15")
                        app._add_availability()
                        entries = get_officer_availability()
                        if entries:
                            app._delete_availability(entries[-1]["id"])

                    _run_step("availability: add + delete", _availability_crud)

                    if app.can("holidays.manage"):

                        def _availability_holiday():
                            app.show_page("availability")
                            dlg = _open_dialog_without_wait(app, app._show_add_holiday_dialog)
                            if dlg:
                                entries = _entries_in(dlg)
                                if len(entries) >= 2:
                                    entries[0].insert(0, "UI Test Holiday")
                                    entries[1].insert(0, "2026-12-26")
                                _invoke_button(dlg, "Save")
                            _close_toplevels(app.root)
                            holidays = get_holidays(2026)
                            ui_holidays = [h for h in holidays if h.get("name") == "UI Test Holiday"]
                            if ui_holidays:
                                app._delete_holiday(ui_holidays[-1]["id"])

                        _run_step("availability: holiday add + delete", _availability_holiday)

                    if app.can("open_shifts.manage") and hasattr(app, "_open_shift_date"):

                        def _availability_open_shift():
                            app.show_page("availability")
                            app._open_shift_date.delete(0, "end")
                            app._open_shift_date.insert(0, work_day_str)
                            app._post_open_shift()
                            shifts = get_open_shifts()
                            if shifts and app.can("open_shifts.claim"):
                                app._claim_open_shift(shifts[-1]["id"])

                        _run_step("availability: post + claim open shift", _availability_open_shift)

                def _notifications_flow():
                    app.show_page("dashboard")
                    app.refresh_notifications()
                    notes = get_notifications(limit=20)
                    unread = [n for n in notes if not n.get("is_read")]
                    if unread:
                        app._mark_notification(unread[0]["id"])
                    if notes:
                        app._navigate_from_notification(notes[0])
                    app._mark_all_notifications_read()
                    app._export_requests_pdf()

                _run_step("notifications: mark/read/navigate/export", _notifications_flow)

                def _users_list():
                    app.show_page("users")
                    app.refresh_users()

                _run_step("users: refresh list", _users_list)

                if mutating and app.can("users.manage"):

                    def _users_create():
                        nonlocal created_username
                        app.show_page("users")
                        created_username = f"uitest_{uuid.uuid4().hex[:8]}"
                        app._user_username.delete(0, "end")
                        app._user_username.insert(0, created_username)
                        app._user_password.delete(0, "end")
                        app._user_password.insert(0, "TestPass1!")
                        app._user_role.set("Officer")
                        app._create_app_user()

                    _run_step("users: create account", _users_create)

                    def _users_edit_reset_toggle():
                        app.show_page("users")
                        app.refresh_users()
                        target = None
                        for user in list_all_users():
                            if created_username and user["username"] == created_username:
                                target = user
                                break
                        if not target:
                            for user in list_all_users():
                                if user["username"].startswith("uitest_"):
                                    target = user
                                    break
                        if not target:
                            return
                        dlg = _open_dialog_without_wait(
                            app,
                            lambda: app._edit_app_user(target, full_edit=True),
                        )
                        if dlg:
                            _invoke_button(dlg, "Save Changes")
                        _close_toplevels(app.root)
                        import customtkinter as ctk

                        with patch.object(ctk.CTkInputDialog, "get_input", return_value="ResetPass1!"):
                            app._reset_user_password(target)
                        app._toggle_user_active(target, active=False)
                        app._toggle_user_active(target, active=True)

                    _run_step("users: edit + reset password + toggle active", _users_edit_reset_toggle)

                def _simulator_flow():
                    app.show_page("simulator")
                    app._simulator_load_roster()
                    app.run_schedule_simulator()
                    app._export_simulation_csv()

                _run_step("simulator: load/run/export", _simulator_flow)

                from scripts.ui_extended_handlers import run_extended_handlers, run_role_sessions

                ctx = {
                    "officer_a": officer_a,
                    "officer_a2": officer_a2,
                    "work_day": work_day,
                    "work_day_str": work_day_str,
                    "off_day_str": off_day_str,
                    "export_pdf": export_pdf,
                    "export_csv": export_csv,
                }
                run_extended_handlers(app, ctx, _run_step, mutating=mutating)
                run_role_sessions(app, ctx, _run_step, mutating=mutating)

                def _shell_shortcuts():
                    app.show_page("dashboard")
                    app.root.event_generate("<Control-Key-2>")
                    app.root.update()
                    app.root.event_generate("<Control-Key-0>")
                    app.root.update()

                _run_step("shell: keyboard shortcuts", _shell_shortcuts)

                if mutating:
                    _run_step("shell: backup database", app.backup_database)

                    def _shell_sign_out_login():
                        app.sign_out()
                        app.root.update()
                        _login_admin(app)

                    _run_step("shell: sign out + re-login", _shell_sign_out_login)

            finally:
                for p in reversed(patches):
                    p.stop()

            if visible and hold_seconds > 0:
                app.root.update()
                time.sleep(hold_seconds)

            report_path = _write_ui_report(
                results,
                visible=visible,
                mutating=mutating,
                isolated=isolated,
                screenshot_dir=screenshot_dir,
            )
            _destroy_app(app.root)

    title = "UI live on-screen test" if visible else "UI exhaustive test"
    failures = [r for r in results if not r[1]]
    if not (visible and step_delay > 0):
        print(f"Dodgeville PD Scheduler — {title}", flush=True)
        print("=" * 60, flush=True)
        for name, ok, detail in results:
            mark = "ok" if ok else "FAIL"
            print(f"  [{mark}] {name}", flush=True)
            if detail:
                for line in detail.strip().splitlines()[-5:]:
                    print(f"         {line}", flush=True)
        print("=" * 60, flush=True)
    else:
        print("=" * 60, flush=True)
    if screenshot_dir:
        report_path = os.path.join(screenshot_dir, "report.json")
        if os.path.isfile(report_path):
            print(f"Report: {report_path}", flush=True)
    if failures:
        print(f"ui exhaustive: {len(failures)} FAILURE(S) / {len(results)} steps")
        return 1
    print(f"ui exhaustive: ALL {len(results)} STEPS PASSED")
    return 0


def _show_profile(app) -> None:
    from ui.profile_dialog import open_my_profile_dialog

    open_my_profile_dialog(app)
    _close_toplevels(app.root)


if __name__ == "__main__":
    raise SystemExit(run_ui_exhaustive())
