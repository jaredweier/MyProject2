import unittest
from datetime import date

from config import ROTATION_BASE_DATE, is_high_risk_night
from validators import (
    applies_night_minimum,
    format_datetime,
    is_night_shift,
    is_officer_active,
    is_overnight_shift,
    night_minimum_violation,
    normalize_officer_job_title,
    parse_date,
    validate_cycle_date,
    validate_day_off_request,
    validate_officer_email,
    validate_officer_job_title,
    validate_officer_phone,
    validate_officer_profile,
    validate_officer_start_date,
    validate_process_day_off,
    validate_request_status,
)


class TestValidators(unittest.TestCase):
    def test_parse_date(self):
        # Product policy: US month-first for slash/dash forms; ISO is unambiguous.
        self.assertEqual(parse_date("01/07/2026"), date(2026, 1, 7))
        self.assertEqual(parse_date("01-07-2026"), date(2026, 1, 7))
        self.assertEqual(parse_date("7/1/2026"), date(2026, 7, 1))
        self.assertEqual(parse_date("2026-07-01"), date(2026, 7, 1))

    def test_format_datetime(self):
        # Display: US short M/D/YY (e.g. 7/1/26)
        self.assertEqual(format_datetime("2026-07-01 14:30:00"), "7/1/26 14:30")
        self.assertEqual(format_datetime(""), "")

    def test_is_officer_active(self):
        self.assertTrue(is_officer_active({"active": 1}))
        self.assertFalse(is_officer_active({"active": 0}))
        self.assertFalse(is_officer_active({"active": None}))

    def test_night_shift_detection(self):
        self.assertTrue(is_night_shift("19:00"))
        self.assertTrue(is_night_shift("15:00"))
        self.assertFalse(is_night_shift("06:00"))

    def test_overnight_shift_detection(self):
        self.assertTrue(is_overnight_shift("19:00", "06:00"))
        self.assertFalse(is_overnight_shift("06:00", "17:00"))
        self.assertFalse(is_overnight_shift("", "06:00"))

    def test_officer_job_title_options(self):
        self.assertTrue(validate_officer_job_title("Sergeant").ok)
        self.assertTrue(validate_officer_job_title("Investigator").ok)
        bad_admin = validate_officer_job_title("Administrative Assistant")
        self.assertFalse(bad_admin.ok)
        self.assertTrue(validate_officer_job_title(None).ok)
        self.assertTrue(validate_officer_job_title("Patrol Officer").ok)
        self.assertEqual(normalize_officer_job_title("Patrol Officer"), "Officer")
        self.assertEqual(normalize_officer_job_title("Chief of Police"), "Chief")
        bad = validate_officer_job_title("Captain")
        self.assertFalse(bad.ok)

    def test_applies_night_minimum(self):
        fri = date(2026, 7, 3)
        self.assertTrue(applies_night_minimum(fri, "19:00", is_high_risk_night))
        self.assertFalse(applies_night_minimum(fri, "06:00", is_high_risk_night))

    def test_validate_cycle_date_before_base(self):
        before = ROTATION_BASE_DATE.replace(day=1)
        result = validate_cycle_date(before)
        self.assertFalse(result.ok)

    def test_validate_request_status_pending_only(self):
        self.assertTrue(validate_request_status("Pending", "approve").ok)
        self.assertTrue(validate_request_status("Pending Manual Review", "approve").ok)
        self.assertTrue(validate_request_status("Pending Manual Review", "reject").ok)
        self.assertFalse(validate_request_status("Approved", "approve").ok)

    def test_validate_day_off_allows_unavailable_date(self):
        from datetime import date

        import logic
        from tests.helpers import test_database
        from validators import validate_day_off_request

        with test_database():
            officer = logic.get_officers_by_seniority()[0]
            work = date(2026, 6, 28)
            logic.add_officer_availability(officer["id"], work.isoformat(), reason="PTO block")
            result = validate_day_off_request(officer, work.isoformat())
            self.assertTrue(result.ok)

    def test_validate_user_role_change_supervisor_limits(self):
        from validators import validate_user_role_change

        supervisor = {"id": 2, "role": "Supervisor"}
        officer_user = {"id": 3, "role": "Officer"}
        admin_user = {"id": 1, "role": "Administration"}

        self.assertTrue(validate_user_role_change(supervisor, officer_user, "Supervisor").ok)
        self.assertFalse(validate_user_role_change(supervisor, officer_user, "Administration").ok)
        self.assertFalse(validate_user_role_change(supervisor, admin_user, "Supervisor").ok)
        self.assertFalse(validate_user_role_change(supervisor, supervisor, "Administration").ok)

    def test_validate_request_type(self):
        from validators import validate_request_type

        self.assertTrue(validate_request_type("Vacation").ok)
        self.assertTrue(validate_request_type("Training").ok)
        self.assertFalse(validate_request_type("Jury Duty").ok)

    def test_validate_day_off_allows_off_rotation(self):
        officer = {"name": "Test", "active": 1}
        result = validate_day_off_request(officer, "2026-06-28")
        self.assertTrue(result.ok)

    def test_validate_process_reject_allows_non_pending(self):
        # reject still requires pending in our rules
        req = {"status": "Pending", "request_date": "2026-06-28", "officer_id": 1}
        officer = {"active": 1}
        self.assertTrue(validate_process_day_off(req, officer, "reject").ok)

    def test_night_minimum_violation(self):
        self.assertTrue(night_minimum_violation(2))
        self.assertFalse(night_minimum_violation(3))

    def test_validate_minimum_rest_gap(self):
        from validators import validate_minimum_rest_gap

        self.assertTrue(validate_minimum_rest_gap(None, 10).ok)
        self.assertTrue(validate_minimum_rest_gap(12.0, 10).ok)
        bad = validate_minimum_rest_gap(6.5, 10, "Off. Smith")
        self.assertFalse(bad.ok)
        self.assertIn("6.5h", bad.message)
        self.assertIn("Off. Smith", bad.message)

    def test_validate_officer_contact_fields(self):
        self.assertTrue(validate_officer_email("officer@dodgeville.gov").ok)
        self.assertFalse(validate_officer_email("bad-email").ok)
        self.assertTrue(validate_officer_phone("(608) 930-5228").ok)
        self.assertFalse(validate_officer_phone("12").ok)
        self.assertTrue(validate_officer_start_date("2026-01-15").ok)
        # US M/D/YYYY accepted for officer start dates (same as parse_date policy)
        self.assertTrue(validate_officer_start_date("01/15/2026").ok)
        self.assertFalse(validate_officer_start_date("not-a-date").ok)

    def test_validate_password(self):
        from validators import validate_password

        self.assertFalse(validate_password("").ok)
        self.assertFalse(validate_password("abc").ok)
        self.assertTrue(validate_password("admin").ok)

    def test_validate_username(self):
        from validators import validate_username

        self.assertTrue(validate_username("jsmith").ok)
        self.assertFalse(validate_username("").ok)
        self.assertFalse(validate_username("bad name").ok)

    def test_validate_manual_override(self):
        from validators import validate_manual_override

        original = {"id": 1, "name": "A", "active": 1}
        replacement = {"id": 2, "name": "B", "active": 1}
        self.assertTrue(validate_manual_override(original, replacement, "2026-07-02").ok)
        self.assertFalse(validate_manual_override(original, original, "2026-07-02").ok)
        self.assertFalse(validate_manual_override(original, replacement, "bad-date").ok)

    def test_validate_officer_profile(self):
        result = validate_officer_profile(
            "Chief Example",
            1,
            "A",
            "06:00",
            "17:00",
            40.0,
            start_date="2026-01-01",
            email="chief@dodgeville.gov",
        )
        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
