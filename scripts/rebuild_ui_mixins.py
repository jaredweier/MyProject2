#!/usr/bin/env python3
"""Rebuild ui/app.py and mixin modules after a failed bulk extraction."""

from __future__ import annotations

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NOTIF = os.path.join(ROOT, "ui", "notifications_pages.py")
PAYROLL = os.path.join(ROOT, "ui", "payroll_pages.py")
APP = os.path.join(ROOT, "ui", "app.py")


def _read(path: str) -> list[str]:
    with open(path, encoding="utf-8") as fh:
        return fh.readlines()


def _slice_by_marker(lines: list[str], start: str, end: str | None = None) -> list[str]:
    s = next(i for i, ln in enumerate(lines) if start in ln and ln.strip().startswith(("#", "def")))
    if end:
        e = next(i for i, ln in enumerate(lines) if end in ln and i > s)
        return lines[s:e]
    return lines[s:]


def _body_only(chunk: list[str]) -> str:
    out = []
    for ln in chunk:
        if ln.strip().startswith("# ──"):
            continue
        out.append(ln)
    return "".join(out)


def _write_mixin(path: str, doc: str, class_name: str, body: str, header: str):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f'"""{doc}"""\n\n')
        fh.write(header.rstrip() + "\n\n\n")
        fh.write(f"class {class_name}:\n")
        fh.write(body)


