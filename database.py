import os
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

from paths import data_path, ensure_data_dirs

ensure_data_dirs()
DB_PATH = os.environ.get("SCHEDULER_DB_PATH", data_path("dodgeville_scheduler.db"))


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    """Context-managed SQLite connection (always closed on exit)."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def get_connection():
    if DB_PATH.startswith("file:"):
        conn = sqlite3.connect(DB_PATH, uri=True)
    else:
        conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if not DB_PATH.startswith("file:"):
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    # Officers
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS officers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            seniority_rank INTEGER NOT NULL,
            squad TEXT,
            shift_start TEXT,
            shift_end TEXT,
            pay_rate REAL DEFAULT 30.0,
            night_differential_rate REAL DEFAULT 1.0,
            photo_path TEXT,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Day Off Requests
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS day_off_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            officer_id INTEGER NOT NULL,
            request_date DATE NOT NULL,
            request_type TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            notes TEXT,
            admin_notes TEXT,
            processed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (officer_id) REFERENCES officers(id)
        )
    """)

    # Schedule Overrides
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedule_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            override_date DATE NOT NULL,
            original_officer_id INTEGER NOT NULL,
            replacement_officer_id INTEGER,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (original_officer_id) REFERENCES officers(id),
            FOREIGN KEY (replacement_officer_id) REFERENCES officers(id)
        )
    """)

    # Shift Swaps
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shift_swaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            swap_date DATE NOT NULL,
            officer1_id INTEGER NOT NULL,
            officer2_id INTEGER NOT NULL,
            status TEXT DEFAULT 'Pending',
            admin_notes TEXT,
            processed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (officer1_id) REFERENCES officers(id),
            FOREIGN KEY (officer2_id) REFERENCES officers(id)
        )
    """)

    # Notifications
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_officer_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            related_id INTEGER,
            related_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (recipient_officer_id) REFERENCES officers(id)
        )
    """)

    # Payroll
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payroll_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            officer_id INTEGER NOT NULL,
            entry_date DATE NOT NULL,
            entry_type TEXT NOT NULL,
            hours REAL NOT NULL,
            night_differential_hours REAL DEFAULT 0,
            calculated_pay REAL DEFAULT 0,
            comp_bank_delta REAL DEFAULT 0,
            sick_bank_delta REAL DEFAULT 0,
            float_holiday_bank_delta REAL DEFAULT 0,
            holiday_bank_delta REAL DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (officer_id) REFERENCES officers(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            officer_id INTEGER,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('Officer', 'Supervisor', 'Administration')),
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (officer_id) REFERENCES officers(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timecard_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            officer_id INTEGER NOT NULL,
            pay_period_start DATE NOT NULL,
            entry_date DATE NOT NULL,
            hours_worked REAL DEFAULT 0,
            time_in TEXT,
            time_out TEXT,
            entry_type TEXT DEFAULT 'Regular Hours',
            night_diff_hours REAL DEFAULT 0,
            notes TEXT,
            payroll_entry_id INTEGER,
            imported_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (officer_id) REFERENCES officers(id),
            FOREIGN KEY (payroll_entry_id) REFERENCES payroll_entries(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timecard_approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            officer_id INTEGER NOT NULL,
            pay_period_start DATE NOT NULL,
            status TEXT NOT NULL DEFAULT 'Draft'
                CHECK(status IN ('Draft', 'Submitted', 'Approved', 'Rejected')),
            submitted_at TIMESTAMP,
            approved_by_user_id INTEGER,
            approved_at TIMESTAMP,
            supervisor_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (officer_id) REFERENCES officers(id),
            FOREIGN KEY (approved_by_user_id) REFERENCES app_users(id),
            UNIQUE(officer_id, pay_period_start)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedule_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            schedule_type TEXT NOT NULL CHECK(schedule_type IN ('base', 'updated')),
            locked INTEGER DEFAULT 0,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            generated_by_user_id INTEGER,
            notes TEXT,
            FOREIGN KEY (generated_by_user_id) REFERENCES app_users(id),
            UNIQUE(year, month, schedule_type)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedule_snapshot_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            assignment_date DATE NOT NULL,
            officer_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            shift_start TEXT,
            shift_end TEXT,
            is_manual INTEGER DEFAULT 0,
            notes TEXT,
            FOREIGN KEY (snapshot_id) REFERENCES schedule_snapshots(id) ON DELETE CASCADE,
            FOREIGN KEY (officer_id) REFERENCES officers(id),
            UNIQUE(snapshot_id, assignment_date, officer_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS officer_time_banks (
            officer_id INTEGER PRIMARY KEY,
            comp_hours REAL DEFAULT 0,
            sick_hours REAL DEFAULT 0,
            float_holiday_hours REAL DEFAULT 0,
            holiday_hours REAL DEFAULT 0,
            sick_accrual_month TEXT,
            annual_accrual_year INTEGER,
            FOREIGN KEY (officer_id) REFERENCES officers(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS holidays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            holiday_date DATE NOT NULL UNIQUE,
            name TEXT NOT NULL,
            is_paid INTEGER DEFAULT 1,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS officer_availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            officer_id INTEGER NOT NULL,
            unavailable_date DATE NOT NULL,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (officer_id) REFERENCES officers(id),
            UNIQUE(officer_id, unavailable_date)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id INTEGER,
            user_id INTEGER,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES app_users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS department_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS open_shifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_date DATE NOT NULL,
            shift_start TEXT NOT NULL,
            shift_end TEXT NOT NULL,
            squad TEXT CHECK(squad IN ('A', 'B')),
            status TEXT DEFAULT 'open' CHECK(status IN ('open', 'filled', 'cancelled')),
            notes TEXT,
            filled_by_officer_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (filled_by_officer_id) REFERENCES officers(id)
        )
    """)

    _ensure_schema_migrations(cursor)
    _ensure_indexes(cursor)
    conn.commit()
    conn.close()

    from seed_data import seed_holidays_if_empty, seed_if_empty, seed_settings_if_empty, seed_users_if_empty

    seed_if_empty()
    seed_users_if_empty()
    seed_holidays_if_empty()
    seed_settings_if_empty()


