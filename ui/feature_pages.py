"""Reports and Availability tab mixins — keeps ui/app.py focused."""

from datetime import date
from tkinter import filedialog, messagebox

import customtkinter as ctk

from config import DATE_INPUT_HINT, SHIFT_TIMES
from logic import (
    add_holiday,
    add_officer_availability,
    compare_base_updated_schedule,
    create_open_shift,
    delete_holiday,
    delete_officer_availability,
    export_audit_csv,
    export_coverage_pdf,
    export_pay_period_history_csv,
    export_pay_stub_pdf,
    export_payroll_csv,
    export_requests_csv,
    export_roster_csv,
    export_schedule_diff_csv,
    export_shift_swaps_csv,
    export_timecard_csv,
    fill_open_shift,
    get_all_department_settings,
    get_audit_log,
    get_coverage_report,
    get_current_cycle_window,
    get_department_setting,
    get_equitable_ot_ledger,
    get_holidays,
    get_labor_budget_status,
    get_labor_cost_forecast,
    get_officer_availability,
    get_officers_by_seniority,
    get_open_shifts,
    get_overtime_alerts,
    get_pay_stub_preview,
    get_payroll_ytd,
    get_schedule_conflicts,
    set_department_setting,
    update_holiday,
)
from ui.theme import (
    CARD_PAD,
    DODGEVILLE_ACCENT,
    DODGEVILLE_BLUE,
    DODGEVILLE_DANGER,
    DODGEVILLE_GOLD,
    DODGEVILLE_SUCCESS,
    DODGEVILLE_WARNING,
    UI_BG,
    UI_SURFACE,
    UI_TEXT_MUTED,
    font,
)
from ui.widgets import (
    AlertBanner,
    Card,
    FormField,
    MetricRow,
    PrimaryButton,
    SectionHeader,
    StatusBadge,
    ToolbarButton,
)
from validators import format_date


