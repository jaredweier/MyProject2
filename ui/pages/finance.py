"""Timecard, banked time, payroll — essential finance surfaces."""

from __future__ import annotations

import customtkinter as ctk

from logic import (
    get_officer_time_banks,
    get_officers_by_seniority,
    get_pay_period,
    get_payroll_period_timesheets,
    get_timecard_period,
)
from ui.pages.base import BasePage
from ui.theme import CARD_PAD, UI_BORDER, UI_SURFACE, UI_TEXT_MUTED, UI_TEXT_PRIMARY, font
from ui.widgets import Card, EmptyState, FormField, SectionHeader, ToolbarButton
from validators import format_date


class TimecardPage(BasePage):
    page_key = "timecard"

    def build(self) -> None:
        scroll = self.scroll_body()
        card = Card(scroll, accent=True)
        card.pack(fill="both", expand=True)
        SectionHeader(card.body, "Timecard", "Biweekly pay-period hours").pack(
            fill="x", padx=CARD_PAD, pady=(CARD_PAD, 8)
        )
        tools = ctk.CTkFrame(card.body, fg_color="transparent")
        tools.pack(fill="x", padx=CARD_PAD, pady=(0, 8))
        self._period_lbl = ctk.CTkLabel(tools, text="", font=font("subheading"), text_color=UI_TEXT_PRIMARY)
        self._period_lbl.pack(side="left")
        ToolbarButton(tools, text="Refresh", command=self.refresh).pack(side="right")
        if not self.is_officer() and self.can("timecard.view_all"):
            self._officer = FormField(
                card.body,
                "Officer",
                lambda p: ctk.CTkComboBox(p, height=34, values=["Loading..."]),
                pack_opts={"padx": CARD_PAD, "pady": (0, 8)},
            ).widget
        else:
            self._officer = None
        self._list = ctk.CTkScrollableFrame(card.body, fg_color="transparent", height=360)
        self._list.pack(fill="both", expand=True, padx=8, pady=(0, CARD_PAD))
        self._officer_map = {}

    def refresh(self) -> None:
        start, end = get_pay_period()
        self._period_lbl.configure(text=f"{format_date(start)} – {format_date(end)}")
        oid = self.app._linked_officer_id()
        if self._officer is not None:
            officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
            labels = [o["name"] for o in officers]
            self._officer_map = {o["name"]: o["id"] for o in officers}
            self._officer.configure(values=labels or ["—"])
            if labels:
                if not self._officer.get() or self._officer.get() not in self._officer_map:
                    self._officer.set(labels[0])
                oid = self._officer_map.get(self._officer.get())
        for w in self._list.winfo_children():
            w.destroy()
        if not oid:
            EmptyState(self._list, "No officer linked", "Link your login to a roster profile.").pack(fill="x", pady=16)
            return
        data = get_timecard_period(oid, start)
        entries = data.get("entries") or data.get("days") or []
        if not entries and isinstance(data, dict) and data.get("success") is False:
            EmptyState(self._list, "Unable to load timecard", data.get("message", "")).pack(fill="x", pady=16)
            return
        if not entries:
            EmptyState(
                self._list,
                "No entries this period",
                "Hours appear as you save timecard rows or prefill from schedule.",
            ).pack(fill="x", pady=16)
            return
        for entry in entries[:40]:
            if isinstance(entry, dict):
                label = entry.get("work_date") or entry.get("date") or ""
                hours = entry.get("hours") or entry.get("total_hours") or entry.get("regular_hours") or "—"
                etype = entry.get("entry_type") or entry.get("type") or ""
                text = f"{label}  ·  {hours}h  ·  {etype}"
            else:
                text = str(entry)
            row = ctk.CTkFrame(self._list, fg_color=UI_SURFACE, corner_radius=8, border_width=1, border_color=UI_BORDER)
            row.pack(fill="x", pady=3, padx=4)
            ctk.CTkLabel(row, text=text, font=font("body"), text_color=UI_TEXT_MUTED, anchor="w").pack(
                fill="x", padx=12, pady=10
            )


