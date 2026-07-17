"""Product complete pack — parity wires + LE residual depth."""

from __future__ import annotations

import unittest
from datetime import date

from tests.helpers import get_any_officer, test_database


class ProductCompletePackTests(unittest.TestCase):
    def test_run_smoke(self):
        with test_database():
            from logic.product_complete_pack import run_product_complete_smoke

            r = run_product_complete_smoke()
            self.assertTrue(r.get("success"), r)

    def test_build_pattern_preview(self):
        with test_database():
            from logic.product_complete_pack import apply_rotation_pattern_setting, preview_rotation_pattern
            from logic.rotation_patterns import build_pattern

            p = build_pattern("6-2,5-3", style="rotating")
            self.assertGreater(p.cycle_length, 0)
            prev = preview_rotation_pattern("6-2,5-3", style="rotating")
            self.assertTrue(prev.get("success"), prev)
            self.assertIn("annual_hours", prev)
            saved = apply_rotation_pattern_setting("6-2,5-3", style="rotating")
            self.assertTrue(saved.get("success"), saved)

    def test_day_coverage_and_windows(self):
        with test_database():
            from logic.coverage_timeline import evaluate_day_coverage
            from logic.coverage_windows_store import list_coverage_windows
            from logic.product_complete_pack import live_day_coverage_report, save_coverage_windows_ui

            cov = live_day_coverage_report(date(2026, 7, 10))
            self.assertTrue(cov.get("success"), cov)
            # Direct evaluate_day_coverage call
            r = evaluate_day_coverage([], date(2026, 7, 10), min_247=0)
            self.assertIn("ok", r)
            existing = list_coverage_windows() or []
            saved = save_coverage_windows_ui(existing, min_247=1)
            self.assertTrue(saved.get("success"), saved)

    def test_off_duty_policy_and_plan_bump(self):
        with test_database():
            from logic.bump_off_duty import load_off_duty_bump_policy, save_off_duty_bump_policy
            from logic.bump_optimizer import plan_bump_chain
            from logic.product_complete_pack import plan_bump_chain_report

            pol = load_off_duty_bump_policy()
            self.assertIsNotNone(pol)
            r = save_off_duty_bump_policy({"allow_off_duty": False, "same_squad_only": True})
            self.assertTrue(r.get("success"), r)
            off = get_any_officer()
            chain, err = plan_bump_chain(
                int(off["id"]),
                "2026-07-10",
                off.get("squad") or "A",
                off.get("shift_start") or "06:00",
            )
            self.assertIsInstance(chain, list)
            report = plan_bump_chain_report(
                int(off["id"]),
                "2026-07-10",
                off.get("squad") or "A",
                off.get("shift_start") or "06:00",
            )
            self.assertIn("text", report)

    def test_court_holdover_ot_election(self):
        with test_database():
            from logic.product_complete_pack import (
                get_court_min_hours,
                get_default_ot_election,
                get_holdover_reason_codes,
                save_holdover_reason_codes,
                set_court_min_hours,
                set_default_ot_election,
            )

            self.assertTrue(set_court_min_hours(3).get("success"))
            self.assertEqual(get_court_min_hours(), 3.0)
            codes = ["Holdover end-of-shift", "Court appearance", "Other"]
            self.assertTrue(save_holdover_reason_codes(codes).get("success"))
            self.assertEqual(get_holdover_reason_codes()[:3], codes)
            self.assertTrue(set_default_ot_election("comp").get("success"))
            self.assertEqual(get_default_ot_election(), "comp")

    def test_notify_live_and_prove_honest(self):
        with test_database():
            from logic.notify_queue import prove_notify_paths
            from logic.product_complete_pack import live_notify_send_test

            proof = prove_notify_paths()
            self.assertTrue(proof.get("success"), proof)
            if proof.get("live_send_proved") and not proof.get("live_any_capable"):
                self.fail("live_send_proved without transport")
            live = live_notify_send_test(email="proof@example.invalid", phone="")
            self.assertTrue(live.get("success"), live)
            # Without real SMTP, must not claim live proved unless transport ready
            if live.get("live_send_proved") and not live.get("live_email_capable"):
                self.fail("live_send_proved honesty bug")

    def test_giveaway_and_cad(self):
        with test_database():
            from logic.cad_rms_export import export_duty_roster_for_cad
            from logic.product_complete_pack import giveaway_shift_as_open, import_cad_rms_duty_json

            off = get_any_officer()
            g = giveaway_shift_as_open(int(off["id"]), date(2026, 7, 12), notes="unit giveaway")
            self.assertTrue(g.get("success"), g)
            cad = export_duty_roster_for_cad(as_of=date(2026, 7, 10), days=1)
            self.assertTrue(cad.get("success"), cad)
            dry = import_cad_rms_duty_json(cad.get("json_path"), dry_run=True)
            self.assertTrue(dry.get("success"), dry)

    def test_flsa_meter_and_hard_pack(self):
        with test_database():
            from logic.product_complete_pack import (
                cert_inventory_health,
                flsa_meter_for_officer,
                hard_pack_headcount_message,
            )

            off = get_any_officer()
            m = flsa_meter_for_officer(int(off["id"]), reference=date(2026, 7, 10))
            self.assertTrue(m.get("success"), m)
            h = hard_pack_headcount_message(7)
            self.assertTrue(h.get("success"))
            self.assertEqual(h.get("recommended_min"), 8)
            c = cert_inventory_health()
            self.assertTrue(c.get("success"))

    def test_gui_parity_symbols_referenced(self):
        """Thin parity symbols must appear as words in gui/ (parity-audit)."""
        from pathlib import Path

        root = Path(__file__).resolve().parents[1] / "gui"
        text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in root.rglob("*.py"))
        for name in (
            "plan_bump_chain",
            "load_off_duty_bump_policy",
            "evaluate_day_coverage",
            "save_coverage_windows",
            "build_pattern",
        ):
            self.assertIn(name, text, f"{name} not referenced in gui/")


if __name__ == "__main__":
    unittest.main()
