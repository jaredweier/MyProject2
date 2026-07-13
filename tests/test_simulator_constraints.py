import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers import test_database


class SimulatorConstraintsTests(unittest.TestCase):
    def setUp(self):
        self._db_cm = test_database()
        self._db_cm.__enter__()

    def tearDown(self):
        self._db_cm.__exit__(None, None, None)

    def test_half_hour_shift_length(self):
        from simulator import SimulatorConfig, simulate_schedule

        cfg = SimulatorConfig(
            rotation_type="2-2-3 (Dodgeville 14-day)",
            num_officers=12,
            shift_length_hours=10.5,
            annual_hours_target=2080,
            shift_starts=["06:00", "14:00", "22:00"],
            apply_department_rules=False,
            min_per_shift=1,
            simulation_days=14,
            auto_min_officers=False,
        )
        result = simulate_schedule(cfg)
        self.assertTrue(result.success, result.message)
        self.assertEqual(cfg.shift_length_hours, 10.5)

    def test_reject_non_half_hour(self):
        from simulator import SimulatorConfig, simulate_schedule

        cfg = SimulatorConfig(
            rotation_type="2-2-3 (Dodgeville 14-day)",
            num_officers=8,
            shift_length_hours=10.25,
            annual_hours_target=2080,
            shift_starts=["06:00", "14:00"],
            apply_department_rules=False,
            auto_min_officers=False,
        )
        result = simulate_schedule(cfg)
        self.assertFalse(result.success)
        self.assertIn("0.5", result.message)

    def test_multi_block_variations_sim(self):
        from simulator import SimulatorConfig, simulate_schedule

        cfg = SimulatorConfig(
            rotation_type="2-2-3 (Dodgeville 14-day)",
            num_officers=16,
            shift_length_hours=11.0,
            annual_hours_target=2080,
            shift_starts=["06:00", "14:00", "22:00"],
            apply_department_rules=False,
            min_per_shift=1,
            simulation_days=32,
            rotation_style="rotating",
            rotation_variations=["5-3,6-2", "5-2,6-3"],
            stagger_phases=True,
            auto_min_officers=False,
        )
        result = simulate_schedule(cfg)
        self.assertTrue(result.success, result.message)
        self.assertEqual(result.metrics.get("custom_patterns"), 2)

    def test_avoid_flsa_detects_heavy_pattern(self):
        from simulator import SimulatorConfig, simulate_schedule

        # 12h shifts, work almost every day → exceeds 171/28 quickly
        cfg = SimulatorConfig(
            rotation_type="2-2-3 (Dodgeville 14-day)",
            num_officers=4,
            shift_length_hours=12.0,
            annual_hours_target=2080,
            shift_starts=["06:00"],
            apply_department_rules=False,
            min_per_shift=0,
            simulation_days=28,
            rotation_style="fixed",
            rotation_variations=["6-1"],  # heavy
            avoid_flsa_overtime=True,
            flsa_work_period_days=28,
            auto_min_officers=False,
        )
        result = simulate_schedule(cfg)
        self.assertTrue(result.success)
        # 6 on / 1 off → 24 work days in 28 → 288h >> 171
        self.assertGreater(result.metrics.get("flsa_violations", 0), 0)
        self.assertFalse(result.metrics.get("hard_constraints_ok", True))

    def test_auto_min_officers(self):
        from simulator import SimulatorConfig, simulate_schedule

        cfg = SimulatorConfig(
            rotation_type="2-2-3 (Dodgeville 14-day)",
            num_officers=0,
            shift_length_hours=11.0,
            annual_hours_target=2080,
            shift_starts=["06:00", "14:00", "22:00"],
            apply_department_rules=False,
            min_per_shift=1,
            simulation_days=14,
            auto_min_officers=True,
        )
        result = simulate_schedule(cfg)
        self.assertTrue(result.success, result.message)
        self.assertTrue(result.metrics.get("auto_sized") or result.metrics.get("min_officers_required", 0) >= 1)


if __name__ == "__main__":
    unittest.main()
