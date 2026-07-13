"""Staffing simulator."""

from __future__ import annotations

from nicegui import ui

from config import SIMULATOR_ROTATION_TYPES
from gui import session
from gui.shell import layout, page_header, panel
from logic import (
    create_shift_bid_from_simulation,
    export_simulation_csv,
    get_simulator_defaults_from_roster,
    run_schedule_simulation,
    run_staffing_optimizer,
    save_simulator_scenario,
)
from logic.cp_sat_bridge import (
    demo_week_instance,
    format_solution_report,
    ortools_available,
    solve_staffing_feasibility,
)
from logic.staffing_config import (
    get_active_annual_hours_target,
    get_active_shift_length_hours,
    get_active_shift_starts,
    get_target_officer_count,
)


def render_simulator() -> None:
    def body() -> None:
        if not session.can("simulator.use"):
            page_header("Schedule Simulator", "Permission Required", kicker="Command")
            ui.html(
                '<div class="alert alert-warn">Schedule Simulator Is Limited To Supervisors.</div>',
                sanitize=False,
            )
            return

        page_header(
            "Schedule Simulator",
            "Model Rotations And Staffing Before You Publish",
            kicker="Command",
        )
        with ui.element("div").classes("grid-2"):
            with panel("Scenario Inputs"):
                rotation = ui.select(
                    list(SIMULATOR_ROTATION_TYPES),
                    value=SIMULATOR_ROTATION_TYPES[0],
                    label="Rotation",
                ).classes("w-full")
                officers = ui.input(label="Officers", value=str(get_target_officer_count())).classes("w-full")
                length = ui.input(label="Shift length (hours)", value=str(get_active_shift_length_hours())).classes(
                    "w-full"
                )
                annual = ui.input(
                    label="Annual hours target", value=str(int(get_active_annual_hours_target()))
                ).classes("w-full")
                starts = ui.input(label="Shift starts", value=", ".join(get_active_shift_starts())).classes("w-full")
                min_ps = ui.input(label="Min per shift", value="1").classes("w-full")
                days = ui.input(label="Simulation days", value="28").classes("w-full")

            with panel("Results"):
                out = (
                    ui.textarea(value="Run A Simulation Or Staffing Sweep.")
                    .classes("w-full")
                    .props("outlined dense dark readonly rows=18")
                )
                last: dict = {"result": None, "config": None}

            def load_defaults():
                d = get_simulator_defaults_from_roster()
                if not d.get("success"):
                    return
                rotation.value = d.get("rotation_type") or SIMULATOR_ROTATION_TYPES[0]
                officers.value = str(d.get("num_officers") or get_target_officer_count())
                length.value = str(d.get("shift_length_hours") or get_active_shift_length_hours())
                annual.value = str(int(d.get("annual_hours_target") or get_active_annual_hours_target()))
                starts.value = d.get("shift_starts") or ", ".join(get_active_shift_starts())
                min_ps.value = str(d.get("min_per_shift") or 1)
                ui.notify("Roster defaults loaded", type="info")

            def _current_config():
                st = [s.strip() for s in (starts.value or "").replace(";", ",").split(",") if s.strip()]
                return {
                    "rotation_type": rotation.value,
                    "num_officers": (officers.value or "").strip(),
                    "shift_length_hours": (length.value or "").strip(),
                    "annual_hours_target": (annual.value or "").strip(),
                    "shift_starts": st,
                    "min_per_shift": (min_ps.value or "").strip(),
                    "simulation_days": (days.value or "").strip(),
                }

            def run_sim():
                try:
                    n = int((officers.value or "0").strip())
                    ln = float((length.value or "0").strip())
                    an = float((annual.value or "0").strip())
                    mp = int((min_ps.value or "1").strip())
                    dy = int((days.value or "28").strip())
                except ValueError:
                    ui.notify("Check numeric fields", type="negative")
                    return
                st = [s.strip() for s in (starts.value or "").replace(";", ",").split(",") if s.strip()]
                result = run_schedule_simulation(
                    rotation_type=rotation.value,
                    num_officers=n,
                    shift_length_hours=ln,
                    annual_hours_target=an,
                    shift_starts=st,
                    min_per_shift=mp,
                    simulation_days=dy,
                )
                last["result"] = result
                last["config"] = _current_config()
                if not result.get("success"):
                    ui.notify(result.get("message", "Failed"), type="negative")
                    return
                metrics = result.get("metrics") or {}
                lines = ["Simulation complete", "", "Metrics:"]
                for k, v in list(metrics.items())[:20]:
                    lines.append(f"  {k}: {v}")
                lines.append("", "Suggestions:")
                for s in result.get("suggestions") or []:
                    lines.append(f"  [{s.get('severity')}] {s.get('title')}: {s.get('message')}")
                out.value = "\n".join(lines)
                ui.notify("Simulation complete", type="positive")

            def run_opt():
                try:
                    ln = float((length.value or "0").strip() or "0") or None
                    an = float((annual.value or "0").strip() or "0") or None
                except ValueError:
                    ln = an = None
                st = [s.strip() for s in (starts.value or "").replace(";", ",").split(",") if s.strip()]
                result = run_staffing_optimizer(
                    shift_length_hours=ln,
                    annual_hours_target=an,
                    shift_starts=st or None,
                    simulation_days=14,
                )
                last["result"] = result
                last["config"] = _current_config()
                if not result.get("success") or not result.get("best"):
                    ui.notify(result.get("message", "No combination found"), type="negative")
                    return
                best = result["best"]
                try:
                    rotation.value = best["rotation_type"]
                except Exception:
                    pass
                officers.value = str(best["num_officers"])
                min_ps.value = str(best["min_per_shift"])
                lines = [result.get("message", "Best staffing found"), "", "Top combinations:"]
                for i, row in enumerate((result.get("ranked") or [])[:8], 1):
                    lines.append(
                        f"{i}. {row['rotation_type']} · {row['num_officers']} officers · "
                        f"min {row['min_per_shift']}/shift · score {row['score']}"
                    )
                out.value = "\n".join(lines)
                ui.notify(result.get("message", "Optimizer complete"), type="positive")

            def save_scenario():
                if not last.get("result"):
                    ui.notify("Run a simulation first", type="warning")
                    return
                uid = (session.current_user() or {}).get("id")
                name = f"Scenario {rotation.value} · {officers.value} off"
                r = save_simulator_scenario(
                    name,
                    config=last.get("config") or _current_config(),
                    result=last.get("result"),
                    user_id=uid,
                    notes="Saved from Chronos simulator",
                )
                ui.notify(
                    r.get("message", "Saved") if r.get("success") else r.get("message", "Save failed"),
                    type="positive" if r.get("success") else "negative",
                )

            def export_csv():
                if not last.get("result"):
                    ui.notify("Run a simulation first", type="warning")
                    return
                r = export_simulation_csv(last["result"])
                if r.get("success"):
                    path = r.get("path") or r.get("output_path") or r.get("file")
                    ui.notify(f"CSV exported{(': ' + str(path)) if path else ''}", type="positive")
                else:
                    ui.notify(r.get("message", "Export failed"), type="negative")

            def bid_from_sim():
                """PowerTime/Snap pattern: promote staffing model into a bid draft."""
                if not last.get("result"):
                    ui.notify("Run a simulation first", type="warning")
                    return
                uid = (session.current_user() or {}).get("id")
                r = create_shift_bid_from_simulation(last["result"], publish=False, user_id=uid)
                if r.get("success"):
                    ui.notify(
                        r.get("message") or f"Bid draft #{r.get('event_id')} created",
                        type="positive",
                    )
                else:
                    ui.notify(r.get("message", "Could not create bid from sim"), type="negative")

            def run_cpsat():
                """OR-Tools shift_scheduling_sat patterns: cover + excess + fairness + transitions."""
                if not ortools_available():
                    ui.notify("Install ortools for CP-SAT (pip install ortools)", type="warning")
                    out.value = "ortools not installed — production path remains coverage_optimizer beam search."
                    return
                try:
                    n = int((officers.value or "8").strip() or "8")
                    dy = int((days.value or "7").strip() or "7")
                except ValueError:
                    n, dy = 8, 7
                inst = demo_week_instance(n_officers=n, n_days=min(dy, 14))
                sol = solve_staffing_feasibility(inst, time_limit_sec=3.0)
                last["result"] = {
                    "success": sol.feasible,
                    "message": sol.message,
                    "metrics": {
                        "feasible": sol.feasible,
                        "objective": sol.objective,
                        "wall_time_sec": sol.wall_time_sec,
                        "penalties": len(sol.penalties),
                    },
                    "penalties": sol.penalties,
                    "assignment": sol.assignment,
                }
                out.value = format_solution_report(sol)
                ui.notify(
                    "CP-SAT feasible" if sol.feasible else sol.message,
                    type="positive" if sol.feasible else "warning",
                )

        with ui.row().classes("gap-2 q-mt-md flex-wrap"):
            ui.button("Load Roster Defaults", on_click=load_defaults).classes("btn-ghost").props("no-caps outline")
            ui.button("Generate Schedule", on_click=run_sim).classes("btn-primary").props("no-caps unelevated")
            ui.button("Find Best Staffing Combination", on_click=run_opt).classes("btn-gold").props(
                "no-caps unelevated"
            )
            ui.button("CP-SAT week (OR-Tools)", on_click=run_cpsat).classes("btn-ghost").props("no-caps outline dense")
            ui.button("Save scenario", on_click=save_scenario).classes("btn-ghost").props("no-caps outline dense")
            ui.button("Export CSV", on_click=export_csv).classes("btn-ghost").props("no-caps outline dense")
            if session.can("shift_bids.manage"):
                ui.button("Create bid draft from sim", on_click=bid_from_sim).classes("btn-ghost").props(
                    "no-caps outline dense"
                )

    layout("simulator", body)
