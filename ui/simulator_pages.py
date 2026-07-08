"""Schedule simulator training tab."""

from tkinter import filedialog, messagebox

import customtkinter as ctk

from config import SIMULATOR_ROTATION_TYPES
from logic import (
    build_shift_bid_payload_from_simulation,
    create_shift_bid_from_simulation,
    export_simulation_csv,
    get_simulator_defaults_from_roster,
    run_schedule_simulation,
    rust_bridge,
    save_simulator_scenario,
)
from logic.staffing_config import (
    get_active_annual_hours_target,
    get_active_shift_length_hours,
    get_active_shift_starts,
    get_target_officer_count,
)
from ui.theme import (
    CARD_PAD,
    DODGEVILLE_ACCENT,
    DODGEVILLE_DANGER,
    DODGEVILLE_GOLD,
    DODGEVILLE_SUCCESS,
    DODGEVILLE_WARNING,
    UI_BORDER,
    UI_SURFACE,
    UI_TEXT_MUTED,
    font,
)
from ui.widgets import Card, FormField, PrimaryButton, SectionHeader

# Training presets aligned with SCHEDULING_RULES.md scenarios S-01..S-11.
SIMULATOR_TRAINING_PRESETS: list[dict] = [
    {
        "id": "",
        "label": "— Custom —",
        "hint": "Adjust inputs manually or load the current roster.",
    },
    {
        "id": "S-04",
        "label": "S-04 Day shift Friday bump",
        "hint": "Department rules on · tests day-shift bumps are not night-blocked.",
        "apply_department_rules": True,
        "min_per_shift": 1,
    },
    {
        "id": "S-05",
        "label": "S-05 Night minimum (Fri/Sat)",
        "hint": "Higher min staffing · stress-tests night minimum on high-risk nights.",
        "apply_department_rules": True,
        "min_per_shift": 2,
    },
    {
        "id": "S-06",
        "label": "S-06 Manual review staffing",
        "hint": "Lean roster · surfaces coverage gaps that route to manual review.",
        "num_officers": 10,
        "apply_department_rules": True,
        "min_per_shift": 2,
    },
    {
        "id": "S-09",
        "label": "S-09 Same-squad replacement",
        "hint": "Current roster defaults · practice on-duty bump coverage.",
        "use_roster": True,
        "apply_department_rules": True,
        "min_per_shift": 1,
    },
    {
        "id": "S-11",
        "label": "S-11 Shift swap coverage",
        "hint": "Full roster model · validate swap coverage after schedule changes.",
        "use_roster": True,
        "apply_department_rules": True,
        "min_per_shift": 1,
    },
]


