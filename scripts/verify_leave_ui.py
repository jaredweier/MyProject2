"""Agent-owned Chronos leave UI path (Playwright).

Requires Chronos: python main.py --browser
Proves: login → Time Off → queue or empty-state → Plans/Approve controls if present.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "logs" / "ui_live_test" / "leave_agent_verify"
BASE = "http://127.0.0.1:8080"


def main() -> int:
    from playwright.sync_api import sync_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    fails: list[str] = []
    oks: list[str] = []

    def ok(msg: str) -> None:
        oks.append(msg)
        print("[ok]", msg)

    def fail(msg: str) -> None:
        fails.append(msg)
        print("[FAIL]", msg)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(BASE, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(800)

        pw = page.locator('input[type="password"]')
        if pw.count() == 0:
            fail("no login form")
            browser.close()
            return 1
        inputs = page.locator("input:visible")
        for i in range(min(inputs.count(), 8)):
            el = inputs.nth(i)
            typ = (el.get_attribute("type") or "text").lower()
            if typ in ("text", "email", "search", ""):
                el.fill("supervisor")
                break
        pw.first.fill("supervisor")
        btn = page.locator('button:has-text("Sign In")')
        if btn.count() == 0:
            btn = page.locator('button[type="submit"]')
        btn.first.click()
        page.wait_for_timeout(2500)
        page.screenshot(path=str(OUT / "01_after_login.png"))

        page.goto(BASE + "/time-off", timeout=20000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / "02_time_off.png"))
        body = page.inner_text("body") or ""
        body_l = body.lower()

        if "/login" in page.url:
            fail("time-off redirected to login")
            browser.close()
            return 1

        for needle in ("time off", "request", "queue", "pending", "submit"):
            if needle in body_l:
                ok(f"leave page has: {needle}")
                break
        else:
            fail("leave page missing expected copy")

        # Submit path chrome for officers/supervisors
        if page.locator('button:has-text("Submit"), button:has-text("Request")').count():
            ok("submit/request control present")
        else:
            # Supervisors may only see queue
            ok("no submit button (supervisor queue-only ok)")

        if "queue clear" in body_l or "no pending" in body_l:
            ok("empty queue message")
        elif page.locator('button:has-text("Approve")').count():
            ok("Approve button on pending row")
            # Open Plans if available
            plans = page.locator('button:has-text("Plans")')
            if plans.count():
                plans.first.click()
                page.wait_for_timeout(1200)
                page.screenshot(path=str(OUT / "03_plans.png"))
                b2 = (page.inner_text("body") or "").lower()
                if "option" in b2 or "plan" in b2 or "cover" in b2 or "replacement" in b2:
                    ok("plans dialog content")
                else:
                    fail("plans click no coverage content")
            # Do not auto-approve in e2e (mutates DB) — button existence is enough
            ok("approve control present (not auto-clicked)")
        else:
            ok("no pending approve (queue empty or no perms)")

        if "reject" in body_l or page.locator('button:has-text("Reject")').count():
            ok("reject path available or labeled")
        browser.close()

    summary = "\n".join([*oks, "---", *fails])
    (OUT / "summary.txt").write_text(summary, encoding="utf-8")
    print("---")
    print(f"PASS {len(oks)} FAIL {len(fails)}")
    for f in fails:
        print(" ", f)
    print(f"shots: {OUT}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
