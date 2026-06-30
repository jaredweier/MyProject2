"""Tests for read_guard."""

import unittest

from scripts.read_guard import check_read, known_large_ui_files


class ReadGuardTests(unittest.TestCase):
    def test_block_full_project_code(self):
        r = check_read("docs/FULL_PROJECT_CODE.txt")
        self.assertEqual(r.action, "deny")

    def test_block_png(self):
        r = check_read("tests/ui_snapshots/baseline/foo.png")
        self.assertEqual(r.action, "deny")

    def test_allow_config(self):
        r = check_read("config.py")
        self.assertEqual(r.action, "allow")

    def test_ask_large_payroll_ui(self):
        r = check_read("ui/payroll_pages.py")
        self.assertEqual(r.action, "ask")

    def test_known_large_ui_nonempty(self):
        large = known_large_ui_files()
        self.assertTrue(any("payroll_pages" in p for p, _ in large))


if __name__ == "__main__":
    unittest.main()