class BankedTimePage(BasePage):
    page_key = "banked_time"

    def build(self) -> None:
        scroll = self.scroll_body()
        card = Card(scroll, accent=True)
        card.pack(fill="both", expand=True)
        SectionHeader(card.body, "Banked time", "Comp, sick, and holiday balances").pack(
            fill="x", padx=CARD_PAD, pady=CARD_PAD
        )
        self._body = ctk.CTkFrame(card.body, fg_color="transparent")
        self._body.pack(fill="x", padx=CARD_PAD, pady=(0, CARD_PAD))

    def refresh(self) -> None:
        for w in self._body.winfo_children():
            w.destroy()
        oid = self.app._linked_officer_id()
        if not oid and not self.is_officer():
            officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
            oid = officers[0]["id"] if officers else None
        if not oid:
            EmptyState(self._body, "No officer", "Link a profile to view banks.").pack(fill="x")
            return
        banks = get_officer_time_banks(oid)
        if not banks or (isinstance(banks, dict) and banks.get("success") is False):
            EmptyState(
                self._body,
                "No bank data",
                getattr(banks, "get", lambda *_: "")("message") if isinstance(banks, dict) else "",
            ).pack(fill="x")
            return
        data = banks if isinstance(banks, dict) else {}
        for key in ("comp", "sick", "holiday", "comp_balance", "sick_balance", "holiday_balance"):
            if key in data:
                row = ctk.CTkFrame(
                    self._body, fg_color=UI_SURFACE, corner_radius=8, border_width=1, border_color=UI_BORDER
                )
                row.pack(fill="x", pady=4)
                ctk.CTkLabel(
                    row,
                    text=f"{key.replace('_', ' ').title()}: {data[key]}",
                    font=font("body"),
                    anchor="w",
                ).pack(fill="x", padx=12, pady=12)
        if not self._body.winfo_children():
            # Show raw keys
            for k, v in list(data.items())[:12]:
                if k in ("success", "message"):
                    continue
                ctk.CTkLabel(
                    self._body, text=f"{k}: {v}", font=font("body"), text_color=UI_TEXT_MUTED, anchor="w"
                ).pack(fill="x", pady=2)


class PayrollPage(BasePage):
    page_key = "payroll"

    def build(self) -> None:
        scroll = self.scroll_body()
        card = Card(scroll, accent=True)
        card.pack(fill="both", expand=True)
        SectionHeader(card.body, "Payroll ledger", "Pay period timesheet summary").pack(
            fill="x", padx=CARD_PAD, pady=CARD_PAD
        )
        self._period = ctk.CTkLabel(card.body, text="", font=font("subheading"), text_color=UI_TEXT_PRIMARY)
        self._period.pack(anchor="w", padx=CARD_PAD)
        self._list = ctk.CTkScrollableFrame(card.body, fg_color="transparent", height=400)
        self._list.pack(fill="both", expand=True, padx=8, pady=CARD_PAD)

    def refresh(self) -> None:
        start, end = get_pay_period()
        self._period.configure(text=f"Period {format_date(start)} – {format_date(end)}")
        for w in self._list.winfo_children():
            w.destroy()
        if self.is_officer() and not self.can("payroll.view_all"):
            EmptyState(
                self._list,
                "Officer view",
                "Use Timecard and Banked time for personal totals. Supervisors see the full ledger.",
            ).pack(fill="x", pady=16)
            return
        data = get_payroll_period_timesheets(start)
        rows = data.get("rows") or data.get("timesheets") or data.get("officers") or []
        if isinstance(data, dict) and data.get("success") is False:
            EmptyState(self._list, "Unable to load payroll", data.get("message", "")).pack(fill="x", pady=16)
            return
        if not rows:
            EmptyState(self._list, "No payroll rows", "Import timecards or enter pay period data.").pack(
                fill="x", pady=16
            )
            return
        for row in rows[:60]:
            if isinstance(row, dict):
                name = row.get("officer_name") or row.get("name") or f"Officer {row.get('officer_id')}"
                hours = row.get("total_hours") or row.get("hours") or "—"
                pay = row.get("gross_pay") or row.get("total_pay") or ""
                text = f"{name}  ·  {hours}h" + (f"  ·  ${pay}" if pay != "" else "")
            else:
                text = str(row)
            fr = ctk.CTkFrame(self._list, fg_color=UI_SURFACE, corner_radius=8, border_width=1, border_color=UI_BORDER)
            fr.pack(fill="x", pady=3, padx=4)
            ctk.CTkLabel(fr, text=text, font=font("body"), text_color=UI_TEXT_MUTED, anchor="w").pack(
                fill="x", padx=12, pady=10
            )
