"""Shared test fixtures for Dodgeville PD Scheduler."""

import os
import uuid
from contextlib import contextmanager
from datetime import date
from typing import Iterator, Optional

# Stable "today" for pay-period and calendar tests (cycle day 3, Squad A on duty).
TEST_REFERENCE_DATE = date(2026, 6, 30)


def reference_today() -> date:
    """Stable calendar anchor — use in test assertions instead of date.today()."""
    return TEST_REFERENCE_DATE


@contextmanager
def test_database(seed: bool = True) -> Iterator[str]:
    """Provide an isolated SQLite DB path; resets env and modules cleanly."""
    path = f"file:dpd_test_{uuid.uuid4().hex}?mode=memory&cache=shared"
    prev = os.environ.get("SCHEDULER_DB_PATH")
    prev_seed = os.environ.get("ROSTER_SEED_PATH")
    os.environ["SCHEDULER_DB_PATH"] = path
    if seed:
        fixture = os.path.join(os.path.dirname(__file__), "fixtures", "roster_seed.json")
        os.environ["ROSTER_SEED_PATH"] = fixture
    else:
        os.environ.pop("ROSTER_SEED_PATH", None)

    import database
    import logic  # noqa: F401 — ensure logic uses this connection

    prev_db_path = database.DB_PATH
    database.DB_PATH = path
    # Shared in-memory DB survives only while a connection stays open.
    keepalive = database.get_connection()
    database.init_database()

    try:
        yield path
    finally:
        keepalive.close()
        database.DB_PATH = prev_db_path
        if prev is None:
            os.environ.pop("SCHEDULER_DB_PATH", None)
        else:
            os.environ["SCHEDULER_DB_PATH"] = prev
        if prev_seed is None:
            os.environ.pop("ROSTER_SEED_PATH", None)
        else:
            os.environ["ROSTER_SEED_PATH"] = prev_seed
        if path and not path.startswith("file:") and os.path.exists(path):
            os.unlink(path)


def get_any_officer(
    squad: str = "A",
    shift_start: Optional[str] = None,
    *,
    include_command_staff: bool = False,
) -> dict:
    import logic
    from validators import officer_uses_command_staff_schedule

    officers = logic.get_officers_by_seniority()
    for o in officers:
        if o["squad"] != squad:
            continue
        if shift_start and o["shift_start"] != shift_start:
            continue
        if not include_command_staff and officer_uses_command_staff_schedule(o):
            continue
        return o
    raise ValueError(f"No officer for squad={squad} shift={shift_start}")


def working_date_for_squad(squad: str) -> date:
    """Rotation day when the squad is on duty (stable date near TEST_REFERENCE_DATE)."""
    from datetime import timedelta

    from config import ROTATION_CYCLE_LENGTH
    from logic import get_cycle_day, get_squad_on_duty

    squad = squad.upper()
    anchor = TEST_REFERENCE_DATE
    for offset in range(ROTATION_CYCLE_LENGTH + 1):
        for delta in (offset, -offset):
            day = anchor + timedelta(days=delta)
            if get_squad_on_duty(get_cycle_day(day)) == squad:
                return day
    raise ValueError(f"No working day found for squad {squad}")


def off_date_for_squad(squad: str) -> date:
    """Rotation day when the squad is off (other squad on duty)."""
    other = "B" if squad.upper() == "A" else "A"
    return working_date_for_squad(other)
