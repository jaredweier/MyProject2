"""Manual schedule builder + last-saved constraints (no invented form defaults)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class ManualScheduleBuildTests(unittest.TestCase):
    def test_seed_respects_off_days(self):
        from logic.manual_schedule_build import seed_grid_from_rotation

        r = seed_grid_from_rotation(
            num_officers=4,
            num_days=14,
            shift_starts=["06:00", "14:00", "19:00", "22:00"],
            rotation_type="2-2-3 (Dodgeville 14-day)",
            rotation_style="rotating",
            rotation_variations=["6-2,5-3", "6-3,5-2"],
            respect_off_days=True,
        )
        self.assertTrue(r.get("success"), r)
        grid = r["grid"]
        self.assertEqual(len(grid), 4)
        self.assertEqual(len(grid[0]), 14)
        self.assertGreater(r.get("off_cells") or 0, 0)
        self.assertGreater(r.get("on_cells") or 0, 0)

    def test_set_cell_and_evaluate(self):
        from logic.manual_schedule_build import (
            empty_grid,
            evaluate_manual_grid,
            set_cell,
        )

        g = empty_grid(2, 3)
        set_cell(g, 0, 0, "06:00")
        set_cell(g, 1, 0, "14:00")
        set_cell(g, 0, 1, "OFF")
        self.assertIsNone(g[0][1])
        self.assertEqual(g[0][0], "06:00")
        r = evaluate_manual_grid(
            g,
            shift_length_hours=8.0,
            coverage_247=0,
            annual_hours_hard=False,
        )
        self.assertTrue(r.get("success"), r)
        self.assertTrue((r.get("metrics") or {}).get("manual_build"))
        self.assertEqual((r.get("simulation_config") or {}).get("source"), "manual_build")

    def test_rotation_presets_cover_simulator_types(self):
        from config import ROTATION_PRESETS, SIMULATOR_ROTATION_TYPES

        for name in SIMULATOR_ROTATION_TYPES:
            self.assertIn(name, ROTATION_PRESETS)

    def test_form_snapshot_roundtrip_no_invent(self):
        from logic.optimizer_features import (
            form_snapshot_path,
            load_form_snapshot,
            load_last_simulator_constraints,
            save_form_snapshot,
        )

        path = form_snapshot_path()
        backup = path.read_text(encoding="utf-8") if path.is_file() else None
        try:
            payload = {
                "use_length": True,
                "length": "8",
                "use_annual": True,
                "annual": "2008",
                "use_windows": False,
                "windows": [],
                "allow_offday": False,
            }
            save_form_snapshot(payload)
            loaded = load_form_snapshot()
            self.assertEqual(loaded.get("length"), "8")
            self.assertFalse(loaded.get("use_windows"))
            last = load_last_simulator_constraints()
            self.assertIsNotNone(last)
            self.assertEqual(last.get("length"), "8")
        finally:
            if backup is None:
                if path.is_file():
                    path.unlink()
            else:
                path.write_text(backup, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
