# PostgreSQL port inventory (master plan §9)

**Status: infra verified against a real Postgres, business logic not yet
ported.** `database.py` + `db_compat.py` hand back a Postgres-backed
connection object that supports the same
`.execute()`/`.cursor()`/`.commit()`/`.lastrowid` interface the existing
~41 sqlite3 call sites already use — no call site rewritten yet. This
infra layer (adapter + baseline migration) has been run against a real,
live Postgres server (`tests/test_postgres_integration.py`, ephemeral
cluster via the `postgresql-binaries` pip package — no Docker needed):

- the baseline migration creates all 36 tables cleanly on real Postgres
  (matches the SQLite count exactly)
- the connection adapter's `RETURNING id` → `.lastrowid` emulation and
  name-based row access verified with a real INSERT/SELECT round-trip
- `logic/officers.py` (a real, completely unmodified business-logic file)
  reads and writes correctly against real Postgres through
  `database.get_connection()`

None of the dialect-specific rewrites below have been done or verified —
that's the remaining, larger-risk work. Run
`CHRONOS_TEST_POSTGRES=1 python -m pytest tests/test_postgres_integration.py`
any time to re-verify the infra layer for real.

## What the connection adapter already handles

- `?` → `%s` placeholder translation (`db_compat.translate_placeholders`)
- `cursor.lastrowid` after a bare `INSERT` (transparently appends
  `RETURNING id` — assumes every table's primary key column is literally
  `id`, true for all tables in `database.py`'s current schema; verify this
  still holds before adding a table with a different PK name)
- Row access by column name (psycopg `dict_row`, matches `sqlite3.Row`)

## What still needs a real per-query rewrite (not mechanical)

### SQL-dialect functions/syntax with no Postgres equivalent as written

| Pattern | Files | Postgres equivalent |
|---|---|---|
| `strftime('...', col)` in SQL | ~~`logic/operations.py`~~ (fixed) | Re-audited 2026-07-24: the other 9 files listed here previously (`logic/callbacks.py`, `exports.py`, `extra_duty.py`, `labor_compliance.py`, `optimizer_features.py`, `ot_equity_ledger.py`, `product_impl_kit.py`, `snapshots.py`, `staffing_insights.py`) only use Python's `datetime.strftime()`/`time.strftime()` for filenames/timestamps — not SQL, dialect-agnostic, no rewrite needed. The one real SQL site, `logic/operations.py::get_holidays()`, replaced `strftime('%Y', holiday_date) = ?` with a portable `holiday_date >= ? AND holiday_date < ?` year-range predicate (string comparison on ISO `YYYY-MM-DD` text works identically on both backends) instead of a dialect-specific `to_char()` branch. |
| `PRAGMA foreign_keys` / `PRAGMA journal_mode` | `logic/time_punch.py`, `database.py`, `seed_data.py` | N/A on Postgres — foreign keys are always enforced, WAL has no equivalent pragma; these calls need to become no-ops or removed on the postgres path |
| `INSERT OR IGNORE` | `database.py` (inside `init_database()`'s migration tree — already unreachable on postgres, see step 4) | n/a, no rewrite needed |

Not found in this codebase (checked, none needed): `GROUP_CONCAT`,
`INSERT OR REPLACE`.

### `cursor.lastrowid` call sites (should work transparently via the
adapter's auto-`RETURNING id`, but each needs a real-Postgres check —
listed so nothing gets missed)

`logic/bidding.py`, `logic/callbacks.py`, `logic/geofence_clock.py`,
`logic/leave_donation.py`, `logic/notify_queue.py`, `logic/officers.py`,
`logic/operations.py`, `logic/ot_equity_ledger.py`, `logic/ot_fill.py`,
`logic/requests.py`, `logic/simulator_store.py`, `logic/snapshots.py`,
`logic/stations.py`, `logic/time_punch.py`, `logic/users.py`

### Schema / DDL

`database.py::init_database()` is pure SQLite DDL (`AUTOINCREMENT`, etc.)
and now raises `RuntimeError` if called with
`SCHEDULER_DB_BACKEND=postgres` rather than silently running wrong SQL.
Postgres schema creation goes through
`migrations/versions/8286dcadb953_baseline_reflect_existing_sqlite_schema.py`
via `alembic upgrade head` (not yet run against real Postgres — see
`migrations/env.py`'s reflection-based `target_metadata`).

## Suggested order for the real rewrite (not started)

1. ~~Verify the connection adapter (`db_compat.py`) against a real
   Postgres instance with a handful of the simplest call sites~~ — done,
   see status above.
2. ~~Rewrite the 3 `PRAGMA` sites to skip/no-op on postgres.~~ — done.
   `db_compat.is_postgres_backend()` added; `database.py`'s
   `PRAGMA foreign_keys`/`journal_mode` (get_connection) and all
   `PRAGMA table_info`/DDL-migration sites (init_database call tree) were
   already unreachable on postgres — `init_database()` raises before
   reaching them. `logic/time_punch.py::ensure_punch_tables` and
   `seed_data.py`'s station-column backfill were reachable independent of
   init_database and are now guarded with `is_postgres_backend()`.
   Not yet run against a real Postgres — covered by existing
   `test_postgres_integration.py` infra check only, not a dedicated case.
3. ~~Rewrite the 10 files' `strftime()` calls to `to_char()`~~ — done, see
   status above (only 1 file had a real SQL `strftime()` call; rewritten
   to a portable range predicate instead of a dialect branch).
4. ~~Convert `database.py`'s 1 `INSERT OR IGNORE`~~ — re-audited: it's
   inside the same migration function as the PRAGMA sites from step 2,
   called only from `init_database()`, which already raises before
   reaching the postgres branch. Already unreachable on postgres, no
   rewrite needed.
5. **Not started.** Full suite green with `SCHEDULER_DB_BACKEND=postgres`
   against a real instance before calling the backend supported. Steps
   2-4 are done (2026-07-24) — remaining risk is the ~15
   `cursor.lastrowid` call sites (listed above) and the ~41 sqlite3 call
   sites overall each getting real per-site verification against
   Postgres, not just the adapter-level infra check
   `test_postgres_integration.py` already covers.
