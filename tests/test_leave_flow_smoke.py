"""Chronos leave path smoke — same logic as gui approve/reject (no browser)."""

import unittest

from scripts.leave_flow_smoke import run_leave_flow_smoke


class LeaveFlowSmokeTests(unittest.TestCase):
    def test_leave_create_preview_approve_reject(self):
        code = run_leave_flow_smoke()
        self.assertEqual(code, 0, "leave_flow_smoke must pass")


if __name__ == "__main__":
    unittest.main()
