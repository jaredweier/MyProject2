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

import os
import re
import threading
from typing import Any, Optional, Sequence

_INSERT_RE = re.compile(r"^\s*INSERT\s+INTO\s+([A-Za-z0-9_\"]+)", re.IGNORECASE)
_RETURNING_RE = re.compile(r"\bRETURNING\b", re.IGNORECASE)

# Tables whose primary key isn't an `id` INTEGER column — the lastrowid
# emulation's blind `RETURNING id` append is wrong for these (real-Postgres
# verification, 2026-07-24: department_settings's PK is `key` TEXT, no `id`
# column at all — see docs/POSTGRES_PORT_INVENTORY.md step 5). No existing
# call site reads .lastrowid after inserting into these tables (sqlite3
# silently no-ops there instead of erroring), so skipping the rewrite for
# them is safe.
_NON_ID_PK_TABLES = {"department_settings", "officer_time_banks"}

# Lightweight per-DSN idle-connection pool (no external pool dependency).
# Existing call sites open+close a connection per logical operation
# (database.get_connection() / logic.connection()); without pooling that's
# a fresh TCP handshake + Postgres backend fork every time, which is what
# made a 22-test run take 67 minutes real-Postgres-verified (2026-07-24 —
# see docs/POSTGRES_PORT_INVENTORY.md step 5). Reusing idle connections
# keeps the same call-site interface (.close() still "closes" from the
# caller's perspective — it just returns the raw connection to the pool).
_pool_lock = threading.Lock()
_idle_pools: dict[str, list[Any]] = {}
_MAX_IDLE_PER_DSN = 20


def close_idle_pool(dsn: str) -> None:
    """Close and drop every idle pooled connection for a DSN. Call when a
    test session's ephemeral Postgres server is about to be torn down —
    otherwise those connections would error against a dead server."""
    with _pool_lock:
        idle = _idle_pools.pop(dsn, [])
    for conn in idle:
        try:
            conn.close()
        except Exception:
            pass


def is_postgres_backend() -> bool:
    """True when SCHEDULER_DB_BACKEND=postgres. Used to skip SQLite-only
    PRAGMA/introspection calls that have no Postgres equivalent — the
    baseline Alembic migration already creates these columns, so the
    add-column-if-missing check they guard is unneeded there."""
    return (os.environ.get("SCHEDULER_DB_BACKEND") or "sqlite").strip().lower() == "postgres"


def translate_placeholders(sql: str) -> str:
    """SQLite's sqlite3 module uses '?' positional placeholders; psycopg
    uses '%s'. Naive text substitution — does not parse SQL, so a literal
    '?' inside a quoted string would also be translated. None of the
    existing ~41 call sites' queries contain literal '?' in string
    literals (grep-verified at write time); if a future query needs one,
    it must be parameterized instead, same as it already must be for
    SQLite to avoid injection."""
    return sql.replace("?", "%s")


class _DualAccessRow:
    """Mimics sqlite3.Row: supports both row["col"] and row[0] (positional
    by column order), since existing call sites use both interchangeably —
    real-Postgres verification (2026-07-24, see
    docs/POSTGRES_PORT_INVENTORY.md step 5) found `cursor.fetchone()[0]`
    call sites that psycopg's plain dict_row can't satisfy (dict keys are
    strings only)."""

    __slots__ = ("_data", "_keys")

    def __init__(self, data: dict) -> None:
        self._data = data
        self._keys = list(data.keys())

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._data[self._keys[key]]
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def keys(self):
        return self._data.keys()

    def items(self):
        return self._data.items()

    def __iter__(self):
        return iter(self._data.values())

    def __len__(self):
        return len(self._data)

    def __contains__(self, key):
        return key in self._data

    def __eq__(self, other):
        if isinstance(other, _DualAccessRow):
            return self._data == other._data
        return self._data == other

    def __repr__(self):
        return f"_DualAccessRow({self._data!r})"


def _dual_access_row_factory(cursor):
    from psycopg.rows import dict_row

    inner = dict_row(cursor)

    def make_row(values):
        return _DualAccessRow(inner(values))

    return make_row


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
        insert_match = _INSERT_RE.match(translated)
        table_name = insert_match.group(1).strip('"').lower() if insert_match else None
        is_bare_insert = (
            insert_match is not None and table_name not in _NON_ID_PK_TABLES and not _RETURNING_RE.search(translated)
        )
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

    def __init__(self, raw_connection: Any, dsn: Optional[str] = None) -> None:
        self._conn = raw_connection
        self._dsn = dsn
        self._returned = False

    def cursor(self) -> PGCursorAdapter:
        return PGCursorAdapter(self._conn.cursor())

    def execute(self, sql: str, params: Sequence[Any] = ()) -> PGCursorAdapter:
        return self.cursor().execute(sql, params)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        """Matches sqlite3's close() semantics for existing call sites, but
        returns the connection to the pool instead of tearing down the TCP
        connection, unless it's broken or the pool is already full."""
        if self._returned:
            return
        self._returned = True
        if self._dsn is None or self._conn.closed:
            try:
                self._conn.close()
            except Exception:
                pass
            return
        try:
            self._conn.rollback()  # discard any uncommitted work before reuse
        except Exception:
            try:
                self._conn.close()
            except Exception:
                pass
            return
        with _pool_lock:
            idle = _idle_pools.setdefault(self._dsn, [])
            if len(idle) < _MAX_IDLE_PER_DSN:
                idle.append(self._conn)
                return
        try:
            self._conn.close()
        except Exception:
            pass

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


def connect_postgres(dsn: str) -> PGConnectionAdapter:
    """Return a psycopg connection with dict-row access, wrapped. Reuses an
    idle pooled connection for this DSN when available; opens a fresh one
    otherwise. Import is local so psycopg (an optional dependency until the
    postgres backend is actually selected) never has to be installed for
    the SQLite-only default path."""
    import psycopg

    with _pool_lock:
        idle = _idle_pools.get(dsn)
        raw = idle.pop() if idle else None

    if raw is not None and not raw.closed:
        try:
            raw.execute("SELECT 1")
            return PGConnectionAdapter(raw, dsn)
        except Exception:
            try:
                raw.close()
            except Exception:
                pass

    raw = psycopg.connect(dsn, row_factory=_dual_access_row_factory)
    _register_text_loaders(raw)
    return PGConnectionAdapter(raw, dsn)


def _register_text_loaders(raw_connection: Any) -> None:
    """SQLite has no real DATE/TIMESTAMP type — every existing call site
    stores and reads dates as plain TEXT (`?.strip()`, string slicing,
    `date.fromisoformat(row["x"])`, etc). Postgres's DATE/TIMESTAMP columns
    are real types and psycopg auto-converts them to datetime.date/datetime
    objects by default, which broke call sites expecting a string
    (real-Postgres verification, 2026-07-24 — see
    docs/POSTGRES_PORT_INVENTORY.md step 5, e.g.
    validators_dates.py::parse_date crashing on a date object). Registering
    the plain-text loader for these OIDs makes psycopg hand back the same
    ISO-formatted string SQLite always did, matching every existing call
    site's assumption without touching them."""
    from psycopg.types.string import TextLoader

    for type_name in ("date", "timestamp", "timestamptz"):
        raw_connection.adapters.register_loader(type_name, TextLoader)
