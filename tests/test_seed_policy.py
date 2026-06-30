import os
import unittest

from tests.helpers import test_database


class SeedPolicyTests(unittest.TestCase):
    def test_skip_demo_users_env(self):
        prev = os.environ.get("SKIP_DEMO_USERS")
        os.environ["SKIP_DEMO_USERS"] = "1"
        try:
            with test_database(seed=False):
                import database

                database.init_database()
                conn = database.get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM app_users")
                count = cursor.fetchone()[0]
                conn.close()
                self.assertEqual(count, 0)
        finally:
            if prev is None:
                os.environ.pop("SKIP_DEMO_USERS", None)
            else:
                os.environ["SKIP_DEMO_USERS"] = prev


if __name__ == "__main__":
    unittest.main()
