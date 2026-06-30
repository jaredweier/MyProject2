import csv
import os
import tempfile
import unittest

from tests.helpers import test_database


class RosterImportTests(unittest.TestCase):
    def test_seed_loads_from_json_fixture(self):
        with test_database():
            import logic

            officers = logic.get_officers_by_seniority()
            self.assertGreater(len(officers), 0)
            self.assertTrue(all("name" in o for o in officers))

    def test_update_officer_job_title(self):
        with test_database():
            import logic
            from tests.helpers import get_any_officer

            officer = get_any_officer("A")
            result = logic.update_officer(officer["id"], job_title="Lieutenant")
            self.assertTrue(result["success"], result.get("message"))
            updated = logic.get_officer_by_id(officer["id"])
            self.assertEqual(updated.get("job_title"), "Lieutenant")

    def test_update_officer_squad_and_shift(self):
        with test_database():
            import logic
            from tests.helpers import get_any_officer

            officer = get_any_officer("A")
            result = logic.update_officer(
                officer["id"],
                squad="B",
                shift_start="19:00",
                shift_end="06:00",
            )
            self.assertTrue(result["success"], result.get("message"))
            updated = logic.get_officer_by_id(officer["id"])
            self.assertEqual(updated.get("squad"), "B")
            self.assertEqual(updated.get("shift_start"), "19:00")
            self.assertEqual(updated.get("shift_end"), "06:00")

    def test_get_suggested_seniority_rank(self):
        with test_database():
            import logic

            max_rank = max(o["seniority_rank"] for o in logic.get_officers_by_seniority())
            self.assertEqual(logic.get_suggested_seniority_rank(), max_rank + 1)

    def test_import_roster_adds_officer(self):
        with test_database():
            import logic

            before = len(logic.get_officers_by_seniority())
            with tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False) as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=[
                        "id",
                        "name",
                        "seniority_rank",
                        "squad",
                        "shift_start",
                        "shift_end",
                        "pay_rate",
                        "night_differential_rate",
                        "job_title",
                        "email",
                        "phone",
                        "start_date",
                        "active",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "name": "Off. Imported",
                        "seniority_rank": 99,
                        "squad": "A",
                        "shift_start": "06:00",
                        "shift_end": "17:00",
                        "pay_rate": 31.0,
                        "active": 1,
                    }
                )
                path = fh.name

            try:
                result = logic.import_roster_from_csv(path)
                self.assertTrue(result["success"], result.get("message"))
                self.assertEqual(result["added"], 1)
                after = len(logic.get_officers_by_seniority())
                self.assertEqual(after, before + 1)
                imported = next(o for o in logic.get_officers_by_seniority() if o["name"] == "Off. Imported")
                self.assertEqual(imported["seniority_rank"], 99)
            finally:
                os.unlink(path)

    def test_get_supervisors_uses_app_user_roles(self):
        with test_database():
            import logic

            supervisors = logic.get_supervisors()
            self.assertGreater(len(supervisors), 0)
            ranks = {o["seniority_rank"] for o in supervisors}
            self.assertIn(1, ranks)
            self.assertIn(2, ranks)


if __name__ == "__main__":
    unittest.main()
