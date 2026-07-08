"""Shared shift-bid dialog helpers (simulator import, calendars, award preview)."""

from __future__ import annotations

from tkinter import messagebox
from typing import Callable, Dict, Optional

import customtkinter as ctk

from config import DATE_INPUT_HINT
from logic import build_shift_bid_payload_from_simulation, preview_shift_bid_awards
from ui.theme import DODGEVILLE_GOLD, DODGEVILLE_SUCCESS, UI_BORDER, UI_TEXT_MUTED, font
from ui.widgets import PrimaryButton
from validators import format_date

_BID_CAL_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_BID_CAL_CELL = 34


def shift_bid_field(parent, label: str, placeholder: str = "", width: int = 280) -> ctk.CTkEntry:
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", pady=4)
    ctk.CTkLabel(row, text=label, font=font("small"), width=140, anchor="w").pack(side="left")
    entry = ctk.CTkEntry(row, placeholder_text=placeholder, width=width, height=32)
    entry.pack(side="left", fill="x", expand=True)
    return entry


def fill_entries_from_simulation(
    sim_result: Dict,
    entries: Dict[str, ctk.CTkEntry],
    *,
    on_success: Optional[Callable[[], None]] = None,
) -> None:
    payload = build_shift_bid_payload_from_simulation(sim_result)
    if not payload.get("success"):
        messagebox.showerror("Simulator", payload.get("message"))
        return
    for key, entry in entries.items():
        entry.delete(0, "end")
        entry.insert(0, payload.get(key) or "")
    if on_success:
        on_success()


def add_simulator_import_button(
    parent,
    sim_result: Optional[Dict],
    entries: Dict[str, ctk.CTkEntry],
    *,
    on_success: Optional[Callable[[], None]] = None,
) -> None:
    if not sim_result or not sim_result.get("success"):
        return

    def _import() -> None:
        fill_entries_from_simulation(sim_result, entries, on_success=on_success)

    ctk.CTkButton(
        parent,
        text="Import from Simulator",
        height=32,
        fg_color=DODGEVILLE_GOLD,
        command=_import,
    ).pack(anchor="w", pady=(8, 0))


def render_shift_bid_mini_calendar(parent, preview: dict) -> None:
    if not preview.get("success"):
        ctk.CTkLabel(
            parent,
            text=preview.get("message", "Calendar preview unavailable"),
            font=font("small"),
            text_color=UI_TEXT_MUTED,
        ).pack(pady=8)
        return
    hdr = ctk.CTkFrame(parent, fg_color="transparent")
    hdr.pack(fill="x", pady=(0, 6))
    shift_start = preview.get("shift_start")
    start_txt = format_date(preview.get("start_date")) if preview.get("start_date") else "—"
    meta = f"{preview.get('pattern_label', '')}  ·  from {start_txt}"
    if shift_start:
        meta += f"  ·  starts {shift_start}"
    meta += f"  ·  {preview.get('on_count', 0)} on / {preview.get('off_count', 0)} off"
    ctk.CTkLabel(hdr, text=meta, font=font("small"), text_color=UI_TEXT_MUTED, anchor="w").pack(fill="x")
    legend = ctk.CTkFrame(parent, fg_color="transparent")
    legend.pack(fill="x", pady=(0, 6))
    for label, color in (("On", DODGEVILLE_SUCCESS), ("Off", UI_BORDER)):
        ctk.CTkLabel(
            legend,
            text=f"  {label}  ",
            font=font("small"),
            fg_color=color,
            corner_radius=4,
            text_color="#FFFFFF" if label == "On" else UI_TEXT_MUTED,
        ).pack(side="left", padx=(0, 6))
    grid = ctk.CTkFrame(parent, fg_color="transparent")
    grid.pack(fill="x")
    for col, name in enumerate(_BID_CAL_WEEKDAYS):
        ctk.CTkLabel(grid, text=name, font=font("small"), text_color=UI_TEXT_MUTED, width=_BID_CAL_CELL).grid(
            row=0, column=col, padx=1, pady=1
        )
    days = preview.get("days") or []
    if not days:
        return
    lead = days[0]["weekday"]
    row = 1
    col = 0
    for _ in range(lead):
        pad = ctk.CTkFrame(grid, width=_BID_CAL_CELL, height=_BID_CAL_CELL, fg_color="transparent")
        pad.grid(row=row, column=col, padx=1, pady=1)
        col += 1
    for entry in days:
        if col > 6:
            col = 0
            row += 1
        bg = DODGEVILLE_SUCCESS if entry.get("on") else UI_BORDER
        fg = "#FFFFFF" if entry.get("on") else UI_TEXT_MUTED
        cell = ctk.CTkFrame(grid, width=_BID_CAL_CELL, height=_BID_CAL_CELL, fg_color=bg, corner_radius=4)
        cell.grid(row=row, column=col, padx=1, pady=1)
        cell.grid_propagate(False)
        ctk.CTkLabel(cell, text=str(entry.get("day", "")), font=font("small"), text_color=fg).pack(expand=True)
        col += 1


