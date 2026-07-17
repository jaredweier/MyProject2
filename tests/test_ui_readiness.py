"""Regression tests for supervisor-ready UI gates (catch false-positive smoke)."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestUiReadiness(unittest.TestCase):
    def test_brand_assets_exist(self):
        """Root placeholders exist for legacy CTk; agency uploads remain optional under photos/."""
        from paths import resource_path
        from photos import chronos_logo_path, department_logo_path, department_photo_path

        # Ship-safe placeholders (tiny generated assets) so headless loaders work.
        for name in ("logo.png", "team_photo.jpg"):
            path = resource_path(name)
            self.assertTrue(os.path.isfile(path), f"missing placeholder {name}: {path}")
            self.assertGreater(os.path.getsize(path), 0, f"empty placeholder {name}")

        # Agency brand APIs must not raise when dept uploads are absent.
        try:
            chronos_logo_path()
            department_logo_path()
            department_photo_path()
        except Exception as exc:
            self.fail(f"brand path APIs failed: {exc}")

        # Department seal/photo are optional (upload in Branding & Media).
        # Chronos product mark may exist as a small default under photos/.
        chronos = chronos_logo_path()
        if chronos is not None:
            self.assertTrue(os.path.isfile(chronos))

    def test_brand_images_load(self):
        from ui.assets import load_logo, load_logo_safe, load_team_photo, make_monogram_badge

        # Placeholders restore load_logo / load_team_photo for CTk paths.
        self.assertIsNotNone(load_logo((64, 64)), "load_logo returned None (need root logo.png placeholder)")
        self.assertIsNotNone(
            load_team_photo((200, 120), cover=True),
            "load_team_photo returned None (need root team_photo.jpg placeholder)",
        )
        # Safe path must never be None even if files go missing later.
        safe = load_logo_safe((48, 48), initials="PD")
        self.assertIsNotNone(safe, "load_logo_safe must return logo or monogram")
        mono = make_monogram_badge((40, 40), initials="CH")
        self.assertIsNotNone(mono, "monogram fallback must paint")

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
            timeout=180,
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
