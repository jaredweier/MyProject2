"""Officer profile dialog — self-service summary and password change."""

from __future__ import annotations

from tkinter import messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk

from logic import (
    change_own_password,
    get_dashboard_insights,
    get_hours_watch,
    get_officer_by_id,
    get_officer_schedule_window,
    get_officer_time_banks,
    get_pay_period,
    get_unread_notification_count,
    is_pay_period_locked,
    project_officer_annual_pay,
)
from photos import load_thumbnail
from ui.theme import (
    DODGEVILLE_ACCENT,
    DODGEVILLE_BLUE,
    DODGEVILLE_GOLD,
    DODGEVILLE_RED,
    DODGEVILLE_WARNING,
    UI_TEXT_MUTED,
    font,
)
from ui.widgets import SectionHeader
from validators import format_date

if TYPE_CHECKING:
    from ui.app import DodgevilleSchedulerApp


def open_my_profile_dialog(app: "DodgevilleSchedulerApp") -> None:
    if not app.current_user:
        return
    dlg = ctk.CTkToplevel(app.root)
    dlg.title("My Profile")
    dlg.geometry("500x640")
    dlg.transient(app.root)
    dlg.grab_set()

    user = app.current_user
    scroll = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
    scroll.pack(fill="both", expand=True, padx=16, pady=16)

    ctk.CTkLabel(scroll, text=user.get("officer_name") or user["username"], font=font("heading")).pack(anchor="w")
    ctk.CTkLabel(scroll, text=user["username"], font=font("body"), text_color=UI_TEXT_MUTED).pack(
        anchor="w",
        pady=(4, 12),
    )

    oid = user.get("officer_id")
    if oid:
        officer = get_officer_by_id(oid)
        if officer:
            thumb, _ = load_thumbnail(officer.get("photo_path"), (96, 96))
            if thumb:
                ctk.CTkLabel(scroll, text="", image=thumb).pack(anchor="w", pady=(0, 8))
            lines = [
                f"Squad {officer['squad']}  ·  {officer['shift_start']}–{officer['shift_end']}",
                f"Pay: ${officer['pay_rate']:.2f}/hr  ·  Rank #{officer['seniority_rank']}",
            ]
            if officer.get("email"):
                lines.append(f"Email: {officer['email']}")
            if officer.get("phone"):
                lines.append(f"Phone: {officer['phone']}")
            banks = get_officer_time_banks(oid)
            if banks.get("success"):
                lines.append(f"Banks: Comp {banks['comp_hours']:.1f}h  ·  Sick {banks['sick_hours']:.1f}h")
            proj = project_officer_annual_pay(oid)
            if proj.get("success"):
                lines.append(f"Projected annual pay: ${proj['total_annual_pay']:,.0f}")
            insights = get_dashboard_insights(officer_id=oid)
            unread = get_unread_notification_count(oid)
            p_start, p_end = get_pay_period()
            lines.append(
                f"Unread notifications: {unread}  ·  Pending requests: {insights['pending_requests']}  ·  "
                f"Pending swaps: {insights['pending_swaps']}"
            )
            lines.append(f"Schedule changes this month: {insights['schedule_diff_count']}")
            if insights.get("schedule_conflicts"):
                lines.append(f"Availability conflicts: {insights['schedule_conflicts']}")
            claimable = insights.get("claimable_open_shifts", 0)
            if claimable:
                lines.append(f"Open shifts you can claim: {claimable}")
            lines.append(f"Current pay period: {format_date(p_start)} – {format_date(p_end)}")
            hours_watch = get_hours_watch(officer_id=oid)
            if hours_watch.get("warning_count"):
                top = hours_watch["warnings"][0]
                lines.append(f"FLSA hours watch: {top['message']}")
            elif insights.get("overtime_alerts"):
                hours = insights.get("overtime_alert_top_hours") or 0
                lines.append(f"Overtime alert: {hours:.1f}h this pay period")
            if is_pay_period_locked(p_start):
                lines.append("Pay period status: Locked")
            week = get_officer_schedule_window(oid, days=7)
            if week.get("success"):
                status_labels = {
                    "working": "Working",
                    "off": "Off",
                    "bumped": "Bumped",
                    "covering": "Covering",
                    "swapped": "Swapped",
                    "training": "Training",
                    "court": "Court",
                    "leave": "Leave",
                }
                lines.append("Next 7 days:")
                for d in week.get("days", []):
                    label = status_labels.get(d["status"], d["status"])
                    lines.append(f"  {d['day_label']}: {label}")
            for line in lines:
                ctk.CTkLabel(scroll, text=line, font=font("body"), anchor="w").pack(fill="x", pady=2)

    SectionHeader(scroll, "Change Password", "").pack(fill="x", pady=(16, 8))
    cur_pw = ctk.CTkEntry(scroll, placeholder_text="Current password", show="•", height=36)
    cur_pw.pack(fill="x", pady=4)
    new_pw = ctk.CTkEntry(scroll, placeholder_text="New password", show="•", height=36)
    new_pw.pack(fill="x", pady=4)

    def save_pw():
        result = change_own_password(user["id"], cur_pw.get(), new_pw.get())
        if result.get("success"):
            messagebox.showinfo("Password", result["message"], parent=dlg)
            dlg.destroy()
        else:
            messagebox.showerror("Password", result.get("message"), parent=dlg)

    ctk.CTkButton(scroll, text="Update Password", fg_color=DODGEVILLE_ACCENT, command=save_pw).pack(fill="x", pady=12)

    if oid:
        _profile_btn = dict(height=32, corner_radius=8, font=font("small"))
        nav_row = ctk.CTkFrame(scroll, fg_color="transparent")
        nav_row.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(
            nav_row,
            text="Timecard",
            fg_color=DODGEVILLE_BLUE,
            command=lambda: (dlg.destroy(), app.show_page("timecard"), app.refresh_timecard()),
            **_profile_btn,
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(
            nav_row,
            text="Payroll Ledger",
            fg_color=DODGEVILLE_GOLD,
            command=lambda: (dlg.destroy(), app.show_page("payroll"), app.refresh_payroll()),
            **_profile_btn,
        ).pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkButton(
            nav_row,
            text="Time Off",
            fg_color=DODGEVILLE_ACCENT,
            command=lambda: (dlg.destroy(), app.show_page("requests"), app.refresh_requests()),
            **_profile_btn,
        ).pack(side="left", fill="x", expand=True, padx=4)
        nav_row2 = ctk.CTkFrame(scroll, fg_color="transparent")
        nav_row2.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(
            nav_row2,
            text="Shift Exchange",
            fg_color=DODGEVILLE_BLUE,
            command=lambda: (dlg.destroy(), app.show_page("swaps"), app.refresh_swaps()),
            **_profile_btn,
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(
            nav_row2,
            text="Command Post",
            fg_color=DODGEVILLE_RED,
            command=lambda: (dlg.destroy(), app.show_page("dashboard"), app._refresh_dashboard()),
            **_profile_btn,
        ).pack(side="left", fill="x", expand=True, padx=4)
        nav_row3 = ctk.CTkFrame(scroll, fg_color="transparent")
        nav_row3.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(
            nav_row3,
            text="Duty Timeline",
            fg_color=DODGEVILLE_RED,
            command=lambda: (dlg.destroy(), app.show_page("timeline"), app.refresh_gantt()),
            **_profile_btn,
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(
            nav_row3,
            text="Blackout Dates",
            fg_color=DODGEVILLE_WARNING,
            command=lambda: (dlg.destroy(), app.show_page("availability"), app.refresh_availability()),
            **_profile_btn,
        ).pack(side="left", fill="x", expand=True, padx=4)
        ctk.CTkButton(
            nav_row3,
            text="Current Monthly Schedule",
            fg_color=DODGEVILLE_GOLD,
            command=lambda: (dlg.destroy(), app.show_page("updated_schedule"), app.refresh_monthly("updated")),
            **_profile_btn,
        ).pack(side="left", fill="x", expand=True, padx=(4, 0))
