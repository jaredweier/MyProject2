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
            # Smoke paths
            for path in (
                "/",
                "/roster",
                "/time-off",
                "/my-schedule",
                "/timecards",
                "/payroll",
                "/notifications",
            ):
                try:
                    page.goto(base_url.rstrip("/") + path, timeout=20000)
                    page.wait_for_timeout(600)
                    if "/login" in page.url:
                        failures.append(f"{path}: redirected to login")
                        print(f"  [FAIL] {path}: still on login")
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
                    ("US date hint", "M/D" in body or "m/d" in body.lower() or "7/9" in body),
                ]
                for label, ok in checks:
                    if ok:
                        print(f"  [ok] time-off chrome: {label}")
                    else:
                        # Stale server may still show EU hint — warn only for date hint
                        if label == "US date hint":
                            print(f"  [warn] time-off chrome: {label} (restart Chronos if DATE_INPUT_HINT stale)")
                        else:
                            failures.append(f"time-off missing: {label}")
                            print(f"  [FAIL] time-off chrome: {label}")
            except Exception as exc:
                failures.append(f"time-off chrome: {exc}")
                print(f"  [FAIL] time-off chrome: {exc}")

            # Payroll / timecards chrome
            try:
                page.goto(base_url.rstrip("/") + "/timecards", timeout=20000)
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
                page.goto(base_url.rstrip("/") + "/payroll", timeout=20000)
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
                page.goto(base_url.rstrip("/") + "/notifications", timeout=20000)
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
