"""Date parse/format/storage helpers (validators split)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from config import (
    DATE_INPUT_HINT,
    DATE_PARSE_FORMATS,
    DATE_STORAGE_FORMAT,
)


def _mdy_short(d: date) -> str:
    """UI date: M/D/YY with no leading zeros — e.g. 7/9/26 (July 9, 2026)."""
    return f"{d.month}/{d.day}/{d.year % 100:02d}"


def _mdy_datetime(dt: datetime) -> str:
    """UI datetime: M/D/YY HH:MM — e.g. 7/9/26 14:30."""
    return f"{dt.month}/{dt.day}/{dt.year % 100:02d} {dt.hour:02d}:{dt.minute:02d}"


def format_date(value) -> str:
    """Format any date-like value for UI as M/D/YY (e.g. 7/9/26). Never D/M/YY for July 9."""
    if value is None or value == "":
        return ""
    try:
        if isinstance(value, datetime):
            value = value.date()
        if isinstance(value, date):
            return _mdy_short(value)
        text = str(value).strip()
        if "T" in text:
            text = text.split("T", 1)[0]
        elif len(text) >= 19 and text[10] == " ":
            text = text[:10]
        return _mdy_short(parse_date(text))
    except Exception:
        text = str(value).strip()
        if len(text) >= 10 and text[4] == "-" and text[7] == "-":
            # ISO YYYY-MM-DD → M/D/YY
            try:
                y, m, d = text[:10].split("-")
                return f"{int(m)}/{int(d)}/{int(y) % 100:02d}"
            except Exception:
                return text
        return text


def format_datetime(value) -> str:
    """Format a timestamp for UI as M/D/YY HH:MM (e.g. 7/9/26 14:30)."""
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        return _mdy_datetime(value)
    text = str(value).strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%y %H:%M:%S",
        "%m/%d/%y %H:%M",
        "%m-%d-%Y %H:%M:%S",
        "%m-%d-%Y %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
    ):
        try:
            parsed = datetime.strptime(text[:26].replace("Z", ""), fmt)
            return _mdy_datetime(parsed)
        except ValueError:
            continue
    if len(text) >= 10:
        try:
            return f"{format_date(text[:10])} 00:00"
        except Exception:
            pass
    return text


def format_row_dates(row: dict, *fields: str) -> dict:
    """Return a copy of row with named date fields formatted for display/export."""
    out = dict(row)
    for field in fields:
        if out.get(field):
            out[field] = format_date(out[field])
    return out


def storage_date(value: date) -> str:
    """ISO date string for SQLite storage and internal keys."""
    return value.strftime(DATE_STORAGE_FORMAT)


def storage_date_str(value: str) -> str:
    return storage_date(parse_date(value))


def parse_date_filter(value: Optional[str]) -> Optional[str]:
    """Parse optional user date filter to ISO storage string."""
    if not value or not str(value).strip():
        return None
    return storage_date(parse_date(value.strip()))


def _time_to_minutes(value: str) -> Optional[int]:
    text = (value or "").strip()
    if not text or ":" not in text:
        return None
    parts = text.split(":", 1)
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
    except ValueError:
        return None
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        return None
    return hours * 60 + minutes


def is_overnight_shift(time_in: str, time_out: str) -> bool:
    """True when time_out falls on the next calendar day (e.g. 19:00 → 06:00)."""
    start_mins = _time_to_minutes(time_in)
    end_mins = _time_to_minutes(time_out)
    if start_mins is None or end_mins is None:
        return False
    return end_mins <= start_mins


def parse_date(value: str) -> date:
    """Parse user dates. Prefer month/day (7/9/26 = July 9); also ISO and legacy day/month."""
    text = (value or "").strip()
    if not text:
        raise ValueError(f"Date must be {DATE_INPUT_HINT}")
    candidates = [text]
    if "/" in text and "-" not in text:
        candidates.append(text.replace("/", "-"))
    if "-" in text and "/" not in text:
        candidates.append(text.replace("-", "/"))
    if "." in text:
        candidates.append(text.replace(".", "/"))
        candidates.append(text.replace(".", "-"))

    formats = (
        DATE_PARSE_FORMATS
        if DATE_PARSE_FORMATS
        else (
            "%m/%d/%Y",
            "%m/%d/%y",
            "%m-%d-%Y",
            "%m-%d-%y",
            DATE_STORAGE_FORMAT,
            "%d/%m/%Y",
            "%d/%m/%y",
        )
    )
    for candidate in candidates:
        for fmt in formats:
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
    raise ValueError(f"Date must be {DATE_INPUT_HINT}")