def main() -> int:
    notif_lines = _read(NOTIF)
    payroll_lines = _read(PAYROLL)
    app_lines = _read(APP)

    # Salvage complete sections from notifications_pages (payroll chunk duplicate).
    dashboard_chunk = _slice_by_marker(notif_lines, "def _build_dashboard", "Officers")
    officers_chunk = _slice_by_marker(notif_lines, "Officers", "Notifications")
    notifications_chunk = _slice_by_marker(notif_lines, "def _build_notifications", None)

    payroll_export_chunk = payroll_lines[100:157]  # _export_payroll_* through blank before gantt fragment
    timecard_payroll_chunk = _slice_by_marker(payroll_lines, "Timecard", None)

    # Profile dialog tail (nav buttons) — corrupted chunk in payroll_pages.
    profile_tail = payroll_lines[157:193]

    # Shell helpers after profile (sign_out … _refresh_page).
    shell_chunk = _slice_by_marker(notif_lines, "def sign_out", "Dashboard")

    # app.py head through _export_pdf_result (line ~417).
    head_end = next(i for i, ln in enumerate(app_lines) if "def _show_my_profile" in ln)
    app_head = "".join(app_lines[:head_end])

    profile_head = "".join(app_lines[head_end:])  # truncated profile start

    dashboard_header = """import customtkinter as ctk
from datetime import date, timedelta
from tkinter import messagebox

from logic import (
    get_current_cycle_window,
    get_cycle_day,
    get_dashboard_insights,
    get_day_off_requests,
    get_pending_day_off_requests,
    get_pending_shift_swap_requests,
    get_squad_on_duty,
    get_unread_notification_count,
    get_upcoming_holidays,
)
from ui.theme import (
    CARD_PAD,
    CORNER_RADIUS,
    DODGEVILLE_ACCENT,
    DODGEVILLE_BLUE,
    DODGEVILLE_GOLD,
    DODGEVILLE_RED,
    DODGEVILLE_WARNING,
    UI_BG,
    UI_SURFACE,
    UI_TEXT_MUTED,
    font,
)
from ui.widgets import AlertBanner, Card, SectionHeader, StatCard"""

    officers_header = """import customtkinter as ctk
from datetime import date
from tkinter import filedialog, messagebox

from logic import (
    add_officer,
    bulk_adjust_pay_rates,
    delete_officer,
    get_officer_by_id,
    get_officers_by_seniority,
    get_suggested_seniority_rank,
    import_roster_from_csv,
    project_officer_annual_pay,
    remove_officer_photo as logic_remove_officer_photo,
    set_officer_photo,
    update_officer,
)
from photos import load_thumbnail
from ui.helpers import refresh_all_officer_dropdowns
from ui.theme import (
    CARD_PAD,
    DODGEVILLE_ACCENT,
    DODGEVILLE_BLUE,
    DODGEVILLE_GOLD,
    DODGEVILLE_RED,
    DODGEVILLE_WARNING,
    UI_BORDER,
    UI_SURFACE,
    UI_TEXT_MUTED,
    font,
)
from ui.widgets import Card, FormField, SearchBar, SectionHeader"""

    notifications_header = """import customtkinter as ctk

from logic import (
    export_requests_pdf,
    get_notification_types,
    get_notifications,
    get_officers_by_seniority,
    get_unread_notification_count,
    mark_all_notifications_read,
    mark_notification_read,
    resolve_notification_navigation,
)
from ui.theme import (
    CORNER_RADIUS,
    DODGEVILLE_ACCENT,
    DODGEVILLE_BLUE,
    UI_BORDER,
    UI_SURFACE,
    UI_SURFACE_LIGHT,
    UI_TEXT_MUTED,
    font,
)
from ui.widgets import SectionHeader"""

    payroll_header = """import customtkinter as ctk
from calendar import monthrange
from datetime import date
from tkinter import filedialog, messagebox
from typing import Optional, Tuple

from config import PAYROLL_ENTRY_TYPES, TIMECARD_ENTRY_TYPES
from logic import (
    calculate_pay_for_entry,
    copy_timecard_from_previous_period,
    create_payroll_entry,
    export_pay_period_history_csv,
    export_pay_stub_pdf,
    export_payroll_csv,
    export_payroll_pdf,
    get_adjacent_pay_period,
    get_department_pay_summary,
    get_officer_by_id,
    get_officer_time_banks,
    get_officers_by_seniority,
    get_pay_period,
    get_pay_period_history,
    get_pay_stub_preview,
    get_payroll_entries,
    get_payroll_period_timesheets,
    import_timecard_to_payroll,
    is_future_pay_period,
    is_pay_period_locked,
    lock_pay_period,
    prefill_timecard_from_schedule,
    project_officer_annual_pay,
    save_timecard_entry,
    unlock_pay_period,
)
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
from ui.widgets import Card, FormField, SectionHeader, StatusBadge"""

    _write_mixin(
        os.path.join(ROOT, "ui", "dashboard_pages.py"),
        "Dashboard tab and refresh helpers.",
        "DashboardPageMixin",
        _body_only(dashboard_chunk)
        + _body_only(_slice_by_marker(notif_lines, "def _apply_dashboard_role_layout", "Officers")),
        dashboard_header,
    )

    _write_mixin(
        os.path.join(ROOT, "ui", "officers_pages.py"),
        "Officer roster CRUD, photos, and CSV import.",
        "OfficersPageMixin",
        _body_only(officers_chunk),
        officers_header,
    )

    _write_mixin(
        os.path.join(ROOT, "ui", "notifications_pages.py"),
        "In-app notification inbox and navigation.",
        "NotificationsPageMixin",
        _body_only(notifications_chunk),
        notifications_header,
    )

    _write_mixin(
        os.path.join(ROOT, "ui", "payroll_pages.py"),
        "Timecard, payroll, and pay-period exports.",
        "PayrollPageMixin",
        "".join(payroll_export_chunk) + _body_only(timecard_payroll_chunk),
        payroll_header,
    )

    mixin_imports = """from ui.dashboard_pages import DashboardPageMixin
from ui.officers_pages import OfficersPageMixin
from ui.notifications_pages import NotificationsPageMixin
from ui.schedule_pages import SchedulePageMixin
from ui.payroll_pages import PayrollPageMixin
from ui.simulator_pages import SimulatorPageMixin
from ui.requests_pages import RequestsPageMixin
"""

    bases = (
        "AdminPageMixin, ReportsPageMixin, AvailabilityPageMixin, RequestsPageMixin, "
        "SchedulePageMixin, PayrollPageMixin, SimulatorPageMixin, NotificationsPageMixin, "
        "OfficersPageMixin, DashboardPageMixin"
    )

    if "from ui.dashboard_pages import DashboardPageMixin" not in app_head:
        app_head = app_head.replace(
            "from ui.admin_pages import AdminPageMixin\n",
            "from ui.admin_pages import AdminPageMixin\n" + mixin_imports,
        )
        # Remove stale single mixin imports
        app_head = re.sub(
            r"from ui\.(officers|notifications|schedule|payroll|simulator)_pages import \w+\n", "", app_head
        )

    app_head = re.sub(
        r"class DodgevilleSchedulerApp\([^)]+\):",
        f"class DodgevilleSchedulerApp({bases}):",
        app_head,
        count=1,
    )

    app_tail = (
        profile_head
        + "".join(profile_tail)
        + _body_only(shell_chunk)
        + "\n\ndef run():\n"
        + "    from config import configure_logging\n"
        + "    configure_logging()\n"
        + "    app = DodgevilleSchedulerApp()\n"
        + "    app.root.mainloop()\n"
    )

    with open(APP, "w", encoding="utf-8") as fh:
        fh.write(app_head + app_tail)

    print("Rebuilt ui/app.py and mixin modules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
