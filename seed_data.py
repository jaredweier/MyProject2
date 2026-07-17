"""Seed roster data for development and testing."""

import json
import os
from typing import Any, Dict, List, Optional

from database import get_connection
from paths import data_path, resource_path

DEFAULT_SETTINGS = {
    "rotation_cycle_length": "14",
    "rotation_base_date": "",
    "rotation_preset": "2-2-3 (14-day)",
    "rotation_squad_a_days": "",
    "shift_length_hours": "11",
    "department_annual_hours_target": "2080",
    "shift_count": "4",
    "target_officer_count": "16",
    "department_shift_starts": "06:00, 10:00, 15:00, 19:00",
    "department_shift_times": "",
    "flsa_work_period_days": "",
    "overtime_threshold": "80",
    "locked_pay_period_start": "",
    "setup_complete": "",
    "department_name": "Police Department",
    "department_mission": ("Protect and serve through integrity, partnership, and professional readiness"),
    "department_tagline": "Workforce command",
    "last_auto_backup": "",
}

SEED_HOLIDAYS = [
    ("2026-01-01", "New Year's Day"),
    ("2026-05-25", "Memorial Day"),
    ("2026-07-04", "Independence Day"),
    ("2026-09-07", "Labor Day"),
    ("2026-11-26", "Thanksgiving"),
    ("2026-12-25", "Christmas"),
]


def roster_seed_path() -> Optional[str]:
    """Resolve optional roster seed file (env override, user data dir, then bundle)."""
    override = os.environ.get("ROSTER_SEED_PATH")
    if override and os.path.isfile(override):
        return override
    for candidate in (data_path("roster_seed.json"), resource_path("roster_seed.json")):
        if os.path.isfile(candidate):
            return candidate
    return None


def load_roster_seed() -> Dict[str, Any]:
    path = roster_seed_path()
    if not path:
        return {"officers": [], "demo_users": []}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _insert_seed_officer(cursor, officer: Dict[str, Any]) -> int:
    # Prefer explicit station from seed JSON; default HQ for multi-post board
    station = (officer.get("station") or "HQ").strip() or "HQ"
    workforce = (officer.get("workforce_class") or "sworn").strip() or "sworn"
    try:
        cursor.execute(
            """
            INSERT INTO officers
            (name, seniority_rank, squad, shift_start, shift_end, pay_rate,
             night_differential_rate, job_title, start_date, email, phone, address,
             station, workforce_class)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                officer["name"],
                officer["seniority_rank"],
                officer["squad"],
                officer["shift_start"],
                officer["shift_end"],
                officer.get("pay_rate", 30.0),
                officer.get("night_differential_rate", 1.0),
                officer.get("job_title"),
                officer.get("start_date"),
                officer.get("email"),
                officer.get("phone"),
                officer.get("address"),
                station,
                workforce,
            ),
        )
    except Exception:
        # Older schema without station/workforce_class columns
        cursor.execute(
            """
            INSERT INTO officers
            (name, seniority_rank, squad, shift_start, shift_end, pay_rate,
             night_differential_rate, job_title, start_date, email, phone, address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                officer["name"],
                officer["seniority_rank"],
                officer["squad"],
                officer["shift_start"],
                officer["shift_end"],
                officer.get("pay_rate", 30.0),
                officer.get("night_differential_rate", 1.0),
                officer.get("job_title"),
                officer.get("start_date"),
                officer.get("email"),
                officer.get("phone"),
                officer.get("address"),
            ),
        )
    return cursor.lastrowid


def seed_if_empty() -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM officers")
    count = cursor.fetchone()[0]
    if count > 0:
        conn.close()
        return False

    data = load_roster_seed()
    officers: List[Dict[str, Any]] = data.get("officers", [])
    if not officers:
        conn.close()
        return False

    officer_ids: List[int] = []
    for officer in officers:
        officer_ids.append(_insert_seed_officer(cursor, officer))

    conn.commit()
    conn.close()
    return True


def seed_default_stations() -> bool:
    """Idempotent: ensure HQ station post exists + unassigned active officers get HQ.

    Uses raw SQL only (no logic.* imports) so init/restore never leave logic-layer
    connections open on Windows file-backed temp DBs.
    Safe on existing DBs (does not wipe custom stations or reassign officers who already
    have a station code).
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS station_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                min_staff INTEGER DEFAULT 1,
                active INTEGER DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # station column may be missing on very old DBs — best-effort
        try:
            cursor.execute("PRAGMA table_info(officers)")
            cols = {row[1] for row in cursor.fetchall()}
            if "station" not in cols:
                cursor.execute("ALTER TABLE officers ADD COLUMN station TEXT")
        except Exception:
            pass

        cursor.execute("SELECT COUNT(*) FROM station_posts")
        n_posts = int(cursor.fetchone()[0] or 0)
        if n_posts == 0:
            cursor.execute("SELECT COUNT(*) FROM officers WHERE active = 1")
            n_active = int(cursor.fetchone()[0] or 0)
            min_staff = 2 if n_active >= 4 else 1
            cursor.execute(
                """
                INSERT INTO station_posts (code, name, min_staff, active, notes)
                VALUES ('HQ', 'Headquarters', ?, 1, 'Default seed post')
                """,
                (min_staff,),
            )
        # Assign blank station → HQ (only blanks)
        try:
            cursor.execute(
                """
                UPDATE officers
                SET station = 'HQ'
                WHERE active = 1 AND (station IS NULL OR TRIM(station) = '')
                """
            )
        except Exception:
            pass
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def seed_settings_if_empty() -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM department_settings")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return False
    for key, value in DEFAULT_SETTINGS.items():
        cursor.execute(
            "INSERT INTO department_settings (key, value) VALUES (?, ?)",
            (key, value),
        )
    conn.commit()
    conn.close()
    return True


def seed_holidays_if_empty() -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM holidays")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return False
    for holiday_date, name in SEED_HOLIDAYS:
        cursor.execute(
            """
            INSERT INTO holidays (holiday_date, name, is_paid)
            VALUES (?, ?, 1)
        """,
            (holiday_date, name),
        )
    conn.commit()
    conn.close()
    return True


def seed_users_if_empty() -> bool:
    if os.environ.get("SKIP_DEMO_USERS", "").lower() in ("1", "true", "yes"):
        return False

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM app_users")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return False

    data = load_roster_seed()
    demo_users = data.get("demo_users", [])
    if not demo_users:
        conn.close()
        return False

    officers_json = data.get("officers", [])

    from auth_password import hash_password

    for user in demo_users:
        idx = user.get("officer_index")
        officer_id = None
        if idx is not None and 0 <= idx < len(officers_json):
            cursor.execute(
                "SELECT id FROM officers WHERE name = ?",
                (officers_json[idx]["name"],),
            )
            row = cursor.fetchone()
            officer_id = row[0] if row else None
        cursor.execute(
            """
            INSERT INTO app_users
            (officer_id, username, password, role, must_change_password)
            VALUES (?, ?, ?, ?, 1)
        """,
            (
                officer_id,
                user["username"],
                hash_password(user["password"]),
                user["role"],
            ),
        )

    conn.commit()
    conn.close()
    return True
