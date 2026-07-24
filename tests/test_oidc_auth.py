import os
import unittest

from logic.oidc_auth import (
    complete_oidc_login,
    get_oidc_field_trial_config,
    oidc_auth_enabled,
    oidc_field_trial_checklist,
    save_oidc_field_trial_settings,
)
from logic.users import create_app_user
from tests.helpers import test_database


class TestOidcAuth(unittest.TestCase):
    def setUp(self):
        self._env_keys = [
            "SCHEDULER_OIDC_ENABLED",
            "SCHEDULER_OIDC_ISSUER",
            "SCHEDULER_OIDC_CLIENT_ID",
            "SCHEDULER_OIDC_CLIENT_SECRET",
            "SCHEDULER_OIDC_REDIRECT_URI",
        ]
        self._env_backup = {k: os.environ.get(k) for k in self._env_keys}
        for k in self._env_keys:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_disabled_by_default(self):
        with test_database():
            self.assertFalse(oidc_auth_enabled())

    def test_env_var_enables(self):
        os.environ["SCHEDULER_OIDC_ENABLED"] = "1"
        with test_database():
            self.assertTrue(oidc_auth_enabled())

    def test_checklist_fails_without_config(self):
        with test_database():
            checklist = oidc_field_trial_checklist()
            self.assertFalse(checklist["ready_for_lab_config"])
            self.assertFalse(checklist["production_ready"])

    def test_save_settings_requires_admin_permission(self):
        with test_database():
            officer = create_app_user("oidc_officer", "Str0ngP@ssw0rd!", "Officer", must_change_password=False)
            result = save_oidc_field_trial_settings({"issuer": "https://idp.example.com/"}, user_id=officer["user_id"])
            self.assertFalse(result["success"])
            self.assertIn("Administration", result["message"])

    def test_admin_can_save_settings(self):
        with test_database():
            admin = create_app_user("oidc_admin", "Str0ngP@ssw0rd!", "Administration", must_change_password=False)
            result = save_oidc_field_trial_settings(
                {
                    "issuer": "https://idp.example.com/",
                    "client_id": "chronos-client",
                    "client_secret": "secret-value",
                    "redirect_uri": "https://chronos.example.com/auth/oidc/callback",
                },
                user_id=admin["user_id"],
            )
            self.assertTrue(result["success"])
            cfg = get_oidc_field_trial_config()
            self.assertEqual(cfg["issuer"], "https://idp.example.com/")
            self.assertTrue(cfg["client_secret_set"])

    def test_checklist_ready_for_lab_after_full_config(self):
        with test_database():
            admin = create_app_user("oidc_admin2", "Str0ngP@ssw0rd!", "Administration", must_change_password=False)
            save_oidc_field_trial_settings(
                {
                    "issuer": "https://idp.example.com/",
                    "client_id": "chronos-client",
                    "client_secret": "secret-value",
                    "redirect_uri": "https://chronos.example.com/auth/oidc/callback",
                    "enabled": True,
                },
                user_id=admin["user_id"],
            )
            checklist = oidc_field_trial_checklist()
            self.assertTrue(checklist["ready_for_lab_config"])
            # Not production_ready without explicit IT sign-off.
            self.assertFalse(checklist["production_ready"])

    def test_production_signoff_required_for_production_ready(self):
        with test_database():
            admin = create_app_user("oidc_admin3", "Str0ngP@ssw0rd!", "Administration", must_change_password=False)
            save_oidc_field_trial_settings(
                {
                    "issuer": "https://idp.example.com/",
                    "client_id": "chronos-client",
                    "client_secret": "secret-value",
                    "redirect_uri": "https://chronos.example.com/auth/oidc/callback",
                    "enabled": True,
                    "production_signoff": True,
                    "signoff_by": "IT Admin",
                },
                user_id=admin["user_id"],
            )
            checklist = oidc_field_trial_checklist()
            self.assertTrue(checklist["production_ready"])

    def test_state_mismatch_rejected_before_any_network_call(self):
        with test_database():
            result = complete_oidc_login(code="abc", state="attacker-state", expected_state="real-state")
            self.assertFalse(result["success"])
            self.assertIn("state mismatch", result["message"].lower())

    def test_login_blocked_when_oidc_disabled(self):
        with test_database():
            result = complete_oidc_login(code="abc", state="s", expected_state="s")
            self.assertFalse(result["success"])
            self.assertIn("not enabled", result["message"].lower())


if __name__ == "__main__":
    unittest.main()
