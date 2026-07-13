"""Staffing simulator — single run + best-combination sweep."""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from config import SIMULATOR_ROTATION_TYPES
from logic import get_simulator_defaults_from_roster, run_schedule_simulation, run_staffing_optimizer
from logic.staffing_config import (
    get_active_annual_hours_target,
    get_active_shift_length_hours,
    get_active_shift_starts,
    get_target_officer_count,
)
from ui.pages.base import BasePage
from ui.theme import CARD_PAD, DODGEVILLE_SUCCESS, font
from ui.widgets import Card, EmptyState, FormField, PrimaryButton, SecondaryButton, SectionHeader


class SimulatorPage(BasePage):
    page_key = "simulator"

    def build(self) -> None:
        if not self.can("simulator.use"):
            EmptyState(self, "No access", "Simulator is limited to supervisors.").grid(
                row=0, column=0, sticky="nsew", padx=24, pady=24
            )
            return
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)

        form_card = Card(self, accent=True)
        form_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        SectionHeader(form_card.body, "Scenario inputs", "Rotation, headcount, and shift bands").pack(
            fill="x", padx=CARD_PAD, pady=(CARD_PAD, 12)
        )
        form = ctk.CTkScrollableFrame(form_card.body, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=CARD_PAD)
        self.sim_rotation = FormField(
            form,
            "Rotation",
            lambda p: ctk.CTkComboBox(p, height=34, values=list(SIMULATOR_ROTATION_TYPES), state="readonly"),
        ).widget
        self.sim_rotation.set(SIMULATOR_ROTATION_TYPES[0])
        self.sim_officers = FormField(form, "Officers", lambda p: ctk.CTkEntry(p, height=34)).widget
        self.sim_officers.insert(0, str(get_target_officer_count()))
        self.sim_shift_length = FormField(form, "Shift length (hours)", lambda p: ctk.CTkEntry(p, height=34)).widget
        self.sim_shift_length.insert(0, str(get_active_shift_length_hours()))
        self.sim_annual = FormField(form, "Annual hours target", lambda p: ctk.CTkEntry(p, height=34)).widget
        self.sim_annual.insert(0, str(int(get_active_annual_hours_target())))
        self.sim_starts = FormField(form, "Shift starts (comma-separated)", lambda p: ctk.CTkEntry(p, height=34)).widget
        self.sim_starts.insert(0, ", ".join(get_active_shift_starts()))
        self.sim_min = FormField(form, "Min per shift", lambda p: ctk.CTkEntry(p, height=34)).widget
        self.sim_min.insert(0, "1")
        self.sim_days = FormField(form, "Simulation days", lambda p: ctk.CTkEntry(p, height=34)).widget
        self.sim_days.insert(0, "28")
        btns = ctk.CTkFrame(form_card.body, fg_color="transparent")
        btns.pack(fill="x", padx=CARD_PAD, pady=CARD_PAD)
        SecondaryButton(btns, text="Load roster defaults", command=self._load_defaults).pack(fill="x", pady=(0, 8))
        PrimaryButton(btns, text="Generate schedule", command=self.run_sim).pack(fill="x", pady=(0, 8))
        PrimaryButton(
            btns, text="Find best staffing combination", fg_color=DODGEVILLE_SUCCESS, command=self.run_optimize
        ).pack(fill="x")

        out = Card(self)
        out.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        SectionHeader(out.body, "Results", "Metrics and ranked recommendations").pack(
            fill="x", padx=CARD_PAD, pady=(CARD_PAD, 8)
        )
        self._results = ctk.CTkTextbox(out.body, font=font("mono"), height=420)
        self._results.pack(fill="both", expand=True, padx=CARD_PAD, pady=(0, CARD_PAD))
        self._results.insert("1.0", "Run a simulation or staffing sweep to see results.")
        self._results.configure(state="disabled")

    def _load_defaults(self):
        d = get_simulator_defaults_from_roster()
        if not d.get("success"):
            return
        self.sim_rotation.set(d.get("rotation_type") or SIMULATOR_ROTATION_TYPES[0])
        self.sim_officers.delete(0, "end")
        self.sim_officers.insert(0, str(d.get("num_officers") or get_target_officer_count()))
        self.sim_shift_length.delete(0, "end")
        self.sim_shift_length.insert(0, str(d.get("shift_length_hours") or get_active_shift_length_hours()))
        self.sim_annual.delete(0, "end")
        self.sim_annual.insert(0, str(int(d.get("annual_hours_target") or get_active_annual_hours_target())))
        self.sim_starts.delete(0, "end")
        self.sim_starts.insert(0, d.get("shift_starts") or ", ".join(get_active_shift_starts()))
        self.sim_min.delete(0, "end")
        self.sim_min.insert(0, str(d.get("min_per_shift") or 1))
        self.app.set_status("Roster defaults loaded", toast=False)

    def _write(self, text: str):
        self._results.configure(state="normal")
        self._results.delete("1.0", "end")
        self._results.insert("1.0", text)
        self._results.configure(state="disabled")

    def run_sim(self):
        try:
            n = int(self.sim_officers.get().strip())
            length = float(self.sim_shift_length.get().strip())
            annual = float(self.sim_annual.get().strip())
            min_ps = int(self.sim_min.get().strip() or "1")
            days = int(self.sim_days.get().strip() or "28")
        except ValueError:
            messagebox.showerror("Validation", "Check numeric fields.")
            return
        starts = [s.strip() for s in self.sim_starts.get().replace(";", ",").split(",") if s.strip()]
        result = run_schedule_simulation(
            rotation_type=self.sim_rotation.get(),
            num_officers=n,
            shift_length_hours=length,
            annual_hours_target=annual,
            shift_starts=starts,
            min_per_shift=min_ps,
            simulation_days=days,
        )
        if not result.get("success"):
            messagebox.showerror("Simulation", result.get("message", "Failed"))
            return
        metrics = result.get("metrics") or {}
        lines = ["Simulation complete", "", "Metrics:"]
        for k, v in list(metrics.items())[:20]:
            lines.append(f"  {k}: {v}")
        lines.append("")
        lines.append("Suggestions:")
        for s in result.get("suggestions") or []:
            lines.append(f"  [{s.get('severity')}] {s.get('title')}: {s.get('message')}")
        self._write("\n".join(lines))
        self.app.set_status("Schedule simulation complete", level="success")

    def run_optimize(self):
        try:
            length = float(self.sim_shift_length.get().strip() or "0") or None
            annual = float(self.sim_annual.get().strip() or "0") or None
        except ValueError:
            length = annual = None
        starts = [s.strip() for s in self.sim_starts.get().replace(";", ",").split(",") if s.strip()]
        result = run_staffing_optimizer(
            shift_length_hours=length,
            annual_hours_target=annual,
            shift_starts=starts or None,
            simulation_days=14,
        )
        if not result.get("success") or not result.get("best"):
            messagebox.showerror("Optimizer", result.get("message", "No combination found"))
            return
        best = result["best"]
        try:
            self.sim_rotation.set(best["rotation_type"])
        except Exception:
            pass
        self.sim_officers.delete(0, "end")
        self.sim_officers.insert(0, str(best["num_officers"]))
        self.sim_min.delete(0, "end")
        self.sim_min.insert(0, str(best["min_per_shift"]))
        lines = [result.get("message", "Best staffing found"), "", "Top combinations:"]
        for i, row in enumerate((result.get("ranked") or [])[:8], 1):
            lines.append(
                f"{i}. {row['rotation_type']} · {row['num_officers']} officers · "
                f"min {row['min_per_shift']}/shift · score {row['score']}"
            )
        self._write("\n".join(lines))
        self.app.set_status(result.get("message", "Optimizer complete"), level="success")
