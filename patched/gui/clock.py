"""Department-local real time for Chronos Command UI.

User-facing dates: M/D/YY (e.g. 7/9/26 for July 9, 2026); / or -; year 2 or 4 digits.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from config import DEPARTMENT_TIMEZONE


def department_tz() -> ZoneInfo:
    try:
        return ZoneInfo(DEPARTMENT_TIMEZONE)
    except Exception:
        return datetime.now().astimezone().tzinfo or timezone.utc  # type: ignore[return-value]


def now_local() -> datetime:
    try:
        return datetime.now(department_tz())
    except Exception:
        return datetime.now().astimezone()


def today_local() -> date:
    return now_local().date()


def format_clock(value: Optional[datetime] = None, *, seconds: bool = False) -> str:
    dt = value or now_local()
    if dt.tzinfo is None:
        try:
            dt = dt.replace(tzinfo=department_tz())
        except Exception:
            pass
    else:
        try:
            dt = dt.astimezone(department_tz())
        except Exception:
            pass
    return dt.strftime("%H:%M:%S" if seconds else "%H:%M")


def format_local_datetime(value: Optional[datetime] = None) -> str:
    """M/D/YY HH:MM in department local time — e.g. 7/9/26 14:30."""
    from validators import format_datetime

    dt = value or now_local()
    if dt.tzinfo is not None:
        try:
            dt = dt.astimezone(department_tz()).replace(tzinfo=None)
        except Exception:
            dt = dt.replace(tzinfo=None)
    return format_datetime(dt)


def format_local_date(value=None, style: str = "sched") -> str:
    """Return formatted date string.

    style='sched' (default) -> 09-Jul-2026  unambiguous; use in schedules, audits, exports.
    style='short'           -> 7/9/26       compact M/D/YY; use in status bar only.
    """
    from validators import format_date

    if value is None:
        d = today_local()
    elif isinstance(value, datetime):
        if value.tzinfo is not None:
            try:
                value = value.astimezone(department_tz())
            except Exception:
                pass
        d = value.date()
    else:
        d = value
    if style == "short":
        return format_date(d)  # existing M/D/YY behaviour
    return d.strftime("%d-%b-%Y")  # DD-MMM-YYYY unambiguous cross-agency format


def timezone_label() -> str:
    dt = now_local()
    try:
        abbr = dt.tzname() or DEPARTMENT_TIMEZONE
    except Exception:
        abbr = DEPARTMENT_TIMEZONE
    return f"{abbr}"
