"""Auth and user account tests."""

import unittest

from tests.helpers import test_database


class AuthTests(unittest.TestCase):
    def test_change_own_password(self):
        with test_database():
            import logic

            users = logic.list_login_users()
            officer_user = next(u for u in users if u["username"] == "officer")
            bad = logic.change_own_password(officer_user["id"], "wrong", "newpass")
            self.assertFalse(bad["success"])
            ok = logic.change_own_password(officer_user["id"], "officer", "newsecret")
            self.assertTrue(ok["success"])
            auth = logic.authenticate_user("officer", "newsecret")
            self.assertTrue(auth["success"])
            updated = logic.get_user_by_id(officer_user["id"])
            self.assertTrue(updated["password"].startswith("pbkdf2$"))

    def test_login_upgrades_plaintext_password(self):
        with test_database():
            import logic
            from database import get_connection

            users = logic.list_login_users()
            officer_user = next(u for u in users if u["username"] == "officer")
            conn = get_connection()
            conn.execute("UPDATE app_users SET password = 'officer' WHERE id = ?", (officer_user["id"],))
            conn.commit()
            conn.close()
            auth = logic.authenticate_user("officer", "officer")
            self.assertTrue(auth["success"])
            stored = logic.get_user_by_id(officer_user["id"])["password"]
            self.assertTrue(stored.startswith("pbkdf2$"))

    def test_login_creates_audit_entry(self):
        with test_database():
            import logic

            logic.authenticate_user("admin", "admin")
            entries = logic.get_audit_log(10)
            self.assertTrue(any(e["action"] == "user.login" for e in entries))

    def test_list_login_users_omits_password(self):
        with test_database():
            import logic

            users = logic.list_login_users()
            self.assertTrue(users)
            self.assertNotIn("password", users[0])

    def test_change_password_validation(self):
        with test_database():
            import logic

            users = logic.list_login_users()
            admin = next(u for u in users if u["username"] == "admin")
            result = logic.change_own_password(admin["id"], "admin", "ab")
            self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()
