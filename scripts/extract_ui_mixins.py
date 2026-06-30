#!/usr/bin/env python3
"""Extract ui/app.py tab sections into mixin modules (bottom-up)."""

from __future__ import annotations

import os
import re
from typing import Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "ui", "app.py")

# Process bottom-up so line indices stay valid when removing chunks.
MIXINS: List[Dict] = [
    {
        "class_name": "SimulatorPageMixin",
        "module": "simulator_pages",
        "doc": "Schedule simulator training tab.",
        "start": "Schedule Simulator",
        "end": "def run():",
    },
    {
        "class_name": "PayrollPageMixin",
        "module": "payroll_pages",
        "doc": "Timecard, payroll, and pay-period exports.",
        "start": "Timecard",
        "end": "Schedule Simulator",
        "extra_start": "Notifications",
        "extra_end": "Gantt Timeline",
        "extra_methods_prefix": "_export_pay",
    },
    {
        "class_name": "SchedulePageMixin",
        "module": "schedule_pages",
        "doc": "Gantt timeline and monthly base/updated schedules.",
        "start": "Gantt Timeline",
        "end": "Timecard",
    },
    {
        "class_name": "NotificationsPageMixin",
        "module": "notifications_pages",
        "doc": "In-app notification inbox and navigation.",
        "start": "Notifications",
        "end": "def _export_payroll_pdf",
    },
    {
        "class_name": "OfficersPageMixin",
        "module": "officers_pages",
        "doc": "Officer roster CRUD, photos, and CSV import.",
        "start": "Officers",
        "end": "Notifications",
    },
]

STDLIB_IMPORTS = {
    "date": "from datetime import date",
    "datetime": "from datetime import datetime",
    "timedelta": "from datetime import timedelta",
    "Tuple": "from typing import Tuple",
    "Optional": "from typing import Optional",
    "filedialog": "from tkinter import filedialog",
    "messagebox": "from tkinter import messagebox",
    "monthrange": "from calendar import monthrange",
}

CONFIG_SYMBOLS = {
    "DAY_OFF_REQUEST_TYPES",
    "DEFAULT_ANNUAL_HOURS",
    "GANTT_COLORS",
    "PAYROLL_ENTRY_TYPES",
    "REQUEST_STATUS",
    "SHIFT_TIMES",
    "SIMULATOR_ROTATION_TYPES",
    "SNAPSHOT_STATUSES",
    "TIMECARD_ENTRY_TYPES",
}

THEME_SYMBOLS = {
    "CARD_PAD",
    "CORNER_RADIUS",
    "DODGEVILLE_ACCENT",
    "DODGEVILLE_BLUE",
    "DODGEVILLE_DANGER",
    "DODGEVILLE_GOLD",
    "DODGEVILLE_RED",
    "DODGEVILLE_SUCCESS",
    "DODGEVILLE_WARNING",
    "UI_BG",
    "UI_BORDER",
    "UI_SIDEBAR",
    "UI_SURFACE",
    "UI_SURFACE_LIGHT",
    "UI_TEXT_MUTED",
    "font",
}

WIDGET_SYMBOLS = {
    "AlertBanner",
    "Card",
    "CoverageBadge",
    "FormField",
    "MetricRow",
    "NavButton",
    "SearchBar",
    "SectionHeader",
    "StatCard",
    "StatusBadge",
}

HELPER_SYMBOLS = {"handle_export_result", "refresh_all_officer_dropdowns", "logic_success", "logic_message"}

PHOTOS_SYMBOLS = {"load_thumbnail"}

VALIDATOR_SYMBOLS = {"parse_date"}


def _parse_app_imports(text: str) -> Dict[str, List[str]]:
    logic_block = re.search(r"from logic import \((.*?)\)", text, re.S)
    logic_names = []
    if logic_block:
        for line in logic_block.group(1).splitlines():
            token = line.strip().split("#")[0].strip().rstrip(",")
            if not token:
                continue
            if " as " in token:
                logic_names.append(token.split(" as ")[0].strip())
            else:
                logic_names.append(token)
    return {"logic": logic_names}


def _find_line(lines: List[str], pattern: str, start: int = 0) -> int:
    needle = pattern.strip()
    for i in range(start, len(lines)):
        line = lines[i]
        if needle in line:
            return i
        # Section banners: match on title text if unicode dashes differ
        if needle.startswith("#") and "──" in needle:
            title = needle.split("──", 1)[-1].strip()
            if title and title in line and line.strip().startswith("#"):
                return i
    raise ValueError(f"Marker not found: {pattern!r}")


def _collect_extra_methods(
    lines: List[str], start_marker: str, end_marker: str, prefix: str
) -> Tuple[List[str], List[int]]:
    start = _find_line(lines, start_marker)
    end = _find_line(lines, end_marker, start)
    picked: List[str] = []
    indices: List[int] = []
    i = start
    while i < end:
        line = lines[i]
        m = re.match(r"    def (\w+)\(", line)
        if m and m.group(1).startswith(prefix):
            j = i
            while j < end:
                picked.append(lines[j])
                j += 1
                if j < end and lines[j].startswith("    def ") and j != i:
                    break
                if j < end and lines[j].startswith("    # ──"):
                    break
            indices.extend(range(i, j))
            i = j
            continue
        i += 1
    return picked, indices


