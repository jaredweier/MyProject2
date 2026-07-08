"""Headless UI smoke — real login path, every page, callback errors fail the gate."""

from __future__ import annotations

import os
import subprocess
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ["SCHEDULER_UI_TEST"] = "1"


def _run_role_subprocess(username: str, password: str, role_label: str) -> str | None:
    env = os.environ.copy()
    env["SCHEDULER_UI_TEST"] = "1"
    script = os.path.join(ROOT, "scripts", "ui_smoke_role.py")
    proc = subprocess.run(
        [
            sys.executable,
            script,
            "--username",
            username,
            "--password",
            password,
            "--role-label",
            role_label,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if proc.returncode == 0:
        return None
    detail = (proc.stdout or "") + (proc.stderr or "")
    return detail.strip() or f"exit {proc.returncode}"


def _check_role_nav_permissions(errors: list[str]) -> None:
    from permissions import role_has_permission

    if not role_has_permission("Supervisor", "simulator.use"):
        errors.append("Supervisor missing simulator.use permission")
    if not role_has_permission("Administration", "simulator.use"):
        errors.append("Administration missing simulator.use permission")
    if role_has_permission("Officer", "simulator.use"):
        errors.append("Officer must not have simulator.use permission")


def run_ui_smoke() -> int:
    errors: list[str] = []

    from scripts.ui_test_helpers import assert_brand_assets

    assert_brand_assets(errors)
    _check_role_nav_permissions(errors)

    try:
        from scripts.ui_login_probe import main as login_probe_main

        if login_probe_main() != 0:
            errors.append("login probe failed (photos or post-login shell)")
    except Exception:
        errors.append(f"login probe:\n{traceback.format_exc()}")

    # Full Tk shell exercise once (fresh process). Role nav matrix checked above without extra Tk roots.
    try:
        err = _run_role_subprocess("admin", "admin", "Administration")
        if err:
            errors.append(f"Administration shell:\n{err}")
    except subprocess.TimeoutExpired:
        errors.append("Administration: timed out after 90s (likely UI hang)")

    try:
        from ui.branding import get_department_branding

        branding = get_department_branding()
        if not branding.get("name"):
            errors.append("department name empty")
        tagline = branding.get("tagline", "")
        if "Wisconsin'S" in tagline:
            errors.append(f"tagline has wrong possessive casing: {tagline!r}")
    except Exception:
        errors.append(f"branding check:\n{traceback.format_exc()}")

    print("Dodgeville PD Scheduler — UI smoke")
    print("-" * 40)
    if errors:
        for err in errors:
            print(f"  [FAIL] {err}")
        print("-" * 40)
        print(f"ui smoke: {len(errors)} FAILURE(S)")
        return 1

    print("  [ok] brand assets on disk")
    print("  [ok] admin shell built and all pages visited")
    print("  [ok] supervisor/admin simulator permission; officer denied")
    print("  [ok] no Tk callback errors")
    print("-" * 40)
    print("ui smoke: ALL PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_ui_smoke())
