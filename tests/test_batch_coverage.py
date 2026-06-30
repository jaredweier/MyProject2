import unittest
from datetime import date

from tests.helpers import test_database


class BatchCoverageTests(unittest.TestCase):
    def test_shift_coverage_batch_matches_single_count(self):
        with test_database():
            import logic

            target = date(2026, 7, 5)
            batch = logic.get_shift_coverage_counts_for_range(target, target)
            single = logic.count_officers_on_shift_on_date(target, "A", "06:00")
            self.assertEqual(batch.get((target.isoformat(), "A", "06:00")), single)

    def test_batch_officer_day_status(self):
        with test_database():
            import logic
            from tests.helpers import get_any_officer

            officer = get_any_officer("A", "06:00")
            target = date(2026, 6, 28)
            single = logic.get_officer_day_status(officer["id"], target)
            batch = logic.batch_officer_day_status([(officer["id"], target)])
            self.assertEqual(batch[(officer["id"], target.isoformat())], single)


if __name__ == "__main__":
    unittest.main()
