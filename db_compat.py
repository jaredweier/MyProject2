"""Master plan §9 PostgreSQL move — connection-compatibility layer.

**Infra only, unverified against real Postgres** (no Docker/Postgres
reachable in the environment this was written in — see
docs/POSTGRES_PORT_INVENTORY.md for what still needs real-Postgres proof
before this is trusted for production traffic).

Goal: let database.py hand back a Postgres-backed connection that the
existing ~41 call sites can use exactly as they use sqlite3 today —
`conn.execute(sql, params)`, row access by column name, `cursor.lastrowid`
after an INSERT, `.commit()`/`.close()` — without touching those call
sites. This does NOT make SQLite-dialect SQL (strftime(), GROUP_CONCAT,
INSERT OR IGNORE/REPLACE, PRAGMA) run on Postgres; that's a per-query
rewrite tracked in the inventory doc, out of scope here.

The SQLite path in database.py is completely unchanged by this module —
existing behavior, existing tests, zero new risk. This module only
activates when SCHEDULER_DB_BACKEND=postgres.
"""

from __future__ import annotations

import re
from typing import Any, Optional, Sequence

_INSERT_RE = re.compile(r"^\s*INSERT\b", re.IGNORECASE)
_RETURNING_RE = re.compile(r"\bRETURNING\b", re.IGNORECASE)


def translate_placeholders(sql: str) -> str:
    """SQLite's sqlite3 module uses '?' positional placeholders; psycopg
    uses '%s'. Naive text substitution — does not parse SQL, so a literal
    '?' inside a quoted string would also be translated. None of the
    existing ~41 call sites' queries contain literal '?' in string
    literals (grep-verified at write time); if a future query needs one,
    it must be parameterized instead, same as it already must be for
    SQLite to avoid injection."""
    return sql.replace("?", "%s")


class PGCursorAdapter:
    """Wraps a psycopg cursor so `.lastrowid` works like sqlite3's does —
    transparently appends `RETURNING id` to bare INSERT statements (no
    existing call site depends on any other primary-key column name; all
    ~40 tables use `id INTEGER PRIMARY KEY AUTOINCREMENT` per
    database.py's schema — verify this holds before trusting it for a new
    table)."""

    def __init__(self, raw_cursor: Any) -> None:
        self._cursor = raw_cursor
        self.lastrowid: Optional[int] = None

    def execute(self, sql: str, params: Sequence[Any] = ()) -> "PGCursorAdapter":
        translated = translate_placeholders(sql)
        is_bare_insert = bool(_INSERT_RE.match(translated)) and not _RETURNING_RE.search(translated)
        if is_bare_insert:
            translated = translated.rstrip().rstrip(";") + " RETURNING id"
        self._cursor.execute(translated, params)
        if is_bare_insert:
            row = self._cursor.fetchone()
            self.lastrowid = row["id"] if row is not None else None
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


class PGConnectionAdapter:
    """Wraps a psycopg connection so it supports the subset of the
    sqlite3.Connection interface the existing 41 call sites use:
    `.execute()` (delegates to a fresh cursor), `.cursor()`, `.commit()`,
    `.close()`. Rows come back dict-like via psycopg's `dict_row` factory
    (set by the caller building this connection), matching sqlite3.Row's
    name-based access.
    """

    def __init__(self, raw_connection: Any) -> None:
        self._conn = raw_connection

    def cursor(self) -> PGCursorAdapter:
        return PGCursorAdapter(self._conn.cursor())

    def execute(self, sql: str, params: Sequence[Any] = ()) -> PGCursorAdapter:
        return self.cursor().execute(sql, params)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


def connect_postgres(dsn: str) -> PGConnectionAdapter:
    """Open a psycopg connection with dict-row access and wrap it. Import
    is local so psycopg (an optional dependency until the postgres backend
    is actually selected) never has to be installed for the SQLite-only
    default path."""
    import psycopg
    from psycopg.rows import dict_row

    raw = psycopg.connect(dsn, row_factory=dict_row)
    return PGConnectionAdapter(raw)
