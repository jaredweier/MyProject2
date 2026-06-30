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
            request_date = "2026-06-30"
            with patch("config.MIN_REST_HOURS_BETWEEN_SHIFTS", 10.0):
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
                second = logic.process_day_off_request(create["request_id"], "approve")
                self.assertTrue(second.success)
                self.assertIn("minimum rest override", second.message.lower())

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
            work_day = off_date_for_squad("A").strftime("%Y-%m-%d")
            cr = logic.create_day_off_request(officer["id"], work_day, "Vacation")
            logic.process_day_off_request(cr["request_id"], "approve")

            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM schedule_overrides WHERE original_officer_id = ?", (officer["id"],))
            first = c.fetchone()[0]

            second = logic.process_day_off_request(cr["request_id"], "approve")
            c.execute("SELECT COUNT(*) FROM schedule_overrides WHERE original_officer_id = ?", (officer["id"],))
            after = c.fetchone()[0]
            conn.close()

            self.assertFalse(second.success)
            self.assertEqual(first, after)

    def test_day_shift_friday_not_night_blocked(self):
        with test_database():
            import logic

            officer = get_any_officer("A", "06:00")
            result = logic.validate_bump_feasibility(
                officer["id"], "2026-07-03", officer["squad"], officer["shift_start"]
            )
            if result.requires_manual:
                self.assertNotIn("night", result.message.lower())

    def test_manual_review_approve_and_reject(self):
        with test_database():
            import logic
            from database import get_connection

            officer = get_any_officer("A", "19:00")
            friday = "2026-07-03"
            if not logic.is_officer_working_on_day(officer["id"], __import__("datetime").date(2026, 7, 3)):
                self.skipTest("Night officer not on duty on test Friday")

            cr = logic.create_day_off_request(officer["id"], friday, "Vacation")
            self.assertTrue(cr["success"])

            first = logic.process_day_off_request(cr["request_id"], "approve")
            self.assertTrue(first.requires_manual)
            self.assertEqual(first.status, "Pending Manual Review")

            second = logic.process_day_off_request(cr["request_id"], "approve")
            self.assertTrue(second.success)
            self.assertEqual(second.status, "Approved")

            conn = get_connection()
            c = conn.cursor()
            c.execute(
                "SELECT status FROM day_off_requests WHERE id = ?",
                (cr["request_id"],),
            )
            self.assertEqual(c.fetchone()[0], "Approved")
            # Supervisor may force-approve without a replacement when cascade is blocked.
            self.assertTrue(second.override_created or second.message.startswith("Approved"))
            conn.close()

            cr2 = logic.create_day_off_request(officer["id"], "2026-07-04", "Sick")
            logic.process_day_off_request(cr2["request_id"], "approve")
            rejected = logic.process_day_off_request(cr2["request_id"], "reject")
            self.assertTrue(rejected.success)
            self.assertEqual(rejected.status, "Rejected")

    def test_scenario_s07_duplicate_blocked_during_manual_review(self):
        with test_database():
            import logic

            officer = get_any_officer("A", "19:00")
            dup_day = "2026-07-17"
            if not logic.is_officer_working_on_day(
                officer["id"],
                __import__("datetime").date.fromisoformat(dup_day),
            ):
                self.skipTest("Night officer not on duty on test date")

            cr = logic.create_day_off_request(officer["id"], dup_day, "Vacation")
            logic.process_day_off_request(cr["request_id"], "approve")

            duplicate = logic.create_day_off_request(officer["id"], dup_day, "Personal")
            self.assertFalse(duplicate["success"])
            self.assertIn("pending", duplicate.get("message", "").lower())

    def test_scenario_s10_cascade_auto_approve_off_rotation(self):
        with test_database():
            import logic
            from database import get_connection

            officer = get_any_officer("A", "06:00")
            request_date = "2026-07-01"
            cr = logic.create_day_off_request(officer["id"], request_date, "Vacation")
            self.assertTrue(cr["success"])
            result = logic.process_day_off_request(cr["request_id"], "approve")
            self.assertTrue(result.success)
            self.assertEqual(result.status, "Approved")

            conn = get_connection()
            c = conn.cursor()
            c.execute(
                "SELECT COUNT(*) FROM schedule_overrides WHERE override_date = ? AND original_officer_id = ?",
                (request_date, officer["id"]),
            )
            self.assertEqual(c.fetchone()[0], 1)
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
            from config import BUMP_RULES

            officer = get_any_officer("A", "06:00")
            result = logic.validate_bump_feasibility(
                officer["id"],
                "2026-06-30",
                officer["squad"],
                officer["shift_start"],
            )
            self.assertTrue(result.success)
            eligible = [
                o
                for o in logic.get_officers_by_seniority()
                if o["squad"] == officer["squad"]
                and o["id"] != officer["id"]
                and logic.get_shift_number(o["shift_start"])
                in BUMP_RULES.get(logic.get_shift_number(officer["shift_start"]), ())
            ]
            eligible_names = {o["name"] for o in eligible}
            self.assertIn(result.replacement_name, eligible_names)

    def test_approve_not_committed_when_override_insert_fails(self):
        with test_database():
            import logic
            from database import get_connection

            officer = get_any_officer("A", "06:00")
            work_day = off_date_for_squad("A").strftime("%Y-%m-%d")
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
            work_day = off_date_for_squad("A").strftime("%Y-%m-%d")
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


if __name__ == "__main__":
    unittest.main()
