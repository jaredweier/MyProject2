import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime

from logic.coverage_timeline import (
    CoverageWindow,
    assignment_intervals,
    check_coverage_247,
    evaluate_day_coverage,
    occupancy_at,
)


class CoverageTimelineTests(unittest.TestCase):
    def test_overnight_intervals_split(self):
        parts = assignment_intervals(date(2026, 7, 10), "22:00", "06:00")
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0][0], datetime(2026, 7, 10, 22, 0))
        self.assertEqual(parts[1][1], datetime(2026, 7, 11, 6, 0))

    def test_example_247_and_extra_window(self):
        """User example: A 14-22, B 19-03, C 22-06 meets Fri 19-03 min=2; + day band for 24/7=1."""
        fri = date(2026, 7, 10)  # Friday
        thu = date(2026, 7, 9)
        # Prior overnight + early day so 24/7 floor of 1 holds on Fri calendar day
        assignments = [
            (thu, "22:00", "06:00"),  # overnight into Fri morning
            (fri, "06:00", "14:00"),  # day band
            (fri, "14:00", "22:00"),  # Officer A
            (fri, "19:00", "03:00"),  # Officer B
            (fri, "22:00", "06:00"),  # Officer C
        ]
        r247 = check_coverage_247(assignments, fri, min_officers=1)
        self.assertTrue(r247["ok"], r247["message"])

        window = CoverageWindow(
            min_officers=2,
            start_time="19:00",
            end_time="03:00",
            specific_date=fri,
            label="Fri night boost",
        )
        # Window check uses A/B/C style overlap (include day bands still ok)
        day = evaluate_day_coverage(assignments, fri, min_247=1, windows=[window])
        self.assertTrue(day["ok"], day)

        # At 20:00: A+B (+ maybe others) >= 2
        self.assertGreaterEqual(occupancy_at(assignments, datetime(2026, 7, 10, 20, 0)), 2)
        # At 00:30 Sat: B+C = 2
        self.assertEqual(occupancy_at(assignments, datetime(2026, 7, 11, 0, 30)), 2)
        # At 04:00: only C = 1
        self.assertEqual(occupancy_at(assignments, datetime(2026, 7, 11, 4, 0)), 1)

        # Isolated user triple: window alone is satisfied without full-day 24/7
        triple = [
            (fri, "14:00", "22:00"),
            (fri, "19:00", "03:00"),
            (fri, "22:00", "06:00"),
        ]
        w_only = evaluate_day_coverage(triple, fri, min_247=0, windows=[window])
        self.assertTrue(w_only["ok"], w_only)

    def test_window_fails_when_understaffed(self):
        fri = date(2026, 7, 10)
        assignments = [(fri, "14:00", "22:00")]  # alone
        window = CoverageWindow(min_officers=2, start_time="19:00", end_time="03:00", specific_date=fri)
        day = evaluate_day_coverage(assignments, fri, min_247=0, windows=[window])
        self.assertFalse(day["ok"])


if __name__ == "__main__":
    unittest.main()
