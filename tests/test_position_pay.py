import unittest

from config import OFFICER_TITLE_OPTIONS
from tests.helpers import get_any_officer, test_database
from validators import (
    position_amount_to_hourly,
    validate_position_pay_entry,
)


class PositionPayTests(unittest.TestCase):
    def test_hourly_monthly_yearly_conversion(self):
        self.assertEqual(position_amount_to_hourly(32.0, "hourly"), 32.0)
        self.assertAlmostEqual(position_amount_to_hourly(5200.0, "monthly"), 30.0, places=2)
        self.assertAlmostEqual(position_amount_to_hourly(93600.0, "yearly"), 45.0, places=2)

    def test_validate_position_pay_entry(self):
        self.assertTrue(validate_position_pay_entry("Sergeant", 37.5, "hourly").ok)
        self.assertTrue(validate_position_pay_entry("Chief", 90000, "yearly", is_salary=True).ok)
        self.assertFalse(validate_position_pay_entry("Captain", 40, "hourly").ok)

    def test_save_and_load_position_pay_rates(self):
        with test_database():
            import logic

            payload = {
                title: {
                    "amount": 30.0 + idx,
                    "pay_basis": "hourly",
                    "is_salary": False,
                }
                for idx, title in enumerate(OFFICER_TITLE_OPTIONS)
            }
            result = logic.save_position_pay_rates(payload)
            self.assertTrue(result["success"], result.get("message"))
            loaded = logic.get_position_pay_rates()
            self.assertEqual(loaded["rates"]["Officer"]["amount"], 30.0)

    def test_apply_position_rates_to_roster(self):
        with test_database():
            import logic

            logic.save_position_pay_rates(
                {
                    "Officer": {"amount": 33.0, "pay_basis": "hourly", "is_salary": False},
                }
            )
            officer = get_any_officer("A")
            logic.update_officer(officer["id"], job_title="Officer", pay_rate=20.0)
            result = logic.apply_position_pay_rates_to_roster()
            self.assertTrue(result["success"])
            self.assertGreaterEqual(result["updated"], 1)
            refreshed = logic.get_officer_by_id(officer["id"])
            self.assertAlmostEqual(refreshed["pay_rate"], 33.0, places=2)


if __name__ == "__main__":
    unittest.main()