def show_award_preview_dialog(root, event_id: int, *, on_finalize: Optional[Callable[[], None]] = None) -> None:
    preview = preview_shift_bid_awards(event_id)
    if not preview.get("success"):
        messagebox.showerror("Award Preview", preview.get("message"))
        return
    dlg = ctk.CTkToplevel(root)
    dlg.title("Award Preview")
    dlg.geometry("460x380")
    dlg.transient(root)
    ctk.CTkLabel(
        dlg,
        text="Seniority-based awards (preview — not saved until you finalize):",
        font=font("small"),
        text_color=UI_TEXT_MUTED,
        wraplength=420,
    ).pack(padx=16, pady=(12, 8), anchor="w")
    scroll = ctk.CTkScrollableFrame(dlg, fg_color="transparent", height=220)
    scroll.pack(fill="both", expand=True, padx=16, pady=4)
    for award in preview.get("awards", []):
        ctk.CTkLabel(
            scroll,
            text=f"{award.get('officer_name')} → {award.get('option_label')} (pref #{award.get('preference_rank')})",
            font=font("body"),
            anchor="w",
        ).pack(fill="x", pady=2)
    unassigned = preview.get("unassigned_options") or []
    if unassigned:
        ctk.CTkLabel(scroll, text="Unassigned:", font=font("small"), anchor="w").pack(fill="x", pady=(8, 2))
        for opt in unassigned:
            ctk.CTkLabel(scroll, text=opt.get("label", "Shift"), font=font("small"), anchor="w").pack(fill="x")
    btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
    btn_row.pack(fill="x", padx=16, pady=12)
    if on_finalize:
        PrimaryButton(
            btn_row, text="Finalize Now", fg_color=DODGEVILLE_SUCCESS, command=lambda: (dlg.destroy(), on_finalize())
        ).pack(side="left", padx=(0, 8))
    ctk.CTkButton(btn_row, text="Close", command=dlg.destroy).pack(side="left")


def create_shift_bid_form_entries(scroll) -> Dict[str, ctk.CTkEntry]:
    return {
        "title": shift_bid_field(scroll, "Title", "e.g. Summer rotation bid"),
        "number_of_shifts": shift_bid_field(scroll, "Number of shifts", "e.g. 4"),
        "shift_length": shift_bid_field(scroll, "Shift length", "e.g. 10 hours, 12h, etc."),
        "rotation": shift_bid_field(scroll, "Rotation", "e.g. 4 on / 4 off, Panamas"),
        "shift_start_times": shift_bid_field(scroll, "Shift start times", "e.g. 06:00, 14:00, 19:00"),
        "shifts_begin": shift_bid_field(scroll, "Shifts begin", DATE_INPUT_HINT),
        "bids_due_by": shift_bid_field(scroll, "Bids due by", "e.g. 2026-08-01 17:00"),
        "notes": shift_bid_field(scroll, "Notes", "Optional instructions for officers"),
    }
