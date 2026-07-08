"""UI theme — modern law-enforcement design system (tokens, fonts, navigation)."""

import customtkinter as ctk

from config import (
    DODGEVILLE_ACCENT,
    DODGEVILLE_BLUE,
    DODGEVILLE_DANGER,
    DODGEVILLE_GOLD,
    DODGEVILLE_RED,
    DODGEVILLE_SUCCESS,
    DODGEVILLE_WARNING,
    SCHEDULE_TYPE_COURT,
    SCHEDULE_TYPE_LEAVE,
    SCHEDULE_TYPE_TRAINING,
    UI_ACCENT_GLOW,
    UI_ACCENT_SUBTLE,
    UI_BG,
    UI_BORDER,
    UI_NAV_ACTIVE,
    UI_SIDEBAR,
    UI_SURFACE,
    UI_SURFACE_LIGHT,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
)

__all__ = [
    "FONT_FAMILY",
    "DODGEVILLE_ACCENT",
    "DODGEVILLE_BLUE",
    "DODGEVILLE_DANGER",
    "DODGEVILLE_GOLD",
    "DODGEVILLE_RED",
    "DODGEVILLE_SUCCESS",
    "DODGEVILLE_WARNING",
    "UI_ACCENT_GLOW",
    "UI_ACCENT_SUBTLE",
    "UI_BG",
    "UI_BORDER",
    "UI_NAV_ACTIVE",
    "SIDEBAR_WIDTH",
    "UI_SIDEBAR",
    "UI_SURFACE",
    "UI_SURFACE_LIGHT",
    "UI_TEXT_MUTED",
    "UI_TEXT_PRIMARY",
]

# Typography — Segoe UI on Windows; clean hierarchy (no shouty all-caps chrome)
FONT_FAMILY = "Segoe UI"

FONT_SPECS = {
    "display": {"size": 28, "weight": "bold", "family": FONT_FAMILY},
    "title": {"size": 22, "weight": "bold", "family": FONT_FAMILY},
    "heading": {"size": 18, "weight": "bold", "family": FONT_FAMILY},
    "subheading": {"size": 15, "weight": "bold", "family": FONT_FAMILY},
    "body": {"size": 14, "family": FONT_FAMILY},
    "small": {"size": 12, "family": FONT_FAMILY},
    "stat_value": {"size": 26, "weight": "bold", "family": FONT_FAMILY},
    "stat_label": {"size": 11, "family": FONT_FAMILY},
    "nav": {"size": 13, "weight": "normal", "family": FONT_FAMILY},
    "nav_section": {"size": 10, "weight": "bold", "family": FONT_FAMILY},
    "mono": {"size": 11, "family": "Consolas"},
}

_font_cache: dict = {}


def font(key: str) -> ctk.CTkFont:
    if key not in _font_cache:
        _font_cache[key] = ctk.CTkFont(**FONT_SPECS[key])
    return _font_cache[key]


def clear_font_cache() -> None:
    _font_cache.clear()


STATUS_COLORS = {
    "Pending": DODGEVILLE_WARNING,
    "Pending Manual Review": DODGEVILLE_WARNING,
    "Approved": DODGEVILLE_SUCCESS,
    "Rejected": DODGEVILLE_DANGER,
    "Active": DODGEVILLE_SUCCESS,
    "Inactive": "#64748B",
    "Auto OK": DODGEVILLE_SUCCESS,
    "Needs Review": DODGEVILLE_WARNING,
    "Open": DODGEVILLE_WARNING,
    "Filled": UI_TEXT_MUTED,
    "Working": DODGEVILLE_SUCCESS,
    "Off": "#64748B",
    "Bumped": DODGEVILLE_WARNING,
    "Covering": DODGEVILLE_GOLD,
    "Swapped": DODGEVILLE_ACCENT,
    "Training": SCHEDULE_TYPE_TRAINING,
    "Court": SCHEDULE_TYPE_COURT,
    "Leave": SCHEDULE_TYPE_LEAVE,
}

SCHEDULE_STATUS_LABELS = {
    "working": "Working",
    "off": "Off",
    "bumped": "Bumped",
    "covering": "Covering",
    "swapped": "Swapped",
    "training": "Training",
    "court": "Court",
    "leave": "Leave",
}

NAV_PERMISSIONS = {
    "officers": "officers.manage",
    "simulator": "simulator.use",
    "reports": "reports.view",
    "users": ("users.manage", "users.edit_role"),
}

# Page registry (labels without emoji — icons handled in NavButton)
NAV_ITEMS = [
    ("dashboard", "Dashboard", ""),
    ("base_schedule", "Original Monthly Schedule", ""),
    ("live_schedule", "Live Schedule", ""),
    ("timecard", "Timecard", ""),
    ("banked_time", "Banked Time", ""),
    ("timeline", "Duty Timeline", ""),
    ("requests", "Time Off", ""),
    ("swaps", "Shift Exchange", ""),
    ("notifications", "Alerts", ""),
    ("officers", "Patrol Roster", ""),
    ("payroll", "Payroll Ledger", ""),
    ("simulator", "Schedule Simulator", ""),
    ("reports", "Ops Reports", ""),
    ("availability", "Blackout Dates", ""),
    ("users", "Access Control", ""),
]

