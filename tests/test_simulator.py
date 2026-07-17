import os
import tempfile
import unittest

from simulator import SimulatorConfig, generate_shift_templates, simulate_schedule
from tests.helpers import get_any_officer, test_database


class SimulatorTests(unittest.TestCase):
    def test_generate_shift_templates_auto(self):
        templates = generate_shift_templates(8.0)
        self.assertGreaterEqual(len(templates), 3)
        self.assertEqual(templates[0][0], "00:00")
        self.assertEqual(templates[0][1], "08:00")

    def test_simulate_dodgeville_rotation(self):
        config = SimulatorConfig(
            rotation_type="2-2-3 (Dodgeville 14-day)",
            num_officers=16,
            shift_length_hours=11.0,
            annual_hours_target=2080.0,
            shift_starts=["06:00", "10:00", "15:00", "19:00"],
            apply_department_rules=True,
        )
        result = simulate_schedule(config)
        self.assertTrue(result.success)
        self.assertEqual(len(result.officer_slots), 16)
        self.assertGreater(result.metrics["coverage_percent"], 0)
        self.assertGreater(len(result.suggestions), 0)

    def test_simulate_understaffed_critical(self):
        config = SimulatorConfig(
            rotation_type="2-2-3 (Dodgeville 14-day)",
            num_officers=4,
            shift_length_hours=12.0,
            annual_hours_target=2080.0,
            shift_starts=["06:00", "18:00"],
            apply_department_rules=False,
            min_per_shift=2,
        )
        result = simulate_schedule(config)
        self.assertTrue(result.success)
        severities = {s.severity for s in result.suggestions}
        self.assertIn("critical", severities)

    def test_run_schedule_simulation_via_logic(self):
        with test_database():
            from logic.scheduling_sim import run_schedule_simulation

            result = run_schedule_simulation(
                "4-on-4-off",
                12,
                10.0,
                2080.0,
                ["06:00", "16:00"],
                apply_department_rules=False,
                min_per_shift=1,
            )
            self.assertTrue(result["success"])
            self.assertIn("metrics", result)

    def test_project_officer_annual_pay(self):
        with test_database():
            import logic

            officer = get_any_officer("A")
            proj = logic.project_officer_annual_pay(officer["id"])
            self.assertTrue(proj["success"])
            self.assertGreater(proj["annual_hours"], 0)
            self.assertGreater(proj["total_annual_pay"], 0)

    def test_bulk_adjust_pay_rates(self):
        with test_database():
            import logic

            officer = get_any_officer("A")
            before = officer["pay_rate"]
            result = logic.bulk_adjust_pay_rates(percent_change=10.0, squad="A")
            self.assertTrue(result["success"])
            updated = logic.get_officer_by_id(officer["id"])
            self.assertAlmostEqual(updated["pay_rate"], before * 1.1, places=1)

    def test_export_simulation_csv(self):
        with test_database():
            import logic
            from logic.scheduling_sim import run_schedule_simulation

            result = run_schedule_simulation(
                rotation_type="2-2-3 (Dodgeville 14-day)",
                num_officers=12,
                shift_length_hours=11.0,
                annual_hours_target=2080.0,
                shift_starts=["06:00", "10:00", "15:00", "19:00"],
            )
            self.assertTrue(result["success"], result.get("message"))
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "sim.csv")
                exported = logic.export_simulation_csv(result, output_path=path)
                self.assertTrue(exported["success"], exported.get("message"))
                self.assertGreaterEqual(exported["count"], 1)
                with open(path, encoding="utf-8") as fh:
                    content = fh.read()
                self.assertIn("shift_start", content)


if __name__ == "__main__":
    unittest.main()