class ReportsPageMixin:
    """Analytics dashboard with coverage, payroll, and export tools."""

    def _build_reports(self):
        page = self.pages["reports"]
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(page, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        toolbar.grid_columnconfigure(0, weight=1)

        hdr_row = ctk.CTkFrame(toolbar, fg_color="transparent")
        hdr_row.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        SectionHeader(hdr_row, "Reports & Analytics").pack(side="left")
        ToolbarButton(hdr_row, text="Refresh", command=self.refresh_reports).pack(side="right")

        controls_row = ctk.CTkFrame(toolbar, fg_color="transparent")
        controls_row.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkLabel(controls_row, text="Schedule month:", font=font("small"), text_color=UI_TEXT_MUTED).pack(
            side="left",
            padx=(0, 6),
        )
        today = date.today()
        self._reports_month_year = ctk.CTkComboBox(
            controls_row,
            values=[f"{today.year}-{m:02d}" for m in range(1, 13)],
            width=120,
            height=32,
            command=lambda _: self.refresh_reports(),
        )
        self._reports_month_year.set(f"{today.year}-{today.month:02d}")
        self._reports_month_year.pack(side="left")
        if self.can("audit.view"):
            ctk.CTkLabel(
                controls_row,
                text="Audit:",
                font=font("small"),
                text_color=UI_TEXT_MUTED,
            ).pack(side="left", padx=(16, 4))
            self._reports_audit_filter = ctk.CTkComboBox(
                controls_row,
                values=["All", "login", "pay_period", "open_shift", "settings"],
                width=110,
                height=32,
                command=lambda _: self.refresh_reports(),
            )
            self._reports_audit_filter.set("All")
            self._reports_audit_filter.pack(side="left")

        if self.can("reports.export"):
            exports_row = ctk.CTkFrame(toolbar, fg_color="transparent")
            exports_row.grid(row=2, column=0, sticky="ew")
            export_actions = [
                ("Roster CSV", DODGEVILLE_ACCENT, self._export_roster_csv),
                ("Payroll CSV", DODGEVILLE_GOLD, self._export_payroll_csv),
                ("Timecard CSV", UI_SURFACE, self._export_timecard_csv),
                ("Pay History", UI_SURFACE, self._export_pay_period_history_csv),
                ("Requests CSV", UI_SURFACE, self._export_requests_csv),
                ("Swaps CSV", UI_SURFACE, self._export_swaps_csv),
                ("Coverage PDF", DODGEVILLE_BLUE, self._export_coverage_pdf),
            ]
            if self.can("audit.view"):
                export_actions.append(("Audit CSV", UI_SURFACE, self._export_audit_csv))
            for idx, (label, color, cmd) in enumerate(export_actions):
                ToolbarButton(exports_row, text=label, fg_color=color, command=cmd).grid(
                    row=idx // 4,
                    column=idx % 4,
                    sticky="w",
                    padx=(0, 8),
                    pady=(0, 6),
                )
            for col in range(4):
                exports_row.grid_columnconfigure(col, weight=1)

        self.reports_scroll = ctk.CTkScrollableFrame(page, fg_color=UI_BG, corner_radius=0)
        self.reports_scroll.grid(row=1, column=0, sticky="nsew")
        self.reports_scroll.grid_columnconfigure(0, weight=1)

        self._reports_metric_row = None
        self._reports_alerts_frame = None

    def _export_audit_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        audit_filt = None
        if hasattr(self, "_reports_audit_filter"):
            val = self._reports_audit_filter.get()
            audit_filt = None if val == "All" else val
        result = export_audit_csv(path or None, action_filter=audit_filt)
        if result.get("success"):
            messagebox.showinfo("Export", f"Audit log exported ({result['count']} rows)\n{result['path']}")
            self.set_status("Audit CSV exported")
        else:
            messagebox.showerror("Export Failed", result.get("message"))

    def _export_coverage_pdf(self):
        start, end = get_current_cycle_window(date.today())
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
        )
        result = export_coverage_pdf(start, end, output_path=path or None)
        if result.get("success"):
            messagebox.showinfo("Export", f"Coverage report saved to:\n{result['path']}")
            self.set_status("Coverage PDF exported")
        else:
            messagebox.showerror("Export Failed", result.get("message", "Unknown error"))

    def _export_roster_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        result = export_roster_csv(path or None)
        if result.get("success"):
            messagebox.showinfo("Export", f"Roster exported ({result['count']} rows)\n{result['path']}")
            self.set_status("Roster CSV exported")
        else:
            messagebox.showerror("Export Failed", result.get("message", "Unknown error"))

    def _export_payroll_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        period = None
        if hasattr(self, "_payroll_period_start") and self._payroll_period_start:
            period = self._payroll_period_start
        result = export_payroll_csv(period_start=period, output_path=path or None)
        if result.get("success"):
            messagebox.showinfo("Export", f"Payroll exported ({result['count']} rows)\n{result['path']}")
            self.set_status("Payroll CSV exported")
        else:
            messagebox.showerror("Export Failed", result.get("message", "Unknown error"))

    def _export_requests_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        result = export_requests_csv(output_path=path or None)
        if result.get("success"):
            messagebox.showinfo("Export", f"Requests exported ({result['count']} rows)\n{result['path']}")
            self.set_status("Requests CSV exported")
        else:
            messagebox.showerror("Export Failed", result.get("message", "Unknown error"))

    def _export_swaps_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        result = export_shift_swaps_csv(output_path=path or None)
        if result.get("success"):
            messagebox.showinfo("Export", f"Shift swaps exported ({result['count']} rows)\n{result['path']}")
            self.set_status("Shift swaps CSV exported")
        else:
            messagebox.showerror("Export Failed", result.get("message", "Unknown error"))

    def _export_timecard_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        period = None
        if hasattr(self, "_timecard_period_start") and self._timecard_period_start:
            period = self._timecard_period_start
        elif hasattr(self, "_payroll_period_start") and self._payroll_period_start:
            period = self._payroll_period_start
        result = export_timecard_csv(period_start=period, output_path=path or None)
        if result.get("success"):
            messagebox.showinfo("Export", f"Timecard exported ({result['count']} rows)\n{result['path']}")
            self.set_status("Timecard CSV exported")
        else:
            messagebox.showerror("Export Failed", result.get("message", "Unknown error"))

    def _export_pay_period_history_csv(self):
        if not (self.can("reports.export") or self._is_officer_role()):
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        officer_id = self._linked_officer_id() if self._is_officer_role() else None
        result = export_pay_period_history_csv(
            limit=12,
            officer_id=officer_id,
            output_path=path,
        )
        if result.get("success"):
            messagebox.showinfo(
                "Export",
                f"Pay period history exported ({result['count']} rows)\n{result['path']}",
            )
            self.set_status("Pay period history CSV exported")
        else:
            messagebox.showerror("Export Failed", result.get("message", "Unknown error"))

    def refresh_reports(self):
        if not hasattr(self, "reports_scroll"):
            return
        for w in self.reports_scroll.winfo_children():
            w.destroy()
        if not self.can("reports.view"):
            ctk.CTkLabel(
                self.reports_scroll,
                text="Reports require Supervisor or Administration access.",
                font=font("body"),
                text_color=UI_TEXT_MUTED,
            ).pack(pady=40)
            return

        today = date.today()
        start, end = get_current_cycle_window(today)
        coverage = get_coverage_report(start, end)
        overtime = get_overtime_alerts()
        conflicts = get_schedule_conflicts(start, end)
        ytd = get_payroll_ytd(today.year)
        labor = get_labor_cost_forecast(3)

        metrics = [
            (
                "Coverage Issues",
                coverage.get("issue_count", 0),
                DODGEVILLE_DANGER if coverage.get("issue_count") else DODGEVILLE_SUCCESS,
            ),
            (
                "Overtime Alerts",
                overtime.get("alert_count", 0),
                DODGEVILLE_WARNING if overtime.get("alert_count") else DODGEVILLE_SUCCESS,
            ),
            (
                "Schedule Conflicts",
                conflicts.get("conflict_count", 0),
                DODGEVILLE_DANGER if conflicts.get("conflict_count") else DODGEVILLE_SUCCESS,
            ),
            ("YTD Labor", f"${ytd.get('department_total_pay', 0):,.0f}", DODGEVILLE_GOLD),
        ]
        MetricRow(self.reports_scroll, metrics).pack(fill="x", pady=(0, 12))

        alerts = []
        if coverage.get("issue_count"):
            alerts.append(
                (
                    f"{coverage['issue_count']} night staffing gap(s) in current cycle",
                    "critical",
                )
            )
        if overtime.get("alert_count"):
            alerts.append(
                (
                    f"{overtime['alert_count']} officer(s) approaching overtime threshold",
                    "warning",
                )
            )
        if conflicts.get("conflict_count"):
            alerts.append(
                (
                    f"{conflicts['conflict_count']} availability conflict(s) with active schedule",
                    "warning",
                )
            )
        if alerts:
            for msg, sev in alerts:
                banner = AlertBanner(self.reports_scroll, msg, sev)
                banner.pack(fill="x", pady=4)
                if "overtime" in msg.lower():
                    banner.configure(cursor="hand2")
                elif "conflict" in msg.lower():
                    banner.bind("<Button-1>", lambda e: self.show_page("availability"))
                    banner.configure(cursor="hand2")
                elif "staffing gap" in msg.lower() or "coverage" in msg.lower():
                    banner.bind("<Button-1>", lambda e: self.show_page("updated_schedule"))
                    banner.configure(cursor="hand2")
        else:
            AlertBanner(
                self.reports_scroll,
                "All clear. No coverage or scheduling alerts.",
                "success",
            ).pack(fill="x", pady=4)

        self._render_report_section(
            "Coverage, Current Cycle",
            f"{format_date(start)} – {format_date(end)}",
            [
                (
                    f"{format_date(d['date'])}  Squad {d['squad_on_duty']}"
                    + ("  ⚠ night gap" if d.get("night_issues") else ""),
                    DODGEVILLE_DANGER if d.get("night_issues") else UI_TEXT_MUTED,
                )
                for d in coverage.get("days", [])[:14]
            ],
        )

        ot_lines = [
            (
                f"{a['officer_name']}  ·  {a['hours']:.1f}h  (cap ~{a['period_cap']:.0f}h)",
                DODGEVILLE_DANGER if a["severity"] == "critical" else DODGEVILLE_WARNING,
            )
            for a in overtime.get("alerts", [])[:8]
        ]
        self._render_report_section("Overtime Alerts", "Current pay period", ot_lines or [("None", DODGEVILLE_SUCCESS)])

        ot_ledger = get_equitable_ot_ledger()
        ledger_lines = [
            (
                f"{row['officer_name']}  ·  Squad {row['squad']}  ·  {row['ot_hours']:.1f}h OT"
                f"  ({row['vs_avg']:+.1f}h vs squad avg)",
                DODGEVILLE_WARNING
                if row["fairness"] == "high"
                else DODGEVILLE_SUCCESS
                if row["fairness"] == "low"
                else UI_TEXT_MUTED,
            )
            for row in ot_ledger.get("ledger", [])[:12]
        ]
        self._render_report_section(
            "Equitable OT Ledger",
            f"Dept avg {ot_ledger.get('department_ot_avg', 0):.1f}h this period",
            ledger_lines or [("No OT/comp entries this period", DODGEVILLE_SUCCESS)],
        )

        conflict_lines = [
            (
                f"{c['officer_name']}  ·  {format_date(c['unavailable_date'])}  ·  scheduled {c['schedule_status']}",
                DODGEVILLE_WARNING,
            )
            for c in conflicts.get("conflicts", [])[:8]
        ]
        self._render_report_section(
            "Availability Conflicts", "Unavailable but scheduled", conflict_lines or [("None", DODGEVILLE_SUCCESS)]
        )

        ytd_lines = [
            (f"{r['officer']['name']}  ·  ${r['total_pay']:,.2f}  ·  {r['total_hours']:.1f}h", UI_TEXT_MUTED)
            for r in ytd.get("officers", [])[:10]
        ]
        self._render_report_section(
            f"Payroll YTD {today.year}",
            f"Department total: ${ytd.get('department_total_pay', 0):,.2f}",
            ytd_lines or [("No payroll entries yet", UI_TEXT_MUTED)],
        )

        forecast_lines = [
            (f"{f['year']}-{f['month']:02d}  ·  ${f['projected_cost']:,.0f} projected", UI_TEXT_MUTED)
            for f in labor.get("forecast", [])
        ]
        self._render_report_section(
            "Labor Cost Forecast",
            f"Monthly avg ${labor.get('monthly_average', 0):,.0f}  ·  Annual ${labor.get('annual_projection', 0):,.0f}",
            forecast_lines,
        )

        budget = get_labor_budget_status(today.year)
        if budget.get("configured"):
            budget_lines = [
                (f"YTD spend: ${budget['ytd_spent']:,.0f} ({budget['ytd_pct']:.0f}% of budget)", UI_TEXT_MUTED),
                (
                    f"Projected annual: ${budget['projected_annual']:,.0f} ({budget['projected_pct']:.0f}%)",
                    UI_TEXT_MUTED,
                ),
            ]
            if budget.get("over_budget"):
                budget_lines.append(("⚠ Projected spend exceeds annual budget", DODGEVILLE_DANGER))
            self._render_report_section(
                "Labor Budget",
                f"Annual budget: ${budget['annual_budget']:,.0f}",
                budget_lines,
            )
        elif self.can("settings.manage"):
            self._build_budget_setting_card()

        if self.can("settings.manage"):
            self._build_department_settings_card()

        report_year, report_month = today.year, today.month
        if hasattr(self, "_reports_month_year"):
            try:
                y_str, m_str = self._reports_month_year.get().split("-")
                report_year, report_month = int(y_str), int(m_str)
            except ValueError:
                pass
        diff = compare_base_updated_schedule(report_year, report_month)
        if diff.get("success"):
            diff_lines = [
                (
                    f"{d['assignment_date']}  ·  {d['officer_name']}  ·  {d['base_status']} → {d['updated_status']}",
                    DODGEVILLE_GOLD,
                )
                for d in diff.get("diffs", [])[:12]
            ]
            subtitle = f"{diff['diff_count']} change(s) this month"
            if not diff_lines:
                diff_lines = [("Schedules match. No deviations from base.", DODGEVILLE_SUCCESS)]
        else:
            subtitle = diff.get("message", "Unavailable")
            diff_lines = [(subtitle, UI_TEXT_MUTED)]
        self._render_report_section("Schedule Diff", f"Base vs Updated  ·  {subtitle}", diff_lines)
        if diff.get("success") and diff.get("diff_count") and self.can("reports.export"):
            self._build_schedule_diff_export_card(report_year, report_month)

        if self.can("audit.view"):
            audit_filt = None
            if hasattr(self, "_reports_audit_filter"):
                val = self._reports_audit_filter.get()
                audit_filt = None if val == "All" else val
            audit = get_audit_log(15, action_filter=audit_filt)
            audit_lines = [
                (f"{a['created_at'][:16]}  ·  {a['action']}  ·  {a.get('username') or 'system'}", UI_TEXT_MUTED)
                for a in audit
            ]
            self._render_report_section(
                "Recent Audit Log", "Last 15 actions", audit_lines or [("No entries", UI_TEXT_MUTED)]
            )

        if self.can("reports.export"):
            self._build_pay_stub_section()

    def _render_report_section(self, title: str, subtitle: str, lines: list):
        card = Card(self.reports_scroll)
        card.pack(fill="x", pady=6)
        SectionHeader(card.body, title, subtitle).pack(fill="x", padx=CARD_PAD, pady=(CARD_PAD, 6))
        content = ctk.CTkFrame(card.body, fg_color="transparent")
        content.pack(fill="x", padx=CARD_PAD, pady=(0, CARD_PAD))
        for text, color in lines:
            ctk.CTkLabel(content, text=text, font=font("small"), text_color=color, anchor="w").pack(fill="x", pady=1)

    def _build_schedule_diff_export_card(self, year: int, month: int):
        card = Card(self.reports_scroll)
        card.pack(fill="x", pady=6)
        row = ctk.CTkFrame(card.body, fg_color="transparent")
        row.pack(fill="x", padx=CARD_PAD, pady=CARD_PAD)
        ctk.CTkButton(
            row,
            text="Export Schedule Diff CSV",
            height=32,
            fg_color=DODGEVILLE_GOLD,
            command=lambda: self._export_schedule_diff_from_reports(year, month),
        ).pack(side="left")

    def _export_schedule_diff_from_reports(self, year: int, month: int):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        result = export_schedule_diff_csv(year, month, path or None)
        if result.get("success"):
            messagebox.showinfo("Export", f"Schedule diff exported ({result['count']} rows)\n{result['path']}")
            self.set_status("Schedule diff CSV exported")
        else:
            messagebox.showerror("Export Failed", result.get("message", "Export failed"))

    def _build_pay_stub_section(self):
        card = Card(self.reports_scroll)
        card.pack(fill="x", pady=6)
        SectionHeader(card.body, "Pay Stub Preview", "Select officer for current period").pack(
            fill="x",
            padx=CARD_PAD,
            pady=(CARD_PAD, 6),
        )
        row = ctk.CTkFrame(card.body, fg_color="transparent")
        row.pack(fill="x", padx=CARD_PAD, pady=(0, CARD_PAD))
        officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
        names = [o["name"] for o in officers]
        self._stub_officer_var = ctk.StringVar(value=names[0] if names else "")
        ctk.CTkOptionMenu(row, variable=self._stub_officer_var, values=names or ["None"], width=220).pack(side="left")
        ctk.CTkButton(
            row,
            text="Preview",
            height=32,
            fg_color=DODGEVILLE_ACCENT,
            command=self._show_pay_stub_preview,
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            row,
            text="Export PDF",
            height=32,
            fg_color=DODGEVILLE_GOLD,
            command=self._export_pay_stub_pdf,
        ).pack(side="left", padx=4)
        self._stub_preview_label = ctk.CTkLabel(
            card.body,
            text="",
            font=font("body"),
            justify="left",
            anchor="nw",
        )
        self._stub_preview_label.pack(fill="x", padx=CARD_PAD, pady=(0, CARD_PAD))
        self._stub_officers = {o["name"]: o["id"] for o in officers}

    def _export_pay_stub_pdf(self):
        oid = self._stub_officers.get(self._stub_officer_var.get())
        if not oid:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
        )
        result = export_pay_stub_pdf(oid, output_path=path or None)
        if result.get("success"):
            messagebox.showinfo("Export", f"Pay stub saved to:\n{result['path']}")
            self.set_status("Pay stub PDF exported")
        else:
            messagebox.showerror("Export Failed", result.get("message"))

    def _build_department_settings_card(self):
        card = Card(self.reports_scroll)
        card.pack(fill="x", pady=6)
        SectionHeader(card.body, "Department Settings", "Administration configuration").pack(
            fill="x",
            padx=CARD_PAD,
            pady=(CARD_PAD, 6),
        )
        settings = get_all_department_settings()
        form = ctk.CTkFrame(card.body, fg_color="transparent")
        form.pack(fill="x", padx=CARD_PAD, pady=(0, CARD_PAD))

        ctk.CTkLabel(form, text="Department name", font=font("small"), text_color=UI_TEXT_MUTED).pack(anchor="w")
        name_row = ctk.CTkFrame(form, fg_color="transparent")
        name_row.pack(fill="x", pady=(4, 8))
        self._dept_name_entry = ctk.CTkEntry(name_row, height=36)
        self._dept_name_entry.insert(0, get_department_setting("department_name", "Dodgeville Police Department"))
        self._dept_name_entry.pack(side="left", fill="x", expand=True)

        def save_name():
            uid = self.current_user.get("id") if self.current_user else None
            result = set_department_setting(
                "department_name",
                self._dept_name_entry.get().strip(),
                user_id=uid,
            )
            if result.get("success"):
                self._refresh_department_branding()
                self.set_status("Department name updated")
            else:
                messagebox.showerror("Error", result.get("message"))

        ctk.CTkButton(name_row, text="Save", height=36, width=70, fg_color=DODGEVILLE_ACCENT, command=save_name).pack(
            side="left",
            padx=8,
        )

        from config import DEFAULT_DEPARTMENT_MISSION, DEFAULT_DEPARTMENT_TAGLINE

        ctk.CTkLabel(form, text="Mission statement", font=font("small"), text_color=UI_TEXT_MUTED).pack(
            anchor="w",
            pady=(8, 0),
        )
        mission_row = ctk.CTkFrame(form, fg_color="transparent")
        mission_row.pack(fill="x", pady=(4, 8))
        self._dept_mission_entry = ctk.CTkEntry(mission_row, height=36)
        self._dept_mission_entry.insert(
            0,
            get_department_setting("department_mission", DEFAULT_DEPARTMENT_MISSION),
        )
        self._dept_mission_entry.pack(side="left", fill="x", expand=True)

        def save_mission():
            uid = self.current_user.get("id") if self.current_user else None
            result = set_department_setting(
                "department_mission",
                self._dept_mission_entry.get().strip(),
                user_id=uid,
            )
            if result.get("success"):
                self._refresh_department_branding()
                self.set_status("Mission statement updated")
            else:
                messagebox.showerror("Error", result.get("message"))

        ctk.CTkButton(
            mission_row,
            text="Save",
            height=36,
            width=70,
            fg_color=DODGEVILLE_ACCENT,
            command=save_mission,
        ).pack(side="left", padx=8)

        ctk.CTkLabel(form, text="Tagline", font=font("small"), text_color=UI_TEXT_MUTED).pack(anchor="w")
        tag_row = ctk.CTkFrame(form, fg_color="transparent")
        tag_row.pack(fill="x", pady=(4, 8))
        self._dept_tagline_entry = ctk.CTkEntry(tag_row, height=36, width=180)
        self._dept_tagline_entry.insert(
            0,
            get_department_setting("department_tagline", DEFAULT_DEPARTMENT_TAGLINE),
        )
        self._dept_tagline_entry.pack(side="left")

        def save_tagline():
            uid = self.current_user.get("id") if self.current_user else None
            result = set_department_setting(
                "department_tagline",
                self._dept_tagline_entry.get().strip(),
                user_id=uid,
            )
            if result.get("success"):
                self._refresh_department_branding()
                self.set_status("Tagline updated")
            else:
                messagebox.showerror("Error", result.get("message"))

        ctk.CTkButton(
            tag_row,
            text="Save",
            height=36,
            width=70,
            fg_color=DODGEVILLE_ACCENT,
            command=save_tagline,
        ).pack(side="left", padx=8)

        ctk.CTkLabel(form, text="Overtime alert threshold (hours)", font=font("small"), text_color=UI_TEXT_MUTED).pack(
            anchor="w"
        )
        ot_row = ctk.CTkFrame(form, fg_color="transparent")
        ot_row.pack(fill="x", pady=(4, 8))
        self._ot_threshold_entry = ctk.CTkEntry(ot_row, height=36, width=100)
        self._ot_threshold_entry.insert(0, get_department_setting("overtime_threshold", "80"))
        self._ot_threshold_entry.pack(side="left")

        def save_ot():
            uid = self.current_user.get("id") if self.current_user else None
            result = set_department_setting(
                "overtime_threshold",
                self._ot_threshold_entry.get().strip(),
                user_id=uid,
            )
            if result.get("success"):
                self.set_status("Overtime threshold updated")
            else:
                messagebox.showerror("Error", result.get("message"))

        ctk.CTkButton(ot_row, text="Save", height=36, width=70, fg_color=DODGEVILLE_ACCENT, command=save_ot).pack(
            side="left",
            padx=8,
        )

        if settings:
            lines = [
                f"{k}: {v}"
                for k, v in sorted(settings.items())
                if k
                not in (
                    "overtime_threshold",
                    "department_name",
                    "department_mission",
                    "department_tagline",
                )
            ]
            if lines:
                ctk.CTkLabel(
                    form,
                    text="Other settings:" + "".join(f" {x}" for x in lines[:4]),
                    font=font("small"),
                    text_color=UI_TEXT_MUTED,
                    wraplength=520,
                    anchor="w",
                ).pack(fill="x", pady=(4, 0))

    def _build_budget_setting_card(self):
        card = Card(self.reports_scroll)
        card.pack(fill="x", pady=6)
        SectionHeader(card.body, "Labor Budget", "Set annual labor budget for tracking").pack(
            fill="x",
            padx=CARD_PAD,
            pady=(CARD_PAD, 6),
        )
        row = ctk.CTkFrame(card.body, fg_color="transparent")
        row.pack(fill="x", padx=CARD_PAD, pady=(0, CARD_PAD))
        self._budget_entry = ctk.CTkEntry(row, placeholder_text="e.g. 2500000", height=36, width=160)
        self._budget_entry.pack(side="left")

        def save_budget():
            uid = self.current_user.get("id") if self.current_user else None
            result = set_department_setting("annual_labor_budget", self._budget_entry.get().strip(), user_id=uid)
            if result.get("success"):
                self.refresh_reports()
                self.set_status("Labor budget saved")
            else:
                messagebox.showerror("Error", result.get("message"))

        ctk.CTkButton(row, text="Save Budget", height=36, fg_color=DODGEVILLE_ACCENT, command=save_budget).pack(
            side="left",
            padx=8,
        )

    def _show_pay_stub_preview(self):
        oid = self._stub_officers.get(self._stub_officer_var.get())
        if not oid:
            return
        stub = get_pay_stub_preview(oid)
        if not stub.get("success"):
            self._stub_preview_label.configure(text=stub.get("message", "Error"))
            return
        o = stub["officer"]
        self._stub_preview_label.configure(
            text=(
                f"{o['name']}  ·  {format_date(stub['period_start'])} to {format_date(stub['period_end'])}\n"
                f"Rate: ${stub['hourly_rate']:.2f}/hr  ·  Regular: {stub['regular_hours']:.1f}h  ·  "
                f"Other: {stub['other_hours']:.1f}h  ·  Gross: ${stub['gross_pay']:,.2f}"
            )
        )


