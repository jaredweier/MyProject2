"""Patrol roster — clean list + detail form."""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from config import OFFICER_SQUAD_OPTIONS
from logic import (
    add_officer,
    get_officer_by_id,
    get_officer_title_options,
    get_officers_by_seniority,
    update_officer,
)
from logic.staffing_config import get_officer_shift_options
from ui.pages.base import BasePage
from ui.theme import CARD_PAD, DODGEVILLE_GOLD, UI_BORDER, UI_SURFACE, UI_TEXT_MUTED, font
from ui.widgets import (
    Card,
    EmptyState,
    FormField,
    PrimaryButton,
    SearchBar,
    SecondaryButton,
    SectionHeader,
    StatusBadge,
)
from validators import format_officer_shift_display, parse_officer_shift_ui


class RosterPage(BasePage):
    page_key = "officers"

    def build(self) -> None:
        if not self.can("officers.manage"):
            EmptyState(self, "No access", "Roster management requires supervisor permission.").grid(
                row=0, column=0, sticky="nsew", padx=24, pady=24
            )
            return
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)

        left = Card(self)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        hdr = ctk.CTkFrame(left.body, fg_color="transparent")
        hdr.pack(fill="x", padx=CARD_PAD, pady=(CARD_PAD, 8))
        SectionHeader(hdr, "Roster", "Click an officer to edit").pack(side="left")
        self._count = ctk.CTkLabel(hdr, text="", font=font("small"), text_color=UI_TEXT_MUTED)
        self._count.pack(side="right")
        self.search = SearchBar(left.body, placeholder="Search by name or squad…")
        self.search.pack(fill="x", padx=CARD_PAD, pady=(0, 8))
        self.search.bind("<KeyRelease>", lambda _e: self.refresh())
        self.officer_list = ctk.CTkScrollableFrame(left.body, fg_color="transparent")
        self.officer_list.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        right = Card(self, accent=True)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        SectionHeader(right.body, "Officer detail", "Title, squad, and shift assignment").pack(
            fill="x", padx=CARD_PAD, pady=(CARD_PAD, 12)
        )
        form = ctk.CTkScrollableFrame(right.body, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=CARD_PAD)
        self.off_name = FormField(form, "Full name", lambda p: ctk.CTkEntry(p, height=36)).widget
        titles = get_officer_title_options()
        self.off_title = FormField(
            form, "Title", lambda p: ctk.CTkComboBox(p, height=36, values=titles, state="readonly")
        ).widget
        self.off_squad = FormField(
            form,
            "Squad",
            lambda p: ctk.CTkComboBox(p, height=36, values=list(OFFICER_SQUAD_OPTIONS), state="readonly"),
        ).widget
        shifts = get_officer_shift_options()
        self.off_shift = FormField(
            form, "Shift", lambda p: ctk.CTkComboBox(p, height=36, values=list(shifts), state="readonly")
        ).widget
        self.off_seniority = FormField(form, "Seniority rank", lambda p: ctk.CTkEntry(p, height=36)).widget
        self.off_active = ctk.CTkCheckBox(form, text="Active on roster", font=font("body"))
        self.off_active.pack(anchor="w", pady=12)
        self.off_active.select()
        btns = ctk.CTkFrame(right.body, fg_color="transparent")
        btns.pack(fill="x", padx=CARD_PAD, pady=(0, CARD_PAD))
        PrimaryButton(btns, text="Save changes", command=self.save_officer).pack(side="left", padx=(0, 8))
        SecondaryButton(btns, text="New officer", command=self.new_officer).pack(side="left")
        self._selected_id = None
        self.app.selected_officer_id = None

    def refresh(self) -> None:
        if not self.can("officers.manage"):
            return
        q = (self.search.get() or "").strip().lower()
        officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
        if q:
            officers = [
                o for o in officers if q in (o.get("name") or "").lower() or q in (o.get("squad") or "").lower()
            ]
        self._count.configure(text=f"{len(officers)} active")
        for w in self.officer_list.winfo_children():
            w.destroy()
        if not officers:
            EmptyState(self.officer_list, "No officers", "Add a patrol officer to the roster.").pack(fill="x", pady=12)
            return
        for o in officers:
            row = ctk.CTkFrame(
                self.officer_list,
                fg_color=UI_SURFACE if o["id"] != self._selected_id else UI_BORDER,
                corner_radius=8,
                border_width=1,
                border_color=DODGEVILLE_GOLD if o["id"] == self._selected_id else UI_BORDER,
                cursor="hand2",
            )
            row.pack(fill="x", pady=3, padx=4)
            inner = ctk.CTkFrame(row, fg_color="transparent")
            inner.pack(fill="x", padx=10, pady=8)
            ctk.CTkLabel(inner, text=o["name"], font=font("subheading"), anchor="w").pack(side="left")
            StatusBadge(inner, o.get("job_title") or "Officer").pack(side="right", padx=(4, 0))
            ctk.CTkLabel(
                row,
                text=f"Squad {o.get('squad') or '—'} · {o.get('shift_start') or '—'} · #{o.get('seniority_rank')}",
                font=font("small"),
                text_color=UI_TEXT_MUTED,
                anchor="w",
            ).pack(fill="x", padx=10, pady=(0, 8))
            row.bind("<Button-1>", lambda _e, oid=o["id"]: self.load_officer(oid))
            for child in row.winfo_children():
                child.bind("<Button-1>", lambda _e, oid=o["id"]: self.load_officer(oid))

    def load_officer(self, officer_id: int):
        o = get_officer_by_id(officer_id)
        if not o:
            return
        self._selected_id = officer_id
        self.app.selected_officer_id = officer_id
        self.off_name.delete(0, "end")
        self.off_name.insert(0, o.get("name") or "")
        self.off_title.set(o.get("job_title") or "Officer")
        self.off_squad.set(o.get("squad") or OFFICER_SQUAD_OPTIONS[0])
        self.off_shift.set(format_officer_shift_display(o.get("shift_start"), o.get("shift_end")))
        self.off_seniority.delete(0, "end")
        self.off_seniority.insert(0, str(o.get("seniority_rank") or ""))
        if o.get("active") == 1:
            self.off_active.select()
        else:
            self.off_active.deselect()
        self.refresh()

    def new_officer(self):
        self._selected_id = None
        self.app.selected_officer_id = None
        self.off_name.delete(0, "end")
        self.off_title.set("Officer")
        self.off_squad.set("A")
        shifts = get_officer_shift_options()
        self.off_shift.set(shifts[1] if len(shifts) > 1 else shifts[0])
        self.off_seniority.delete(0, "end")
        self.off_active.select()

    def save_officer(self):
        name = self.off_name.get().strip()
        if not name:
            messagebox.showerror("Validation", "Name is required.")
            return
        start, end = parse_officer_shift_ui(self.off_shift.get())
        try:
            rank = int(self.off_seniority.get().strip() or "0")
        except ValueError:
            messagebox.showerror("Validation", "Seniority must be a number.")
            return
        fields = {
            "name": name,
            "job_title": self.off_title.get(),
            "squad": self.off_squad.get() if self.off_squad.get() != "Unassigned" else None,
            "shift_start": start,
            "shift_end": end,
            "seniority_rank": rank,
        }
        if self._selected_id:
            fields["active"] = 1 if self.off_active.get() else 0
            result = update_officer(self._selected_id, **fields)
        else:
            result = add_officer(
                name=fields["name"],
                seniority_rank=fields["seniority_rank"],
                squad=fields["squad"],
                shift_start=fields["shift_start"],
                shift_end=fields["shift_end"],
                job_title=fields["job_title"],
            )
        if result.get("success"):
            self.app.set_status(result.get("message", "Officer saved"), level="success")
            oid = result.get("officer_id") or self._selected_id
            self._selected_id = oid
            self.refresh()
            if oid:
                self.load_officer(oid)
        else:
            messagebox.showerror("Save failed", result.get("message", "Unknown error"))
