"""Session-scoped real Postgres backend for running the *existing* test
suite (not just tests/test_postgres_integration.py's dedicated tests)
against a real server.

Master plan §9 port inventory step 5: full suite green with
SCHEDULER_DB_BACKEND=postgres against a real instance. Opt-in via
CHRONOS_PG_TEST_MODE=1 (deliberately a different flag than
CHRONOS_TEST_POSTGRES, which gates tests/test_postgres_integration.py's
own ephemeral-per-test instances — the two must not collide).

One ephemeral Postgres server is started for the whole pytest session
(a fresh initdb per test would make a 300+ call-site suite take forever).
The schema is created once via `alembic upgrade head`. Each
tests.helpers.test_database() call then TRUNCATEs every table instead of
recreating the database, for per-test isolation at SQLite-fixture speed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional

PG_TEST_MODE_ENV = "CHRONOS_PG_TEST_MODE"

_dsn: Optional[str] = None
_ctx = None


def pg_test_mode_enabled() -> bool:
    return os.environ.get(PG_TEST_MODE_ENV) == "1"


def get_session_dsn() -> str:
    """Start (once) and return the shared ephemeral Postgres DSN for this
    test session, with the baseline schema already migrated."""
    global _dsn, _ctx
    if _dsn is not None:
        return _dsn

    from tests.pg_fixture import ephemeral_postgres

    _ctx = ephemeral_postgres()
    _dsn = _ctx.__enter__()

    env = {**os.environ, "SCHEDULER_DB_BACKEND": "postgres", "SCHEDULER_PG_DSN": _dsn}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alembic upgrade head failed for test session Postgres: {result.stderr}")

    return _dsn


def truncate_all_tables(dsn: str) -> None:
    """Reset all tables between tests — much faster than a fresh initdb."""
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as conn:
        rows = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name != 'alembic_version'"
        ).fetchall()
        table_names = [r[0] for r in rows]
        if not table_names:
            return
        quoted = ", ".join(f'"{name}"' for name in table_names)
        conn.execute(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE")


def stop_session() -> None:
    """Tear down the shared server. Call at end of test session (best-effort;
    OS process cleanup on interpreter exit covers the case this isn't reached)."""
    global _dsn, _ctx
    if _dsn is not None:
        from db_compat import close_idle_pool

        close_idle_pool(_dsn)
    if _ctx is not None:
        try:
            _ctx.__exit__(None, None, None)
        except Exception:
            pass
    _dsn = None
    _ctx = None
