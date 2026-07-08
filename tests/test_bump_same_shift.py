"""Bump/coverage with duplicate shift bands and custom staffing settings."""

import unittest

from tests.helpers import test_database, working_date_for_squad


class BumpSameShiftTests(unittest.TestCase):
    def test_two_officers_same_band_second_remains_stops_cascade(self):
        with test_database():
            import logic
            from database import get_connection
            from logic.staffing_config import save_staffing_settings
            from validators import officer_uses_command_staff_schedule

            save_staffing_settings(
                shift_length_hours=8.0,
                annual_hours_target=2080.0,
                shift_count=2,
                target_officer_count=10,
                shift_starts_text="06:00, 14:00",
            )

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO officers
                    (name, seniority_rank, squad, shift_start, shift_end, pay_rate, active, job_title)
                VALUES ('Off. Peer A', 20, 'A', '06:00', '14:00', 30.0, 1, 'Officer')
                """
            )
            cursor.execute(
                """
                INSERT INTO officers
                    (name, seniority_rank, squad, shift_start, shift_end, pay_rate, active, job_title)
                VALUES ('Off. Peer B', 21, 'A', '06:00', '14:00', 30.0, 1, 'Officer')
                """
            )
            cursor.execute(
                """
                INSERT INTO officers
                    (name, seniority_rank, squad, shift_start, shift_end, pay_rate, active, job_title)
                VALUES ('Off. Cover 14', 19, 'A', '14:00', '22:00', 30.0, 1, 'Officer')
                """
            )
            conn.commit()
            conn.close()

            officers = [
                o
                for o in logic.get_officers_by_seniority()
                if o["squad"] == "A" and o["shift_start"] == "06:00" and not officer_uses_command_staff_schedule(o)
            ]
            self.assertGreaterEqual(len(officers), 2)
            requester = officers[0]
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")

            suggestion = logic.suggest_bump_chain(
                requester["id"],
                work_day,
                requester["squad"],
                "06:00",
            )
            self.assertTrue(suggestion.success, suggestion.message)
            self.assertEqual(len(suggestion.steps), 1)
            self.assertTrue(suggestion.steps[0].replacement_on_duty)

            remaining = [
                o
                for o in logic.get_officers_by_seniority()
                if o["squad"] == "A"
                and o["shift_start"] == "06:00"
                and o["id"] != requester["id"]
                and not officer_uses_command_staff_schedule(o)
            ]
            self.assertGreaterEqual(len(remaining), 1)

    def test_coverage_counts_multiple_same_start_separately(self):
        with test_database():
            import logic
            from database import get_connection

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO officers
                    (name, seniority_rank, squad, shift_start, shift_end, pay_rate, active, job_title)
                VALUES ('Off. Dup A', 22, 'A', '10:00', '21:00', 30.0, 1, 'Officer')
                """
            )
            cursor.execute(
                """
                INSERT INTO officers
                    (name, seniority_rank, squad, shift_start, shift_end, pay_rate, active, job_title)
                VALUES ('Off. Dup B', 23, 'A', '10:00', '21:00', 30.0, 1, 'Officer')
                """
            )
            conn.commit()
            conn.close()

            target = working_date_for_squad("A")
            count = logic.count_officers_on_shift_on_date(target, "A", "10:00")
            self.assertGreaterEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
