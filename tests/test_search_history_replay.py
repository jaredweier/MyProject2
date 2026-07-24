import json
import unittest
from unittest.mock import patch

from logic import staffing_optimizer
from logic.optimizer_features import (
    append_search_history,
    list_search_history,
    replay_search_history,
    search_history_path,
)
from logic.scheduling_sim import clear_optimizer_cache

_BASE_KW = dict(
    rotation_types=["12hr_2days"],
    officer_counts=[6],
    min_per_shift_options=[1],
    shift_length_hours=12.0,
    annual_hours_target=2080.0,
    shift_starts=["06:00", "18:00"],
    simulation_days=28,
)


def _exhaustive_result(**overrides):
    r = {
        "success": True,
        "search_exhaustive": True,
        "budget_exhausted": False,
        "cancelled": False,
        "ranked": [{"rotation_type": "12hr_2days"}],
        "best": {"rotation_type": "12hr_2days", "num_officers": 6},
    }
    r.update(overrides)
    return r


class TestHistorySnapshotRoundTrip(unittest.TestCase):
    def setUp(self):
        self._orig = None
        p = search_history_path()
        if p.is_file():
            self._orig = p.read_text(encoding="utf-8")

    def tearDown(self):
        p = search_history_path()
        if self._orig is not None:
            p.write_text(self._orig, encoding="utf-8")
        elif p.is_file():
            p.unlink()

    def test_config_snapshot_round_trips(self):
        append_search_history(
            {
                "success": True,
                "message": "ok",
                "num_officers": 6,
                "wall_time_ms": 123,
                "scenarios_evaluated": 10,
                "hard_ok": True,
                "search_exhaustive": True,
                "config_snapshot": dict(_BASE_KW),
            }
        )
        rows = list_search_history(limit=1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["config_snapshot"], json.loads(json.dumps(_BASE_KW)))
        self.assertTrue(rows[0]["search_exhaustive"])


class TestReplay(unittest.TestCase):
    def setUp(self):
        clear_optimizer_cache()

    def tearDown(self):
        clear_optimizer_cache()

    def test_replay_hits_cache_for_exhaustive_original(self):
        with patch.object(
            staffing_optimizer, "optimize_staffing_scenarios", return_value=_exhaustive_result()
        ) as mock_solve:
            from logic.scheduling_sim import run_staffing_optimizer

            original = run_staffing_optimizer(**_BASE_KW)
            entry = {"config_snapshot": dict(_BASE_KW), "search_exhaustive": original["search_exhaustive"]}

            replayed = replay_search_history(entry)

            self.assertEqual(mock_solve.call_count, 1)  # replay hit the cache, no second solve
            self.assertTrue(replayed["replay_original_exhaustive"])
            self.assertEqual(replayed["best"], original["best"])

    def test_replay_of_truncated_original_is_honest_resolve(self):
        truncated = _exhaustive_result(search_exhaustive=False, budget_exhausted=True)
        with patch.object(staffing_optimizer, "optimize_staffing_scenarios", return_value=truncated) as mock_solve:
            from logic.scheduling_sim import run_staffing_optimizer

            run_staffing_optimizer(**_BASE_KW)
            entry = {"config_snapshot": dict(_BASE_KW), "search_exhaustive": False}

            replayed = replay_search_history(entry)

            self.assertEqual(mock_solve.call_count, 2)  # truncated original never cached, fresh re-solve
            self.assertFalse(replayed["replay_original_exhaustive"])
            self.assertIn("fresh re-solve", replayed["replay_note"])

    def test_replay_missing_snapshot_reported_honestly(self):
        result = replay_search_history({"success": True})
        self.assertFalse(result["success"])
        self.assertIn("snapshot", result["message"])


if __name__ == "__main__":
    unittest.main()
