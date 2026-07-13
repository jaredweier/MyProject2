"""Staffing simulator."""

from __future__ import annotations

from nicegui import ui

from config import SIMULATOR_ROTATION_TYPES
from gui import session
from gui.shell import layout, page_header, panel
from logic import (
    create_shift_bid_from_simulation,
    export_simulation_csv,
    format_optimized_plan_view,
    get_last_optimized_plan,
    get_simulator_defaults_from_roster,
    implement_optimized_plan,
    recommend_implement_dates,
    run_schedule_simulation,
    run_staffing_optimizer,
    save_last_optimized_plan,
    save_simulator_scenario,
)
from logic.cp_sat_bridge import (
    demo_week_instance,
    format_solution_report,
    minimize_officer_count,
    ortools_available,
    solve_staffing_feasibility,
)
from logic.staffing_config import (
    get_active_annual_hours_target,
    get_active_annual_hours_variance,
    get_active_shift_length_hours,
    get_active_shift_starts,
    get_target_officer_count,
)
from validators import format_date


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
                    label="Rotation preset",
                ).classes("w-full")
                officers = ui.input(
                    label="Officers (blank = auto minimum)",
                    value=str(get_target_officer_count()),
                ).classes("w-full")
                length = ui.input(
                    label="Shift length hours (0.5 steps)",
                    value=str(get_active_shift_length_hours()),
                ).classes("w-full")
                annual = ui.input(
                    label="Annual hours target", value=str(int(get_active_annual_hours_target()))
                ).classes("w-full")
                annual_var = ui.input(
                    label="Annual hours ± variance",
                    value=str(int(get_active_annual_hours_variance())),
                ).classes("w-full")
                starts = ui.input(label="Shift starts", value=", ".join(get_active_shift_starts())).classes("w-full")
                min_ps = ui.input(label="Min per shift band", value="1").classes("w-full")
                cov247 = ui.input(label="24/7 min officers (0=off)", value="0").classes("w-full")
                days = ui.input(label="Simulation days", value="28").classes("w-full")
                rot_style = ui.select(
                    ["preset", "fixed", "rotating"],
                    value="preset",
                    label="Rotation style",
                ).classes("w-full")
                variations = ui.input(
                    label="Variations (same cycle length; | separates)",
                    value="",
                    placeholder="5-3,6-2 | 5-2,6-3",
                ).classes("w-full")
                avoid_flsa = ui.checkbox("Avoid FLSA overtime (hard)", value=False)
                flsa_days = ui.input(label="FLSA work period days (7–28)", value="28").classes("w-full")

            with panel("Results"):
                out = (
                    ui.textarea(value="Run A Simulation Or Staffing Sweep.")
                    .classes("w-full")
                    .props("outlined dense dark readonly rows=18")
                )
                plan_view = (
                    ui.textarea(value="Optimized plan view appears here after Generate / Optimize.")
                    .classes("w-full")
                    .props("outlined dense dark readonly rows=14")
                )
                last: dict = {"result": None, "config": None}

            with panel("Implement as monthly schedule"):
                rec = recommend_implement_dates()
                rec_raw = rec.get("recommended_date") or ""
                try:
                    rec_date = format_date(rec_raw) if rec_raw else ""
                except Exception:
                    rec_date = rec_raw
                rec_label = rec.get("recommended_label") or ""
                ui.label(f"Recommended start: {rec_label} ({rec.get('reason', '')})").classes("text-sm text-gray-300")
                impl_date = ui.input(
                    label="Implement start date (M/D/YY)",
                    value=rec_date,
                    placeholder="M/D/YY or M-D-YYYY",
                ).classes("w-full")
                with ui.row().classes("gap-2 flex-wrap"):
                    for opt in rec.get("options") or []:
                        d = opt.get("date") or ""
                        try:
                            d_disp = format_date(d) if d else d
                        except Exception:
                            d_disp = d
                        lab = (
                            "★ " + (opt.get("label") or d_disp)
                            if opt.get("recommended")
                            else (opt.get("label") or d_disp)
                        )

                        def _pick(date_val=d_disp):
                            impl_date.value = date_val

                        ui.button(lab, on_click=_pick).classes("btn-ghost").props("no-caps outline dense")
                apply_officers = ui.checkbox("Update officer home shifts/squads from plan", value=True)
                force_regen = ui.checkbox("Regenerate monthly if already published", value=True)

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
                    n_raw = (officers.value or "").strip()
                    n = int(n_raw) if n_raw else 0
                    ln = float((length.value or "0").strip())
                    an = float((annual.value or "0").strip())
                    av = float((annual_var.value or "40").strip())
                    mp = int((min_ps.value or "1").strip())
                    dy = int((days.value or "28").strip())
                    c247 = int((cov247.value or "0").strip())
                    fd = int((flsa_days.value or "28").strip())
                except ValueError:
                    ui.notify("Check numeric fields", type="negative")
                    return
                st = [s.strip() for s in (starts.value or "").replace(";", ",").split(",") if s.strip()]
                vars_raw = (variations.value or "").strip()
                var_list = [p.strip() for p in vars_raw.split("|") if p.strip()] if vars_raw else []
                style = "" if rot_style.value == "preset" else (rot_style.value or "")
                result = run_schedule_simulation(
                    rotation_type=rotation.value,
                    num_officers=n,
                    shift_length_hours=ln,
                    annual_hours_target=an,
                    shift_starts=st,
                    min_per_shift=mp,
                    simulation_days=dy,
                    annual_hours_variance=av,
                    coverage_247=c247,
                    avoid_flsa_overtime=bool(avoid_flsa.value),
                    flsa_work_period_days=fd,
                    rotation_style=style,
                    rotation_variations=var_list,
                    auto_min_officers=(n < 1),
                )
                last["result"] = result
                last["config"] = _current_config()
                if not result.get("success"):
                    ui.notify(result.get("message", "Failed"), type="negative")
                    return
                uid = (session.current_user() or {}).get("id")
                save_last_optimized_plan(result, last["config"], user_id=uid)
                metrics = result.get("metrics") or {}
                lines = ["Simulation complete", "", "Metrics:"]
                for k, v in list(metrics.items())[:24]:
                    lines.append(f"  {k}: {v}")
                lines.extend(["", "Suggestions:"])
                for s in result.get("suggestions") or []:
                    lines.append(f"  [{s.get('severity')}] {s.get('title')}: {s.get('message')}")
                out.value = "\n".join(lines)
                view = format_optimized_plan_view(result, last["config"])
                plan_view.value = view.get("text") or ""
                ui.notify("Simulation complete — plan ready to view/implement", type="positive")

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
                # Re-run full simulation for the best combo so plan has slots + coverage
                try:
                    full = run_schedule_simulation(
                        rotation_type=best["rotation_type"],
                        num_officers=int(best["num_officers"]),
                        shift_length_hours=float(ln or get_active_shift_length_hours()),
                        annual_hours_target=float(an or get_active_annual_hours_target()),
                        shift_starts=st,
                        min_per_shift=int(best["min_per_shift"]),
                        simulation_days=28,
                    )
                    if full.get("success"):
                        last["result"] = full
                        last["config"] = {
                            **_current_config(),
                            "rotation_type": best["rotation_type"],
                            "num_officers": str(best["num_officers"]),
                            "min_per_shift": str(best["min_per_shift"]),
                        }
                        uid = (session.current_user() or {}).get("id")
                        save_last_optimized_plan(full, last["config"], user_id=uid)
                        plan_view.value = format_optimized_plan_view(full, last["config"]).get("text") or ""
                except Exception:
                    pass
                ui.notify(result.get("message", "Optimizer complete"), type="positive")

            def view_plan():
                res = last.get("result")
                cfg = last.get("config")
                if not res:
                    stored = get_last_optimized_plan()
                    if stored:
                        res, cfg = stored.get("result"), stored.get("config")
                if not res:
                    ui.notify("Run Generate or Optimize first", type="warning")
                    return
                view = format_optimized_plan_view(res, cfg)
                plan_view.value = view.get("text") or view.get("message") or ""
                out.value = (out.value or "") + "\n\n— Plan refreshed on screen —"
                ui.notify("Plan view updated", type="info")

            def implement_plan():
                res = last.get("result")
                cfg = last.get("config")
                if not res or not res.get("success"):
                    stored = get_last_optimized_plan()
                    if stored:
                        res, cfg = stored.get("result"), stored.get("config")
                if not res or not res.get("success"):
                    ui.notify("No successful plan to implement", type="warning")
                    return
                uid = (session.current_user() or {}).get("id")
                r = implement_optimized_plan(
                    start_date=(impl_date.value or "").strip(),
                    result=res,
                    config=cfg or _current_config(),
                    user_id=uid,
                    apply_officer_assignments=bool(apply_officers.value),
                    force_regenerate=bool(force_regen.value),
                    save_as_defaults=True,
                )
                ui.notify(
                    r.get("message", "Done") if r.get("success") else r.get("message", "Failed"),
                    type="positive" if r.get("success") else "negative",
                )
                if r.get("success"):
                    plan_view.value = (plan_view.value or "") + f"\n\nIMPLEMENTED: {r.get('message')}"

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
                    n_raw = (officers.value or "").strip()
                    n = int(n_raw) if n_raw else 0
                    dy = int((days.value or "7").strip() or "7")
                    st = [s.strip() for s in (starts.value or "").replace(";", ",").split(",") if s.strip()]
                except ValueError:
                    n, dy, st = 0, 7, ["06:00", "14:00", "22:00"]
                bands = st or ["06:00", "14:00", "22:00"]
                days_list = [f"d{i}" for i in range(min(dy, 14))]
                if n < 1:
                    sol = minimize_officer_count(
                        bands,
                        days_list,
                        min_per_band={b: int((min_ps.value or "1").strip() or "1") for b in bands},
                        max_officers=40,
                        time_limit_sec=3.0,
                    )
                else:
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
                        "min_officers_required": len(sol.officer_ids) if hasattr(sol, "officer_ids") else None,
                        "solver": sol.solver,
                    },
                    "penalties": sol.penalties,
                    "assignment": sol.assignment,
                }
                out.value = format_solution_report(sol)
                ui.notify(
                    sol.message if sol.feasible else sol.message,
                    type="positive" if sol.feasible else "warning",
                )

        with ui.row().classes("gap-2 q-mt-md flex-wrap"):
            ui.button("Load Roster Defaults", on_click=load_defaults).classes("btn-ghost").props("no-caps outline")
            ui.button("Generate Schedule", on_click=run_sim).classes("btn-primary").props("no-caps unelevated")
            ui.button("Find Best Staffing Combination", on_click=run_opt).classes("btn-gold").props(
                "no-caps unelevated"
            )
            ui.button("View optimized plan", on_click=view_plan).classes("btn-ghost").props("no-caps outline")
            ui.button("Implement as monthly", on_click=implement_plan).classes("btn-primary").props(
                "no-caps unelevated"
            )
            ui.button("CP-SAT min officers / week", on_click=run_cpsat).classes("btn-ghost").props(
                "no-caps outline dense"
            )
            ui.button("Save scenario", on_click=save_scenario).classes("btn-ghost").props("no-caps outline dense")
            ui.button("Export CSV", on_click=export_csv).classes("btn-ghost").props("no-caps outline dense")
            if session.can("shift_bids.manage"):
                ui.button("Create bid draft from sim", on_click=bid_from_sim).classes("btn-ghost").props(
                    "no-caps outline dense"
                )

    layout("simulator", body)
