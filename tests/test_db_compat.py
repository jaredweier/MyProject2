"""Phase 4 — Postgres connection-compatibility adapter (db_compat.py).

Unit-tests the adapter logic against fakes shaped like psycopg's cursor/
connection API — NOT a real Postgres (none reachable in this environment,
see docs/POSTGRES_PORT_INVENTORY.md). This proves the adapter's own
translation/lastrowid logic is correct; it does not prove the ~41 existing
call sites' actual SQL runs on real Postgres.
"""

from db_compat import PGConnectionAdapter, PGCursorAdapter, translate_placeholders


def test_translate_placeholders_converts_question_marks_to_percent_s():
    assert translate_placeholders("SELECT * FROM officers WHERE id = ?") == "SELECT * FROM officers WHERE id = %s"
    assert translate_placeholders("INSERT INTO t (a, b) VALUES (?, ?)") == "INSERT INTO t (a, b) VALUES (%s, %s)"


class _FakeRawCursor:
    def __init__(self, fetchone_result=None):
        self.executed = []
        self._fetchone_result = fetchone_result

    def execute(self, sql, params):
        self.executed.append((sql, params))

    def fetchone(self):
        return self._fetchone_result

    def fetchall(self):
        return [self._fetchone_result] if self._fetchone_result else []


def test_bare_insert_gets_returning_id_and_populates_lastrowid():
    raw = _FakeRawCursor(fetchone_result={"id": 42})
    cursor = PGCursorAdapter(raw)

    cursor.execute("INSERT INTO officers (name) VALUES (?)", ("Test",))

    assert raw.executed == [("INSERT INTO officers (name) VALUES (%s) RETURNING id", ("Test",))]
    assert cursor.lastrowid == 42


def test_insert_with_existing_returning_is_left_alone():
    raw = _FakeRawCursor(fetchone_result={"id": 7})
    cursor = PGCursorAdapter(raw)

    cursor.execute("INSERT INTO officers (name) VALUES (?) RETURNING id", ("Test",))

    # Not doubled — exactly one RETURNING id clause.
    sql, _ = raw.executed[0]
    assert sql.upper().count("RETURNING") == 1
    # lastrowid is NOT auto-populated here (caller already asked for
    # RETURNING explicitly and presumably reads it themselves via
    # fetchone()) — the adapter only auto-populates for bare INSERTs.
    assert cursor.lastrowid is None


def test_select_does_not_touch_lastrowid_or_append_returning():
    raw = _FakeRawCursor(fetchone_result={"id": 1, "name": "Test"})
    cursor = PGCursorAdapter(raw)

    cursor.execute("SELECT * FROM officers WHERE id = ?", (1,))

    sql, _ = raw.executed[0]
    assert "RETURNING" not in sql.upper()
    assert cursor.lastrowid is None


class _FakeRawConnection:
    def __init__(self):
        self.committed = False
        self.closed = False

    def cursor(self):
        return _FakeRawCursor(fetchone_result={"id": 99})

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def test_connection_adapter_execute_commit_close():
    raw = _FakeRawConnection()
    conn = PGConnectionAdapter(raw)

    cursor = conn.execute("INSERT INTO officers (name) VALUES (?)", ("Test",))
    assert cursor.lastrowid == 99

    conn.commit()
    assert raw.committed is True

    conn.close()
    assert raw.closed is True