def _build_imports(chunk: str, logic_names: List[str]) -> str:
    stdlib = []
    for sym, stmt in STDLIB_IMPORTS.items():
        if re.search(rf"\b{sym}\b", chunk):
            if stmt not in stdlib:
                stdlib.append(stmt)

    config_used = sorted(s for s in CONFIG_SYMBOLS if re.search(rf"\b{s}\b", chunk))
    theme_used = sorted(s for s in THEME_SYMBOLS if re.search(rf"\b{s}\b", chunk))
    widget_used = sorted(s for s in WIDGET_SYMBOLS if re.search(rf"\b{s}\b", chunk))
    helper_used = sorted(s for s in HELPER_SYMBOLS if re.search(rf"\b{s}\b", chunk))
    photos_used = sorted(s for s in PHOTOS_SYMBOLS if re.search(rf"\b{s}\b", chunk))
    validator_used = sorted(s for s in VALIDATOR_SYMBOLS if re.search(rf"\b{s}\b", chunk))
    logic_used = sorted(n for n in logic_names if re.search(rf"\b{n}\b", chunk))

    parts = ['"""{doc}"""', "", "import customtkinter as ctk"]
    parts.extend(stdlib)
    if config_used:
        parts.append(f"from config import {', '.join(config_used)}")
    if logic_used:
        parts.append("from logic import (")
        for name in logic_used:
            parts.append(f"    {name},")
        parts.append(")")
    if photos_used:
        parts.append(f"from photos import {', '.join(photos_used)}")
    if validator_used:
        parts.append(f"from validators import {', '.join(validator_used)}")
    if helper_used:
        parts.append(f"from ui.helpers import {', '.join(helper_used)}")
    if theme_used:
        parts.append("from ui.theme import (")
        for name in theme_used:
            parts.append(f"    {name},")
        parts.append(")")
    if widget_used:
        parts.append(f"from ui.widgets import {', '.join(widget_used)}")
    return "\n".join(parts)


def _extract_chunk(lines: List[str], start_marker: str, end_marker: str) -> Tuple[str, int, int]:
    start = _find_line(lines, start_marker)
    end = _find_line(lines, end_marker, start + 1)
    body_lines = lines[start:end]
    # Drop section banner comment; keep method defs
    if body_lines and body_lines[0].strip().startswith("# ──"):
        body_lines = body_lines[1:]
    return "".join(body_lines), start, end


def main() -> int:
    with open(APP, encoding="utf-8") as fh:
        lines = fh.readlines()

    app_text = "".join(lines)
    imports = _parse_app_imports(app_text)
    logic_names = imports["logic"]

    created: List[str] = []
    mixin_classes: List[str] = []
    all_remove_ranges: List[Tuple[int, int]] = []
    original_lines = list(lines)

    for spec in MIXINS:
        chunk, start, end = _extract_chunk(original_lines, spec["start"], spec["end"])
        remove_ranges = [(start, end)]

        if spec.get("extra_methods_prefix"):
            extra_lines, extra_indices = _collect_extra_methods(
                original_lines,
                spec["extra_start"],
                spec["extra_end"],
                spec["extra_methods_prefix"],
            )
            if extra_lines:
                chunk = "".join(extra_lines) + chunk
                if extra_indices:
                    remove_ranges.append((min(extra_indices), max(extra_indices) + 1))

        header = _build_imports(chunk, logic_names).format(doc=spec["doc"])
        module_path = os.path.join(ROOT, "ui", f"{spec['module']}.py")
        with open(module_path, "w", encoding="utf-8") as fh:
            fh.write(header + "\n\n\n")
            fh.write(f"class {spec['class_name']}:\n")
            fh.write(chunk)
        created.append(spec["module"])
        mixin_classes.append(spec["class_name"])
        all_remove_ranges.extend(remove_ranges)

    for rm_start, rm_end in sorted(all_remove_ranges, reverse=True):
        del lines[rm_start:rm_end]

    content = "".join(lines)

    # Update class bases and imports
    base_match = re.search(
        r"class DodgevilleSchedulerApp\((.*?)\):",
        content,
    )
    if not base_match:
        raise RuntimeError("DodgevilleSchedulerApp class not found")

    existing = [b.strip() for b in base_match.group(1).split(",") if b.strip()]
    for cls, mod in zip(mixin_classes, created):
        if cls not in existing:
            existing.append(cls)
        import_line = f"from ui.{mod} import {cls}\n"
        if import_line not in content:
            content = content.replace(
                "from ui.admin_pages import AdminPageMixin\n",
                "from ui.admin_pages import AdminPageMixin\n" + import_line,
            )

    new_bases = ", ".join(existing)
    content = re.sub(
        r"class DodgevilleSchedulerApp\([^)]+\):",
        f"class DodgevilleSchedulerApp({new_bases}):",
        content,
        count=1,
    )

    with open(APP, "w", encoding="utf-8") as fh:
        fh.write(content)

    print("Created mixins:")
    for mod in created:
        print(f"  ui/{mod}.py")
    print(f"Trimmed {APP}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
