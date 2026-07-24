import unittest

from logic.optimizer_features import wall_time_p95, wall_time_p95_report


def _rows(times, num_officers=25):
    return [{"wall_time_ms": t, "num_officers": num_officers} for t in times]


class TestWallTimeP95(unittest.TestCase):
    def test_empty_list_not_enough_data(self):
        res = wall_time_p95([])
        self.assertFalse(res["ok"])
        self.assertEqual(res["n"], 0)
        self.assertIn("Not enough data", res["message"])

    def test_single_entry_not_enough_data(self):
        res = wall_time_p95(_rows([1000]))
        self.assertFalse(res["ok"])
        self.assertEqual(res["n"], 1)

    def test_below_min_samples_default_threshold(self):
        # 4 samples < default min_samples=5 -> refuse
        res = wall_time_p95(_rows([100, 200, 300, 400]))
        self.assertFalse(res["ok"])
        self.assertEqual(res["n"], 4)

    def test_known_input_known_output_nearest_rank(self):
        # 20 samples: 100ms..2000ms in 100ms steps. nearest-rank p95 of n=20
        # is index ceil(0.95*20)-1 = 18 (1-indexed 19th) -> value 1900.
        times = [i * 100 for i in range(1, 21)]
        res = wall_time_p95(_rows(times), min_samples=5)
        self.assertTrue(res["ok"])
        self.assertEqual(res["n"], 20)
        self.assertEqual(res["p95_ms"], 1900)
        self.assertEqual(res["p95_s"], 1.9)

    def test_exact_percentile_boundary_n_20_matches_manual_calc(self):
        # order-independent: shuffle input, result should be identical
        times = [
            2000,
            100,
            1900,
            300,
            1800,
            500,
            700,
            900,
            1100,
            1300,
            1500,
            1700,
            200,
            400,
            600,
            800,
            1000,
            1200,
            1400,
            1600,
        ]
        res = wall_time_p95(_rows(times), min_samples=5)
        self.assertEqual(res["p95_ms"], 1900)

    def test_min_samples_override(self):
        res = wall_time_p95(_rows([100, 200, 300]), min_samples=2)
        self.assertTrue(res["ok"])
        self.assertEqual(res["n"], 3)

    def test_drops_missing_or_non_numeric_wall_time(self):
        rows = [
            {"wall_time_ms": 100, "num_officers": 10},
            {"wall_time_ms": None, "num_officers": 10},
            {"num_officers": 10},
            {"wall_time_ms": "bad", "num_officers": 10},
            {"wall_time_ms": 200, "num_officers": 10},
        ]
        res = wall_time_p95(rows, min_samples=2)
        self.assertTrue(res["ok"])
        self.assertEqual(res["n"], 2)

    def test_officer_bucket_filter(self):
        rows = _rows([100, 200, 300, 400, 500], num_officers=20) + _rows(
            [9000, 9100, 9200, 9300, 9400], num_officers=90
        )
        res_25 = wall_time_p95(rows, officer_bucket=25, min_samples=5)
        res_100 = wall_time_p95(rows, officer_bucket=100, min_samples=5)
        self.assertTrue(res_25["ok"])
        self.assertTrue(res_100["ok"])
        self.assertEqual(res_25["n"], 5)
        self.assertEqual(res_100["n"], 5)
        self.assertLess(res_25["p95_ms"], res_100["p95_ms"])

    def test_report_text_includes_buckets(self):
        rows = _rows([100, 200, 300, 400, 500], num_officers=20)
        # wall_time_p95_report reads from list_search_history internally when
        # called with no args; here we just check wall_time_p95 composes into
        # text the same way the report does, via direct rows.
        overall = wall_time_p95(rows)
        self.assertTrue(overall["ok"])
        # sanity check the report function itself doesn't crash on live store
        text = wall_time_p95_report()
        self.assertIn("Optimizer wall-time p95", text)
        self.assertIn("overall:", text)
        self.assertIn("<= 25 officers", text)
        self.assertIn("<= 100 officers", text)
        self.assertIn("<= 500 officers", text)


if __name__ == "__main__":
    unittest.main()
