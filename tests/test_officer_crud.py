import unittest
from datetime import date

from tests.helpers import test_database


class OfficerCrudTests(unittest.TestCase):
    def test_add_officer_with_contact_fields(self):
        with test_database():
            import logic

            result = logic.add_officer(
                "Off. Contact Test",
                20,
                "A",
                "06:00",
                "17:00",
                31.0,
                start_date="2026-01-15",
                email="contact@dodgeville.gov",
                phone="(608) 930-5228",
                address="410 E Leffler St\nDodgeville, WI 53533",
            )
            self.assertTrue(result["success"], result.get("message"))
            officer = logic.get_officer_by_id(result["officer_id"])
            self.assertEqual(officer["email"], "contact@dodgeville.gov")
            self.assertEqual(officer["start_date"], "2026-01-15")

    def test_update_officer_contact_fields(self):
        with test_database():
            import logic

            created = logic.add_officer("Off. Update Me", 21, "B", "10:00", "21:00")
            officer_id = created["officer_id"]
            result = logic.update_officer(
                officer_id,
                name="Off. Updated",
                email="updated@dodgeville.gov",
                phone="608-555-0100",
            )
            self.assertTrue(result["success"], result.get("message"))
            officer = logic.get_officer_by_id(officer_id)
            self.assertEqual(officer["name"], "Off. Updated")
            self.assertEqual(officer["email"], "updated@dodgeville.gov")

    def test_delete_officer_without_history(self):
        with test_database():
            import logic

            created = logic.add_officer("Off. Delete Me", 22, "A", "15:00", "02:00")
            officer_id = created["officer_id"]
            result = logic.delete_officer(officer_id)
            self.assertTrue(result["success"], result.get("message"))
            self.assertIsNone(logic.get_officer_by_id(officer_id))

    def test_delete_officer_blocked_with_history(self):
        with test_database():
            import logic
            from tests.helpers import get_any_officer, working_date_for_squad

            officer = get_any_officer("A", "06:00")
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            logic.create_day_off_request(officer["id"], work_day, "Vacation")
            result = logic.delete_officer(officer["id"])
            self.assertFalse(result["success"])
            self.assertIn("Deactivate", result["message"])

    def test_officer_unassigned_squad_and_shift(self):
        with test_database():
            import logic

            result = logic.add_officer(
                "Off. Floater",
                25,
                None,
                None,
                None,
                28.0,
            )
            self.assertTrue(result["success"], result.get("message"))
            officer = logic.get_officer_by_id(result["officer_id"])
            self.assertIsNone(officer["squad"])
            self.assertIsNone(officer["shift_start"])
            self.assertFalse(logic.is_officer_working_on_day(officer["id"], date.today()))

            assign = logic.update_officer(
                result["officer_id"],
                squad="B",
                shift_start="10:00",
                shift_end="21:00",
            )
            self.assertTrue(assign["success"], assign.get("message"))
            officer = logic.get_officer_by_id(result["officer_id"])
            self.assertEqual(officer["squad"], "B")

    def test_add_officer_rejects_invalid_email(self):
        with test_database():
            import logic

            result = logic.add_officer(
                "Off. Bad Email",
                23,
                "A",
                "06:00",
                "17:00",
                email="not-an-email",
            )
            self.assertFalse(result["success"])
            self.assertIn("email", result["message"].lower())


if __name__ == "__main__":
    unittest.main()
