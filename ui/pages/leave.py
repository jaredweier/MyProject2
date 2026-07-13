"""Time off + shift exchange — coverage-first leave workflows."""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from config import DATE_INPUT_HINT, DAY_OFF_REQUEST_TYPES, REQUEST_STATUS
from logic import (
    create_day_off_request,
    create_shift_swap_request,
    describe_day_off_request,
    format_bump_suggestion,
    get_day_off_requests_for_viewer,
    get_officers_by_seniority,
    get_pending_day_off_requests,
    get_pending_shift_swap_requests,
    get_shift_swap_requests,
    preview_best_coverage_plans,
    process_day_off_request,
    process_shift_swap,
    suggest_bump_chain,
    validate_swap_feasibility,
)
from ui.helpers import today_placeholder
from ui.pages.base import BasePage
from ui.theme import (
    CARD_PAD,
    DODGEVILLE_DANGER,
    DODGEVILLE_SUCCESS,
    DODGEVILLE_WARNING,
    UI_BORDER,
    UI_SURFACE,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    font,
)
from ui.widgets import (
    Card,
    CompactButton,
    DangerButton,
    EmptyState,
    FormField,
    PrimaryButton,
    SecondaryButton,
    SectionHeader,
    StatusBadge,
)
from validators import format_date, parse_date