NAV_HUBS: dict[str, dict] = {
    "schedules": {
        "label": "Schedules",
        "icon": "",
        "default": "base_schedule",
        "pages": ("base_schedule", "live_schedule", "timeline"),
        "tabs": (
            ("base_schedule", "Original Monthly"),
            ("live_schedule", "Live Schedule"),
            ("timeline", "Timeline"),
        ),
    },
    "leave": {
        "label": "Leave & Swaps",
        "icon": "",
        "default": "requests",
        "pages": ("requests", "swaps"),
        "tabs": (
            ("requests", "Time Off"),
            ("swaps", "Shift Exchange"),
        ),
    },
    "payroll_hub": {
        "label": "Payroll",
        "icon": "",
        "default": "timecard",
        "pages": ("timecard", "banked_time", "payroll"),
        "tabs": (
            ("timecard", "Timecard"),
            ("banked_time", "Banked Time"),
            ("payroll", "Ledger"),
        ),
    },
    "operations": {
        "label": "Operations",
        "icon": "",
        "default": "reports",
        "pages": ("reports", "availability"),
        "tabs": (
            ("reports", "Reports"),
            ("availability", "Blackout Dates"),
        ),
    },
}

SIDEBAR_NAV = [
    ("section", "Overview"),
    ("dashboard", "Dashboard", ""),
    ("section", "Scheduling"),
    ("schedules", "Schedules", ""),
    ("simulator", "Simulator", ""),
    ("leave", "Leave & Swaps", ""),
    ("section", "People"),
    ("officers", "Roster", ""),
    ("section", "Finance"),
    ("payroll_hub", "Payroll", ""),
    ("section", "Administration"),
    ("operations", "Operations", ""),
    ("users", "Access Control", ""),
]

PAGE_SUBTITLES = {
    "dashboard": "Today's watch, alerts, and pending actions",
    "base_schedule": "Rotation plan from squad and shift assignments",
    "live_schedule": "Live schedule with time off, bumps, swaps, and coverage",
    "timecard": "Biweekly pay period time entry",
    "banked_time": "Comp, sick, and holiday banks with FLSA tracking",
    "timeline": "14-day duty timeline by officer and squad",
    "requests": "Submit time off, preview coverage, and review history",
    "swaps": "Exchange shifts between officers on the same duty day",
    "notifications": "Alerts for requests, swaps, and coverage events",
    "officers": "Photos, ranks, pay rates, and time banks",
    "payroll": "Biweekly pay period timesheets and ledger",
    "simulator": "Model rotations and staffing before publishing",
    "reports": "Coverage, overtime, labor cost, and exports",
    "availability": "Officer blackout dates and department holidays",
    "users": "Logins, roles, and password management",
}

OFFICER_PAGE_SUBTITLES = {
    "dashboard": "Your rotation, requests, and alerts at a glance",
    "base_schedule": "Original monthly plan — your scheduled days are highlighted",
    "live_schedule": "Your live schedule with time off, bumps, and swaps",
    "timeline": "Your 14-day shift timeline",
    "requests": "Submit and track your time off requests",
    "swaps": "Request and manage shift exchanges",
    "notifications": "Alerts for your requests and coverage",
    "timecard": "Your biweekly pay period time entries",
    "banked_time": "Your comp, sick, and holiday bank balances",
    "payroll": "Your biweekly pay period totals",
    "availability": "Mark blackout dates and view holidays",
}

UI_TEXT_LIGHT = UI_TEXT_PRIMARY
UI_TEXT_ACCENT = UI_ACCENT_GLOW
UI_NAV_TEXT = UI_TEXT_PRIMARY
UI_PHOTO_BG = "#0A0D12"
BRAND_PHOTO_BORDER = UI_BORDER

CORNER_RADIUS = 10
CARD_PAD = 18
CONTENT_PAD = 24
SUBNAV_HEIGHT = 40
TOPBAR_HEIGHT = 56
BTN_HEIGHT_PRIMARY = 38
BTN_HEIGHT_TOOLBAR = 32
BTN_HEIGHT_COMPACT = 28
BTN_RADIUS = 6
SIDEBAR_WIDTH = 220
ACCENT_STRIPE_HEIGHT = 1
TACTICAL_STRIPE_GOLD_HEIGHT = 0


def tactical_stripe(parent, *, side="top", pack_kwargs=None) -> None:
    """Subtle separator — replaces legacy dual cyan/gold bars across the app."""
    pack_kwargs = pack_kwargs or {}
    pack_kwargs.setdefault("fill", "x")
    ctk.CTkFrame(parent, fg_color=UI_BORDER, height=1, corner_radius=0).pack(
        side=side,
        **pack_kwargs,
    )


def hub_for_page(page_key: str) -> str | None:
    for hub_key, hub in NAV_HUBS.items():
        if page_key in hub["pages"]:
            return hub_key
    return None


def page_title(page_key: str) -> str:
    hub = hub_for_page(page_key)
    if hub:
        return NAV_HUBS[hub]["label"]
    for key, label, _ in NAV_ITEMS:
        if key == page_key:
            return label
    return page_key.replace("_", " ").title()


def resolve_nav_target(key: str) -> str:
    if key in NAV_HUBS:
        return NAV_HUBS[key]["default"]
    return key
