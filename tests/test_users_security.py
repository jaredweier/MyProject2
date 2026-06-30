import unittest

from tests.helpers import test_database


class UserSecurityTests(unittest.TestCase):
    def test_seed_users_require_password_change(self):
        with test_database():
            import logic

            users = logic.list_all_users()
            self.assertTrue(users)
            for user in users:
                self.assertEqual(user.get("must_change_password"), 1)

    def test_create_app_user(self):
        with test_database():
            import logic

            result = logic.create_app_user("newuser", "temppass", "Officer")
            self.assertTrue(result["success"])
            users = logic.list_all_users()
            created = next(u for u in users if u["username"] == "newuser")
            self.assertEqual(created["role"], "Officer")
            self.assertEqual(created["must_change_password"], 1)

    def test_change_password_clears_must_change_flag(self):
        with test_database():
            import logic

            users = logic.list_login_users()
            officer_user = next(u for u in users if u["username"] == "officer")
            result = logic.change_own_password(officer_user["id"], "officer", "newsecret")
            self.assertTrue(result["success"])
            refreshed = logic.get_user_by_id(officer_user["id"])
            self.assertEqual(refreshed.get("must_change_password"), 0)

    def test_admin_reset_password_sets_must_change(self):
        with test_database():
            import logic

            users = logic.list_login_users()
            target = next(u for u in users if u["username"] == "officer")
            logic.change_own_password(target["id"], "officer", "cleared1")
            reset = logic.admin_reset_user_password(target["id"], "resetpass")
            self.assertTrue(reset["success"])
            refreshed = logic.get_user_by_id(target["id"])
            self.assertEqual(refreshed.get("must_change_password"), 1)

    def test_complete_initial_setup(self):
        with test_database():
            import logic

            self.assertFalse(logic.is_setup_complete())
            result = logic.complete_initial_setup("Dodgeville PD Test")
            self.assertTrue(result["success"])
            self.assertTrue(logic.is_setup_complete())
            self.assertEqual(logic.get_department_setting("department_name"), "Dodgeville PD Test")

    def test_update_app_user_role_and_officer_link(self):
        with test_database():
            import logic

            created = logic.create_app_user("linked", "temppass", "Officer")
            self.assertTrue(created["success"])
            linked_ids = {u["officer_id"] for u in logic.list_all_users() if u.get("officer_id")}
            officer = next(o for o in logic.get_officers_by_seniority() if o["id"] not in linked_ids)
            updated = logic.update_app_user(
                created["user_id"],
                role="Supervisor",
                officer_id=officer["id"],
            )
            self.assertTrue(updated["success"])
            user = logic.get_user_by_id(created["user_id"])
            self.assertEqual(user["role"], "Supervisor")
            self.assertEqual(user["officer_id"], officer["id"])

            cleared = logic.update_app_user(created["user_id"], clear_officer_link=True)
            self.assertTrue(cleared["success"])
            user = logic.get_user_by_id(created["user_id"])
            self.assertIsNone(user["officer_id"])

    def test_supervisor_can_change_officer_role(self):
        with test_database():
            import logic

            supervisor = next(u for u in logic.list_login_users() if u["username"] == "supervisor")
            officer_user = next(u for u in logic.list_login_users() if u["username"] == "officer")
            result = logic.update_app_user(
                officer_user["id"],
                role="Supervisor",
                actor_user_id=supervisor["id"],
            )
            self.assertTrue(result["success"])
            refreshed = logic.get_user_by_id(officer_user["id"])
            self.assertEqual(refreshed["role"], "Supervisor")

    def test_supervisor_cannot_assign_administration(self):
        with test_database():
            import logic

            supervisor = next(u for u in logic.list_login_users() if u["username"] == "supervisor")
            officer_user = next(u for u in logic.list_login_users() if u["username"] == "officer")
            result = logic.update_app_user(
                officer_user["id"],
                role="Administration",
                actor_user_id=supervisor["id"],
            )
            self.assertFalse(result["success"])

    def test_supervisor_cannot_modify_admin_account(self):
        with test_database():
            import logic

            supervisor = next(u for u in logic.list_login_users() if u["username"] == "supervisor")
            admin_user = next(u for u in logic.list_login_users() if u["username"] == "admin")
            result = logic.update_app_user(
                admin_user["id"],
                role="Supervisor",
                actor_user_id=supervisor["id"],
            )
            self.assertFalse(result["success"])

    def test_admin_can_change_any_role(self):
        with test_database():
            import logic

            admin = next(u for u in logic.list_login_users() if u["username"] == "admin")
            officer_user = next(u for u in logic.list_login_users() if u["username"] == "officer")
            result = logic.update_app_user(
                officer_user["id"],
                role="Administration",
                actor_user_id=admin["id"],
            )
            self.assertTrue(result["success"])
            logic.update_app_user(
                officer_user["id"],
                role="Officer",
                actor_user_id=admin["id"],
            )

    def test_allowed_roles_for_supervisor(self):
        with test_database():
            import logic

            supervisor = next(u for u in logic.list_login_users() if u["username"] == "supervisor")
            roles = logic.allowed_roles_for_actor(supervisor["id"])
            self.assertEqual(roles, ["Officer", "Supervisor"])

    def test_export_officer_schedule_ical(self):
        with test_database():
            import os
            import tempfile

            import logic

            officer = logic.get_officers_by_seniority()[0]
            start, end = logic.get_current_cycle_window()
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "sched.ics")
                result = logic.export_officer_schedule_ical(
                    officer["id"],
                    start_date=start,
                    end_date=end,
                    output_path=path,
                )
                self.assertTrue(result["success"])
                self.assertTrue(os.path.isfile(path))
                with open(path, encoding="utf-8") as handle:
                    content = handle.read()
                self.assertIn("BEGIN:VCALENDAR", content)


if __name__ == "__main__":
    unittest.main()
