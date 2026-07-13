"""Wrapper: feature_flow_smoke must pass (logic paths only)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class FeatureFlowSmokeTests(unittest.TestCase):
    def test_feature_flow_smoke(self):
        from scripts.feature_flow_smoke import run_feature_flow_smoke

        code = run_feature_flow_smoke()
        self.assertEqual(code, 0, "feature_flow_smoke must pass")


if __name__ == "__main__":
    unittest.main()
