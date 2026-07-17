"""Fast readiness gate — catches failures that imports/audit miss (UI probe + core invariants)."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _run_login_probe() -> int:
    script = os.path.join(ROOT, "scripts", "ui_login_probe.py")
    env = os.environ.copy()
    env["SCHEDULER_UI_TEST"] = "1"
    result = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=150,
    )
    if result.returncode != 0:
        combined = (result.stdout or "") + (result.stderr or "")
        print(combined[-4000:], file=sys.stderr)
    return result.returncode


def _run_readiness_unittests() -> int:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for case in (
        "tests.test_users_security.UserSecurityTests.test_seed_users_require_password_change",
        "tests.test_tier2.Tier2FeatureTests.test_parse_bids_due_datetime_formats",
        "tests.test_three_brains_boundary",
    ):
        loaded = loader.loadTestsFromName(case)
        suite.addTests(loaded)
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


def run_readiness_check() -> int:
    print("Dodgeville PD Scheduler — readiness-check")
    print("=" * 60)
    failed: list[str] = []

    print("\n>>> ui-login-probe", flush=True)
    if _run_login_probe() != 0:
        failed.append("ui-login-probe")

    print("\n>>> readiness-unittests", flush=True)
    if _run_readiness_unittests() != 0:
        failed.append("readiness-unittests")

    print("\n" + "=" * 60)
    if failed:
        print(f"readiness-check: FAILED — {', '.join(failed)}")
        return 1
    print("readiness-check: ALL PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_readiness_check())
