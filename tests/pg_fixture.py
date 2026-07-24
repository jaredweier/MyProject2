"""Real, ephemeral PostgreSQL for tests — no Docker, no system install, no
admin rights. Uses the `postgresql-binaries` pip package (bundled real
Postgres server binaries) to initdb + start a scratch cluster in a temp
directory on a free port, and stop + delete it afterward.

This exists so the master plan §9 PostgreSQL move can be verified for
real (see docs/POSTGRES_PORT_INVENTORY.md) instead of only unit-tested
against mocks. Tests using this fixture are opt-in (skipped unless
CHRONOS_TEST_POSTGRES=1) since starting a real server takes a couple
seconds and this dependency is dev/test-only.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Iterator

import pytest


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextlib.contextmanager
def ephemeral_postgres() -> Iterator[str]:
    """Yields a DSN for a freshly initdb'd, running, empty Postgres
    database. Tears down (stop + delete data dir) on exit."""
    import postgresql_binaries as pb

    bin_dir = pb.bin()
    port = _free_port()
    tmp_dir = tempfile.mkdtemp(prefix="chronos_pg_test_")
    data_dir = Path(tmp_dir) / "data"

    subprocess.run(
        [
            str(bin_dir / "initdb.exe"),
            "-D",
            str(data_dir),
            "-U",
            "postgres",
            "-A",
            "trust",
            "--no-locale",
            "-E",
            "UTF8",
        ],
        check=True,
        capture_output=True,
    )
    log_path = data_dir / "logfile.txt"
    # pg_ctl start's child postgres.exe keeps stdout/stderr open past pg_ctl's
    # own return on Windows — subprocess.run(capture_output=True) blocks
    # forever waiting for those pipes to close even though the server has
    # already started. Redirect to DEVNULL instead of capturing.
    with open(os.devnull, "wb") as devnull:
        subprocess.run(
            [
                str(bin_dir / "pg_ctl.exe"),
                "-D",
                str(data_dir),
                "-l",
                str(log_path),
                "-o",
                f"-p {port} -c listen_addresses=127.0.0.1 -c max_connections=300 "
                "-c fsync=off -c synchronous_commit=off -c full_page_writes=off",
                "start",
            ],
            check=True,
            stdout=devnull,
            stderr=devnull,
            timeout=30,
        )
    try:
        _wait_for_ready(port)
        import psycopg

        with psycopg.connect(f"postgresql://postgres@127.0.0.1:{port}/postgres", autocommit=True) as conn:
            conn.execute("CREATE DATABASE chronos_test")
        # connect_timeout so a starved/overloaded server fails a connect fast
        # (a few seconds) instead of hanging for the OS-level TCP default —
        # that hang is what made an early test-mode run take 67 minutes for
        # 22 tests instead of surfacing the real problem quickly.
        yield f"postgresql://postgres@127.0.0.1:{port}/chronos_test?connect_timeout=5"
    finally:
        subprocess.run(
            [str(bin_dir / "pg_ctl.exe"), "-D", str(data_dir), "stop", "-m", "fast"],
            capture_output=True,
            timeout=30,
        )
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _wait_for_ready(port: int, timeout: float = 15.0) -> None:
    import psycopg

    deadline = time.monotonic() + timeout
    last_err = None
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(f"postgresql://postgres@127.0.0.1:{port}/postgres", connect_timeout=1):
                return
        except Exception as exc:  # noqa: BLE001 — just retrying until ready or timeout
            last_err = exc
            time.sleep(0.3)
    raise RuntimeError(f"Postgres did not become ready on port {port}: {last_err}")


requires_postgres = pytest.mark.skipif(
    os.environ.get("CHRONOS_TEST_POSTGRES") != "1",
    reason="set CHRONOS_TEST_POSTGRES=1 to run real-Postgres integration tests (starts an ephemeral server)",
)
