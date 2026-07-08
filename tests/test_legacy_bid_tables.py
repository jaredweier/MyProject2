"""Legacy shift_bid_slots / shift_bids tables are dropped when empty."""

import unittest

from database import get_connection, init_database
from tests.helpers import test_database


class LegacyBidTablesTests(unittest.TestCase):
    def test_empty_legacy_tables_dropped_on_init(self):
        with test_database():
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS shift_bid_slots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shift_date DATE NOT NULL,
                    shift_start TEXT NOT NULL,
                    shift_end TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS shift_bids (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slot_id INTEGER NOT NULL,
                    officer_id INTEGER NOT NULL
                )
                """
            )
            conn.commit()
            conn.close()

            init_database()

            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('shift_bids', 'shift_bid_slots')"
            )
            remaining = {row[0] for row in cur.fetchall()}
            conn.close()
            self.assertEqual(remaining, set())

    def test_legacy_tables_with_data_are_retained(self):
        with test_database():
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS shift_bid_slots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shift_date DATE NOT NULL,
                    shift_start TEXT NOT NULL,
                    shift_end TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS shift_bids (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slot_id INTEGER NOT NULL,
                    officer_id INTEGER NOT NULL
                )
                """
            )
            cur.execute(
                "INSERT INTO shift_bid_slots (shift_date, shift_start, shift_end) VALUES ('2026-07-01', '06:00', '14:00')"
            )
            conn.commit()
            conn.close()

            init_database()

            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = 'shift_bid_slots'")
            self.assertIsNotNone(cur.fetchone())
            conn.close()


if __name__ == "__main__":
    unittest.main()
