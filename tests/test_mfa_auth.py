import unittest

import pyotp

from logic.mfa_auth import (
    begin_mfa_enrollment,
    confirm_mfa_enrollment,
    disable_mfa,
    mfa_status,
    verify_mfa_login,
)
from logic.users import authenticate_user, complete_mfa_login, create_app_user
from tests.helpers import test_database


class TestMfaAuth(unittest.TestCase):
    def test_login_without_mfa_succeeds_immediately(self):
        with test_database():
            create_app_user("mfa_none", "Str0ngP@ssw0rd!", "Officer", must_change_password=False)
            result = authenticate_user("mfa_none", "Str0ngP@ssw0rd!")
            self.assertTrue(result["success"])
            self.assertNotIn("mfa_required", result)

    def test_enrollment_requires_code_confirmation_before_activation(self):
        with test_database():
            created = create_app_user("mfa_pending", "Str0ngP@ssw0rd!", "Officer", must_change_password=False)
            user_id = created["user_id"]

            status_before = mfa_status(user_id)
            self.assertFalse(status_before["mfa_enabled"])

            enroll = begin_mfa_enrollment(user_id)
            self.assertTrue(enroll["success"])
            self.assertIn("secret", enroll)

            # Not yet activated — password login should still succeed without MFA.
            result = authenticate_user("mfa_pending", "Str0ngP@ssw0rd!")
            self.assertTrue(result["success"])
            self.assertNotIn("mfa_required", result)

    def test_confirm_enrollment_activates_mfa_and_gates_login(self):
        with test_database():
            created = create_app_user("mfa_active", "Str0ngP@ssw0rd!", "Officer", must_change_password=False)
            user_id = created["user_id"]

            enroll = begin_mfa_enrollment(user_id)
            secret = enroll["secret"]
            code = pyotp.TOTP(secret).now()

            confirm = confirm_mfa_enrollment(user_id, code)
            self.assertTrue(confirm["success"])
            self.assertTrue(mfa_status(user_id)["mfa_enabled"])

            # Password auth now pauses for MFA instead of completing login.
            password_result = authenticate_user("mfa_active", "Str0ngP@ssw0rd!")
            self.assertFalse(password_result["success"])
            self.assertTrue(password_result.get("mfa_required"))
            self.assertEqual(password_result["user_id"], user_id)

            # Correct code completes login.
            final = complete_mfa_login(user_id, pyotp.TOTP(secret).now())
            self.assertTrue(final["success"])
            self.assertEqual(final["user"]["username"], "mfa_active")

    def test_wrong_code_rejected(self):
        with test_database():
            created = create_app_user("mfa_wrong", "Str0ngP@ssw0rd!", "Officer", must_change_password=False)
            user_id = created["user_id"]
            enroll = begin_mfa_enrollment(user_id)
            confirm_mfa_enrollment(user_id, pyotp.TOTP(enroll["secret"]).now())

            result = verify_mfa_login(user_id, "000000")
            self.assertFalse(result["success"])

    def test_confirm_enrollment_rejects_bad_code(self):
        with test_database():
            created = create_app_user("mfa_badconfirm", "Str0ngP@ssw0rd!", "Officer", must_change_password=False)
            user_id = created["user_id"]
            begin_mfa_enrollment(user_id)

            result = confirm_mfa_enrollment(user_id, "000000")
            self.assertFalse(result["success"])
            self.assertFalse(mfa_status(user_id)["mfa_enabled"])

    def test_self_disable_allowed(self):
        with test_database():
            created = create_app_user("mfa_self_off", "Str0ngP@ssw0rd!", "Officer", must_change_password=False)
            user_id = created["user_id"]
            enroll = begin_mfa_enrollment(user_id)
            confirm_mfa_enrollment(user_id, pyotp.TOTP(enroll["secret"]).now())

            result = disable_mfa(user_id, actor_user_id=user_id)
            self.assertTrue(result["success"])
            self.assertFalse(mfa_status(user_id)["mfa_enabled"])

    def test_other_officer_cannot_disable_mfa(self):
        with test_database():
            target = create_app_user("mfa_target", "Str0ngP@ssw0rd!", "Officer", must_change_password=False)
            other = create_app_user("mfa_bystander", "Str0ngP@ssw0rd!", "Officer", must_change_password=False)
            target_id = target["user_id"]
            enroll = begin_mfa_enrollment(target_id)
            confirm_mfa_enrollment(target_id, pyotp.TOTP(enroll["secret"]).now())

            result = disable_mfa(target_id, actor_user_id=other["user_id"])
            self.assertFalse(result["success"])
            self.assertTrue(mfa_status(target_id)["mfa_enabled"])

    def test_admin_can_disable_other_users_mfa(self):
        with test_database():
            admin = create_app_user("mfa_admin", "Str0ngP@ssw0rd!", "Administration", must_change_password=False)
            target = create_app_user("mfa_target2", "Str0ngP@ssw0rd!", "Officer", must_change_password=False)
            target_id = target["user_id"]
            enroll = begin_mfa_enrollment(target_id)
            confirm_mfa_enrollment(target_id, pyotp.TOTP(enroll["secret"]).now())

            result = disable_mfa(target_id, actor_user_id=admin["user_id"])
            self.assertTrue(result["success"])
            self.assertFalse(mfa_status(target_id)["mfa_enabled"])


if __name__ == "__main__":
    unittest.main()