def _ensure_schema_migrations(cursor) -> None:
    """Add columns/tables introduced after initial release (safe to re-run)."""
    cursor.execute("PRAGMA table_info(payroll_entries)")
    payroll_cols = {row[1] for row in cursor.fetchall()}
    for col, ddl in [
        ("comp_bank_delta", "ALTER TABLE payroll_entries ADD COLUMN comp_bank_delta REAL DEFAULT 0"),
        ("sick_bank_delta", "ALTER TABLE payroll_entries ADD COLUMN sick_bank_delta REAL DEFAULT 0"),
        ("float_holiday_bank_delta", "ALTER TABLE payroll_entries ADD COLUMN float_holiday_bank_delta REAL DEFAULT 0"),
        ("holiday_bank_delta", "ALTER TABLE payroll_entries ADD COLUMN holiday_bank_delta REAL DEFAULT 0"),
        ("pay_period_start", "ALTER TABLE payroll_entries ADD COLUMN pay_period_start DATE"),
    ]:
        if col not in payroll_cols:
            cursor.execute(ddl)
    _backfill_payroll_pay_period_start(cursor)

    cursor.execute("PRAGMA table_info(officers)")
    officer_cols = {row[1] for row in cursor.fetchall()}
    cursor.execute("PRAGMA table_info(app_users)")
    user_cols = {row[1] for row in cursor.fetchall()}
    if "must_change_password" not in user_cols:
        cursor.execute("ALTER TABLE app_users ADD COLUMN must_change_password INTEGER DEFAULT 1")

    cursor.execute("PRAGMA table_info(schedule_overrides)")
    override_cols = {row[1] for row in cursor.fetchall()}
    if "covered_shift_start" not in override_cols:
        cursor.execute("ALTER TABLE schedule_overrides ADD COLUMN covered_shift_start TEXT")

    for col, ddl in [
        ("start_date", "ALTER TABLE officers ADD COLUMN start_date DATE"),
        ("email", "ALTER TABLE officers ADD COLUMN email TEXT"),
        ("phone", "ALTER TABLE officers ADD COLUMN phone TEXT"),
        ("address", "ALTER TABLE officers ADD COLUMN address TEXT"),
        ("job_title", "ALTER TABLE officers ADD COLUMN job_title TEXT"),
        ("annual_hours_target", "ALTER TABLE officers ADD COLUMN annual_hours_target REAL DEFAULT 2080"),
        ("overtime_multiplier", "ALTER TABLE officers ADD COLUMN overtime_multiplier REAL DEFAULT 1.5"),
    ]:
        if col not in officer_cols:
            cursor.execute(ddl)

    _migrate_officers_nullable_assignment(cursor)
    _migrate_timecard_multi_entry(cursor)
    _ensure_department_setting_defaults(cursor)
    _ensure_tier2_tables(cursor)


