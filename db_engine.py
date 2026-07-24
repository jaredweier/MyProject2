"""Master plan §9 — PostgreSQL move, phase 1 (SQLAlchemy abstraction).

Scaffolding only: builds a SQLAlchemy engine URL from environment, for either
SQLite (current default, matches database.py's DB_PATH resolution) or
PostgreSQL (opt-in, docker-compose `postgres` service). Nothing in
logic/*.py uses this engine yet — every existing read/write still goes
through database.py's raw sqlite3 connections. This module exists so
Alembic has a target and the next slice (porting raw SQL to SQLAlchemy
Core) has a stable place to plug in, without touching any working code path.

Env vars:
  SCHEDULER_DB_BACKEND=sqlite (default) | postgres
  SCHEDULER_DB_PATH        — SQLite file path (sqlite backend; reuses the
                              same var database.py already reads)
  SCHEDULER_PG_DSN         — full postgres DSN (postgres backend), e.g.
                              postgresql+psycopg://user:pass@host:5432/chronos
"""

from __future__ import annotations

import os

from sqlalchemy import Engine, create_engine


def database_url() -> str:
    backend = (os.environ.get("SCHEDULER_DB_BACKEND") or "sqlite").strip().lower()
    if backend == "postgres":
        dsn = (os.environ.get("SCHEDULER_PG_DSN") or "").strip()
        if not dsn:
            raise RuntimeError("SCHEDULER_DB_BACKEND=postgres requires SCHEDULER_PG_DSN")
        return dsn
    if backend != "sqlite":
        raise RuntimeError(f"Unknown SCHEDULER_DB_BACKEND={backend!r} (expected sqlite or postgres)")

    from database import DB_PATH  # reuse the same path resolution as the live app

    if DB_PATH.startswith("file:"):
        # SQLAlchemy's sqlite driver takes a plain filesystem path, not a
        # sqlite3 URI (mode=memory&cache=shared etc.) — in-memory/URI paths
        # aren't representable here yet; real files are.
        raise RuntimeError("SQLAlchemy sqlite backend does not support sqlite3 URI paths (mode=memory, etc.)")
    return f"sqlite:///{DB_PATH}"


def get_engine() -> Engine:
    return create_engine(database_url())
