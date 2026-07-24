"""Phase 4 — SQLAlchemy engine scaffolding (master plan §9 PostgreSQL move).

db_engine.py doesn't back any live code path yet; this just proves the URL
resolution is correct for both backends before anything depends on it.
"""

import pytest

import db_engine


def test_default_backend_is_sqlite_using_database_db_path(monkeypatch):
    monkeypatch.delenv("SCHEDULER_DB_BACKEND", raising=False)
    monkeypatch.setattr("database.DB_PATH", "/tmp/some_test.db", raising=False)
    assert db_engine.database_url() == "sqlite:////tmp/some_test.db"


def test_sqlite_backend_rejects_in_memory_uri_paths(monkeypatch):
    monkeypatch.setenv("SCHEDULER_DB_BACKEND", "sqlite")
    monkeypatch.setattr("database.DB_PATH", "file:foo?mode=memory&cache=shared", raising=False)
    with pytest.raises(RuntimeError, match="does not support sqlite3 URI"):
        db_engine.database_url()


def test_postgres_backend_requires_dsn(monkeypatch):
    monkeypatch.setenv("SCHEDULER_DB_BACKEND", "postgres")
    monkeypatch.delenv("SCHEDULER_PG_DSN", raising=False)
    with pytest.raises(RuntimeError, match="SCHEDULER_PG_DSN"):
        db_engine.database_url()


def test_postgres_backend_uses_dsn_verbatim(monkeypatch):
    monkeypatch.setenv("SCHEDULER_DB_BACKEND", "postgres")
    monkeypatch.setenv("SCHEDULER_PG_DSN", "postgresql+psycopg://u:p@host:5432/chronos")
    assert db_engine.database_url() == "postgresql+psycopg://u:p@host:5432/chronos"


def test_unknown_backend_raises(monkeypatch):
    monkeypatch.setenv("SCHEDULER_DB_BACKEND", "mongodb")
    with pytest.raises(RuntimeError, match="Unknown SCHEDULER_DB_BACKEND"):
        db_engine.database_url()
