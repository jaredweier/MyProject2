"""Tests for shared test helpers."""

import unittest
from datetime import date

from tests.helpers import TEST_REFERENCE_DATE, reference_today


class HelperTests(unittest.TestCase):
    def test_reference_today_constant(self):
        self.assertEqual(reference_today(), TEST_REFERENCE_DATE)
        self.assertEqual(reference_today(), date(2026, 6, 30))


if __name__ == "__main__":
    unittest.main()