class RequestsPage(BasePage):
    page_key = "requests"

    def build(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=3)

        form = Card(self, accent=True)
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        form.body.grid_rowconfigure(1, weight=1)
        SectionHeader(
            form.body,
            "New request",
            "Submit on behalf of any officer" if not self.is_officer() else "Your time-off request",
        ).pack(fill="x", padx=CARD_PAD, pady=(CARD_PAD, 12))
        ff = ctk.CTkScrollableFrame(form.body, fg_color="transparent")
        ff.pack(fill="both", expand=True, padx=CARD_PAD)
        self.req_officer = FormField(
            ff, "Officer", lambda p: ctk.CTkComboBox(p, height=36, values=["Loading..."])
        ).widget
        self.req_date = FormField(
            ff, "Date", lambda p: ctk.CTkEntry(p, height=36, placeholder_text=today_placeholder())
        ).widget
        self.req_type = FormField(
            ff, "Request type", lambda p: ctk.CTkComboBox(p, height=36, values=list(DAY_OFF_REQUEST_TYPES))
        ).widget
        self.req_notes = FormField(ff, "Notes (optional)", lambda p: ctk.CTkEntry(p, height=36)).widget
        self.req_coverage_status = ctk.CTkLabel(
            ff, text="Coverage: not checked", font=font("small"), text_color=UI_TEXT_MUTED, anchor="w"
        )
        self.req_coverage_status.pack(fill="x", pady=(4, 0))
        self.req_bump_preview = ctk.CTkTextbox(
            ff,
            height=100,
            font=font("small"),
            fg_color=UI_SURFACE,
            text_color=UI_TEXT_MUTED,
            border_width=1,
            border_color=UI_BORDER,
        )
        self.req_bump_preview.pack(fill="x", pady=(6, 8))
        self.req_bump_preview.insert("1.0", "Coverage plan appears after preview.")
        self.req_bump_preview.configure(state="disabled")
        btn = ctk.CTkFrame(form.body, fg_color="transparent")
        btn.pack(fill="x", padx=CARD_PAD, pady=(0, CARD_PAD))
        SecondaryButton(btn, text="Preview coverage", command=self.preview_request_coverage).pack(
            side="left", fill="x", expand=True, padx=(0, 6)
        )
        PrimaryButton(btn, text="Submit request", command=self.submit_request).pack(
            side="left", fill="x", expand=True, padx=(6, 0)
        )
        self.req_officer_map = {}

        queue = Card(self)
        queue.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        qh = ctk.CTkFrame(queue.body, fg_color="transparent")
        qh.pack(fill="x", padx=CARD_PAD, pady=(CARD_PAD, 8))
        SectionHeader(qh, "Request queue", "Pending and review items").pack(side="left")
        self.request_list = ctk.CTkScrollableFrame(queue.body, fg_color="transparent")
        self.request_list.pack(fill="both", expand=True, padx=8, pady=(0, CARD_PAD))
        self._request_row_widgets = {}
        self.app._request_row_widgets = self._request_row_widgets
        self._request_view = "queue"

    def refresh(self) -> None:
        officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
        if self.is_officer():
            oid = self.app._linked_officer_id()
            officers = [o for o in officers if o["id"] == oid]
        labels = [o["name"] for o in officers] or ["—"]
        self.req_officer_map = {o["name"]: o["id"] for o in officers}
        self.req_officer.configure(values=labels)
        if labels:
            self.req_officer.set(labels[0])
        self.refresh_requests()

    def preview_request_coverage(self):
        officer_id = self.req_officer_map.get(self.req_officer.get())
        request_date = self.req_date.get().strip()
        if not officer_id or not request_date:
            return
        try:
            parse_date(request_date)
        except ValueError:
            self.req_coverage_status.configure(text=f"Date must be {DATE_INPUT_HINT}", text_color=DODGEVILLE_DANGER)
            return
        context = describe_day_off_request(officer_id, request_date)
        suggestion = context.get("suggestion") if context.get("success") else None
        if suggestion is None:
            officer = next((o for o in get_officers_by_seniority() if o["id"] == officer_id), None)
            if officer:
                suggestion = suggest_bump_chain(
                    officer_id, request_date, officer.get("squad") or "A", officer.get("shift_start") or "06:00"
                )
        if suggestion:
            ok = bool(getattr(suggestion, "success", False))
            self.req_coverage_status.configure(
                text="Coverage: auto-approve ready" if ok else "Coverage: needs review",
                text_color=DODGEVILLE_SUCCESS if ok else DODGEVILLE_WARNING,
            )
            self.req_bump_preview.configure(state="normal")
            self.req_bump_preview.delete("1.0", "end")
            self.req_bump_preview.insert("1.0", format_bump_suggestion(suggestion))
            self.req_bump_preview.configure(state="disabled")

    def submit_request(self):
        if not self.can("requests.submit") and not self.can("requests.submit_any"):
            messagebox.showwarning("Permission", "You cannot submit time off.")
            return
        officer_id = self.req_officer_map.get(self.req_officer.get())
        if self.is_officer() and officer_id != self.app._linked_officer_id():
            messagebox.showwarning("Permission", "Officers may only submit for themselves.")
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
            self.app.set_status(
                f"Request #{result['request_id']} submitted — supervisors will review",
                level="success",
            )
            self.refresh()
        else:
            messagebox.showerror("Cannot submit", result.get("message", "Failed"))

    def refresh_requests(self):
        for child in self.request_list.winfo_children():
            child.destroy()
        self._request_row_widgets.clear()
        if self.can("requests.approve"):
            requests = get_pending_day_off_requests()
        else:
            role = self.app.current_user.get("role") if self.app.current_user else ""
            data = get_day_off_requests_for_viewer(role, linked_officer_id=self.app._linked_officer_id())
            requests = [
                r
                for r in (data.get("requests") or [])
                if r.get("status") in (REQUEST_STATUS["pending"], REQUEST_STATUS["pending_manual"])
            ]
        if not requests:
            EmptyState(
                self.request_list,
                "Queue is clear",
                "Pending time-off requests appear here for review.",
            ).pack(fill="x", pady=16, padx=8)
            return
        for req in requests:
            row = ctk.CTkFrame(
                self.request_list, fg_color=UI_SURFACE, corner_radius=8, border_width=1, border_color=UI_BORDER
            )
            row.pack(fill="x", pady=4, padx=4)
            inner = ctk.CTkFrame(row, fg_color="transparent")
            inner.pack(fill="x", padx=12, pady=10)
            top = ctk.CTkFrame(inner, fg_color="transparent")
            top.pack(fill="x")
            ctk.CTkLabel(
                top,
                text=f"{req.get('officer_name', 'Officer')} · {req.get('request_type', '')}",
                font=font("subheading"),
                text_color=UI_TEXT_PRIMARY,
                anchor="w",
            ).pack(side="left")
            StatusBadge(top, req.get("status", "Pending")).pack(side="right")
            ctk.CTkLabel(
                inner,
                text=f"{format_date(req['request_date'])}  ·  {req.get('squad', '')}  {req.get('shift_start', '')}",
                font=font("small"),
                text_color=UI_TEXT_MUTED,
                anchor="w",
            ).pack(fill="x", pady=(4, 0))
            if self.can("requests.approve") and req.get("status") in (
                REQUEST_STATUS["pending"],
                REQUEST_STATUS["pending_manual"],
            ):
                btns = ctk.CTkFrame(inner, fg_color="transparent")
                btns.pack(fill="x", pady=(8, 0))
                CompactButton(btns, text="Plans", width=70, command=lambda r=req: self._show_plans(r)).pack(
                    side="right", padx=(4, 0)
                )
                PrimaryButton(
                    btns, text="Approve", width=80, height=28, command=lambda r=req: self._confirm_approve(r)
                ).pack(side="right", padx=(4, 0))
                DangerButton(
                    btns,
                    text="Reject",
                    width=80,
                    height=28,
                    command=lambda rid=req["id"]: self.handle_request(rid, "reject"),
                ).pack(side="right")
            self._request_row_widgets[req["id"]] = row

    def _show_plans(self, req):
        payload = preview_best_coverage_plans(
            req["officer_id"], req["request_date"], req["squad"], req.get("shift_start") or "", max_plans=5
        )
        lines = []
        for i, plan in enumerate(payload.get("plans") or [], 1):
            lines.append(f"Plan {i}: {plan.get('message', '')}")
            for s in plan.get("steps") or []:
                lines.append(f"  {s.get('step')}. {s.get('replacement')} → {s.get('original')}")
        messagebox.showinfo("Coverage plans", "\n".join(lines) or "No plans")

    def _confirm_approve(self, req):
        payload = preview_best_coverage_plans(
            req["officer_id"], req["request_date"], req["squad"], req.get("shift_start") or "", max_plans=5
        )
        plans = [p for p in (payload.get("plans") or []) if p.get("success")]
        if len(plans) <= 1:
            summary = plans[0].get("message") if plans else "Approve with best available coverage?"
            if messagebox.askyesno("Approve request", f"{req.get('officer_name')}\n\n{summary}"):
                chain = (plans[0].get("chain") if plans else None) or None
                self.handle_request(req["id"], "approve", preferred_chain=chain)
            return
        dlg = ctk.CTkToplevel(self.app.root)
        dlg.title("Select coverage plan")
        dlg.geometry("520x420")
        dlg.transient(self.app.root)
        scroll = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=12, pady=12)

        def apply(plan):
            dlg.destroy()
            self.handle_request(req["id"], "approve", preferred_chain=plan.get("chain") or [])

        for i, plan in enumerate(plans, 1):
            card = ctk.CTkFrame(scroll, fg_color=UI_SURFACE, corner_radius=8, border_width=1, border_color=UI_BORDER)
            card.pack(fill="x", pady=6)
            ctk.CTkLabel(card, text=f"Plan {i}: {plan.get('message', '')}", font=font("subheading"), anchor="w").pack(
                fill="x", padx=12, pady=(10, 4)
            )
            for s in plan.get("steps") or []:
                ctk.CTkLabel(
                    card,
                    text=f"  {s.get('step')}. {s.get('replacement')} covers {s.get('original')}",
                    font=font("small"),
                    text_color=UI_TEXT_MUTED,
                    anchor="w",
                ).pack(fill="x", padx=12)
            PrimaryButton(card, text=f"Use plan {i}", height=30, command=lambda p=plan: apply(p)).pack(
                anchor="e", padx=12, pady=10
            )
        SecondaryButton(dlg, text="Cancel", command=dlg.destroy).pack(pady=8)

    def handle_request(self, request_id, action, preferred_chain=None):
        result = process_day_off_request(request_id, action=action, preferred_chain=preferred_chain)
        if result.success:
            self.app.set_status(result.message, level="success")
        elif result.requires_manual:
            self.app.set_status(f"Manual review: {result.message}")
            messagebox.showinfo("Manual review", result.message)
        else:
            messagebox.showwarning("Action failed", result.message)
        from ui.helpers import refresh_after_schedule_change

        self.refresh()
        refresh_after_schedule_change(self.app)