class AvailabilityPageMixin:
    """Officer blackout dates and department holidays."""

    def _build_availability(self):
        page = self.pages["availability"]
        page.grid_columnconfigure(0, weight=1)
        page.grid_columnconfigure(1, weight=1)
        page.grid_rowconfigure(0, weight=1)

        left = Card(page)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.body.grid_rowconfigure(1, weight=1)
        SectionHeader(left.body, "Officer Availability", "Blackout / unavailable dates").pack(
            fill="x",
            padx=CARD_PAD,
            pady=(CARD_PAD, 8),
        )
        self._avail_alert_frame = ctk.CTkFrame(left.body, fg_color="transparent")
        self._avail_alert_frame.pack(fill="x", padx=CARD_PAD, pady=(0, 4))

        form = ctk.CTkFrame(left.body, fg_color="transparent")
        form.pack(fill="x", padx=CARD_PAD, pady=(0, 8))
        officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
        if self.current_user and self.current_user.get("officer_id") and not self.can("availability.manage_all"):
            linked = [o for o in officers if o["id"] == self.current_user["officer_id"]]
            officers = linked or officers
        names = [o["name"] for o in officers]
        self._avail_officer_var = ctk.StringVar(value=names[0] if names else "")
        self._avail_officers = {o["name"]: o["id"] for o in officers}
        FormField(
            form,
            "Officer",
            lambda p: ctk.CTkOptionMenu(p, variable=self._avail_officer_var, values=names or ["None"]),
        ).pack(fill="x", pady=4)
        date_field = FormField(
            form,
            "Unavailable Date",
            lambda p: ctk.CTkEntry(p, placeholder_text=DATE_INPUT_HINT, height=36),
        )
        date_field.pack(fill="x", pady=4)
        self._avail_date_entry = date_field.widget
        reason_field = FormField(
            form,
            "Reason",
            lambda p: ctk.CTkEntry(p, placeholder_text="Optional reason", height=36),
        )
        reason_field.pack(fill="x", pady=4)
        self._avail_reason_entry = reason_field.widget
        ctk.CTkButton(
            form,
            text="Add Unavailable Date",
            height=36,
            fg_color=DODGEVILLE_ACCENT,
            command=self._add_availability,
        ).pack(fill="x", pady=(8, 0))

        self.avail_list = ctk.CTkScrollableFrame(left.body, fg_color="transparent")
        self.avail_list.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        right = Card(page)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right.body.grid_rowconfigure(1, weight=1)
        hdr = ctk.CTkFrame(right.body, fg_color="transparent")
        hdr.pack(fill="x", padx=CARD_PAD, pady=(CARD_PAD, 8))
        SectionHeader(hdr, "Department Holidays", "Administration: add, edit, or remove").pack(side="left")
        if self.can("holidays.manage"):
            self._holiday_year_var = ctk.StringVar(value=str(date.today().year))
            years = [str(y) for y in range(date.today().year - 1, date.today().year + 3)]
            ctk.CTkOptionMenu(
                hdr,
                variable=self._holiday_year_var,
                values=years,
                width=90,
                command=lambda _: self.refresh_availability(),
            ).pack(side="right", padx=(4, 0))
            ctk.CTkButton(
                hdr,
                text="+ Add",
                width=70,
                height=28,
                fg_color=DODGEVILLE_GOLD,
                command=self._show_add_holiday_dialog,
            ).pack(side="right", padx=(4, 0))

        self.holiday_list = ctk.CTkScrollableFrame(right.body, fg_color="transparent", height=180)
        self.holiday_list.pack(fill="x", padx=8, pady=(0, 8))

        self._open_shift_header = SectionHeader(
            right.body,
            "Open Shifts",
            "Coverage gaps officers can claim",
        )
        self._open_shift_header.pack(fill="x", padx=CARD_PAD, pady=(4, 6))
        if self.can("open_shifts.manage"):
            os_form = ctk.CTkFrame(right.body, fg_color="transparent")
            os_form.pack(fill="x", padx=CARD_PAD, pady=(0, 6))
            self._open_shift_date = ctk.CTkEntry(os_form, placeholder_text=DATE_INPUT_HINT, height=32, width=110)
            self._open_shift_date.pack(side="left", padx=(0, 4))
            shift_opts = [f"{s} - {e}" for s, e in SHIFT_TIMES.values()]
            self._open_shift_var = ctk.StringVar(value=shift_opts[0] if shift_opts else "")
            ctk.CTkOptionMenu(os_form, variable=self._open_shift_var, values=shift_opts, width=140).pack(
                side="left", padx=4
            )
            ctk.CTkButton(
                os_form,
                text="+ Post",
                width=70,
                height=32,
                fg_color=DODGEVILLE_ACCENT,
                command=self._post_open_shift,
            ).pack(side="left", padx=4)

        self.open_shift_list = ctk.CTkScrollableFrame(right.body, fg_color="transparent")
        self.open_shift_list.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _add_availability(self):
        if not self.can("availability.manage_own") and not self.can("availability.manage_all"):
            messagebox.showerror("Permission", "You cannot manage availability")
            return
        oid = self._avail_officers.get(self._avail_officer_var.get())
        if not oid:
            return
        uid = self.current_user.get("id") if self.current_user else None
        result = add_officer_availability(
            oid,
            self._avail_date_entry.get().strip(),
            self._avail_reason_entry.get().strip(),
            user_id=uid,
        )
        if result.get("success"):
            self._avail_date_entry.delete(0, "end")
            self._avail_reason_entry.delete(0, "end")
            self.refresh_availability()
            self._refresh_dashboard_data()
            self._update_notification_badge()
            if result.get("warning"):
                messagebox.showwarning("Schedule Conflict", result["warning"])
            self.set_status("Availability recorded")
        else:
            messagebox.showerror("Error", result.get("message"))

    def _show_add_holiday_dialog(self):
        self._show_holiday_dialog()

    def _show_edit_holiday_dialog(self, holiday: dict):
        self._show_holiday_dialog(holiday)

    def _show_holiday_dialog(self, holiday: dict | None = None):
        editing = holiday is not None
        dlg = ctk.CTkToplevel(self.root)
        dlg.title("Edit Holiday" if editing else "Add Holiday")
        dlg.geometry("380x300")
        dlg.transient(self.root)
        dlg.grab_set()
        ctk.CTkLabel(dlg, text="Holiday Name", font=font("small"), text_color=UI_TEXT_MUTED).pack(
            anchor="w", padx=20, pady=(16, 4)
        )
        name_e = ctk.CTkEntry(dlg, height=36)
        name_e.pack(fill="x", padx=20)
        if editing:
            name_e.insert(0, holiday.get("name") or "")
        ctk.CTkLabel(dlg, text=f"Date ({DATE_INPUT_HINT})", font=font("small"), text_color=UI_TEXT_MUTED).pack(
            anchor="w", padx=20, pady=(12, 4)
        )
        date_e = ctk.CTkEntry(dlg, height=36)
        date_e.pack(fill="x", padx=20)
        if editing:
            date_e.insert(0, format_date(holiday.get("holiday_date")))
        paid_var = ctk.BooleanVar(value=bool(holiday.get("is_paid", 1)) if editing else True)
        ctk.CTkCheckBox(dlg, text="Paid holiday", variable=paid_var, font=font("body")).pack(
            anchor="w", padx=20, pady=(12, 0)
        )
        ctk.CTkLabel(dlg, text="Notes (optional)", font=font("small"), text_color=UI_TEXT_MUTED).pack(
            anchor="w", padx=20, pady=(12, 4)
        )
        notes_e = ctk.CTkEntry(dlg, height=36)
        notes_e.pack(fill="x", padx=20)
        if editing and holiday.get("notes"):
            notes_e.insert(0, holiday["notes"])

        def save():
            uid = self.current_user.get("id") if self.current_user else None
            payload = dict(
                name=name_e.get().strip(),
                holiday_date=date_e.get().strip(),
                is_paid=paid_var.get(),
                notes=notes_e.get().strip(),
                user_id=uid,
            )
            if editing:
                result = update_holiday(holiday["id"], **payload)
            else:
                result = add_holiday(**payload)
            if result.get("success"):
                dlg.destroy()
                self.refresh_availability()
                self._refresh_dashboard_data()
                self.set_status("Holiday updated" if editing else "Holiday added")
            else:
                messagebox.showerror("Error", result.get("message"), parent=dlg)

        ctk.CTkButton(dlg, text="Save", fg_color=DODGEVILLE_ACCENT, command=save).pack(pady=20)

    def _post_open_shift(self):
        date_str = self._open_shift_date.get().strip()
        parts = self._open_shift_var.get().split(" - ")
        if len(parts) != 2:
            return
        uid = self.current_user.get("id") if self.current_user else None
        result = create_open_shift(date_str, parts[0], parts[1], user_id=uid)
        if result.get("success"):
            self._open_shift_date.delete(0, "end")
            self.refresh_availability()
            self._refresh_dashboard_data()
            self.set_status("Open shift posted")
        else:
            messagebox.showerror("Error", result.get("message"))

    def _claim_open_shift(self, shift_id: int):
        if not self.can("open_shifts.claim"):
            return
        oid = self.current_user.get("officer_id") if self.current_user else None
        if not oid:
            messagebox.showwarning("Claim", "Link your user account to an officer profile.")
            return
        uid = self.current_user.get("id")
        result = fill_open_shift(shift_id, oid, user_id=uid)
        if result.get("success"):
            self.refresh_availability()
            self._refresh_dashboard_data()
            self.set_status("Open shift claimed")
        else:
            messagebox.showerror("Error", result.get("message"))

    def refresh_availability(self):
        if not hasattr(self, "avail_list"):
            return
        for w in self.avail_list.winfo_children():
            w.destroy()
        for w in self.holiday_list.winfo_children():
            w.destroy()
        if hasattr(self, "open_shift_list"):
            for w in self.open_shift_list.winfo_children():
                w.destroy()
        for row in list(getattr(self, "_open_shift_row_widgets", {}).values()):
            try:
                if row.winfo_exists():
                    row.configure(border_width=0)
            except Exception:
                pass
        self._open_shift_row_widgets = {}

        officer_id = None
        if not self.can("availability.manage_all") and self.current_user:
            officer_id = self.current_user.get("officer_id")
        start, end = get_current_cycle_window()
        conflicts_data = get_schedule_conflicts(start, end, officer_id=officer_id)
        conflict_keys = {(c["officer_id"], c["unavailable_date"]) for c in conflicts_data.get("conflicts", [])}
        if hasattr(self, "_avail_alert_frame"):
            for w in self._avail_alert_frame.winfo_children():
                w.destroy()
        for row in list(getattr(self, "_availability_row_widgets", {}).values()):
            try:
                if row.winfo_exists():
                    row.destroy()
            except Exception:
                pass
        self._availability_row_widgets = {}
        entries = get_officer_availability(officer_id=officer_id)
        first_conflict_id = None
        if not entries:
            ctk.CTkLabel(
                self.avail_list,
                text="No blackout dates recorded.",
                text_color=UI_TEXT_MUTED,
                font=font("body"),
            ).pack(anchor="w", padx=8, pady=8)
        else:
            can_delete = self.can("availability.manage_all") or self.can("availability.manage_own")
            for entry in entries:
                is_conflict = (entry["officer_id"], entry["unavailable_date"]) in conflict_keys
                if is_conflict and first_conflict_id is None:
                    first_conflict_id = entry["id"]
                row_kwargs = {
                    "fg_color": UI_SURFACE,
                    "corner_radius": 8,
                    "border_width": 2 if is_conflict else 0,
                }
                if is_conflict:
                    row_kwargs["border_color"] = DODGEVILLE_GOLD
                row = ctk.CTkFrame(self.avail_list, **row_kwargs)
                row.pack(fill="x", pady=3, padx=4)
                inner = ctk.CTkFrame(row, fg_color="transparent")
                inner.pack(fill="x", padx=12, pady=8)
                text = f"{entry['officer_name']}  ·  {format_date(entry['unavailable_date'])}"
                if entry.get("reason"):
                    text += f"  ·  {entry['reason']}"
                if is_conflict:
                    text += "  ·  ⚠ conflicts with schedule"
                ctk.CTkLabel(
                    inner,
                    text=text,
                    font=font("body"),
                    anchor="w",
                    text_color=DODGEVILLE_GOLD if is_conflict else None,
                ).pack(side="left", fill="x", expand=True)
                if can_delete:
                    ctk.CTkButton(
                        inner,
                        text="✕",
                        width=32,
                        height=28,
                        fg_color=DODGEVILLE_DANGER,
                        command=lambda eid=entry["id"]: self._delete_availability(eid),
                    ).pack(side="right")
                self._availability_row_widgets[entry["id"]] = row

        conflict_count = len(conflict_keys)
        if hasattr(self, "_avail_alert_frame") and conflict_count:
            msg = (
                f"{conflict_count} blackout date(s) conflict with scheduled shifts this cycle"
                if officer_id
                else f"{conflict_count} availability conflict(s) this cycle"
            )
            if first_conflict_id:
                msg += ". Click to highlight."
            banner = AlertBanner(self._avail_alert_frame, msg, "warning")
            banner.pack(fill="x")
            if first_conflict_id:
                banner.bind(
                    "<Button-1>",
                    lambda e, eid=first_conflict_id: self._focus_availability_row(eid),
                )
                banner.configure(cursor="hand2")

        if getattr(self, "_highlight_availability_id", None):
            self._apply_row_highlight(
                self._availability_row_widgets,
                self._highlight_availability_id,
                "_highlight_availability_id",
            )

        year = date.today().year
        if hasattr(self, "_holiday_year_var"):
            try:
                year = int(self._holiday_year_var.get())
            except ValueError:
                year = date.today().year
        holidays = get_holidays(year)
        if not holidays:
            ctk.CTkLabel(
                self.holiday_list,
                text=f"No holidays configured for {year}.",
                text_color=UI_TEXT_MUTED,
                font=font("body"),
            ).pack(anchor="w", padx=8, pady=8)
        else:
            for h in holidays:
                row = ctk.CTkFrame(self.holiday_list, fg_color=UI_SURFACE, corner_radius=8)
                row.pack(fill="x", pady=3, padx=4)
                inner = ctk.CTkFrame(row, fg_color="transparent")
                inner.pack(fill="x", padx=12, pady=8)
                paid = "Paid" if h.get("is_paid") else "Unpaid"
                ctk.CTkLabel(
                    inner,
                    text=f"{format_date(h['holiday_date'])}  ·  {h['name']}  ·  {paid}",
                    font=font("body"),
                    anchor="w",
                ).pack(side="left", fill="x", expand=True)
                if self.can("holidays.manage"):
                    btn_row = ctk.CTkFrame(inner, fg_color="transparent")
                    btn_row.pack(side="right")
                    ctk.CTkButton(
                        btn_row,
                        text="Edit",
                        width=52,
                        height=28,
                        fg_color=DODGEVILLE_BLUE,
                        command=lambda hd=h: self._show_edit_holiday_dialog(hd),
                    ).pack(side="left", padx=(0, 4))
                    ctk.CTkButton(
                        btn_row,
                        text="✕",
                        width=32,
                        height=28,
                        fg_color=DODGEVILLE_DANGER,
                        command=lambda hid=h["id"]: self._delete_holiday(hid),
                    ).pack(side="left")

        if hasattr(self, "open_shift_list"):
            oid = self._linked_officer_id() if self._is_officer_role() else None
            shifts = get_open_shifts(officer_id=oid)
            open_count = len(shifts)
            if hasattr(self, "_open_shift_header"):
                subtitle = (
                    f"{open_count} shift(s) you can claim"
                    if self._is_officer_role() and open_count
                    else f"{open_count} open shift(s) posted"
                )
                self._open_shift_header.configure(subtitle=subtitle)
            if not shifts:
                empty = ctk.CTkFrame(self.open_shift_list, fg_color=UI_SURFACE, corner_radius=8)
                empty.pack(fill="x", pady=6, padx=4)
                ctk.CTkLabel(
                    empty,
                    text="No open shifts right now.",
                    font=font("body"),
                    text_color=UI_TEXT_MUTED,
                ).pack(anchor="w", padx=12, pady=(10, 4))
                if self.can("open_shifts.manage") and hasattr(self, "_open_shift_date"):
                    PrimaryButton(
                        empty,
                        text="Post Open Shift",
                        fg_color=DODGEVILLE_ACCENT,
                        command=lambda: self._open_shift_date.focus(),
                    ).pack(anchor="w", padx=12, pady=(0, 10))
            else:
                for shift in shifts:
                    row = ctk.CTkFrame(self.open_shift_list, fg_color=UI_SURFACE, corner_radius=8)
                    row.pack(fill="x", pady=3, padx=4)
                    inner = ctk.CTkFrame(row, fg_color="transparent")
                    inner.pack(fill="x", padx=12, pady=8)
                    left = ctk.CTkFrame(inner, fg_color="transparent")
                    left.pack(side="left", fill="x", expand=True)
                    badge_row = ctk.CTkFrame(left, fg_color="transparent")
                    badge_row.pack(fill="x")
                    status = shift.get("status") or "Open"
                    StatusBadge(badge_row, status).pack(side="left")
                    if shift.get("squad"):
                        StatusBadge(badge_row, f"Squad {shift['squad']}").pack(side="left", padx=(6, 0))
                    ctk.CTkLabel(
                        left,
                        text=f"{format_date(shift['shift_date'])}  ·  {shift['shift_start']}–{shift['shift_end']}",
                        font=font("body"),
                        anchor="w",
                    ).pack(fill="x", pady=(4, 0))
                    if shift.get("notes"):
                        ctk.CTkLabel(
                            left,
                            text=shift["notes"],
                            font=font("small"),
                            text_color=UI_TEXT_MUTED,
                            anchor="w",
                        ).pack(fill="x")
                    if self.can("open_shifts.claim") and status == "Open":
                        PrimaryButton(
                            inner,
                            text="Claim Shift",
                            width=110,
                            height=30,
                            fg_color=DODGEVILLE_SUCCESS,
                            command=lambda sid=shift["id"]: self._claim_open_shift(sid),
                        ).pack(side="right")
                    self._open_shift_row_widgets[shift["id"]] = row

        if getattr(self, "_highlight_open_shift_id", None):
            self._apply_row_highlight(
                self._open_shift_row_widgets,
                self._highlight_open_shift_id,
                "_highlight_open_shift_id",
            )

    def _delete_availability(self, entry_id: int):
        uid = self.current_user.get("id") if self.current_user else None
        result = delete_officer_availability(entry_id, user_id=uid)
        if result.get("success"):
            self.refresh_availability()
            self._refresh_dashboard_data()
        else:
            messagebox.showerror("Error", result.get("message"))

    def _delete_holiday(self, holiday_id: int):
        uid = self.current_user.get("id") if self.current_user else None
        result = delete_holiday(holiday_id, user_id=uid)
        if result.get("success"):
            self.refresh_availability()
            self._refresh_dashboard_data()
            self.set_status("Holiday removed")
        else:
            messagebox.showerror("Error", result.get("message"))