def _ensure_department_setting_defaults(cursor) -> None:
    """Insert branding keys added after initial release."""
    from config import (
        DEFAULT_DEPARTMENT_MISSION,
        DEFAULT_DEPARTMENT_TAGLINE,
    )

    for key, value in (
        ("department_mission", DEFAULT_DEPARTMENT_MISSION),
        ("department_tagline", DEFAULT_DEPARTMENT_TAGLINE),
    ):
        cursor.execute("SELECT value FROM department_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        if not row:
            cursor.execute(
                "INSERT INTO department_settings (key, value) VALUES (?, ?)",
                (key, value),
            )
        elif key == "department_mission" and row[0] in (
            "To Protect and Serve",
            "",
        ):
            cursor.execute(
                "UPDATE department_settings SET value = ? WHERE key = ?",
                (DEFAULT_DEPARTMENT_MISSION, key),
            )


def _ensure_tier2_tables(cursor) -> None:
    """Tier 2 features: shift bidding, callback rotation, certifications, fatigue settings."""
    # Legacy per-slot bidding (superseded by shift_bid_events); retained for DB compatibility only.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shift_bid_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_date DATE NOT NULL,
            shift_start TEXT NOT NULL,
            shift_end TEXT NOT NULL,
            squad TEXT CHECK(squad IN ('A', 'B')),
            status TEXT DEFAULT 'bidding' CHECK(status IN ('bidding', 'awarded', 'cancelled')),
            notes TEXT,
            awarded_officer_id INTEGER,
            bids_close_at TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (awarded_officer_id) REFERENCES officers(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shift_bids (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_id INTEGER NOT NULL,
            officer_id INTEGER NOT NULL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'awarded', 'rejected')),
            FOREIGN KEY (slot_id) REFERENCES shift_bid_slots(id),
            FOREIGN KEY (officer_id) REFERENCES officers(id),
            UNIQUE(slot_id, officer_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS callback_rotation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            officer_id INTEGER NOT NULL UNIQUE,
            sort_order INTEGER NOT NULL,
            active INTEGER DEFAULT 1,
            notes TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (officer_id) REFERENCES officers(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS callback_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            officer_id INTEGER NOT NULL,
            event_date DATE NOT NULL,
            hours REAL NOT NULL,
            notes TEXT,
            created_by_user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (officer_id) REFERENCES officers(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS certification_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT,
            active INTEGER DEFAULT 1
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS officer_certifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            officer_id INTEGER NOT NULL,
            cert_type_id INTEGER NOT NULL,
            issued_date DATE,
            expires_date DATE,
            notes TEXT,
            FOREIGN KEY (officer_id) REFERENCES officers(id),
            FOREIGN KEY (cert_type_id) REFERENCES certification_types(id),
            UNIQUE(officer_id, cert_type_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shift_cert_requirements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_start TEXT NOT NULL,
            cert_type_id INTEGER NOT NULL,
            FOREIGN KEY (cert_type_id) REFERENCES certification_types(id),
            UNIQUE(shift_start, cert_type_id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shift_bids_slot ON shift_bids(slot_id)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shift_bid_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            status TEXT DEFAULT 'draft' CHECK(status IN ('draft', 'open', 'finalized', 'cancelled')),
            number_of_shifts TEXT,
            shift_length TEXT,
            rotation TEXT,
            shift_start_times TEXT,
            shifts_begin TEXT,
            bids_due_by TEXT,
            squad TEXT CHECK(squad IN ('A', 'B') OR squad IS NULL),
            notes TEXT,
            created_by_user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            published_at TEXT,
            finalized_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shift_bid_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            option_number INTEGER NOT NULL,
            label TEXT NOT NULL,
            status TEXT DEFAULT 'open' CHECK(status IN ('open', 'awarded', 'unassigned')),
            awarded_officer_id INTEGER,
            FOREIGN KEY (event_id) REFERENCES shift_bid_events(id) ON DELETE CASCADE,
            FOREIGN KEY (awarded_officer_id) REFERENCES officers(id),
            UNIQUE(event_id, option_number)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shift_bid_rankings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            officer_id INTEGER NOT NULL,
            option_id INTEGER NOT NULL,
            preference_rank INTEGER NOT NULL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES shift_bid_events(id) ON DELETE CASCADE,
            FOREIGN KEY (officer_id) REFERENCES officers(id),
            FOREIGN KEY (option_id) REFERENCES shift_bid_options(id) ON DELETE CASCADE,
            UNIQUE(event_id, officer_id, option_id),
            UNIQUE(event_id, officer_id, preference_rank)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shift_bid_options_event ON shift_bid_options(event_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shift_bid_rankings_event ON shift_bid_rankings(event_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_callback_events_officer ON callback_events(officer_id)")
    defaults = (
        ("FIREARMS", "Firearms Qualification", "Annual range qualification"),
        ("CPR", "CPR / First Aid", "Current CPR certification"),
        ("FTO", "Field Training Officer", "Authorized FTO"),
    )
    for code, name, desc in defaults:
        cursor.execute("SELECT id FROM certification_types WHERE code = ?", (code,))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO certification_types (code, name, description, active) VALUES (?, ?, ?, 1)",
                (code, name, desc),
            )
    _migrate_tier2_bidding_extensions(cursor)


def _migrate_tier2_bidding_extensions(cursor) -> None:
    """Shift-bid v2 columns and simulator scenario library."""
    cursor.execute("PRAGMA table_info(shift_bid_events)")
    event_cols = {row[1] for row in cursor.fetchall()}
    for col, ddl in [
        ("rotation_json", "ALTER TABLE shift_bid_events ADD COLUMN rotation_json TEXT"),
        ("simulation_id", "ALTER TABLE shift_bid_events ADD COLUMN simulation_id INTEGER"),
        ("bids_closed_at", "ALTER TABLE shift_bid_events ADD COLUMN bids_closed_at TEXT"),
    ]:
        if col not in event_cols:
            cursor.execute(ddl)

    cursor.execute("PRAGMA table_info(shift_bid_options)")
    option_cols = {row[1] for row in cursor.fetchall()}
    for col, ddl in [
        ("shift_start", "ALTER TABLE shift_bid_options ADD COLUMN shift_start TEXT"),
        ("shift_date", "ALTER TABLE shift_bid_options ADD COLUMN shift_date TEXT"),
    ]:
        if col not in option_cols:
            cursor.execute(ddl)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS simulator_scenarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            config_json TEXT NOT NULL,
            result_json TEXT,
            notes TEXT,
            created_by_user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_simulator_scenarios_created ON simulator_scenarios(created_at)")


def _backfill_payroll_pay_period_start(cursor) -> None:
    """Assign pay_period_start from shift start date (entry_date)."""
    from datetime import datetime, timedelta

    from config import PAY_PERIOD_BASE_DATE, PAY_PERIOD_LENGTH

    cursor.execute(
        """
        SELECT id, entry_date FROM payroll_entries
        WHERE pay_period_start IS NULL OR pay_period_start = ''
    """
    )
    rows = cursor.fetchall()
    for row in rows:
        entry_date = row["entry_date"]
        if not entry_date:
            continue
        try:
            parsed = datetime.strptime(entry_date[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        period_index = (parsed - PAY_PERIOD_BASE_DATE).days // PAY_PERIOD_LENGTH
        period_start = PAY_PERIOD_BASE_DATE + timedelta(days=period_index * PAY_PERIOD_LENGTH)
        cursor.execute(
            "UPDATE payroll_entries SET pay_period_start = ? WHERE id = ?",
            (period_start.isoformat(), row["id"]),
        )


def _migrate_timecard_multi_entry(cursor) -> None:
    """Allow multiple timecard rows per officer per day (different pay types)."""
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='timecard_entries'")
    row = cursor.fetchone()
    if not row or not row[0] or "UNIQUE(officer_id, entry_date)" not in row[0]:
        return
    cursor.execute("""
        CREATE TABLE timecard_entries__new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            officer_id INTEGER NOT NULL,
            pay_period_start DATE NOT NULL,
            entry_date DATE NOT NULL,
            hours_worked REAL DEFAULT 0,
            time_in TEXT,
            time_out TEXT,
            entry_type TEXT DEFAULT 'Regular Hours',
            night_diff_hours REAL DEFAULT 0,
            notes TEXT,
            payroll_entry_id INTEGER,
            imported_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (officer_id) REFERENCES officers(id),
            FOREIGN KEY (payroll_entry_id) REFERENCES payroll_entries(id)
        )
    """)
    cursor.execute("""
        INSERT INTO timecard_entries__new
        SELECT id, officer_id, pay_period_start, entry_date, hours_worked, time_in, time_out,
               entry_type, night_diff_hours, notes, payroll_entry_id, imported_at,
               created_at, updated_at
        FROM timecard_entries
    """)
    cursor.execute("DROP TABLE timecard_entries")
    cursor.execute("ALTER TABLE timecard_entries__new RENAME TO timecard_entries")


def _migrate_officers_nullable_assignment(cursor) -> None:
    """Allow NULL squad/shift (unassigned) by rebuilding legacy CHECK/NOT NULL schema."""
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='officers'")
    row = cursor.fetchone()
    if not row or not row[0]:
        return
    ddl = row[0]
    if "CHECK(squad" not in ddl and "squad TEXT NOT NULL" not in ddl:
        return

    cursor.execute("PRAGMA table_info(officers)")
    columns = [r[1] for r in cursor.fetchall()]
    col_defs = ", ".join(columns)

    cursor.execute("PRAGMA foreign_keys=OFF")
    cursor.execute("""
        CREATE TABLE officers__new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            seniority_rank INTEGER NOT NULL,
            squad TEXT,
            shift_start TEXT,
            shift_end TEXT,
            pay_rate REAL DEFAULT 30.0,
            night_differential_rate REAL DEFAULT 1.0,
            photo_path TEXT,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            start_date DATE,
            email TEXT,
            phone TEXT,
            address TEXT,
            job_title TEXT,
            annual_hours_target REAL DEFAULT 2080,
            overtime_multiplier REAL DEFAULT 1.5
        )
    """)
    cursor.execute(f"INSERT INTO officers__new ({col_defs}) SELECT {col_defs} FROM officers")
    cursor.execute("DROP TABLE officers")
    cursor.execute("ALTER TABLE officers__new RENAME TO officers")
    cursor.execute("PRAGMA foreign_keys=ON")


def _ensure_indexes(cursor) -> None:
    """Create indexes for common query patterns (safe to re-run)."""
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_overrides_date ON schedule_overrides(override_date)",
        "CREATE INDEX IF NOT EXISTS idx_overrides_original ON schedule_overrides(original_officer_id, override_date)",
        "CREATE INDEX IF NOT EXISTS idx_overrides_replacement ON schedule_overrides(replacement_officer_id, override_date)",
        "CREATE INDEX IF NOT EXISTS idx_requests_status ON day_off_requests(status)",
        "CREATE INDEX IF NOT EXISTS idx_requests_date ON day_off_requests(request_date)",
        "CREATE INDEX IF NOT EXISTS idx_payroll_date ON payroll_entries(entry_date)",
        "CREATE INDEX IF NOT EXISTS idx_payroll_officer ON payroll_entries(officer_id)",
        "CREATE INDEX IF NOT EXISTS idx_payroll_period ON payroll_entries(pay_period_start)",
        "CREATE INDEX IF NOT EXISTS idx_payroll_officer_period ON payroll_entries(officer_id, pay_period_start)",
        "CREATE INDEX IF NOT EXISTS idx_notifications_recipient ON notifications(recipient_officer_id, is_read)",
        "CREATE INDEX IF NOT EXISTS idx_timecard_officer_period ON timecard_entries(officer_id, pay_period_start)",
        "CREATE INDEX IF NOT EXISTS idx_timecard_officer_date ON timecard_entries(officer_id, entry_date)",
        "CREATE INDEX IF NOT EXISTS idx_timecard_date ON timecard_entries(entry_date)",
        "CREATE INDEX IF NOT EXISTS idx_timecard_approval_period ON timecard_approvals(pay_period_start)",
        "CREATE INDEX IF NOT EXISTS idx_timecard_approval_officer ON timecard_approvals(officer_id, pay_period_start)",
        "CREATE INDEX IF NOT EXISTS idx_snapshot_rows_date ON schedule_snapshot_rows(snapshot_id, assignment_date)",
        "CREATE INDEX IF NOT EXISTS idx_snapshot_rows_officer ON schedule_snapshot_rows(officer_id, assignment_date)",
        "CREATE INDEX IF NOT EXISTS idx_holidays_date ON holidays(holiday_date)",
        "CREATE INDEX IF NOT EXISTS idx_availability_officer ON officer_availability(officer_id, unavailable_date)",
        "CREATE INDEX IF NOT EXISTS idx_availability_date ON officer_availability(unavailable_date)",
        "CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_open_shifts_date ON open_shifts(shift_date, status)",
    ]
    for statement in index_statements:
        cursor.execute(statement)


def backup_database() -> str:
    backup_dir = data_path("backups")
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"dodgeville_scheduler_backup_{timestamp}.db")

    if DB_PATH.startswith("file:"):
        src = get_connection()
        try:
            dst = sqlite3.connect(backup_path)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
        return backup_path

    if not os.path.exists(DB_PATH):
        init_database()
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def _resolve_db_file_path() -> str:
    """Filesystem path for the live database (not in-memory URI)."""
    if DB_PATH.startswith("file:"):
        raise RuntimeError("Cannot restore while using in-memory database URI")
    return DB_PATH


def list_backup_files() -> list[str]:
    """Return backup .db paths under backups/, newest first."""
    backup_dir = data_path("backups")
    if not os.path.isdir(backup_dir):
        return []
    files = [
        os.path.join(backup_dir, name)
        for name in os.listdir(backup_dir)
        if name.endswith(".db") and os.path.isfile(os.path.join(backup_dir, name))
    ]
    return sorted(files, key=os.path.getmtime, reverse=True)


def restore_database(backup_path: str) -> str:
    """
    Replace the live database from a backup file.
    Creates a pre-restore safety copy in backups/ first.
    """
    if not os.path.isfile(backup_path):
        raise FileNotFoundError(f"Backup not found: {backup_path}")

    try:
        probe = sqlite3.connect(backup_path)
        try:
            probe.execute("SELECT name FROM sqlite_master LIMIT 1")
        finally:
            probe.close()
    except sqlite3.Error as exc:
        raise ValueError(f"Invalid SQLite backup: {backup_path}") from exc

    live_path = _resolve_db_file_path()
    if os.path.normcase(os.path.normpath(backup_path)) == os.path.normcase(os.path.normpath(live_path)):
        raise ValueError("Cannot restore from the live database file")

    safety = backup_database()
    if not os.path.exists(os.path.dirname(live_path)):
        os.makedirs(os.path.dirname(live_path), exist_ok=True)
    try:
        live_conn = sqlite3.connect(live_path)
        try:
            live_conn.execute("PRAGMA wal_checkpoint(FULL)")
        finally:
            live_conn.close()
    except sqlite3.Error:
        pass
    for suffix in ("", "-wal", "-shm"):
        path = f"{live_path}{suffix}"
        if os.path.isfile(path):
            os.remove(path)
    shutil.copy2(backup_path, live_path)
    return safety
