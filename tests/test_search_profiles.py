import unittest
from pathlib import Path

from gui.pages.simulator.state import SEARCH_PROFILES, SimulatorState


class SearchProfilePresetTests(unittest.TestCase):
    def test_quick_is_short_and_first_feasible_leaning(self):
        quick = SEARCH_PROFILES["quick"]
        deep = SEARCH_PROFILES["deep_proof"]
        self.assertLess(quick["time_budget_seconds"], deep["time_budget_seconds"])
        self.assertEqual(quick["search_depth"], "standard")

    def test_deep_proof_is_longest_and_strongest(self):
        balanced = SEARCH_PROFILES["balanced"]
        deep = SEARCH_PROFILES["deep_proof"]
        self.assertGreater(deep["time_budget_seconds"], balanced["time_budget_seconds"])
        self.assertEqual(deep["search_depth"], "deep")

    def test_balanced_matches_pre_existing_default_behavior(self):
        # Balanced must equal what standard-depth search already did before
        # profiles existed (page.py's old unconditional 120.0 default).
        balanced = SEARCH_PROFILES["balanced"]
        self.assertEqual(balanced["time_budget_seconds"], 120.0)
        self.assertEqual(balanced["search_depth"], "standard")

    def test_custom_is_not_a_preset_key(self):
        # "custom" must not appear in SEARCH_PROFILES: the override logic in
        # page.py keys off "not in SEARCH_PROFILES" to mean no-op / manual
        # controls apply as-is. Adding a "custom" entry here would silently
        # break that no-op behavior.
        self.assertNotIn("custom", SEARCH_PROFILES)

    def test_default_state_profile_is_custom(self):
        # Default must be a no-op so existing callers/tests are unaffected.
        st = SimulatorState()
        self.assertEqual(st.search_profile, "custom")


class SearchProfileWiringStaticTests(unittest.TestCase):
    def test_page_wires_profile_override_and_disable_pattern(self):
        text = (Path(__file__).resolve().parents[1] / "gui" / "pages" / "simulator" / "page.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("SEARCH_PROFILES", text)
        self.assertIn('state["search_profile"]', text)
        # Custom leaves the manual Depth toggle editable (existing
        # disable/remove=disable pattern used elsewhere in this file).
        self.assertIn('search_depth.props("disable")', text)
        self.assertIn('search_depth.props(remove="disable")', text)


if __name__ == "__main__":
    unittest.main()
