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
        required = {
            "tier",
            "cost",
            "slice",
            "skill",
            "cursor",
            "agent",
            "model",
            "ui_lane",
            "verify",
            "agents",
            "external",
            "oss_searches",
            "oss_actions",
        }
        self.assertEqual(set(shaped.keys()), required)
        text = dump_json(shaped)
        parsed = json.loads(text)
        self.assertEqual(parsed["tier"], rec.complexity)

    def test_dump_compact_no_whitespace(self):
        text = dump_json([{"index": 0, "ok": True, "score": 50}])
        self.assertNotIn("\n", text)
        self.assertNotIn(" ", text)

    def test_trivial_route_no_oss_tax(self):
        rec = route_task("fix typo on button")
        self.assertIn(rec.cost_tier, ("free", "cheap"))
        self.assertEqual(rec.oss_searches, [])
        self.assertEqual(rec.oss_actions, [])
        self.assertLessEqual(len(rec.agents), 3)
        self.assertEqual(rec.subagents, [])

    def test_chronos_medium_short_chain(self):
        rec = route_task("wire chronos leave approve page")
        self.assertLessEqual(len(rec.agents), 3)
        self.assertNotIn("skyvern", rec.agents)
        self.assertNotIn("browser-use", rec.agents)


if __name__ == "__main__":
    unittest.main()
