"""Real, live-Postgres integration proof for master plan §9's PostgreSQL
move — not mocks. Uses tests/pg_fixture.py's ephemeral server (real
Postgres binaries via the `postgresql-binaries` pip package, no Docker).

Opt-in: set CHRONOS_TEST_POSTGRES=1 to run. Not in the fast/default test
tier since it starts a real server (a couple seconds of startup cost).
"""

import os
import subprocess
import sys

from tests.pg_fixture import ephemeral_postgres, requires_postgres


@requires_postgres
def test_baseline_migration_creates_all_tables_on_real_postgres():
    with ephemeral_postgres() as dsn:
        env = {**os.environ, "SCHEDULER_DB_BACKEND": "postgres", "SCHEDULER_PG_DSN": dsn}
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr

        import psycopg

        with psycopg.connect(dsn) as conn:
            rows = conn.execute(
                "select table_name from information_schema.tables where table_schema='public'"
            ).fetchall()
        table_names = {r[0] for r in rows}
        assert "officers" in table_names
        assert "optimizer_jobs" in table_names
        assert len(table_names) == 36  # matches the SQLite baseline exactly


@requires_postgres
def test_db_compat_adapter_lastrowid_and_row_access_on_real_postgres():
    with ephemeral_postgres() as dsn:
        env = {**os.environ, "SCHEDULER_DB_BACKEND": "postgres", "SCHEDULER_PG_DSN": dsn}
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, check=True, capture_output=True)

        from db_compat import connect_postgres

        conn = connect_postgres(dsn)
        try:
            cur = conn.execute(
                "INSERT INTO officers (name, seniority_rank, squad, shift_start, shift_end) VALUES (?, ?, ?, ?, ?)",
                ("Test Officer", 1, "A", "07:00", "15:00"),
            )
            assert cur.lastrowid is not None

            row = conn.execute("SELECT * FROM officers WHERE id = ?", (cur.lastrowid,)).fetchone()
            assert row["name"] == "Test Officer"
            conn.commit()
        finally:
            conn.close()


@requires_postgres
def test_unmodified_logic_officers_module_works_against_real_postgres(monkeypatch):
    """The real proof this whole adapter exists for: a business-logic file
    from the ~41 call sites, completely unmodified, reading/writing
    correctly against real Postgres."""
    with ephemeral_postgres() as dsn:
        env = {**os.environ, "SCHEDULER_DB_BACKEND": "postgres", "SCHEDULER_PG_DSN": dsn}
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, check=True, capture_output=True)

        monkeypatch.setenv("SCHEDULER_DB_BACKEND", "postgres")
        monkeypatch.setenv("SCHEDULER_PG_DSN", dsn)

        from logic.officers import get_officer_by_id, get_officers_by_seniority

        assert get_officers_by_seniority() == []

        import database

        conn = database.get_connection()
        conn.execute(
            "INSERT INTO officers (name, seniority_rank, squad, shift_start, shift_end) VALUES (?, ?, ?, ?, ?)",
            ("Officer One", 1, "A", "07:00", "15:00"),
        )
        conn.commit()
        conn.close()

        rows = get_officers_by_seniority()
        assert len(rows) == 1
        assert rows[0]["name"] == "Officer One"
        assert get_officer_by_id(rows[0]["id"])["name"] == "Officer One"
