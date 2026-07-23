import unittest
from unittest.mock import patch

from tests.helpers import (
    get_any_officer,
    off_date_for_squad,
    test_database,
    working_date_for_squad,
)


class TestRegressions(unittest.TestCase):
    def test_export_requests_pdf_with_date_filter(self):
        with test_database():
            import os
            import tempfile

            import logic

            officer = get_any_officer("A")
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            logic.create_day_off_request(officer["id"], work_day, "Vacation")
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "req.pdf")
                result = logic.export_requests_pdf(
                    date_from=work_day,
                    date_to=work_day,
                    output_path=path,
                )
                self.assertTrue(result["success"])
                self.assertTrue(os.path.isfile(path))

    def test_day_off_request_date_filter(self):
        with test_database():
            import logic

            officer = get_any_officer("A")
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            logic.create_day_off_request(officer["id"], work_day, "Vacation")
            all_reqs = logic.get_day_off_requests()
            self.assertEqual(len(all_reqs), 1)
            filtered = logic.get_day_off_requests(date_from=work_day, date_to=work_day)
            self.assertEqual(len(filtered), 1)
            empty = logic.get_day_off_requests(date_from="2099-01-01")
            self.assertEqual(len(empty), 0)

    def test_day_off_request_created_at_timestamp(self):
        with test_database():
            import logic

            officer = get_any_officer("A")
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            created = logic.create_day_off_request(officer["id"], work_day, "Vacation")
            self.assertTrue(created["success"], created.get("message"))
            self.assertIsNotNone(created.get("created_at"))
            ts = logic.get_day_off_request_created_at(created["request_id"])
            self.assertTrue(ts["success"])
            self.assertEqual(ts["created_at"], created["created_at"])

    def test_day_off_requests_for_viewer_role_scope(self):
        with test_database():
            import logic

            officer_a = get_any_officer("A")
            officer_b = get_any_officer("B")
            work_a = working_date_for_squad("A").strftime("%Y-%m-%d")
            work_b = working_date_for_squad("B").strftime("%Y-%m-%d")
            logic.create_day_off_request(officer_a["id"], work_a, "Vacation")
            logic.create_day_off_request(officer_b["id"], work_b, "Sick")

            officer_view = logic.get_day_off_requests_for_viewer(
                "Officer",
                linked_officer_id=officer_a["id"],
            )
            self.assertTrue(officer_view["success"])
            self.assertEqual(officer_view["scope"], "own")
            self.assertEqual(len(officer_view["requests"]), 1)
            self.assertEqual(officer_view["requests"][0]["officer_id"], officer_a["id"])

            supervisor_view = logic.get_day_off_requests_for_viewer("Supervisor")
            self.assertTrue(supervisor_view["success"])
            self.assertEqual(supervisor_view["scope"], "all")
            self.assertEqual(len(supervisor_view["requests"]), 2)

    def test_minimum_rest_routes_to_manual_then_supervisor_override(self):
        with test_database():
            from unittest.mock import patch

            import logic
            from tests.helpers import get_any_officer

            original = get_any_officer("A", "06:00")
            request_date = working_date_for_squad("A").strftime("%Y-%m-%d")
            with patch("config.MIN_REST_HOURS_BETWEEN_SHIFTS", 18.0):
                create = logic.create_day_off_request(
                    original["id"],
                    request_date,
                    "Vacation",
                    "Rest override test",
                )
                self.assertTrue(create["success"])
                first = logic.process_day_off_request(create["request_id"], "approve")
                self.assertFalse(first.success)
                self.assertTrue(first.requires_manual)
                self.assertIn("Minimum rest", first.message)
                supervisor = next(
                    user for user in logic.list_login_users() if user["role"] in ("Supervisor", "Administration")
                )
                second = logic.process_day_off_request(
                    create["request_id"],
                    "approve",
                    actor_user_id=supervisor["id"],
                    admin_notes="Emergency minimum-rest exception",
                )
                self.assertTrue(second.success)
                self.assertIn("minimum rest override", second.message.lower())
                from database import connection

                with connection() as conn:
                    evidence = conn.execute(
                        """
                        SELECT relaxed_constraint, override_authority_user_id,
                               override_interval_start, override_interval_end,
                               override_reason, override_evidence
                        FROM schedule_overrides
                        WHERE original_officer_id = ?
                        """,
                        (original["id"],),
                    ).fetchone()
                self.assertEqual(evidence["relaxed_constraint"], "minimum_rest")
                self.assertEqual(evidence["override_authority_user_id"], supervisor["id"])
                self.assertTrue(evidence["override_interval_start"])
                self.assertTrue(evidence["override_interval_end"])
                self.assertEqual(evidence["override_reason"], "Emergency minimum-rest exception")
                self.assertTrue(evidence["override_evidence"])

    def test_off_rotation_request_allowed(self):
        with test_database():
            import logic
            from config import DAY_OFF_REQUEST_TYPES

            officer = get_any_officer("B")
            off_day = off_date_for_squad("B").strftime("%Y-%m-%d")
            for req_type in DAY_OFF_REQUEST_TYPES:
                result = logic.create_day_off_request(
                    officer["id"],
                    off_day,
                    req_type,
                    notes=f"Type test {req_type}",
                )
                self.assertTrue(result["success"], f"{req_type}: {result.get('message')}")
                logic.process_day_off_request(result["request_id"], "reject")

    def test_day_off_notifies_supervisor_and_admin_reviewers(self):
        with test_database():
            import logic

            officer = get_any_officer("A", "06:00")
            admin = next(u for u in logic.list_all_users() if u["role"] == "Administration" and u.get("officer_id"))
            supervisor = next(u for u in logic.list_all_users() if u["role"] == "Supervisor" and u.get("officer_id"))
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            result = logic.create_day_off_request(officer["id"], work_day, "Personal")
            self.assertTrue(result["success"])

            admin_notes = logic.get_notifications(officer_id=admin["officer_id"])
            sup_notes = logic.get_notifications(officer_id=supervisor["officer_id"])
            self.assertTrue(any("New Day-Off Request" in n["title"] for n in admin_notes))
            self.assertTrue(any("New Day-Off Request" in n["title"] for n in sup_notes))

    def test_unavailable_date_still_submittable(self):
        with test_database():
            import logic

            officer = get_any_officer("A")
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            logic.add_officer_availability(officer["id"], work_day, reason="Family event")
            result = logic.create_day_off_request(officer["id"], work_day, "Personal")
            self.assertTrue(result["success"])

    def test_reapprove_blocked(self):
        with test_database():
            import logic
            from database import get_connection

            officer = get_any_officer("A", "06:00")
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            cr = logic.create_day_off_request(officer["id"], work_day, "Vacation")
            first_approve = logic.process_day_off_request(cr["request_id"], "approve")
            self.assertTrue(first_approve.success, first_approve.message)

            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM schedule_overrides WHERE original_officer_id = ?", (officer["id"],))
            first = c.fetchone()[0]
            self.assertGreaterEqual(first, 1)

            second = logic.process_day_off_request(cr["request_id"], "approve")
            c.execute("SELECT COUNT(*) FROM schedule_overrides WHERE original_officer_id = ?", (officer["id"],))
            after = c.fetchone()[0]
            conn.close()

            self.assertFalse(second.success)
            self.assertEqual(first, after)

    def test_day_shift_friday_not_night_blocked(self):
        with test_database():
            from logic.coverage_optimizer import validate_bump_feasibility

            officer = get_any_officer("A", "06:00")
            result = validate_bump_feasibility(officer["id"], "2026-07-03", officer["squad"], officer["shift_start"])
            if result.requires_manual:
                self.assertNotIn("night", result.message.lower())

    def test_manual_review_approve_and_reject(self):
        with test_database():
            from unittest.mock import patch

            import logic
            from database import get_connection

            officer = get_any_officer("A", "06:00")
            work_day = "2026-07-02"

            with patch("config.MIN_REST_HOURS_BETWEEN_SHIFTS", 18.0):
                cr = logic.create_day_off_request(officer["id"], work_day, "Vacation")
                self.assertTrue(cr["success"])

                first = logic.process_day_off_request(cr["request_id"], "approve")
                self.assertTrue(first.requires_manual)
                self.assertEqual(first.status, "Pending Manual Review")

                supervisor = next(
                    user for user in logic.list_login_users() if user["role"] in ("Supervisor", "Administration")
                )
                second = logic.process_day_off_request(
                    cr["request_id"],
                    "approve",
                    actor_user_id=supervisor["id"],
                    admin_notes="Emergency minimum-rest exception",
                )
                self.assertTrue(second.success)
                self.assertEqual(second.status, "Approved")

            conn = get_connection()
            c = conn.cursor()
            c.execute(
                "SELECT status FROM day_off_requests WHERE id = ?",
                (cr["request_id"],),
            )
            self.assertEqual(c.fetchone()[0], "Approved")
            self.assertTrue(second.override_created or second.message.startswith("Approved"))
            conn.close()

            second_day = "2026-07-02"
            with patch("config.MIN_REST_HOURS_BETWEEN_SHIFTS", 18.0):
                cr2 = logic.create_day_off_request(officer["id"], second_day, "Sick")
                pending = logic.process_day_off_request(cr2["request_id"], "approve")
                self.assertEqual(pending.status, "Pending Manual Review")
                rejected = logic.process_day_off_request(cr2["request_id"], "reject")
            self.assertTrue(rejected.success)
            self.assertEqual(rejected.status, "Rejected")

    def test_scenario_s07_duplicate_blocked_during_manual_review(self):
        with test_database():
            from unittest.mock import patch

            import logic

            officer = get_any_officer("A", "06:00")
            dup_day = "2026-07-07"

            with patch("config.MIN_REST_HOURS_BETWEEN_SHIFTS", 18.0):
                cr = logic.create_day_off_request(officer["id"], dup_day, "Vacation")
                logic.process_day_off_request(cr["request_id"], "approve")

                duplicate = logic.create_day_off_request(officer["id"], dup_day, "Personal")
                self.assertFalse(duplicate["success"])
                self.assertIn("pending", duplicate.get("message", "").lower())

    def test_scenario_s10_off_rotation_routes_manual_review(self):
        with test_database():
            import logic
            from database import get_connection
            from tests.helpers import off_date_for_squad

            officer = get_any_officer("A", "06:00")
            request_date = off_date_for_squad("A").strftime("%Y-%m-%d")
            cr = logic.create_day_off_request(officer["id"], request_date, "Vacation")
            self.assertTrue(cr["success"])
            result = logic.process_day_off_request(cr["request_id"], "approve")
            self.assertFalse(result.success)
            self.assertTrue(result.requires_manual)
            self.assertEqual(result.status, "Pending Manual Review")

            conn = get_connection()
            c = conn.cursor()
            c.execute(
                "SELECT COUNT(*) FROM schedule_overrides WHERE override_date = ? AND original_officer_id = ?",
                (request_date, officer["id"]),
            )
            self.assertEqual(c.fetchone()[0], 0)
            conn.close()

    def test_scenario_s11_shift_swap_dual_overrides(self):
        with test_database():
            import logic
            from database import get_connection

            o1 = get_any_officer("A", "06:00")
            o2 = get_any_officer("A", "10:00")
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            cr = logic.create_shift_swap_request(o1["id"], o2["id"], work_day)
            self.assertTrue(cr["success"])
            result = logic.process_shift_swap(cr["swap_id"], "approve")
            self.assertTrue(result.success)

            conn = get_connection()
            c = conn.cursor()
            c.execute(
                "SELECT COUNT(*) FROM schedule_overrides WHERE override_date = ? AND reason = 'Shift Swap'",
                (work_day,),
            )
            self.assertEqual(c.fetchone()[0], 2)
            conn.close()

    def test_scenario_s09_eligible_replacement_selected(self):
        with test_database():
            import logic
            from logic.coverage_optimizer import validate_bump_feasibility
            from logic.staffing_config import can_officer_cover_shift

            officer = get_any_officer("A", "06:00")
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            result = validate_bump_feasibility(
                officer["id"],
                work_day,
                officer["squad"],
                officer["shift_start"],
            )
            self.assertTrue(result.success)
            eligible = [
                o
                for o in logic.get_officers_by_seniority()
                if o["id"] != officer["id"] and can_officer_cover_shift(o["shift_start"], officer["shift_start"])
            ]
            eligible_names = {o["name"] for o in eligible}
            self.assertIn(result.replacement_name, eligible_names)

    def test_vacation_pending_sorted_by_seniority_for_granting(self):
        """Seniority rank applies only to Vacation requests — senior officers first in grant queue."""
        with test_database():
            import logic

            senior = get_any_officer("A", "06:00")
            junior = get_any_officer("A", "10:00")
            self.assertLess(senior["seniority_rank"], junior["seniority_rank"])
            day = off_date_for_squad("A").strftime("%Y-%m-%d")
            logic.create_day_off_request(junior["id"], day, "Vacation")
            logic.create_day_off_request(senior["id"], day, "Vacation")
            pending = logic.get_pending_day_off_requests()
            vacation_ids = [
                r["officer_id"] for r in pending if r["request_type"] == "Vacation" and r["request_date"] == day
            ]
            self.assertEqual(vacation_ids[0], senior["id"])
            self.assertEqual(vacation_ids[1], junior["id"])

    def test_approve_not_committed_when_override_insert_fails(self):
        with test_database():
            import logic
            from database import get_connection

            officer = get_any_officer("A", "06:00")
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            cr = logic.create_day_off_request(officer["id"], work_day, "Vacation")

            with patch("logic.requests._insert_override_record", side_effect=RuntimeError("override failed")):
                result = logic.process_day_off_request(cr["request_id"], "approve")

            self.assertFalse(result.success)

            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT status FROM day_off_requests WHERE id = ?", (cr["request_id"],))
            self.assertEqual(c.fetchone()[0], "Pending")
            c.execute(
                "SELECT COUNT(*) FROM schedule_overrides WHERE original_officer_id = ?",
                (officer["id"],),
            )
            self.assertEqual(c.fetchone()[0], 0)
            conn.close()

    def test_manual_coverage_override(self):
        with test_database():
            import logic

            original = get_any_officer("A", "06:00")
            replacement = get_any_officer("A", "10:00")
            work_day = off_date_for_squad("A").strftime("%Y-%m-%d")
            result = logic.create_manual_coverage_override(
                original["id"],
                replacement["id"],
                work_day,
                reason="Supervisor assign",
            )
            self.assertTrue(result["success"])

            dup = logic.create_manual_coverage_override(
                original["id"],
                replacement["id"],
                work_day,
            )
            self.assertFalse(dup["success"])

            from datetime import date

            count = logic.count_officers_on_shift_on_date(
                date.fromisoformat(work_day),
                "A",
                "06:00",
            )
            self.assertGreaterEqual(count, 1)

    def test_covered_shift_start_used_for_staffing_count(self):
        with test_database():
            from datetime import date

            import logic
            from database import get_connection

            original = get_any_officer("A", "06:00")
            replacement = get_any_officer("A", "10:00")
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            target = date.fromisoformat(work_day)

            before = logic.count_officers_on_shift_on_date(target, "A", "06:00")

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO schedule_overrides
                (override_date, original_officer_id, replacement_officer_id, reason, covered_shift_start)
                VALUES (?, ?, ?, 'Test', ?)
            """,
                (work_day, original["id"], replacement["id"], original["shift_start"]),
            )
            conn.commit()
            conn.close()

            with_covered = logic.count_officers_on_shift_on_date(target, "A", "06:00")
            self.assertEqual(with_covered, before)

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM schedule_overrides WHERE original_officer_id = ?", (original["id"],))
            cursor.execute(
                """
                INSERT INTO schedule_overrides
                (override_date, original_officer_id, replacement_officer_id, reason, covered_shift_start)
                VALUES (?, ?, ?, 'Test', NULL)
            """,
                (work_day, original["id"], replacement["id"]),
            )
            conn.commit()
            conn.close()

            without_slot = logic.count_officers_on_shift_on_date(target, "A", "06:00")
            self.assertEqual(without_slot, before - 1)

    def test_command_staff_monday_friday_schedule(self):
        with test_database():
            from datetime import date

            import logic

            chief = get_any_officer("A", "06:00", include_command_staff=True)
            logic.update_officer(chief["id"], job_title="Chief")
            monday = date(2026, 7, 6)
            saturday = date(2026, 7, 11)
            self.assertEqual(logic.get_officer_day_status(chief["id"], monday), "working")
            self.assertEqual(logic.get_officer_day_status(chief["id"], saturday), "off")
            self.assertTrue(logic.is_officer_working_on_day(chief["id"], monday))
            self.assertFalse(logic.is_officer_working_on_day(chief["id"], saturday))

    def test_court_and_training_request_types(self):
        with test_database():
            import logic

            court_officer = get_any_officer("B", "10:00")
            training_officer = get_any_officer("B", "15:00")
            court_day = off_date_for_squad("B").strftime("%Y-%m-%d")
            training_day = "2026-07-04"
            court = logic.create_day_off_request(court_officer["id"], court_day, "Court")
            training = logic.create_day_off_request(training_officer["id"], training_day, "Training")
            self.assertTrue(court.get("success"), court.get("message"))
            self.assertTrue(training.get("success"), training.get("message"))


if __name__ == "__main__":
    unittest.main()
