"""Extract schedule matrix / day-status helpers → logic/scheduling_matrix.py."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "logic" / "scheduling.py"
OUT = ROOT / "logic" / "scheduling_matrix.py"

NAMES = (
    "build_schedule_matrix",
    "get_officer_day_status",
    "batch_officer_day_status",
    "_get_monthly_rotation_base_only",
    "_load_override_maps_for_range",
    "_schedule_status_for_override_reason",
    "_officer_day_status",
    "_officer_history_reason",
    "_officer_shift_hours",
    "_officer_work_days_per_cycle",
    "_rotation_only_status",
    "_shift_hours",
    "get_monthly_rotation_summary",
    "get_officer_work_dates_from_summary",
    "get_schedule_conflicts",
    # also used by rest + matrix
    "_load_covering_shift_starts_for_range",
    "get_officer_effective_shift_band",
)

HEADER = '''"""Schedule matrix, day status, and override maps.

Extracted from ``logic.scheduling``. Re-exported via ``logic.scheduling``.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional, Set, Tuple

from database import get_connection
from logic import rust_bridge, rust_fallback
from logic.officers import get_officer_by_id, get_officers_by_seniority
from logic.rotation_config import (
    get_active_rotation_base_date,
    get_active_rotation_cycle_length,
)
from logic.staffing_config import get_active_shift_times


def _scheduling():
    import logic.scheduling as s

    return s


'''

REEXPORT = """
# Matrix / day status (extracted)
from logic.scheduling_matrix import (  # noqa: E402
    build_schedule_matrix,
    get_officer_day_status,
    batch_officer_day_status,
    get_monthly_rotation_summary,
    get_officer_work_dates_from_summary,
    get_schedule_conflicts,
    get_officer_effective_shift_band,
)
"""


def _rewrite(chunk: str) -> str:
    reps = {
        "_OFFICER_WORKING_STATUSES": "_scheduling()._OFFICER_WORKING_STATUSES",
        "get_cycle_day(": "_scheduling().get_cycle_day(",
        "get_squad_on_duty(": "_scheduling().get_squad_on_duty(",
        "officer_base_rotation_working(": "_scheduling().officer_base_rotation_working(",
        "is_officer_working_on_day(": "_scheduling().is_officer_working_on_day(",
        "resolve_officer_shift_band(": "_scheduling().resolve_officer_shift_band(",
        "_shift_end_for_start(": "_scheduling()._shift_end_for_start(",
        "_shift_bounds(": "_scheduling()._shift_bounds(",
        "_normalize_shift_band(": "_scheduling()._normalize_shift_band(",
        "get_current_cycle_window(": "_scheduling().get_current_cycle_window(",
    }
    # Avoid double-wrapping _scheduling()._scheduling()
    out = chunk
    for a, b in reps.items():
        out = out.replace(a, b)
    # Fix double prefix if any
    out = out.replace("_scheduling()._scheduling()", "_scheduling()")
    return out


def main() -> None:
    src = SRC.read_text(encoding="utf-8")
    if "from logic.scheduling_matrix import" in src and OUT.exists():
        print("already extracted")
        return

    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)
    ranges: dict[str, tuple[int, int]] = {}
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name in NAMES:
            ranges[n.name] = (n.lineno, n.end_lineno or n.lineno)
    missing = [n for n in NAMES if n not in ranges]
    if missing:
        raise SystemExit(f"missing: {missing}")

    parts = []
    for name in NAMES:
        s, e = ranges[name]
        parts.append(_rewrite("".join(lines[s - 1 : e])))

    OUT.write_text(HEADER + "\n\n".join(parts) + "\n", encoding="utf-8")

    for s, e in sorted(ranges.values(), key=lambda t: t[0], reverse=True):
        del lines[s - 1 : e]

    text = "".join(lines).rstrip() + "\n"
    if "from logic.scheduling_matrix import" not in text:
        text += "\n" + REEXPORT + "\n"
    SRC.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.name}; scheduling.py ~{text.count(chr(10)) + 1} lines")


if __name__ == "__main__":
    main()
