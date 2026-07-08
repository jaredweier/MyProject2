"""Rust bridge and scheduling math parity (Python fallback always; Rust when built)."""

import unittest
from datetime import date
from unittest.mock import patch

from config import ROTATION_BASE_DATE, ROTATION_CYCLE_LENGTH
from logic import rust_bridge


class RustBridgeTests(unittest.TestCase):
    def test_cycle_day_python_path(self):
        target = date(2026, 7, 10)
        day = rust_bridge.get_cycle_day(target, ROTATION_BASE_DATE, ROTATION_CYCLE_LENGTH)
        self.assertGreaterEqual(day, 1)
        self.assertLessEqual(day, ROTATION_CYCLE_LENGTH)

    def test_squad_on_duty(self):
        self.assertEqual(rust_bridge.get_squad_on_duty(1), "A")
        self.assertEqual(rust_bridge.get_squad_on_duty(3), "B")

    def test_backend_reports_python_when_extension_missing(self):
        if rust_bridge.available():
            self.assertEqual(rust_bridge.backend_name(), "rust")
        else:
            self.assertEqual(rust_bridge.backend_name(), "python")

    def test_rust_matches_python_cycle_day_when_built(self):
        if not rust_bridge.available():
            self.skipTest("scheduler_core extension not built")
        import scheduler_core

        iso = "2026-07-15"
        self.assertEqual(
            scheduler_core.get_cycle_day(ROTATION_BASE_DATE.isoformat(), iso, ROTATION_CYCLE_LENGTH),
            rust_bridge.get_cycle_day(date(2026, 7, 15), ROTATION_BASE_DATE, ROTATION_CYCLE_LENGTH),
        )

    def test_rust_matches_python_custom_squad_schedule_when_built(self):
        if not rust_bridge.available():
            self.skipTest("scheduler_core extension not built")
        schedule = {
            "mode": "squad_a_days",
            "cycle_length": 14,
            "squad_a_days": [1, 2, 3, 4, 5, 6, 7],
        }
        import scheduler_core

        for day in range(1, 15):
            py = "A" if day in schedule["squad_a_days"] else "B"
            rust = scheduler_core.get_squad_on_duty(day, schedule)
            self.assertEqual(rust, py, f"day {day}")

    def test_rust_batch_day_status_matches_python_when_built(self):
        if not rust_bridge.available():
            self.skipTest("scheduler_core extension not built")
        from tests.helpers import test_database, working_date_for_squad

        with test_database():
            import logic

            target = working_date_for_squad("A")
            officers = [o for o in logic.get_officers_by_seniority() if o.get("active") == 1]
            pairs = [(officers[0]["id"], target), (officers[-1]["id"], target)]
            with patch.object(rust_bridge, "_RUST", None):
                py_statuses = logic.batch_officer_day_status(pairs)
            rust_statuses = logic.batch_officer_day_status(pairs)
            self.assertEqual(py_statuses, rust_statuses)

    def test_rust_officer_rotation_working_when_built(self):
        if not rust_bridge.available():
            self.skipTest("scheduler_core extension not built")
        from tests.helpers import off_date_for_squad, test_database, working_date_for_squad

        with test_database():
            import logic
            from validators import officer_uses_command_staff_schedule

            patrol = next(
                o
                for o in logic.get_officers_by_seniority()
                if o.get("active") == 1 and not officer_uses_command_staff_schedule(o)
            )
            work_day = working_date_for_squad(patrol["squad"])
            off_day = off_date_for_squad(patrol["squad"])
            self.assertTrue(logic.officer_base_rotation_working(patrol, work_day))
            self.assertFalse(logic.officer_base_rotation_working(patrol, off_day))

    def test_rust_bump_chain_on_duty_when_built(self):
        if not rust_bridge.available():
            self.skipTest("scheduler_core extension not built")
        from tests.helpers import test_database, working_date_for_squad
        from validators import officer_uses_command_staff_schedule

        with test_database():
            import logic

            officers = [
                o
                for o in logic.get_officers_by_seniority()
                if o["squad"] == "A" and o["shift_start"] == "15:00" and not officer_uses_command_staff_schedule(o)
            ]
            officer = officers[0]
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            suggestion = logic.suggest_bump_chain(officer["id"], work_day, officer["squad"], officer["shift_start"])
            self.assertTrue(suggestion.success, suggestion.message)
            self.assertTrue(suggestion.steps)
            self.assertTrue(all(step.replacement_on_duty for step in suggestion.steps))

    def test_rust_bump_chain_matches_python_fallback_when_built(self):
        if not rust_bridge.available():
            self.skipTest("scheduler_core extension not built")
        from tests.helpers import test_database, working_date_for_squad
        from validators import officer_uses_command_staff_schedule

        with test_database():
            import logic

            officer = next(
                o
                for o in logic.get_officers_by_seniority()
                if o["squad"] == "A" and o["shift_start"] == "06:00" and not officer_uses_command_staff_schedule(o)
            )
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            with patch.object(rust_bridge, "_RUST", None):
                py_suggestion = logic.suggest_bump_chain(
                    officer["id"], work_day, officer["squad"], officer["shift_start"]
                )
            rust_suggestion = logic.suggest_bump_chain(
                officer["id"], work_day, officer["squad"], officer["shift_start"]
            )
            self.assertEqual(py_suggestion.success, rust_suggestion.success)
            self.assertEqual(len(py_suggestion.chain), len(rust_suggestion.chain))
            self.assertEqual(
                [s.replacement_officer_id for s in py_suggestion.steps],
                [s.replacement_officer_id for s in rust_suggestion.steps],
            )

    def test_rust_minimum_rest_gap_matches_python_when_built(self):
        if not rust_bridge.available():
            self.skipTest("scheduler_core extension not built")
        from tests.helpers import test_database, working_date_for_squad

        with test_database():
            import logic

            patrol = next(
                o for o in logic.get_officers_by_seniority() if o.get("active") == 1 and o.get("squad") == "A"
            )
            work_day = working_date_for_squad("A")
            from logic.shift_assignment import shift_end_for_start

            shift_end = shift_end_for_start(patrol["shift_start"])
            with patch.object(rust_bridge, "_RUST", None):
                py_gap = logic.compute_minimum_rest_gap(patrol["id"], work_day, patrol["shift_start"], shift_end)
            rust_gap = logic.compute_minimum_rest_gap(patrol["id"], work_day, patrol["shift_start"], shift_end)
            self.assertEqual(py_gap, rust_gap)

    def test_rust_consecutive_work_days_when_built(self):
        if not rust_bridge.available():
            self.skipTest("scheduler_core extension not built")
        from logic.labor_compliance import count_consecutive_work_days_ending
        from tests.helpers import test_database, working_date_for_squad

        with test_database():
            import logic

            patrol = next(
                o for o in logic.get_officers_by_seniority() if o.get("active") == 1 and o.get("squad") == "A"
            )
            work_day = working_date_for_squad("A")
            streak = count_consecutive_work_days_ending(patrol["id"], work_day)
            self.assertGreaterEqual(streak, 1)
            self.assertLessEqual(streak, 20)

    def test_rust_simulator_engine_when_built(self):
        if not rust_bridge.available():
            self.skipTest("scheduler_core extension not built")
        from simulator import SimulatorConfig, simulate_schedule

        config = SimulatorConfig(
            rotation_type="2-2-3 (Dodgeville 14-day)",
            num_officers=12,
            shift_length_hours=11.0,
            annual_hours_target=2080.0,
            shift_starts=["06:00", "10:00", "15:00", "19:00"],
            apply_department_rules=True,
            min_per_shift=1,
            simulation_days=14,
        )
        result = simulate_schedule(config)
        self.assertTrue(result.success)
        self.assertEqual(result.compute_backend, "rust")
        self.assertGreater(len(result.coverage_by_day), 0)


if __name__ == "__main__":
    unittest.main()
