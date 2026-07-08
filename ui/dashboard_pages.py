"""Dashboard tab and refresh helpers."""

from datetime import date

import customtkinter as ctk

from config import SCHEDULE_TYPE_COURT, SCHEDULE_TYPE_TRAINING
from logic import (
    get_current_cycle_window,
    get_cycle_day,
    get_dashboard_insights,
    get_officer_by_id,
    get_officer_schedule_window,
    get_pending_day_off_requests,
    get_shift_coverage_counts_for_range,
    get_squad_on_duty,
    get_unread_notification_count,
    get_upcoming_holidays,
)
from logic.staffing_config import get_active_shift_times
from ui.branding import get_department_branding
from ui.helpers import active_officers
from ui.theme import (
    CARD_PAD,
    CORNER_RADIUS,
    DODGEVILLE_ACCENT,
    DODGEVILLE_BLUE,
    DODGEVILLE_DANGER,
    DODGEVILLE_GOLD,
    DODGEVILLE_RED,
    DODGEVILLE_SUCCESS,
    DODGEVILLE_WARNING,
    UI_BORDER,
    UI_SURFACE,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    font,
)
from ui.widgets import AlertBanner, Card, CompactButton, MetricRow, PrimaryButton, SectionHeader, StatCard
from validators import format_date


