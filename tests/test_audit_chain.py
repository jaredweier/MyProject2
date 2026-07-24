import unittest

from database import connection
from logic.users import create_app_user, log_audit_action, verify_audit_chain
from tests.helpers import test_database


class TestAuditChain(unittest.TestCase):
    def test_chain_intact_after_multiple_actions(self):
        with test_database():
            create_app_user("audit_a", "Str0ngP@ssw0rd!", "Officer", must_change_password=False)
            create_app_user("audit_b", "Str0ngP@ssw0rd!", "Officer", must_change_password=False)
            log_audit_action("test.action", "widget", 1, None, "first")
            log_audit_action("test.action", "widget", 2, None, "second")

            result = verify_audit_chain()
            self.assertTrue(result["intact"])
            self.assertGreaterEqual(result["rows_checked"], 4)

    def test_tampered_details_breaks_chain(self):
        with test_database():
            log_audit_action("test.action", "widget", 1, None, "original")
            with connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM audit_log ORDER BY id DESC LIMIT 1")
                row_id = cursor.fetchone()["id"]
                cursor.execute("UPDATE audit_log SET details = ? WHERE id = ?", ("tampered", row_id))
                conn.commit()

            result = verify_audit_chain()
            self.assertFalse(result["intact"])
            self.assertEqual(result["broken_at_id"], row_id)

    def test_deleted_row_breaks_chain_for_next_row(self):
        with test_database():
            log_audit_action("test.action", "widget", 1, None, "one")
            log_audit_action("test.action", "widget", 2, None, "two")
            log_audit_action("test.action", "widget", 3, None, "three")

            with connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM audit_log WHERE details = 'two' ORDER BY id DESC LIMIT 1")
                middle_id = cursor.fetchone()["id"]
                cursor.execute("DELETE FROM audit_log WHERE id = ?", (middle_id,))
                conn.commit()

            result = verify_audit_chain()
            self.assertFalse(result["intact"])

    def test_hash_chain_links_sequential_rows(self):
        with test_database():
            log_audit_action("test.action", "widget", 1, None, "one")
            log_audit_action("test.action", "widget", 2, None, "two")

            with connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, prev_hash, row_hash FROM audit_log WHERE details IN ('one', 'two') ORDER BY id ASC"
                )
                rows = [dict(r) for r in cursor.fetchall()]

            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[1]["prev_hash"], rows[0]["row_hash"])
            self.assertNotEqual(rows[0]["row_hash"], rows[1]["row_hash"])


if __name__ == "__main__":
    unittest.main()
