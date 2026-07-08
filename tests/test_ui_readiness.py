"""Regression tests for supervisor-ready UI gates (catch false-positive smoke)."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestUiReadiness(unittest.TestCase):
    def test_brand_assets_exist(self):
        from paths import resource_path

        for name in ("logo.png", "team_photo.jpg"):
            path = resource_path(name)
            self.assertTrue(os.path.isfile(path), f"missing {name}: {path}")

    def test_brand_images_load(self):
        from ui.assets import load_logo, load_team_photo

        self.assertIsNotNone(load_logo((64, 64)), "load_logo returned None")
        self.assertIsNotNone(
            load_team_photo((200, 120), cover=True),
            "load_team_photo returned None",
        )

    def test_title_case_preserves_possessive_s(self):
        from ui.helpers import title_case_ui

        result = title_case_ui("wisconsin's oldest courthouse")
        self.assertIn("'s", result)
        self.assertNotIn("'S", result)

    def test_supervisor_simulator_permission(self):
        from permissions import role_has_permission

        self.assertTrue(role_has_permission("Supervisor", "simulator.use"))
        self.assertTrue(role_has_permission("Administration", "simulator.use"))
        self.assertFalse(role_has_permission("Officer", "simulator.use"))

    def test_login_probe_subprocess(self):
        """Login must paint brand images and complete headless shell login."""
        env = os.environ.copy()
        env["SCHEDULER_UI_TEST"] = "1"
        script = os.path.join(ROOT, "scripts", "ui_login_probe.py")
        proc = subprocess.run(
            [sys.executable, script],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=90,
        )
        combined = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(proc.returncode, 0, f"login probe failed:\n{combined[-4000:]}")
        self.assertIn("OK:", combined)

    def test_ui_smoke_subprocess_completes(self):
        """ui-smoke must finish (no hang) and return 0 — catches login handler storms."""
        env = os.environ.copy()
        env["SCHEDULER_UI_TEST"] = "1"
        script = os.path.join(ROOT, "scripts", "ui_smoke_test.py")
        proc = subprocess.run(
            [sys.executable, script],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        combined = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(
            proc.returncode,
            0,
            f"ui-smoke failed (exit {proc.returncode}):\n{combined[-8000:]}",
        )
        self.assertIn("ALL PASSED", combined)


if __name__ == "__main__":
    unittest.main()
