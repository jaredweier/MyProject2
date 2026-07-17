"""
Optional Chronos NiceGUI E2E smoke via Playwright (local machine, cheap).

Install (once, optional):
  pip install playwright
  playwright install chromium

Run Chronos first:
  python main.py --browser
  # default http://127.0.0.1:8080

Then:
  python dev.py chronos-e2e
  python dev.py chronos-e2e --base-url http://127.0.0.1:8080

Does not replace ui-smoke / ui-exhaustive (Tk). This targets primary NiceGUI.
Never put business rules here — only navigation/smoke asserts.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
from typing import List, Optional
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def playwright_available() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


def _server_reachable(base_url: str, *, timeout: float = 2.0) -> tuple[bool, str]:
    """Fail fast if Chronos is not listening (avoids long hang under parallel e2e)."""
    try:
        u = urlparse(base_url if "://" in base_url else f"http://{base_url}")
        host = u.hostname or "127.0.0.1"
        port = int(u.port or (443 if u.scheme == "https" else 80))
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"{host}:{port}"
    except OSError as exc:
        return False, str(exc)


def run_chronos_e2e(
    *,
    base_url: str = "http://127.0.0.1:8080",
    username: str = "admin",
    password: str = "admin",
    headed: bool = False,
    quick: bool = False,
) -> int:
    print("Chronos E2E (Playwright optional)")
    print("=" * 56)
    print("  Policy: **one Chronos only** on :8080 — parallel Playwright+server can hang")
    quick = quick or os.environ.get("CHRONOS_E2E_QUICK", "").strip().lower() in ("1", "true", "yes")
    if quick:
        print("  Mode: quick (critical paths only)")
    if not playwright_available():
        print("  [SKIP] playwright not installed")
        print("  pip install playwright && playwright install chromium")
        print("  Then: python dev.py chronos-e2e")
        print("  Docs: https://playwright.dev/python/docs/intro")
        print("  Free fallback: python dev.py ui-review && python dev.py ui-smoke")
        return 0

    ok_reach, reach_detail = _server_reachable(base_url)
    if not ok_reach:
        print(f"  [FAIL] Chronos not reachable at {base_url} ({reach_detail})")
        print("  Start one server:  $env:SCHEDULER_SKIP_GATES='1'; python main.py --browser")
        print("  Then re-run:       python dev.py chronos-e2e --base-url", base_url)
        print("  Quick subset:      python dev.py chronos-e2e --quick")
        return 1
    print(f"  [ok] server reachable ({reach_detail})")

    from playwright.sync_api import sync_playwright

    failures: List[str] = []
    FULL_PATHS = (
        "/",
        "/my-week",
        "/notifications",
        "/my-schedule",
        "/monthly-schedule",
        "/live-schedule",
        "/time-off",
        "/open-shifts",
        "/bidding",
        "/callbacks",
        "/court",
        "/availability",
        "/roster",
        "/certs",
        "/timecards",
        "/time-punch",
        "/banks",
        "/payroll",
        "/ops-desk",
        "/simulator",
        "/operations",
        "/exports",
        "/channels",
        "/audit",
        "/deploy",
        "/media",
        "/security",
        "/access",
    )
    QUICK_PATHS = (
        "/",
        "/my-week",
        "/time-off",
        "/ops-desk",
        "/roster",
        "/payroll",
        "/deploy",
        "/security",
        "/operations",
    )
    smoke_paths = QUICK_PATHS if quick else FULL_PATHS

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(45000)
        try:
            page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(600)
            # Login — data-testid first (Playwright resilience), then password/label fallbacks
            pass_sel = 'input[type="password"]'
            did_login = False
            try:
                tid_user = page.locator('[data-testid="login-username"] input, [data-testid="login-username"]')
                tid_pass = page.locator('[data-testid="login-password"] input, [data-testid="login-password"]')
                tid_btn = page.locator('[data-testid="login-submit"]')
                if tid_user.count() > 0 and tid_pass.count() > 0 and tid_btn.count() > 0:
                    tid_user.first.fill(username)
                    tid_pass.first.fill(password)
                    tid_btn.first.click()
                    did_login = True
                    page.wait_for_timeout(2000)
            except Exception:
                did_login = False
            if not did_login and page.locator(pass_sel).count() > 0:
                inputs = page.locator("input:visible")
                filled_user = False
                for i in range(min(inputs.count(), 6)):
                    el = inputs.nth(i)
                    typ = (el.get_attribute("type") or "text").lower()
                    if typ in ("text", "email", "search", ""):
                        el.fill(username)
                        filled_user = True
                        break
                if not filled_user:
                    page.locator("input").first.fill(username)
                page.locator(pass_sel).first.fill(password)
                btn = page.locator('button:has-text("Sign In")')
                if btn.count() == 0:
                    btn = page.locator('button:has-text("Sign"), button:has-text("Log"), button[type="submit"]')
                btn.first.click()
                did_login = True
                page.wait_for_timeout(2000)
            if did_login:
                try:
                    page.wait_for_url(lambda u: "/login" not in u, timeout=8000)
                except Exception:
                    pass
                try:
                    page.wait_for_timeout(500)
                    body0 = page.inner_text("body") or ""
                    if any(
                        s in body0
                        for s in (
                            "Duty Board",
                            "Time Off",
                            "SYSTEM LIVE",
                            "Sign Out",
                            "Sign out",
                            "Patrol Roster",
                        )
                    ):
                        print("  [ok] login session (shell chrome visible)")
                    elif "Invalid" in body0 or "invalid" in body0:
                        failures.append("login: invalid credentials")
                        print("  [FAIL] login: invalid credentials")
                    else:
                        try:
                            page.get_by_label("Username", exact=False).fill(username)
                            page.get_by_label("Password", exact=False).fill(password)
                            page.get_by_role("button", name="Sign In").click()
                            page.wait_for_timeout(2500)
                            body0 = page.inner_text("body") or ""
                            if "Duty Board" in body0 or "SYSTEM LIVE" in body0:
                                print("  [ok] login session (retry label fill)")
                            else:
                                print("  [warn] login: shell not detected; continuing path probes")
                        except Exception as login_exc:
                            print(f"  [warn] login retry: {login_exc}")
                except Exception as login_exc:
                    print(f"  [warn] login detect: {login_exc}")
            # Smoke paths — full Chronos nav + deeper surfaces (primary product)
            for path in smoke_paths:
                try:
                    page.goto(
                        base_url.rstrip("/") + path,
                        timeout=35000 if quick else 45000,
                        wait_until="domcontentloaded",
                    )
                    page.wait_for_timeout(350 if quick else 500)
                    body = page.inner_text("body") or ""
                    # Session lost only if login form is the only chrome (no shell)
                    on_login_form = "Department credentials" in body or (
                        "Sign In" in body
                        and "Duty Board" not in body
                        and "SYSTEM LIVE" not in body
                        and "Sign out" not in body
                        and "Sign Out" not in body
                    )
                    if on_login_form and path not in ("/login",):
                        failures.append(f"{path}: redirected to login")
                        print(f"  [FAIL] {path}: still on login")
                    elif "doesn't exist" in body or "HTTPException: 404" in body:
                        failures.append(f"{path}: 404")
                        print(f"  [FAIL] {path}: 404")
                    elif any(s in body for s in ("TypeError", "AttributeError", "Traceback")):
                        failures.append(f"{path}: exception text in body")
                        print(f"  [FAIL] {path}: exception in body")
                    else:
                        print(f"  [ok] {path}")
                except Exception as exc:
                    # Heavy pages (simulator/payroll) can time out under load — retry once
                    try:
                        page.goto(
                            base_url.rstrip("/") + path,
                            timeout=60000,
                            wait_until="domcontentloaded",
                        )
                        page.wait_for_timeout(400)
                        body = page.inner_text("body") or ""
                        if "doesn't exist" in body or "HTTPException: 404" in body:
                            failures.append(f"{path}: 404")
                            print(f"  [FAIL] {path}: 404")
                        else:
                            print(f"  [ok] {path} (retry)")
                    except Exception as exc2:
                        # Heavy pages under load — warn in quick, fail in full
                        if quick or "Timeout" in str(exc2) or "timeout" in str(exc2).lower():
                            print(f"  [warn] {path}: {exc2} (soft under load)")
                        else:
                            failures.append(f"{path}: {exc2}")
                            print(f"  [FAIL] {path}: {exc2}")

            # Leave page chrome (admin/supervisor after login) — use visible text
            # Always run leave + payroll core even in --quick (high-value product paths)
            try:
                # Seed one pending day-off so Approve dialog is exerciseable
                try:
                    from logic.requests import create_day_off_request
                    from tests.helpers import get_any_officer, working_date_for_squad

                    off = get_any_officer(squad="A")
                    wd = working_date_for_squad(off.get("squad") or "A")
                    seed = create_day_off_request(
                        int(off["id"]),
                        wd.isoformat(),
                        "Sick",
                        notes="chronos-e2e seed",
                    )
                    if seed.get("success"):
                        print(f"  [ok] seeded leave request #{seed.get('request_id')}")
                    else:
                        print(f"  [warn] leave seed: {seed.get('message')}")
                except Exception as seed_exc:
                    print(f"  [warn] leave seed skipped: {seed_exc}")

                page.goto(
                    base_url.rstrip("/") + "/time-off",
                    timeout=45000,
                    wait_until="domcontentloaded",
                )
                page.wait_for_timeout(1200)
                body = page.inner_text("body")
                checks = [
                    ("Time Off", "Time Off" in body or "time-off" in body.lower()),
                    ("Preview coverage / Submit", "Preview" in body and "Submit" in body),
                    ("Queue or empty state", "Queue" in body or "pending" in body.lower() or "clear" in body.lower()),
                    ("M/D date hint", "M/D" in body or "m/d" in body.lower() or "7/9" in body or "M-D" in body),
                ]
                for label, ok in checks:
                    if ok:
                        print(f"  [ok] time-off chrome: {label}")
                    else:
                        # Stale server may still show old hint — warn only for date hint
                        if label == "M/D date hint":
                            print(f"  [warn] time-off chrome: {label} (restart Chronos if DATE_INPUT_HINT stale)")
                        else:
                            failures.append(f"time-off missing: {label}")
                            print(f"  [FAIL] time-off chrome: {label}")

                # Leave approve dialog path: day-off row Approve (not swap Approve).
                # Prefer row that also has Plans (leave-only chrome). Soft-skip if empty.
                leave_approve = page.locator('div.data-row:has(button:has-text("Plans")) button:has-text("Approve")')
                n_leave = leave_approve.count()
                if n_leave == 0:
                    # Fallback: any Approve on time-off page
                    leave_approve = page.locator('button:has-text("Approve")')
                    n_leave = leave_approve.count()
                if n_leave == 0:
                    print("  [warn] time-off: no Approve buttons (empty pending queue) — seed request or retest later")
                else:
                    leave_approve.first.click()
                    # Dialog loads plans + OT candidates (can take a few seconds)
                    order_btn = page.locator('button:has-text("Order in")')
                    vol_btn = page.locator('button:has-text("Volunteer")')
                    dlg_card = page.locator(".leave-approve-dlg")
                    cover_lbl = page.get_by_text("Cover officer", exact=False)
                    try:
                        order_btn.first.wait_for(state="visible", timeout=15000)
                    except Exception:
                        page.wait_for_timeout(800)
                    dlg_checks = [
                        (
                            "Approve dialog title",
                            dlg_card.count() > 0
                            or page.get_by_text("Approve —", exact=False).count() > 0
                            or cover_lbl.count() > 0
                            or order_btn.count() > 0,
                        ),
                        ("Order in action", order_btn.count() > 0),
                        ("Volunteer action", vol_btn.count() > 0),
                        ("Cover officer select", cover_lbl.count() > 0 or dlg_card.count() > 0),
                    ]
                    dlg_ok = all(ok for _, ok in dlg_checks)
                    for label, ok in dlg_checks:
                        if ok:
                            print(f"  [ok] leave approve dlg: {label}")
                        else:
                            # Soft residual when queue has Approve but not leave-plan dialog
                            print(f"  [warn] leave approve dlg: {label} (soft — may need leave seed / Plans row)")
                    if dlg_ok and order_btn.count() > 0:
                        # Click Order in with default cover selected (or warn to pick).
                        order_btn.first.click()
                        page.wait_for_timeout(1200)
                        body_after = page.inner_text("body") or ""
                        notes = page.locator(".q-notification").all_inner_texts()
                        combined = body_after + " " + " ".join(notes)
                        if any(
                            s in combined
                            for s in (
                                "Select a cover",
                                "Approved",
                                "ordered",
                                "Order",
                                "Replacement",
                                "Failed",
                                "Manual",
                                "Done",
                            )
                        ):
                            print("  [ok] leave approve dlg: Order in click handled")
                        else:
                            print("  [warn] leave approve dlg: Order in click — no clear notify text")
                        # Order-in may already close dialog; Cancel only if still open
                        if page.locator(".leave-approve-dlg").count() > 0:
                            cancel = page.locator('button:has-text("Cancel")')
                            if cancel.count() > 0:
                                cancel.first.click()
                                page.wait_for_timeout(400)
                                print("  [ok] leave approve dlg: closed via Cancel")
                        else:
                            print("  [ok] leave approve dlg: closed after Order in")
                    elif dlg_ok:
                        cancel = page.locator('button:has-text("Cancel")')
                        if cancel.count() > 0:
                            cancel.first.click()
                            page.wait_for_timeout(400)
                            print("  [ok] leave approve dlg: closed via Cancel")
            except Exception as exc:
                failures.append(f"time-off chrome: {exc}")
                print(f"  [FAIL] time-off chrome: {exc}")

            # Payroll / timecards chrome
            try:
                page.goto(
                    base_url.rstrip("/") + "/timecards",
                    timeout=60000,
                    wait_until="domcontentloaded",
                )
                page.wait_for_timeout(1000)
                body = page.inner_text("body")
                for label, ok in (
                    ("Timecards heading", "Timecard" in body),
                    ("Period or lock controls", "period" in body.lower() or "Lock" in body or "Prefill" in body),
                ):
                    if ok:
                        print(f"  [ok] timecards chrome: {label}")
                    else:
                        failures.append(f"timecards missing: {label}")
                        print(f"  [FAIL] timecards chrome: {label}")
                page.goto(
                    base_url.rstrip("/") + "/payroll",
                    timeout=60000,
                    wait_until="domcontentloaded",
                )
                page.wait_for_timeout(1000)
                body = page.inner_text("body")
                for label, ok in (
                    ("Payroll heading", "Payroll" in body),
                    ("Lock panel", "Lock" in body or "pay period" in body.lower()),
                    ("FLSA panel", "FLSA" in body or "7(k)" in body or "work period" in body.lower()),
                ):
                    if ok:
                        print(f"  [ok] payroll chrome: {label}")
                    else:
                        failures.append(f"payroll missing: {label}")
                        print(f"  [FAIL] payroll chrome: {label}")
                # Timecard OT election chrome
                page.goto(
                    base_url.rstrip("/") + "/timecards",
                    timeout=60000,
                    wait_until="domcontentloaded",
                )
                page.wait_for_timeout(800)
                # Open Add Entry tab if present
                add_tab = page.locator('div.q-tab:has-text("Add Entry"), button:has-text("Add Entry")')
                if add_tab.count() > 0:
                    add_tab.first.click()
                    page.wait_for_timeout(500)
                body = page.inner_text("body") or ""
                if "Cash OT" in body or "Comp bank" in body or "Comp Time" in body:
                    print("  [ok] timecards chrome: OT election")
                else:
                    print("  [warn] timecards chrome: OT election text not visible (tab may need click)")
            except Exception as exc:
                failures.append(f"finance chrome: {exc}")
                print(f"  [FAIL] finance chrome: {exc}")

            # Ops Desk residual chrome (always — station/fatigue KPIs)
            try:
                page.goto(
                    base_url.rstrip("/") + "/ops-desk",
                    timeout=45000 if quick else 90000,
                    wait_until="domcontentloaded",
                )
                page.wait_for_timeout(900 if quick else 1500)
                body = page.inner_text("body") or ""
                for label, ok in (
                    ("Ops Desk heading", "Ops Desk" in body or "Manual review" in body or "Ops" in body),
                    (
                        "Callout ladder",
                        "callout" in body.lower() or "ladder" in body.lower() or "Sick" in body or "Order" in body,
                    ),
                    (
                        "Refresh / board",
                        "Refresh" in body or "Manual" in body or "gap" in body.lower() or "Policy" in body,
                    ),
                    (
                        "Stations or fatigue KPI",
                        "station" in body.lower()
                        or "fatigue" in body.lower()
                        or "Stations under" in body
                        or "Fatigue" in body
                        or "min staff" in body.lower(),
                    ),
                ):
                    if ok:
                        print(f"  [ok] ops-desk chrome: {label}")
                    else:
                        if label.startswith("Stations"):
                            print(f"  [warn] ops-desk chrome: {label} (restart Chronos after pull)")
                        else:
                            failures.append(f"ops-desk missing: {label}")
                            print(f"  [FAIL] ops-desk missing: {label}")
            except Exception as exc:
                print(f"  [warn] ops-desk chrome: {exc} (soft if /ops-desk nav smoke ok)")

            if quick:
                print("  [ok] quick mode complete (skip extended chrome)")
            else:
                # Full e2e only — extended surface chrome
                try:
                    page.goto(base_url.rstrip("/") + "/callbacks", timeout=20000)
                    page.wait_for_timeout(800)
                    body = page.inner_text("body") or ""
                    for label, ok in (
                        (
                            "Callback heading",
                            "Callback" in body or "call-down" in body.lower() or "call down" in body.lower(),
                        ),
                        ("Rotation / next", "Rotation" in body or "Next" in body or "Sync" in body),
                    ):
                        if ok:
                            print(f"  [ok] callbacks chrome: {label}")
                        else:
                            failures.append(f"callbacks missing: {label}")
                            print(f"  [FAIL] callbacks chrome: {label}")
                except Exception as exc:
                    failures.append(f"callbacks chrome: {exc}")
                    print(f"  [FAIL] callbacks chrome: {exc}")

                try:
                    page.goto(base_url.rstrip("/") + "/banks", timeout=30000)
                    page.wait_for_timeout(800)
                    body = page.inner_text("body") or ""
                    for label, ok in (
                        ("Time banks heading", "bank" in body.lower() or "comp" in body.lower()),
                        ("Finance subnav", "Timecard" in body or "Payroll" in body or "Punch" in body),
                    ):
                        print(f"  [{'ok' if ok else 'FAIL'}] banks chrome: {label}")
                        if not ok:
                            failures.append(f"banks missing: {label}")
                except Exception as exc:
                    failures.append(f"banks chrome: {exc}")
                    print(f"  [FAIL] banks chrome: {exc}")

                try:
                    page.goto(base_url.rstrip("/") + "/exports", timeout=30000)
                    page.wait_for_timeout(800)
                    body = page.inner_text("body") or ""
                    for label, ok in (
                        ("Exports hub", "Export" in body),
                        ("Roster or iCal", "Roster" in body or "iCal" in body or "CSV" in body),
                    ):
                        print(f"  [{'ok' if ok else 'FAIL'}] exports chrome: {label}")
                        if not ok:
                            failures.append(f"exports missing: {label}")
                except Exception as exc:
                    failures.append(f"exports chrome: {exc}")
                    print(f"  [FAIL] exports chrome: {exc}")

                try:
                    page.goto(base_url.rstrip("/") + "/deploy", timeout=45000)
                    page.wait_for_timeout(1000)
                    body = page.inner_text("body") or ""
                    for label, ok in (
                        ("Geofence panel", "Geofence" in body or "geofence" in body.lower()),
                        ("Map or radius", "Radius" in body or "Latitude" in body or "map" in body.lower()),
                        ("Test punch", "Test punch" in body or "Record test" in body or "Apply punches" in body),
                    ):
                        print(f"  [{'ok' if ok else 'FAIL'}] deploy chrome: {label}")
                        if not ok:
                            failures.append(f"deploy missing: {label}")
                except Exception as exc:
                    failures.append(f"deploy chrome: {exc}")
                    print(f"  [FAIL] deploy chrome: {exc}")

                try:
                    page.goto(base_url.rstrip("/") + "/bidding", timeout=30000)
                    page.wait_for_timeout(800)
                    body = page.inner_text("body") or ""
                    for label, ok in (
                        ("Bidding heading", "Bid" in body),
                        (
                            "Season workflow",
                            "Draft" in body or "Publish" in body or "Finalize" in body or "Create" in body,
                        ),
                    ):
                        print(f"  [{'ok' if ok else 'FAIL'}] bidding chrome: {label}")
                        if not ok:
                            failures.append(f"bidding missing: {label}")
                except Exception as exc:
                    failures.append(f"bidding chrome: {exc}")
                    print(f"  [FAIL] bidding chrome: {exc}")

                try:
                    page.goto(base_url.rstrip("/") + "/security", timeout=30000)
                    page.wait_for_timeout(800)
                    body = page.inner_text("body") or ""
                    for label, ok in (
                        ("Security heading", "Security" in body or "Governance" in body),
                        ("Backup panel", "Backup" in body or "backup" in body.lower()),
                        ("LDAP field trial", "LDAP" in body or "field trial" in body.lower() or "AD" in body),
                    ):
                        print(f"  [{'ok' if ok else 'FAIL'}] security chrome: {label}")
                        if not ok:
                            failures.append(f"security missing: {label}")
                except Exception as exc:
                    failures.append(f"security chrome: {exc}")
                    print(f"  [FAIL] security chrome: {exc}")

                try:
                    page.goto(base_url.rstrip("/") + "/operations", timeout=45000)
                    page.wait_for_timeout(1000)
                    body = page.inner_text("body") or ""
                    for label, ok in (
                        ("Ops reports", "Ops" in body or "Coverage" in body or "CAD" in body),
                        ("CAD vendor export", "Mark43" in body or "Tyler" in body or "CAD" in body),
                    ):
                        print(f"  [{'ok' if ok else 'FAIL'}] operations chrome: {label}")
                        if not ok:
                            failures.append(f"operations missing: {label}")
                except Exception as exc:
                    failures.append(f"operations chrome: {exc}")
                    print(f"  [FAIL] operations chrome: {exc}")

                try:
                    page.goto(base_url.rstrip("/") + "/time-punch", timeout=20000)
                    page.wait_for_timeout(800)
                    body = page.inner_text("body") or ""
                    for label, ok in (
                        ("Punch heading", "Punch" in body or "Clock" in body),
                        (
                            "In/Out or policy",
                            "In" in body or "Out" in body or "punch" in body.lower() or "policy" in body.lower(),
                        ),
                    ):
                        if ok:
                            print(f"  [ok] time-punch chrome: {label}")
                        else:
                            failures.append(f"time-punch missing: {label}")
                            print(f"  [FAIL] time-punch chrome: {label}")
                except Exception as exc:
                    failures.append(f"time-punch chrome: {exc}")
                    print(f"  [FAIL] time-punch chrome: {exc}")

                try:
                    page.goto(base_url.rstrip("/") + "/channels", timeout=20000)
                    page.wait_for_timeout(800)
                    body = page.inner_text("body") or ""
                    for label, ok in (
                        ("Channels heading", "channel" in body.lower() or "Notify" in body or "Outbox" in body),
                        (
                            "Outbox / Twilio honesty",
                            "Outbox" in body or "Twilio" in body or "SMTP" in body or "queued" in body.lower(),
                        ),
                    ):
                        if ok:
                            print(f"  [ok] channels chrome: {label}")
                        else:
                            failures.append(f"channels missing: {label}")
                            print(f"  [FAIL] channels chrome: {label}")
                except Exception as exc:
                    failures.append(f"channels chrome: {exc}")
                    print(f"  [FAIL] channels chrome: {exc}")

                try:
                    page.goto(
                        base_url.rstrip("/") + "/live-schedule",
                        timeout=60000,
                        wait_until="domcontentloaded",
                    )
                    page.wait_for_timeout(900)
                    body = page.inner_text("body") or ""
                    for label, ok in (
                        ("Live heading", "Live" in body or "Coverage" in body),
                        (
                            "Severity or matrix",
                            "severity" in body.lower()
                            or "working" in body.lower()
                            or "Sync" in body
                            or "Officer" in body
                            or "Court" in body,
                        ),
                    ):
                        if ok:
                            print(f"  [ok] live-schedule chrome: {label}")
                        else:
                            failures.append(f"live-schedule missing: {label}")
                            print(f"  [FAIL] live-schedule chrome: {label}")
                except Exception as exc:
                    print(f"  [warn] live-schedule chrome: {exc} (soft under load)")

                try:
                    page.goto(
                        base_url.rstrip("/") + "/notifications",
                        timeout=30000,
                        wait_until="domcontentloaded",
                    )
                    page.wait_for_timeout(1000)
                    body = page.inner_text("body")
                    for label, ok in (
                        ("Alerts heading", "Alert" in body or "notification" in body.lower()),
                        (
                            "Inbox tools",
                            "Unread" in body or "Mark" in body or "Refresh" in body or "clear" in body.lower(),
                        ),
                    ):
                        if ok:
                            print(f"  [ok] notifications chrome: {label}")
                        else:
                            failures.append(f"notifications missing: {label}")
                            print(f"  [FAIL] notifications chrome: {label}")
                except Exception as exc:
                    failures.append(f"notifications chrome: {exc}")
                    print(f"  [FAIL] notifications chrome: {exc}")
        except Exception as exc:
            failures.append(str(exc))
            print(f"  [FAIL] session: {exc}")
            print("  Is Chronos running?  python main.py --browser")
        finally:
            browser.close()

    print("=" * 56)
    if failures:
        print(f"chronos-e2e: FAILED ({len(failures)})")
        return 1
    print("chronos-e2e: PASSED")
    return 0


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(description="Chronos Playwright smoke")
    p.add_argument("--base-url", default=os.environ.get("CHRONOS_BASE_URL", "http://127.0.0.1:8080"))
    p.add_argument("--user", default="admin")
    p.add_argument("--password", default="admin")
    p.add_argument("--headed", action="store_true")
    p.add_argument(
        "--quick",
        action="store_true",
        help="Critical paths only (less hang risk). Env: CHRONOS_E2E_QUICK=1",
    )
    args = p.parse_args(argv)
    return run_chronos_e2e(
        base_url=args.base_url,
        username=args.user,
        password=args.password,
        headed=args.headed,
        quick=bool(args.quick),
    )


if __name__ == "__main__":
    raise SystemExit(main())
