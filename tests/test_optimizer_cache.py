import unittest
from unittest.mock import patch

from logic import staffing_optimizer
from logic.scheduling_sim import _optimizer_cache_key, clear_optimizer_cache, run_staffing_optimizer

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
        "best": {"rotation_type": "12hr_2days"},
    }
    r.update(overrides)
    return r


class OptimizerCacheTests(unittest.TestCase):
    def setUp(self):
        clear_optimizer_cache()

    def tearDown(self):
        clear_optimizer_cache()

    def test_identical_job_hits_cache_second_call(self):
        with patch.object(
            staffing_optimizer, "optimize_staffing_scenarios", return_value=_exhaustive_result()
        ) as mock_solve:
            r1 = run_staffing_optimizer(**_BASE_KW)
            r2 = run_staffing_optimizer(**_BASE_KW)
        self.assertEqual(mock_solve.call_count, 1)  # second call was a cache hit
        self.assertIs(r1, r2)

    def test_changing_deterministic_input_misses_cache(self):
        with patch.object(
            staffing_optimizer, "optimize_staffing_scenarios", return_value=_exhaustive_result()
        ) as mock_solve:
            run_staffing_optimizer(**_BASE_KW)
            kw2 = dict(_BASE_KW, officer_counts=[7])
            run_staffing_optimizer(**kw2)
        self.assertEqual(mock_solve.call_count, 2)

    def test_cache_key_changes_with_availability_style_input(self):
        key_a = _optimizer_cache_key(dict(_BASE_KW, shift_starts=["06:00", "18:00"]))
        key_b = _optimizer_cache_key(dict(_BASE_KW, shift_starts=["07:00", "19:00"]))
        self.assertNotEqual(key_a, key_b)

    def test_time_limited_result_not_cached(self):
        budget_result = _exhaustive_result(search_exhaustive=False, budget_exhausted=True)
        with patch.object(staffing_optimizer, "optimize_staffing_scenarios", return_value=budget_result) as mock_solve:
            run_staffing_optimizer(**_BASE_KW, time_budget_seconds=5.0)
            run_staffing_optimizer(**_BASE_KW, time_budget_seconds=5.0)
        # both calls re-solved — a budget-truncated "best so far" is not
        # replayed as if it were a reproducible, complete answer.
        self.assertEqual(mock_solve.call_count, 2)

    def test_cancelled_result_not_cached(self):
        cancelled_result = _exhaustive_result(search_exhaustive=False, cancelled=True)
        with patch.object(
            staffing_optimizer, "optimize_staffing_scenarios", return_value=cancelled_result
        ) as mock_solve:
            run_staffing_optimizer(**_BASE_KW)
            run_staffing_optimizer(**_BASE_KW)
        self.assertEqual(mock_solve.call_count, 2)

    def test_progress_and_cancel_callables_excluded_from_key(self):
        with patch.object(
            staffing_optimizer, "optimize_staffing_scenarios", return_value=_exhaustive_result()
        ) as mock_solve:
            run_staffing_optimizer(**_BASE_KW, progress_callback=lambda **k: None)
            run_staffing_optimizer(**_BASE_KW, cancel_check=lambda: False)
        self.assertEqual(mock_solve.call_count, 1)


if __name__ == "__main__":
    unittest.main()