class DashboardPageMixin:
    def _dashboard_officer_id(self):
        return self._linked_officer_id() if self._is_officer_role() else None

    def _build_dashboard(self):
        page = self.pages["dashboard"]
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(5, weight=1)
        page.grid_rowconfigure(6, weight=0)

        branding = get_department_branding()
        hero = ctk.CTkFrame(
            page,
            fg_color=UI_SURFACE,
            corner_radius=CORNER_RADIUS,
            border_width=1,
            border_color=UI_BORDER,
        )
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        hero.grid_columnconfigure(0, weight=1)

        hero_body = ctk.CTkFrame(hero, fg_color="transparent")
        hero_body.pack(fill="x", padx=CARD_PAD, pady=16)
        hero_body.grid_columnconfigure(0, weight=1)

        hero_left = ctk.CTkFrame(hero_body, fg_color="transparent")
        hero_left.grid(row=0, column=0, sticky="w")
        self._hero_greeting_label = ctk.CTkLabel(
            hero_left,
            text="Good day",
            font=font("display"),
            text_color=UI_TEXT_PRIMARY,
            anchor="w",
        )
        self._hero_greeting_label.pack(fill="x")
        self._hero_dept_label = ctk.CTkLabel(
            hero_left,
            text=branding["name"],
            font=font("body"),
            text_color=UI_TEXT_MUTED,
            anchor="w",
        )
        self._hero_dept_label.pack(fill="x", pady=(4, 0))
        self._hero_mission_label = ctk.CTkLabel(
            hero_left,
            text=branding["tagline"],
            font=font("small"),
            text_color=UI_TEXT_MUTED,
            anchor="w",
            wraplength=520,
        )
        self._hero_mission_label.pack(fill="x", pady=(2, 0))

        hero_right = ctk.CTkFrame(hero_body, fg_color="transparent")
        hero_right.grid(row=0, column=1, sticky="e", padx=(16, 0))
        self._hero_date_label = ctk.CTkLabel(
            hero_right,
            text="",
            font=font("subheading"),
            text_color=UI_TEXT_PRIMARY,
            anchor="e",
        )
        self._hero_date_label.pack(anchor="e")
        self._hero_cycle_label = ctk.CTkLabel(
            hero_right,
            text="",
            font=font("small"),
            text_color=UI_TEXT_MUTED,
            anchor="e",
        )
        self._hero_cycle_label.pack(anchor="e", pady=(4, 0))

        self._dash_alert_stack = ctk.CTkFrame(page, fg_color="transparent")
        self._dash_alert_stack.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        self._dash_on_duty_strip = Card(self._dash_alert_stack)
        self._dash_on_duty_strip.pack(fill="x", pady=(0, 8))
        on_duty_hdr = ctk.CTkFrame(self._dash_on_duty_strip.body, fg_color="transparent")
        on_duty_hdr.pack(fill="x", padx=CARD_PAD, pady=(CARD_PAD, 4))
        SectionHeader(on_duty_hdr, "On Duty Now", "Live headcount by shift band").pack(side="left")
        self._dash_on_duty_body = ctk.CTkFrame(self._dash_on_duty_strip.body, fg_color="transparent")
        self._dash_on_duty_body.pack(fill="x", padx=CARD_PAD, pady=(0, CARD_PAD))

        self._dash_alerts = ctk.CTkFrame(self._dash_alert_stack, fg_color="transparent")
        self._dash_alerts.pack(fill="x")

        stats_row = ctk.CTkFrame(page, fg_color="transparent")
        stats_row.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        for col in range(3):
            stats_row.grid_columnconfigure(col, weight=1)

        self.stat_cards["officers"] = StatCard(
            stats_row,
            "Active Officers",
            "…",
            accent=DODGEVILLE_BLUE,
            badge_style=True,
        )
        self.stat_cards["officers"].grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=(0, 6))
        self.stat_cards["officers"].bind("<Button-1>", lambda e: self.show_page("officers"))

        self.stat_cards["pending"] = StatCard(
            stats_row,
            "Pending Requests",
            "0",
            accent=DODGEVILLE_WARNING,
            clickable=True,
            badge_style=True,
        )
        self.stat_cards["pending"].grid(row=0, column=1, sticky="ew", padx=6, pady=(0, 6))
        self.stat_cards["pending"].bind("<Button-1>", lambda e: self.show_page("requests"))

        self.stat_cards["pending_swaps"] = StatCard(
            stats_row,
            "Pending Swaps",
            "0",
            accent=DODGEVILLE_ACCENT,
            clickable=True,
            badge_style=True,
        )
        self.stat_cards["pending_swaps"].grid(row=0, column=2, sticky="ew", padx=(6, 0), pady=(0, 6))
        self.stat_cards["pending_swaps"].bind("<Button-1>", lambda e: self.show_page("swaps"))

        self.stat_cards["schedule_diff"] = StatCard(
            stats_row,
            "Schedule Changes",
            "0",
            accent=DODGEVILLE_GOLD,
            clickable=True,
            badge_style=True,
        )
        self.stat_cards["schedule_diff"].grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=(0, 0))
        self.stat_cards["schedule_diff"].bind("<Button-1>", lambda e: self.show_page("live_schedule"))

        self.stat_cards["open_shifts"] = StatCard(
            stats_row,
            "Open Shifts",
            "0",
            accent=DODGEVILLE_SUCCESS,
            clickable=True,
            badge_style=True,
        )
        self.stat_cards["open_shifts"].grid(row=1, column=1, sticky="ew", padx=6, pady=(0, 0))
        self.stat_cards["open_shifts"].bind(
            "<Button-1>",
            lambda e: (self.show_page("availability"), self.refresh_availability()),
        )

        self.stat_cards["manual"] = StatCard(
            stats_row,
            "Manual Review",
            "0",
            accent=DODGEVILLE_DANGER,
            clickable=True,
            badge_style=True,
        )
        self.stat_cards["manual"].grid(row=1, column=2, sticky="ew", padx=(6, 0), pady=(0, 0))
        self.stat_cards["manual"].bind(
            "<Button-1>",
            lambda e: (
                self._set_request_view("review"),
                self.show_page("requests"),
            ),
        )

        self._dash_gap_board_card = Card(page)
        self._dash_gap_board_card.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        gap_hdr = ctk.CTkFrame(self._dash_gap_board_card.body, fg_color="transparent")
        gap_hdr.pack(fill="x", padx=CARD_PAD, pady=(CARD_PAD, 4))
        SectionHeader(
            gap_hdr,
            "Coverage Gap Board",
            "Staffing gaps in the next 48 hours",
        ).pack(side="left")
        CompactButton(
            gap_hdr,
            text="View Schedule",
            width=110,
            command=lambda: self.show_page("live_schedule"),
        ).pack(side="right")
        self._dash_gap_board_list = ctk.CTkScrollableFrame(
            self._dash_gap_board_card.body,
            fg_color="transparent",
            height=96,
        )
        self._dash_gap_board_list.pack(fill="x", padx=8, pady=(0, CARD_PAD))

        mid_row = ctk.CTkFrame(page, fg_color="transparent")
        mid_row.grid(row=4, column=0, sticky="ew", pady=(0, 12))
        mid_row.grid_columnconfigure(0, weight=3)
        mid_row.grid_columnconfigure(1, weight=2)
        mid_row.grid_columnconfigure(2, weight=2)

        ops_card = Card(mid_row)
        ops_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        SectionHeader(
            ops_card.body,
            "Today's Watch",
            "Current rotation and cycle status",
        ).pack(fill="x", padx=CARD_PAD, pady=(CARD_PAD, 8))
        self._dash_ops_body = ctk.CTkFrame(ops_card.body, fg_color="transparent")
        self._dash_ops_body.pack(fill="both", expand=True, padx=CARD_PAD, pady=(0, CARD_PAD))
        self._dash_ops_metrics_host = ctk.CTkFrame(self._dash_ops_body, fg_color="transparent")
        self._dash_ops_metrics_host.pack(fill="x", pady=(0, 8))
        self._dash_ops_detail = ctk.CTkLabel(
            self._dash_ops_body,
            text="",
            font=font("body"),
            text_color=UI_TEXT_MUTED,
            anchor="w",
            justify="left",
        )
        self._dash_ops_detail.pack(fill="x")
        ctk.CTkLabel(
            self._dash_ops_body,
            text="Upcoming Holidays",
            font=font("small"),
            text_color=UI_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", pady=(10, 4))
        self._dash_holiday_list = ctk.CTkScrollableFrame(
            self._dash_ops_body,
            fg_color="transparent",
            height=88,
        )
        self._dash_holiday_list.pack(fill="x")

        self._dash_my_week_card = Card(mid_row)
        self._dash_my_week_card.grid(row=0, column=1, sticky="nsew")
        SectionHeader(
            self._dash_my_week_card.body,
            "My Week",
            "Your next 7 days on the rotation",
        ).pack(fill="x", padx=CARD_PAD, pady=(CARD_PAD, 8))
        self._dash_my_week_list = ctk.CTkScrollableFrame(
            self._dash_my_week_card.body,
            fg_color="transparent",
            height=120,
        )
        self._dash_my_week_list.pack(fill="x", padx=8, pady=(0, CARD_PAD))

        self._dash_quick_card = Card(mid_row)
        self._dash_quick_card.grid(row=0, column=2, sticky="nsew")
        SectionHeader(self._dash_quick_card.body, "Quick Actions", "Common patrol and supervisor tasks").pack(
            fill="x",
            padx=CARD_PAD,
            pady=(CARD_PAD, 8),
        )
        self._dash_quick = ctk.CTkFrame(self._dash_quick_card.body, fg_color="transparent")
        self._dash_quick.pack(fill="both", expand=True, padx=CARD_PAD, pady=(0, CARD_PAD))
        self._build_dashboard_quick_actions()

        bottom_row = ctk.CTkFrame(page, fg_color="transparent")
        bottom_row.grid(row=5, column=0, sticky="nsew")
        bottom_row.grid_columnconfigure(0, weight=2)
        bottom_row.grid_columnconfigure(1, weight=3)
        bottom_row.grid_rowconfigure(0, weight=1)

        pending_card = Card(bottom_row)
        pending_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        pending_hdr = ctk.CTkFrame(pending_card.body, fg_color="transparent")
        pending_hdr.pack(fill="x", padx=CARD_PAD, pady=(CARD_PAD, 4))
        self._dash_pending_header = SectionHeader(
            pending_hdr,
            "Pending Time Off",
            "Requests awaiting supervisor action",
        )
        self._dash_pending_header.pack(side="left")
        CompactButton(
            pending_hdr,
            text="View All",
            width=90,
            command=lambda: self.show_page("requests"),
        ).pack(side="right")
        self._dash_pending_list = ctk.CTkScrollableFrame(
            pending_card.body,
            fg_color="transparent",
        )
        self._dash_pending_list.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        alerts_card = Card(bottom_row)
        alerts_card.grid(row=0, column=1, sticky="nsew")
        self._build_alerts_inbox(alerts_card.body)

    def _build_dashboard_quick_actions(self):
        for child in self._dash_quick.winfo_children():
            child.destroy()

        if self._is_officer_role():
            actions = [
                ("My Schedule", DODGEVILLE_BLUE, lambda: self.show_page("timeline")),
                ("Request Time Off", DODGEVILLE_ACCENT, lambda: self.show_page("requests")),
                ("Alerts", DODGEVILLE_WARNING, lambda: self.show_page("notifications")),
            ]
            if self.can("schedule.updated.view"):
                actions.append(
                    ("Live Schedule", DODGEVILLE_GOLD, lambda: self.show_page("live_schedule")),
                )
        else:
            actions = [
                ("Submit Time Off", DODGEVILLE_ACCENT, lambda: self.show_page("requests")),
                ("Duty Timeline", DODGEVILLE_BLUE, lambda: self.show_page("timeline")),
            ]
            if self.can("schedule.updated.view"):
                actions.append(
                    ("Live Schedule", DODGEVILLE_GOLD, lambda: self.show_page("live_schedule")),
                )
            if self.can("reports.view"):
                actions.append(("Ops Reports", DODGEVILLE_WARNING, lambda: self.show_page("reports")))
            if self.can("officers.manage"):
                actions.append(("Patrol Roster", DODGEVILLE_BLUE, lambda: self.show_page("officers")))
            if self.can("database.backup"):
                actions.append(("Backup Database", DODGEVILLE_SUCCESS, self.backup_database))
                actions.append(("Restore Backup", DODGEVILLE_WARNING, self.restore_database))

        for idx, (label, color, cmd) in enumerate(actions):
            PrimaryButton(
                self._dash_quick,
                text=label,
                fg_color=color,
                command=cmd,
            ).grid(row=idx // 2, column=idx % 2, sticky="ew", padx=4, pady=4)
        self._dash_quick.grid_columnconfigure((0, 1), weight=1)

    _SCHEDULE_STATUS_COLORS = {
        "working": DODGEVILLE_SUCCESS,
        "off": UI_TEXT_MUTED,
        "bumped": DODGEVILLE_WARNING,
        "covering": DODGEVILLE_GOLD,
        "swapped": DODGEVILLE_ACCENT,
        "training": SCHEDULE_TYPE_TRAINING,
        "court": SCHEDULE_TYPE_COURT,
        "leave": UI_TEXT_MUTED,
    }
    _SCHEDULE_STATUS_LABELS = {
        "working": "Working",
        "off": "Off",
        "bumped": "Bumped",
        "covering": "Covering",
        "swapped": "Swapped",
        "training": "Training",
        "court": "Court",
        "leave": "Leave",
    }

    def _refresh_dashboard_my_week(self, insights: dict):
        if not hasattr(self, "_dash_my_week_list"):
            return
        for child in self._dash_my_week_list.winfo_children():
            child.destroy()
        if not insights.get("officer_scoped"):
            self._dash_my_week_card.grid_remove()
            return
        oid = self._dashboard_officer_id()
        if not oid:
            self._dash_my_week_card.grid_remove()
            return
        self._dash_my_week_card.grid()
        week = get_officer_schedule_window(oid, days=7)
        if not week.get("success"):
            ctk.CTkLabel(
                self._dash_my_week_list,
                text="Schedule unavailable.",
                font=font("body"),
                text_color=UI_TEXT_MUTED,
            ).pack(pady=12)
            return
        officer = week.get("officer") or {}
        shift_band = ""
        if officer.get("shift_start") and officer.get("shift_end"):
            shift_band = f"{officer['shift_start']}–{officer['shift_end']}"
        for day in week.get("days", []):
            status = day.get("status", "off")
            color = self._SCHEDULE_STATUS_COLORS.get(status, UI_TEXT_MUTED)
            label = self._SCHEDULE_STATUS_LABELS.get(status, status.title())
            detail = label
            if status in ("working", "covering", "swapped", "training", "court") and shift_band:
                detail = f"{label}  ·  {shift_band}"
            row = ctk.CTkFrame(self._dash_my_week_list, fg_color=UI_SURFACE, corner_radius=8)
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(
                row,
                text=f"{day['day_label']}  ·  {detail}",
                font=font("body"),
                text_color=color,
                anchor="w",
            ).pack(fill="x", padx=12, pady=6)

    def _refresh_dashboard_on_duty_now(self, insights: dict):
        if not hasattr(self, "_dash_on_duty_strip"):
            return
        if insights.get("officer_scoped"):
            self._dash_on_duty_strip.pack_forget()
            return
        if not self._dash_on_duty_strip.winfo_ismapped():
            self._dash_on_duty_strip.pack(fill="x", pady=(0, 8), before=self._dash_alerts)
        for child in self._dash_on_duty_body.winfo_children():
            child.destroy()
        today = date.today()
        day_str = today.isoformat()
        squad = get_squad_on_duty(get_cycle_day(today))
        coverage = get_shift_coverage_counts_for_range(today, today)
        shift_labels = []
        for shift_start, shift_end in get_active_shift_times().values():
            count = coverage.get((day_str, squad, shift_start), 0)
            shift_labels.append(f"{shift_start}–{shift_end}: {count}")
        ctk.CTkLabel(
            self._dash_on_duty_body,
            text=f"Squad {squad} on duty  ·  " + "  ·  ".join(shift_labels),
            font=font("body"),
            text_color=UI_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x")

    def _refresh_dashboard_gap_board(self, insights: dict):
        if not hasattr(self, "_dash_gap_board_list"):
            return
        if insights.get("officer_scoped"):
            self._dash_gap_board_card.grid_remove()
            return
        self._dash_gap_board_card.grid()
        for child in self._dash_gap_board_list.winfo_children():
            child.destroy()
        gaps = insights.get("coverage_gaps") or []
        if not gaps:
            ctk.CTkLabel(
                self._dash_gap_board_list,
                text="No staffing gaps in the next 48 hours.",
                font=font("body"),
                text_color=DODGEVILLE_SUCCESS,
            ).pack(pady=12)
            return
        for gap in gaps[:8]:
            color = DODGEVILLE_DANGER if gap["severity"] == "critical" else DODGEVILLE_WARNING
            if gap["gap_type"] == "zero_coverage":
                detail = "zero officers scheduled"
            else:
                detail = f"{gap['count']}/{gap['minimum']} night minimum"
            row = ctk.CTkFrame(self._dash_gap_board_list, fg_color=UI_SURFACE, corner_radius=8)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(
                row,
                text=(f"{gap['date']}  ·  Squad {gap['squad_on_duty']}  ·  {gap['shift_label']}  ·  {detail}"),
                font=font("body"),
                text_color=color,
                anchor="w",
            ).pack(fill="x", padx=12, pady=8)

    def _apply_dashboard_role_layout(self):
        is_officer = self._is_officer_role()
        if is_officer:
            if hasattr(self, "_dash_my_week_card"):
                self._dash_my_week_card.grid(row=0, column=1, sticky="nsew", padx=0)
            if hasattr(self, "_dash_quick_card"):
                self._dash_quick_card.grid(row=0, column=2, sticky="nsew", padx=0)
            self.stat_cards["officers"].set_label("My Squad")
            self.stat_cards["pending"].set_label("My Requests")
            self.stat_cards["pending_swaps"].set_label("My Swaps")
            self.stat_cards["schedule_diff"].set_label("My Changes")
            self.stat_cards["open_shifts"].set_label("Claimable Shifts")
            self.stat_cards["manual"].grid_remove()
            self.stat_cards["officers"].bind(
                "<Button-1>",
                lambda e: self.show_page("timeline"),
            )
            self.stat_cards["pending"].bind(
                "<Button-1>",
                lambda e: (self.show_page("requests"), self.refresh_requests()),
            )
            if hasattr(self, "_dash_pending_header"):
                self._dash_pending_header.configure(
                    title="My Requests",
                    subtitle="Your submitted time off",
                )
        else:
            if hasattr(self, "_dash_my_week_card"):
                self._dash_my_week_card.grid_remove()
            if hasattr(self, "_dash_quick_card"):
                self._dash_quick_card.grid(row=0, column=1, sticky="nsew", columnspan=2, padx=0)
            self.stat_cards["officers"].set_label("Active Officers")
            self.stat_cards["pending"].set_label("Pending Requests")
            self.stat_cards["pending_swaps"].set_label("Pending Swaps")
            self.stat_cards["schedule_diff"].set_label("Schedule Changes")
            self.stat_cards["open_shifts"].set_label("Open Shifts")
            self.stat_cards["manual"].grid(row=1, column=2, sticky="ew", padx=(6, 0))
            if hasattr(self, "_dash_pending_header"):
                self._dash_pending_header.configure(
                    title="Pending Time Off",
                    subtitle="Requests awaiting supervisor action",
                )
        self._build_dashboard_quick_actions()

    def _refresh_dashboard_alerts(self, insights: dict):
        for child in self._dash_alerts.winfo_children():
            child.destroy()
        alerts = []
        gap_count = insights.get("coverage_gap_count", 0)
        if gap_count > 0:
            critical = insights.get("coverage_gap_critical", 0)
            if critical:
                alerts.append(
                    (
                        f"Coverage gap board: {critical} zero-staffing slot(s) in the next 48 hours.",
                        "critical",
                    )
                )
            elif gap_count:
                alerts.append(
                    (
                        f"Coverage gap board: {gap_count} near-term staffing gap(s) in the next 48 hours.",
                        "warning",
                    )
                )
        if insights.get("coverage_issues", 0) > 0:
            alerts.append(
                (
                    f"Coverage alert: {insights['coverage_issues']} night minimum issue(s) this cycle.",
                    "critical",
                )
            )
        hw_count = insights.get("hours_watch_count", 0)
        if hw_count > 0:
            top_hw = insights.get("hours_watch_top") or {}
            if top_hw.get("message"):
                alerts.append(
                    (
                        f"FLSA hours watch: {top_hw['message']}",
                        top_hw.get("severity", "warning"),
                    )
                )
            elif insights.get("hours_watch_critical", 0):
                alerts.append(
                    (
                        f"FLSA hours watch: {insights['hours_watch_critical']} officer(s) at or over threshold.",
                        "critical",
                    )
                )
            else:
                alerts.append(
                    (
                        f"FLSA hours watch: {hw_count} officer(s) approaching weekly or period limits.",
                        "warning",
                    )
                )
        lc_count = insights.get("labor_compliance_count", 0)
        if lc_count > 0:
            top_lc = insights.get("labor_compliance_top") or {}
            if top_lc.get("message"):
                alerts.append(
                    (
                        f"Labor compliance: {top_lc['message']}",
                        top_lc.get("severity", "warning"),
                    )
                )
            elif insights.get("labor_compliance_critical", 0):
                alerts.append(
                    (
                        f"Labor compliance: {insights['labor_compliance_critical']} critical issue(s) "
                        "(§207(k), comp cap, or consecutive days).",
                        "critical",
                    )
                )
            else:
                alerts.append(
                    (
                        f"Labor compliance: {lc_count} officer(s) with FLSA or fatigue warnings.",
                        "warning",
                    )
                )
        elif insights.get("overtime_alerts", 0) > 0:
            top_h = insights.get("overtime_alert_top_hours")
            if top_h is not None:
                alerts.append(
                    (
                        f"Overtime watch: {top_h:.1f}h logged this pay period.",
                        insights.get("overtime_alert_top_severity", "warning"),
                    )
                )
            else:
                alerts.append(
                    (
                        f"Overtime alert: {insights['overtime_alerts']} officer(s) over threshold.",
                        "warning",
                    )
                )
        if insights.get("schedule_conflicts", 0) > 0:
            alerts.append(
                (
                    f"Availability conflict: {insights['schedule_conflicts']} blackout vs. rotation clash(es).",
                    "warning",
                )
            )
        if insights.get("pending_manual_review", 0) > 0 and not insights.get("officer_scoped"):
            alerts.append(
                (
                    f"Manual review queue: {insights['pending_manual_review']} request(s) need supervisor override.",
                    "warning",
                )
            )
        if insights.get("officer_scoped") and insights.get("claimable_bid_slots", 0) > 0:
            alerts.append(
                ("Shift bid open — rank your preferences on the Availability tab.", "warning"),
            )
        elif insights.get("open_shift_bid_count", 0) > 0:
            alerts.append(
                (
                    f"Shift bidding: {insights['open_shift_bid_count']} open bid event(s) awaiting officer responses.",
                    "warning",
                )
            )
        budget = insights.get("labor_budget") or {}
        if budget.get("configured") and budget.get("over_budget"):
            alerts.append(
                (
                    f"Labor budget exceeded: ${budget['ytd_spent']:,.0f} YTD vs ${budget['annual_budget']:,.0f} cap.",
                    "critical",
                )
            )
        if not insights.get("officer_scoped"):
            backup = insights.get("backup_status") or {}
            if backup.get("needs_backup"):
                age = backup.get("latest_age_days")
                if age is None:
                    backup_msg = "No database backup on file."
                else:
                    backup_msg = f"Latest backup is {age} day(s) old."
                alerts.append(
                    (
                        f"{backup_msg} Use Backup Database in the sidebar (recommended every "
                        f"{backup.get('max_age_days', 7)} days).",
                        "warning",
                    )
                )
            fatigue_top = insights.get("fatigue_top")
            if fatigue_top and fatigue_top.get("severity"):
                alerts.append(
                    (
                        f"Fatigue watch: {fatigue_top['officer_name']} "
                        f"score {fatigue_top['score']:.0f}/100 — review scheduling load.",
                        fatigue_top.get("severity", "warning"),
                    )
                )
            lock_rem = insights.get("pay_period_lock_reminder") or {}
            if lock_rem.get("needs_reminder"):
                days_left = lock_rem.get("days_until_end", 0)
                day_word = "day" if days_left == 1 else "days"
                alerts.append(
                    (
                        f"Pay period ends in {days_left} {day_word}. Lock the period on Payroll when "
                        "timecards are final.",
                        "warning",
                    )
                )
        if not alerts:
            AlertBanner(
                self._dash_alerts,
                "All clear. No critical coverage or scheduling alerts for this watch.",
                "success",
            ).pack(fill="x")
            return
        for message, severity in alerts[:3]:
            AlertBanner(self._dash_alerts, message, severity).pack(fill="x", pady=(0, 6))

    def _refresh_dashboard_ops(self, insights: dict):
        today = date.today()
        cycle = get_cycle_day(today)
        squad = get_squad_on_duty(cycle)
        start, end = get_current_cycle_window(today)
        unread = get_unread_notification_count(officer_id=self._dashboard_officer_id())
        shift_times = " · ".join(f"{start}–{end}" for start, end in get_active_shift_times().values())

        for child in self._dash_ops_metrics_host.winfo_children():
            child.destroy()

        metrics = [
            ("Cycle Day", str(cycle), DODGEVILLE_GOLD),
            ("Squad On Duty", f"Squad {squad}", DODGEVILLE_ACCENT),
            ("Unread Alerts", str(unread), DODGEVILLE_RED if unread else DODGEVILLE_SUCCESS),
        ]
        if not insights.get("officer_scoped"):
            metrics.append(
                (
                    "Coverage Issues",
                    str(insights.get("coverage_issues", 0)),
                    DODGEVILLE_DANGER,
                )
            )
        MetricRow(self._dash_ops_metrics_host, metrics).pack(fill="x")

        if insights.get("officer_scoped"):
            lines = [f"{today.strftime('%A')}, {format_date(today)}"]
            oid = self._dashboard_officer_id()
            if oid:
                officer = get_officer_by_id(oid)
                if officer:
                    lines.append(
                        f"Your shift: Squad {officer['squad']} · {officer['shift_start']}–{officer['shift_end']}"
                    )
            lines.append(f"Pay cycle: {format_date(start)} – {format_date(end)}")
            claimable = insights.get("claimable_open_shifts", 0)
            if claimable:
                lines.append(f"{claimable} open shift(s) available to claim")
            bid_slots = insights.get("claimable_bid_slots", 0)
            if bid_slots:
                lines.append(f"{bid_slots} shift bid slot(s) open — Blackout Dates")
        else:
            lines = [
                f"{today.strftime('%A')}, {format_date(today)}",
                f"Pay cycle window: {format_date(start)} – {format_date(end)}",
                f"Shift bands: {shift_times}",
            ]
        if not insights.get("officer_scoped") and insights.get("monthly_labor_cost"):
            lines.append(f"Projected monthly labor: ${insights['monthly_labor_cost']:,.0f}")
        self._dash_ops_detail.configure(text="\n".join(lines))

    def _refresh_dashboard_holidays(self):
        for child in self._dash_holiday_list.winfo_children():
            child.destroy()
        if self._is_officer_role():
            ctk.CTkLabel(
                self._dash_holiday_list,
                text="Your week and status cards above are your home base. Use Schedules for full calendar detail.",
                font=font("small"),
                text_color=UI_TEXT_MUTED,
                wraplength=420,
                justify="left",
            ).pack(pady=12, padx=4)
            return
        holidays = get_upcoming_holidays(60)
        if not holidays:
            ctk.CTkLabel(
                self._dash_holiday_list,
                text="No upcoming holidays in the next 60 days.",
                font=font("body"),
                text_color=UI_TEXT_MUTED,
            ).pack(pady=16)
            return
        for holiday in holidays[:4]:
            row = ctk.CTkFrame(self._dash_holiday_list, fg_color=UI_SURFACE, corner_radius=8)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(
                row,
                text=f"{format_date(holiday['holiday_date'])}  ·  {holiday['name']}",
                font=font("body"),
                anchor="w",
            ).pack(fill="x", padx=12, pady=8)

    def _refresh_dashboard_pending(self):
        for child in self._dash_pending_list.winfo_children():
            child.destroy()
        officer_id = self._dashboard_officer_id()
        pending = get_pending_day_off_requests()
        if officer_id:
            pending = [r for r in pending if r["officer_id"] == officer_id]
        if not pending:
            ctk.CTkLabel(
                self._dash_pending_list,
                text="No pending requests.",
                font=font("body"),
                text_color=UI_TEXT_MUTED,
            ).pack(pady=20)
            return
        show_actions = self.can("requests.approve") and not self._is_officer_role()
        for req in pending[:6]:
            self._render_request_row(
                self._dash_pending_list,
                req,
                compact=True,
                show_actions=show_actions,
            )

    def _refresh_dashboard_data(self):
        if not self.stat_cards:
            return
        today = date.today()
        if hasattr(self, "_hero_greeting_label"):
            from datetime import datetime

            h = datetime.now().hour
            if h < 12:
                greet = "Good morning"
            elif h < 17:
                greet = "Good afternoon"
            else:
                greet = "Good evening"
            self._hero_greeting_label.configure(text=greet)
        if hasattr(self, "_hero_date_label"):
            self._hero_date_label.configure(text=format_date(today))
        if hasattr(self, "_hero_cycle_label"):
            cycle = get_cycle_day(today)
            squad = get_squad_on_duty(cycle)
            self._hero_cycle_label.configure(text=f"Cycle day {cycle} · Squad {squad}")
        officer_id = self._dashboard_officer_id()
        import os

        if os.environ.get("SCHEDULER_UI_TEST", "").strip() == "1":
            insights = {
                "success": True,
                "officer_scoped": officer_id is not None,
                "coverage_issues": 0,
                "coverage_gap_count": 0,
                "coverage_gap_critical": 0,
                "coverage_gaps": [],
                "overtime_alerts": 0,
                "hours_watch_count": 0,
                "hours_watch_critical": 0,
                "labor_compliance_count": 0,
                "schedule_conflicts": 0,
                "pending_requests": 0,
                "pending_swaps": 0,
                "pending_manual_review": 0,
                "claimable_open_shifts": 0,
                "claimable_bid_slots": 0,
                "open_shifts": 0,
                "open_shift_bid_count": 0,
                "schedule_diff_count": 0,
            }
        else:
            insights = get_dashboard_insights(officer_id=officer_id)
        if insights.get("officer_scoped"):
            oid = officer_id
            squad_label = "…"
            if oid:
                officer = get_officer_by_id(oid)
                if officer:
                    squad_label = f"Squad {officer['squad']}"
            self.stat_cards["officers"].set_value(squad_label)
            if insights.get("claimable_bid_slots", 0) > 0:
                self.stat_cards["open_shifts"].set_label("Shift Bids Open")
                open_val = insights["claimable_bid_slots"]
            else:
                self.stat_cards["open_shifts"].set_label("Claimable Shifts")
                open_val = insights.get("claimable_open_shifts", 0)
        else:
            self.stat_cards["officers"].set_value(str(len(active_officers())))
            open_val = insights.get("open_shifts", 0)
            self.stat_cards["open_shifts"].set_label("Open Shifts")
            bid_count = insights.get("open_shift_bid_count", 0)
            if "manual" in self.stat_cards:
                if bid_count > 0:
                    self.stat_cards["manual"].set_label("Open Shift Bids")
                    self.stat_cards["manual"].set_value(str(bid_count))
                    self.stat_cards["manual"].bind(
                        "<Button-1>",
                        lambda e: (self.show_page("availability"), self.refresh_availability()),
                    )
                else:
                    self.stat_cards["manual"].set_label("Manual Review")
                    self.stat_cards["manual"].set_value(str(insights.get("pending_manual_review", 0)))
                    self.stat_cards["manual"].bind(
                        "<Button-1>",
                        lambda e: (
                            self._set_request_view("review"),
                            self.show_page("requests"),
                        ),
                    )
        self.stat_cards["pending"].set_value(str(insights.get("pending_requests", 0)))
        self.stat_cards["pending_swaps"].set_value(str(insights.get("pending_swaps", 0)))
        self.stat_cards["schedule_diff"].set_value(str(insights.get("schedule_diff_count", 0)))
        self.stat_cards["open_shifts"].set_value(str(open_val))
        if hasattr(self, "_dash_alerts"):
            self._refresh_dashboard_alerts(insights)
        if hasattr(self, "_dash_ops_body"):
            self._refresh_dashboard_ops(insights)
        if hasattr(self, "_dash_gap_board_list"):
            self._refresh_dashboard_gap_board(insights)
        if hasattr(self, "_dash_my_week_list"):
            self._refresh_dashboard_my_week(insights)
        if hasattr(self, "_dash_on_duty_body"):
            self._refresh_dashboard_on_duty_now(insights)

    def _refresh_dashboard(self):
        self._apply_dashboard_role_layout()
        self._refresh_dashboard_data()
        if hasattr(self, "_dash_pending_list"):
            self._refresh_dashboard_pending()
        if hasattr(self, "_dash_holiday_list"):
            self._refresh_dashboard_holidays()
        if hasattr(self, "notif_list"):
            self.root.after(150, self.refresh_notifications)
