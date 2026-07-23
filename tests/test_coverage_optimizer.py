"""Coverage optimizer — multi-plan bump search and staffing scenario sweep."""

import unittest
from datetime import timedelta
from unittest.mock import patch

from tests.helpers import test_database, working_date_for_squad
from validators import officer_uses_command_staff_schedule


class CoverageOptimizerTests(unittest.TestCase):
    def test_load_policy_defaults(self):
        from logic.coverage_optimizer import load_coverage_policy

        with test_database():
            p = load_coverage_policy()
            self.assertGreaterEqual(p.min_per_shift, 1)
            self.assertGreaterEqual(p.night_minimum, 1)
            self.assertGreaterEqual(p.max_cascade_depth, 1)

    def test_list_scored_replacements_prefers_junior(self):
        from logic import get_officers_by_seniority
        from logic.coverage_optimizer import list_scored_replacements
        from logic.scheduling import get_generated_schedule_day_context

        with test_database():
            officers = [
                o
                for o in get_officers_by_seniority()
                if o["squad"] == "A"
                and o.get("shift_start") == "06:00"
                and not officer_uses_command_staff_schedule(o)
                and o.get("active") == 1
            ]
            self.assertTrue(officers)
            requester = officers[0]
            day = working_date_for_squad("A")
            ctx = get_generated_schedule_day_context(day)
            ranked = list_scored_replacements(
                requester["id"],
                day.strftime("%Y-%m-%d"),
                requester["squad"],
                requester["shift_start"],
                ctx,
                limit=5,
            )
            self.assertTrue(ranked)
            # Best candidate should be among highest seniority_rank (junior-first)
            scores = [s for s, _ in ranked]
            self.assertEqual(scores, sorted(scores, reverse=True))

    def test_optimize_day_off_finds_plan(self):
        from logic import get_officers_by_seniority
        from logic.coverage_optimizer import optimize_day_off_coverage, suggest_bump_chain

        with test_database():
            officers = [
                o
                for o in get_officers_by_seniority()
                if o["squad"] == "A"
                and o.get("shift_start") == "06:00"
                and not officer_uses_command_staff_schedule(o)
                and o.get("active") == 1
            ]
            requester = officers[0]
            day = working_date_for_squad("A").strftime("%Y-%m-%d")
            plan = optimize_day_off_coverage(
                requester["id"],
                day,
                requester["squad"],
                requester["shift_start"],
            )
            self.assertTrue(plan.success, plan.message)
            self.assertTrue(plan.chain)
            via_api = suggest_bump_chain(requester["id"], day, requester["squad"], requester["shift_start"])
            self.assertTrue(via_api.success, via_api.message)

    def test_preview_best_coverage_plans(self):
        from logic import get_officers_by_seniority
        from logic.scheduling_sim import preview_best_coverage_plans

        with test_database():
            officers = [
                o
                for o in get_officers_by_seniority()
                if o["squad"] == "A"
                and o.get("shift_start") == "06:00"
                and not officer_uses_command_staff_schedule(o)
                and o.get("active") == 1
            ]
            requester = officers[0]
            day = working_date_for_squad("A").strftime("%Y-%m-%d")
            result = preview_best_coverage_plans(
                requester["id"], day, requester["squad"], requester["shift_start"], max_plans=3
            )
            self.assertTrue(result["success"])
            self.assertGreaterEqual(result["count"], 1)
            self.assertIn("policy", result)

    def test_staffing_optimizer_ranks_scenarios(self):
        from logic.scheduling_sim import run_staffing_optimizer

        with test_database():
            result = run_staffing_optimizer(
                simulation_days=14,
                officer_counts=[12, 16],
                min_per_shift_options=[1, 2],
                require_hard_ok=False,
            )
            self.assertTrue(result["success"], result.get("message"))
            self.assertGreaterEqual(result["scenarios_evaluated"], 1)
            self.assertIsNotNone(result["best"])
            self.assertIn("rotation_type", result["best"])

    def test_parse_min_staffing_by_band(self):
        from logic.coverage_optimizer import parse_min_staffing_by_band

        self.assertEqual(parse_min_staffing_by_band('{"06:00": 2, "19:00": 2}'), {"06:00": 2, "19:00": 2})
        self.assertEqual(parse_min_staffing_by_band("06:00=2, 19:00=3"), {"06:00": 2, "19:00": 3})
        self.assertEqual(parse_min_staffing_by_band(""), {})

    def test_min_for_band_policy(self):
        from logic.coverage_optimizer import CoveragePolicy

        p = CoveragePolicy(min_per_shift=1, min_by_band={"19:00": 2, "06:00": 2})
        self.assertEqual(p.min_for_band("19:00"), 2)
        self.assertEqual(p.min_for_band("10:00"), 1)

    def test_preferred_chain_approve(self):
        from logic import (
            create_day_off_request,
            get_officers_by_seniority,
            process_day_off_request,
        )
        from logic.coverage_optimizer import suggest_bump_chain

        with test_database():
            officers = [
                o
                for o in get_officers_by_seniority()
                if o["squad"] == "A"
                and o.get("shift_start") == "06:00"
                and not officer_uses_command_staff_schedule(o)
                and o.get("active") == 1
            ]
            requester = officers[0]
            day = working_date_for_squad("A").strftime("%Y-%m-%d")
            plan = suggest_bump_chain(requester["id"], day, requester["squad"], requester["shift_start"])
            self.assertTrue(plan.success, plan.message)
            # User-facing messages must not leak internal plan scores
            self.assertNotIn("score ", (plan.message or "").lower())
            created = create_day_off_request(requester["id"], day, "Vacation", "optimizer test")
            self.assertTrue(created.get("success"), created.get("message"))
            rid = created["request_id"]
            result = process_day_off_request(rid, action="approve", preferred_chain=list(plan.chain))
            self.assertTrue(result.success, result.message)

    def test_preferred_chain_rejects_unverified_existing_officer_pair(self):
        from logic import (
            create_day_off_request,
            get_officers_by_seniority,
            process_day_off_request,
        )

        with test_database():
            requester = next(
                o
                for o in get_officers_by_seniority()
                if o["squad"] == "A"
                and o.get("shift_start") == "06:00"
                and not officer_uses_command_staff_schedule(o)
                and o.get("active") == 1
            )
            day = working_date_for_squad("A").strftime("%Y-%m-%d")
            created = create_day_off_request(requester["id"], day, "Vacation", "forged plan test")
            self.assertTrue(created.get("success"), created)

            result = process_day_off_request(
                created["request_id"],
                action="approve",
                preferred_chain=[(requester["id"], requester["id"])],
            )
            self.assertFalse(result.success, result.message)
            self.assertIn("stale or failed", result.message)

    def test_approval_rolls_back_when_live_schedule_rebuild_fails(self):
        from logic import (
            create_day_off_request,
            get_day_off_requests,
            get_officers_by_seniority,
            process_day_off_request,
        )

        with test_database():
            requester = next(
                o
                for o in get_officers_by_seniority()
                if o["squad"] == "A"
                and o.get("shift_start") == "06:00"
                and not officer_uses_command_staff_schedule(o)
                and o.get("active") == 1
            )
            day = working_date_for_squad("A").strftime("%Y-%m-%d")
            created = create_day_off_request(requester["id"], day, "Vacation", "atomic failure test")
            self.assertTrue(created.get("success"), created)

            with patch(
                "logic.snapshots.apply_live_schedule_for_date_in_transaction",
                return_value={"success": False, "message": "injected rebuild failure"},
            ):
                result = process_day_off_request(created["request_id"], action="approve")

            self.assertFalse(result.success, result.message)
            request = next(r for r in get_day_off_requests() if r["id"] == created["request_id"])
            self.assertNotEqual(request["status"], "Approved")

    def test_approval_rolls_back_every_effect_when_outbox_insert_fails(self):
        from database import connection
        from logic import (
            create_day_off_request,
            get_day_off_requests,
            get_officers_by_seniority,
            process_day_off_request,
        )

        with test_database():
            requester = next(
                o
                for o in get_officers_by_seniority()
                if o["squad"] == "A"
                and o.get("shift_start") == "06:00"
                and not officer_uses_command_staff_schedule(o)
                and o.get("active") == 1
            )
            day = working_date_for_squad("A").strftime("%Y-%m-%d")
            created = create_day_off_request(requester["id"], day, "Vacation", "outbox failure test")
            self.assertTrue(created.get("success"), created)

            with patch(
                "logic.requests._queue_leave_approval_notifications_in_transaction",
                side_effect=RuntimeError("injected outbox failure"),
            ):
                result = process_day_off_request(created["request_id"], action="approve")

            self.assertFalse(result.success)
            request = next(r for r in get_day_off_requests() if r["id"] == created["request_id"])
            self.assertNotEqual(request["status"], "Approved")
            with connection() as conn:
                override_count = conn.execute(
                    "SELECT COUNT(*) FROM schedule_overrides WHERE override_date = ?",
                    (day,),
                ).fetchone()[0]
                ledger_exists = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'leave_accrual_ledger'"
                ).fetchone()
                ledger_count = (
                    conn.execute(
                        "SELECT COUNT(*) FROM leave_accrual_ledger WHERE request_id = ?",
                        (created["request_id"],),
                    ).fetchone()[0]
                    if ledger_exists
                    else 0
                )
                outbox_count = conn.execute(
                    "SELECT COUNT(*) FROM notify_outbox WHERE template_key IN ('leave_approved', 'leave_cover')"
                ).fetchone()[0]
                audit_count = conn.execute(
                    "SELECT COUNT(*) FROM audit_log WHERE action = 'day_off.approve' AND entity_id = ?",
                    (created["request_id"],),
                ).fetchone()[0]
            self.assertEqual(override_count, 0)
            self.assertEqual(ledger_count, 0)
            self.assertEqual(outbox_count, 0)
            self.assertEqual(audit_count, 0)

    def test_bulk_approval_rolls_back_every_request_when_second_outbox_fails(self):
        from database import connection
        from logic import (
            bulk_approve_auto_ok_requests,
            create_day_off_request,
            get_day_off_requests,
            get_officers_by_seniority,
        )
        from logic.requests import _queue_leave_approval_notifications_in_transaction

        with test_database():
            requester = next(
                o
                for o in get_officers_by_seniority()
                if o["squad"] == "A"
                and o.get("shift_start") == "06:00"
                and not officer_uses_command_staff_schedule(o)
                and o.get("active") == 1
            )
            first_day = working_date_for_squad("A")
            request_ids = []
            for day in (first_day, first_day + timedelta(days=14)):
                created = create_day_off_request(
                    requester["id"], day.strftime("%Y-%m-%d"), "Vacation", "atomic batch test"
                )
                self.assertTrue(created.get("success"), created)
                request_ids.append(created["request_id"])

            calls = 0

            def fail_second_outbox(*args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise RuntimeError("injected second outbox failure")
                return _queue_leave_approval_notifications_in_transaction(*args, **kwargs)

            with patch(
                "logic.requests._queue_leave_approval_notifications_in_transaction",
                side_effect=fail_second_outbox,
            ):
                result = bulk_approve_auto_ok_requests()

            self.assertFalse(result["success"], result)
            self.assertEqual(result["approved"], 0)
            self.assertEqual(calls, 2)
            requests = {r["id"]: r for r in get_day_off_requests()}
            self.assertTrue(all(requests[rid]["status"] != "Approved" for rid in request_ids))
            with connection() as conn:
                for request_id in request_ids:
                    self.assertEqual(
                        conn.execute(
                            "SELECT COUNT(*) FROM leave_accrual_ledger WHERE request_id = ?",
                            (request_id,),
                        ).fetchone()[0],
                        0,
                    )
                    self.assertEqual(
                        conn.execute(
                            "SELECT COUNT(*) FROM audit_log WHERE action = 'day_off.approve' AND entity_id = ?",
                            (request_id,),
                        ).fetchone()[0],
                        0,
                    )

    def test_plan_messages_omit_scores_and_chain_unique(self):
        from logic import get_officers_by_seniority
        from logic.plan_explain import explain_coverage_plans
        from logic.scheduling_sim import preview_best_coverage_plans

        with test_database():
            officers = [
                o
                for o in get_officers_by_seniority()
                if o["squad"] == "A"
                and o.get("shift_start") == "06:00"
                and not officer_uses_command_staff_schedule(o)
                and o.get("active") == 1
            ]
            requester = officers[0]
            day = working_date_for_squad("A").strftime("%Y-%m-%d")
            result = preview_best_coverage_plans(
                requester["id"], day, requester["squad"], requester["shift_start"], max_plans=5
            )
            self.assertTrue(result["success"])
            for plan in result.get("plans") or []:
                msg = (plan.get("message") or "").lower()
                self.assertNotIn("score ", msg)
                chain = plan.get("chain") or []
                if chain and plan.get("success"):
                    officers_in = []
                    for a, b in chain:
                        officers_in.extend([a, b])
                    # No self-loops; cycle of immediate pair forbidden
                    self.assertTrue(all(a != b for a, b in chain))
            narrative = explain_coverage_plans(result)
            self.assertIn("Option", narrative)
            low = narrative.lower()
            self.assertNotIn("score=", low)
            self.assertNotIn("soft score", low)
            self.assertNotIn("weights:", low)

    def test_staffing_ranked_human_metrics(self):
        from logic.scheduling_sim import run_staffing_optimizer

        with test_database():
            result = run_staffing_optimizer(
                simulation_days=14,
                officer_counts=[12, 16],
                min_per_shift_options=[1],
                require_hard_ok=False,
            )
            self.assertTrue(result["success"], result.get("message"))
            self.assertNotIn("score ", (result.get("message") or "").lower())
            ranked = result.get("ranked") or []
            self.assertTrue(ranked)
            self.assertIn("summary", ranked[0])
            self.assertIn("human_metrics", ranked[0])
            self.assertEqual(ranked[0].get("rank"), 1)

    def test_cp_sat_instance_from_department(self):
        from logic.cp_sat_bridge import (
            format_solution_report,
            instance_from_department,
            ortools_available,
            solve_staffing_feasibility,
        )

        with test_database():
            inst = instance_from_department(n_officers=8, n_days=5)
            self.assertGreaterEqual(len(inst.officer_ids), 1)
            self.assertTrue(inst.bands)
            sol = solve_staffing_feasibility(inst, time_limit_sec=2.0)
            report = format_solution_report(sol)
            self.assertIn("CP-SAT", report)
            if ortools_available():
                self.assertTrue(sol.available)
            else:
                self.assertFalse(sol.available)


if __name__ == "__main__":
    unittest.main()
