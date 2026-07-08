"""Demo account password-change policy on existing databases."""

import unittest

from auth_password import hash_password
from tests.helpers import test_database


class DemoPasswordMigrationTests(unittest.TestCase):
    def test_migration_flags_factory_demo_passwords(self):
        with test_database():
            from database import get_connection, init_database

            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE app_users SET password = ?, must_change_password = 0
                WHERE username = 'officer'
                """,
                (hash_password("officer"),),
            )
            conn.commit()
            conn.close()

            init_database()

            from logic import list_all_users

            officer = next(u for u in list_all_users() if u["username"] == "officer")
            self.assertEqual(officer.get("must_change_password"), 1)

    def test_migration_skips_changed_passwords(self):
        with test_database():
            from database import get_connection, init_database

            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE app_users SET password = ?, must_change_password = 0
                WHERE username = 'officer'
                """,
                (hash_password("CustomSecret99!"),),
            )
            conn.commit()
            conn.close()

            init_database()

            from logic import list_all_users

            officer = next(u for u in list_all_users() if u["username"] == "officer")
            self.assertEqual(officer.get("must_change_password"), 0)


if __name__ == "__main__":
    unittest.main()
