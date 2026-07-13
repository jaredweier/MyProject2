"""Design tokens + navigation registry — enterprise LE command center (2026)."""

from __future__ import annotations

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
    UI_BORDER_GLOW,
    UI_NAV_ACTIVE,
    UI_SIDEBAR,
    UI_SURFACE,
    UI_SURFACE_ELEVATED,
    UI_SURFACE_LIGHT,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
)

# ---------------------------------------------------------------------------
# Spacing scale (8pt grid — Linear / Mark43 density)
# ---------------------------------------------------------------------------
SPACE_1 = 4
SPACE_2 = 8
SPACE_3 = 12
SPACE_4 = 16
SPACE_5 = 20
SPACE_6 = 24
SPACE_8 = 32

CORNER_RADIUS = 10
BTN_RADIUS = 8
CARD_PAD = SPACE_4
CONTENT_PAD = SPACE_5
SIDEBAR_WIDTH = 240
TOPBAR_HEIGHT = 56
SUBNAV_HEIGHT = 44
BTN_HEIGHT_PRIMARY = 36
BTN_HEIGHT_TOOLBAR = 30
BTN_HEIGHT_COMPACT = 28
ACCENT_STRIPE_HEIGHT = 2

FONT_FAMILY = "Segoe UI"
FONT_SPECS = {
    "display": {"size": 26, "weight": "bold", "family": FONT_FAMILY},
    "title": {"size": 20, "weight": "bold", "family": FONT_FAMILY},
    "heading": {"size": 16, "weight": "bold", "family": FONT_FAMILY},
    "subheading": {"size": 13, "weight": "bold", "family": FONT_FAMILY},
    "body": {"size": 13, "family": FONT_FAMILY},
    "small": {"size": 11, "family": FONT_FAMILY},
    "micro": {"size": 9, "weight": "bold", "family": FONT_FAMILY},
    "stat_value": {"size": 28, "weight": "bold", "family": FONT_FAMILY},
    "stat_label": {"size": 10, "family": FONT_FAMILY},
    "nav": {"size": 13, "family": FONT_FAMILY},
    "nav_section": {"size": 9, "weight": "bold", "family": FONT_FAMILY},
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

# Page keys must remain stable for smoke/tests
NAV_ITEMS = [
    ("dashboard", "Dashboard", ""),
    ("base_schedule", "Original monthly", ""),
    ("live_schedule", "Live schedule", ""),
    ("timecard", "Timecard", ""),
    ("banked_time", "Banked time", ""),
    ("timeline", "Timeline", ""),
    ("requests", "Time off", ""),
    ("swaps", "Shift exchange", ""),
    ("notifications", "Alerts", ""),
    ("officers", "Patrol roster", ""),
    ("payroll", "Payroll ledger", ""),
    ("simulator", "Simulator", ""),
    ("reports", "Ops reports", ""),
    ("availability", "Blackout dates", ""),
    ("users", "Access control", ""),
]

NAV_PERMISSIONS = {
    "officers": "officers.manage",
    "simulator": "simulator.use",
    "reports": "reports.view",
    "users": ("users.manage", "users.edit_role"),
}

NAV_HUBS: dict[str, dict] = {
    "schedules": {
        "label": "Schedules",
        "default": "base_schedule",
        "pages": ("base_schedule", "live_schedule", "timeline"),
        "tabs": (
            ("base_schedule", "Original monthly"),
            ("live_schedule", "Live schedule"),
            ("timeline", "Timeline"),
        ),
    },
    "leave": {
        "label": "Leave & swaps",
        "default": "requests",
        "pages": ("requests", "swaps"),
        "tabs": (
            ("requests", "Time off"),
            ("swaps", "Shift exchange"),
        ),
    },
    "payroll_hub": {
        "label": "Payroll",
        "default": "timecard",
        "pages": ("timecard", "banked_time", "payroll"),
        "tabs": (
            ("timecard", "Timecard"),
            ("banked_time", "Banked time"),
            ("payroll", "Ledger"),
        ),
    },
    "operations": {
        "label": "Operations",
        "default": "reports",
        "pages": ("reports", "availability"),
        "tabs": (
            ("reports", "Reports"),
            ("availability", "Blackout dates"),
        ),
    },
}

SIDEBAR_NAV = [
    ("section", "Overview"),
    ("dashboard", "Dashboard", ""),
    ("section", "Scheduling"),
    ("schedules", "Schedules", ""),
    ("simulator", "Simulator", ""),
    ("leave", "Leave & swaps", ""),
    ("section", "People"),
    ("officers", "Roster", ""),
    ("section", "Finance"),
    ("payroll_hub", "Payroll", ""),
    ("section", "Administration"),
    ("operations", "Operations", ""),
    ("users", "Access control", ""),
]

PAGE_SUBTITLES = {
    "dashboard": "Today's watch, alerts, and next actions",
    "base_schedule": "Rotation plan fixed after generation",
    "live_schedule": "Live coverage with time off, bumps, and swaps",
    "timecard": "Biweekly pay-period time entry",
    "banked_time": "Comp, sick, and holiday banks",
    "timeline": "14-day duty timeline by officer",
    "requests": "Submit and review time off with coverage plans",
    "swaps": "Exchange shifts on the same duty day",
    "notifications": "Alerts for coverage and requests",
    "officers": "Roster, ranks, and assignments",
    "payroll": "Pay period ledger and stubs",
    "simulator": "Model staffing before you publish",
    "reports": "Coverage, overtime, and exports",
    "availability": "Blackout dates and holidays",
    "users": "Logins, roles, and passwords",
}

OFFICER_PAGE_SUBTITLES = {
    "dashboard": "Your rotation, requests, and alerts",
    "base_schedule": "Your scheduled days on the monthly plan",
    "live_schedule": "Your live schedule with changes",
    "timeline": "Your 14-day shift timeline",
    "requests": "Submit and track time off",
    "swaps": "Request shift exchanges",
    "notifications": "Your alerts",
    "timecard": "Your biweekly time entries",
    "banked_time": "Your bank balances",
    "payroll": "Your pay period totals",
    "availability": "Your blackout dates",
}

UI_TEXT_LIGHT = UI_TEXT_PRIMARY
UI_TEXT_ACCENT = UI_ACCENT_GLOW
UI_NAV_TEXT = UI_TEXT_PRIMARY
UI_PHOTO_BG = "#0A0D12"
BRAND_PHOTO_BORDER = UI_BORDER
TACTICAL_STRIPE_GOLD_HEIGHT = 0


def tactical_stripe(parent, *, side="top", pack_kwargs=None, color=None) -> None:
    pack_kwargs = pack_kwargs or {}
    pack_kwargs.setdefault("fill", "x")
    ctk.CTkFrame(
        parent,
        fg_color=color or UI_BORDER_GLOW,
        height=ACCENT_STRIPE_HEIGHT,
        corner_radius=0,
    ).pack(side=side, **pack_kwargs)


def micro_label(parent, text: str, *, color=None, **pack):
    lbl = ctk.CTkLabel(
        parent,
        text=(text or "").upper(),
        font=font("micro"),
        text_color=color or UI_ACCENT_GLOW,
        anchor="w",
    )
    if pack:
        lbl.pack(**pack)
    return lbl


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
    "UI_BORDER_GLOW",
    "UI_NAV_ACTIVE",
    "UI_SIDEBAR",
    "UI_SURFACE",
    "UI_SURFACE_ELEVATED",
    "UI_SURFACE_LIGHT",
    "UI_TEXT_MUTED",
    "UI_TEXT_PRIMARY",
    "SIDEBAR_WIDTH",
    "font",
    "NAV_ITEMS",
    "NAV_HUBS",
    "NAV_PERMISSIONS",
    "SIDEBAR_NAV",
    "PAGE_SUBTITLES",
    "OFFICER_PAGE_SUBTITLES",
    "STATUS_COLORS",
    "hub_for_page",
    "page_title",
    "resolve_nav_target",
]