class SwapsPage(BasePage):
    page_key = "swaps"

    def build(self) -> None:
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)
        form = Card(self, accent=True)
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        SectionHeader(form.body, "New swap", "Exchange shifts for one day").pack(
            fill="x", padx=CARD_PAD, pady=(CARD_PAD, 12)
        )
        sf = ctk.CTkFrame(form.body, fg_color="transparent")
        sf.pack(fill="x", padx=CARD_PAD)
        self.swap_officer1 = FormField(
            sf, "Officer 1", lambda p: ctk.CTkComboBox(p, height=36, values=["Loading..."])
        ).widget
        self.swap_officer2 = FormField(
            sf, "Officer 2", lambda p: ctk.CTkComboBox(p, height=36, values=["Loading..."])
        ).widget
        self.swap_date = FormField(
            sf, "Swap date", lambda p: ctk.CTkEntry(p, height=36, placeholder_text=today_placeholder())
        ).widget
        self.swap_preview = ctk.CTkLabel(
            sf, text="Validation: not checked", font=font("small"), text_color=UI_TEXT_MUTED, anchor="w"
        )
        self.swap_preview.pack(fill="x", pady=(8, 8))
        sbtn = ctk.CTkFrame(form.body, fg_color="transparent")
        sbtn.pack(fill="x", padx=CARD_PAD, pady=(0, CARD_PAD))
        SecondaryButton(sbtn, text="Validate", command=self.preview_swap).pack(
            side="left", fill="x", expand=True, padx=(0, 6)
        )
        PrimaryButton(sbtn, text="Submit swap", command=self.submit_swap).pack(
            side="left", fill="x", expand=True, padx=(6, 0)
        )
        self.swap_officer_map = {}

        list_card = Card(self)
        list_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        SectionHeader(list_card.body, "Swap queue").pack(fill="x", padx=CARD_PAD, pady=(CARD_PAD, 8))
        self.swap_list = ctk.CTkScrollableFrame(list_card.body, fg_color="transparent")
        self.swap_list.pack(fill="both", expand=True, padx=8, pady=(0, CARD_PAD))
        self._swap_row_widgets = {}
        self.app._swap_row_widgets = self._swap_row_widgets

    def refresh(self) -> None:
        officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
        labels = [o["name"] for o in officers] or ["—"]
        self.swap_officer_map = {o["name"]: o["id"] for o in officers}
        for combo in (self.swap_officer1, self.swap_officer2):
            combo.configure(values=labels)
            if labels:
                combo.set(labels[0])
        for child in self.swap_list.winfo_children():
            child.destroy()
        swaps = get_pending_shift_swap_requests() if self.can("swaps.approve") else get_shift_swap_requests()
        if not swaps:
            EmptyState(self.swap_list, "No swap requests", "Pending exchanges show here.").pack(
                fill="x", pady=16, padx=8
            )
            return
        for swap in swaps[:50]:
            row = ctk.CTkFrame(
                self.swap_list, fg_color=UI_SURFACE, corner_radius=8, border_width=1, border_color=UI_BORDER
            )
            row.pack(fill="x", pady=4, padx=4)
            inner = ctk.CTkFrame(row, fg_color="transparent")
            inner.pack(fill="x", padx=12, pady=10)
            ctk.CTkLabel(
                inner,
                text=f"{swap.get('officer1_name')} ⇄ {swap.get('officer2_name')}",
                font=font("subheading"),
                anchor="w",
            ).pack(fill="x")
            ctk.CTkLabel(
                inner,
                text=f"{format_date(swap.get('swap_date'))} · {swap.get('status')}",
                font=font("small"),
                text_color=UI_TEXT_MUTED,
                anchor="w",
            ).pack(fill="x")
            if self.can("swaps.approve") and swap.get("status") in ("Pending", "Pending Manual Review"):
                btns = ctk.CTkFrame(inner, fg_color="transparent")
                btns.pack(fill="x", pady=(8, 0))
                PrimaryButton(
                    btns,
                    text="Approve",
                    width=80,
                    height=28,
                    command=lambda sid=swap["id"]: self._handle_swap(sid, "approve"),
                ).pack(side="right", padx=(4, 0))
                DangerButton(
                    btns,
                    text="Reject",
                    width=80,
                    height=28,
                    command=lambda sid=swap["id"]: self._handle_swap(sid, "reject"),
                ).pack(side="right")

    def preview_swap(self):
        o1 = self.swap_officer_map.get(self.swap_officer1.get())
        o2 = self.swap_officer_map.get(self.swap_officer2.get())
        d = self.swap_date.get().strip()
        try:
            parse_date(d)
        except ValueError:
            self.swap_preview.configure(text="Invalid date", text_color=DODGEVILLE_DANGER)
            return
        result = validate_swap_feasibility(o1, o2, d)
        ok = bool(getattr(result, "success", result.get("success") if isinstance(result, dict) else False))
        msg = getattr(result, "message", None) or (result.get("message") if isinstance(result, dict) else str(result))
        self.swap_preview.configure(
            text=msg or ("OK" if ok else "Not feasible"),
            text_color=DODGEVILLE_SUCCESS if ok else DODGEVILLE_WARNING,
        )

    def submit_swap(self):
        o1 = self.swap_officer_map.get(self.swap_officer1.get())
        o2 = self.swap_officer_map.get(self.swap_officer2.get())
        d = self.swap_date.get().strip()
        result = create_shift_swap_request(o1, o2, d)
        if result.get("success"):
            self.app.set_status(f"Swap #{result.get('swap_id')} submitted", level="success")
            self.refresh()
        else:
            messagebox.showerror("Swap", result.get("message", "Failed"))

    def _handle_swap(self, swap_id, action):
        result = process_shift_swap(swap_id, action=action)
        ok = getattr(result, "success", False)
        msg = getattr(result, "message", str(result))
        if ok:
            self.app.set_status(msg, level="success")
        else:
            messagebox.showwarning("Swap", msg)
        self.refresh()
