"""Phase 4 — database.py's backend dispatch (still infra-only/unverified
against real Postgres; see docs/POSTGRES_PORT_INVENTORY.md).

Proves: (1) the SQLite default path is completely untouched by this
dispatch, (2) init_database() fails loudly rather than running wrong DDL
against Postgres, (3) get_connection() routes to db_compat.connect_postgres
when asked.
"""

import pytest

import database


def test_init_database_raises_on_postgres_backend(monkeypatch):
    monkeypatch.setenv("SCHEDULER_DB_BACKEND", "postgres")
    with pytest.raises(RuntimeError, match="does not support SCHEDULER_DB_BACKEND=postgres"):
        database.init_database()


def test_get_connection_postgres_backend_requires_dsn(monkeypatch):
    monkeypatch.setenv("SCHEDULER_DB_BACKEND", "postgres")
    monkeypatch.delenv("SCHEDULER_PG_DSN", raising=False)
    with pytest.raises(RuntimeError, match="SCHEDULER_PG_DSN"):
        database.get_connection()


def test_get_connection_postgres_backend_delegates_to_db_compat(monkeypatch):
    monkeypatch.setenv("SCHEDULER_DB_BACKEND", "postgres")
    monkeypatch.setenv("SCHEDULER_PG_DSN", "postgresql://u:p@host/db")

    calls = {}

    def _fake_connect(dsn):
        calls["dsn"] = dsn
        return "fake-pg-connection"

    monkeypatch.setattr("db_compat.connect_postgres", _fake_connect)

    result = database.get_connection()
    assert result == "fake-pg-connection"
    assert calls["dsn"] == "postgresql://u:p@host/db"


def test_get_connection_default_backend_is_unaffected_sqlite(monkeypatch):
    monkeypatch.delenv("SCHEDULER_DB_BACKEND", raising=False)
    conn = database.get_connection()
    try:
        assert conn.row_factory is not None
    finally:
        conn.close()
