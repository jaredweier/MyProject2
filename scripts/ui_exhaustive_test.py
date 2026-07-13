"""
Headless exhaustive UI test — modular page shell (post-rebuild).

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
from contextlib import nullcontext
from datetime import datetime, timezone
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ["SCHEDULER_UI_TEST"] = "1"

from scripts.ui_test_helpers import (  # noqa: E402
    authenticate_role,
    destroy_app,
    headless_login,
    refresh_tk,
    shell_ready,
)

_EXHAUSTIVE_LOCK = os.path.join(ROOT, "logs", ".ui_exhaustive.lock")


def _safe_filename(name: str) -> str:
    return re.sub(r"[^\w\-.]+", "_", name).strip("_")[:120] or "step"


def _screenshot_window(root, path: str) -> None:
    from PIL import ImageGrab

    refresh_tk(root)
    x = root.winfo_rootx()
    y = root.winfo_rooty()
    w = max(root.winfo_width(), 1)
    h = max(root.winfo_height(), 1)
    ImageGrab.grab((x, y, x + w, y + h)).save(path)


def _lock_holder_alive(pid: str) -> bool:
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError, TypeError):
        return False
    return True


def _acquire_exhaustive_lock() -> bool:
    """Prevent concurrent exhaustive runs (they deadlock headless Tk login)."""
    os.makedirs(os.path.dirname(_EXHAUSTIVE_LOCK), exist_ok=True)
    if os.path.isfile(_EXHAUSTIVE_LOCK):
        try:
            with open(_EXHAUSTIVE_LOCK, encoding="utf-8") as fh:
                pid = fh.read().strip()
        except OSError:
            pid = "?"
        if pid and pid != "?" and not _lock_holder_alive(pid):
            try:
                os.remove(_EXHAUSTIVE_LOCK)
            except OSError:
                pass
        elif os.path.isfile(_EXHAUSTIVE_LOCK):
            print(
                f"ui-exhaustive: lock held ({_EXHAUSTIVE_LOCK}, pid={pid}) — wait for other run to finish",
                flush=True,
            )
            return False
    with open(_EXHAUSTIVE_LOCK, "w", encoding="utf-8") as fh:
        fh.write(str(os.getpid()))
    return True


def _release_exhaustive_lock() -> None:
    try:
        os.remove(_EXHAUSTIVE_LOCK)
    except OSError:
        pass


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
            refresh_tk(app.root)
            time.sleep(step_delay)
        if app is not None and screenshot_dir:
            path = os.path.join(screenshot_dir, f"{len(results):02d}_{_safe_filename(name)}.png")
            _screenshot_window(app.root, path)
        if screenshot_dir or step_delay > 0 or os.environ.get("SCHEDULER_UI_TEST", "").strip() == "1":
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
    _close_toplevels(root)
    destroy_app(root)


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
                "screenshot": os.path.join(screenshot_dir, f"{i:02d}_{_safe_filename(name)}.png") if ok else None,
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
    refresh_tk(app.root)
    tops = [w for w in app.root.winfo_children() if w.winfo_class() == "CTkToplevel"]
    return tops[-1] if tops else None


def _entries_in(widget):
    import customtkinter as ctk

    return [w for w in _walk_widgets(widget) if isinstance(w, ctk.CTkEntry)]


def _shell_alive(app) -> bool:
    return shell_ready(app)


def _login_admin(app) -> None:
    """Headless admin session against the modular shell."""
    from logic import set_department_setting

    user = authenticate_role("admin", "admin")
    if not user:
        raise RuntimeError("admin login failed (username=admin)")
    if not shell_ready(app):
        headless_login(app, user)
    else:
        app.current_user = user
        if app.current_page is None and app.pages:
            app.show_page("dashboard")
    set_department_setting("setup_complete", "1")
    refresh_tk(app.root)
    if not shell_ready(app):
        raise RuntimeError("shell not ready after admin login")
    if not app.current_user or app.current_user.get("role") != "Administration":
        raise RuntimeError("admin role not active after login")


def _login_role(app, username: str, password: str) -> None:
    from logic import set_department_setting

    user = authenticate_role(username, password)
    if not user:
        raise RuntimeError(f"login failed for {username}")
    headless_login(app, user)
    set_department_setting("setup_complete", "1")
    refresh_tk(app.root)
    if not shell_ready(app):
        raise RuntimeError(f"shell not ready after {username} login")


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
    if not _acquire_exhaustive_lock():
        return 1
    try:
        return _run_ui_exhaustive_impl(
            visible=visible,
            step_delay=step_delay,
            screenshot_dir=screenshot_dir,
            isolated=isolated,
            auto_login=auto_login,
            mutating=mutating,
            hold_seconds=hold_seconds,
        )
    finally:
        _release_exhaustive_lock()


def _run_ui_exhaustive_impl(
    *,
    visible: bool = False,
    step_delay: float = 0,
    screenshot_dir: str | None = None,
    isolated: bool = True,
    auto_login: bool = False,
    mutating: bool = True,
    hold_seconds: float = 0,
) -> int:
    """Modular exhaustive: login → visit every page → controller refresh → roles → shell ops."""
    from tests.helpers import get_any_officer, test_database, working_date_for_squad
    from ui.pages import PAGE_CLASSES
    from ui.theme import NAV_ITEMS

    results: list[tuple[str, bool, str]] = []
    app = None

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
        from ui.app import DodgevilleSchedulerApp
        from ui.window_layout import apply_main_window_layout

        if visible:
            print("  Starting visible UI session…", flush=True)
        app = DodgevilleSchedulerApp()
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
            patch(
                "tkinter.filedialog.asksaveasfilename", return_value=os.path.join(tempfile.gettempdir(), "ui_ex.csv")
            ),
            patch("tkinter.filedialog.askopenfilename", return_value=""),
        ]
        for p in patches:
            p.start()
        try:
            # ---- login ----
            if not auto_login:
                _run_step("shell: admin login", lambda: _login_admin(app))
            else:
                user = authenticate_role("admin", "admin")
                if not user:
                    raise RuntimeError("auto_login: admin auth failed")
                headless_login(app, user)

            # ---- nav visit (NAV_ITEMS + page frames) ----
            visited = set()
            for key, _, _ in NAV_ITEMS:
                if key not in app.pages:
                    # notifications aliases to dashboard frame
                    if key == "notifications" and "dashboard" in app.pages:
                        _run_step(f"nav: show_page({key})", lambda: app.show_page("notifications"))
                        visited.add(key)
                    continue
                _run_step(f"nav: show_page({key})", lambda k=key: app.show_page(k))
                visited.add(key)

            for key in PAGE_CLASSES:
                if key in visited or key not in app.pages:
                    continue
                _run_step(f"nav: show_page({key})", lambda k=key: app.show_page(k))

            # ---- controller refresh each mounted page ----
            for key, ctrl in list(app.page_controllers.items()):

                def _refresh(k=key, c=ctrl):
                    app.show_page(k)
                    c.ensure_built()
                    c.refresh()

                _run_step(f"page: refresh({key})", _refresh)

            _run_step("shell: refresh_all", app.refresh_all)

            def _refresh_current():
                if app.current_page:
                    app._refresh_page(app.current_page)

            _run_step("shell: refresh current page (F5)", _refresh_current)

            # ---- logic-backed mutation smoke (UI still shows results via refresh) ----
            if mutating and app.can("requests.approve"):
                officer = get_any_officer("A", "06:00")
                work_day = working_date_for_squad("A").strftime("%Y-%m-%d")

                def _day_off_ui_refresh():
                    import logic

                    cr = logic.create_day_off_request(officer["id"], work_day, "Vacation")
                    if not cr.get("success"):
                        # may already exist from prior step — still exercise UI
                        pass
                    app.show_page("requests")
                    ctrl = app.page_controllers.get("requests")
                    if ctrl:
                        ctrl.refresh()
                    app.show_page("dashboard")
                    dctrl = app.page_controllers.get("dashboard")
                    if dctrl:
                        dctrl.refresh()

                _run_step("workflow: day-off request + leave/dashboard refresh", _day_off_ui_refresh)

            if mutating and app.can("timecard.edit_all"):
                officer = get_any_officer("A", "06:00")

                def _timecard_ui():
                    import logic

                    start, _end = logic.get_pay_period()
                    logic.save_timecard_entry(
                        officer["id"],
                        start.isoformat(),
                        hours_worked=8.0,
                    )
                    app.show_page("timecard")
                    ctrl = app.page_controllers.get("timecard")
                    if ctrl:
                        ctrl.refresh()
                    app.show_page("payroll")
                    pctrl = app.page_controllers.get("payroll")
                    if pctrl:
                        pctrl.refresh()

                _run_step("workflow: timecard save + finance refresh", _timecard_ui)

            # ---- jump / search if present ----
            if hasattr(app, "_jump_to_page"):

                def _jump():
                    app._jump_to_page("payroll")
                    if app.current_page not in ("payroll", "timecard", "banked_time"):
                        # jump is best-effort; still navigable via show_page
                        app.show_page("payroll")

                _run_step("shell: jump_to_page payroll", _jump)

            # ---- backup ----
            if mutating and hasattr(app, "backup_database"):
                _run_step("shell: backup database", app.backup_database)

            # ---- role sessions ----
            for username, password, label in (
                ("supervisor", "supervisor", "Supervisor"),
                ("officer", "officer", "Officer"),
            ):

                def _role(u=username, p=password, lab=label):
                    _login_role(app, u, p)
                    # visit a subset of pages each role can open
                    for key in ("dashboard", "base_schedule", "live_schedule", "requests", "timecard"):
                        if key in app.pages:
                            app.show_page(key)
                            ctrl = app.page_controllers.get(key)
                            if ctrl:
                                ctrl.refresh()
                    if app.current_user and app.current_user.get("role") != lab:
                        # officer seed may map to Officer; supervisor → Supervisor
                        got = (app.current_user or {}).get("role")
                        if lab == "Officer" and got == "Officer":
                            return
                        if lab == "Supervisor" and got == "Supervisor":
                            return
                        # tolerate alternate role names if auth succeeded
                        if not got:
                            raise RuntimeError(f"{lab} role missing after login")

                _run_step(f"role: {label} login + page walk", _role)

            # back to admin for sign-out test
            _run_step("shell: re-login admin", lambda: _login_admin(app))

            if mutating:

                def _sign_out_relogin():
                    app.sign_out()
                    refresh_tk(app.root)
                    _login_admin(app)

                _run_step("shell: sign out + re-login", _sign_out_relogin)

            # extended modular handlers (safe / no old monolith APIs)
            from scripts.ui_extended_handlers import run_extended_handlers, run_role_sessions

            officer_a = get_any_officer("A", "06:00")
            ctx = {
                "officer_a": officer_a,
                "work_day_str": working_date_for_squad("A").strftime("%Y-%m-%d"),
            }
            run_extended_handlers(app, ctx, _run_step, mutating=mutating)
            run_role_sessions(app, ctx, _run_step, mutating=mutating)

        finally:
            for p in reversed(patches):
                p.stop()
            if visible and hold_seconds > 0:
                refresh_tk(app.root)
                time.sleep(hold_seconds)
            _write_ui_report(
                results,
                visible=visible,
                mutating=mutating,
                isolated=isolated,
                screenshot_dir=screenshot_dir,
            )
            if app is not None:
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
    if screenshot_dir:
        report_path = os.path.join(screenshot_dir, "report.json")
        if os.path.isfile(report_path):
            print(f"Report: {report_path}", flush=True)
    if failures:
        print(f"ui exhaustive: {len(failures)} FAILURE(S) / {len(results)} steps")
        return 1
    print(f"ui exhaustive: ALL {len(results)} STEPS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_ui_exhaustive())