class SimulatorPageMixin:
    def _build_simulator(self):
        page = self.pages["simulator"]
        page.grid_columnconfigure(0, weight=2)
        page.grid_columnconfigure(1, weight=3)
        page.grid_rowconfigure(0, weight=1)

        left = Card(page)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        SectionHeader(
            left.body,
            "Schedule Simulator",
            "Model rotation, staffing, and coverage before publishing to the roster",
        ).pack(fill="x", padx=CARD_PAD, pady=(CARD_PAD, 8))
        form = ctk.CTkScrollableFrame(left.body, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=CARD_PAD, pady=(0, CARD_PAD))

        self.sim_rotation = FormField(
            form, "Rotation Pattern", lambda p: ctk.CTkComboBox(p, values=SIMULATOR_ROTATION_TYPES, height=36)
        ).widget
        self.sim_rotation.set(SIMULATOR_ROTATION_TYPES[0])

        self.sim_officers = FormField(
            form, "Number of Officers", lambda p: ctk.CTkSlider(p, from_=4, to=40, number_of_steps=36)
        ).widget
        target_officers = get_target_officer_count()
        self.sim_officers.set(target_officers)
        self.sim_officers_label = ctk.CTkLabel(
            form, text=f"Officers: {target_officers}", font=font("small"), text_color=UI_TEXT_MUTED
        )
        self.sim_officers_label.pack(anchor="w", pady=(0, 8))
        self.sim_officers.configure(command=lambda v: self.sim_officers_label.configure(text=f"Officers: {int(v)}"))

        self.sim_shift_length = FormField(
            form, "Shift Length (hours)", lambda p: ctk.CTkEntry(p, height=36, placeholder_text="11")
        ).widget
        self.sim_shift_length.insert(0, str(get_active_shift_length_hours()))

        self.sim_annual_hours = FormField(
            form, "Annual Hours Target (per officer)", lambda p: ctk.CTkEntry(p, height=36, placeholder_text="2080")
        ).widget
        self.sim_annual_hours.insert(0, str(int(get_active_annual_hours_target())))

        self.sim_shift_starts = FormField(
            form,
            "Shift Start Times (comma separated)",
            lambda p: ctk.CTkEntry(p, height=36, placeholder_text="06:00, 10:00, 15:00, 19:00"),
        ).widget
        self.sim_shift_starts.insert(0, ", ".join(get_active_shift_starts()))

        self.sim_min_shift = FormField(
            form, "Minimum Officers per Shift", lambda p: ctk.CTkEntry(p, height=36, placeholder_text="1")
        ).widget
        self.sim_min_shift.insert(0, "1")

        self.sim_sim_days = FormField(
            form, "Simulation horizon (days)", lambda p: ctk.CTkEntry(p, height=36, placeholder_text="28")
        ).widget
        self.sim_sim_days.insert(0, "28")

        self.sim_night_min = FormField(
            form,
            "Night minimum (Fri/Sat high-risk)",
            lambda p: ctk.CTkEntry(p, height=36, placeholder_text="4"),
        ).widget
        from config import NIGHT_MINIMUM_OFFICERS

        self.sim_night_min.insert(0, str(NIGHT_MINIMUM_OFFICERS))

        SectionHeader(form, "Rotation Overrides", "Optional — applies when department rules are on").pack(
            fill="x", pady=(12, 6)
        )

        import json

        from logic import get_department_setting
        from logic.rotation_config import get_active_rotation_base_date, get_active_rotation_cycle_length
        from validators import format_date

        self.sim_cycle_length = FormField(
            form, "Cycle length (days)", lambda p: ctk.CTkEntry(p, height=36, placeholder_text="14")
        ).widget
        self.sim_cycle_length.insert(0, str(get_active_rotation_cycle_length()))

        self.sim_base_date = FormField(
            form,
            "Rotation base date (DD/MM/YYYY)",
            lambda p: ctk.CTkEntry(p, height=36, placeholder_text="28/06/2026"),
        ).widget
        self.sim_base_date.insert(0, format_date(get_active_rotation_base_date()))

        squad_raw = get_department_setting("rotation_squad_a_days", "").strip()
        squad_text = ""
        if squad_raw:
            try:
                days = json.loads(squad_raw)
                if isinstance(days, list):
                    squad_text = ",".join(str(d) for d in days)
            except (json.JSONDecodeError, TypeError, ValueError):
                squad_text = squad_raw
        self.sim_squad_a_days = FormField(
            form,
            "Squad A on-duty cycle days",
            lambda p: ctk.CTkEntry(p, height=36, placeholder_text="1,2,5,6,7,10,11"),
        ).widget
        if squad_text:
            self.sim_squad_a_days.insert(0, squad_text)

        self.sim_save_rotation = ctk.CTkCheckBox(
            form,
            text="Save rotation overrides to department settings before simulating",
            font=font("body"),
        )
        self.sim_save_rotation.select()
        self.sim_save_rotation.pack(anchor="w", pady=(4, 8))

        self.sim_use_rules = ctk.CTkCheckBox(
            form,
            text="Apply department rules (rotation, night minimum Fri/Sat, roster officers on any shift band)",
            font=font("body"),
        )
        self.sim_use_rules.select()
        self.sim_use_rules.pack(anchor="w", pady=12)

        preset_labels = [p["label"] for p in SIMULATOR_TRAINING_PRESETS]
        self._sim_preset_map = {p["label"]: p for p in SIMULATOR_TRAINING_PRESETS}
        self.sim_training_preset = FormField(
            form,
            "Training Scenario",
            lambda p: ctk.CTkComboBox(p, values=preset_labels, height=36),
        ).widget
        self.sim_training_preset.set(preset_labels[0])
        self.sim_preset_hint = ctk.CTkLabel(
            form,
            text="",
            font=font("small"),
            text_color=UI_TEXT_MUTED,
            wraplength=360,
            justify="left",
        )
        self.sim_preset_hint.pack(anchor="w", pady=(0, 8))
        self.sim_training_preset.configure(command=self._simulator_preset_changed)

        btn_row = ctk.CTkFrame(form, fg_color="transparent")
        btn_row.pack(fill="x", pady=8)
        ctk.CTkButton(
            btn_row,
            text="Load Training Preset",
            height=36,
            fg_color=DODGEVILLE_GOLD,
            command=self._simulator_apply_preset,
        ).pack(fill="x", pady=(0, 8))
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
        self.sim_backend_label = ctk.CTkLabel(
            sim_hdr,
            text="",
            font=font("small"),
            text_color=UI_TEXT_MUTED,
        )
        self.sim_backend_label.pack(side="right", padx=(8, 0))
        self._update_simulator_backend_label()
        if self.can("shift_bids.manage"):
            PrimaryButton(
                sim_hdr,
                text="Create Shift Bid",
                width=120,
                height=28,
                fg_color=DODGEVILLE_SUCCESS,
                command=self._import_simulation_to_shift_bid,
            ).pack(side="right", padx=(0, 6))
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

    def _update_simulator_backend_label(self):
        if not hasattr(self, "sim_backend_label"):
            return
        if rust_bridge.available():
            self.sim_backend_label.configure(text="Engine: Rust (scheduler_core)")
        else:
            hint = "python dev.py build-rust"
            self.sim_backend_label.configure(text=f"Engine: Python fallback · {hint}")

    def _simulator_preset_changed(self, _selection: str | None = None) -> None:
        preset = self._sim_preset_map.get(self.sim_training_preset.get(), {})
        self.sim_preset_hint.configure(text=preset.get("hint", ""))

    def _simulator_apply_preset(self) -> None:
        preset = self._sim_preset_map.get(self.sim_training_preset.get(), {})
        if not preset.get("id"):
            messagebox.showinfo("Training Preset", "Select a scenario other than Custom.")
            return
        if preset.get("use_roster"):
            self._simulator_load_roster()
        if preset.get("num_officers") is not None:
            count = int(preset["num_officers"])
            self.sim_officers.set(count)
            self.sim_officers_label.configure(text=f"Officers: {count}")
        if "min_per_shift" in preset:
            self.sim_min_shift.delete(0, "end")
            self.sim_min_shift.insert(0, str(preset["min_per_shift"]))
        if preset.get("apply_department_rules"):
            self.sim_use_rules.select()
        else:
            self.sim_use_rules.deselect()
        self._simulator_preset_changed()
        self.set_status(f"Loaded training preset {preset['id']}")

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
        import json

        from logic import get_department_setting
        from logic.rotation_config import get_active_rotation_base_date, get_active_rotation_cycle_length
        from validators import format_date

        self.sim_cycle_length.delete(0, "end")
        self.sim_cycle_length.insert(0, str(get_active_rotation_cycle_length()))
        self.sim_base_date.delete(0, "end")
        self.sim_base_date.insert(0, format_date(get_active_rotation_base_date()))
        squad_raw = get_department_setting("rotation_squad_a_days", "").strip()
        self.sim_squad_a_days.delete(0, "end")
        if squad_raw:
            try:
                days = json.loads(squad_raw)
                if isinstance(days, list):
                    self.sim_squad_a_days.insert(0, ",".join(str(d) for d in days))
            except (json.JSONDecodeError, TypeError, ValueError):
                self.sim_squad_a_days.insert(0, squad_raw)
        if data["apply_department_rules"]:
            self.sim_use_rules.select()
        else:
            self.sim_use_rules.deselect()
        self.set_status("Loaded settings from current roster")

    def run_schedule_simulator(self):
        if not self.can("simulator.use"):
            messagebox.showwarning("Permission", "You do not have access to the Schedule Simulator.")
            return
        try:
            num_officers = int(self.sim_officers.get())
            shift_length = float(self.sim_shift_length.get().strip())
            annual_hours = float(self.sim_annual_hours.get().strip())
            min_shift = int(self.sim_min_shift.get().strip() or "1")
            sim_days = int(self.sim_sim_days.get().strip() or "28")
            night_min = int(self.sim_night_min.get().strip() or "4")
        except ValueError:
            messagebox.showerror("Validation", "Check numeric inputs.")
            return
        shift_starts = [s.strip() for s in self.sim_shift_starts.get().split(",") if s.strip()]
        if bool(self.sim_use_rules.get()) and bool(self.sim_save_rotation.get()):
            from logic.rotation_config import save_rotation_settings

            try:
                cycle_len = int(self.sim_cycle_length.get().strip())
            except ValueError:
                messagebox.showerror("Validation", "Enter a valid rotation cycle length.")
                return
            uid = self.current_user.get("id") if self.current_user else None
            rot = save_rotation_settings(
                cycle_length=cycle_len,
                preset=self.sim_rotation.get().strip(),
                base_date_text=self.sim_base_date.get().strip(),
                squad_a_days_text=self.sim_squad_a_days.get().strip(),
                user_id=uid,
            )
            if not rot.get("success"):
                messagebox.showerror("Rotation", rot.get("message", "Could not save rotation settings."))
                return
        result = run_schedule_simulation(
            rotation_type=self.sim_rotation.get(),
            num_officers=num_officers,
            shift_length_hours=shift_length,
            annual_hours_target=annual_hours,
            shift_starts=shift_starts,
            apply_department_rules=bool(self.sim_use_rules.get()),
            min_per_shift=min_shift,
            simulation_days=sim_days,
            night_minimum=night_min,
        )
        if not result.get("success"):
            messagebox.showerror("Simulation", result.get("message", "Failed"))
            return
        sim_config = result.get("simulation_config") or {
            "rotation_type": self.sim_rotation.get(),
            "num_officers": num_officers,
            "shift_length_hours": shift_length,
            "annual_hours": annual_hours,
            "shift_starts": shift_starts,
            "min_per_shift": min_shift,
            "apply_department_rules": bool(self.sim_use_rules.get()),
        }
        saved = save_simulator_scenario(
            f"{self.sim_rotation.get()} — {num_officers} officers",
            config=sim_config,
            result=result,
            user_id=self.current_user.get("id") if self.current_user else None,
        )
        if saved.get("success"):
            result["scenario_id"] = saved["scenario_id"]
        self._last_simulation_result = result
        self._render_simulation_results(result)
        self.set_status("Schedule simulation complete")

    def _import_simulation_to_shift_bid(self) -> None:
        if not self.can("shift_bids.manage"):
            messagebox.showwarning("Permission", "You do not have permission to manage shift bids.")
            return
        sim = getattr(self, "_last_simulation_result", None)
        if not sim or not sim.get("success"):
            messagebox.showwarning("Shift Bid", "Run a simulation first, then import the results.")
            return

        preview = build_shift_bid_payload_from_simulation(sim)
        if not preview.get("success"):
            messagebox.showerror("Shift Bid", preview.get("message"))
            return

        dlg = ctk.CTkToplevel(self.root)
        dlg.title("Import Simulation to Shift Bid")
        dlg.geometry("520x480")
        dlg.transient(self.root)
        ctk.CTkLabel(
            dlg,
            text="Create a shift bid draft from the current simulation. Review fields, then save or publish.",
            font=font("small"),
            text_color=UI_TEXT_MUTED,
            wraplength=480,
        ).pack(padx=16, pady=(12, 8), anchor="w")

        form = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=16, pady=4)
        fields = {}
        for label, key in (
            ("Title", "title"),
            ("Number of shifts", "number_of_shifts"),
            ("Shift length", "shift_length"),
            ("Rotation", "rotation"),
            ("Shift start times", "shift_start_times"),
            ("Shifts begin", "shifts_begin"),
            ("Bids due by", "bids_due_by"),
            ("Notes", "notes"),
        ):
            row = ctk.CTkFrame(form, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=label, font=font("small"), width=130, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(row, height=32)
            entry.pack(side="left", fill="x", expand=True)
            entry.insert(0, preview.get(key) or "")
            fields[key] = entry

        squad_row = ctk.CTkFrame(form, fg_color="transparent")
        squad_row.pack(fill="x", pady=3)
        ctk.CTkLabel(squad_row, text="Squad", font=font("small"), width=130, anchor="w").pack(side="left")
        squad_var = ctk.StringVar(value="All")
        ctk.CTkOptionMenu(squad_row, variable=squad_var, values=["All", "A", "B"], width=100).pack(side="left")

        publish_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            form,
            text="Publish to officers immediately",
            variable=publish_var,
            font=font("body"),
        ).pack(anchor="w", pady=(8, 4))

        def submit() -> None:
            overrides = {key: fields[key].get().strip() for key in fields}
            overrides["squad"] = squad_var.get()
            uid = self.current_user.get("id") if self.current_user else None
            result = create_shift_bid_from_simulation(
                sim,
                publish=bool(publish_var.get()),
                user_id=uid,
                **overrides,
            )
            if not result.get("success"):
                messagebox.showerror("Shift Bid", result.get("message"))
                return
            dlg.destroy()
            if result.get("published"):
                messagebox.showinfo(
                    "Shift Bid",
                    f"Published to officers — {result.get('option_count', 0)} shift(s) (ID {result['event_id']})",
                )
            else:
                messagebox.showinfo(
                    "Shift Bid", f"Draft created (ID {result['event_id']}). Publish from Blackout Dates."
                )
            if hasattr(self, "refresh_availability"):
                self.refresh_availability()
            self.set_status("Shift bid imported from simulator")

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=12)
        PrimaryButton(btn_row, text="Create Shift Bid", fg_color=DODGEVILLE_SUCCESS, command=submit).pack(side="left")

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
        backend = result.get("compute_backend") or m.get("compute_backend", "python")
        self.sim_metrics.configure(
            text=(
                f"Coverage {m.get('coverage_percent', 0)}%  ·  "
                f"FTE needed {m.get('fte_required', 0)}  ·  "
                f"Avg annual hours {m.get('avg_annual_hours', 0)}  ·  "
                f"Gap events {m.get('gap_events', 0)}  ·  "
                f"Engine {backend}"
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
