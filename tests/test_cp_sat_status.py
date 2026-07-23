import unittest

from logic.cp_sat_bridge import (
    StaffingInstance,
    _canonical_cp_sat_status,
    solve_staffing_feasibility,
)


class CpSatStatusTests(unittest.TestCase):
    def test_canonical_status_translation_preserves_unknown(self):
        self.assertEqual(_canonical_cp_sat_status("OPTIMAL"), "OPTIMAL")
        self.assertEqual(_canonical_cp_sat_status("FEASIBLE"), "FEASIBLE")
        self.assertEqual(_canonical_cp_sat_status("INFEASIBLE"), "INFEASIBLE")
        self.assertEqual(_canonical_cp_sat_status("MODEL_INVALID"), "MODEL_INVALID")
        self.assertEqual(_canonical_cp_sat_status("UNKNOWN"), "UNKNOWN")

    def test_proven_eligibility_shortfall_is_infeasible(self):
        solution = solve_staffing_feasibility(
            StaffingInstance(
                officer_ids=[1],
                days=["d1"],
                bands=["06:00"],
                min_per_band={"06:00": 2},
            )
        )
        if not solution.available:
            self.skipTest("OR-Tools unavailable")
        self.assertFalse(solution.feasible)
        self.assertEqual(solution.status, "INFEASIBLE")


if __name__ == "__main__":
    unittest.main()
