"""Tests for structured JSON output schemas."""

import json
import unittest

from scripts.agent_route import route_task
from scripts.batch_process import process_batch
from scripts.structured_output import (
    BATCH_FIELDS,
    dump_json,
    shape_batch_results,
    shape_route,
)


class StructuredOutputTests(unittest.TestCase):
    def test_batch_flat_fields_only(self):
        raw = process_batch("classification", ["fix bump", "ui tab"], workers=1)
        out = shape_batch_results("classification", raw)
        self.assertEqual(len(out), 2)
        row = out[0]
        self.assertIn("complexity", row)
        self.assertIn("slice_id", row)
        self.assertNotIn("result", row)
        self.assertNotIn("cursor_mode", row)

    def test_batch_schema_keys_match(self):
        for task, fields in BATCH_FIELDS.items():
            self.assertTrue(fields, f"{task} needs fields")

    def test_route_json_shape(self):
        rec = route_task("verify tests pass")
        shaped = shape_route(rec)
        self.assertEqual(set(shaped.keys()), {"tier", "slice", "skill", "cursor", "verify"})
        text = dump_json(shaped)
        parsed = json.loads(text)
        self.assertEqual(parsed["tier"], rec.complexity)

    def test_dump_compact_no_whitespace(self):
        text = dump_json([{"index": 0, "ok": True, "score": 50}])
        self.assertNotIn("\n", text)
        self.assertNotIn(" ", text)


if __name__ == "__main__":
    unittest.main()
