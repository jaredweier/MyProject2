"""Constraint suggestion engine — options from already-locked fields."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class ConstraintSuggestTests(unittest.TestCase):
    def test_annual_from_length_and_pattern(self):
        from logic.constraint_suggest import suggest_constraint

        r = suggest_constraint(
            "annual",
            {
                "use_length": True,
                "length": "8",
                "use_style": True,
                "variations": "6-2,5-3 | 6-3,5-2",
            },
        )
        self.assertTrue(r.get("success"))
        self.assertTrue(r.get("allow_custom"))
        opts = r.get("options") or []
        self.assertGreaterEqual(len(opts), 1)
        rec = next(o for o in opts if o.get("recommended"))
        ann = int(rec["values"]["annual"])
        self.assertAlmostEqual(ann, 2008, delta=5)

    def test_officers_from_windows_and_247(self):
        from logic.constraint_suggest import suggest_constraint

        r = suggest_constraint(
            "officers",
            {
                "use_length": True,
                "length": "8",
                "use_247": True,
                "cov247": "1",
                "use_windows": True,
                "windows": [
                    {"min_officers": 2, "enabled": True},
                    {"min_officers": 2, "enabled": True},
                ],
            },
        )
        rec = next(o for o in r["options"] if o.get("recommended"))
        self.assertEqual(str(rec["values"]["officers"]), "8")

    def test_starts_for_12h(self):
        from logic.constraint_suggest import suggest_constraint

        r = suggest_constraint(
            "starts",
            {"use_length": True, "length": "12"},
        )
        labels = " ".join(o["label"] for o in r["options"])
        self.assertIn("06:00", labels)
        self.assertIn("18:00", labels)

    def test_empty_context_still_has_options(self):
        from logic.constraint_suggest import (
            context_has_locked_constraints,
            suggest_constraint,
        )

        self.assertFalse(context_has_locked_constraints({}))
        r = suggest_constraint("length", {})
        self.assertGreaterEqual(len(r.get("options") or []), 1)


if __name__ == "__main__":
    unittest.main()
