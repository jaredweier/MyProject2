"""Import-boundary guards for generator / optimizer / payroll separation."""

import unittest


class ThreeBrainsBoundaryTests(unittest.TestCase):
    def test_scheduling_generator_does_not_export_optimizer(self):
        import logic.scheduling as scheduling

        for name in (
            "suggest_bump_chain",
            "validate_bump_feasibility",
            "plan_bump_chain",
            "format_bump_suggestion",
            "run_schedule_simulation",
            "run_staffing_optimizer",
            "preview_best_coverage_plans",
            "estimate_staffing_search_space",
            "get_simulator_defaults_from_roster",
        ):
            self.assertFalse(
                hasattr(scheduling, name),
                f"generator facade still exports optimizer API: {name}",
            )

    def test_optimizer_public_surface(self):
        from logic import coverage_optimizer, scheduling_sim

        self.assertTrue(callable(coverage_optimizer.suggest_bump_chain))
        self.assertTrue(callable(coverage_optimizer.optimize_day_off_coverage))
        self.assertTrue(callable(scheduling_sim.run_schedule_simulation))
        self.assertTrue(callable(scheduling_sim.run_staffing_optimizer))

    def test_bump_impl_module_is_bump_optimizer(self):
        import logic.bump_optimizer as bump

        self.assertTrue(callable(bump.suggest_bump_chain))
        self.assertTrue(callable(bump.find_replacement_officer))

    def test_no_scheduling_bump_module(self):
        import importlib.util

        self.assertIsNone(
            importlib.util.find_spec("logic.scheduling_bump"),
            "scheduling_bump shim should be removed; use bump_optimizer",
        )

    def test_payroll_does_not_import_optimizer(self):
        import ast
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent / "logic" / "payroll"
        banned = (
            "coverage_optimizer",
            "bump_optimizer",
            "scheduling_sim",
            "staffing_optimizer",
            "ot_fill",
            "optimized_schedule_apply",
        )
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    mod = node.module
                    for bad in banned:
                        self.assertNotIn(
                            bad,
                            mod,
                            f"{path.name} imports optimizer module {mod}",
                        )

    def test_optimizer_apply_does_not_import_payroll_package(self):
        import ast
        from pathlib import Path

        path = Path(__file__).resolve().parent.parent / "logic" / "optimized_schedule_apply.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                self.assertFalse(
                    node.module.startswith("logic.payroll"),
                    f"optimized_schedule_apply imports payroll: {node.module}",
                )

    def test_package_does_not_reexport_optimizer(self):
        import logic

        for name in (
            "suggest_bump_chain",
            "validate_bump_feasibility",
            "run_schedule_simulation",
            "run_staffing_optimizer",
            "preview_best_coverage_plans",
        ):
            self.assertFalse(
                hasattr(logic, name),
                f"import logic still re-exports optimizer API: {name}",
            )

    def test_logic_resolve_finds_optimizer_on_brain_modules(self):
        from scripts.logic_resolve import logic_has, resolve_logic

        self.assertTrue(logic_has("suggest_bump_chain"))
        self.assertTrue(logic_has("run_schedule_simulation"))
        self.assertTrue(callable(resolve_logic("suggest_bump_chain")))
        self.assertTrue(callable(resolve_logic("run_schedule_simulation")))


if __name__ == "__main__":
    unittest.main()
