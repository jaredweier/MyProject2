"""Unit tests for product-priority features (2026-07-16)."""

from __future__ import annotations

import unittest
from pathlib import Path


class NotifyTemplatesTests(unittest.TestCase):
    def test_format_templates(self):
        from logic.notify_channels import NOTIFY_TEMPLATES, format_notify_template

        self.assertIn("open_shift", NOTIFY_TEMPLATES)
        t = format_notify_template("open_shift", date="7/16/26", start="19:00", end="03:00", squad="A")
        self.assertIn("19:00", t["body"])
        self.assertTrue(t["subject"])

    def test_dispatch_no_channels(self):
        from logic.notify_channels import dispatch_channel_hooks

        r = dispatch_channel_hooks(subject="x", body="y")
        self.assertTrue(r.get("success"))
        self.assertIn("sms_sent", r)


class CallbackCalldownTests(unittest.TestCase):
    def test_calldown_and_export(self):
        from datetime import date

        from logic.callbacks import (
            export_callback_equity_csv,
            run_callback_calldown,
            sync_callback_rotation_from_roster,
        )

        sync_callback_rotation_from_roster()
        r = run_callback_calldown(date.today().isoformat(), max_offers=2, notify=False)
        self.assertIn("offers", r)
        ex = export_callback_equity_csv()
        self.assertTrue(ex.get("success"))
        self.assertTrue(Path(ex["path"]).is_file())


class CourtCalendarTests(unittest.TestCase):
    def test_list_board(self):
        from logic.court_calendar import court_calendar_summary, list_court_training_events

        b = list_court_training_events()
        self.assertTrue(b.get("success"))
        s = court_calendar_summary()
        self.assertTrue(s.get("success"))


class FlsaSplitTests(unittest.TestCase):
    def test_export_csv(self):
        from logic.labor_compliance import export_flsa_vs_contract_ot_csv

        r = export_flsa_vs_contract_ot_csv()
        self.assertTrue(r.get("success"))
        self.assertTrue(Path(r["path"]).is_file())


class ExtraDutyMarketplaceTests(unittest.TestCase):
    def test_marketplace_board(self):
        from logic.extra_duty import marketplace_board

        r = marketplace_board()
        self.assertTrue(r.get("success"))
        self.assertIn("open", r)


class CompareLengthsImportTests(unittest.TestCase):
    def test_import(self):
        from logic.scheduling_sim import compare_shift_length_scenarios

        self.assertTrue(callable(compare_shift_length_scenarios))


if __name__ == "__main__":
    unittest.main()
