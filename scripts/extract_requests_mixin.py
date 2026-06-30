#!/usr/bin/env python3
"""Extract Requests+Swaps methods from ui/app.py into ui/requests_pages.py."""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "ui", "app.py")
OUT = os.path.join(ROOT, "ui", "requests_pages.py")

HEADER = '''"""Day-off requests and shift swaps tab mixin."""

import customtkinter as ctk
from datetime import date
from tkinter import filedialog, messagebox

from config import DAY_OFF_REQUEST_TYPES, REQUEST_STATUS
from logic import (
    bulk_approve_auto_ok_requests,
    bulk_reject_pending_requests,
    create_day_off_request,
    create_shift_swap_request,
    describe_day_off_request,
    export_requests_csv,
    export_requests_pdf,
    export_shift_swaps_csv,
    export_shift_swaps_pdf,
    format_bump_suggestion,
    get_day_off_requests,
    get_officers_by_seniority,
    get_pending_day_off_requests,
    get_pending_shift_swap_requests,
    get_shift_swap_requests,
    process_day_off_request,
    process_shift_swap,
    validate_swap_feasibility,
)
from ui.helpers import handle_export_result, logic_success, logic_message
from ui.theme import (
    CARD_PAD,
    DODGEVILLE_ACCENT,
    DODGEVILLE_BLUE,
    DODGEVILLE_DANGER,
    DODGEVILLE_GOLD,
    DODGEVILLE_SUCCESS,
    DODGEVILLE_WARNING,
    UI_BORDER,
    UI_SURFACE,
    UI_TEXT_MUTED,
    font,
)
from ui.widgets import Card, FormField, SectionHeader, StatusBadge


class RequestsPageMixin:
'''

FOOTER = "\n"


def main():
    with open(APP, encoding="utf-8") as fh:
        lines = fh.readlines()

    # 0-based: from `def _build_requests` through end of swaps section
    start = next(i for i, line in enumerate(lines) if line.strip().startswith("def _build_requests(self):"))
    end = next(i for i, line in enumerate(lines) if line.strip().startswith("# ── Notifications"))
    chunk = lines[start:end]
    body = "".join(chunk)
    body = body.replace("    # ── Requests", "    # ── Requests (mixin)", 1)

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(HEADER + body + FOOTER)

    new_lines = lines[:start] + lines[end:]

    # Update class bases
    content = "".join(new_lines)
    content = content.replace(
        "class DodgevilleSchedulerApp(AdminPageMixin, ReportsPageMixin, AvailabilityPageMixin):",
        "class DodgevilleSchedulerApp(AdminPageMixin, ReportsPageMixin, AvailabilityPageMixin, RequestsPageMixin):",
    )
    import_line = "from ui.requests_pages import RequestsPageMixin\n"
    if import_line not in content:
        content = content.replace(
            "from ui.admin_pages import AdminPageMixin\n",
            "from ui.admin_pages import AdminPageMixin\n" + import_line,
        )

    with open(APP, "w", encoding="utf-8") as fh:
        fh.write(content)

    print(f"Wrote {OUT}, trimmed ui/app.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
