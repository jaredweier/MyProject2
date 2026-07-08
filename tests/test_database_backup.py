"""Database backup slice — manual, auto, restore, and status."""

import os
import sqlite3
import tempfile
import unittest
import uuid
from contextlib import contextmanager
from typing import Iterator

from tests.helpers import test_database


def _sqlite_backup(src_path: str, dest_path: str) -> None:
    src = sqlite3.connect(src_path)
    dst = sqlite3.connect(dest_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


@contextmanager
def file_test_database() -> Iterator[str]:
    """Isolated on-disk DB for restore tests (in-memory URIs cannot be restored)."""
    path = os.path.join(tempfile.gettempdir(), f"dpd_file_test_{uuid.uuid4().hex}.db")
    prev = os.environ.get("SCHEDULER_DB_PATH")
    prev_seed = os.environ.get("ROSTER_SEED_PATH")
    os.environ["SCHEDULER_DB_PATH"] = path
    os.environ.pop("ROSTER_SEED_PATH", None)
    import database
    import logic  # noqa: F401

    prev_db = database.DB_PATH
    database.DB_PATH = path
    database.init_database()
    try:
        yield path
    finally:
        database.DB_PATH = prev_db
        if prev is None:
            os.environ.pop("SCHEDULER_DB_PATH", None)
        else:
            os.environ["SCHEDULER_DB_PATH"] = prev
        if prev_seed is None:
            os.environ.pop("ROSTER_SEED_PATH", None)
        else:
            os.environ["ROSTER_SEED_PATH"] = prev_seed
        for extra in (path, f"{path}.snapshot.db"):
            if os.path.exists(extra):
                os.unlink(extra)


class DatabaseBackupTests(unittest.TestCase):
    def test_manual_backup_creates_file(self):
        with test_database():
            import database

            path = database.backup_database()
            self.assertTrue(os.path.isfile(path))
            self.assertTrue(path.endswith(".db"))

    def test_maybe_run_auto_backup_returns_path_or_skips(self):
        with test_database():
            import logic

            first = logic.maybe_run_auto_backup()
            self.assertIsNotNone(first)
            self.assertTrue(os.path.isfile(first))
            second = logic.maybe_run_auto_backup()
            self.assertIsNone(second)

    def test_list_backup_files_newest_first(self):
        with test_database():
            import time

            import database

            first = database.backup_database()
            time.sleep(0.05)
            second = database.backup_database()
            files = database.list_backup_files()
            self.assertGreaterEqual(len(files), 2)
            self.assertEqual(files[0], second)
            self.assertIn(first, files)

    def test_get_backup_status_flags_overdue(self):
        with test_database():
            import logic
            from database import backup_database

            backup_database()
            status = logic.get_backup_status(max_age_days=0)
            self.assertTrue(status.get("success"))
            self.assertTrue(status.get("needs_backup"))
            self.assertGreaterEqual(status.get("backup_count", 0), 1)

    def test_restore_database_from_backup_round_trip(self):
        with file_test_database() as db_path:
            import logic

            baseline = len(logic.get_officers_by_seniority())
            first = logic.add_officer("Backup Test Officer", 99, "A", "06:00", "17:00")
            self.assertTrue(first.get("success"), first.get("message"))
            backup_path = f"{db_path}.snapshot.db"
            _sqlite_backup(db_path, backup_path)
            second = logic.add_officer("After Backup Officer", 100, "B", "10:00", "21:00")
            self.assertTrue(second.get("success"), second.get("message"))
            self.assertEqual(len(logic.get_officers_by_seniority()), baseline + 2)

            result = logic.restore_database_from_backup(backup_path)
            self.assertTrue(result.get("success"), result.get("message"))
            self.assertTrue(os.path.isfile(result.get("safety_backup", "")))
            names = [o["name"] for o in logic.get_officers_by_seniority()]
            self.assertIn("Backup Test Officer", names)
            self.assertNotIn("After Backup Officer", names)
            self.assertEqual(len(names), baseline + 1)

    def test_restore_rejects_live_database_path(self):
        with file_test_database():
            import database

            live = database._resolve_db_file_path()
            with self.assertRaises(ValueError):
                database.restore_database(live)


if __name__ == "__main__":
    unittest.main()
