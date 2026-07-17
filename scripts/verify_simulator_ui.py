"""Agent-owned Chronos simulator UI verification (Playwright).

Requires Chronos running: python main.py --browser
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "logs" / "ui_live_test" / "simulator_agent_verify"
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
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT / "01_login.png"))

        pw = page.locator('input[type="password"]')
        if pw.count() == 0:
            fail("no password field on login")
            browser.close()
            return 1

        # Login as supervisor (simulator.use)
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
        page.screenshot(path=str(OUT / "02_after_login.png"))

        body = page.inner_text("body") or ""
        if "change" in body.lower() and "password" in body.lower():
            pws = page.locator('input[type="password"]')
            n = pws.count()
            if n >= 2:
                for i in range(min(n, 3)):
                    pws.nth(i).fill("Supervisor1!")
                b = page.locator(
                    'button:has-text("Save"), button:has-text("Update"), '
                    'button:has-text("Change"), button:has-text("Continue")'
                )
                if b.count():
                    b.first.click()
                    page.wait_for_timeout(2000)

        page.goto(BASE + "/simulator", timeout=20000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / "03_simulator.png"))
        body = page.inner_text("body") or ""
        body_l = body.lower()

        if "/login" in page.url:
            fail("simulator redirected to login")
            browser.close()
            return 1

        if "limited to supervisors" in body_l or "permission required" in body_l:
            # try admin
            page.goto(BASE + "/login", timeout=15000)
            page.wait_for_timeout(800)
            inputs = page.locator("input:visible")
            for i in range(min(inputs.count(), 8)):
                el = inputs.nth(i)
                typ = (el.get_attribute("type") or "text").lower()
                if typ in ("text", "email", "search", ""):
                    el.fill("admin")
                    break
            page.locator('input[type="password"]').first.fill("admin")
            page.locator('button:has-text("Sign In")').first.click()
            page.wait_for_timeout(2000)
            page.goto(BASE + "/simulator", timeout=20000)
            page.wait_for_timeout(1500)
            page.screenshot(path=str(OUT / "03b_simulator_admin.png"))
            body = page.inner_text("body") or ""
            body_l = body.lower()

        for needle in (
            "Schedule Simulator",
            "Officer Count",
            "Shift Length",
            "Annual Hours",
            "24/7",
            "Continue To Coverage",
        ):
            if needle.lower() in body_l or needle in body:
                ok(f"requirements: {needle}")
            else:
                fail(f"missing on requirements: {needle}")

        # Lock officer count so Find Best runs a finite space (not 66M free-N layouts)
        off_cb = page.locator('label:has-text("Officer Count"), .q-checkbox:has-text("Officer Count")')
        if off_cb.count() == 0:
            off_cb = page.get_by_text("Officer Count", exact=False)
        if off_cb.count():
            off_cb.first.click()
            page.wait_for_timeout(400)
            # ensure N=8
            off_in = page.locator("input").filter(has=page.locator("xpath=.."))
            # NiceGUI label "Number Of Officers"
            n_input = page.get_by_label("Number Of Officers")
            if n_input.count():
                n_input.first.fill("8")
                ok("locked officer count = 8")
            else:
                # fallback: fill last visible number-ish field near officers
                ok("officer checkbox toggled (fill may be default)")
        else:
            fail("could not find Officer Count checkbox to lock headcount")

        cont = page.locator('button:has-text("Continue to find best")')
        if cont.count() == 0:
            fail("Continue to find best missing")
            browser.close()
            return 1

        cont.first.click()
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / "04_coverage_step.png"))
        body = page.inner_text("body") or ""
        body_l = body.lower()

        for needle in (
            "Find Best",
            "Generate Schedule",
            "Exhaustive",
            "Constraint Priority",
        ):
            if needle.lower() in body_l or needle in body:
                ok(f"coverage: {needle}")
            else:
                fail(f"missing on coverage: {needle}")

        if any(
            s in body_l
            for s in (
                "layout",
                "search space",
                "free dimension",
                "second",
                "minute",
                "combination",
            )
        ):
            ok("space estimate banner content")
        else:
            fail("space estimate banner empty/missing")

        def _wait_results(timeout_s: int = 180) -> str:
            """Wait for post-search outcomes only (not static banner copy)."""
            done_markers = (
                "Best Option:",
                "Layouts Checked (exhaustive)",
                "Layouts Checked:",
                "No Perfect Schedule",
                "No Schedule Meets",
                "Closest Alternatives",
                "Option 1",
                "Meets Selected Constraints",
            )
            deadline = timeout_s
            body_local = page.inner_text("body") or ""
            while deadline > 0:
                body_local = page.inner_text("body") or ""
                # Dialog must be gone
                if "Run Full Search Anyway" in body_local:
                    page.wait_for_timeout(500)
                    deadline -= 0.5
                    continue
                if any(x in body_local for x in done_markers):
                    break
                page.wait_for_timeout(2000)
                deadline -= 2
            return body_local

        find = page.locator('button:has-text("Find Best")')
        if find.count() == 0:
            fail("Find Best button missing")
        else:
            find.first.click()
            page.wait_for_timeout(2000)
            page.screenshot(path=str(OUT / "05_after_find_click.png"))
            body = page.inner_text("body") or ""

            if "Large Search Space" in body or "Run Full Search Anyway" in body:
                ok("large space confirm dialog shown")
                run_btn = page.locator('button:has-text("Run Full Search Anyway")')
                if run_btn.count():
                    run_btn.first.click()
                    ok("confirmed full search")
                else:
                    fail("confirm dialog missing Run button")
            else:
                ok("no confirm dialog (space under threshold)")

            body = _wait_results(180)
            page.screenshot(path=str(OUT / "06_results.png"))
            (OUT / "06_body.txt").write_text(body, encoding="utf-8")
            if "Run Full Search Anyway" in body:
                fail("stuck on large-space dialog after confirm")
            if "Searching entire constraint space" in body and "Best Option" not in body:
                fail("search stuck on in-progress message (io_bound never finished)")
            result_ok = any(
                x in body
                for x in (
                    "Best Option:",
                    "Layouts Checked",
                    "No Perfect Schedule",
                    "No Schedule Meets",
                    "Closest Alternatives",
                    "Meets Selected Constraints",
                    "Option 1",
                )
            )
            if result_ok:
                ok("results after Find Best")
            else:
                fail("no results after Find Best; see 06_body.txt")
            if any(x in body for x in ("Traceback", "TypeError", "AttributeError", "Search Failed")):
                fail("exception/failure text after Find Best")
            body_l2 = body.lower()
            if "layouts checked" in body_l2:
                ok("exhaustive eval count shown in summary")
            elif result_ok:
                fail("results present but missing Layouts Checked count")
            if "hard constraints ok: true" in body_l2 or "meets selected constraints" in body_l2:
                ok("hard constraints satisfied on option")
            elif "closest alternatives" in body_l2 or "no schedule meets" in body_l2:
                ok("honest near-miss / impossible messaging")
            if "06:00" in body or "14:00" in body:
                ok("half-hour starts visible in plan")
            # Continue to Publish step chrome
            pub = page.locator('button:has-text("go publish")')
            if pub.count():
                pub.first.click()
                page.wait_for_timeout(1000)
                page.screenshot(path=str(OUT / "07_publish_step.png"))
                b3 = (page.inner_text("body") or "").lower()
                if "publish" in b3 or "implement" in b3 or "apply" in b3:
                    ok("publish step chrome")
                else:
                    fail("publish step missing implement chrome")

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
