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
import sys
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def playwright_available() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


def run_chronos_e2e(
    *,
    base_url: str = "http://127.0.0.1:8080",
    username: str = "admin",
    password: str = "admin",
    headed: bool = False,
) -> int:
    print("Chronos E2E (Playwright optional)")
    print("=" * 56)
    if not playwright_available():
        print("  [SKIP] playwright not installed")
        print("  pip install playwright && playwright install chromium")
        print("  Then: python dev.py chronos-e2e")
        print("  Docs: https://playwright.dev/python/docs/intro")
        print("  Free fallback: python dev.py ui-review && python dev.py ui-smoke")
        return 0

    from playwright.sync_api import sync_playwright

    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        page = browser.new_page()
        try:
            page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(800)
            # Login form — Chronos uses labeled text + password fields
            pass_sel = 'input[type="password"]'
            if page.locator(pass_sel).count() > 0:
                # Prefer visible text inputs (username); avoid filling password twice
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
                # Prefer explicit Sign In
                btn = page.locator('button:has-text("Sign In")')
                if btn.count() == 0:
                    btn = page.locator('button:has-text("Sign"), button:has-text("Log"), button[type="submit"]')
                btn.first.click()
                page.wait_for_timeout(2000)
                # Wait until we leave /login when possible
                try:
                    page.wait_for_url(lambda u: "/login" not in u, timeout=8000)
                except Exception:
                    pass
            # Smoke paths — full Chronos nav (primary product surface)
            for path in (
                "/",
                "/notifications",
                "/my-schedule",
                "/monthly-schedule",
                "/live-schedule",
                "/time-off",
                "/open-shifts",
                "/bidding",
                "/callbacks",
                "/availability",
                "/roster",
                "/certs",
                "/timecards",
                "/payroll",
                "/simulator",
                "/operations",
                "/media",
                "/security",
                "/access",
            ):
                try:
                    page.goto(base_url.rstrip("/") + path, timeout=20000)
                    page.wait_for_timeout(600)
                    body = page.inner_text("body") or ""
                    if "/login" in page.url:
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
                    failures.append(f"{path}: {exc}")
                    print(f"  [FAIL] {path}: {exc}")

            # Leave page chrome (admin/supervisor after login) — use visible text
            try:
                page.goto(base_url.rstrip("/") + "/time-off", timeout=20000)
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
                        order_btn.first.wait_for(state="visible", timeout=12000)
                    except Exception:
                        page.wait_for_timeout(500)
                    dlg_checks = [
                        (
                            "Approve dialog title",
                            dlg_card.count() > 0
                            or page.get_by_text("Approve —", exact=False).count() > 0
                            or cover_lbl.count() > 0,
                        ),
                        ("Order in action", order_btn.count() > 0),
                        ("Volunteer action", vol_btn.count() > 0),
                        ("Cover officer select", cover_lbl.count() > 0 or dlg_card.count() > 0),
                    ]
                    dlg_ok = True
                    for label, ok in dlg_checks:
                        if ok:
                            print(f"  [ok] leave approve dlg: {label}")
                        else:
                            dlg_ok = False
                            failures.append(f"leave approve dlg missing: {label}")
                            print(f"  [FAIL] leave approve dlg: {label}")
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
                    timeout=30000,
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
                    timeout=30000,
                    wait_until="domcontentloaded",
                )
                page.wait_for_timeout(1000)
                body = page.inner_text("body")
                for label, ok in (
                    ("Payroll heading", "Payroll" in body),
                    ("Lock panel", "Lock" in body or "pay period" in body.lower()),
                ):
                    if ok:
                        print(f"  [ok] payroll chrome: {label}")
                    else:
                        failures.append(f"payroll missing: {label}")
                        print(f"  [FAIL] payroll chrome: {label}")
            except Exception as exc:
                failures.append(f"finance chrome: {exc}")
                print(f"  [FAIL] finance chrome: {exc}")

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
                    ("Inbox tools", "Unread" in body or "Mark" in body or "Refresh" in body or "clear" in body.lower()),
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
    args = p.parse_args(argv)
    return run_chronos_e2e(
        base_url=args.base_url,
        username=args.user,
        password=args.password,
        headed=args.headed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
