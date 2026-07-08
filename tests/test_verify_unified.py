"""Unified verification — tiers must be strict supersets, no duplicate/conflicting gates."""

import unittest

from scripts.verify import (
    STEP_CHECK,
    STEP_FAST,
    STEP_FULL,
    STEP_PREFLIGHT,
    is_subset,
    tier_steps,
)


class VerifyUnifiedTests(unittest.TestCase):
    def test_fast_subset_of_preflight(self):
        self.assertTrue(is_subset("fast", "preflight"))

    def test_preflight_subset_of_check(self):
        self.assertTrue(is_subset("preflight", "check"))

    def test_check_subset_of_full(self):
        self.assertTrue(is_subset("check", "full"))

    def test_full_subset_of_release(self):
        self.assertTrue(is_subset("full", "release"))

    def test_no_duplicate_steps_in_check(self):
        steps = tier_steps("check")
        self.assertEqual(len(steps), len(set(steps)), f"duplicate steps: {steps}")

    def test_readiness_in_fast_and_preflight(self):
        self.assertIn("readiness", STEP_FAST)
        self.assertIn("readiness", STEP_PREFLIGHT)

    def test_audit_runs_once_in_check(self):
        self.assertEqual(tier_steps("check").count("audit"), 1)

    def test_check_includes_test_and_scenarios(self):
        self.assertIn("test", STEP_CHECK)
        self.assertIn("scenarios", STEP_CHECK)

    def test_full_includes_smoke_and_ui_smoke(self):
        self.assertIn("smoke", STEP_FULL)
        self.assertIn("ui-smoke", STEP_FULL)
        self.assertIn("ui-workflow", STEP_FULL)

    def test_check_includes_rust_backend(self):
        self.assertIn("rust-backend", STEP_CHECK)

    def test_tier_alias_cheap_check(self):
        self.assertEqual(tier_steps("cheap-check"), tier_steps("fast"))


if __name__ == "__main__":
    unittest.main()
