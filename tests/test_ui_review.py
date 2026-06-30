"""Tests for scripts/ui_aesthetics_review.py."""

import json
import os
import unittest

from scripts.ui_aesthetics_review import run_ui_aesthetics_review


class UiAestheticsReviewTests(unittest.TestCase):
    def test_review_runs_and_writes_report(self):
        code = run_ui_aesthetics_review(
            strict=False,
            include_screenshots=False,
            verbose=False,
        )
        self.assertEqual(code, 0)

        log_root = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "logs",
            "ui_review",
        )
        runs = sorted(d for d in os.listdir(log_root) if os.path.isdir(os.path.join(log_root, d)))
        self.assertTrue(runs)
        latest = os.path.join(log_root, runs[-1])
        json_path = os.path.join(latest, "report.json")
        md_path = os.path.join(latest, "report.md")
        self.assertTrue(os.path.isfile(json_path))
        self.assertTrue(os.path.isfile(md_path))
        with open(json_path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertGreater(data["ui_files_scanned"], 10)
        self.assertGreater(data["strings_found"], 100)
        self.assertIn("findings", data)


if __name__ == "__main__":
    unittest.main()
