import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers import test_database


class OptimizedScheduleApplyTests(unittest.TestCase):
    def setUp(self):
        self._db_cm = test_database()
        self._db_cm.__enter__()

    def tearDown(self):
        self._db_cm.__exit__(None, None, None)

    def test_recommend_pay_period_dates(self):
        from logic.optimized_schedule_apply import recommend_implement_dates

        rec = recommend_implement_dates()
        self.assertTrue(rec.get("success"))
        self.assertTrue(rec.get("recommended_date"))
        self.assertGreaterEqual(len(rec.get("options") or []), 2)

    def test_coverage_windows_crud(self):
        from logic.coverage_windows_store import (
            add_coverage_window,
            delete_coverage_window,
            get_active_coverage_windows,
            get_coverage_247_minimum,
            list_coverage_windows,
            set_coverage_247_minimum,
        )

        set_coverage_247_minimum(1)
        self.assertEqual(get_coverage_247_minimum(), 1)
        r = add_coverage_window(
            min_officers=2,
            start_time="19:00",
            end_time="03:00",
            weekday=4,
            label="Fri night",
        )
        self.assertTrue(r.get("success"), r)
        self.assertGreaterEqual(len(list_coverage_windows()), 1)
        self.assertGreaterEqual(len(get_active_coverage_windows()), 1)
        wid = list_coverage_windows()[0]["id"]
        d = delete_coverage_window(wid)
        self.assertTrue(d.get("success"))

    def test_format_and_implement_plan(self):
        from logic.optimized_schedule_apply import (
            format_optimized_plan_view,
            get_schedule_builder_defaults,
            implement_optimized_plan,
            save_last_optimized_plan,
        )
        from logic.scheduling_sim import run_schedule_simulation
        from logic.snapshots import get_schedule_snapshot

        sim = run_schedule_simulation(
            rotation_type="2-2-3 (Dodgeville 14-day)",
            num_officers=12,
            shift_length_hours=11.0,
            annual_hours_target=2080,
            shift_starts=["06:00", "14:00", "22:00"],
            apply_department_rules=False,
            min_per_shift=1,
            simulation_days=14,
            auto_min_officers=False,
        )
        self.assertTrue(sim.get("success"), sim.get("message"))
        view = format_optimized_plan_view(sim, sim.get("simulation_config"))
        self.assertTrue(view.get("success"))
        self.assertIn("slots", view)

        cfg = {
            "rotation_type": "2-2-3 (Dodgeville 14-day)",
            "num_officers": 12,
            "shift_length_hours": 11.0,
            "annual_hours_target": 2080,
            "shift_starts": ["06:00", "14:00", "22:00"],
            "min_per_shift": 1,
            "annual_hours_variance": 40,
        }
        save_last_optimized_plan(sim, cfg)
        impl = implement_optimized_plan(
            start_date="2026-09-01",
            result=sim,
            config=cfg,
            apply_officer_assignments=True,
            force_regenerate=True,
            save_as_defaults=True,
        )
        self.assertTrue(impl.get("success"), impl.get("message"))
        defaults = get_schedule_builder_defaults()
        self.assertEqual(defaults.get("source"), "optimized_plan")
        base = get_schedule_snapshot(2026, 9, "base")
        live = get_schedule_snapshot(2026, 9, "updated")
        self.assertTrue(base)
        self.assertTrue(live)

    def test_officer_rotation_pattern_duty(self):
        from datetime import timedelta

        from logic.officers import get_officer_by_id, get_officers_by_seniority, update_officer
        from logic.rotation_config import get_active_rotation_base_date
        from logic.scheduling import officer_base_rotation_working

        officers = [o for o in get_officers_by_seniority() if o.get("active") == 1 and o.get("squad")]
        self.assertTrue(officers)
        o = officers[0]
        update_officer(o["id"], rotation_pattern="5-2", rotation_phase=0)
        refreshed = get_officer_by_id(o["id"])
        base = get_active_rotation_base_date()
        self.assertTrue(officer_base_rotation_working(refreshed, base))
        day6 = base + timedelta(days=5)
        self.assertFalse(officer_base_rotation_working(refreshed, day6))


if __name__ == "__main__":
    unittest.main()
