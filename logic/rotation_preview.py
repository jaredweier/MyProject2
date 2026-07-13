"""Rotation pattern parsing and shift-bid calendar previews."""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Dict, List, Optional

from validators import parse_date, storage_date_str


def shift_start_times_list(text: Optional[str]) -> List[str]:
    if not text:
        return []
    return re.findall(r"\d{1,2}:\d{2}", str(text))


def shift_start_for_option(event: Dict, option: Dict) -> Optional[str]:
    explicit = option.get("shift_start")
    if explicit:
        return str(explicit).strip()
    times = shift_start_times_list(event.get("shift_start_times"))
    if not times:
        return None
    idx = max(0, int(option.get("option_number", 1)) - 1)
    return times[idx % len(times)]


def parse_bid_rotation_pattern(rotation_text: Optional[str]) -> Dict:
    """Infer a repeating on/off pattern from supervisor free-text rotation."""
    from logic.rotation_config import get_active_rotation_cycle_length, get_active_squad_a_days

    text = (rotation_text or "").strip().lower()
    if not text:
        cycle_len = get_active_rotation_cycle_length()
        squad_days = sorted(get_active_squad_a_days())
        cycle = [day in squad_days for day in range(1, cycle_len + 1)]
        return {
            "kind": "cycle",
            "cycle": cycle,
            "label": f"Department rotation ({cycle_len}-day)",
            "stagger_block": 0,
        }

    match = re.search(r"(\d+)\s*(?:on|/|-)\s*(\d+)(?:\s*off)?", text)
    if match:
        days_on, days_off = int(match.group(1)), int(match.group(2))
        days_on = max(1, min(days_on, 14))
        days_off = max(1, min(days_off, 14))
        cycle = [True] * days_on + [False] * days_off
        return {
            "kind": "on_off",
            "cycle": cycle,
            "label": f"{days_on} on / {days_off} off",
            "stagger_block": days_on,
        }

    if "panama" in text:
        return {
            "kind": "on_off",
            "cycle": [True] * 7 + [False] * 7,
            "label": "Panama (7 on / 7 off)",
            "stagger_block": 7,
        }
    if "continental" in text:
        return {
            "kind": "on_off",
            "cycle": [True, True, True, False, False, True, True],
            "label": "Continental (5 on / 2 off)",
            "stagger_block": 3,
        }
    if "2-2-3" in text or "dodgeville" in text or "2/2/3" in text:
        cycle_len = get_active_rotation_cycle_length()
        squad_days = sorted(get_active_squad_a_days())
        cycle = [day in squad_days for day in range(1, cycle_len + 1)]
        return {
            "kind": "cycle",
            "cycle": cycle,
            "label": "2-2-3 (department rotation)",
            "stagger_block": 0,
        }

    cycle_len = get_active_rotation_cycle_length()
    squad_days = sorted(get_active_squad_a_days())
    cycle = [day in squad_days for day in range(1, cycle_len + 1)]
    return {
        "kind": "cycle",
        "cycle": cycle,
        "label": f"Department rotation ({text or 'default'})",
        "stagger_block": 0,
    }


def rotation_pattern_from_json(raw: Optional[str]) -> Optional[Dict]:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or "cycle" not in data:
        return None
    return data


def serialize_rotation_pattern(pattern: Dict, *, shift_starts: Optional[List[str]] = None) -> str:
    payload = {
        "kind": pattern.get("kind"),
        "cycle": pattern.get("cycle"),
        "label": pattern.get("label"),
        "stagger_block": pattern.get("stagger_block", 0),
    }
    if shift_starts:
        payload["shift_starts"] = shift_starts
    return json.dumps(payload)


def build_shift_bid_option_calendar(
    event: Dict,
    option: Dict,
    *,
    weeks: int = 6,
) -> Dict:
    """Projected on/off days for one bid shift option."""
    stored = rotation_pattern_from_json(event.get("rotation_json"))
    pattern = stored or parse_bid_rotation_pattern(event.get("rotation"))
    cycle = pattern["cycle"]
    if not cycle:
        return {"success": False, "message": "Could not parse rotation pattern"}

    begin_raw = event.get("shifts_begin")
    if begin_raw:
        try:
            start = parse_date(storage_date_str(begin_raw))
        except ValueError:
            try:
                start = parse_date(begin_raw)
            except ValueError:
                start = date.today()
    else:
        start = date.today()

    option_number = int(option.get("option_number") or 1)
    offset = 0
    if pattern["kind"] == "on_off" and pattern.get("stagger_block"):
        offset = (option_number - 1) * int(pattern["stagger_block"])

    total_days = weeks * 7
    end = start + timedelta(days=total_days - 1)
    days: List[Dict] = []
    on_count = 0
    for idx in range(total_days):
        current = start + timedelta(days=idx)
        cycle_idx = (idx + offset) % len(cycle)
        is_on = bool(cycle[cycle_idx])
        if is_on:
            on_count += 1
        from validators import format_date

        days.append(
            {
                "date": current.isoformat(),  # storage key (ISO)
                "date_display": format_date(current),  # UI M/D/YY e.g. 7/9/26
                "day": current.day,
                "month": current.month,
                "year": current.year,
                "weekday": current.weekday(),
                "on": is_on,
            }
        )

    from validators import format_date as _fmt

    return {
        "success": True,
        "option_id": option.get("id"),
        "option_label": option.get("label"),
        "shift_start": shift_start_for_option(event, option),
        "pattern_label": pattern["label"],
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "start_date_display": _fmt(start),
        "end_date_display": _fmt(end),
        "weeks": weeks,
        "on_count": on_count,
        "off_count": total_days - on_count,
        "days": days,
    }


def award_schedule_dates(event: Dict, option: Dict, *, weeks: int = 2) -> List[tuple]:
    """On-duty (date, shift_start) pairs for applying bid awards to the live schedule."""
    preview = build_shift_bid_option_calendar(event, option, weeks=weeks)
    if not preview.get("success"):
        return []
    shift_start = preview.get("shift_start")
    if not shift_start:
        return []
    return [(entry["date"], shift_start) for entry in preview.get("days", []) if entry.get("on")]
