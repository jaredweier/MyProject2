"""
Automated end-to-end workflow probe — replaces manual GUI checklist where possible.

Headless UI + logic paths for workflows supervisors care about daily.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ["SCHEDULER_UI_TEST"] = "1"


def _fail(errors: list[str], msg: str) -> None:
    errors.append(msg)


def _check_rust_backend(errors: list[str]) -> None:
    from logic import rust_bridge

    if rust_bridge.backend_name() != "rust":
        _fail(errors, f"scheduling backend is {rust_bridge.backend_name()!r}, expected rust")


def _check_window_layout_guard(errors: list[str]) -> None:
    session_path = os.path.join(ROOT, "ui", "session_pages.py")
    with open(session_path, encoding="utf-8") as fh:
        source = fh.read()
    if 'bind("<Map>"' in source and "apply_main_window_layout" in source:
        _fail(errors, "session_pages binds <Map> to apply_main_window_layout (focus loop risk)")
    layout_path = os.path.join(ROOT, "ui", "window_layout.py")
    with open(layout_path, encoding="utf-8") as fh:
        layout_src = fh.read()
    if "_applied_for" not in layout_src:
        _fail(errors, "window_layout missing _applied_for guard")


def _check_day_off_approval_chain(errors: list[str]) -> None:
    from tests.helpers import get_any_officer, test_database, working_date_for_squad

    with test_database():
        import logic

        squad_a = get_any_officer("A", "06:00")
        officers_a = [
            o
            for o in logic.get_officers_by_seniority()
            if o["squad"] == "A" and o["shift_start"] == "06:00" and o.get("active") == 1
        ]
        if len(officers_a) < 2:
            _fail(errors, "need two Squad A 06:00 officers for bump chain test")
            return
        original, replacement = officers_a[0], officers_a[1]
        work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
        cr = logic.create_day_off_request(original["id"], work_day, "Vacation")
        if not cr.get("success"):
            _fail(errors, f"create day-off failed: {cr.get('message')}")
            return
        pr = logic.process_day_off_request(cr["request_id"], "approve")
        if not pr.success:
            _fail(errors, f"approve day-off failed: {pr.message}")
            return
        from database import get_connection

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT replacement_officer_id FROM schedule_overrides
            WHERE original_officer_id = ? AND override_date = ?
            ORDER BY id DESC LIMIT 1
            """,
            (original["id"], work_day),
        )
        row = cur.fetchone()
        conn.close()
        if not row or not row[0]:
            _fail(errors, "no schedule override after day-off approval")
            return
        replacement_id = row[0]
        notes = logic.get_notifications(replacement_id, unread_only=False, limit=20)
        if not any("covering" in (n.get("message") or "").lower() for n in notes):
            _fail(errors, "replacement officer did not receive coverage notification")


def _check_pay_period_lock(errors: list[str]) -> None:
    from tests.helpers import get_any_officer, test_database

    with test_database():
        import logic

        officer = get_any_officer("A", "06:00")
        start, _end = logic.get_pay_period()
        lock = logic.lock_pay_period(start)
        if not lock.get("success"):
            _fail(errors, f"lock pay period failed: {lock.get('message')}")
            return
        if not logic.is_pay_period_locked(start):
            _fail(errors, "pay period not locked after lock_pay_period")
        entry = logic.save_timecard_entry(
            officer["id"],
            start.isoformat(),
            hours_worked=8.0,
        )
        if entry.get("success"):
            _fail(errors, "save_timecard_entry succeeded on locked period")
        logic.unlock_pay_period()


def _check_demo_password_policy(errors: list[str]) -> None:
    from tests.helpers import test_database

    with test_database():
        import logic

        users = {u["username"]: u for u in logic.list_all_users()}
        for username in ("admin", "supervisor", "officer"):
            user = users.get(username)
            if not user:
                _fail(errors, f"missing demo user {username}")
                continue
            if user.get("must_change_password") != 1:
                _fail(errors, f"{username} must_change_password is not 1")


def _check_password_change_login_path(errors: list[str]) -> None:
    """Officer with must_change_password can complete change and enter shell."""
    from tests.helpers import test_database

    with test_database():
        import logic

        users = logic.list_login_users()
        officer_user = next((u for u in users if u["username"] == "officer"), None)
        if not officer_user:
            _fail(errors, "officer demo user missing")
            return
        if officer_user.get("must_change_password") != 1:
            _fail(errors, "officer should require password change before login completes")
        result = logic.change_own_password(officer_user["id"], "officer", "NewOfficer1!")
        if not result.get("success"):
            _fail(errors, f"password change failed: {result.get('message')}")
            return
        refreshed = logic.get_user_by_id(officer_user["id"])
        if refreshed.get("must_change_password") != 0:
            _fail(errors, "must_change_password not cleared after change")


def _check_headless_ui_shell(errors: list[str]) -> None:
    from scripts.ui_test_helpers import (
        authenticate_role,
        create_headless_app,
        destroy_app,
        headless_login,
        shell_ready,
    )
    from ui.assets import reset_brand_image_cache

    reset_brand_image_cache()
    user = authenticate_role("admin", "admin")
    if not user:
        _fail(errors, "admin authenticate failed")
        return
    user["must_change_password"] = 0
    app, callback_errors = create_headless_app()
    try:
        headless_login(app, user)
        if not shell_ready(app):
            _fail(errors, "shell not ready after login")
        if callback_errors:
            _fail(errors, f"{len(callback_errors)} Tk callback errors during shell login")
    finally:
        destroy_app(app.root)


def run_ui_workflow_probe() -> int:
    from ui.assets import reset_brand_image_cache

    reset_brand_image_cache()
    print("Dodgeville PD Scheduler — ui-workflow-probe")
    print("=" * 60)
    errors: list[str] = []

    checks = (
        ("rust-backend", _check_rust_backend),
        ("window-layout-guard", _check_window_layout_guard),
        ("demo-password-policy", _check_demo_password_policy),
        ("password-change-path", _check_password_change_login_path),
        ("day-off-approval-chain", _check_day_off_approval_chain),
        ("pay-period-lock", _check_pay_period_lock),
        ("headless-ui-shell", _check_headless_ui_shell),
    )
    for name, fn in checks:
        print(f"\n>>> {name}", flush=True)
        try:
            fn(errors)
        except Exception as exc:
            _fail(errors, f"{name}: {exc}")

    print("\n" + "=" * 60)
    if errors:
        for err in errors:
            print(f"  [FAIL] {err}")
        print("ui-workflow-probe: FAILED")
        return 1
    print("ui-workflow-probe: ALL PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_ui_workflow_probe())
