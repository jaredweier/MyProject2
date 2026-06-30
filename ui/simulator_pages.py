"""Schedule simulator training tab."""

from tkinter import filedialog, messagebox

import customtkinter as ctk

from config import DEFAULT_ANNUAL_HOURS, SIMULATOR_ROTATION_TYPES
from logic import (
    export_simulation_csv,
    get_simulator_defaults_from_roster,
    run_schedule_simulation,
)
from ui.theme import (
    CARD_PAD,
    DODGEVILLE_ACCENT,
    DODGEVILLE_DANGER,
    DODGEVILLE_GOLD,
    DODGEVILLE_WARNING,
    UI_BORDER,
    UI_SURFACE,
    UI_TEXT_MUTED,
    font,
)
from ui.widgets import Card, FormField, SectionHeader


class SimulatorPageMixin:
    def _build_simulator(self):
        page = self.pages["simulator"]
        page.grid_columnconfigure(0, weight=2)
        page.grid_columnconfigure(1, weight=3)
        page.grid_rowconfigure(0, weight=1)

        left = Card(page)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        SectionHeader(left.body, "Simulation Inputs", "Configure rotation and staffing parameters").pack(
            fill="x", padx=CARD_PAD, pady=(CARD_PAD, 8)
        )
        form = ctk.CTkScrollableFrame(left.body, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=CARD_PAD, pady=(0, CARD_PAD))

        self.sim_rotation = FormField(
            form, "Rotation Pattern", lambda p: ctk.CTkComboBox(p, values=SIMULATOR_ROTATION_TYPES, height=36)
        ).widget
        self.sim_rotation.set(SIMULATOR_ROTATION_TYPES[0])

        self.sim_officers = FormField(
            form, "Number of Officers", lambda p: ctk.CTkSlider(p, from_=4, to=40, number_of_steps=36)
        ).widget
        self.sim_officers.set(16)
        self.sim_officers_label = ctk.CTkLabel(form, text="Officers: 16", font=font("small"), text_color=UI_TEXT_MUTED)
        self.sim_officers_label.pack(anchor="w", pady=(0, 8))
        self.sim_officers.configure(command=lambda v: self.sim_officers_label.configure(text=f"Officers: {int(v)}"))

        self.sim_shift_length = FormField(
            form, "Shift Length (hours)", lambda p: ctk.CTkEntry(p, height=36, placeholder_text="11")
        ).widget
        self.sim_shift_length.insert(0, "11")

        self.sim_annual_hours = FormField(
            form, "Annual Hours Target (per officer)", lambda p: ctk.CTkEntry(p, height=36, placeholder_text="2080")
        ).widget
        self.sim_annual_hours.insert(0, str(int(DEFAULT_ANNUAL_HOURS)))

        self.sim_shift_starts = FormField(
            form,
            "Shift Start Times (comma separated)",
            lambda p: ctk.CTkEntry(p, height=36, placeholder_text="06:00, 10:00, 15:00, 19:00"),
        ).widget
        self.sim_shift_starts.insert(0, "06:00, 10:00, 15:00, 19:00")

        self.sim_min_shift = FormField(
            form, "Minimum Officers per Shift", lambda p: ctk.CTkEntry(p, height=36, placeholder_text="1")
        ).widget
        self.sim_min_shift.insert(0, "1")

        self.sim_use_rules = ctk.CTkCheckBox(
            form,
            text="Apply Dodgeville PD rules (14 day rotation, night minimum Fri/Sat, department shifts)",
            font=font("body"),
        )
        self.sim_use_rules.select()
        self.sim_use_rules.pack(anchor="w", pady=12)

        btn_row = ctk.CTkFrame(form, fg_color="transparent")
        btn_row.pack(fill="x", pady=8)
        ctk.CTkButton(
            btn_row,
            text="Load Current Roster",
            height=36,
            fg_color=UI_BORDER,
            command=self._simulator_load_roster,
        ).pack(fill="x", pady=(0, 8))
        ctk.CTkButton(
            btn_row,
            text="Generate Optimal Schedule",
            height=40,
            fg_color=DODGEVILLE_ACCENT,
            command=self.run_schedule_simulator,
        ).pack(fill="x")

        right = Card(page)
        right.grid(row=0, column=1, sticky="nsew")
        sim_hdr = ctk.CTkFrame(right.body, fg_color="transparent")
        sim_hdr.pack(fill="x", padx=CARD_PAD, pady=(CARD_PAD, 4))
        SectionHeader(sim_hdr, "Simulation Results", "Coverage metrics and optimization suggestions").pack(side="left")
        ctk.CTkButton(
            sim_hdr,
            text="Export CSV",
            width=100,
            height=28,
            fg_color=DODGEVILLE_GOLD,
            command=self._export_simulation_csv,
        ).pack(side="right")
        self.sim_metrics = ctk.CTkLabel(
            right.body,
            text="Run a simulation to see results.",
            font=font("body"),
            text_color=UI_TEXT_MUTED,
            anchor="w",
        )
        self.sim_metrics.pack(fill="x", padx=CARD_PAD, pady=(0, 8))
        self.sim_results_scroll = ctk.CTkScrollableFrame(right.body, fg_color="transparent")
        self.sim_results_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _simulator_load_roster(self):
        data = get_simulator_defaults_from_roster()
        if not data.get("success"):
            messagebox.showerror("Simulator", data.get("message", "Could not load roster settings."))
            return
        self.sim_rotation.set(data["rotation_type"])
        self.sim_officers.set(data["num_officers"])
        self.sim_officers_label.configure(text=f"Officers: {data['num_officers']}")
        self.sim_shift_length.delete(0, "end")
        self.sim_shift_length.insert(0, str(data["shift_length_hours"]))
        self.sim_annual_hours.delete(0, "end")
        self.sim_annual_hours.insert(0, str(int(data["annual_hours_target"])))
        self.sim_shift_starts.delete(0, "end")
        self.sim_shift_starts.insert(0, data["shift_starts"])
        self.sim_min_shift.delete(0, "end")
        self.sim_min_shift.insert(0, str(data["min_per_shift"]))
        if data["apply_department_rules"]:
            self.sim_use_rules.select()
        else:
            self.sim_use_rules.deselect()
        self.set_status("Loaded settings from current roster")

    def run_schedule_simulator(self):
        if not self.can("simulator.use"):
            messagebox.showwarning("Permission", "You do not have access to the simulator.")
            return
        try:
            num_officers = int(self.sim_officers.get())
            shift_length = float(self.sim_shift_length.get().strip())
            annual_hours = float(self.sim_annual_hours.get().strip())
            min_shift = int(self.sim_min_shift.get().strip() or "1")
        except ValueError:
            messagebox.showerror("Validation", "Check numeric inputs.")
            return
        shift_starts = [s.strip() for s in self.sim_shift_starts.get().split(",") if s.strip()]
        result = run_schedule_simulation(
            rotation_type=self.sim_rotation.get(),
            num_officers=num_officers,
            shift_length_hours=shift_length,
            annual_hours_target=annual_hours,
            shift_starts=shift_starts,
            apply_department_rules=bool(self.sim_use_rules.get()),
            min_per_shift=min_shift,
        )
        if not result.get("success"):
            messagebox.showerror("Simulation", result.get("message", "Failed"))
            return
        self._last_simulation_result = result
        self._render_simulation_results(result)
        self.set_status("Schedule simulation complete")

    def _export_simulation_csv(self):
        if not self._last_simulation_result:
            messagebox.showwarning("Export", "Run a simulation first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        result = export_simulation_csv(self._last_simulation_result, output_path=path)
        if result.get("success"):
            messagebox.showinfo(
                "Export",
                f"Simulation exported ({result['count']} rows)\n{result['path']}",
            )
            self.set_status("Simulation CSV exported")
        else:
            messagebox.showerror("Export Failed", result.get("message", "Unknown error"))

    def _render_simulation_results(self, result: dict):
        for w in self.sim_results_scroll.winfo_children():
            w.destroy()
        m = result.get("metrics", {})
        self.sim_metrics.configure(
            text=(
                f"Coverage {m.get('coverage_percent', 0)}%  ·  "
                f"FTE needed {m.get('fte_required', 0)}  ·  "
                f"Avg annual hours {m.get('avg_annual_hours', 0)}  ·  "
                f"Gap events {m.get('gap_events', 0)}"
            )
        )

        metrics_card = ctk.CTkFrame(self.sim_results_scroll, fg_color=UI_SURFACE, corner_radius=8)
        metrics_card.pack(fill="x", pady=(0, 8))
        mc = ctk.CTkFrame(metrics_card, fg_color="transparent")
        mc.pack(fill="x", padx=12, pady=10)
        for label, key in [
            ("Coverage", "coverage_percent"),
            ("Min per shift", "min_shift_coverage"),
            ("FTE required", "fte_required"),
            ("Night risk gaps", "night_risk_gaps"),
        ]:
            val = m.get(key, "n/a")
            suffix = "%" if key == "coverage_percent" else ""
            ctk.CTkLabel(mc, text=f"{label}: {val}{suffix}", font=font("body"), anchor="w").pack(fill="x")

        SectionHeader(self.sim_results_scroll, "Optimization Suggestions", "").pack(fill="x", pady=(8, 4))
        suggestions = result.get("suggestions", [])
        if not suggestions:
            ctk.CTkLabel(
                self.sim_results_scroll,
                text="No issues found.",
                text_color=UI_TEXT_MUTED,
                font=font("body"),
            ).pack(pady=8)
        for sug in suggestions:
            color = {
                "critical": DODGEVILLE_DANGER,
                "warning": DODGEVILLE_WARNING,
                "info": DODGEVILLE_ACCENT,
            }.get(sug.get("severity"), UI_TEXT_MUTED)
            card = ctk.CTkFrame(self.sim_results_scroll, fg_color=UI_SURFACE, corner_radius=8)
            card.pack(fill="x", pady=4)
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=12, pady=10)
            ctk.CTkLabel(inner, text=sug.get("title", ""), font=font("subheading"), text_color=color, anchor="w").pack(
                fill="x"
            )
            ctk.CTkLabel(inner, text=sug.get("message", ""), font=font("body"), anchor="w", wraplength=520).pack(
                fill="x"
            )
            if sug.get("recommendation"):
                ctk.CTkLabel(
                    inner,
                    text=f"→ {sug['recommendation']}",
                    font=font("small"),
                    text_color=UI_TEXT_MUTED,
                    anchor="w",
                    wraplength=520,
                ).pack(fill="x", pady=(4, 0))

        SectionHeader(self.sim_results_scroll, "Proposed Officer Assignments", "").pack(fill="x", pady=(12, 4))
        for slot in result.get("officer_slots", []):
            line = (
                f"{slot['label']}  ·  Squad {slot['squad']}  ·  "
                f"{slot['shift_start']}–{slot['shift_end']}  ·  "
                f"{slot['projected_annual_hours']:.0f}h/yr"
            )
            ctk.CTkLabel(self.sim_results_scroll, text=line, font=font("small"), anchor="w").pack(fill="x", pady=1)

        SectionHeader(self.sim_results_scroll, "14 Day Coverage Sample", "").pack(fill="x", pady=(12, 4))
        for day in result.get("coverage_by_day", [])[:14]:
            counts = day.get("shift_counts", {})
            parts = "  ".join(f"{k}: {v}" for k, v in counts.items())
            risk = " ⚠" if day.get("high_risk_night") else ""
            ctk.CTkLabel(
                self.sim_results_scroll,
                text=f"{day['date']}  cycle {day['cycle_day']}  ·  {parts}{risk}",
                font=font("small"),
                text_color=UI_TEXT_MUTED,
                anchor="w",
            ).pack(fill="x", pady=1)
