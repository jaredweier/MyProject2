"""Ops-floor dashboard — role-aware, severity-first, outcome actions."""

from __future__ import annotations

from datetime import date

import customtkinter as ctk

from logic import (
    get_cycle_day,
    get_dashboard_insights,
    get_shift_coverage_counts_for_range,
    get_squad_on_duty,
    get_unread_notification_count,
)
from logic.staffing_config import get_active_shift_times
from ui.branding import get_department_branding
from ui.helpers import active_officers
from ui.pages.base import BasePage
from ui.theme import (
    CARD_PAD,
    CONTENT_PAD,
    DODGEVILLE_ACCENT,
    DODGEVILLE_WARNING,
    UI_ACCENT_GLOW,
    UI_BORDER,
    UI_BORDER_GLOW,
    UI_SURFACE,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    font,
    micro_label,
)
from ui.widgets import ActionTile, AlertBanner, Card, SectionHeader, StatCard
from validators import format_date


class DashboardPage(BasePage):
    page_key = "dashboard"

    def build(self) -> None:
        scroll = self.scroll_body()
        branding = get_department_branding()

        hero = Card(scroll, accent=True)
        hero.pack(fill="x", pady=(0, CONTENT_PAD))
        hb = ctk.CTkFrame(hero.body, fg_color="transparent")
        hb.pack(fill="x", padx=CARD_PAD, pady=CARD_PAD)
        hb.grid_columnconfigure(0, weight=1)
        left = ctk.CTkFrame(hb, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")
        micro_label(left, "Ops floor").pack(anchor="w")
        self._greeting = ctk.CTkLabel(
            left, text="Good day", font=font("display"), text_color=UI_TEXT_PRIMARY, anchor="w"
        )
        self._greeting.pack(fill="x", pady=(4, 0))
        self._dept = ctk.CTkLabel(left, text=branding["name"], font=font("body"), text_color=UI_TEXT_MUTED, anchor="w")
        self._dept.pack(fill="x")
        self._tagline = ctk.CTkLabel(
            left, text=branding["tagline"], font=font("small"), text_color=UI_TEXT_MUTED, anchor="w"
        )
        self._tagline.pack(fill="x", pady=(2, 0))
        right = ctk.CTkFrame(hb, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e", padx=(16, 0))
        pill = ctk.CTkFrame(right, fg_color=UI_SURFACE, corner_radius=10, border_width=1, border_color=UI_BORDER_GLOW)
        pill.pack(anchor="e")
        pin = ctk.CTkFrame(pill, fg_color="transparent")
        pin.pack(padx=12, pady=10)
        self._date_lbl = ctk.CTkLabel(pin, text="", font=font("subheading"), text_color=UI_TEXT_PRIMARY)
        self._date_lbl.pack(anchor="e")
        self._cycle_lbl = ctk.CTkLabel(pin, text="", font=font("mono"), text_color=UI_ACCENT_GLOW)
        self._cycle_lbl.pack(anchor="e", pady=(4, 0))

        self._on_duty = Card(scroll)
        self._on_duty.pack(fill="x", pady=(0, CONTENT_PAD))
        SectionHeader(self._on_duty.body, "On duty now", "Live headcount by shift band").pack(
            fill="x", padx=CARD_PAD, pady=(CARD_PAD, 4)
        )
        self._on_duty_body = ctk.CTkFrame(self._on_duty.body, fg_color="transparent")
        self._on_duty_body.pack(fill="x", padx=CARD_PAD, pady=(0, CARD_PAD))

        self._alerts = ctk.CTkFrame(scroll, fg_color="transparent")
        self._alerts.pack(fill="x", pady=(0, CONTENT_PAD))

        stats = ctk.CTkFrame(scroll, fg_color="transparent")
        stats.pack(fill="x", pady=(0, CONTENT_PAD))
        for c in range(3):
            stats.grid_columnconfigure(c, weight=1)
        self.stat_cards = {}
        self.app.stat_cards = self.stat_cards
        specs = [
            ("officers", "Active officers", "…", DODGEVILLE_ACCENT, "officers"),
            ("pending", "Pending requests", "0", DODGEVILLE_WARNING, "requests"),
            ("pending_swaps", "Pending swaps", "0", DODGEVILLE_ACCENT, "swaps"),
        ]
        for i, (key, label, val, accent, page) in enumerate(specs):
            card = StatCard(stats, label, val, accent=accent, clickable=True, badge_style=True)
            card.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 6, 0 if i == 2 else 6))
            card.bind("<Button-1>", lambda _e, p=page: self.app.show_page(p))
            self.stat_cards[key] = card

        actions = Card(scroll, accent=True)
        actions.pack(fill="x", pady=(0, CONTENT_PAD))
        SectionHeader(actions.body, "Next actions", "Outcome-first shortcuts").pack(
            fill="x", padx=CARD_PAD, pady=(CARD_PAD, 8)
        )
        self._actions = ctk.CTkFrame(actions.body, fg_color="transparent")
        self._actions.pack(fill="x", padx=CARD_PAD, pady=(0, CARD_PAD))
        self._actions.grid_columnconfigure((0, 1), weight=1)

        inbox = Card(scroll)
        inbox.pack(fill="both", expand=True)
        SectionHeader(inbox.body, "Watch notes", "Unread alerts and coverage signals").pack(
            fill="x", padx=CARD_PAD, pady=(CARD_PAD, 8)
        )
        self._inbox = ctk.CTkFrame(inbox.body, fg_color="transparent")
        self._inbox.pack(fill="x", padx=CARD_PAD, pady=(0, CARD_PAD))

    def refresh(self) -> None:
        today = date.today()
        hour = __import__("datetime").datetime.now().hour
        greet = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
        user = self.app.current_user or {}
        name = user.get("officer_name") or user.get("username") or ""
        self._greeting.configure(text=f"{greet}{', ' + name.split()[0] if name else ''}")
        cycle = get_cycle_day(today)
        squad = get_squad_on_duty(cycle)
        self._date_lbl.configure(text=format_date(today))
        self._cycle_lbl.configure(text=f"Cycle day {cycle} · Squad {squad}")

        for w in self._on_duty_body.winfo_children():
            w.destroy()
        if not self.is_officer():
            day_str = today.isoformat()
            coverage = get_shift_coverage_counts_for_range(today, today)
            row = ctk.CTkFrame(self._on_duty_body, fg_color="transparent")
            row.pack(fill="x")
            ctk.CTkLabel(row, text=f"Squad {squad}", font=font("subheading"), text_color=UI_TEXT_PRIMARY).pack(
                side="left", padx=(0, 12)
            )
            for start, end in get_active_shift_times().values():
                count = coverage.get((day_str, squad, start), 0)
                chip = ctk.CTkFrame(row, fg_color=UI_SURFACE, corner_radius=8, border_width=1, border_color=UI_BORDER)
                chip.pack(side="left", padx=(0, 8))
                ctk.CTkLabel(chip, text=f"{start}–{end}", font=font("small"), text_color=UI_TEXT_MUTED).pack(
                    side="left", padx=(10, 6), pady=6
                )
                ctk.CTkLabel(
                    chip,
                    text=str(count),
                    font=font("subheading"),
                    text_color=DODGEVILLE_ACCENT if count else DODGEVILLE_WARNING,
                ).pack(side="left", padx=(0, 10), pady=6)
        else:
            ctk.CTkLabel(
                self._on_duty_body,
                text="See Timeline for your personal duty window.",
                font=font("body"),
                text_color=UI_TEXT_MUTED,
            ).pack(anchor="w")

        officer_id = self.app._linked_officer_id() if self.is_officer() else None
        insights = get_dashboard_insights(officer_id=officer_id) if callable(get_dashboard_insights) else {}
        if not isinstance(insights, dict):
            insights = {}
        self.stat_cards["officers"].set_value(str(len(active_officers())))
        self.stat_cards["pending"].set_value(str(insights.get("pending_requests", 0)))
        self.stat_cards["pending_swaps"].set_value(str(insights.get("pending_swaps", 0)))

        for w in self._alerts.winfo_children():
            w.destroy()
        alerts = []
        if insights.get("coverage_gap_count", 0):
            alerts.append((f"Coverage gaps in next 48h: {insights.get('coverage_gap_count')}", "warning"))
        if insights.get("coverage_issues", 0):
            alerts.append((f"Night minimum issues this cycle: {insights['coverage_issues']}", "critical"))
        if not alerts:
            AlertBanner(self._alerts, "All clear for this watch.", severity="success").pack(fill="x")
        else:
            for msg, sev in alerts[:4]:
                AlertBanner(self._alerts, msg, severity=sev).pack(fill="x", pady=(0, 6))

        for w in self._actions.winfo_children():
            w.destroy()
        if self.is_officer():
            tiles = [
                ("My schedule", "14-day timeline", lambda: self.app.show_page("timeline")),
                ("Request time off", "Submit leave", lambda: self.app.show_page("requests")),
                ("Live schedule", "Coverage changes", lambda: self.app.show_page("live_schedule")),
                ("Timecard", "Pay period hours", lambda: self.app.show_page("timecard")),
            ]
        else:
            tiles = [
                ("Review time off", "Approve with coverage plans", lambda: self.app.show_page("requests")),
                ("Duty timeline", "Who works which day", lambda: self.app.show_page("timeline")),
                ("Live schedule", "Ops floor after changes", lambda: self.app.show_page("live_schedule")),
                ("Roster", "People & assignments", lambda: self.app.show_page("officers")),
            ]
            if self.can("simulator.use"):
                tiles.append(("Simulator", "Find best staffing", lambda: self.app.show_page("simulator")))
            if self.can("reports.view"):
                tiles.append(("Ops reports", "Coverage & OT", lambda: self.app.show_page("reports")))
        for i, (t, s, cmd) in enumerate(tiles):
            ActionTile(self._actions, t, s, command=cmd).grid(row=i // 2, column=i % 2, sticky="nsew", padx=4, pady=4)

        for w in self._inbox.winfo_children():
            w.destroy()
        count = get_unread_notification_count(officer_id=officer_id)
        ctk.CTkLabel(
            self._inbox,
            text=f"{count} unread alert(s)" if count else "No unread alerts",
            font=font("body"),
            text_color=UI_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x")
