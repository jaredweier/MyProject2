import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from logic.rotation_patterns import (
    annual_hours_within_band,
    build_pattern,
    parse_variation_set,
    projected_annual_hours,
    validate_variation_set,
)


class RotationPatternsTests(unittest.TestCase):
    def test_fixed_single_block(self):
        p = build_pattern("5-2", style="fixed")
        self.assertEqual(p.cycle_length, 7)
        self.assertEqual(p.work_days_per_cycle(), 5)
        self.assertTrue(p.is_working(1))
        self.assertFalse(p.is_working(6))

    def test_rotating_multi_block_long(self):
        p = build_pattern("4-4,4-4,4-4,5-3,5-3", style="rotating")
        self.assertEqual(p.cycle_length, 40)
        self.assertEqual(p.work_days_per_cycle(), 4 * 3 + 5 * 2)

    def test_fixed_rejects_multi_block(self):
        with self.assertRaises(ValueError):
            build_pattern("5-3,6-2", style="fixed")

    def test_rotating_rejects_single(self):
        with self.assertRaises(ValueError):
            build_pattern("5-2", style="rotating")

    def test_same_length_variations(self):
        patterns = parse_variation_set(["5-3,6-2", "5-2,6-3"], style="rotating")
        self.assertEqual(len(patterns), 2)
        self.assertEqual(patterns[0].cycle_length, patterns[1].cycle_length)
        ok, _ = validate_variation_set(patterns)
        self.assertTrue(ok)

    def test_different_length_variations_rejected(self):
        with self.assertRaises(ValueError):
            parse_variation_set(["5-2", "4-3,5-2"], style=None)

    def test_phase_stagger(self):
        p = build_pattern("5-2", style="fixed")
        a = p.with_phase(0)
        b = p.with_phase(3)
        # day 1 work for A; B phase 3 means cycle idx (0+3)%7 = 3 → still on for 5-2
        self.assertTrue(a.is_working(1))
        self.assertNotEqual(
            [a.is_working(d) for d in range(1, 8)],
            [b.is_working(d) for d in range(1, 8)],
        )

    def test_half_hour_annual_band(self):
        p = build_pattern("5-2", style="fixed")
        hours = projected_annual_hours(p, 10.5)
        self.assertGreater(hours, 0)
        ok, lo, hi, dist = annual_hours_within_band(hours, hours, variance_hours=40)
        self.assertTrue(ok)
        self.assertEqual(dist, 0.0)
        ok2, _, _, dist2 = annual_hours_within_band(hours + 100, hours, variance_hours=40)
        self.assertFalse(ok2)
        self.assertGreater(dist2, 0)


if __name__ == "__main__":
    unittest.main()
