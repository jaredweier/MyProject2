"""Day-off requests and shift swaps tab mixin."""

from tkinter import filedialog, messagebox

import customtkinter as ctk

from config import DATE_INPUT_HINT, DAY_OFF_REQUEST_TYPES, REQUEST_STATUS
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
    get_day_off_requests_for_viewer,
    get_officers_by_seniority,
    get_pending_day_off_requests,
    get_pending_shift_swap_requests,
    get_shift_swap_requests,
    is_officer_working_on_day,
    process_day_off_request,
    process_shift_swap,
    suggest_bump_chain,
    validate_swap_feasibility,
)
from ui.helpers import today_placeholder
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
from ui.widgets import (
    Card,
    CompactButton,
    CoverageBadge,
    FormField,
    PrimaryButton,
    SecondaryButton,
    SectionHeader,
    SegmentBar,
    StatusBadge,
)
from validators import format_date, format_datetime, parse_date


class RequestsPageMixin:
    def _build_requests(self):
        page = self.pages["requests"]
        page.grid_columnconfigure(0, weight=2)
        page.grid_columnconfigure(1, weight=3)
        page.grid_rowconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)

        form_card = Card(page)
        form_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        req_subtitle = (
            "Any request type. Submission does not guarantee approval."
            if self._is_officer_role()
            else "Submit on behalf of any officer"
        )
        SectionHeader(form_card.body, "New Request", req_subtitle).pack(fill="x", padx=CARD_PAD, pady=(CARD_PAD, 12))
        ff = ctk.CTkFrame(form_card.body, fg_color="transparent")
        ff.pack(fill="x", padx=CARD_PAD)
        self.req_officer = FormField(
            ff, "Officer", lambda p: ctk.CTkComboBox(p, height=36, values=["Loading..."])
        ).widget
        self.req_date = FormField(
            ff, "Date", lambda p: ctk.CTkEntry(p, height=36, placeholder_text=today_placeholder())
        ).widget
        self.req_date.bind("<KeyRelease>", lambda _e: self.preview_request_coverage())
        self.req_type = FormField(
            ff,
            "Request Type",
            lambda p: ctk.CTkComboBox(p, height=36, values=list(DAY_OFF_REQUEST_TYPES)),
        ).widget
        self.req_notes = FormField(ff, "Notes (optional)", lambda p: ctk.CTkEntry(p, height=36)).widget
        self.req_coverage_status = ctk.CTkLabel(
            ff, text="Coverage: not checked", font=font("small"), text_color=UI_TEXT_MUTED, anchor="w"
        )
        self.req_coverage_status.pack(fill="x", pady=(4, 0))
        self.req_bump_preview = ctk.CTkTextbox(
            ff,
            height=110,
            font=font("small"),
            fg_color=UI_BORDER,
            text_color=UI_TEXT_MUTED,
            activate_scrollbars=False,
        )
        self.req_bump_preview.pack(fill="x", pady=(4, 8))
        self.req_bump_preview.insert("1.0", "Coverage plan will appear here after preview.")
        self.req_bump_preview.configure(state="disabled")
        btn_row = ctk.CTkFrame(form_card.body, fg_color="transparent")
        btn_row.pack(fill="x", padx=CARD_PAD, pady=(0, 8))
        SecondaryButton(
            btn_row,
            text="Preview Coverage",
            command=self.preview_request_coverage,
        ).pack(side="left", fill="x", expand=True, padx=(0, 6))
        PrimaryButton(
            btn_row,
            text="Submit Request",
            fg_color=DODGEVILLE_SUCCESS,
            command=self.submit_request,
        ).pack(side="left", fill="x", expand=True, padx=(6, 0))
        self.req_officer_map = {}
        self._refresh_officer_dropdown()

        queue = Card(page)
        queue.grid(row=0, column=1, sticky="nsew")
        qhdr = ctk.CTkFrame(queue.body, fg_color="transparent")
        qhdr.pack(fill="x", padx=CARD_PAD, pady=(CARD_PAD, 6))
        SectionHeader(qhdr, "Request Queue").pack(side="left")
        actions = ctk.CTkFrame(qhdr, fg_color="transparent")
        actions.pack(side="right")
        if self.can("requests.approve"):
            CompactButton(
                actions,
                text="Bulk Approve",
                fg_color=DODGEVILLE_SUCCESS,
                command=self._bulk_approve_requests,
            ).pack(side="right", padx=(6, 0))
            CompactButton(
                actions,
                text="Bulk Reject",
                fg_color=DODGEVILLE_DANGER,
                command=self._bulk_reject_requests,
            ).pack(side="right", padx=(6, 0))
        if self.can("requests.approve") or self._is_officer_role():
            csv_label = "My CSV" if self._is_officer_role() else "CSV"
            CompactButton(
                actions,
                text=csv_label,
                fg_color=DODGEVILLE_GOLD,
                width=72,
                command=self._export_requests_csv_filtered,
            ).pack(side="right", padx=(6, 0))
        if self._is_officer_role():
            CompactButton(
                actions,
                text="My PDF",
                fg_color=DODGEVILLE_BLUE,
                width=72,
                command=self._export_requests_pdf_filtered,
            ).pack(side="right", padx=(6, 0))
        elif self.can("requests.approve"):
            CompactButton(
                actions,
                text="PDF",
                fg_color=DODGEVILLE_BLUE,
                width=64,
                command=self._export_requests_pdf_filtered,
            ).pack(side="right", padx=(6, 0))

        view_row = ctk.CTkFrame(queue.body, fg_color="transparent")
        view_row.pack(fill="x", padx=CARD_PAD, pady=(0, 8))
        view_row.grid_columnconfigure(0, weight=2)
        view_row.grid_columnconfigure(1, weight=3)
        segments = [("queue", "Queue"), ("history", "History")]
        if self.can("requests.approve"):
            segments.append(("review", "Needs Review"))
        self.req_view_bar = SegmentBar(view_row, on_select=self._set_request_view)
        self.req_view_bar.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.req_view_bar.set_segments(segments, "queue")

        filter_row = ctk.CTkFrame(view_row, fg_color="transparent")
        filter_row.grid(row=0, column=1, sticky="e")
        self.req_history_filter = ctk.CTkComboBox(
            filter_row,
            values=["All", REQUEST_STATUS["approved"], REQUEST_STATUS["rejected"], REQUEST_STATUS["pending_manual"]],
            width=160,
            height=30,
            command=lambda _: self.refresh_requests(),
        )
        self.req_history_filter.set("All")
        self.req_date_from = ctk.CTkEntry(filter_row, width=100, height=28, placeholder_text=DATE_INPUT_HINT)
        self.req_date_to = ctk.CTkEntry(filter_row, width=100, height=28, placeholder_text=DATE_INPUT_HINT)
        self.req_date_filter_btn = CompactButton(filter_row, text="Filter", width=64, command=self.refresh_requests)
        self.request_list = ctk.CTkScrollableFrame(queue.body, fg_color="transparent")
        self.request_list.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        ledger_card = Card(page)
        ledger_card.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        ledger_hdr = ctk.CTkFrame(ledger_card.body, fg_color="transparent")
        ledger_hdr.pack(fill="x", padx=CARD_PAD, pady=(CARD_PAD, 6))
        self._day_off_ledger_title = SectionHeader(
            ledger_hdr,
            "Day Off Requests",
            "Submitted requests with type and timestamp",
        )
        self._day_off_ledger_title.pack(side="left", fill="x", expand=True)
        self._ledger_type_filter = "All"
        self._ledger_status_filter = "All"
        self._ledger_chip_row = ctk.CTkFrame(ledger_card.body, fg_color="transparent")
        self._ledger_chip_row.pack(fill="x", padx=CARD_PAD, pady=(0, 4))
        self._ledger_chip_buttons = {}
        for label in ["All"] + list(DAY_OFF_REQUEST_TYPES):
            btn = ctk.CTkButton(
                self._ledger_chip_row,
                text=label,
                height=26,
                corner_radius=14,
                font=font("small"),
                fg_color=DODGEVILLE_ACCENT if label == "All" else UI_BORDER,
                command=lambda t=label: self._set_ledger_type_filter(t),
            )
            btn.pack(side="left", padx=(0, 6))
            self._ledger_chip_buttons[label] = btn
        self._ledger_status_chip_row = ctk.CTkFrame(ledger_card.body, fg_color="transparent")
        self._ledger_status_chip_row.pack(fill="x", padx=CARD_PAD, pady=(0, 6))
        self._ledger_status_chip_buttons = {}
        status_labels = ["All", "Pending", "Approved", "Mine"]
        for label in status_labels:
            btn = ctk.CTkButton(
                self._ledger_status_chip_row,
                text=label,
                height=26,
                corner_radius=14,
                font=font("small"),
                fg_color=DODGEVILLE_ACCENT if label == "All" else UI_BORDER,
                command=lambda s=label: self._set_ledger_status_filter(s),
            )
            btn.pack(side="left", padx=(0, 6))
            self._ledger_status_chip_buttons[label] = btn
        self.day_off_ledger_list = ctk.CTkScrollableFrame(ledger_card.body, fg_color="transparent", height=220)
        self.day_off_ledger_list.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._day_off_ledger_header = ctk.CTkFrame(ledger_card.body, fg_color=UI_BORDER, corner_radius=8)
        self._day_off_ledger_header.pack(fill="x", padx=CARD_PAD, pady=(0, 6))
        ledger_cols = ctk.CTkFrame(self._day_off_ledger_header, fg_color="transparent")
        ledger_cols.pack(fill="x", padx=12, pady=8)
        for col, (text, width) in enumerate(
            [
                ("Submitted", 130),
                ("Employee", 160),
                ("Type", 110),
                ("Date Off", 100),
                ("Status", 120),
            ]
        ):
            ctk.CTkLabel(
                ledger_cols,
                text=text,
                width=width,
                anchor="w",
                font=font("small"),
                text_color=UI_TEXT_MUTED,
            ).grid(row=0, column=col, padx=2, sticky="w")
        self.refresh_day_off_request_ledger()

    def _refresh_officer_dropdown(self):
        if getattr(self, "_shell_building", False):
            return
        officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
        if self._is_officer_role():
            oid = self._linked_officer_id()
            officers = [o for o in officers if o["id"] == oid] if oid else []
        labels = [f"{o['name']}  ·  Squad {o['squad']}  ·  {o['shift_start']}" for o in officers]
        self.req_officer_map = {lbl: o["id"] for lbl, o in zip(labels, officers)}
        self.req_officer.configure(values=labels or ["No active officers"])
        if self._is_officer_role() and labels:
            self.req_officer.configure(state="disabled")
        else:
            self.req_officer.configure(state="normal")
        if labels:
            self.req_officer.set(labels[0])

    def _set_request_view(self, view: str):
        self._request_view = view
        if hasattr(self, "req_view_bar"):
            self.req_view_bar.set_active(view)
        if view == "history":
            self.req_history_filter.pack(side="left", padx=(0, 6))
            self.req_date_from.pack(side="left", padx=(0, 4))
            self.req_date_to.pack(side="left", padx=(0, 4))
            self.req_date_filter_btn.pack(side="left")
        else:
            self.req_history_filter.pack_forget()
            self.req_date_from.pack_forget()
            self.req_date_to.pack_forget()
            self.req_date_filter_btn.pack_forget()
        for row in self._request_row_widgets.values():
            row.destroy()
        self._request_row_widgets = {}
        self.refresh_requests()

    def _display_bump_suggestion(self, suggestion, status_label=None, textbox=None, hint_prefix=None):
        label = status_label or self.req_coverage_status
        box = textbox or self.req_bump_preview
        if suggestion.success:
            status = "Coverage: auto approve possible if supervisor approves"
            color = DODGEVILLE_SUCCESS
        else:
            status = "Coverage: Supervisor review likely"
            color = DODGEVILLE_WARNING
        if hint_prefix:
            status = f"{hint_prefix} · {status}"
        label.configure(text=status, text_color=color)
        body = format_bump_suggestion(suggestion)
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", body)
        box.configure(state="disabled")

    def preview_request_coverage(self):
        officer_id = self.req_officer_map.get(self.req_officer.get())
        request_date = self.req_date.get().strip()
        if not officer_id or not request_date:
            return
        try:
            parse_date(request_date)
        except ValueError:
            self.req_coverage_status.configure(
                text=f"Date must be {DATE_INPUT_HINT}",
                text_color=DODGEVILLE_DANGER,
            )
            return
        context = describe_day_off_request(officer_id, request_date)
        if not context.get("success"):
            return
        hints = [context.get("summary", "")]
        if not context.get("on_rotation"):
            hints.insert(0, "Off rotation day. You may still submit.")
        if context.get("unavailable"):
            hints.insert(0, "Blackout on file. Supervisor will review.")
        hint_text = " · ".join(h for h in hints if h)
        suggestion = context.get("suggestion")
        if suggestion:
            self._display_bump_suggestion(suggestion, hint_prefix=hint_text)
        else:
            self.req_coverage_status.configure(text=hint_text, text_color=UI_TEXT_MUTED)

    def submit_request(self):
        if not self.can("requests.submit"):
            messagebox.showwarning("Permission", "You cannot submit time off requests.")
            return
        if not self.req_officer_map:
            messagebox.showerror("Error", "No active officers available.")
            return
        officer_id = self.req_officer_map.get(self.req_officer.get())
        if self._is_officer_role():
            linked = self._linked_officer_id()
            if not linked or officer_id != linked:
                messagebox.showwarning("Permission", "Officers may only submit requests for themselves.")
                return
        request_date = self.req_date.get().strip()
        try:
            parse_date(request_date)
        except ValueError:
            messagebox.showerror("Validation", f"Date must be {DATE_INPUT_HINT}.")
            return
        result = create_day_off_request(officer_id, request_date, self.req_type.get(), self.req_notes.get().strip())
        if result.get("success"):
            self.req_notes.delete(0, "end")
            messagebox.showinfo(
                "Request Submitted",
                "Your request was sent to supervisors for review. You will be notified when it is approved or denied.",
            )
            self.refresh_day_off_request_ledger(force=True)
            self.refresh_requests()
            self.refresh_notifications()
            self._update_notification_badge()
            self._refresh_dashboard_data()
            self.set_status(f"Request #{result['request_id']} submitted")
        else:
            messagebox.showerror("Cannot Submit", result.get("message", "Submit failed."))

    def _render_request_row(self, parent, req, compact=False, show_actions=None):
        row = ctk.CTkFrame(parent, fg_color=UI_SURFACE, corner_radius=8)
        if compact:
            row.pack(fill="x", pady=4, padx=4)
        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=10)
        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text=req["officer_name"], font=font("subheading"), anchor="w").pack(side="left")
        badges = ctk.CTkFrame(top, fg_color="transparent")
        badges.pack(side="right")
        if req["status"] == "Pending Manual Review":
            CoverageBadge(badges, auto_ok=False).pack(side="right", padx=(0, 6))
        StatusBadge(badges, req["status"]).pack(side="right")
        try:
            on_rotation = is_officer_working_on_day(
                req["officer_id"],
                parse_date(req["request_date"]),
            )
        except ValueError:
            on_rotation = True
        rotation_note = "" if on_rotation else "  ·  Off rotation"
        submitted = format_datetime(req.get("created_at"))
        submitted_line = f"Submitted {submitted}" if submitted else ""
        detail = (
            f"{format_date(req['request_date'])}  ·  {req['request_type']}  ·  "
            f"Squad {req['squad']} ({req['shift_start']}–{req['shift_end']}){rotation_note}"
        )
        ctk.CTkLabel(inner, text=detail, font=font("small"), text_color=UI_TEXT_MUTED, anchor="w").pack(
            fill="x", pady=(4, 0)
        )
        if submitted_line:
            ctk.CTkLabel(
                inner,
                text=submitted_line,
                font=font("small"),
                text_color=UI_TEXT_MUTED,
                anchor="w",
            ).pack(fill="x")
        if req.get("notes"):
            ctk.CTkLabel(
                inner, text=f"Notes: {req['notes']}", font=font("small"), text_color=UI_TEXT_MUTED, anchor="w"
            ).pack(fill="x")
        if req.get("admin_notes"):
            ctk.CTkLabel(
                inner, text=f"Admin: {req['admin_notes']}", font=font("small"), text_color=UI_TEXT_MUTED, anchor="w"
            ).pack(fill="x")
        if show_actions is None:
            show_actions = not compact
        if show_actions and req["status"] in ("Pending", "Pending Manual Review"):
            btns = ctk.CTkFrame(inner, fg_color="transparent")
            btns.pack(fill="x", pady=(8, 0))
            ctk.CTkButton(
                btns,
                text="Preview",
                width=80,
                height=28,
                corner_radius=6,
                fg_color=UI_BORDER,
                command=lambda r=req: self._show_request_bump_preview(r),
            ).pack(side="right", padx=(4, 0))
            if self.can("requests.approve"):
                ctk.CTkButton(
                    btns,
                    text="Approve",
                    width=80,
                    height=28,
                    corner_radius=6,
                    fg_color=DODGEVILLE_SUCCESS,
                    command=lambda r=req: self._confirm_approve_request(r),
                ).pack(side="right", padx=(4, 0))
            if self.can("requests.approve"):
                ctk.CTkButton(
                    btns,
                    text="Reject",
                    width=80,
                    height=28,
                    corner_radius=6,
                    fg_color=DODGEVILLE_DANGER,
                    command=lambda rid=req["id"]: self.handle_request(rid, "reject"),
                ).pack(side="right")
        return row

    def _show_request_bump_preview(self, req):
        suggestion = suggest_bump_chain(req["officer_id"], req["request_date"], req["squad"], req["shift_start"])
        messagebox.showinfo("Coverage Plan", format_bump_suggestion(suggestion))

    def _set_ledger_type_filter(self, label: str):
        self._ledger_type_filter = label
        for chip_label, btn in getattr(self, "_ledger_chip_buttons", {}).items():
            btn.configure(
                fg_color=DODGEVILLE_ACCENT if chip_label == label else UI_BORDER,
            )
        self.refresh_day_off_request_ledger(force=True)

    def _set_ledger_status_filter(self, label: str):
        self._ledger_status_filter = label
        for chip_label, btn in getattr(self, "_ledger_status_chip_buttons", {}).items():
            btn.configure(
                fg_color=DODGEVILLE_ACCENT if chip_label == label else UI_BORDER,
            )
        self.refresh_day_off_request_ledger(force=True)

    def _confirm_approve_request(self, req):
        suggestion = suggest_bump_chain(
            req["officer_id"],
            req["request_date"],
            req["squad"],
            req["shift_start"],
        )
        summary = format_bump_suggestion(suggestion)
        officer_name = req.get("officer_name") or "Officer"
        manual_note = ""
        if suggestion.get("requires_manual"):
            manual_note = "\n\nThis request may route to manual review if no on-duty replacement is found."
        prompt = (
            f"Approve {req.get('request_type', 'time off')} for {officer_name} "
            f"on {format_date(req['request_date'])}?\n\n{summary}{manual_note}"
        )
        if messagebox.askyesno("Approve Request", prompt):
            self.handle_request(req["id"], "approve")

    def refresh_day_off_request_ledger(self, force: bool = False):
        if not hasattr(self, "day_off_ledger_list"):
            return
        role = self.current_user.get("role") if self.current_user else ""
        linked_id = self._linked_officer_id()
        data = get_day_off_requests_for_viewer(role, linked_officer_id=linked_id)
        requests = data.get("requests") or []
        if getattr(self, "_ledger_type_filter", "All") != "All":
            requests = [r for r in requests if r.get("request_type") == self._ledger_type_filter]
        status_filter = getattr(self, "_ledger_status_filter", "All")
        if status_filter == "Pending":
            requests = [
                r
                for r in requests
                if r.get("status")
                in (
                    REQUEST_STATUS["pending"],
                    REQUEST_STATUS["pending_manual"],
                )
            ]
        elif status_filter == "Approved":
            requests = [r for r in requests if r.get("status") == REQUEST_STATUS["approved"]]
        elif status_filter == "Mine" and linked_id:
            requests = [r for r in requests if r.get("officer_id") == linked_id]
        signature = (
            data.get("success"),
            tuple((r.get("id"), r.get("status"), r.get("created_at")) for r in requests),
        )
        if not force and signature == getattr(self, "_day_off_ledger_signature", None):
            return
        self._day_off_ledger_signature = signature
        for child in self.day_off_ledger_list.winfo_children():
            child.destroy()
        if self._is_officer_role():
            title = "My Day Off Requests"
            subtitle = "Your submitted requests with type and timestamp"
        else:
            title = "Employee Day Off Requests"
            subtitle = "All employee requests with type and submission timestamp"
        self._day_off_ledger_title.configure(title=title, subtitle=subtitle)
        if not data.get("success"):
            ctk.CTkLabel(
                self.day_off_ledger_list,
                text=data.get("message", "Unable to load requests"),
                font=font("body"),
                text_color=UI_TEXT_MUTED,
            ).pack(pady=16)
            return
        if not requests:
            empty = (
                "You have not submitted any day off requests yet."
                if self._is_officer_role()
                else ("No day off requests on file.")
            )
            ctk.CTkLabel(
                self.day_off_ledger_list,
                text=empty,
                font=font("body"),
                text_color=UI_TEXT_MUTED,
            ).pack(pady=16)
            return
        linked_id = self._linked_officer_id() if self._is_officer_role() else None
        for req in requests:
            is_self = linked_id and req.get("officer_id") == linked_id
            row = ctk.CTkFrame(
                self.day_off_ledger_list,
                fg_color=UI_SURFACE,
                corner_radius=8,
                border_width=2 if is_self else 0,
                border_color=DODGEVILLE_GOLD if is_self else UI_SURFACE,
            )
            row.pack(fill="x", pady=3)
            inner = ctk.CTkFrame(row, fg_color="transparent")
            inner.pack(fill="x", padx=12, pady=8)
            ctk.CTkLabel(
                inner,
                text=format_datetime(req.get("created_at")) or "—",
                width=130,
                anchor="w",
                font=font("small"),
                text_color=UI_TEXT_MUTED,
            ).grid(row=0, column=0, padx=2, sticky="w")
            ctk.CTkLabel(
                inner,
                text=req.get("officer_name") or "—",
                width=160,
                anchor="w",
                font=font("subheading"),
                text_color=DODGEVILLE_GOLD if is_self else None,
            ).grid(row=0, column=1, padx=2, sticky="w")
            ctk.CTkLabel(
                inner,
                text=req.get("request_type") or "—",
                width=110,
                anchor="w",
                font=font("body"),
            ).grid(row=0, column=2, padx=2, sticky="w")
            ctk.CTkLabel(
                inner,
                text=format_date(req.get("request_date")) or "—",
                width=100,
                anchor="w",
                font=font("body"),
            ).grid(row=0, column=3, padx=2, sticky="w")
            badge_host = ctk.CTkFrame(inner, fg_color="transparent", width=120)
            badge_host.grid(row=0, column=4, padx=2, sticky="w")
            StatusBadge(badge_host, req.get("status") or "Pending").pack(anchor="w")

    def refresh_requests(self):
        self.refresh_day_off_request_ledger()
        if self._request_view == "history":
            filt = self.req_history_filter.get()
            status = None if filt == "All" else filt
            date_from = self.req_date_from.get().strip() or None
            date_to = self.req_date_to.get().strip() or None
            requests = get_day_off_requests(
                status_filter=status,
                date_from=date_from,
                date_to=date_to,
            )
        elif self._request_view == "review":
            requests = get_day_off_requests(status_filter=REQUEST_STATUS["pending_manual"])
        else:
            requests = get_pending_day_off_requests()
        if self._is_officer_role():
            oid = self._linked_officer_id()
            if oid:
                requests = [r for r in requests if r["officer_id"] == oid]
        pending_ids = {req["id"] for req in requests}

        for request_id, row in list(self._request_row_widgets.items()):
            if request_id not in pending_ids:
                row.destroy()
                del self._request_row_widgets[request_id]

        for widget in self.request_list.winfo_children():
            if widget not in self._request_row_widgets.values():
                widget.destroy()

        if not requests:
            if self._request_view == "history":
                empty = "No requests in history."
            elif self._is_officer_role():
                empty = "No pending requests. Submit time off from the form above."
            else:
                empty = "Queue is clear — no pending time-off requests."
            ctk.CTkLabel(
                self.request_list,
                text=empty,
                text_color=UI_TEXT_MUTED,
                font=font("body"),
            ).pack(pady=20)
            return

        for req in requests:
            row = self._request_row_widgets.get(req["id"])
            if row is None:
                row = self._render_request_row(
                    self.request_list,
                    req,
                    show_actions=(self._request_view == "queue" and self.can("requests.approve")),
                )
                self._request_row_widgets[req["id"]] = row
            row.pack_forget()

        for req in requests:
            self._request_row_widgets[req["id"]].pack(fill="x", pady=4)
        self._apply_row_highlight(
            self._request_row_widgets,
            self._highlight_request_id,
            "_highlight_request_id",
        )

    def _focus_availability_row(self, entry_id: int):
        self._apply_row_highlight(
            self._availability_row_widgets,
            entry_id,
            "_highlight_availability_id",
        )

    def _apply_row_highlight(self, widget_map, item_id, attr_name):
        if not item_id or item_id not in widget_map:
            setattr(self, attr_name, None)
            return
        row = widget_map[item_id]
        row.configure(border_width=2, border_color=DODGEVILLE_GOLD)
        setattr(self, attr_name, None)
        self.root.after(4000, lambda r=row: r.configure(border_width=0))

    def _request_export_filters(self):
        status = None
        date_from = None
        date_to = None
        if self._request_view == "history":
            filt = self.req_history_filter.get()
            status = None if filt == "All" else filt
            date_from = self.req_date_from.get().strip() or None
            date_to = self.req_date_to.get().strip() or None
        elif self._request_view == "review":
            status = REQUEST_STATUS["pending_manual"]
        return status, date_from, date_to

    def _export_requests_pdf(self):
        if not (self.can("reports.export") or self.can("requests.approve") or self._is_officer_role()):
            return
        officer_id = self._linked_officer_id() if self._is_officer_role() else None
        self._export_pdf_result(
            export_requests_pdf(officer_id=officer_id),
            "Requests PDF",
        )

    def _export_requests_pdf_filtered(self):
        if not (self.can("requests.approve") or self._is_officer_role()):
            return
        status, date_from, date_to = self._request_export_filters()
        officer_id = self._linked_officer_id() if self._is_officer_role() else None
        self._export_pdf_result(
            export_requests_pdf(
                status_filter=status,
                date_from=date_from,
                date_to=date_to,
                officer_id=officer_id,
            ),
            "Requests PDF",
        )

    def _export_requests_csv_filtered(self):
        if not (self.can("reports.export") or self._is_officer_role()):
            return
        status, date_from, date_to = self._request_export_filters()
        officer_id = self._linked_officer_id() if self._is_officer_role() else None
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        result = export_requests_csv(
            status_filter=status,
            date_from=date_from,
            date_to=date_to,
            officer_id=officer_id,
            output_path=path,
        )
        if result.get("success"):
            messagebox.showinfo(
                "Export",
                f"Requests exported ({result['count']} rows)\n{result['path']}",
            )
            self.set_status("Requests CSV exported")
        else:
            messagebox.showerror("Export Failed", result.get("message", "Unknown error"))

    def _bulk_approve_requests(self):
        if not self.can("requests.approve"):
            return
        if not messagebox.askyesno(
            "Bulk Approve",
            "Approve all pending requests with automatic bump coverage?\n"
            "Requests needing manual review will be skipped.",
        ):
            return
        result = bulk_approve_auto_ok_requests()
        messagebox.showinfo("Bulk Approve", result.get("message", "Done"))
        if result.get("failed"):
            messagebox.showwarning("Partial Failures", "\n".join(result["failed"][:5]))
        from ui.helpers import refresh_after_schedule_change

        self.refresh_day_off_request_ledger(force=True)
        self.refresh_requests()
        self.refresh_notifications()
        refresh_after_schedule_change(self)

    def _bulk_reject_requests(self):
        if not self.can("requests.approve"):
            return
        if not messagebox.askyesno(
            "Bulk Reject",
            "Reject all standard pending requests?\nRequests needing manual review will be skipped.",
        ):
            return
        result = bulk_reject_pending_requests()
        messagebox.showinfo("Bulk Reject", result.get("message", "Done"))
        if result.get("failed"):
            messagebox.showwarning("Partial Failures", "\n".join(result["failed"][:5]))
        self.refresh_day_off_request_ledger(force=True)
        self.refresh_requests()
        self.refresh_notifications()
        self._refresh_dashboard_data()
        if self.current_page == "dashboard":
            self._refresh_dashboard()

    def handle_request(self, request_id, action):
        result = process_day_off_request(request_id, action=action)
        if result.success:
            self.set_status(result.message)
        elif result.requires_manual:
            self.set_status(f"Manual review: {result.message}")
            messagebox.showinfo("Manual Review", result.message)
        else:
            messagebox.showwarning("Action Failed", result.message)
        from ui.helpers import refresh_after_schedule_change

        self.refresh_day_off_request_ledger(force=True)
        self.refresh_requests()
        self.refresh_notifications()
        self._update_notification_badge()
        refresh_after_schedule_change(self)

    # ── Shift Swaps ────────────────────────────────────────────────────
    def _build_swaps(self):
        page = self.pages["swaps"]
        page.grid_columnconfigure(0, weight=2)
        page.grid_columnconfigure(1, weight=3)
        page.grid_rowconfigure(0, weight=1)

        form_card = Card(page)
        form_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        SectionHeader(form_card.body, "New Swap Request", "Exchange shifts for one day").pack(
            fill="x", padx=CARD_PAD, pady=(CARD_PAD, 12)
        )
        sf = ctk.CTkFrame(form_card.body, fg_color="transparent")
        sf.pack(fill="x", padx=CARD_PAD)
        self.swap_officer1 = FormField(
            sf, "Officer 1", lambda p: ctk.CTkComboBox(p, height=36, values=["Loading..."])
        ).widget
        self.swap_officer2 = FormField(
            sf, "Officer 2", lambda p: ctk.CTkComboBox(p, height=36, values=["Loading..."])
        ).widget
        self.swap_date = FormField(
            sf, "Swap Date", lambda p: ctk.CTkEntry(p, height=36, placeholder_text=today_placeholder())
        ).widget
        self.swap_preview = ctk.CTkLabel(
            sf, text="Validation: not checked", font=font("small"), text_color=UI_TEXT_MUTED, anchor="w", wraplength=320
        )
        self.swap_preview.pack(fill="x", pady=(4, 8))
        sbtn = ctk.CTkFrame(form_card.body, fg_color="transparent")
        sbtn.pack(fill="x", padx=CARD_PAD, pady=(0, CARD_PAD))
        SecondaryButton(sbtn, text="Validate", command=self.preview_swap).pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 6),
        )
        PrimaryButton(
            sbtn,
            text="Submit Swap",
            fg_color=DODGEVILLE_SUCCESS,
            command=self.submit_swap,
        ).pack(side="left", fill="x", expand=True, padx=(6, 0))
        self.swap_officer_map = {}

        list_card = Card(page)
        list_card.grid(row=0, column=1, sticky="nsew")
        shdr = ctk.CTkFrame(list_card.body, fg_color="transparent")
        shdr.pack(fill="x", padx=CARD_PAD, pady=(CARD_PAD, 6))
        SectionHeader(shdr, "Swap Queue").pack(side="left")
        swap_actions = ctk.CTkFrame(shdr, fg_color="transparent")
        swap_actions.pack(side="right")
        if self.can("swaps.approve") or self._is_officer_role():
            swap_csv_label = "My CSV" if self._is_officer_role() else "CSV"
            CompactButton(
                swap_actions,
                text=swap_csv_label,
                fg_color=DODGEVILLE_GOLD,
                width=72,
                command=self._export_swaps_csv_filtered,
            ).pack(side="right", padx=(6, 0))
        if self.can("swaps.approve"):
            CompactButton(
                swap_actions,
                text="PDF",
                fg_color=DODGEVILLE_BLUE,
                width=64,
                command=self._export_swaps_pdf_filtered,
            ).pack(side="right", padx=(6, 0))

        filter_row = ctk.CTkFrame(list_card.body, fg_color="transparent")
        filter_row.pack(fill="x", padx=CARD_PAD, pady=(0, 8))
        self.swap_filter = ctk.CTkComboBox(
            filter_row,
            values=["Pending", "Manual Review", "Approved", "Rejected", "All"],
            width=140,
            height=30,
            command=lambda _: self.refresh_swaps(),
        )
        self.swap_filter.set("Pending")
        self.swap_filter.pack(side="left", padx=(0, 8))
        self.swap_date_from = ctk.CTkEntry(filter_row, width=100, height=28, placeholder_text=DATE_INPUT_HINT)
        self.swap_date_from.pack(side="left", padx=(0, 4))
        self.swap_date_to = ctk.CTkEntry(filter_row, width=100, height=28, placeholder_text=DATE_INPUT_HINT)
        self.swap_date_to.pack(side="left", padx=(0, 4))
        CompactButton(filter_row, text="Apply", width=64, command=self.refresh_swaps).pack(side="left")
        self.swap_list = ctk.CTkScrollableFrame(list_card.body, fg_color="transparent")
        self.swap_list.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._refresh_swap_officer_dropdowns()

    def _refresh_swap_officer_dropdowns(self):
        officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
        if self._is_officer_role():
            oid = self._linked_officer_id()
            self_officer = next((o for o in officers if o["id"] == oid), None)
            officers_for_o2 = [o for o in officers if o["id"] != oid]
            labels = [f"{o['name']}  ·  {o['shift_start']}–{o['shift_end']}" for o in officers]
            self.swap_officer_map = {lbl: o["id"] for lbl, o in zip(labels, officers)}
            if self_officer:
                o1_label = f"{self_officer['name']}  ·  {self_officer['shift_start']}–{self_officer['shift_end']}"
                o2_labels = [f"{o['name']}  ·  {o['shift_start']}–{o['shift_end']}" for o in officers_for_o2]
                self.swap_officer1.configure(values=[o1_label])
                self.swap_officer1.set(o1_label)
                self.swap_officer1.configure(state="disabled")
                self.swap_officer2.configure(values=o2_labels or ["No other officers"])
                if o2_labels:
                    self.swap_officer2.set(o2_labels[0])
            return
        labels = [f"{o['name']}  ·  {o['shift_start']}–{o['shift_end']}" for o in officers]
        self.swap_officer_map = {lbl: o["id"] for lbl, o in zip(labels, officers)}
        self.swap_officer1.configure(state="normal")
        for combo in (self.swap_officer1, self.swap_officer2):
            combo.configure(values=labels or ["No active officers"])
        if len(labels) >= 2:
            self.swap_officer1.set(labels[0])
            self.swap_officer2.set(labels[1])
        elif labels:
            self.swap_officer1.set(labels[0])

    def preview_swap(self):
        o1 = self.swap_officer_map.get(self.swap_officer1.get())
        o2 = self.swap_officer_map.get(self.swap_officer2.get())
        swap_date = self.swap_date.get().strip()
        if not o1 or not o2:
            return
        result = validate_swap_feasibility(o1, o2, swap_date)
        if result.success:
            text = "Swap is valid. Both officers working, no conflicts."
        elif result.requires_manual:
            text = f"Manual review: {result.message}"
        else:
            text = result.message
        self.swap_preview.configure(text=f"Validation: {text}")

    def submit_swap(self):
        if not self.can("swaps.submit"):
            messagebox.showwarning("Permission", "You cannot submit shift swaps.")
            return
        o1 = self.swap_officer_map.get(self.swap_officer1.get())
        o2 = self.swap_officer_map.get(self.swap_officer2.get())
        swap_date = self.swap_date.get().strip()
        if self._is_officer_role():
            linked = self._linked_officer_id()
            if linked and linked not in (o1, o2):
                messagebox.showwarning("Permission", "Officers must be party to their swap requests.")
                return
        if not o1 or not o2:
            messagebox.showerror("Error", "Select both officers.")
            return
        result = create_shift_swap_request(o1, o2, swap_date)
        if result.get("success"):
            self.refresh_swaps()
            self.refresh_notifications()
            self._update_notification_badge()
            self.set_status(f"Swap request #{result['swap_id']} submitted")
        elif result.get("requires_manual"):
            messagebox.showinfo("Manual Review", result.get("message", "Requires supervisor review"))
        else:
            messagebox.showerror("Cannot Submit", result.get("message", "Submit failed."))

    def handle_swap(self, swap_id, action):
        result = process_shift_swap(swap_id, action=action)
        if result.success:
            self.set_status(result.message)
        elif result.requires_manual:
            messagebox.showinfo("Manual Review", result.message)
        else:
            messagebox.showwarning("Action Failed", result.message)
        from ui.helpers import refresh_after_schedule_change

        self.refresh_swaps()
        self.refresh_notifications()
        refresh_after_schedule_change(self)

    def refresh_swaps(self):
        filt = self.swap_filter.get()
        date_from = self.swap_date_from.get().strip() if hasattr(self, "swap_date_from") else ""
        date_to = self.swap_date_to.get().strip() if hasattr(self, "swap_date_to") else ""
        date_from = date_from or None
        date_to = date_to or None
        if filt == "All":
            swaps = get_shift_swap_requests(date_from=date_from, date_to=date_to)
        elif filt == "Pending":
            swaps = get_pending_shift_swap_requests(date_from=date_from, date_to=date_to)
        elif filt == "Manual Review":
            swaps = get_shift_swap_requests(
                status_filter="Pending Manual Review",
                date_from=date_from,
                date_to=date_to,
            )
        else:
            swaps = get_shift_swap_requests(
                status_filter=filt,
                date_from=date_from,
                date_to=date_to,
            )
        if self._is_officer_role():
            oid = self._linked_officer_id()
            if oid:
                swaps = [s for s in swaps if s["officer1_id"] == oid or s["officer2_id"] == oid]
        swap_ids = {s["id"] for s in swaps}
        for swap_id, row in list(self._swap_row_widgets.items()):
            if swap_id not in swap_ids:
                row.destroy()
                del self._swap_row_widgets[swap_id]
        for widget in self.swap_list.winfo_children():
            if widget not in self._swap_row_widgets.values():
                widget.destroy()
        if not swaps:
            ctk.CTkLabel(
                self.swap_list,
                text="No swap requests.",
                text_color=UI_TEXT_MUTED,
                font=font("body"),
            ).pack(pady=20)
            return
        for swap in swaps:
            row = self._swap_row_widgets.get(swap["id"])
            if row is None:
                row = ctk.CTkFrame(self.swap_list, fg_color=UI_SURFACE, corner_radius=8)
                inner = ctk.CTkFrame(row, fg_color="transparent")
                inner.pack(fill="x", padx=12, pady=10)
                top = ctk.CTkFrame(inner, fg_color="transparent")
                top.pack(fill="x")
                ctk.CTkLabel(
                    top,
                    text=f"{swap['officer1_name']} ⇄ {swap['officer2_name']}",
                    font=font("subheading"),
                    anchor="w",
                ).pack(side="left")
                StatusBadge(top, swap["status"]).pack(side="right")
                detail = f"{format_date(swap['swap_date'])}  ·  {swap['officer1_shift']} ↔ {swap['officer2_shift']}"
                ctk.CTkLabel(inner, text=detail, font=font("small"), text_color=UI_TEXT_MUTED, anchor="w").pack(
                    fill="x", pady=(4, 0)
                )
                if swap["status"] in ("Pending", "Pending Manual Review") and self.can("swaps.approve"):
                    btns = ctk.CTkFrame(inner, fg_color="transparent")
                    btns.pack(fill="x", pady=(8, 0))
                    ctk.CTkButton(
                        btns,
                        text="Approve",
                        width=80,
                        height=28,
                        corner_radius=6,
                        fg_color=DODGEVILLE_SUCCESS,
                        command=lambda sid=swap["id"]: self.handle_swap(sid, "approve"),
                    ).pack(side="right", padx=(4, 0))
                    ctk.CTkButton(
                        btns,
                        text="Reject",
                        width=80,
                        height=28,
                        corner_radius=6,
                        fg_color=DODGEVILLE_DANGER,
                        command=lambda sid=swap["id"]: self.handle_swap(sid, "reject"),
                    ).pack(side="right")
                self._swap_row_widgets[swap["id"]] = row
            row.pack_forget()
        for swap in swaps:
            self._swap_row_widgets[swap["id"]].pack(fill="x", pady=4)
        self._apply_row_highlight(
            self._swap_row_widgets,
            self._highlight_swap_id,
            "_highlight_swap_id",
        )

    def _swap_export_filters(self):
        filt = self.swap_filter.get()
        date_from = self.swap_date_from.get().strip() if hasattr(self, "swap_date_from") else ""
        date_to = self.swap_date_to.get().strip() if hasattr(self, "swap_date_to") else ""
        date_from = date_from or None
        date_to = date_to or None
        status = None
        pending_only = False
        if filt == "Pending":
            pending_only = True
        elif filt == "Manual Review":
            status = "Pending Manual Review"
        elif filt != "All":
            status = filt
        return status, date_from, date_to, pending_only

    def _export_swaps_csv_filtered(self):
        if not (self.can("reports.export") or self._is_officer_role()):
            return
        status, date_from, date_to, pending_only = self._swap_export_filters()
        officer_id = self._linked_officer_id() if self._is_officer_role() else None
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        result = export_shift_swaps_csv(
            status_filter=status,
            date_from=date_from,
            date_to=date_to,
            officer_id=officer_id,
            pending_only=pending_only,
            output_path=path,
        )
        if result.get("success"):
            messagebox.showinfo(
                "Export",
                f"Shift swaps exported ({result['count']} rows)\n{result['path']}",
            )
            self.set_status("Shift swaps CSV exported")
        else:
            messagebox.showerror("Export Failed", result.get("message", "Unknown error"))

    def _export_swaps_pdf_filtered(self):
        if not self.can("swaps.approve"):
            return
        status, date_from, date_to, pending_only = self._swap_export_filters()
        self._export_pdf_result(
            export_shift_swaps_pdf(
                status_filter=status,
                date_from=date_from,
                date_to=date_to,
                pending_only=pending_only,
            ),
            "Shift Swaps PDF",
        )
