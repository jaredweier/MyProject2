"""Shift bidding UI — supervisor events, officer rankings, award preview."""

from __future__ import annotations

from tkinter import messagebox
from typing import Optional

import customtkinter as ctk

from logic import (
    build_shift_bid_option_calendar,
    cancel_shift_bid_event,
    create_shift_bid_event,
    finalize_shift_bid_event,
    format_bid_event_summary,
    get_officer_shift_bid_awards,
    get_shift_bid_event,
    get_shift_bid_events,
    get_shift_bid_participation_report,
    get_shift_bid_rankings_for_event,
    officer_has_active_shift_bid,
    publish_shift_bid_event,
    submit_shift_bid_rankings,
    update_shift_bid_assignments,
    update_shift_bid_event,
)
from logic.officers import get_officers_by_seniority
from ui.bid_dialogs import (
    add_simulator_import_button,
    create_shift_bid_form_entries,
    render_shift_bid_mini_calendar,
    show_award_preview_dialog,
)
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
from ui.widgets import PrimaryButton, SectionHeader, StatusBadge
from validators import format_date


class BidPageMixin:
    def _build_tier2_availability_sections(self, parent) -> None:
        self._shift_bid_container = ctk.CTkFrame(
            parent,
            fg_color=UI_SURFACE,
            corner_radius=8,
            border_width=1,
            border_color=UI_BORDER,
        )
        self._bid_header = SectionHeader(
            self._shift_bid_container,
            "Shift Bidding",
            "Rank preferences or manage bid events",
        )
        self._bid_header.pack(fill="x", padx=CARD_PAD, pady=(8, 6))
        if self.can("shift_bids.manage"):
            mgr = ctk.CTkFrame(self._shift_bid_container, fg_color="transparent")
            mgr.pack(fill="x", padx=CARD_PAD, pady=(0, 6))
            PrimaryButton(
                mgr,
                text="+ Create Shift Bid",
                fg_color=DODGEVILLE_GOLD,
                command=self._show_create_shift_bid_dialog,
            ).pack(side="left")
        self.shift_bid_list = ctk.CTkScrollableFrame(self._shift_bid_container, fg_color="transparent", height=180)
        self.shift_bid_list.pack(fill="x", padx=8, pady=(0, 8))
        self._shift_bid_container.pack(fill="x", padx=0, pady=(0, 4))
        self._officer_bid_awards_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._officer_bid_awards_list = ctk.CTkFrame(self._officer_bid_awards_frame, fg_color="transparent")
        self._shift_bid_container_visible = True
        self._officer_awards_visible = False

    def _show_create_shift_bid_dialog(self, event_id: Optional[int] = None) -> None:
        if not self.can("shift_bids.manage"):
            return
        existing = get_shift_bid_event(event_id) if event_id else None
        dlg = ctk.CTkToplevel(self.root)
        dlg.title("Edit Shift Bid" if existing else "Create Shift Bid")
        dlg.geometry("520x560")
        dlg.transient(self.root)
        scroll = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=12)
        entries = create_shift_bid_form_entries(scroll)
        squad_row = ctk.CTkFrame(scroll, fg_color="transparent")
        squad_row.pack(fill="x", pady=4)
        ctk.CTkLabel(squad_row, text="Squad", font=font("small"), width=140, anchor="w").pack(side="left")
        squad_var = ctk.StringVar(value="All")
        ctk.CTkOptionMenu(squad_row, variable=squad_var, values=["All", "A", "B"], width=120).pack(side="left")
        if not existing:
            add_simulator_import_button(
                scroll,
                getattr(self, "_last_simulation_result", None),
                entries,
                on_success=lambda: self.set_status("Filled from last simulation"),
            )
        if existing:
            for key, entry in entries.items():
                entry.insert(0, existing.get(key) or "")
            squad_var.set(existing.get("squad") or "All")

        def save_draft() -> None:
            payload = {key: entry.get().strip() for key, entry in entries.items()}
            payload["squad"] = squad_var.get()
            uid = self.current_user.get("id") if self.current_user else None
            if existing:
                result = update_shift_bid_event(existing["id"], **payload)
                event_id_saved = existing["id"]
            else:
                result = create_shift_bid_event(user_id=uid, **payload)
                event_id_saved = result.get("event_id")
            if not result.get("success"):
                messagebox.showerror("Shift Bid", result.get("message"))
                return
            if messagebox.askyesno("Publish", "Publish this bid to officers now?"):
                pub = publish_shift_bid_event(event_id_saved, user_id=uid)
                if not pub.get("success"):
                    messagebox.showerror("Publish", pub.get("message"))
                    return
                messagebox.showinfo("Published", f"Sent to officers — {pub.get('option_count', 0)} shift(s)")
            dlg.destroy()
            self.refresh_availability()
            self.set_status("Shift bid saved")

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=12)
        PrimaryButton(btn_row, text="Save / Publish", fg_color=DODGEVILLE_SUCCESS, command=save_draft).pack(
            side="left", padx=(0, 8)
        )
        ctk.CTkButton(btn_row, text="Cancel", command=dlg.destroy).pack(side="left")

    def _show_officer_ranking_dialog(self, event_id: int) -> None:
        oid = self._linked_officer_id()
        if not oid:
            messagebox.showwarning("Shift Bid", "Link your account to an officer profile first.")
            return
        event = get_shift_bid_event(event_id, officer_id=oid)
        if not event or event.get("status") != "open":
            messagebox.showwarning("Shift Bid", "This bid event is not open.")
            return
        options = event.get("options") or []
        if not options:
            messagebox.showwarning("Shift Bid", "No shifts configured for this bid.")
            return
        dlg = ctk.CTkToplevel(self.root)
        dlg.title(event.get("title") or "Rank Shift Preferences")
        dlg.geometry("760x640")
        dlg.minsize(640, 520)
        dlg.transient(self.root)
        ctk.CTkLabel(
            dlg,
            text="Review each shift calendar, then rank preferences (1 = most preferred).",
            font=font("small"),
            text_color=UI_TEXT_MUTED,
            wraplength=700,
        ).pack(padx=16, pady=(12, 6), anchor="w")
        info = ctk.CTkFrame(dlg, fg_color=UI_SURFACE, corner_radius=8)
        info.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkLabel(
            info,
            text=(
                f"Length: {event.get('shift_length') or '—'}  ·  Rotation: {event.get('rotation') or '—'}\n"
                f"Shift times: {event.get('shift_start_times') or '—'}  ·  Begin: {event.get('shifts_begin') or '—'}\n"
                f"Bids due by: {event.get('bids_due_by') or '—'}"
            ),
            font=font("small"),
            justify="left",
        ).pack(padx=12, pady=10, anchor="w")
        rank_vars: dict[int, ctk.StringVar] = {}
        existing = {r["option_id"]: str(r["preference_rank"]) for r in event.get("my_rankings", [])}
        rank_choices = [""] + [str(i) for i in range(1, len(options) + 1)]
        tabs = ctk.CTkTabview(dlg, fg_color="transparent")
        tabs.pack(fill="both", expand=True, padx=16, pady=4)
        for opt in options:
            label = opt.get("label") or f"Shift {opt.get('option_number')}"
            tab = tabs.add(label)
            rank_row = ctk.CTkFrame(tab, fg_color="transparent")
            rank_row.pack(fill="x", pady=(4, 8))
            ctk.CTkLabel(rank_row, text="Your preference rank", font=font("body")).pack(side="left")
            var = ctk.StringVar(value=existing.get(opt["id"], ""))
            ctk.CTkOptionMenu(rank_row, variable=var, values=rank_choices, width=80).pack(side="right")
            rank_vars[opt["id"]] = var
            preview = build_shift_bid_option_calendar(event, opt)
            cal_scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent", height=360)
            cal_scroll.pack(fill="both", expand=True)
            render_shift_bid_mini_calendar(cal_scroll, preview)

        def submit() -> None:
            rankings = []
            for option_id, var in rank_vars.items():
                val = var.get().strip()
                if val:
                    rankings.append({"option_id": option_id, "preference_rank": int(val)})
            uid = self.current_user.get("id") if self.current_user else None
            result = submit_shift_bid_rankings(event_id, oid, rankings, user_id=uid)
            if result.get("success"):
                dlg.destroy()
                self.refresh_availability()
                self.set_status("Preferences submitted")
            else:
                messagebox.showerror("Shift Bid", result.get("message"))

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=12)
        PrimaryButton(btn_row, text="Submit Rankings", fg_color=DODGEVILLE_ACCENT, command=submit).pack(side="left")

    def _show_supervisor_event_detail(self, event_id: int) -> None:
        event = get_shift_bid_event(event_id)
        if not event:
            return
        report = get_shift_bid_participation_report(event_id)
        dlg = ctk.CTkToplevel(self.root)
        dlg.title(event.get("title") or "Shift Bid")
        dlg.geometry("520x480")
        dlg.transient(self.root)
        ctk.CTkLabel(dlg, text=format_bid_event_summary(event_id), font=font("body"), justify="left").pack(
            padx=16, pady=16, anchor="w"
        )
        if report.get("success"):
            ctk.CTkLabel(
                dlg,
                text=(
                    f"Participation: {report.get('respondent_count', 0)} / {report.get('eligible_count', 0)} "
                    f"eligible officer(s)"
                ),
                font=font("small"),
                text_color=UI_TEXT_MUTED,
            ).pack(padx=16, anchor="w")
        if event.get("status") == "finalized":
            scroll = ctk.CTkScrollableFrame(dlg, fg_color="transparent", height=160)
            scroll.pack(fill="both", expand=True, padx=12, pady=(0, 8))
            ctk.CTkLabel(scroll, text="Final assignments:", font=font("small"), anchor="w").pack(fill="x", pady=(0, 4))
            for opt in event.get("options", []):
                assigned = opt.get("awarded_officer_name") or "Unassigned"
                ctk.CTkLabel(scroll, text=f"{opt.get('label')}: {assigned}", font=font("small"), anchor="w").pack(
                    fill="x", pady=2
                )
        else:
            rankings = get_shift_bid_rankings_for_event(event_id)
            if rankings:
                scroll = ctk.CTkScrollableFrame(dlg, fg_color="transparent", height=160)
                scroll.pack(fill="both", expand=True, padx=12, pady=(0, 8))
                for row in rankings:
                    ctk.CTkLabel(
                        scroll,
                        text=(
                            f"{row['officer_name']}  ·  {row['option_label']}  ·  "
                            f"pref #{row['preference_rank']}  ·  rank {row['seniority_rank']}"
                        ),
                        font=font("small"),
                        anchor="w",
                    ).pack(fill="x", pady=2)
            missing = report.get("missing_officers") or []
            if missing:
                ctk.CTkLabel(
                    dlg, text=f"No response: {', '.join(m['name'] for m in missing)}", font=font("small")
                ).pack(padx=16, anchor="w")
        ctk.CTkButton(dlg, text="Close", command=dlg.destroy).pack(pady=12)

    def _show_edit_assignments_dialog(self, event_id: int) -> None:
        if not self.can("shift_bids.manage"):
            return
        event = get_shift_bid_event(event_id)
        if not event or event.get("status") != "finalized":
            messagebox.showwarning("Assignments", "Only finalized bid events can be edited.")
            return
        options = event.get("options") or []
        officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
        if event.get("squad"):
            officers = [o for o in officers if o.get("squad") == event["squad"]]
        officer_labels = ["— Unassigned —"] + [o["name"] for o in officers]
        label_to_id = {o["name"]: o["id"] for o in officers}

        dlg = ctk.CTkToplevel(self.root)
        dlg.title(f"Edit Assignments — {event.get('title') or 'Shift Bid'}")
        dlg.geometry("480x420")
        dlg.transient(self.root)
        ctk.CTkLabel(
            dlg,
            text="Override automatic results. Each officer may hold one shift.",
            font=font("small"),
            text_color=UI_TEXT_MUTED,
        ).pack(padx=16, pady=(12, 8), anchor="w")
        scroll = ctk.CTkScrollableFrame(dlg, fg_color="transparent", height=260)
        scroll.pack(fill="both", expand=True, padx=16, pady=4)
        choice_vars: dict[int, ctk.StringVar] = {}
        for opt in options:
            row = ctk.CTkFrame(scroll, fg_color=UI_SURFACE, corner_radius=8)
            row.pack(fill="x", pady=3)
            inner = ctk.CTkFrame(row, fg_color="transparent")
            inner.pack(fill="x", padx=12, pady=8)
            ctk.CTkLabel(inner, text=opt.get("label") or f"Shift {opt.get('option_number')}", font=font("body")).pack(
                side="left", fill="x", expand=True
            )
            current = opt.get("awarded_officer_name") or "— Unassigned —"
            var = ctk.StringVar(value=current if current in officer_labels else "— Unassigned —")
            ctk.CTkOptionMenu(inner, variable=var, values=officer_labels, width=180).pack(side="right")
            choice_vars[opt["id"]] = var

        def save() -> None:
            assignments = []
            for option_id, var in choice_vars.items():
                label = var.get()
                officer_id = None if label == "— Unassigned —" else label_to_id.get(label)
                assignments.append({"option_id": option_id, "officer_id": officer_id})
            uid = self.current_user.get("id") if self.current_user else None
            result = update_shift_bid_assignments(event_id, assignments, user_id=uid)
            if result.get("success"):
                changed = result.get("changed", 0)
                dlg.destroy()
                self.refresh_availability()
                self.set_status(f"Updated {changed} assignment(s)" if changed else "No changes")
            else:
                messagebox.showerror("Assignments", result.get("message"))

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=12)
        PrimaryButton(btn_row, text="Save Assignments", fg_color=DODGEVILLE_SUCCESS, command=save).pack(
            side="left", padx=(0, 8)
        )
        ctk.CTkButton(btn_row, text="Cancel", command=dlg.destroy).pack(side="left")

    def _publish_shift_bid(self, event_id: int) -> None:
        uid = self.current_user.get("id") if self.current_user else None
        result = publish_shift_bid_event(event_id, user_id=uid)
        if result.get("success"):
            messagebox.showinfo("Published", f"Sent to officers — {result.get('option_count', 0)} shift(s)")
            self.refresh_availability()
        else:
            messagebox.showerror("Publish", result.get("message"))

    def _finalize_shift_bid(self, event_id: int) -> None:
        show_award_preview_dialog(
            self.root,
            event_id,
            on_finalize=lambda: self._confirm_finalize_shift_bid(event_id),
        )

    def _confirm_finalize_shift_bid(self, event_id: int) -> None:
        uid = self.current_user.get("id") if self.current_user else None
        result = finalize_shift_bid_event(event_id, user_id=uid)
        if result.get("success"):
            lines = [f"{a['officer_name']} → {a['option_label']}" for a in result.get("awards", [])]
            messagebox.showinfo("Finalized", "\n".join(lines) or "No awards made")
            self.refresh_availability()
            self._refresh_dashboard_data()
        else:
            messagebox.showerror("Finalize", result.get("message"))

    def _cancel_shift_bid(self, event_id: int) -> None:
        if not messagebox.askyesno("Cancel", "Cancel this shift bid event?"):
            return
        uid = self.current_user.get("id") if self.current_user else None
        result = cancel_shift_bid_event(event_id, user_id=uid)
        if result.get("success"):
            self.refresh_availability()
        else:
            messagebox.showerror("Cancel", result.get("message"))

    def _refresh_officer_bid_awards(self, officer_id: Optional[int]) -> None:
        if not hasattr(self, "_officer_bid_awards_frame"):
            return
        for w in self._officer_bid_awards_list.winfo_children():
            w.destroy()
        if not officer_id or self.can("shift_bids.manage"):
            if getattr(self, "_officer_awards_visible", False):
                self._officer_bid_awards_frame.pack_forget()
                self._officer_awards_visible = False
            return
        awards = get_officer_shift_bid_awards(officer_id)
        if not awards:
            if getattr(self, "_officer_awards_visible", False):
                self._officer_bid_awards_frame.pack_forget()
                self._officer_awards_visible = False
            return
        if not getattr(self, "_officer_awards_visible", False):
            self._officer_bid_awards_frame.pack(fill="x", after=self._shift_bid_container)
            self._officer_awards_visible = True
        SectionHeader(
            self._officer_bid_awards_frame,
            "Your Shift Awards",
            "Finalized bid assignments",
        ).pack(fill="x", padx=CARD_PAD, pady=(4, 4))
        self._officer_bid_awards_list.pack(fill="x", padx=CARD_PAD, pady=(0, 8))
        for row in awards:
            begin = format_date(row.get("shifts_begin")) if row.get("shifts_begin") else "—"
            ctk.CTkLabel(
                self._officer_bid_awards_list,
                text=f"{row.get('title') or 'Shift Bid'}: {row.get('label')} (begins {begin})",
                font=font("small"),
                anchor="w",
            ).pack(fill="x", pady=2)

    def _refresh_shift_bidding(self) -> None:
        if not hasattr(self, "shift_bid_list"):
            return
        is_supervisor = self.can("shift_bids.manage")
        oid = self._linked_officer_id() if self._is_officer_role() else None
        show_for_officer = oid and officer_has_active_shift_bid(oid)
        if not is_supervisor and not show_for_officer:
            if getattr(self, "_shift_bid_container_visible", False):
                self._shift_bid_container.pack_forget()
                self._shift_bid_container_visible = False
        else:
            if not getattr(self, "_shift_bid_container_visible", False):
                self._shift_bid_container.pack(fill="x")
                self._shift_bid_container_visible = True

        for w in self.shift_bid_list.winfo_children():
            w.destroy()
        for row in list(getattr(self, "_shift_bid_row_widgets", {}).values()):
            try:
                if row.winfo_exists():
                    row.configure(border_width=0)
            except Exception:
                pass
        self._shift_bid_row_widgets = {}

        if is_supervisor:
            events = [
                e
                for e in get_shift_bid_events(include_drafts=True, limit=30)
                if e.get("status") in ("draft", "open", "finalized")
            ]
        else:
            events = get_shift_bid_events(officer_id=oid)
            for idx, ev in enumerate(events):
                full = get_shift_bid_event(ev["id"], officer_id=oid)
                if full:
                    events[idx]["has_submitted"] = full.get("has_submitted")

        if hasattr(self, "_bid_header"):
            if is_supervisor:
                subtitle = f"{len(events)} bid event(s) — drafts, open, and finalized"
            else:
                subtitle = f"{len(events)} open bid(s) — rank your preferences"
            self._bid_header.configure(subtitle=subtitle)

        if not events:
            ctk.CTkLabel(
                self.shift_bid_list,
                text="No shift bids right now." if not is_supervisor else "No bid events yet — create one above.",
                font=font("body"),
                text_color=UI_TEXT_MUTED,
            ).pack(pady=8)
        else:
            for event in events:
                row = ctk.CTkFrame(self.shift_bid_list, fg_color=UI_SURFACE, corner_radius=8)
                row.pack(fill="x", pady=3, padx=4)
                inner = ctk.CTkFrame(row, fg_color="transparent")
                inner.pack(fill="x", padx=12, pady=8)
                left = ctk.CTkFrame(inner, fg_color="transparent")
                left.pack(side="left", fill="x", expand=True)
                badge_row = ctk.CTkFrame(left, fg_color="transparent")
                badge_row.pack(fill="x")
                StatusBadge(badge_row, event.get("status", "draft").title()).pack(side="left")
                if event.get("squad"):
                    StatusBadge(badge_row, f"Squad {event['squad']}").pack(side="left", padx=(6, 0))
                if event.get("has_submitted"):
                    ctk.CTkLabel(
                        badge_row,
                        text="Submitted",
                        font=font("small"),
                        fg_color=DODGEVILLE_SUCCESS,
                        corner_radius=4,
                        padx=10,
                        pady=4,
                    ).pack(side="left", padx=(6, 0))
                ctk.CTkLabel(left, text=event.get("title") or "Shift Bid", font=font("body"), anchor="w").pack(
                    fill="x", pady=(4, 0)
                )
                detail = (
                    f"{event.get('number_of_shifts') or '—'} shifts  ·  {event.get('shift_length') or '—'}  ·  "
                    f"due {event.get('bids_due_by') or '—'}"
                )
                ctk.CTkLabel(left, text=detail, font=font("small"), text_color=UI_TEXT_MUTED, anchor="w").pack(fill="x")
                if is_supervisor:
                    ctk.CTkLabel(
                        left,
                        text=f"{event.get('respondent_count', 0)} response(s)",
                        font=font("small"),
                        text_color=UI_TEXT_MUTED,
                        anchor="w",
                    ).pack(fill="x")
                btn_row = ctk.CTkFrame(inner, fg_color="transparent")
                btn_row.pack(side="right")
                eid = event["id"]
                if is_supervisor:
                    if event.get("status") == "draft":
                        ctk.CTkButton(
                            btn_row,
                            text="Edit",
                            width=56,
                            height=28,
                            fg_color=DODGEVILLE_BLUE,
                            command=lambda eid=eid: self._show_create_shift_bid_dialog(eid),
                        ).pack(side="left", padx=2)
                        PrimaryButton(
                            btn_row,
                            text="Publish",
                            width=72,
                            height=28,
                            fg_color=DODGEVILLE_SUCCESS,
                            command=lambda eid=eid: self._publish_shift_bid(eid),
                        ).pack(side="left", padx=2)
                        ctk.CTkButton(
                            btn_row,
                            text="✕",
                            width=32,
                            height=28,
                            fg_color=DODGEVILLE_DANGER,
                            command=lambda eid=eid: self._cancel_shift_bid(eid),
                        ).pack(side="left", padx=2)
                    elif event.get("status") == "open":
                        ctk.CTkButton(
                            btn_row,
                            text="Responses",
                            width=80,
                            height=28,
                            fg_color=DODGEVILLE_BLUE,
                            command=lambda eid=eid: self._show_supervisor_event_detail(eid),
                        ).pack(side="left", padx=2)
                        ctk.CTkButton(
                            btn_row,
                            text="Preview",
                            width=72,
                            height=28,
                            fg_color=DODGEVILLE_WARNING,
                            command=lambda eid=eid: show_award_preview_dialog(self.root, eid),
                        ).pack(side="left", padx=2)
                        PrimaryButton(
                            btn_row,
                            text="Finalize",
                            width=72,
                            height=28,
                            fg_color=DODGEVILLE_GOLD,
                            command=lambda eid=eid: self._finalize_shift_bid(eid),
                        ).pack(side="left", padx=2)
                        ctk.CTkButton(
                            btn_row,
                            text="✕",
                            width=32,
                            height=28,
                            fg_color=DODGEVILLE_DANGER,
                            command=lambda eid=eid: self._cancel_shift_bid(eid),
                        ).pack(side="left", padx=2)
                    elif event.get("status") == "finalized":
                        ctk.CTkButton(
                            btn_row,
                            text="Results",
                            width=72,
                            height=28,
                            fg_color=DODGEVILLE_BLUE,
                            command=lambda eid=eid: self._show_supervisor_event_detail(eid),
                        ).pack(side="left", padx=2)
                        PrimaryButton(
                            btn_row,
                            text="Edit Assignments",
                            width=120,
                            height=28,
                            fg_color=DODGEVILLE_WARNING,
                            command=lambda eid=eid: self._show_edit_assignments_dialog(eid),
                        ).pack(side="left", padx=2)
                elif event.get("status") == "open":
                    PrimaryButton(
                        btn_row,
                        text="Rank Shifts" if not event.get("has_submitted") else "Edit Rankings",
                        width=110,
                        height=28,
                        fg_color=DODGEVILLE_ACCENT,
                        command=lambda eid=eid: self._show_officer_ranking_dialog(eid),
                    ).pack(side="left", padx=2)
                self._shift_bid_row_widgets[event["id"]] = row

        if getattr(self, "_highlight_shift_bid_id", None):
            self._apply_row_highlight(
                self._shift_bid_row_widgets,
                self._highlight_shift_bid_id,
                "_highlight_shift_bid_id",
            )
        self._refresh_officer_bid_awards(oid)
