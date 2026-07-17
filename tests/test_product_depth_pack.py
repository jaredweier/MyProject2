"""Product depth pack — ops desk, policy, callout, publish, accruals, payroll exceptions, sim."""

from __future__ import annotations

import unittest
from datetime import date

from tests.helpers import get_any_officer, test_database


class ProductDepthPackTests(unittest.TestCase):
    def test_policy_pack_export_import_roundtrip(self):
        with test_database():
            from logic.policy_pack import collect_policy_pack, export_policy_pack, import_policy_pack

            pack = collect_policy_pack(label="unit-test")
            self.assertEqual(pack.get("version"), 1)
            self.assertIn("settings", pack)
            r = export_policy_pack(label="unit-test")
            self.assertTrue(r.get("success"), r)
            self.assertTrue(r.get("path"))
            dry = import_policy_pack(pack, dry_run=True, apply_staffing=False)
            self.assertTrue(dry.get("success"), dry)

    def test_ops_desk_board_and_manual_queue(self):
        with test_database():
            from logic.ops_desk import get_ops_desk_board, list_manual_review_queue

            board = get_ops_desk_board(reference=date(2026, 7, 10))
            self.assertTrue(board.get("success"), board)
            self.assertIn("kpi", board)
            q = list_manual_review_queue()
            self.assertTrue(q.get("success"))

    def test_callout_ladder_builds(self):
        with test_database():
            from logic.callout_desk import build_callout_ladder, get_ot_equity_sort_enabled

            oid = int(get_any_officer()["id"])
            ladder = build_callout_ladder(oid, "2026-07-10", reason="Sick")
            self.assertTrue(ladder.get("success"), ladder)
            self.assertIn("candidates", ladder)
            self.assertIsInstance(get_ot_equity_sort_enabled(), bool)

    def test_publish_preflight(self):
        with test_database():
            from logic.publish_gates import live_coverage_severity_for_window, preflight_publish_base_schedule

            pre = preflight_publish_base_schedule(2026, 7)
            self.assertTrue(pre.get("success"), pre)
            self.assertIn("manual_count", pre)
            sev = live_coverage_severity_for_window("2026-07-01", "2026-07-07")
            self.assertTrue(sev.get("success"), sev)
            self.assertGreaterEqual(len(sev.get("days") or []), 1)

    def test_leave_accruals_balances(self):
        with test_database():
            from logic.leave_accruals import get_officer_accrual_balances, list_roster_accrual_balances

            oid = int(get_any_officer()["id"])
            bal = get_officer_accrual_balances(oid, as_of=date(2026, 7, 1))
            self.assertTrue(bal.get("success"), bal)
            roster = list_roster_accrual_balances(as_of=date(2026, 7, 1))
            self.assertTrue(roster.get("success"), roster)

    def test_payroll_exceptions_and_flsa_banners(self):
        with test_database():
            from logic.payroll_exceptions import export_pay_pack, flsa_period_banners, list_payroll_exceptions

            banners = flsa_period_banners(reference=date(2026, 7, 10))
            self.assertIsInstance(banners, list)
            ex = list_payroll_exceptions(reference=date(2026, 7, 10))
            self.assertTrue(ex.get("success"), ex)
            pack = export_pay_pack(reference=date(2026, 7, 10))
            self.assertIn("message", pack)

    def test_sim_product_plain_explain(self):
        with test_database():
            from logic.sim_product_pack import (
                fairness_report_full,
                import_live_department_constraints,
                plain_english_staffing_explain,
            )

            exp = plain_english_staffing_explain(
                {"success": True, "best": {"hard_constraints_ok": True, "summary": "ok"}}
            )
            self.assertTrue(exp.get("success"), exp)
            self.assertTrue(exp.get("lines"))
            fair = fairness_report_full({})
            self.assertTrue(fair.get("success"))
            live = import_live_department_constraints()
            self.assertTrue(live.get("success"), live)

    def test_diagnose_missing_request(self):
        with test_database():
            from logic.ops_desk import diagnose_manual_review

            d = diagnose_manual_review(999999)
            self.assertFalse(d.get("success"))

    def test_notify_prove_and_sensitivity_cheap(self):
        with test_database():
            import time

            from logic.notify_queue import process_notify_outbox, prove_notify_paths
            from logic.sim_product_pack import sensitivity_headcount

            proof = prove_notify_paths()
            self.assertTrue(proof.get("success"), proof)
            self.assertFalse(proof.get("live_send_proved") and not proof.get("live_any_capable"))
            dry = process_notify_outbox(limit=5, dry_run=True)
            self.assertEqual(int(dry.get("sent") or 0), 0)
            self.assertTrue(dry.get("dry_run"))
            t0 = time.time()
            sens = sensitivity_headcount(
                {
                    "num_officers": 8,
                    "_cached_result": {
                        "success": True,
                        "best": {"hard_constraints_ok": True, "summary": "ok"},
                    },
                },
                deep=False,
            )
            self.assertTrue(sens.get("success"), sens)
            self.assertEqual(sens.get("mode"), "cheap")
            self.assertLess(time.time() - t0, 8.0)

    def test_manual_review_resolve_reject_path(self):
        with test_database():
            from database import get_connection
            from logic.ops_desk import diagnose_manual_review, resolve_manual_review
            from logic.requests import create_day_off_request
            from tests.helpers import working_date_for_squad

            off = get_any_officer(squad="A")
            d = working_date_for_squad("A")
            cr = create_day_off_request(int(off["id"]), d.isoformat(), "Sick", notes="depth pack")
            self.assertTrue(cr.get("success"), cr)
            rid = int(cr["request_id"])
            # Force manual review status
            conn = get_connection()
            conn.execute(
                "UPDATE day_off_requests SET status = 'Pending Manual Review', admin_notes = ? WHERE id = ?",
                ("cascade incomplete", rid),
            )
            conn.commit()
            conn.close()
            diag = diagnose_manual_review(rid)
            self.assertTrue(diag.get("success"), diag)
            self.assertTrue(diag.get("why_lines"))
            r = resolve_manual_review(rid, "reject", admin_notes="ops desk unit", user_id=1)
            self.assertTrue(r.get("success"), r)


if __name__ == "__main__":
    unittest.main()
