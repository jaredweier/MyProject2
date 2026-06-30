"""Tests for batch_process — index-aligned JSON array output."""

import json
import os
import tempfile
import unittest

from scripts.batch_process import process_batch, run_batch_process


class BatchProcessTests(unittest.TestCase):
    def test_classification_index_aligned(self):
        from scripts.structured_output import shape_batch_results

        items = ["fix day-off bump", "explain payroll tab", "typo in comment"]
        raw = process_batch("classification", items, workers=1)
        out = shape_batch_results("classification", raw)
        self.assertEqual(len(out), 3)
        self.assertEqual([r["index"] for r in out], [0, 1, 2])
        self.assertEqual(out[0]["slice_id"], "scheduling")
        self.assertEqual(out[1]["slice_id"], "payroll-timecard")
        self.assertEqual(out[2]["complexity"], "trivial")

    def test_validation_mixed_items(self):
        from scripts.structured_output import shape_batch_results

        items = ["2026-07-10", {"name": "", "email": "bad"}]
        out = shape_batch_results("validation", process_batch("validation", items, workers=1))
        self.assertEqual(len(out), 2)
        self.assertTrue(out[0]["ok"])
        self.assertFalse(out[1]["ok"])

    def test_extraction_finds_dates_and_paths(self):
        from scripts.structured_output import shape_batch_results

        text = "edit logic/requests.py on 2026-07-01 for process_day_off_request()"
        out = shape_batch_results("extraction", process_batch("extraction", [text], workers=1))
        self.assertEqual(out[0]["index"], 0)
        self.assertIn("logic/requests.py", out[0]["paths"])
        self.assertTrue(out[0]["valid_dates"])

    def test_scoring_and_summarization(self):
        from scripts.structured_output import shape_batch_results

        items = ["refactor logic package split across modules"]
        score = shape_batch_results("scoring", process_batch("scoring", items))[0]
        summary = shape_batch_results("summarization", process_batch("summarization", items))[0]
        self.assertGreaterEqual(score["score"], 50)
        self.assertIn("preview", summary)

    def test_parallel_same_length(self):
        items = [f"task {i} ui widget" for i in range(6)]
        out = process_batch("classification", items, workers=4)
        self.assertEqual(len(out), len(items))
        for i, row in enumerate(out):
            self.assertEqual(row["index"], i)

    def test_cli_writes_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            inp = os.path.join(tmp, "in.json")
            out_path = os.path.join(tmp, "out.json")
            with open(inp, "w", encoding="utf-8") as fh:
                json.dump({"items": ["verify tests pass"]}, fh)
            code = run_batch_process(
                "classification",
                input_path=inp,
                output_path=out_path,
                quiet=True,
            )
            self.assertEqual(code, 0)
            with open(out_path, encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["index"], 0)


if __name__ == "__main__":
    unittest.main()
