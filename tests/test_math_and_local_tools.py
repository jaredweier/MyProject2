"""Tests for math scenarios, CP-SAT bridge, and local dispatch."""

import unittest


class LocalDispatchTests(unittest.TestCase):
    def test_verify_task_is_free_machine(self):
        from scripts.local_dispatch import plan_local

        plan = plan_local("run verify and tests")
        self.assertEqual(plan.lane, "free-machine")
        self.assertTrue(any("verify" in c for c in plan.commands))

    def test_typo_is_free_machine(self):
        from scripts.local_dispatch import plan_local

        plan = plan_local("fix typo in label")
        self.assertEqual(plan.lane, "free-machine")


class CpSatBridgeTests(unittest.TestCase):
    def test_demo_instance_shape(self):
        from logic.cp_sat_bridge import demo_week_instance

        inst = demo_week_instance(n_officers=4, n_days=3)
        self.assertEqual(len(inst.officer_ids), 4)
        self.assertEqual(len(inst.days), 3)
        self.assertIn("19:00", inst.bands)

    def test_solve_when_ortools_present_or_skip(self):
        from logic.cp_sat_bridge import demo_week_instance, ortools_available, solve_staffing_feasibility

        sol = solve_staffing_feasibility(demo_week_instance(n_officers=8, n_days=5), time_limit_sec=5.0)
        if not ortools_available():
            self.assertFalse(sol.available)
            return
        self.assertTrue(sol.available)
        self.assertTrue(sol.feasible, sol.message)


class MathScenariosSmoke(unittest.TestCase):
    def test_math_scenarios_exit_zero(self):
        from scripts.math_scenarios import run_math_scenarios

        # Include CP-SAT if installed; still must pass without requiring it
        code = run_math_scenarios(with_cpsat=True, require_cpsat=False)
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
