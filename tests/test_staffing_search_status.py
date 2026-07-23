import unittest

from logic.staffing_optimizer import _derive_search_status


class StaffingSearchStatusTests(unittest.TestCase):
    def test_verified_candidate_is_feasible(self):
        self.assertEqual(
            _derive_search_status(
                cancelled=False,
                has_verified_result=True,
                search_exhaustive=False,
            ),
            "FEASIBLE",
        )

    def test_exhaustive_miss_is_infeasible(self):
        self.assertEqual(
            _derive_search_status(
                cancelled=False,
                has_verified_result=False,
                search_exhaustive=True,
            ),
            "INFEASIBLE",
        )

    def test_limited_miss_is_unknown(self):
        self.assertEqual(
            _derive_search_status(
                cancelled=False,
                has_verified_result=False,
                search_exhaustive=False,
            ),
            "UNKNOWN",
        )

    def test_cancelled_takes_priority_over_partial_candidate(self):
        self.assertEqual(
            _derive_search_status(
                cancelled=True,
                has_verified_result=True,
                search_exhaustive=False,
            ),
            "CANCELLED",
        )


if __name__ == "__main__":
    unittest.main()
