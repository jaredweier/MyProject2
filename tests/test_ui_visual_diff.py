"""Tests for scripts/ui_visual_diff.py."""

import os
import tempfile
import unittest

from PIL import Image

from scripts.ui_visual_diff import _filter_quick, _is_quick_shot, run_ui_visual_diff


class UiVisualDiffTests(unittest.TestCase):
    def test_quick_filter_nav_only(self):
        names = [
            "01_shell_admin_login.png",
            "15_nav_show_page_users.png",
            "16_shell_refresh_all.png",
            "99_other.png",
        ]
        quick = _filter_quick(names)
        self.assertEqual(quick, names[:2])
        self.assertTrue(_is_quick_shot("02_nav_show_page_dashboard.png"))
        self.assertFalse(_is_quick_shot("20_dashboard_quick_actions.png"))

    def test_no_baseline_reports_update_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            Image.new("RGB", (10, 10), color=(1, 2, 3)).save(os.path.join(tmp, "01_test.png"))
            code = run_ui_visual_diff(current_dir=tmp, update_baseline=False)
            self.assertEqual(code, 0)

    def test_identical_images_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline_root = os.path.join(tmp, "baseline")
            os.makedirs(baseline_root, exist_ok=True)
            path = os.path.join(tmp, "shot.png")
            Image.new("RGB", (20, 20), color=(10, 20, 30)).save(path)
            import scripts.ui_visual_diff as mod

            old = mod.BASELINE_DIR
            try:
                mod.BASELINE_DIR = baseline_root
                Image.new("RGB", (20, 20), color=(10, 20, 30)).save(os.path.join(baseline_root, "shot.png"))
                code = run_ui_visual_diff(current_dir=tmp, verbose=True)
                self.assertEqual(code, 0)
            finally:
                mod.BASELINE_DIR = old


if __name__ == "__main__":
    unittest.main()
