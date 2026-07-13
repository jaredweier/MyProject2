"""Schedule views — monthly base/live + duty timeline."""

from __future__ import annotations

from datetime import date
from tkinter import messagebox

import customtkinter as ctk

from config import GANTT_COLORS
from logic import (
    build_schedule_matrix,
    ensure_original_monthly_schedule,
    get_adjacent_cycle_window,
    get_current_cycle_window,
    get_cycle_day,
    is_future_cycle_window,
    sync_updated_schedule,
)
from ui.pages.base import BasePage
from ui.theme import (
    UI_ACCENT_GLOW,
    UI_SURFACE,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    font,
)
from ui.widgets import CompactButton, EmptyState, PrimaryButton, StatusLegend, ToolbarButton
from validators import format_date

GANTT_CELL_W = 40
GANTT_CELL_H = 16
GANTT_NAME_W = 160


class _ScheduleBase(BasePage):
    mode = "base"  # base | live

    def build(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self._month_label = ctk.CTkLabel(bar, text="", font=font("heading"), text_color=UI_TEXT_PRIMARY)
        self._month_label.pack(side="left")
        if self.mode == "base" and self.can("schedule.base.publish"):
            PrimaryButton(bar, text="Generate / lock month", height=32, command=self._generate).pack(
                side="right", padx=(8, 0)
            )
        if self.mode == "live" and self.can("schedule.updated.sync"):
            ToolbarButton(bar, text="Sync live", command=self._sync).pack(side="right")
        self._scroll = ctk.CTkScrollableFrame(self, fg_color=UI_SURFACE, corner_radius=10)
        self._scroll.grid(row=1, column=0, sticky="nsew")

    def refresh(self) -> None:
        today = date.today()
        self._month_label.configure(text=today.strftime("%B %Y"))
        for w in self._scroll.winfo_children():
            w.destroy()
        # Always show cycle matrix — reliable across snapshot shapes
        start, end = get_current_cycle_window()
        matrix, day_list = build_schedule_matrix(start, end)
        if self.is_officer():
            oid = self.app._linked_officer_id()
            matrix = [e for e in matrix if e["officer"]["id"] == oid]
        mode_lbl = "Original plan" if self.mode == "base" else "Live coverage"
        ctk.CTkLabel(
            self._scroll,
            text=f"{mode_lbl} · {format_date(start)} – {format_date(end)}",
            font=font("small"),
            text_color=UI_TEXT_MUTED,
        ).pack(anchor="w", padx=12, pady=8)
        self._draw_matrix(matrix, day_list)

    def _draw_matrix(self, matrix, days):
        if not matrix:
            EmptyState(self._scroll, "No rows", "No officers in this window.").pack(fill="x", pady=16)
            return
        grid = ctk.CTkFrame(self._scroll, fg_color="transparent")
        grid.pack(padx=10, pady=10)
        ctk.CTkLabel(grid, text="Officer", width=GANTT_NAME_W, font=font("small"), text_color=UI_TEXT_MUTED).grid(
            row=0, column=0
        )
        today = date.today()
        for col, day in enumerate(days, start=1):
            ctk.CTkLabel(
                grid,
                text=f"{day.strftime('%a')}\n{format_date(day)}",
                width=GANTT_CELL_W + 4,
                font=font("small"),
                text_color=UI_ACCENT_GLOW if day == today else UI_TEXT_MUTED,
            ).grid(row=0, column=col, padx=1)
        for row_idx, entry in enumerate(matrix, start=1):
            officer = entry["officer"]
            ctk.CTkLabel(
                grid,
                text=officer["name"][:22],
                width=GANTT_NAME_W,
                anchor="w",
                font=font("small"),
                text_color=UI_TEXT_PRIMARY,
            ).grid(row=row_idx, column=0, sticky="w")
            for col, day in enumerate(days, start=1):
                status = entry["days"][day]
                color = GANTT_COLORS.get(status, GANTT_COLORS.get("unknown", "#64748B"))
                cell = ctk.CTkFrame(
                    grid,
                    width=GANTT_CELL_W,
                    height=GANTT_CELL_H,
                    fg_color=color,
                    corner_radius=4,
                    border_width=1 if day == today else 0,
                    border_color=UI_ACCENT_GLOW,
                )
                cell.grid(row=row_idx, column=col, padx=1, pady=1)

    def _generate(self):
        today = date.today()
        result = ensure_original_monthly_schedule(today.year, today.month)
        if result.get("success"):
            self.app.set_status(result.get("message", "Month generated"), level="success")
            self.refresh()
        else:
            messagebox.showerror("Schedule", result.get("message", "Failed"))

    def _sync(self):
        today = date.today()
        result = sync_updated_schedule(today.year, today.month)
        if result.get("success"):
            self.app.set_status(result.get("message", "Live schedule synced"), level="success")
            self.refresh()
        else:
            messagebox.showerror("Schedule", result.get("message", "Failed"))


class OriginalSchedulePage(_ScheduleBase):
    page_key = "base_schedule"
    mode = "base"


class LiveSchedulePage(_ScheduleBase):
    page_key = "live_schedule"
    mode = "live"


class TimelinePage(BasePage):
    page_key = "timeline"

    def build(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self._cycle_label = ctk.CTkLabel(bar, text="", font=font("body"), text_color=UI_TEXT_MUTED)
        self._cycle_label.pack(side="left")
        CompactButton(bar, text="◀", width=36, command=lambda: self._shift(-1)).pack(side="left", padx=(12, 4))
        ToolbarButton(bar, text="Today", command=self._today).pack(side="left", padx=4)
        CompactButton(bar, text="▶", width=36, command=lambda: self._shift(1)).pack(side="left", padx=4)
        self._scroll = ctk.CTkScrollableFrame(self, fg_color=UI_SURFACE, corner_radius=10)
        self._scroll.grid(row=1, column=0, sticky="nsew")
        legend_items = [(s.replace("_", " ").title(), c) for s, c in GANTT_COLORS.items() if s != "night_window"]
        StatusLegend(self, legend_items).grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self._cycle_start = None
        self.app._gantt_cycle_start = None

    def _window(self):
        ref = self._cycle_start or date.today()
        return get_current_cycle_window(ref)

    def _shift(self, direction: int):
        start, _ = self._window()
        nxt, _ = get_adjacent_cycle_window(start, direction)
        if direction > 0 and is_future_cycle_window(nxt):
            return
        self._cycle_start = nxt
        self.app._gantt_cycle_start = nxt
        self.refresh()

    def _today(self):
        self._cycle_start = None
        self.app._gantt_cycle_start = None
        self.refresh()

    def refresh(self) -> None:
        start, end = self._window()
        self._cycle_label.configure(text=f"Cycle window: {format_date(start)} – {format_date(end)}")
        for w in self._scroll.winfo_children():
            w.destroy()
        matrix, days = build_schedule_matrix(start, end)
        if self.is_officer():
            oid = self.app._linked_officer_id()
            matrix = [e for e in matrix if e["officer"]["id"] == oid]
        if not matrix:
            EmptyState(self._scroll, "No schedule rows", "No officers in this cycle window.").pack(
                fill="x", pady=24, padx=12
            )
            return
        grid = ctk.CTkFrame(self._scroll, fg_color="transparent")
        grid.pack(padx=10, pady=10)
        today = date.today()
        ctk.CTkLabel(grid, text="Officer", width=GANTT_NAME_W, font=font("small"), text_color=UI_TEXT_MUTED).grid(
            row=0, column=0
        )
        for col, day in enumerate(days, start=1):
            ctk.CTkLabel(
                grid,
                text=f"{day.strftime('%a')}\n{format_date(day)}\nD{get_cycle_day(day)}",
                width=GANTT_CELL_W + 4,
                font=font("small"),
                text_color=UI_ACCENT_GLOW if day == today else UI_TEXT_MUTED,
            ).grid(row=0, column=col, padx=1)
        self.app._gantt_cells = {}
        for row_idx, entry in enumerate(matrix, start=1):
            officer = entry["officer"]
            shift = officer.get("shift_start") or ""
            ctk.CTkLabel(
                grid,
                text=f"{officer['name'][:20]}\n{shift}",
                width=GANTT_NAME_W,
                anchor="w",
                font=font("small"),
                text_color=UI_TEXT_PRIMARY,
            ).grid(row=row_idx, column=0, sticky="w")
            for col, day in enumerate(days, start=1):
                status = entry["days"][day]
                color = GANTT_COLORS.get(status, "#64748B")
                cell = ctk.CTkFrame(
                    grid,
                    width=GANTT_CELL_W,
                    height=GANTT_CELL_H,
                    fg_color=color,
                    corner_radius=4,
                    border_width=1 if day == today else 0,
                    border_color=UI_ACCENT_GLOW,
                )
                cell.grid(row=row_idx, column=col, padx=1, pady=1)
                self.app._gantt_cells[(row_idx, col)] = cell
                cell.bind(
                    "<Button-1>",
                    lambda _e, n=officer["name"], d=day, s=status: self.app.set_status(
                        f"{n}: {format_date(d)} · {s}", toast=False
                    ),
                )
