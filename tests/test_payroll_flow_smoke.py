"""Payroll lock path smoke — same logic as Chronos finance UI."""

import unittest

from scripts.payroll_flow_smoke import run_payroll_flow_smoke


class PayrollFlowSmokeTests(unittest.TestCase):
    def test_save_lock_block_unlock(self):
        self.assertEqual(run_payroll_flow_smoke(), 0)


if __name__ == "__main__":
    unittest.main()
