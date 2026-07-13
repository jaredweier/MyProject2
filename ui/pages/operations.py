"""Reports + blackout/availability."""

from __future__ import annotations

from datetime import date

import customtkinter as ctk

from logic import (
    get_coverage_report,
    get_dashboard_insights,
    get_holidays_in_range,
)
from ui.pages.base import BasePage
from ui.theme import CARD_PAD, CONTENT_PAD, UI_BORDER, UI_SURFACE, UI_TEXT_MUTED, font
from ui.widgets import Card, EmptyState, SectionHeader, ToolbarButton


class ReportsPage(BasePage):
    page_key = "reports"

    def build(self) -> None:
        if not self.can("reports.view"):
            EmptyState(self, "No access", "Ops reports require supervisor permission.").grid(
                row=0, column=0, sticky="nsew", padx=24, pady=24
            )
            return
        scroll = self.scroll_body()
        card = Card(scroll, accent=True)
        card.pack(fill="x", pady=(0, CONTENT_PAD))
        hdr = ctk.CTkFrame(card.body, fg_color="transparent")
        hdr.pack(fill="x", padx=CARD_PAD, pady=CARD_PAD)
        SectionHeader(hdr, "Ops reports", "Coverage and labor signals").pack(side="left")
        ToolbarButton(hdr, text="Refresh", command=self.refresh).pack(side="right")
        self._metrics = ctk.CTkFrame(card.body, fg_color="transparent")
        self._metrics.pack(fill="x", padx=CARD_PAD, pady=(0, CARD_PAD))
        self._body = ctk.CTkFrame(scroll, fg_color="transparent")
        self._body.pack(fill="both", expand=True)

    def refresh(self) -> None:
        if not self.can("reports.view"):
            return
        for w in self._metrics.winfo_children():
            w.destroy()
        for w in self._body.winfo_children():
            w.destroy()
        insights = get_dashboard_insights() or {}
        if not isinstance(insights, dict):
            insights = {}
        for label, key in (
            ("Pending requests", "pending_requests"),
            ("Pending swaps", "pending_swaps"),
            ("Coverage gaps", "coverage_gap_count"),
            ("Night issues", "coverage_issues"),
        ):
            chip = ctk.CTkFrame(
                self._metrics, fg_color=UI_SURFACE, corner_radius=8, border_width=1, border_color=UI_BORDER
            )
            chip.pack(side="left", padx=(0, 8), pady=4)
            ctk.CTkLabel(chip, text=str(insights.get(key, 0)), font=font("stat_value")).pack(padx=16, pady=(8, 0))
            ctk.CTkLabel(chip, text=label, font=font("small"), text_color=UI_TEXT_MUTED).pack(padx=16, pady=(0, 8))
        today = date.today()
        report = get_coverage_report(today, today)
        text = report.get("message") if isinstance(report, dict) else str(report)
        if isinstance(report, dict) and report.get("summary"):
            text = str(report["summary"])
        body_card = Card(self._body)
        body_card.pack(fill="x", pady=8)
        SectionHeader(body_card.body, "Coverage snapshot", "Today").pack(fill="x", padx=CARD_PAD, pady=(CARD_PAD, 8))
        ctk.CTkLabel(
            body_card.body,
            text=text or "Coverage data loaded.",
            font=font("body"),
            text_color=UI_TEXT_MUTED,
            wraplength=720,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=CARD_PAD, pady=(0, CARD_PAD))


class AvailabilityPage(BasePage):
    page_key = "availability"

    def build(self) -> None:
        scroll = self.scroll_body()
        card = Card(scroll, accent=True)
        card.pack(fill="both", expand=True)
        SectionHeader(card.body, "Blackout dates & holidays", "Department calendar").pack(
            fill="x", padx=CARD_PAD, pady=CARD_PAD
        )
        self._list = ctk.CTkScrollableFrame(card.body, fg_color="transparent", height=400)
        self._list.pack(fill="both", expand=True, padx=8, pady=(0, CARD_PAD))

    def refresh(self) -> None:
        for w in self._list.winfo_children():
            w.destroy()
        today = date.today()
        end = today.replace(year=today.year + 1) if today.month < 12 else today
        try:
            holidays = get_holidays_in_range(today, end)
        except Exception:
            holidays = []
        if isinstance(holidays, dict):
            holidays = holidays.get("holidays") or holidays.get("rows") or []
        if not holidays:
            EmptyState(
                self._list,
                "No holidays in range",
                "Department holidays and blackout dates appear here when configured.",
            ).pack(fill="x", pady=16)
            return
        for h in holidays[:40]:
            if isinstance(h, dict):
                text = f"{h.get('name') or h.get('holiday_name') or 'Holiday'} · {h.get('date') or h.get('holiday_date') or ''}"
            else:
                text = str(h)
            row = ctk.CTkFrame(self._list, fg_color=UI_SURFACE, corner_radius=8, border_width=1, border_color=UI_BORDER)
            row.pack(fill="x", pady=3, padx=4)
            ctk.CTkLabel(row, text=text, font=font("body"), text_color=UI_TEXT_MUTED, anchor="w").pack(
                fill="x", padx=12, pady=10
            )
