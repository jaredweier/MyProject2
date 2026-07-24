"""Phase 4 — SQLAlchemy engine scaffolding (master plan §9 PostgreSQL move).

db_engine.py doesn't back any live code path yet; this just proves the URL
resolution is correct for both backends before anything depends on it.
"""

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine

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


def test_reflect_metadata_finds_real_tables():
    """Reflects a real (file-backed, not in-memory) SQLite DB built by
    database.init_database() — proves reflection sees actual production
    tables like 'officers' and 'optimizer_jobs', not a hand-typed stand-in
    that could drift from what's really on disk."""
    import database

    with tempfile.TemporaryDirectory() as tmp:
        path = str(Path(tmp) / "reflect_test.db")
        prev_path = database.DB_PATH
        database.DB_PATH = path
        try:
            database.init_database()

            engine = create_engine(f"sqlite:///{path}")
            try:
                metadata = db_engine.reflect_metadata(engine=engine)
            finally:
                engine.dispose()
            assert "officers" in metadata.tables
            assert "optimizer_jobs" in metadata.tables
        finally:
            database.DB_PATH = prev_path
