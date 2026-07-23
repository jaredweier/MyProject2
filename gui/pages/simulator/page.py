"""Schedule Simulator — fixed constraint rows (no layout jump), hard search, publish."""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

from nicegui import run, ui

_OPT_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="staffing-opt")

from config import SIMULATOR_ROTATION_TYPES
from gui import session
from gui.pages.simulator.actions import build_action_handlers
from gui.pages.simulator.decision_table import build_decision_table
from gui.pages.simulator.helpers import (
    _HINT,
    _STEP_DONE,
    _STEP_OFF,
    _STEP_ON,
    _chip_html,
    _kpi_html,
    _set_enabled,
)
from gui.pages.simulator.options_panel import render_options_panel
from gui.pages.simulator.publish_panel import render_publish_panel
from gui.pages.simulator.results_panel import render_results_panel_tools
from gui.pages.simulator.search_flow import open_search_plan_dialog
from gui.pages.simulator.state import SimulatorState
from gui.pages.simulator.stepper_rail import render_stepper_rail
from gui.pages.simulator.styles import apply_simulator_css
from gui.shell import layout, page_header, panel
from gui.ui_patterns import skeleton_block, throttled
from logic import (
    format_optimized_plan_view,
    get_last_optimized_plan,
    get_simulator_scenario,
    implement_optimized_plan,
    list_simulator_scenarios,
    save_last_optimized_plan,
)
from logic.constraint_suggest import (
    suggest_constraint,
)
from logic.manual_schedule_build import (
    cycle_cell_start,
    empty_grid,
    evaluate_manual_grid,
    grid_to_text,
    seed_grid_with_nearby_hops,
    set_cell,
)
from logic.optimizer_features import (
    append_search_history,
    default_weight_map,
    export_form_config_json,
    format_checklist_line,
    load_last_simulator_constraints,
    near_miss_deltas,
    save_form_snapshot,
    shift_coverage_heatmap,
    weights_from_sliders,
    why_best_lines,
)
from logic.plan_explain import explain_ranked_option, explain_staffing_result
from logic.rotation_config import normalize_rotation_preset_name
from logic.scheduling_sim import (
    compare_shift_length_scenarios,
    estimate_staffing_search_space,
    find_min_officers_hard,
    get_simulator_defaults_from_roster,
    run_schedule_simulation,
    run_staffing_optimizer_isolated,
    what_if_staffing_delta,
)
from logic.staffing_insights import (
    detect_constraint_conflicts,
    enrich_option_economics,
    export_staffing_memo,
)
from logic.staffing_optimizer import simulator_understood_lines


def render_simulator() -> None:
    def body() -> None:
        apply_simulator_css(ui)
        if not session.can("simulator.use"):
            page_header("Schedule Simulator", "Permission Required", kicker="Command")
            ui.html(
                '<div class="alert alert-warn">Schedule Simulator Is Limited To Supervisors.</div>',
                sanitize=False,
            )
            return

        page_header(
            "Schedule Simulator",
            "Lock requirements · Find best coverage · Publish",
            kicker="Command",
        )

        state_obj = SimulatorState()
        state = state_obj.to_dict()  # Temporary shim to keep dict access working

        step_labels: dict = {}
        step_panels: dict = {}
        sim_page = ui.element("div").classes("sim-page w-full")
        variations = None
        multi_catalog = None

        def go_step(n: int) -> None:
            state["step"] = n
            try:
                state["max_step_reached"] = max(int(state.get("max_step_reached") or 1), n)
            except Exception:
                state["max_step_reached"] = n
            for i in (1, 2, 3, 4):
                if step_labels.get(i):
                    if i == n:
                        cls = _STEP_ON
                    elif i < n or (i <= int(state.get("max_step_reached") or 1) and i != n):
                        cls = _STEP_DONE if i < n else _STEP_OFF
                    else:
                        cls = _STEP_OFF
                    # visited but not current → done styling only for prior steps
                    if i < n:
                        cls = _STEP_DONE
                    elif i == n:
                        cls = _STEP_ON
                    else:
                        cls = _STEP_OFF
                    step_labels[i].classes(replace=cls)
                if step_panels.get(i):
                    step_panels[i].style("display:block" if i == n else "display:none")
            if n == 2:
                try:
                    _refresh_space_estimate()
                except Exception:
                    pass
                try:
                    _refresh_lock_strip()
                except Exception:
                    pass
            if n == 3:
                try:
                    if _manual_refresh_view:
                        _manual_refresh_view()
                except Exception:
                    pass
            try:
                _refresh_lock_progress()
            except Exception:
                pass

        with sim_page:
            render_stepper_rail(state, step_labels, go_step)

            # Widget placeholders only — real values come from last saved constraints.
            # Do not treat these as product defaults when a snapshot exists.
            _placeholder_rot = SIMULATOR_ROTATION_TYPES[0] if SIMULATOR_ROTATION_TYPES else ""

            # ── Step 1 ─────────────────────────────────────────────────────────
            step1 = ui.element("div").classes("w-full")
            step_panels[1] = step1
            with step1:
                with ui.element("div").classes("sim-quickstart q-mb-sm"):
                    ui.label("Start with a question").classes("sim-section-label")
                    with ui.row().classes("gap-2 flex-wrap"):
                        btn_q_min = (
                            ui.button("Fewest officers that cover this", icon="groups")
                            .classes("btn-primary")
                            .props("no-caps unelevated")
                            .tooltip("Finds the smallest headcount that meets every requirement below")
                        )
                        btn_q_will = (
                            ui.button("Will N officers work?", icon="help_center")
                            .classes("btn-primary")
                            .props("no-caps unelevated")
                            .tooltip("Set a headcount as Given and search for a workable schedule")
                        )
                        btn_q_plus = (
                            ui.button("What does +1 officer buy me?", icon="trending_up")
                            .classes("btn-primary")
                            .props("no-caps unelevated")
                            .tooltip("Compares current headcount against one more officer")
                        )

                ui.label(
                    "Given = your number. Solve for = the optimizer searches it. "
                    "Checked requirements must be satisfied."
                ).style(_HINT)

                def _refresh_lock_progress():
                    # Progress strip removed in the declutter pass — the
                    # Given/Solve-for toggles already show state per row.
                    pass

            with ui.expansion("Advanced requirements", icon="tune").classes("grid-2 sim-adv w-full"):
                ui_elements = render_options_panel(
                    state,
                    _placeholder_rot,
                    lambda: _persist_form(),
                    lambda: _refresh_space_estimate(),
                    lambda *args, **kwargs: _show_constraint_suggestions(*args, **kwargs),
                )
                use_start_date = ui_elements["use_start_date"]
                sim_start_date = ui_elements["sim_start_date"]
                use_rotation = ui_elements["use_rotation"]
                rotation = ui_elements["rotation"]
                use_officers = ui_elements["use_officers"]
                officers = ui_elements["officers"]
                officers_range_lo = ui_elements["officers_range_lo"]
                officers_range_hi = ui_elements["officers_range_hi"]
                use_length = ui_elements["use_length"]
                length = ui_elements["length"]
                use_annual = ui_elements["use_annual"]
                annual = ui_elements["annual"]
                annual_var = ui_elements["annual_var"]
                use_starts = ui_elements["use_starts"]
                starts = ui_elements["starts"]
                use_min_ps = ui_elements["use_min_ps"]
                min_ps = ui_elements["min_ps"]
                use_247 = ui_elements["use_247"]
                cov247 = ui_elements["cov247"]
                use_style = ui_elements["use_style"]
                rot_style = ui_elements["rot_style"]
                multi_catalog = ui_elements["multi_catalog"]
                variations = ui_elements["variations"]
                use_nearby = ui_elements["use_nearby"]
                nearby_hops = ui_elements["nearby_hops"]
                allow_offday = ui_elements["allow_offday"]
                use_certs = ui_elements["use_certs"]
                cert_codes = ui_elements["cert_codes"]
                use_fatigue = ui_elements["use_fatigue"]
                min_rest = ui_elements["min_rest"]
                max_consec = ui_elements["max_consec"]
                use_start_span = ui_elements["use_start_span"]
                max_start_span = ui_elements["max_start_span"]
                prefer_unique_starts = ui_elements["prefer_unique_starts"]
                use_flsa = ui_elements["use_flsa"]
                flsa_days = ui_elements["flsa_days"]
                ot_hourly_rate = ui_elements["ot_hourly_rate"]
                use_windows = ui_elements["use_windows"]
                _refresh_win_list = ui_elements["_refresh_win_list"]
                hint_rotation = ui_elements["hint_rotation"]
                hint_officers = ui_elements["hint_officers"]
                hint_length = ui_elements["hint_length"]
                hint_starts = ui_elements["hint_starts"]
                hint_style = ui_elements["hint_style"]
                win_inputs = ui_elements["win_inputs"]

            def load_defaults():
                """Optional: pull current roster/dept numbers into form (user action only)."""
                d = get_simulator_defaults_from_roster()
                if not d.get("success"):
                    ui.notify(d.get("message") or "No roster defaults", type="warning")
                    return
                if d.get("rotation_type"):
                    try:
                        rotation.value = d["rotation_type"]
                        use_rotation.value = True
                        _set_enabled([rotation], True)
                    except Exception:
                        pass
                if d.get("num_officers") is not None:
                    officers.value = str(d["num_officers"])
                    use_officers.value = True
                    _set_enabled([officers], True)
                if d.get("shift_length_hours") is not None:
                    length.value = str(d["shift_length_hours"])
                    use_length.value = True
                    _set_enabled([length], True)
                if d.get("annual_hours_target") is not None:
                    annual.value = str(int(d["annual_hours_target"]))
                    use_annual.value = True
                    _set_enabled([annual, annual_var], True)
                st = d.get("shift_starts")
                if st:
                    starts.value = ", ".join(st) if isinstance(st, list) else str(st)
                    use_starts.value = True
                    _set_enabled([starts], True)
                if d.get("min_per_shift") is not None:
                    min_ps.value = str(d["min_per_shift"])
                    use_min_ps.value = True
                    _set_enabled([min_ps], True)
                _persist_form()
                ui.notify("Roster values loaded into form (saved)", type="info")

            def save_constraints():
                _persist_form()
                ui.notify("Constraints saved for next session", type="positive")

            with ui.element("div").classes("sim-footer-actions"):
                ui.button("Save constraints", on_click=save_constraints).classes("btn-ghost").props("no-caps outline")
                ui.button(
                    "Load last saved", on_click=lambda: (_restore_form(), ui.notify("Restored last saved", type="info"))
                ).classes("btn-ghost").props("no-caps outline")
                ui.button("Load roster defaults", on_click=load_defaults).classes("btn-ghost").props("no-caps outline")
                ui.button("Suggest values", on_click=lambda: _suggest_next_unlocked()).classes("btn-ghost").props(
                    "no-caps outline"
                )

                def open_load_scenarios():
                    rows = list_simulator_scenarios(limit=20)
                    with (
                        ui.dialog() as dlg,
                        ui.card()
                        .classes("q-pa-md")
                        .style("min-width:22rem;max-width:36rem;background:#0C1A2E;color:#E8EDF4"),
                    ):
                        ui.label("Saved Scenarios").style("font-weight:700;font-size:1.1rem;color:#F8FAFC")
                        if not rows:
                            ui.label("No saved scenarios yet.").style("color:#9AABC4")
                        for row in rows:
                            tags = row.get("tags") or []
                            lab = f"#{row.get('id')} · {row.get('name') or 'Scenario'}" + (
                                f" · {', '.join(tags)}" if tags else ""
                            )

                            def _load(sid=row.get("id")):
                                sc = get_simulator_scenario(int(sid))
                                if not sc:
                                    ui.notify("Not found", type="negative")
                                    return
                                cfg = sc.get("config") or {}
                                res = sc.get("result")
                                if cfg.get("rotation_type"):
                                    try:
                                        rotation.value = cfg["rotation_type"]
                                    except Exception:
                                        pass
                                if cfg.get("num_officers") is not None:
                                    officers.value = str(cfg["num_officers"])
                                    use_officers.value = True
                                if cfg.get("shift_length_hours") is not None:
                                    length.value = str(cfg["shift_length_hours"])
                                if cfg.get("annual_hours_target") is not None:
                                    annual.value = str(int(cfg["annual_hours_target"]))
                                st = cfg.get("shift_starts")
                                if st:
                                    starts.value = ", ".join(st) if isinstance(st, list) else str(st)
                                if cfg.get("min_per_shift") is not None:
                                    min_ps.value = str(cfg["min_per_shift"])
                                if cfg.get("rotation_variations"):
                                    variations.value = " | ".join(cfg["rotation_variations"])
                                    use_style.value = True
                                if cfg.get("extra_windows"):
                                    state["windows"] = list(cfg["extra_windows"])
                                    use_windows.value = True
                                    try:
                                        _refresh_win_list()
                                    except Exception:
                                        pass
                                if res and res.get("success"):
                                    state["result"] = res
                                    state["config"] = cfg
                                dlg.close()
                                ui.notify(f"Loaded scenario #{sid}", type="positive")

                            ui.button(lab[:90], on_click=_load).classes("btn-ghost q-mt-xs").props(
                                "no-caps outline dense align=left"
                            ).style("width:100%;text-align:left")
                        ui.button("Close", on_click=dlg.close).classes("btn-ghost q-mt-sm").props("no-caps outline")
                    dlg.open()

                ui.button("Load saved scenario", on_click=open_load_scenarios).classes("btn-ghost").props(
                    "no-caps outline"
                )
                ui.button(
                    "Continue to find best",
                    icon="travel_explore",
                    on_click=lambda: go_step(2),
                ).classes("btn-primary").props("no-caps unelevated")

            # Live lock progress as checkboxes toggle
            for _lock_cb in (
                use_rotation,
                use_officers,
                use_length,
                use_annual,
                use_starts,
                use_min_ps,
                use_247,
                use_style,
                use_windows,
                use_nearby,
                use_certs,
                use_fatigue,
                use_flsa,
            ):
                try:
                    _lock_cb.on_value_change(lambda e=None: _refresh_lock_progress())
                except Exception:
                    pass
            try:
                _refresh_lock_progress()
            except Exception:
                pass

        # ── Step 2 ─────────────────────────────────────────────────────────
        step2 = ui.element("div").classes("w-full").style("display:none")
        step_panels[2] = step2
        with step2:
            # Decision hero — one primary action region (LE command pattern)
            with ui.element("div").classes("sim-hero"):
                ui.html(
                    '<div class="sim-hero-title">Coverage search</div>'
                    '<p class="sim-hero-sub">'
                    "Mark what you know as Given on Requirements; Solve-for axes are searched. "
                    "Officer count on Solve for always searches 4–20. "
                    "Standard: shift lengths 8/10/12h · Deep: 8–12h in half-hour steps. "
                    "Hard checks always use a 28-day simulation."
                    "</p>",
                    sanitize=False,
                )
                ui.html(
                    '<div class="sim-micro" style="margin-bottom:6px">Active locks</div>',
                    sanitize=False,
                )
                lock_strip = ui.element("div").classes("sim-lock-strip")
                try:
                    from logic.product_complete_pack import hard_pack_headcount_message

                    _hp = hard_pack_headcount_message(7)
                    if _hp.get("message"):
                        ui.label(_hp.get("message") or "").classes("text-xs w-full").style(
                            "color: var(--muted);margin-bottom:8px"
                        )
                except Exception:
                    pass
                with ui.element("div").classes("sim-hero-actions"):
                    # Markers: NiceGUI ElementFilter / tests (llms.txt)
                    btn_opt = (
                        ui.button("Find best", icon="travel_explore")
                        .classes("btn-primary")
                        .props("no-caps unelevated")
                        .mark("sim-find-best")
                    )
                    btn_gen = (
                        ui.button("Generate schedule", icon="calendar_month")
                        .classes("btn-ghost")
                        .props("no-caps outline")
                        .mark("sim-generate")
                    )

                    def _cancel_opt():
                        ev = state.get("opt_cancel")
                        if ev is not None:
                            ev.set()
                            ui.notify("Cancelling search…", type="warning")
                        else:
                            ui.notify("No search running", type="info")

                    ui.button("Cancel search", icon="cancel", on_click=_cancel_opt).classes("btn-ghost").props(
                        "no-caps outline"
                    )
                    with ui.element("div").classes("sim-tool-group"):
                        ui.html(
                            '<span class="sim-tool-group-label">Depth</span>',
                            sanitize=False,
                        )
                        search_depth = (
                            ui.toggle(
                                {"standard": "Standard", "deep": "Deep"},
                                value="standard",
                            )
                            .props("no-caps dense dark")
                            .tooltip(
                                "Both search free officer count exhaustively (4–20). "
                                "Deep additionally uses a denser free-length grid (slower). "
                                "Both use 28-day hard evaluation."
                            )
                        )

                    def _on_depth(e=None):
                        state["search_depth"] = str(getattr(e, "value", None) or search_depth.value or "standard")
                        try:
                            _refresh_space_estimate()
                        except Exception:
                            pass

                    search_depth.on_value_change(_on_depth)
                    mode_label = (
                        ui.label("Mode: hard constraints")
                        .classes("text-xs")
                        .style("color:var(--muted);margin-left:4px")
                    )

                with ui.element("div").classes("sim-hero-secondary"):
                    with ui.element("div").classes("sim-tool-group"):
                        ui.html(
                            '<span class="sim-tool-group-label">Explore</span>',
                            sanitize=False,
                        )
                        btn_compare = (
                            ui.button("Compare 8/10/12h")
                            .classes("btn-ghost")
                            .props("no-caps outline dense")
                            .tooltip("Parallel hard search at 8, 10, 12h")
                        )
                        compare_quick = ui.checkbox("Quick compare", value=True).tooltip(
                            "Faster: 14-day sim, one start pack per length"
                        )
                        btn_min_n = (
                            ui.button("Min officers")
                            .classes("btn-ghost")
                            .props("no-caps outline dense")
                            .tooltip("Binary search smallest N for hard multi-block constraints")
                        )
                        btn_whatif = ui.button("What-if +1 officer").classes("btn-ghost").props("no-caps outline dense")

                    with ui.element("div").classes("sim-tool-group"):
                        ui.html(
                            '<span class="sim-tool-group-label">Search</span>',
                            sanitize=False,
                        )

                        async def soft_search():
                            await _run_opt(require_hard_ok=False)

                        ui.button("Soften search", on_click=soft_search).classes("btn-ghost").props(
                            "no-caps outline dense"
                        )
                        ui.button(
                            "Search history",
                            on_click=lambda: show_search_history(),
                        ).classes("btn-ghost").props("no-caps outline dense")

                    with ui.element("div").classes("sim-tool-group"):
                        ui.html(
                            '<span class="sim-tool-group-label">Jump</span>',
                            sanitize=False,
                        )
                        ui.button("Requirements", on_click=lambda: go_step(1)).classes("btn-ghost").props(
                            "no-caps outline dense"
                        )
                        ui.button("Manual build", on_click=lambda: go_step(3)).classes("btn-ghost").props(
                            "no-caps outline dense"
                        )
                        ui.button("Publish", on_click=lambda: go_step(4)).classes("btn-ghost").props(
                            "no-caps outline dense"
                        )

            search_status_host = ui.element("div").classes("sim-search-status")
            with search_status_host:
                progress_bar = (
                    ui.linear_progress(value=0, show_value=False)
                    .classes("flex-1")
                    .props("color=primary track-color=grey-9 size=8px")
                )
                progress_bar.style("display:none")
                search_spinner = ui.spinner("dots", size="1.6em", color="primary")
                search_spinner.set_visibility(False)
                search_status = ui.label("Ready · hard constraints").classes("text-xs").style("color:var(--muted)")
            kpi_host = ui.element("div").classes("kpi-row q-mb-md")
            with kpi_host:
                ui.html(
                    '<div class="empty-state" style="grid-column:1/-1">'
                    '<div class="empty-state-title">No search yet</div>'
                    '<div class="empty-state-hint">'
                    "Run Find best or Generate schedule. Results land here as KPIs."
                    "</div></div>",
                    sanitize=False,
                )
            skeleton_host = ui.element("div").classes("q-mb-sm")
            skeleton_host.set_visibility(False)
            with skeleton_host:
                # Native NiceGUI skeleton (llms.txt) + Chronos shimmer fallback
                ui.skeleton(type="QToolbar").classes("w-full q-mb-xs")
                ui.skeleton(type="QToolbar").classes("w-full q-mb-xs")
                ui.skeleton(type="text").classes("w-3/4")
                skeleton_block(rows=2, label="Searching layouts…")
            space_warn = ui.element("div").classes("sim-space-warn risk-medium")
            with space_warn:
                ui.label("Select requirements, then open Find best — space size appears here.")

            prio_labels = {
                "coverage_247": "24/7 coverage",
                "windows": "Extra windows",
                "gaps": "Min per shift band",
                "flsa": "FLSA OT avoid",
                "annual": "Annual hours (year-average fairness)",
                "start_changes": "Fewer disruptive start changes",
                "duplicate_starts": "Fewer same-time starts",
                "overcoverage": "Less unnecessary overcoverage",
                "headcount": "Prefer fewer officers",
            }
            prio_col = ui.column().classes("w-full gap-1 q-mb-sm")
            weight_sliders: dict = {}

            def _render_priority():
                prio_col.clear()
                order = list(state.get("constraint_priority") or [])
                with prio_col:
                    for i, key in enumerate(order):
                        with ui.row().classes("gap-2 items-center flex-wrap"):
                            ui.label(f"{i + 1}. {prio_labels.get(key, key)}").style("color:#D6E6FF;min-width:16rem")

                            def _up(idx=i):
                                o = list(state["constraint_priority"])
                                if idx > 0:
                                    o[idx - 1], o[idx] = o[idx], o[idx - 1]
                                    state["constraint_priority"] = o
                                    _render_priority()

                            def _dn(idx=i):
                                o = list(state["constraint_priority"])
                                if idx < len(o) - 1:
                                    o[idx + 1], o[idx] = o[idx], o[idx + 1]
                                    state["constraint_priority"] = o
                                    _render_priority()

                            ui.button("↑", on_click=_up).props("dense flat no-caps").classes("btn-ghost")
                            ui.button("↓", on_click=_dn).props("dense flat no-caps").classes("btn-ghost")

            with ui.expansion(
                "Advanced: priority & weights (near-miss ranking)",
                icon="tune",
            ).classes("sim-adv w-full"):
                ui.label(
                    "When no perfect match, reorder priority (top = most important) "
                    "and tune weights for near-miss ranking."
                ).style(_HINT)
                _render_priority()
                ui.label("Constraint weights").style("color:#E8EDF4;font-weight:600;margin-top:8px")
                with ui.column().classes("w-full gap-1 q-mb-sm"):
                    for wkey, wlabel in (
                        ("coverage_247", "24/7"),
                        ("windows", "Windows"),
                        ("gaps", "Gaps"),
                        ("flsa", "FLSA"),
                        ("annual", "Annual"),
                        ("headcount", "Fewer officers"),
                    ):
                        with ui.row().classes("gap-2 items-center flex-wrap"):
                            ui.label(wlabel).style("color:#D6E6FF;min-width:7rem")
                            sl = (
                                ui.slider(
                                    min=0,
                                    max=120,
                                    value=float((state.get("constraint_weights") or {}).get(wkey, 50)),
                                    step=5,
                                )
                                .classes("w-64")
                                .props("label dark")
                            )
                            weight_sliders[wkey] = sl

                            def _sync_w(e=None, k=wkey, s=sl):
                                state["constraint_weights"] = weights_from_sliders(
                                    {
                                        **(state.get("constraint_weights") or {}),
                                        k: float(s.value or 0),
                                    }
                                )

                            sl.on_value_change(_sync_w)

            def set_space_warn(text: str, *, risk: str = "low"):
                space_warn.clear()
                rk = risk if risk in ("low", "medium", "high", "extreme") else "medium"
                space_warn.classes(replace=f"sim-space-warn risk-{rk}")
                color = {
                    "low": "#A7F3D0",
                    "medium": "#FDE68A",
                    "high": "#FDBA74",
                    "extreme": "#FCA5A5",
                }.get(rk, "#FDE68A")
                with space_warn:
                    ui.label(text or "—").style(f"color:{color};white-space:pre-wrap;line-height:1.45")

            def _refresh_lock_strip():
                lock_strip.clear()
                pairs = [
                    ("Rotation", bool(use_rotation.value)),
                    ("Officers", bool(use_officers.value)),
                    ("Length", bool(use_length.value)),
                    ("Annual", bool(use_annual.value)),
                    ("Starts", bool(use_starts.value)),
                    ("Min/shift", bool(use_min_ps.value)),
                    ("24/7", bool(use_247.value)),
                    ("Multi-block", bool(use_style.value)),
                    ("Windows", bool(use_windows.value)),
                ]
                with lock_strip:
                    for lab, locked in pairs:
                        # Native NiceGUI chips (Quasar) — clearer than custom HTML
                        chip = ui.chip(
                            f"{lab} · {'LOCK' if locked else 'FREE'}",
                            icon="lock" if locked else "lock_open",
                        ).props("dense outline")
                        if locked:
                            chip.props("color=positive text-color=white")
                            chip.classes("sim-ng-chip-on")
                        else:
                            chip.props("color=warning text-color=dark")
                            chip.classes("sim-ng-chip-free")
                    depth = state.get("search_depth") or "standard"
                    ui.chip(
                        f"Search · {depth.upper()}",
                        icon="speed",
                    ).props("dense outline color=primary")

            def _paint_kpis(
                *,
                hard_ok=None,
                officers_n=None,
                layouts=None,
                annual_avg=None,
                window_fails=None,
                mode_text: str = "",
            ):
                try:
                    kpi_host.clear()
                except RuntimeError:
                    return
                except Exception:
                    return
                with kpi_host:
                    if hard_ok is True:
                        tone_h, val_h, hint_h = "g", "OK", "All hard constraints"
                    elif hard_ok is False:
                        tone_h, val_h, hint_h = "d", "MISS", "Near-miss or fail"
                    else:
                        tone_h, val_h, hint_h = "v", "—", mode_text or "Awaiting run"
                    ui.html(
                        _kpi_html("Hard", val_h, hint_h, tone_h)
                        + _kpi_html(
                            "Officers",
                            str(officers_n if officers_n is not None else "—"),
                            "Selected plan N",
                            "v",
                        )
                        + _kpi_html(
                            "Layouts",
                            f"{int(layouts):,}" if layouts is not None else "—",
                            "Checked (exhaustive)",
                            "v",
                        )
                        + _kpi_html(
                            "Annual avg",
                            f"{float(annual_avg):.0f}" if annual_avg is not None else "—",
                            "Hours / year",
                            "w"
                            if annual_avg is not None and abs(float(annual_avg) - 2008) > 20
                            else "g"
                            if annual_avg is not None
                            else "v",
                        )
                        + _kpi_html(
                            "Windows",
                            str(window_fails if window_fails is not None else "—"),
                            "Extra-window shortfalls",
                            "d" if window_fails else "g" if window_fails == 0 else "v",
                        ),
                        sanitize=False,
                    )

            ui.html('<div class="sim-section-title">Summary</div>', sanitize=False)
            summary_box = ui.element("div").classes("sim-result-panel")
            ui.html(
                '<div class="sim-section-title" style="margin-top:12px">Why #1 / tips</div>',
                sanitize=False,
            )
            why_box = ui.element("div").classes("sim-result-panel").style("min-height:3rem;max-height:10rem")

            # Secondary tools grouped into 4 menus (Phase 6) — every former
            # strip button lives on, one level down. Handlers are late-bound
            # closures: defined further below in body(), resolved at click.
            with ui.row().classes("gap-2 flex-wrap q-mt-sm items-center"):
                btn_apply_month = (
                    ui.button("Apply winner → draft month").classes("btn-primary").props("no-caps unelevated dense")
                )
                with (
                    ui.dropdown_button("Compare", icon="compare_arrows")
                    .classes("btn-ghost")
                    .props("no-caps outline dense")
                ):
                    ui.menu_item("Diff A vs B", on_click=lambda: run_diff_ab())
                    ui.menu_item("Sensitivity (+N / night)", on_click=lambda: run_sensitivity())
                    ui.menu_item("CP-SAT (small N)", on_click=lambda: run_cpsat_small())
                with (
                    ui.dropdown_button("Explain", icon="psychology").classes("btn-ghost").props("no-caps outline dense")
                ):
                    ui.menu_item("Plain English explain", on_click=lambda: run_plain_explain())
                    ui.menu_item("Fairness report", on_click=lambda: run_fairness())
                    ui.menu_item("Weekend heat", on_click=lambda: show_weekend_heat())
                    ui.menu_item("Heat map (PNG)", on_click=lambda: do_heat())
                    ui.menu_item("Window failures", on_click=lambda: do_window_drill())
                with ui.dropdown_button("Export", icon="ios_share").classes("btn-ghost").props("no-caps outline dense"):
                    ui.menu_item("Options CSV", on_click=lambda: export_options())
                    ui.menu_item("Search audit JSON", on_click=lambda: export_audit())
                    ui.menu_item("Staffing memo", on_click=lambda: export_memo())
                    ui.menu_item("Config JSON", on_click=lambda: export_config())
                    ui.menu_item("Share best (.eml)", on_click=lambda: do_share())
                    ui.menu_item("Copy summary", on_click=lambda: copy_summary())
                with (
                    ui.dropdown_button("Scenarios", icon="inventory_2")
                    .classes("btn-ghost")
                    .props("no-caps outline dense")
                ):
                    ui.menu_item("Save → A", on_click=lambda: save_slot("A"))
                    ui.menu_item("Save → B", on_click=lambda: save_slot("B"))
                    ui.menu_item("Save → C", on_click=lambda: save_slot("C"))
                    ui.menu_item("Open A/B/C", on_click=lambda: show_slots())
                    ui.menu_item("Pin selected", on_click=lambda: do_pin())
                    ui.menu_item("Pinned list", on_click=lambda: show_pins())
                    ui.menu_item("Lock selected as seed", on_click=lambda: lock_selected_seed())
                    ui.menu_item("Import config JSON", on_click=lambda: import_config())
                    ui.menu_item("Import live constraints", on_click=lambda: run_import_live())

            # Decision table paints here after every search (primary output)
            decision_host = ui.element("div").classes("w-full q-mt-sm")
            inline_heat_host = ui.element("div").classes("w-full q-mt-sm")

            def _paint_inline_heatmap():
                inline_heat_host.clear()
                hm = shift_coverage_heatmap(state.get("result") or {})
                if not hm.get("success"):
                    return
                matrix = hm.get("matrix") or []
                days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                with inline_heat_host:
                    ui.label("Coverage heatmap (average officers, 2-hour blocks)").classes("sim-section-title")
                    with ui.element("div").classes("sim-inline-heatmap"):
                        for day_index, day in enumerate(days):
                            row = matrix[day_index] if day_index < len(matrix) else []
                            values = [
                                round(sum(row[i : i + 4]) / max(1, len(row[i : i + 4])), 1) for i in range(0, 48, 4)
                            ]
                            ui.label(day).classes("sim-heat-day")
                            for value in values:
                                tone = "thin" if value < 1 else "ok" if value < 2 else "strong"
                                ui.label(str(value)).classes(f"sim-heat-cell {tone}")

            # Splitter: ranked options | plan detail (NiceGUI layout primitive)
            with ui.splitter(value=52).classes("w-full sim-split q-mt-sm") as result_split:
                with result_split.before:
                    ui.html(
                        '<div class="sim-section-title">Coverage options</div>',
                        sanitize=False,
                    )
                    ui.label("Select one · mark A/B for diff · click card to load").style(_HINT)
                    # scroll_area + refreshable = NiceGUI llms.txt list pattern
                    with ui.scroll_area().classes("w-full").style("height: 22rem; max-height: 50vh;"):

                        @ui.refreshable
                        def options_ui() -> None:
                            ranked = list(state.get("ranked") or [])
                            selected = int(state.get("selected_rank") or 1)
                            if not ranked:
                                ui.html(
                                    '<div class="empty-state">'
                                    '<div class="empty-state-title">No coverage options yet</div>'
                                    '<div class="empty-state-hint">'
                                    "Run Find best — ranked plans appear here with hard/near-miss chips."
                                    "</div></div>",
                                    sanitize=False,
                                )
                                return
                            for row in ranked[:10]:
                                rank = int(row.get("rank") or 0)
                                detail_lines = explain_ranked_option(row)
                                check = format_checklist_line(row)
                                if check:
                                    detail_lines = [check] + detail_lines
                                deltas = near_miss_deltas(row)
                                if deltas and not row.get("hard_constraints_ok"):
                                    detail_lines.append("Missed by: " + "; ".join(deltas[:3]))
                                if row.get("suggestions"):
                                    detail_lines.append(row.get("suggestions"))
                                summary = row.get("summary") or (
                                    f"{row.get('rotation_type')} · "
                                    f"{row.get('num_officers')} officers · "
                                    f"Min {row.get('min_per_shift')} per shift"
                                )
                                body = "\n".join(detail_lines[:8]) if detail_lines else summary
                                try:
                                    cost_rate = float((ot_hourly_rate.value or "35").strip() or 35)
                                except ValueError:
                                    cost_rate = 35.0
                                economics = enrich_option_economics(row, hourly_rate=cost_rate).get("economics") or {}
                                if economics.get("est_ot_cost_usd") is not None:
                                    body += (
                                        f"\nEstimated OT: ${float(economics['est_ot_cost_usd']):,.0f} "
                                        f"({float(economics.get('est_ot_hours_total') or 0):.1f}h)"
                                    )
                                hard = row.get("hard_constraints_ok")
                                if hard is None:
                                    hard = (row.get("human_metrics") or {}).get("hard_constraints_ok")
                                active = rank == selected
                                is_a = state.get("compare_a") is row or (
                                    (state.get("compare_a") or {}).get("rank") == rank and state.get("compare_a")
                                )
                                is_b = state.get("compare_b") is row or (
                                    (state.get("compare_b") or {}).get("rank") == rank and state.get("compare_b")
                                )
                                chips = []
                                if active:
                                    chips.append(_chip_html("Selected", "info"))
                                if hard is True:
                                    chips.append(_chip_html("Hard OK", "ok"))
                                elif hard is False:
                                    chips.append(_chip_html("Near-miss", "warn"))
                                chips.append(_chip_html(f"N={row.get('num_officers') or '—'}", "info"))
                                if row.get("shift_length_hours") is not None:
                                    chips.append(_chip_html(f"{row.get('shift_length_hours')}h", "info"))
                                if is_a:
                                    chips.append(_chip_html("Diff A", "info"))
                                if is_b:
                                    chips.append(_chip_html("Diff B", "info"))

                                def _select(r=row, rk=rank):
                                    state["selected_row"] = r
                                    state["selected_rank"] = rk
                                    _apply_ranked_option(r)
                                    options_ui.refresh()
                                    try:
                                        set_why("\n".join(why_best_lines({"best": r, "ranked": ranked})))
                                    except Exception:
                                        pass
                                    try:
                                        m = r.get("metrics") or r.get("human_metrics") or {}
                                        _paint_kpis(
                                            hard_ok=r.get("hard_constraints_ok"),
                                            officers_n=r.get("num_officers"),
                                            layouts=None,
                                            annual_avg=m.get("avg_annual_hours"),
                                            window_fails=m.get("extra_window_failures"),
                                            mode_text="Selected option",
                                        )
                                    except Exception:
                                        pass

                                def _mark_a(r=row):
                                    state["compare_a"] = r
                                    ui.notify(f"Option {r.get('rank')} → Diff A", type="info")
                                    options_ui.refresh()

                                def _mark_b(r=row):
                                    state["compare_b"] = r
                                    ui.notify(f"Option {r.get('rank')} → Diff B", type="info")
                                    options_ui.refresh()

                                card = ui.element("div").classes(
                                    "sim-option-card active" if active else "sim-option-card"
                                )
                                card.props(
                                    f'tabindex="0" role="button" '
                                    f'aria-pressed="{"true" if active else "false"}" '
                                    f'aria-label="Coverage option {rank}"'
                                )
                                with card:
                                    ui.html(
                                        f'<div class="sim-option-head">'
                                        f'<span class="sim-option-rank">#{rank}</span>'
                                        f'<span class="sim-option-title">Option {rank}</span>'
                                        f"{''.join(chips)}</div>",
                                        sanitize=False,
                                    )
                                    ui.label(body).classes("sim-option-body")
                                    with ui.row().classes("gap-2 q-mt-xs flex-wrap sim-option-actions"):
                                        ui.button("Load", icon="check", on_click=_select).classes("btn-primary").props(
                                            "dense no-caps unelevated"
                                        )
                                        ui.button("Mark A", on_click=_mark_a).classes("btn-ghost").props(
                                            "dense no-caps outline"
                                        )
                                        ui.button("Mark B", on_click=_mark_b).classes("btn-ghost").props(
                                            "dense no-caps outline"
                                        )
                                card.on("click", _select)
                                card.on("keydown.enter", _select)

                        options_ui()
                with result_split.after:
                    ui.html(
                        '<div class="sim-section-title">Plan detail</div>',
                        sanitize=False,
                    )
                    with ui.scroll_area().classes("w-full").style("height: 22rem; max-height: 50vh;"):
                        plan_box = ui.element("div").classes("sim-result-panel")

            def _ui_safe(fn) -> None:
                """Ignore updates after client disconnect (Cloudflare tunnel blips)."""
                try:
                    fn()
                except RuntimeError as exc:
                    msg = str(exc).lower()
                    if "deleted" in msg or "client" in msg:
                        return
                    raise
                except Exception:
                    return

            def set_summary(text: str):
                def _do():
                    summary_box.clear()
                    with summary_box:
                        ui.label(text or "—").style("color:#E8EDF4;white-space:pre-wrap;line-height:1.5")

                _ui_safe(_do)

            def set_why(text: str = ""):
                def _do():
                    why_box.clear()
                    with why_box:
                        ui.label(text or "—").style(
                            "color:#D6E6FF;white-space:pre-wrap;line-height:1.45;font-size:0.9rem"
                        )

                _ui_safe(_do)

            # Bound rendered plan text so one label can't blow up a WebSocket
            # frame (the raised 10MB cap in gui/app.py stays as safety net,
            # but should no longer be load-bearing). Full text stays in
            # state["plan_full_text"] server-side for exports.
            _PLAN_RENDER_CAP = 60_000  # chars ≈ well under default 1MB frame

            def set_plan(text: str):
                def _do():
                    full = text or "—"
                    state["plan_full_text"] = full
                    shown = full
                    if len(full) > _PLAN_RENDER_CAP:
                        shown = (
                            full[:_PLAN_RENDER_CAP]
                            + "\n… (view truncated — use Export › Options CSV / Staffing memo for the full plan)"
                        )
                    plan_box.clear()
                    with plan_box:
                        ui.label(shown).style("color:#D6E6FF;white-space:pre-wrap;line-height:1.45")

                _ui_safe(_do)

            set_summary("Run Find best or Generate schedule.")
            set_plan(
                "Plan detail appears after a successful run.\n"
                "Ranked options and Why #1 explain hard-constraint tradeoffs."
            )
            _paint_kpis(mode_text="Hard constraints · ready")

        # ── Step 3 · Manual Build ──────────────────────────────────────────
        step3 = ui.element("div").classes("w-full").style("display:none")
        step_panels[3] = step3
        with step3:
            with panel("Manual schedule builder"):
                ui.label(
                    "Build any schedule by editing officer × day cells. "
                    "Seed from rotation ON days, then override freely. "
                    "Evaluate hard constraints, then send to publish."
                ).style(_HINT)
                with ui.row().classes("gap-2 flex-wrap items-end"):
                    man_days = ui.input(label="Days In Grid", value="14").classes("w-32")
                    man_officer = ui.input(label="Officer # (1-based)", value="1").classes("w-32")
                    man_day = ui.input(label="Day # (0-based)", value="0").classes("w-32")
                    man_start = ui.input(
                        label="Start (HH:MM or OFF)",
                        value="OFF",
                        placeholder="19:00 or OFF",
                    ).classes("w-40")
                man_grid_box = ui.element("div").classes("sim-grid-host")
                man_eval_box = ui.element("div").classes("sim-result-panel").style("min-height:3rem;")

                def _manual_n_officers() -> int:
                    try:
                        n = int((officers.value or "").strip() or "0")
                    except ValueError:
                        n = 0
                    return max(n, 1)

                def _manual_starts_list() -> list:
                    st = _parse_starts()
                    return st if st else ["06:00", "14:00", "19:00", "22:00"]

                def _manual_set_eval(text: str):
                    man_eval_box.clear()
                    with man_eval_box:
                        ui.label(text or "—").style("color:#D6E6FF;white-space:pre-wrap;line-height:1.45")

                def manual_new_empty():
                    try:
                        days = max(1, min(56, int((man_days.value or "14").strip() or "14")))
                    except ValueError:
                        days = 14
                    state["manual_days"] = days
                    state["manual_grid"] = empty_grid(_manual_n_officers(), days)
                    _manual_refresh_view()
                    _manual_set_eval(f"Empty grid {_manual_n_officers()} officers × {days} days")
                    ui.notify("Empty grid ready", type="info")

                def manual_seed_rotation():
                    base = _baseline_kwargs()
                    if base.get("error"):
                        ui.notify(base["error"], type="negative")
                        return
                    try:
                        days = max(1, min(56, int((man_days.value or "14").strip() or "14")))
                    except ValueError:
                        days = 14
                    n = _manual_n_officers()
                    hops = int(base.get("nearby_start_hops") or 0)
                    r = seed_grid_with_nearby_hops(
                        num_officers=n,
                        num_days=days,
                        shift_starts=_manual_starts_list(),
                        rotation_type=base.get("rotation_type") or "",
                        rotation_style=base.get("rotation_style") or "rotating",
                        rotation_variations=base.get("rotation_variations") or [],
                        nearby_hops=hops,
                        respect_off_days=True,
                    )
                    state["manual_grid"] = r.get("grid")
                    state["manual_days"] = days
                    _manual_refresh_view()
                    _manual_set_eval(r.get("message") or "Seeded")
                    ui.notify(r.get("message") or "Seeded", type="positive")

                def _manual_refresh_view():
                    grid = state.get("manual_grid")
                    man_grid_box.clear()
                    with man_grid_box:
                        if not grid:
                            ui.label("No grid yet. Use Seed From Rotation or New Empty Grid.").style("color:#9AABC4")
                            return
                        ui.label(grid_to_text(grid, max_days=14)).style(
                            "color:#E8EDF4;white-space:pre;font-size:0.85rem;"
                        )
                        ui.label("Click a cell button to cycle OFF → pack starts (editable).").style(
                            "color:#9AABC4;font-size:0.8rem;margin-top:8px"
                        )
                        pack = _manual_starts_list()
                        show_days = min(len(grid[0]), 14)
                        show_off = min(len(grid), 12)
                        for oi in range(show_off):
                            with ui.element("div").classes("sim-grid-row"):
                                ui.html(
                                    f'<span class="sim-grid-label">O{oi + 1}</span>',
                                    sanitize=False,
                                )
                                for di in range(show_days):
                                    val = grid[oi][di] or "OFF"
                                    is_off = str(val).upper() in ("OFF", "", "NONE")

                                    def _cycle(o=oi, d=di):
                                        g = state.get("manual_grid")
                                        if not g:
                                            return
                                        r = cycle_cell_start(g, o, d, pack)
                                        if r.get("success"):
                                            state["manual_grid"] = r["grid"]
                                            _manual_refresh_view()

                                    cell_cls = (
                                        "btn-ghost sim-cell-btn sim-cell-off"
                                        if is_off
                                        else "btn-ghost sim-cell-btn sim-cell-on"
                                    )
                                    ui.button(
                                        str(val)[:5],
                                        on_click=_cycle,
                                    ).classes(cell_cls).props("dense no-caps outline size=sm").tooltip(
                                        f"Officer {oi + 1} · day {di}"
                                    )
                        if len(grid) > show_off or len(grid[0]) > show_days:
                            ui.label(
                                f"Showing {show_off}×{show_days} of {len(grid)}×{len(grid[0])} "
                                "(use Set Cell for full edit)."
                            ).style("color:#7A8FA8;font-size:0.75rem")

                def manual_set_cell():
                    grid = state.get("manual_grid")
                    if not grid:
                        ui.notify("Create a grid first", type="warning")
                        return
                    try:
                        oi = int((man_officer.value or "1").strip()) - 1
                        di = int((man_day.value or "0").strip())
                    except ValueError:
                        ui.notify("Bad officer/day", type="negative")
                        return
                    raw = (man_start.value or "OFF").strip()
                    r = set_cell(grid, oi, di, raw)
                    if not r.get("success"):
                        ui.notify(r.get("message") or "Failed", type="negative")
                        return
                    state["manual_grid"] = r["grid"]
                    _manual_refresh_view()
                    ui.notify(f"O{oi + 1} day {di} → {raw}", type="info")

                def manual_evaluate():
                    grid = state.get("manual_grid")
                    if not grid:
                        ui.notify("No grid", type="warning")
                        return
                    base = _baseline_kwargs()
                    if base.get("error"):
                        ui.notify(base["error"], type="negative")
                        return
                    sh_len = base.get("shift_length_hours")
                    if sh_len is None:
                        try:
                            sh_len = float((length.value or "").strip())
                        except Exception:
                            sh_len = None
                    if sh_len is None:
                        ui.notify("Lock shift length on Requirements first", type="warning")
                        return
                    result = evaluate_manual_grid(
                        grid,
                        shift_length_hours=float(sh_len),
                        coverage_247=int(base.get("coverage_247") or 0),
                        use_extra_windows=bool(base.get("use_extra_windows")),
                        extra_windows=list(base.get("extra_windows") or []),
                        annual_hours_target=float(base.get("annual_hours_target") or 0)
                        if base.get("annual_hours_target") is not None
                        else 0.0,
                        annual_hours_variance=float(base.get("annual_hours_variance") or 0)
                        if base.get("annual_hours_variance") is not None
                        else 0.0,
                        annual_hours_hard=bool(base.get("annual_hours_hard")),
                        rotation_type=base.get("rotation_type") or "",
                        rotation_style=base.get("rotation_style") or "",
                        rotation_variations=list(base.get("rotation_variations") or []),
                        nearby_start_hops=int(base.get("nearby_start_hops") or 0),
                        allow_offday_coverage=bool(base.get("allow_offday_coverage")),
                    )
                    if not result.get("success"):
                        ui.notify(result.get("message") or "Eval failed", type="negative")
                        return
                    m = result.get("metrics") or {}
                    lines = [
                        result.get("message") or "Evaluated",
                        f"Hard OK: {m.get('hard_constraints_ok')}",
                        f"24/7 shortfalls: {m.get('coverage_247_failures')}",
                        f"Window shortfalls: {m.get('extra_window_failures')}",
                        f"Avg annual (from grid): {m.get('avg_annual_hours')}",
                    ]
                    _manual_set_eval("\n".join(lines))
                    ui.notify("Manual schedule evaluated", type="positive")

                def manual_use_plan():
                    grid = state.get("manual_grid")
                    if not grid:
                        ui.notify("No grid", type="warning")
                        return
                    base = _baseline_kwargs()
                    if base.get("error"):
                        ui.notify(base["error"], type="negative")
                        return
                    sh_len = base.get("shift_length_hours")
                    if sh_len is None:
                        try:
                            sh_len = float((length.value or "").strip())
                        except Exception:
                            ui.notify("Lock shift length first", type="warning")
                            return
                    result = evaluate_manual_grid(
                        grid,
                        shift_length_hours=float(sh_len),
                        coverage_247=int(base.get("coverage_247") or 0),
                        use_extra_windows=bool(base.get("use_extra_windows")),
                        extra_windows=list(base.get("extra_windows") or []),
                        annual_hours_target=float(base.get("annual_hours_target") or 0)
                        if base.get("annual_hours_target") is not None
                        else 0.0,
                        annual_hours_variance=float(base.get("annual_hours_variance") or 0)
                        if base.get("annual_hours_variance") is not None
                        else 0.0,
                        annual_hours_hard=bool(base.get("annual_hours_hard")),
                        rotation_type=base.get("rotation_type") or "",
                        rotation_style=base.get("rotation_style") or "",
                        rotation_variations=list(base.get("rotation_variations") or []),
                        nearby_start_hops=int(base.get("nearby_start_hops") or 0),
                        allow_offday_coverage=bool(base.get("allow_offday_coverage")),
                    )
                    if not result.get("success"):
                        ui.notify(result.get("message") or "Failed", type="negative")
                        return
                    state["result"] = result
                    state["config"] = result.get("simulation_config") or _current_config()
                    uid = (session.current_user() or {}).get("id")
                    save_last_optimized_plan(result, state["config"], user_id=uid)
                    view = format_optimized_plan_view(result, state["config"])
                    try:
                        set_plan(view.get("text") or result.get("message") or "")
                        set_summary(result.get("message") or "Manual plan ready")
                    except Exception:
                        pass
                    _manual_set_eval((result.get("message") or "OK") + "\nPlan stored — go to Publish.")
                    ui.notify("Manual plan ready for Publish", type="positive")
                    go_step(4)

                with ui.row().classes("gap-2 flex-wrap q-mt-md"):
                    ui.button("New Empty Grid", on_click=manual_new_empty).classes("btn-ghost").props("no-caps outline")
                    ui.button("Seed From Rotation (ON Days)", on_click=manual_seed_rotation).classes(
                        "btn-primary"
                    ).props("no-caps unelevated")
                    ui.button("Set Cell", on_click=manual_set_cell).classes("btn-ghost").props("no-caps outline")
                    ui.button("Evaluate", on_click=manual_evaluate).classes("btn-ghost").props("no-caps outline")
                    ui.button("Use as plan → publish", on_click=manual_use_plan).classes("btn-primary").props(
                        "no-caps unelevated"
                    )
                with ui.row().classes("gap-2 flex-wrap q-mt-sm"):
                    ui.button("Back to find best", on_click=lambda: go_step(2)).classes("btn-ghost").props(
                        "no-caps outline"
                    )
                    ui.button("Back to requirements", on_click=lambda: go_step(1)).classes("btn-ghost").props(
                        "no-caps outline"
                    )

        # ── Step 4 · Publish ───────────────────────────────────────────────
        step4, step4_elements = render_publish_panel(state, go_step)
        step_panels[4] = step4

        # Extract elements needed below
        impl_date = step4_elements["impl_date"]
        apply_officers = step4_elements["apply_officers"]
        force_regen = step4_elements["force_regen"]
        save_defaults = step4_elements["save_defaults"]
        set_action_log = step4_elements["set_action_log"]
        btn_impl = step4_elements["btn_impl"]
        btn_preview = step4_elements["btn_preview"]
        btn_apply_stay = step4_elements["btn_apply_stay"]
        btn_apply_pub = step4_elements["btn_apply_pub"]
        btn_save = step4_elements["btn_save"]
        btn_csv = step4_elements["btn_csv"]
        btn_bid = step4_elements["btn_bid"]

        def _on_lock_with_suggest(field: str, enable_fn, widget_lock_flag):
            """enable_fn enables inputs on lock toggle. No auto-popups here:
            suggestions open only from the explicit Suggest button (P0.1 —
            auto-suggest on lock/focus caused stacked, self-reopening dialogs)."""

            def _handler(e=None):
                on = bool(widget_lock_flag.value)
                enable_fn(on)
                try:
                    _refresh_space_estimate()
                except Exception:
                    pass
                try:
                    _persist_form()
                except Exception:
                    pass

            return _handler

        # Re-bind locks so enabling a constraint offers context-aware suggestions
        def _en_rot(on: bool):
            _set_enabled([rotation], on)
            hint_rotation.set_visibility(not on)

        def _en_off(on: bool):
            _set_enabled([officers], on)
            hint_officers.set_visibility(not on)

        def _en_len(on: bool):
            _set_enabled([length], on)
            hint_length.set_visibility(not on)

        def _en_ann(on: bool):
            _set_enabled([annual, annual_var], on)

        def _en_st(on: bool):
            _set_enabled([starts], on)
            hint_starts.set_visibility(not on)

        def _en_mp(on: bool):
            _set_enabled([min_ps], on)

        def _en_247(on: bool):
            _set_enabled([cov247], on)

        def _en_style(on: bool):
            _set_enabled([rot_style, multi_catalog, variations], on)
            hint_style.set_visibility(not on)

        def _en_near(on: bool):
            _set_enabled([nearby_hops], on)

        def _en_flsa(on: bool):
            _set_enabled([flsa_days], on)

        use_rotation.on_value_change(_on_lock_with_suggest("rotation", _en_rot, use_rotation))
        use_officers.on_value_change(_on_lock_with_suggest("officers", _en_off, use_officers))
        use_length.on_value_change(_on_lock_with_suggest("length", _en_len, use_length))
        use_annual.on_value_change(_on_lock_with_suggest("annual", _en_ann, use_annual))
        use_starts.on_value_change(_on_lock_with_suggest("starts", _en_st, use_starts))
        use_min_ps.on_value_change(_on_lock_with_suggest("min_ps", _en_mp, use_min_ps))
        use_247.on_value_change(_on_lock_with_suggest("coverage_247", _en_247, use_247))
        use_style.on_value_change(_on_lock_with_suggest("variations", _en_style, use_style))
        use_nearby.on_value_change(_on_lock_with_suggest("nearby", _en_near, use_nearby))
        use_flsa.on_value_change(_on_lock_with_suggest("flsa", _en_flsa, use_flsa))

        def _on_windows_lock(e=None):
            _set_enabled(win_inputs, bool(use_windows.value))
            try:
                _persist_form()
            except Exception:
                pass

        use_windows.on_value_change(_on_windows_lock)

        def _on_offday_lock(e=None):
            try:
                _persist_form()
            except Exception:
                pass

        allow_offday.on_value_change(_on_offday_lock)
        use_fatigue.on_value_change(lambda e: _set_enabled([min_rest, max_consec], bool(use_fatigue.value)))

        # P0.1: focus-triggered suggestion popups removed — closing a dialog
        # returned focus to the field, which immediately re-opened the dialog
        # (the "popup trap"). Suggestions are explicit-only now.

        def _suggest_next_unlocked():
            """Popup for the first unlocked common field given current locks."""
            order = [
                ("length", use_length),
                ("annual", use_annual),
                ("starts", use_starts),
                ("officers", use_officers),
                ("variations", use_style),
                ("coverage_247", use_247),
                ("windows", use_windows),
                ("nearby", use_nearby),
            ]
            for name, lock in order:
                if not lock.value:
                    _show_constraint_suggestions(name, force=True)
                    return
            _show_constraint_suggestions("officers", force=True)

        # Suggestions are reachable only via the explicit "Suggest values"
        # button in the Requirements footer (wired to _suggest_next_unlocked).

        def _nums():
            """Parse locked fields only. Empty locked field → error. Unlocked → None."""
            try:
                n = None
                if use_officers.value:
                    raw = (officers.value or "").strip()
                    if not raw:
                        return None, None, None, None, None, None, None, "Officer count required when locked"
                    n = int(raw)
                ln = None
                if use_length.value:
                    raw = (length.value or "").strip()
                    if not raw:
                        return None, None, None, None, None, None, None, "Shift length required when locked"
                    ln = float(raw)
                an = None
                av = None
                if use_annual.value:
                    raw_a = (annual.value or "").strip()
                    raw_v = (annual_var.value or "").strip()
                    if not raw_a:
                        return None, None, None, None, None, None, None, "Annual hours required when locked"
                    an = float(raw_a)
                    av = float(raw_v) if raw_v else 0.0
                mp = None
                if use_min_ps.value:
                    raw = (min_ps.value or "").strip()
                    if not raw:
                        return None, None, None, None, None, None, None, "Min per shift required when locked"
                    mp = int(raw)
                c247 = None
                if use_247.value:
                    raw = (cov247.value or "").strip()
                    if not raw:
                        return None, None, None, None, None, None, None, "24/7 minimum required when locked"
                    c247 = int(raw)
                fd = None
                if use_flsa.value:
                    raw = (flsa_days.value or "").strip()
                    fd = int(raw) if raw else 28
                return n, ln, an, av, mp, c247, fd, None
            except ValueError as exc:
                return None, None, None, None, None, None, None, str(exc)

        def _parse_starts() -> list:
            text = starts.value or ""
            return [s.strip() for s in text.replace(";", ",").split(",") if s.strip()]

        def _parse_nearby_hops() -> int:
            if not bool(use_nearby.value):
                return 0
            try:
                raw = (nearby_hops.value or "").strip()
                if not raw:
                    return 0
                return max(0, min(6, int(raw)))
            except (TypeError, ValueError):
                return 0

        def _style_value() -> str:
            if not use_style.value:
                return ""
            return "rotating" if (rot_style.value or "").lower().startswith("rotat") else "fixed"

        def _var_sets() -> list:
            """All manually-entered rotation sets — one per non-empty line, each
            line's patterns pipe-separated. Every set is tried by the search."""
            if not use_style.value:
                return []
            sets = []
            for line in (variations.value or "").splitlines():
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if parts:
                    sets.append(parts)
            return sets

        def _var_list() -> list:
            """The first/only rotation set — for call sites that re-simulate one
            exact scenario (manual editor, publish, applying a chosen result)."""
            sets = _var_sets()
            return sets[0] if sets else []

        def _baseline_kwargs() -> dict:
            n, ln, an, av, mp, c247, fd, err = _nums()
            if err:
                return {"error": err}
            st = _parse_starts() if use_starts.value else []
            if use_starts.value and not st:
                return {"error": "Shift starts required when locked"}
            if use_rotation.value and not (rotation.value or "").strip():
                return {"error": "Rotation pattern required when locked"}
            # Unlocked dimensions: free for search / neutral for single sim
            return {
                "rotation_type": (rotation.value if use_rotation.value else (rotation.value or _placeholder_rot)),
                "num_officers": int(n) if use_officers.value and n and n >= 1 else 0,
                "auto_min_officers": not use_officers.value or not n or n < 1,
                "shift_length_hours": float(ln) if use_length.value and ln is not None else None,
                "annual_hours_target": float(an) if use_annual.value and an is not None else None,
                "annual_hours_variance": float(av) if use_annual.value and av is not None else None,
                "annual_hours_hard": bool(use_annual.value and state.get("hard_mode", True)),
                "shift_starts": st if use_starts.value else None,
                "min_per_shift": int(mp) if use_min_ps.value and mp is not None else 1,
                "simulation_days": 56,
                "coverage_247": int(c247) if use_247.value and c247 is not None else 0,
                "sim_start_date": sim_start_date.value if use_start_date.value else None,
                "avoid_flsa_overtime": bool(use_flsa.value),
                "flsa_work_period_days": int(fd) if use_flsa.value and fd is not None else 28,
                "rotation_style": _style_value(),
                "rotation_variations": _var_list(),
                "use_extra_windows": bool(use_windows.value and state["windows"]),
                "extra_windows": list(state["windows"]) if use_windows.value else [],
                "apply_department_rules": False,
                "stagger_phases": True,
                "nearby_start_hops": _parse_nearby_hops(),
                "allow_offday_coverage": bool(allow_offday.value),
                "min_rest_hours": (float((min_rest.value or "0").strip() or 0) if use_fatigue.value else 0.0),
                "max_consecutive_work_days": (
                    int(float((max_consec.value or "0").strip() or 0)) if use_fatigue.value else 0
                ),
                "required_cert_codes": (
                    [c.strip() for c in (cert_codes.value or "").replace(";", ",").split(",") if c.strip()]
                    if use_certs.value
                    else []
                ),
            }

        def _optimizer_kwargs(*, require_hard_ok: bool) -> dict:
            n, ln, an, av, mp, c247, fd, err = _nums()
            if err:
                return {"error": err}
            free_starts = not use_starts.value
            free_lengths = not use_length.value
            free_officers = not (use_officers.value and n is not None and n >= 1)
            if not free_officers:
                off_counts = [int(n)]
            else:
                # Unselected officer count must search the full realistic
                # range, not a narrow band around a guessed hint — a hint-based
                # band could sit entirely outside the true viable range and
                # cause Find Best to report "impossible" when a valid option
                # actually exists just outside the band. Standard vs Deep still
                # controls length-grid density below (a genuinely continuous
                # dimension), but headcount is a small, cheap-to-enumerate
                # integer axis, so both depths search it exhaustively.
                # Range is user-editable (Range Min/Max) — no longer fixed to
                # 4-20; falls back to that default only if the fields are blank
                # or invalid.
                try:
                    lo = int((officers_range_lo.value or "4").strip())
                except ValueError:
                    lo = 4
                try:
                    hi = int((officers_range_hi.value or "20").strip())
                except ValueError:
                    hi = 20
                lo, hi = max(1, min(lo, hi)), max(lo, hi)
                off_counts = list(range(lo, hi + 1))
            # Unselected shift length must search the full 8-12.5h half-hour
            # grid regardless of depth (AGENTS.md: "if off, all shift lengths
            # in range of 8 and 12.5 hours in .5 hour increments should be
            # considered" — narrowing by depth could miss the only viable
            # length, same failure shape as the officer-count banding bug).
            length_opts = None
            if free_lengths:
                length_opts = [8.0, 8.5, 9.0, 9.5, 10.0, 10.5, 11.0, 11.5, 12.0, 12.5]
            st = _parse_starts() if use_starts.value else None
            hard_inputs = []
            soft_inputs = []
            open_inputs = []

            def _item(key, label, *, value=None, domain=None):
                item = {"key": key, "label": label}
                if value is not None:
                    item["value"] = value
                if domain is not None:
                    item["domain"] = domain
                return item

            if free_officers:
                open_inputs.append(_item("officer_count", "Officer count", domain=off_counts))
            else:
                hard_inputs.append(_item("officer_count", f"Officer count = {int(n)}", value=int(n)))
            if free_lengths:
                open_inputs.append(_item("shift_length", "Shift length", domain=length_opts))
            else:
                hard_inputs.append(_item("shift_length", f"Shift length = {float(ln):g}h", value=float(ln)))
            open_inputs.append(
                _item(
                    "shift_starts",
                    "Shift starts from allowed domain" if st else "Shift starts",
                    domain=st or "solver-generated",
                )
            )
            if use_rotation.value:
                hard_inputs.append(_item("rotation", f"Rotation = {rotation.value}", value=rotation.value))
            else:
                open_inputs.append(_item("rotation", "Rotation pattern", domain="available presets"))
            if use_style.value and _var_sets():
                open_inputs.append(_item("rotation_variation", "Pattern variation", domain=_var_sets()))
            if use_annual.value and an is not None:
                target_item = _item("annual_hours", f"Annual hours = {float(an):g} +/- {float(av or 0):g}", value=an)
                (hard_inputs if require_hard_ok else soft_inputs).append(target_item)
            if use_min_ps.value and mp is not None:
                hard_inputs.append(_item("min_per_shift", f"Minimum per shift = {int(mp)}", value=int(mp)))
            if use_247.value and c247 is not None:
                hard_inputs.append(_item("coverage_247", f"24/7 minimum = {int(c247)}", value=int(c247)))
            if use_windows.value and state["windows"]:
                hard_inputs.append(_item("coverage_windows", f"Coverage windows ({len(state['windows'])})"))
            if use_fatigue.value:
                if (min_rest.value or "").strip():
                    hard_inputs.append(_item("min_rest", f"Minimum rest = {min_rest.value}h"))
                if (max_consec.value or "").strip():
                    hard_inputs.append(_item("max_consecutive", f"Maximum consecutive days = {max_consec.value}"))
            if use_start_span.value:
                hard_inputs.append(_item("max_start_span", f"Maximum start span = {max_start_span.value}h"))
            if prefer_unique_starts.value:
                soft_inputs.append(_item("unique_daily_starts", "Fewer same-time starts"))
            required_certs = (
                [code.strip() for code in (cert_codes.value or "").replace(";", ",").split(",") if code.strip()]
                if use_certs.value
                else []
            )
            if required_certs:
                hard_inputs.append(_item("certifications", "Required certifications: " + ", ".join(required_certs)))
            return {
                "rotation_types": [rotation.value] if use_rotation.value else None,
                "officer_counts": off_counts,
                "min_per_shift_options": [int(mp)] if use_min_ps.value and mp is not None else None,
                "shift_length_hours": float(ln) if use_length.value and ln is not None else None,
                "shift_length_options": length_opts,
                "annual_hours_target": float(an) if use_annual.value and an is not None else None,
                "shift_starts": st,
                "free_starts": free_starts,
                "free_lengths": free_lengths,
                "free_officer_counts": free_officers,
                "free_variations": not use_style.value or not _var_sets(),
                # Always 28-day hard eval — shorter windows can false-green lean N
                "simulation_days": 56,
                "coverage_247": int(c247) if use_247.value and c247 is not None else 0,
                "sim_start_date": sim_start_date.value if use_start_date.value else None,
                "avoid_flsa_overtime": bool(use_flsa.value),
                "flsa_work_period_days": int(fd) if use_flsa.value and fd is not None else 28,
                "annual_hours_variance": float(av) if use_annual.value and av is not None else None,
                "annual_hours_hard": bool(use_annual.value and require_hard_ok),
                "use_extra_windows": bool(use_windows.value and state["windows"]),
                "extra_windows": list(state["windows"]) if use_windows.value else [],
                "require_hard_ok": require_hard_ok,
                "rotation_style": _style_value(),
                "rotation_variations": _var_list(),
                "rotation_variation_sets": _var_sets(),
                "stagger_phases": True,
                "nearby_start_hops": _parse_nearby_hops(),
                "allow_offday_coverage": bool(allow_offday.value),
                "min_rest_hours": (float((min_rest.value or "0").strip() or 0) if use_fatigue.value else 0.0),
                "max_consecutive_work_days": (
                    int(float((max_consec.value or "0").strip() or 0)) if use_fatigue.value else 0
                ),
                "max_start_variation_hours": (
                    float((max_start_span.value or "").strip()) if use_start_span.value else None
                ),
                "prefer_unique_daily_starts": bool(prefer_unique_starts.value),
                "input_roles": {
                    "hard_constraints": hard_inputs,
                    "soft_preferences": soft_inputs,
                    "open_variables": open_inputs,
                },
                "warm_start": ((state.get("opt_result") or {}).get("best") or None),
                "required_cert_codes": required_certs,
                "constraint_priority": list(state.get("constraint_priority") or []),
                "constraint_weights": dict(state.get("constraint_weights") or default_weight_map()),
                # P0.3: every UI-launched search is time-boxed; best-so-far is
                # returned at the budget with budget_exhausted=True. Deep gets
                # a longer leash. Multi-hour runs must be an explicit opt-in.
                "time_budget_seconds": 300.0 if state.get("search_depth") == "deep" else 120.0,
            }

        def _refresh_space_estimate():
            kw = _optimizer_kwargs(require_hard_ok=bool(state.get("hard_mode", True)))
            if kw.get("error"):
                set_space_warn(f"Fix numbers: {kw['error']}", risk="high")
                return None
            kw.pop("error", None)
            est = estimate_staffing_search_space(
                **{
                    k: v
                    for k, v in kw.items()
                    if k
                    not in (
                        "require_hard_ok",
                        "annual_hours_hard",
                        "annual_hours_variance",
                        "annual_hours_target",
                        "coverage_247",
                        "avoid_flsa_overtime",
                        "flsa_work_period_days",
                        "simulation_days",
                        "constraint_priority",
                        "constraint_weights",
                        "min_rest_hours",
                        "max_consecutive_work_days",
                        "allow_offday_coverage",
                        "nearby_start_hops",
                        "require_hard_ok",
                    )
                }
            )
            state["space_estimate"] = est
            risk = est.get("risk") or "low"
            lines = [
                est.get("warning") or "",
                f"Layouts In Space: {int(est.get('total_layouts') or 0):,}",
                f"Free Dimensions: {', '.join(est.get('free_dimensions') or []) or 'none (fully locked)'}",
            ]
            if est.get("requires_confirm"):
                lines.append(
                    "Confirm before Find Best — this can take a long time. "
                    "Lock officer count / starts / length if possible."
                )
            set_space_warn("\n".join(lines), risk=risk)
            return est

        def _current_config():
            base = _baseline_kwargs()
            base.pop("error", None)
            base.pop("auto_min_officers", None)
            base.pop("stagger_phases", None)
            return base

        def _human_metrics(metrics: dict) -> list[str]:
            lines = []
            for label, key in (
                ("Coverage Percent", "coverage_percent"),
                ("Coverage Gaps", "gap_events"),
                ("Constraints Met", "hard_constraints_ok"),
                ("24/7 Shortfalls", "coverage_247_failures"),
                ("Window Shortfalls", "extra_window_failures"),
                ("Avg Annual Hours", "avg_annual_hours"),
                ("Officers Used", "min_officers_required"),
                ("Nearby Start Bumps", "nearby_start_hops"),
                ("Off-Day Coverage On", "allow_offday_coverage"),
                ("Off-Day Assignments", "offday_coverage_assignments"),
            ):
                if key in (metrics or {}):
                    lines.append(f"{label}: {metrics[key]}")
            return lines

        def _load_option(row: dict):
            """Select + load a ranked option (decision table and cards share this)."""
            state["selected_row"] = row
            state["selected_rank"] = int(row.get("rank") or 1)
            _apply_ranked_option(row)
            try:
                options_ui.refresh()
            except Exception:
                pass
            try:
                set_why("\n".join(why_best_lines({"best": row, "ranked": list(state.get("ranked") or [])})))
            except Exception:
                pass
            try:
                m = row.get("metrics") or row.get("human_metrics") or {}
                _paint_kpis(
                    hard_ok=row.get("hard_constraints_ok"),
                    officers_n=row.get("num_officers"),
                    layouts=None,
                    annual_avg=m.get("avg_annual_hours"),
                    window_fails=m.get("extra_window_failures"),
                    mode_text="Selected option",
                )
            except Exception:
                pass

        async def _run_stress_test():
            from logic.staffing_insights import absence_stress_test

            top = list(state.get("ranked") or [])[:3]
            if not top:
                return
            kw = _baseline_kwargs()
            kw.pop("error", None)
            ui.notify("Stress-testing top options (1 officer out)…", type="info")

            def _work():
                return {int(r.get("rank") or 0): absence_stress_test(r, kw) for r in top}

            try:
                state["stress_results"] = await run.io_bound(_work)
            except Exception as exc:
                ui.notify(f"Stress test failed: {exc}", type="negative")
                return
            _paint_decision_table()
            _paint_inline_heatmap()
            ui.notify("Stress test done", type="positive")

        def _paint_decision_table():
            try:
                _, _, an, _, _, _, fd, _ = _nums()
            except Exception:
                an, fd = None, None
            try:
                build_decision_table(
                    decision_host,
                    list(state.get("ranked") or []),
                    on_load=_load_option,
                    annual_target=an,
                    flsa_period_days=int(fd or 28),
                    hourly_rate=float((ot_hourly_rate.value or "35").strip() or 35),
                    on_stress_test=lambda: asyncio.create_task(_run_stress_test()),
                    stress_results=state.get("stress_results") or {},
                )
            except Exception:
                pass

        def _render_ranked(ranked: list, selected: int = 1):
            """Update ranked list state + refresh NiceGUI local-scope options_ui."""
            state["ranked"] = list(ranked or [])
            state["selected_rank"] = int(selected or 1)
            state["stress_results"] = {}  # stale after any new search
            try:
                options_ui.refresh()
            except Exception:
                pass
            _paint_decision_table()

        def _apply_ranked_option(row: dict):
            try:
                rt = row.get("rotation_type") or rotation.value
                rotation.value = normalize_rotation_preset_name(rt) if rt else rotation.value
            except Exception:
                pass
            if row.get("num_officers") is not None:
                officers.value = str(row["num_officers"])
            if row.get("min_per_shift") is not None:
                min_ps.value = str(row["min_per_shift"])
            if row.get("shift_length_hours") is not None:
                length.value = str(row["shift_length_hours"])
            if row.get("annual_hours_target") is not None:
                annual.value = str(int(row["annual_hours_target"]))
            st = row.get("shift_starts")
            if st:
                starts.value = ", ".join(st) if isinstance(st, list) else str(st)
            if row.get("rotation_variations"):
                variations.value = " | ".join(row["rotation_variations"])
                use_style.value = True

            base = _baseline_kwargs()
            if base.get("error"):
                ui.notify(f"Check Numbers: {base['error']}", type="negative")
                return
            ph = row.get("phase_overrides")
            pm = row.get("pattern_slot_map")
            home_starts = row.get("officer_home_starts")
            cycle_starts = row.get("officer_cycle_starts")
            full = run_schedule_simulation(
                rotation_type=row.get("rotation_type") or base["rotation_type"],
                num_officers=int(row.get("num_officers") or base["num_officers"] or 0),
                shift_length_hours=float(row.get("shift_length_hours") or base["shift_length_hours"]),
                annual_hours_target=float(row.get("annual_hours_target") or base["annual_hours_target"]),
                shift_starts=list(row.get("shift_starts") or base["shift_starts"]),
                min_per_shift=int(
                    row["min_per_shift"] if row.get("min_per_shift") is not None else base["min_per_shift"]
                ),
                simulation_days=112 if cycle_starts else 56,
                annual_hours_variance=float(base["annual_hours_variance"]),
                annual_hours_hard=bool(base["annual_hours_hard"]),
                coverage_247=int(base["coverage_247"]),
                avoid_flsa_overtime=bool(base["avoid_flsa_overtime"]),
                flsa_work_period_days=int(base["flsa_work_period_days"]),
                rotation_style=base["rotation_style"] or row.get("rotation_style") or "",
                rotation_variations=list(row.get("rotation_variations") or base["rotation_variations"]),
                auto_min_officers=False,
                apply_department_rules=False,
                use_extra_windows=bool(base["use_extra_windows"]),
                extra_windows=list(base["extra_windows"]),
                # Replay optimizer layout exactly when present
                stagger_phases=bool(ph is None and pm is None),
                phase_overrides=list(ph) if isinstance(ph, (list, tuple)) else None,
                pattern_slot_map=list(pm) if isinstance(pm, (list, tuple)) else None,
                officer_home_starts=list(home_starts) if isinstance(home_starts, (list, tuple)) else None,
                officer_cycle_starts=(
                    [list(days) for days in cycle_starts] if isinstance(cycle_starts, (list, tuple)) else None
                ),
                # A full CP-SAT solve proved this exact per-officer start pins the
                # windows/24-7 result — day-pool rebalancing (hops>0) would silently
                # depart from the proven assignment, so force it off when replaying one.
                nearby_start_hops=(0 if (home_starts or cycle_starts) else int(base.get("nearby_start_hops") or 0)),
                allow_offday_coverage=bool(base.get("allow_offday_coverage")),
            )
            if full.get("success"):
                state["result"] = full
                state["config"] = _current_config()
                _paint_inline_heatmap()
                uid = (session.current_user() or {}).get("id")
                save_last_optimized_plan(full, state["config"], user_id=uid)
                view = format_optimized_plan_view(full, state["config"])
                set_plan(view.get("text") or full.get("message") or "")
                ui.notify(f"Using Option {row.get('rank')}", type="positive")
            else:
                ui.notify(full.get("message") or "Could Not Build Plan", type="warning")

        def _show_no_match_dialog(
            evaluated: int,
            rejected: int,
            extra: str = "",
            near_misses: list | None = None,
        ):
            with (
                ui.dialog() as dlg,
                ui.card()
                .classes("q-pa-md")
                .style(
                    "min-width:24rem;max-width:36rem;background:#0C1A2E;color:#E8EDF4;"
                    "border:1px solid rgba(91,141,239,0.4)"
                ),
            ):
                ui.label("No Perfect Schedule").style("font-size:1.15rem;font-weight:700;color:#F8FAFC")
                body = (
                    "No plan meets every selected hard requirement after checking "
                    f"{evaluated or rejected:,} layout(s) ({rejected:,} ruled out).\n\n"
                    "Annual hours use a year-average (365.25-day) model — officers will not "
                    "all work identical hours in a calendar year when cycles do not divide "
                    "365/366 evenly; the optimizer looks for similar hours across the roster.\n\n"
                    "Closest alternatives (if any) are listed below. Reorder Constraint "
                    "Priority above, then search again to re-rank tradeoffs."
                )
                if extra:
                    body += f"\n\n{extra}"
                ui.label(body).style("color:#9AABC4;margin:12px 0;line-height:1.45;white-space:pre-wrap")

                from logic.optimizer_features import suggest_relaxations

                sugs = suggest_relaxations(state.get("opt_result") or {}, state.get("config") or {})

                def _last_int(text: str):
                    import re

                    nums = re.findall(r"\d+", text or "")
                    return int(nums[-1]) if nums else None

                def _apply_relaxation(s: dict) -> bool:
                    """Apply one suggested relaxation to the form. True if applied."""
                    cat = (s.get("category") or "").lower()
                    action = s.get("action") or ""
                    delta = s.get("delta") or ""
                    if cat == "headcount":
                        n = _last_int(action)
                        if not n:
                            return False
                        officers.value = str(n)
                        use_officers.value = True
                        _en_off(True)
                        return True
                    if cat == "coverage_247":
                        n = _last_int(delta) or _last_int(action)
                        if n is None:
                            return False
                        cov247.value = str(max(0, n))
                        return True
                    if cat == "annual_hours":
                        n = _last_int(delta)
                        if not n:
                            return False
                        annual_var.value = str(n)
                        return True
                    if cat == "window":
                        n = _last_int(delta)
                        if n is None:
                            return False
                        import re

                        mlab = re.search(r"'([^']+)'", action)
                        lab = mlab.group(1) if mlab else ""
                        wins = list(state.get("windows") or [])
                        for w in wins:
                            if isinstance(w, dict) and (not lab or w.get("label") == lab):
                                w["min_officers"] = n
                                break
                        else:
                            return False
                        state["windows"] = wins
                        try:
                            _refresh_win_list()
                        except Exception:
                            pass
                        return True
                    if cat == "gaps":
                        if use_starts.value:
                            cur = _parse_starts()
                            if "19:00" not in cur:
                                starts.value = ", ".join([*cur, "19:00"])
                        return True
                    if cat == "general":
                        use_officers.value = False
                        _en_off(False)
                        use_starts.value = False
                        _en_st(False)
                        return True
                    return False

                if sugs:
                    ui.label("Fix it with one click").style("color:#86efac;font-weight:600;margin-top:4px")
                    for s in sugs[:3]:

                        async def _try_fix(sg=s):
                            if not _apply_relaxation(sg):
                                ui.notify("Could not auto-apply — adjust the form manually", type="warning")
                                return
                            dlg.close()
                            _persist_form()
                            ui.notify(f"Applied: {sg.get('delta') or sg.get('action')}", type="info")
                            await _run_opt(require_hard_ok=True)

                        ui.button(
                            f"{s.get('action', '')}",
                            icon="auto_fix_high",
                            on_click=_try_fix,
                        ).classes("btn-primary q-mt-xs").props("no-caps unelevated align=left dense").style(
                            "width:100%;text-align:left;white-space:normal"
                        )
                        ui.label(s.get("why", "")).style(
                            "color:#9AABC4;font-size:0.85rem;margin-bottom:8px;margin-left:14px"
                        )

                misses = list(near_misses or [])[:5]
                if misses:
                    ui.label("Closest Alternatives").style("color:#E8EDF4;font-weight:600;margin-top:10px")
                    for nm in misses:

                        def _pick(row=nm):
                            dlg.close()
                            _apply_ranked_option(row)
                            _render_ranked(
                                [{"rank": 1, **row, "summary": row.get("summary")}],
                                selected=1,
                            )
                            set_summary(
                                "Loaded Near-Miss Alternative (does not meet all hard constraints).\n"
                                + (row.get("summary") or "")
                            )

                        ui.button(
                            (nm.get("summary") or "Alternative")[:120],
                            on_click=_pick,
                        ).classes("btn-ghost q-mt-xs").props("no-caps outline dense align=left").style(
                            "width:100%;text-align:left;white-space:normal"
                        )

                async def _soften():
                    dlg.close()
                    state["hard_mode"] = False
                    mode_label.set_text("Mode: Softened (Best Effort)")
                    await _run_opt(require_hard_ok=False)

                async def _research():
                    dlg.close()
                    await _run_opt(require_hard_ok=True)

                def _cancel():
                    dlg.close()
                    set_summary(
                        "No Schedule Meets Selected Hard Constraints.\n"
                        "Use closest alternatives, change priority order, or soften."
                    )

                with ui.row().classes("gap-2 flex-wrap q-mt-md"):
                    ui.button("Search Again With Current Priority", on_click=_research).classes("btn-primary").props(
                        "no-caps unelevated"
                    )
                    ui.button("Soften & Search", on_click=_soften).classes("btn-ghost").props("no-caps outline")
                    ui.button("Close", on_click=_cancel).classes("btn-ghost").props("no-caps outline")
            dlg.open()

        def _constraint_context() -> dict:
            """Currently locked form values for suggestion engine."""
            return {
                "use_rotation": bool(use_rotation.value),
                "rotation": getattr(rotation, "value", None),
                "use_officers": bool(use_officers.value),
                "officers": officers.value,
                "use_length": bool(use_length.value),
                "length": length.value,
                "use_annual": bool(use_annual.value),
                "annual": annual.value,
                "annual_var": annual_var.value,
                "use_starts": bool(use_starts.value),
                "starts": starts.value,
                "use_min_ps": bool(use_min_ps.value),
                "min_ps": min_ps.value,
                "use_247": bool(use_247.value),
                "cov247": cov247.value,
                "use_style": bool(use_style.value),
                "variations": variations.value,
                "rot_style": getattr(rot_style, "value", None),
                "use_windows": bool(use_windows.value),
                "windows": list(state.get("windows") or []),
                "use_nearby": bool(use_nearby.value),
                "nearby_hops": nearby_hops.value,
                "allow_offday": bool(allow_offday.value),
                "use_flsa": bool(use_flsa.value),
                "flsa_days": flsa_days.value,
                "ot_hourly_rate": ot_hourly_rate.value,
                "use_fatigue": bool(use_fatigue.value),
                "min_rest": min_rest.value,
                "max_consec": max_consec.value,
                "use_start_span": bool(use_start_span.value),
                "max_start_span": max_start_span.value,
                "prefer_unique_starts": bool(prefer_unique_starts.value),
                "use_certs": bool(use_certs.value),
                "required_certs": (cert_codes.value if use_certs.value else ""),
            }

        def _apply_suggest_values(values: dict) -> None:
            if not values:
                return

            def _has_value(*keys: str) -> bool:
                # A lock may only be restored as locked if every value it needs
                # actually came back with it — otherwise the form reloads into a
                # stuck "locked but empty" state that blocks Find Best with a
                # silent "Fix numbers" error until the user notices and manually
                # unlocks it.
                for k in keys:
                    v = values.get(k)
                    if v is None or (isinstance(v, str) and not v.strip()):
                        return False
                return True

            state["suppress_suggest"] = True
            try:
                if values.get("rotation"):
                    try:
                        rotation.value = values["rotation"]
                    except Exception:
                        pass
                if "use_rotation" in values:
                    use_rotation.value = bool(values["use_rotation"]) and _has_value("rotation")
                    _set_enabled([rotation], bool(use_rotation.value))
                if values.get("officers") is not None:
                    officers.value = str(values["officers"])
                if "use_officers" in values:
                    use_officers.value = bool(values["use_officers"]) and _has_value("officers")
                    _set_enabled([officers], bool(use_officers.value))
                if values.get("length") is not None:
                    length.value = str(values["length"])
                if "use_length" in values:
                    use_length.value = bool(values["use_length"]) and _has_value("length")
                    _set_enabled([length], bool(use_length.value))
                if values.get("annual") is not None:
                    annual.value = str(values["annual"])
                if values.get("annual_var") is not None:
                    annual_var.value = str(values["annual_var"])
                if "use_annual" in values:
                    use_annual.value = bool(values["use_annual"]) and _has_value("annual")
                    _set_enabled([annual, annual_var], bool(use_annual.value))
                if values.get("starts") is not None:
                    starts.value = str(values["starts"])
                if "use_starts" in values:
                    use_starts.value = bool(values["use_starts"]) and _has_value("starts")
                    _set_enabled([starts], bool(use_starts.value))
                if values.get("min_ps") is not None:
                    min_ps.value = str(values["min_ps"])
                if "use_min_ps" in values:
                    use_min_ps.value = bool(values["use_min_ps"]) and _has_value("min_ps")
                    _set_enabled([min_ps], bool(use_min_ps.value))
                if values.get("cov247") is not None:
                    cov247.value = str(values["cov247"])
                if "use_247" in values:
                    use_247.value = bool(values["use_247"]) and _has_value("cov247")
                    _set_enabled([cov247], bool(use_247.value))
                if values.get("variations") is not None:
                    variations.value = str(values["variations"])
                if values.get("rot_style"):
                    try:
                        rot_style.value = values["rot_style"]
                    except Exception:
                        pass
                if "use_style" in values:
                    use_style.value = bool(values["use_style"]) and _has_value("variations")
                    _set_enabled([rot_style, multi_catalog, variations], bool(use_style.value))
                if "use_windows" in values:
                    use_windows.value = bool(values["use_windows"])
                if "windows" in values:
                    state["windows"] = list(values.get("windows") or [])
                    try:
                        _refresh_win_list()
                    except Exception:
                        pass
                if values.get("nearby_hops") is not None:
                    nearby_hops.value = str(values["nearby_hops"])
                if "use_nearby" in values:
                    use_nearby.value = bool(values["use_nearby"]) and _has_value("nearby_hops")
                    _set_enabled([nearby_hops], bool(use_nearby.value))
                if "allow_offday" in values:
                    allow_offday.value = bool(values["allow_offday"])
                if values.get("flsa_days") is not None:
                    flsa_days.value = str(values["flsa_days"])
                if "use_flsa" in values:
                    use_flsa.value = bool(values["use_flsa"])
                    _set_enabled([flsa_days], bool(use_flsa.value))

                try:
                    _refresh_space_estimate()
                except Exception:
                    pass
                _persist_form()
            finally:
                state["suppress_suggest"] = False

        def _show_constraint_suggestions(field: str, *, force: bool = False) -> None:
            if state.get("restoring_form") or state.get("suppress_suggest"):
                return
            # Only one suggestion dialog at a time (P0.1: stacked dialogs trap)
            prev = state.get("suggest_dialog")
            if prev is not None:
                try:
                    prev.close()
                except Exception:
                    pass
                state["suggest_dialog"] = None
            ctx = _constraint_context()
            # Only guide when other constraints already locked (or forced Help)
            field_flags = {
                "rotation": "use_rotation",
                "officers": "use_officers",
                "length": "use_length",
                "annual": "use_annual",
                "starts": "use_starts",
                "min_ps": "use_min_ps",
                "coverage_247": "use_247",
                "variations": "use_style",
                "style": "use_style",
                "windows": "use_windows",
                "nearby": "use_nearby",
                "flsa": "use_flsa",
                "offday": "allow_offday",
            }
            self_flag = field_flags.get((field or "").lower())
            other_flags = (
                "use_rotation",
                "use_officers",
                "use_length",
                "use_annual",
                "use_starts",
                "use_min_ps",
                "use_247",
                "use_style",
                "use_windows",
                "use_nearby",
                "use_flsa",
                "allow_offday",
            )
            other_locked = any(bool(ctx.get(k)) for k in other_flags if k != self_flag)
            if not force and not other_locked:
                return
            # Suggest from other locks; temporarily clear self so engine ignores empty new field
            ctx_for = dict(ctx)
            if self_flag:
                ctx_for[self_flag] = False
            sugg = suggest_constraint(field, ctx_for)
            opts = list(sugg.get("options") or [])
            if not opts and not force:
                return

            with (
                ui.dialog() as dlg,
                ui.card()
                .classes("q-pa-md")
                .style(
                    "min-width:22rem;max-width:34rem;background:#0C1A2E;color:#E8EDF4;"
                    "border:1px solid rgba(91,141,239,0.45)"
                ),
            ):
                ui.label(sugg.get("title") or "Suggestions").style("font-weight:700;font-size:1.1rem;color:#F8FAFC")
                ui.label(sugg.get("explanation") or "").style(
                    "color:#9AABC4;font-size:0.88rem;margin:6px 0 10px;white-space:pre-wrap"
                )
                ui.label(sugg.get("custom_hint") or "").style("color:#86efac;font-size:0.82rem;margin-bottom:10px")
                for opt in opts:
                    lab = opt.get("label") or "Option"
                    if opt.get("recommended"):
                        lab = "★ " + lab
                    why = opt.get("why") or ""
                    with ui.row().classes("w-full items-start gap-2 q-mb-sm flex-wrap"):
                        with ui.column().classes("flex-1"):
                            ui.label(lab).style("color:#E8EDF4;font-weight:600;font-size:0.92rem")
                            if why:
                                ui.label(why).style("color:#9AABC4;font-size:0.8rem;white-space:pre-wrap")

                        def _pick(vals=opt.get("values") or {}):
                            _apply_suggest_values(vals)
                            dlg.close()
                            ui.notify("Suggestion applied — edit freely anytime", type="positive")

                        ui.button("Use", on_click=_pick).classes("btn-primary").props("dense no-caps unelevated")
                with ui.row().classes("gap-2 q-mt-sm flex-wrap"):
                    ui.button(
                        "Enter My Own Value",
                        on_click=dlg.close,
                    ).classes("btn-ghost").props("no-caps outline")
                    ui.button(
                        "Why These?",
                        on_click=lambda: ui.notify(
                            sugg.get("explanation") or "Based on locked constraints",
                            type="info",
                            multi_line=True,
                        ),
                    ).classes("btn-ghost").props("no-caps outline")
            state["suggest_dialog"] = dlg
            dlg.on("hide", lambda: state.update(suggest_dialog=None) if state.get("suggest_dialog") is dlg else None)
            dlg.open()

        def _precheck_conflicts(*, force_dialog: bool = True) -> bool:
            """Return True if search may proceed (no hard conflicts or user overrides)."""
            ctx = _constraint_context()
            if use_fatigue.value:
                ctx["use_fatigue"] = True
                ctx["min_rest"] = min_rest.value
                ctx["max_consec"] = max_consec.value
            chk = detect_constraint_conflicts(ctx)
            if chk.get("ok") and not chk.get("warnings"):
                return True
            lines = chk.get("lines") or [chk.get("message") or "Conflict check"]
            if force_dialog:
                with (
                    ui.dialog() as dlg,
                    ui.card()
                    .classes("q-pa-md")
                    .style(
                        "min-width:22rem;max-width:34rem;background:#0C1A2E;color:#E8EDF4;"
                        "border:1px solid rgba(251,191,36,0.5)"
                    ),
                ):
                    ui.label("Constraint Precheck").style("font-weight:700;font-size:1.05rem;color:#FDE68A")
                    for msg in lines[:12]:
                        ui.label(f"· {msg}").style("color:#E8EDF4;font-size:0.88rem;margin-top:4px")
                    if chk.get("blocking"):
                        ui.label("Blocking conflicts — fix constraints before long search.").style(
                            "color:#fca5a5;margin-top:10px"
                        )
                        ui.button("Close", on_click=dlg.close).classes("btn-ghost q-mt-md").props("no-caps outline")
                    else:
                        ui.label("Warnings only — you may continue.").style("color:#FDE68A;margin-top:10px")
                        state["_precheck_continue"] = False

                        def _go():
                            state["_precheck_continue"] = True
                            dlg.close()

                        ui.button("Search Anyway", on_click=_go).classes("btn-primary q-mt-md").props(
                            "no-caps unelevated"
                        )
                        ui.button("Cancel", on_click=dlg.close).classes("btn-ghost q-mt-md").props("no-caps outline")
                dlg.open()
                if chk.get("blocking"):
                    return False
                # Dialog is async-ish; for sync path treat warnings as proceed with notify
                for msg in lines[:3]:
                    ui.notify(msg, type="warning")
            return not chk.get("blocking")

        def run_sim():
            base = _baseline_kwargs()
            if base.get("error"):
                ui.notify(base["error"] or "Check Numeric Fields", type="negative")
                return
            if base.get("shift_length_hours") is None:
                ui.notify("Lock Shift Length before Generate", type="warning")
                return
            if not base.get("shift_starts"):
                ui.notify("Lock Shift Starts before Generate", type="warning")
                return
            if base.get("annual_hours_target") is None:
                ui.notify("Lock Annual Hours before Generate", type="warning")
                return
            if not _precheck_conflicts(force_dialog=False):
                ui.notify("Fix blocking constraint conflicts first", type="negative")
                return
            _persist_form()
            result = run_schedule_simulation(
                rotation_type=base["rotation_type"],
                num_officers=base["num_officers"],
                shift_length_hours=float(base["shift_length_hours"]),
                annual_hours_target=float(base["annual_hours_target"]),
                shift_starts=list(base["shift_starts"]),
                min_per_shift=base["min_per_shift"],
                simulation_days=56,
                annual_hours_variance=float(base.get("annual_hours_variance") or 0),
                annual_hours_hard=base["annual_hours_hard"],
                coverage_247=base["coverage_247"],
                avoid_flsa_overtime=base["avoid_flsa_overtime"],
                flsa_work_period_days=base["flsa_work_period_days"],
                rotation_style=base["rotation_style"],
                rotation_variations=base["rotation_variations"],
                auto_min_officers=base["auto_min_officers"],
                apply_department_rules=False,
                use_extra_windows=base["use_extra_windows"],
                extra_windows=base["extra_windows"],
                stagger_phases=True,
                nearby_start_hops=int(base.get("nearby_start_hops") or 0),
                allow_offday_coverage=bool(base.get("allow_offday_coverage")),
                min_rest_hours=float(base.get("min_rest_hours") or 0),
                max_consecutive_work_days=int(base.get("max_consecutive_work_days") or 0),
            )
            state["result"] = result
            state["config"] = _current_config()
            if not result.get("success"):
                set_summary(result.get("message", "Failed"))
                ui.notify(result.get("message", "Failed"), type="negative")
                return
            metrics = result.get("metrics") or {}
            hard = bool(state.get("hard_mode", True))
            lines = [result.get("message") or "Simulation Complete", ""] + _human_metrics(metrics)
            # Always explain plan (UX residual)
            try:
                from logic.plan_explain import explain_staffing_result

                lines.append("")
                lines.extend(
                    explain_staffing_result(
                        {
                            "success": True,
                            "best": {
                                "metrics": metrics,
                                "shift_starts": base.get("shift_starts"),
                                "num_officers": base.get("num_officers"),
                                "shift_length_hours": base.get("shift_length_hours"),
                                "hard_constraints_ok": metrics.get("hard_constraints_ok"),
                            },
                            "message": result.get("message"),
                        }
                    )[:8]
                )
            except Exception:
                pass
            set_summary("\n".join(lines))
            if hard and not metrics.get("hard_constraints_ok", True):
                _show_no_match_dialog(1, 1)
            uid = (session.current_user() or {}).get("id")
            save_last_optimized_plan(result, state["config"], user_id=uid)
            view = format_optimized_plan_view(result, state["config"])
            set_plan(view.get("text") or "")
            single = [
                {
                    "rank": 1,
                    "summary": (
                        f"{base['rotation_type']} · "
                        f"{metrics.get('min_officers_required', base['num_officers'])} Officers · "
                        f"Min {base['min_per_shift']} Per Shift"
                    ),
                    "rotation_type": base["rotation_type"],
                    "num_officers": int(metrics.get("min_officers_required") or base["num_officers"] or 0),
                    "min_per_shift": base["min_per_shift"],
                    "shift_length_hours": base["shift_length_hours"],
                    "annual_hours_target": base["annual_hours_target"],
                    "shift_starts": base["shift_starts"],
                    "rotation_variations": base["rotation_variations"],
                    "rotation_style": base["rotation_style"],
                    "hard_constraints_ok": metrics.get("hard_constraints_ok"),
                }
            ]
            _render_ranked(single, selected=1)
            try:
                _paint_kpis(
                    hard_ok=metrics.get("hard_constraints_ok"),
                    officers_n=metrics.get("min_officers_required") or base.get("num_officers"),
                    layouts=1,
                    annual_avg=metrics.get("avg_annual_hours"),
                    window_fails=metrics.get("extra_window_failures"),
                    mode_text="Generate schedule",
                )
            except Exception:
                pass
            ui.notify("Simulation complete", type="positive")

        def _apply_opt_result(result: dict, *, require_hard_ok: bool) -> None:
            state["config"] = _current_config()
            near = result.get("near_misses") or []
            # P0.3: budget ran out with nothing qualifying — honest partial
            # verdict, NOT the impossible/no-match dialog (nothing was proven).
            if result.get("budget_exhausted") and not result.get("best"):
                state["opt_result"] = result
                set_summary(
                    "\n".join(
                        [
                            result.get("message") or "Time budget reached — no qualifying option yet.",
                            "This is NOT proof the constraints are impossible — the search ran out of time.",
                            "Lock more requirements to shrink the space, or switch Depth to Deep for a longer budget.",
                        ]
                    )
                )
                _render_ranked(near[:10] if near else [])
                ui.notify("Time budget reached — partial results only", type="warning")
                return
            if result.get("impossible") or (require_hard_ok and (not result.get("success") or not result.get("best"))):
                state["opt_result"] = result
                note = result.get("space_note") or ""
                hist = result.get("failure_histogram") or {}
                if hist:
                    top = ", ".join(f"{k}={v}" for k, v in sorted(hist.items(), key=lambda x: -x[1]) if v)
                    if top:
                        note = (note + "\n" if note else "") + f"Reject reasons: {top}"
                evals = int(result.get("scenarios_evaluated") or 0)
                full_n = int(result.get("full_sims_run") or 0)
                tips = explain_staffing_result(result)
                set_summary(
                    "\n".join(
                        tips
                        or [
                            result.get("message") or "No Schedule Meets Selected Hard Constraints",
                            f"Layouts Checked (exhaustive): {evals:,}",
                            f"Combinations Tried: {evals:,}",
                            f"Full Simulations: {full_n:,} · Pruned Impossible: {result.get('pruned_cheap', '—')}",
                            note,
                            "",
                            "Closest alternatives listed below (if any).",
                        ]
                    )
                )
                try:
                    set_why("\n".join(tips[-8:] if tips else []))
                except Exception:
                    pass
                if near:
                    _render_ranked(near[:10], selected=1)
                else:
                    _render_ranked([])
                try:
                    nm0 = (near[0] if near else {}) or {}
                    m0 = nm0.get("metrics") or nm0.get("human_metrics") or {}
                    _paint_kpis(
                        hard_ok=False,
                        officers_n=nm0.get("num_officers"),
                        layouts=evals,
                        annual_avg=m0.get("avg_annual_hours"),
                        window_fails=m0.get("extra_window_failures"),
                        mode_text="No hard match",
                    )
                except Exception:
                    pass
                _show_no_match_dialog(
                    evals,
                    int(result.get("rejected_hard_constraints") or 0),
                    extra=note,
                    near_misses=near,
                )
                return
            if not result.get("success") or not result.get("best"):
                set_summary(result.get("message", "No Combination Found"))
                ui.notify(result.get("message", "No Combination Found"), type="negative")
                _render_ranked([])
                return
            ranked = result.get("ranked") or []
            best = result["best"]
            state["opt_result"] = result
            lines = list(explain_staffing_result(result))
            lines.extend(
                [
                    f"Structural Configs: {result.get('outer_configs', '—')} · "
                    f"Full Simulations: {result.get('full_sims_run', '—')} · "
                    f"Pruned Impossible: {result.get('pruned_cheap', '—')}",
                    f"Options Kept: {result.get('scenarios_kept', len(ranked))}",
                    ("Search: Exhaustive" if result.get("search_exhaustive") else "Search: Partial (time budget)")
                    + (f" · {result.get('wall_time_ms')} ms" if result.get("wall_time_ms") else ""),
                ]
            )
            if result.get("space_note"):
                lines.append(result["space_note"])
            if result.get("solver_status"):
                lines.append(f"Solver status: {result['solver_status'].replace('_', ' ')}")
            canonical_status = result.get("canonical_status")
            if canonical_status is not None:
                status_label = getattr(canonical_status, "value", str(canonical_status))
                lines.append(f"Canonical status: {status_label}")
            sim_report = result.get("simulation_report")
            verification = getattr(sim_report, "verification", None) if sim_report is not None else None
            if verification is not None:
                verdict = "PASSED" if verification.verified else "FAILED"
                detail = f" ({', '.join(verification.violations)})" if verification.violations else ""
                lines.append(f"Independent verification: {verdict}{detail}")
            if result.get("budget_exhausted"):
                lines.append(
                    "Time budget reached — best-so-far shown; a longer Deep search may still find better options."
                )
            lines.extend(["", "Select An Option Below To Load It."])
            set_summary("\n".join(lines))
            try:
                set_why("\n".join(why_best_lines(result)))
            except Exception:
                set_why("")
            _render_ranked(ranked, selected=int(best.get("rank") or 1))
            _apply_ranked_option(best)
            try:
                bm = best.get("metrics") or best.get("human_metrics") or {}
                _paint_kpis(
                    hard_ok=best.get("hard_constraints_ok"),
                    officers_n=best.get("num_officers"),
                    layouts=result.get("scenarios_evaluated"),
                    annual_avg=bm.get("avg_annual_hours"),
                    window_fails=bm.get("extra_window_failures"),
                    mode_text="Hard" if require_hard_ok else "Softened",
                )
            except Exception:
                pass
            ui.notify(result.get("message", "Coverage Search Complete"), type="positive")

        def _set_search_buttons(running: bool) -> None:
            state["opt_running"] = running
            try:
                if running:
                    btn_opt.props("disable loading")
                    btn_gen.props("disable")
                    btn_compare.props("disable")
                    btn_min_n.props("disable")
                    btn_whatif.props("disable")
                else:
                    btn_opt.props(remove="disable loading")
                    btn_gen.props(remove="disable")
                    btn_compare.props(remove="disable")
                    btn_min_n.props(remove="disable")
                    btn_whatif.props(remove="disable")
            except Exception:
                pass
            try:
                search_spinner.set_visibility(bool(running))
                skeleton_host.set_visibility(bool(running))
                if running:
                    search_status.set_text("Searching layouts…")
                    search_status_host.classes(add="is-running")
                else:
                    search_status.set_text("Ready · hard constraints")
                    search_status_host.classes(remove="is-running")
            except Exception:
                pass

        async def _execute_opt(kw: dict, *, require_hard_ok: bool):
            """Run search on worker thread; poll progress on UI thread (no hang)."""
            if state.get("opt_running"):
                ui.notify("Search already running", type="warning")
                return
            state["hard_mode"] = require_hard_ok
            mode_label.set_text("Mode: hard constraints" if require_hard_ok else "Mode: softened (best effort)")
            cancel_ev = threading.Event()
            progress: dict = {
                "message": "Searching entire constraint space…",
                "done": 0,
                "total": 0,
                "full_sims": 0,
            }
            state["opt_cancel"] = cancel_ev
            import time as _time

            state["opt_t0"] = _time.perf_counter()
            _set_search_buttons(True)
            try:
                progress_bar.style("display:block")
                progress_bar.value = 0
            except Exception:
                pass
            try:
                state["ranked"] = []
                options_ui.refresh()
            except Exception:
                pass
            understood = "Simulator understood\n" + "\n".join(simulator_understood_lines(kw.get("input_roles")))
            set_summary(f"{understood}\n\nSearching entire constraint space…")
            ui.notify("Searching entire constraint space…", type="info", position="top")
            await asyncio.sleep(0.05)

            def _on_progress(info: dict) -> None:
                if not isinstance(info, dict):
                    return
                progress["message"] = str(info.get("message") or progress["message"])
                if info.get("done") is not None:
                    progress["done"] = int(info["done"])
                if info.get("total") is not None:
                    progress["total"] = int(info["total"])
                if info.get("full_sims") is not None:
                    progress["full_sims"] = int(info["full_sims"])

            # P0.4: the search runs in a child process (GIL starvation froze
            # the whole app when it ran on a thread — 84s page loads, measured).
            # The executor thread below only relays progress/cancel over IPC.
            job_kw = dict(kw)

            loop = asyncio.get_event_loop()
            try:
                fut = loop.run_in_executor(
                    _OPT_EXECUTOR,
                    lambda: run_staffing_optimizer_isolated(
                        job_kw,
                        progress_callback=_on_progress,
                        cancel_check=cancel_ev.is_set,
                    ),
                )
                while not fut.done():
                    done = int(progress.get("done") or 0)
                    total = int(progress.get("total") or 0)
                    full = int(progress.get("full_sims") or 0)
                    msg = progress.get("message") or "Searching…"
                    eta = ""
                    t0 = state.get("opt_t0")
                    if t0 and done > 5 and total > done:
                        import time as _time

                        elapsed = max(0.1, _time.perf_counter() - float(t0))
                        rate = done / elapsed
                        remain = max(0, (total - done) / max(rate, 1e-6))
                        eta = f" · ETA ~{int(remain)}s"
                    if total > 0:
                        frac = min(1.0, done / max(total, 1))
                        pct = f" · {int(100 * frac)}%"
                        try:
                            progress_bar.value = frac
                        except Exception:
                            pass
                        try:
                            search_status.set_text(f"{int(100 * frac)}% · {done:,}/{total:,}{eta}")
                        except Exception:
                            pass
                        set_summary(
                            f"{msg}\nLayouts: {done:,} / {total:,}{pct}{eta} · "
                            f"Full Sims: {full:,}\n"
                            "Cancel search stops after the current layout."
                        )
                    else:
                        try:
                            search_status.set_text(f"{done:,} layouts · sims {full:,}{eta}")
                        except Exception:
                            pass
                        set_summary(
                            f"{msg}\nLayouts: {done:,} · Full Sims: {full:,}{eta}\n"
                            "Cancel search stops after the current layout."
                        )
                    await asyncio.sleep(0.25)
                result = fut.result()
            except Exception as exc:
                _set_search_buttons(False)
                set_summary(f"Search Failed: {exc}")
                ui.notify(f"Search Failed: {exc}", type="negative")
                return
            finally:
                _set_search_buttons(False)
                state["opt_cancel"] = None
                state["opt_t0"] = None
                try:
                    progress_bar.style("display:none")
                    progress_bar.value = 0
                except Exception:
                    pass

            if not isinstance(result, dict):
                set_summary(f"Search Failed: unexpected result type {type(result)!r}")
                ui.notify("Search Failed: bad result", type="negative")
                return
            if result.get("cancelled") and not result.get("best") and not result.get("near_misses"):
                set_summary(result.get("message") or "Search cancelled")
                ui.notify("Search cancelled", type="warning")
                return
            try:
                best = result.get("best") or {}
                append_search_history(
                    {
                        "success": result.get("success"),
                        "message": (result.get("message") or "")[:120],
                        "num_officers": best.get("num_officers"),
                        "wall_time_ms": result.get("wall_time_ms"),
                        "scenarios_evaluated": result.get("scenarios_evaluated"),
                        "hard_ok": best.get("hard_constraints_ok"),
                    }
                )
            except Exception:
                pass
            try:
                _apply_opt_result(result, require_hard_ok=require_hard_ok)
            except Exception as exc:
                set_summary(
                    f"{result.get('message') or 'Search finished'}\n"
                    f"Layouts Checked (exhaustive): {int(result.get('scenarios_evaluated') or 0):,}\n"
                    f"UI apply error: {exc}"
                )
                ui.notify(f"Search finished; apply error: {exc}", type="warning")
                near = result.get("near_misses") or result.get("ranked") or []
                if near:
                    _render_ranked(near[:10], selected=1)

        async def _run_opt(*, require_hard_ok: bool, force: bool = False):
            kw = _optimizer_kwargs(require_hard_ok=require_hard_ok)
            if kw.get("error"):
                ui.notify(kw.get("error") or "Check Numeric Fields", type="negative")
                return
            chk = detect_constraint_conflicts(_constraint_context())
            if chk.get("blocking"):
                for msg in (chk.get("lines") or [])[:4]:
                    ui.notify(msg, type="negative")
                return
            if chk.get("warnings") and not force:
                for msg in (chk.get("lines") or [])[:3]:
                    ui.notify(msg, type="warning")
            if use_officers.value:
                try:
                    n = int((officers.value or "0").strip() or "0")
                except ValueError:
                    n = 0
                if n < 1:
                    ui.notify("Officer Count Requires A Number When Selected", type="warning")
                    return
            kw.pop("error", None)
            est = _refresh_space_estimate()
            if not force and est and est.get("requires_confirm") and require_hard_ok:

                async def _run_from_plan(job, hard):
                    await _execute_opt(job, require_hard_ok=hard)

                open_search_plan_dialog(
                    ui,
                    estimate=est,
                    kwargs=kw,
                    require_hard_ok=require_hard_ok,
                    understood_lines=simulator_understood_lines(kw.get("input_roles")),
                    on_run=_run_from_plan,
                )
                return

            await _execute_opt(kw, require_hard_ok=require_hard_ok)

        async def run_opt():
            _refresh_space_estimate()
            await _run_opt(require_hard_ok=True)

        async def run_compare():
            """Compare 8/10/12h under same coverage constraints (locked N)."""
            if state.get("opt_running"):
                ui.notify("Search already running", type="warning")
                return
            try:
                n = int((officers.value or "8").strip() or "8")
            except ValueError:
                n = 8
            if n < 1:
                n = 8
            try:
                annual = float((annual.value or "2008").strip() or "2008")
            except ValueError:
                annual = 2008.0
            try:
                variance = float((annual_var.value or "20").strip() or "20")
            except ValueError:
                variance = 20.0
            # Use current form windows when enabled (same keys as Find Best)
            wins = []
            if bool(use_windows.value):
                wins = [w for w in (state.get("windows") or []) if isinstance(w, dict) and w.get("enabled", True)]
            cancel_ev = threading.Event()
            state["opt_cancel"] = cancel_ev
            state["opt_running"] = True
            depth = "quick" if bool(compare_quick.value) else "deep"
            set_summary(
                f"Comparing 8h / 10h / 12h ({depth}, parallel)…\nCancel Search stops mid-search on each length."
            )
            try:
                result = await run.io_bound(
                    lambda: compare_shift_length_scenarios(
                        lengths=[8.0, 10.0, 12.0],
                        officer_count=n,
                        annual_hours_target=annual,
                        annual_hours_variance=variance,
                        coverage_247=1 if bool(use_247.value) else 0,
                        extra_windows=wins or None,
                        require_hard_ok=True,
                        cancel_check=cancel_ev.is_set,
                        depth=depth,
                    )
                )
            except Exception as exc:
                set_summary(f"Compare Failed: {exc}")
                ui.notify(f"Compare Failed: {exc}", type="negative")
                state["opt_running"] = False
                state["opt_cancel"] = None
                return
            state["opt_running"] = False
            state["opt_cancel"] = None
            if result.get("cancelled"):
                set_summary(result.get("message") or "Compare cancelled")
                ui.notify("Compare cancelled", type="warning")
                return
            lines = list(result.get("table_lines") or [])
            if not lines:
                lines = [result.get("message") or "Shift Length Comparison", ""]
                for c in result.get("comparisons") or []:
                    flag = "OK" if c.get("success") else "NO"
                    lines.append(
                        f"{c.get('shift_length_hours')}h · {flag} · "
                        f"Layouts Checked: {c.get('scenarios_evaluated', '—')} · "
                        f"starts={c.get('best_starts') or '—'} · "
                        f"var={c.get('best_variation') or '—'} · "
                        f"near_miss={c.get('near_miss_count', 0)}"
                    )
            set_summary("\n".join(lines))
            set_why(result.get("message") or "Compare finished")
            ui.notify(result.get("message") or "Compare Done", type="positive")

        async def run_min_n():
            if state.get("opt_running"):
                ui.notify("Search already running", type="warning")
                return
            cancel_ev = threading.Event()
            state["opt_cancel"] = cancel_ev
            _set_search_buttons(True)
            set_summary("Finding minimum officers for hard constraints…")
            try:
                base = _baseline_kwargs()
                result = await run.io_bound(
                    lambda: find_min_officers_hard(
                        lo=4,
                        hi=16,
                        shift_length_hours=float(base.get("shift_length_hours") or 8),
                        annual_hours_target=float(base.get("annual_hours_target") or 2008),
                        annual_hours_variance=float(base.get("annual_hours_variance") or 20),
                        rotation_variations=list(base.get("rotation_variations") or []),
                        shift_starts=list(base.get("shift_starts") or []),
                        coverage_247=int(base.get("coverage_247") or 0),
                        extra_windows=list(base.get("extra_windows") or []) or None,
                        night_minimum=base.get("night_minimum"),
                        cancel_check=cancel_ev.is_set,
                    )
                )
            except Exception as exc:
                set_summary(f"Min-N failed: {exc}")
                ui.notify(str(exc), type="negative")
                _set_search_buttons(False)
                return
            _set_search_buttons(False)
            state["opt_cancel"] = None
            lines = [result.get("message") or "Min officers", ""]
            for t in result.get("trials") or []:
                st = t.get("best_starts") or []
                st_s = ",".join(str(s) for s in st) if isinstance(st, list) else ""
                lines.append(
                    f"N={t.get('num_officers')}: "
                    f"{'OK' if t.get('success') else 'NO'}" + (f" · starts={st_s}" if st_s else "")
                )
            best = result.get("best") or {}
            bst = best.get("shift_starts") or []
            if bst:
                lines.append("Best starts: " + (",".join(str(s) for s in bst) if isinstance(bst, list) else str(bst)))
            if result.get("cpsat_note"):
                lines.append(f"CP-SAT note: {result['cpsat_note']}")
            set_summary("\n".join(lines))
            if result.get("success") and result.get("min_officers"):
                officers.value = str(result["min_officers"])
                use_officers.value = True
                # Reflect LE pack that hard-OK'd (incl. 19:00 when used)
                if bst and isinstance(bst, list):
                    try:
                        starts.value = ", ".join(str(s) for s in bst)
                        use_starts.value = True
                    except Exception:
                        pass
                ui.notify(f"Min officers: {result['min_officers']}", type="positive")
            else:
                ui.notify(result.get("message") or "No min N", type="warning")

        async def run_whatif():
            if state.get("opt_running"):
                ui.notify("Search already running", type="warning")
                return
            kw = _optimizer_kwargs(require_hard_ok=True)
            if kw.get("error"):
                ui.notify("Check numeric fields", type="negative")
                return
            kw.pop("error", None)
            _set_search_buttons(True)
            set_summary("What-if: +1 officer…")
            try:
                result = await run.io_bound(lambda: what_if_staffing_delta(kw, delta_officers=1))
            except Exception as exc:
                set_summary(f"What-if failed: {exc}")
                _set_search_buttons(False)
                return
            _set_search_buttons(False)
            set_summary(
                f"{result.get('message')}\nBase: {result.get('base_message')}\nAlt (+1): {result.get('alt_message')}"
            )
            ui.notify(result.get("message") or "What-if done", type="info")

        async def implement_plan():
            res = state.get("result")
            cfg = state.get("config")
            if not res or not res.get("success"):
                stored = get_last_optimized_plan()
                if stored:
                    res, cfg = stored.get("result"), stored.get("config")
            if not res or not res.get("success"):
                ui.notify("No Successful Plan To Publish", type="warning")
                set_action_log("Publish Failed: No Plan In Memory.", ok=False)
                return
            start_date = (impl_date.value or "").strip()
            uid = (session.current_user() or {}).get("id")
            plan_cfg = cfg or _current_config()
            plan_res = res
            btn_impl.props("disable loading")
            set_action_log("Publishing In Background…", ok=None)
            try:
                r = await run.io_bound(
                    implement_optimized_plan,
                    start_date=start_date,
                    result=plan_res,
                    config=plan_cfg,
                    user_id=uid,
                    apply_officer_assignments=bool(apply_officers.value),
                    force_regenerate=bool(force_regen.value),
                    save_as_defaults=bool(save_defaults.value),
                )
            except Exception as exc:
                r = {"success": False, "message": f"Publish Crashed: {exc}"}
            finally:
                try:
                    btn_impl.props(remove="disable loading")
                except Exception:
                    pass
            msg = r.get("message") or ("Done" if r.get("success") else "Failed")
            ui.notify(msg, type="positive" if r.get("success") else "negative")
            if r.get("success"):
                set_action_log(
                    "\n".join(
                        [
                            "Publish OK",
                            msg,
                            f"Year/Month: {r.get('year')}/{r.get('month')}",
                            f"Snapshot Id: {r.get('snapshot_id')}",
                            f"Live Snapshot Id: {r.get('live_snapshot_id')}",
                        ]
                    ),
                    ok=True,
                )
            else:
                set_action_log(f"Publish Failed\n{msg}", ok=False)

        handlers = build_action_handlers(
            state,
            {**ui_elements, **step4_elements},
            {
                "set_action_log": set_action_log,
                "_current_config": lambda: _current_config(),
                "set_summary": lambda t: set_summary(t),
                "set_why": lambda t="": set_why(t),
                "set_plan": lambda t: set_plan(t),
                "_refresh_space_estimate": lambda: _refresh_space_estimate(),
                "go_step": go_step,
                "_apply_ranked_option": lambda row: _apply_ranked_option(row),
            },
        )
        save_scenario = handlers["save_scenario"]
        preview_publish = handlers["preview_publish"]
        export_csv = handlers["export_csv"]
        bid_from_sim = handlers["bid_from_sim"]
        export_options = handlers["export_options"]
        export_audit = handlers["export_audit"]
        run_diff_ab = handlers["run_diff_ab"]
        run_fairness = handlers["run_fairness"]
        run_plain_explain = handlers["run_plain_explain"]
        run_sensitivity = handlers["run_sensitivity"]
        run_import_live = handlers["run_import_live"]
        run_apply_winner_month = handlers["run_apply_winner_month"]
        run_cpsat_small = handlers["run_cpsat_small"]
        do_pin = handlers["do_pin"]
        do_share = handlers["do_share"]
        save_slot = handlers["save_slot"]
        lock_selected_seed = handlers["lock_selected_seed"]
        apply_stay = handlers["apply_stay"]
        apply_and_publish_step = handlers["apply_and_publish_step"]

        tools = render_results_panel_tools(
            state, _apply_ranked_option, lambda data: _apply_form_payload(data), set_plan, plan_box, _ui_safe, set_why
        )
        show_search_history = tools["show_search_history"]
        show_pins = tools["show_pins"]
        show_slots = tools["show_slots"]
        do_heat = tools["do_heat"]
        show_weekend_heat = tools["show_weekend_heat"]
        do_window_drill = tools["do_window_drill"]

        def _form_payload() -> dict:
            return {
                "officers": officers.value,
                "officers_range_lo": officers_range_lo.value,
                "officers_range_hi": officers_range_hi.value,
                "length": length.value,
                "annual": annual.value,
                "annual_var": annual_var.value,
                "starts": starts.value,
                "min_ps": min_ps.value,
                "variations": variations.value,
                "use_officers": bool(use_officers.value),
                "use_length": bool(use_length.value),
                "use_starts": bool(use_starts.value),
                "use_247": bool(use_247.value),
                "use_windows": bool(use_windows.value),
                "use_min_ps": bool(use_min_ps.value),
                "use_rotation": bool(use_rotation.value),
                "use_style": bool(use_style.value),
                "use_annual": bool(use_annual.value),
                "use_flsa": bool(use_flsa.value),
                "use_nearby": bool(use_nearby.value),
                "nearby_hops": nearby_hops.value,
                "allow_offday": bool(allow_offday.value),
                "use_certs": bool(use_certs.value),
                "required_certs": cert_codes.value,
                "use_fatigue": bool(use_fatigue.value),
                "min_rest": min_rest.value,
                "max_consec": max_consec.value,
                "cov247": cov247.value,
                "flsa_days": flsa_days.value,
                "rot_style": getattr(rot_style, "value", None),
                "multi_catalog": getattr(multi_catalog, "value", None),
                "windows": list(state.get("windows") or []),
                "rotation": getattr(rotation, "value", None),
                "manual_days": man_days.value if "man_days" in dir() else state.get("manual_days"),
                "manual_grid": state.get("manual_grid"),
            }

        def _apply_form_payload(data: dict) -> None:
            if not data:
                return
            state["restoring_form"] = True
            try:
                _apply_form_payload_inner(data)
            finally:
                state["restoring_form"] = False

        def _apply_form_payload_inner(data: dict) -> None:
            def _val_ok(key: str, widget) -> bool:
                # Same guard as _apply_suggest_values (Bug B): a Given/Require
                # flag may only restore as ON if its paired value survives the
                # round-trip — otherwise the form reloads locked-but-empty and
                # silently blocks Find Best with "Fix numbers". This restore
                # path (page load) previously had no guard; found live
                # 2026-07-17 after a save-during-restore race emptied cov247.
                v = data.get(key)
                if v is None:
                    v = getattr(widget, "value", None)
                return v is not None and str(v).strip() != ""

            if data.get("officers") is not None:
                officers.value = str(data["officers"])
            if data.get("officers_range_lo") is not None:
                officers_range_lo.value = str(data["officers_range_lo"])
            if data.get("officers_range_hi") is not None:
                officers_range_hi.value = str(data["officers_range_hi"])
            if data.get("length") is not None:
                length.value = str(data["length"])
            if data.get("annual") is not None:
                annual.value = str(data["annual"])
            if data.get("annual_var") is not None:
                annual_var.value = str(data["annual_var"])
            if data.get("starts") is not None:
                starts.value = str(data["starts"])
            if data.get("min_ps") is not None:
                min_ps.value = str(data["min_ps"])
            if data.get("variations") is not None:
                variations.value = str(data["variations"])
            if data.get("use_officers") is not None:
                use_officers.value = bool(data["use_officers"]) and _val_ok("officers", officers)
                _set_enabled([officers], bool(use_officers.value))
            if data.get("use_length") is not None:
                use_length.value = bool(data["use_length"]) and _val_ok("length", length)
                _set_enabled([length], bool(use_length.value))
            if data.get("use_starts") is not None:
                use_starts.value = bool(data["use_starts"]) and _val_ok("starts", starts)
                _set_enabled([starts], bool(use_starts.value))
            if data.get("use_247") is not None:
                use_247.value = bool(data["use_247"]) and _val_ok("cov247", cov247)
                _set_enabled([cov247], bool(use_247.value))
            if data.get("use_windows") is not None:
                use_windows.value = bool(data["use_windows"])
            if data.get("use_min_ps") is not None:
                use_min_ps.value = bool(data["use_min_ps"]) and _val_ok("min_ps", min_ps)
                _set_enabled([min_ps], bool(use_min_ps.value))
            if data.get("use_rotation") is not None:
                use_rotation.value = bool(data["use_rotation"]) and _val_ok("rotation", rotation)
                _set_enabled([rotation], bool(use_rotation.value))
            if data.get("use_style") is not None:
                use_style.value = bool(data["use_style"]) and _val_ok("variations", variations)
                _set_enabled([rot_style, multi_catalog, variations], bool(use_style.value))
            if data.get("use_annual") is not None:
                use_annual.value = bool(data["use_annual"]) and _val_ok("annual", annual)
                _set_enabled([annual, annual_var], bool(use_annual.value))
            if data.get("use_flsa") is not None:
                use_flsa.value = bool(data["use_flsa"])
                _set_enabled([flsa_days], bool(use_flsa.value))
            if data.get("use_nearby") is not None:
                use_nearby.value = bool(data["use_nearby"]) and _val_ok("nearby_hops", nearby_hops)
                _set_enabled([nearby_hops], bool(use_nearby.value))
            if data.get("nearby_hops") is not None:
                nearby_hops.value = str(data["nearby_hops"])
            if data.get("allow_offday") is not None:
                allow_offday.value = bool(data["allow_offday"])
            if data.get("max_start_span") is not None:
                max_start_span.value = str(data["max_start_span"])
            if data.get("use_start_span") is not None:
                use_start_span.value = bool(data["use_start_span"]) and bool(str(max_start_span.value or "").strip())
                _set_enabled([max_start_span], bool(use_start_span.value))
            if data.get("prefer_unique_starts") is not None:
                prefer_unique_starts.value = bool(data["prefer_unique_starts"])
            if data.get("cov247") is not None:
                cov247.value = str(data["cov247"])
            if data.get("flsa_days") is not None:
                flsa_days.value = str(data["flsa_days"])
            if data.get("ot_hourly_rate") is not None:
                ot_hourly_rate.value = str(data["ot_hourly_rate"])
            if data.get("rot_style"):
                try:
                    rot_style.value = data["rot_style"]
                except Exception:
                    pass
            if data.get("multi_catalog"):
                try:
                    multi_catalog.value = data["multi_catalog"]
                except Exception:
                    pass
            if data.get("windows") is not None:
                state["windows"] = list(data["windows"] or [])
                try:
                    _refresh_win_list()
                except Exception:
                    pass
            if data.get("rotation"):
                try:
                    rotation.value = normalize_rotation_preset_name(data["rotation"])
                except Exception:
                    pass
            if data.get("manual_grid") is not None:
                state["manual_grid"] = data["manual_grid"]
            if data.get("manual_days") is not None:
                state["manual_days"] = data["manual_days"]
                try:
                    man_days.value = str(data["manual_days"])
                except Exception:
                    pass

        def _push_undo():
            try:
                stack = list(state.get("form_undo") or [])
                stack.append(_form_payload())
                state["form_undo"] = stack[-15:]
            except Exception:
                pass

        def undo_form():
            stack = list(state.get("form_undo") or [])
            if not stack:
                ui.notify("Nothing to undo", type="info")
                return
            data = stack.pop()
            state["form_undo"] = stack
            _apply_form_payload(data)
            ui.notify("Form undone", type="info")

        def _persist_form():
            # Value-change handlers fire while a restore is mid-flight; saving
            # then snapshots a half-restored form (e.g. use_247 on, cov247 not
            # yet set) and corrupts the stored constraints for the next load.
            if state.get("restoring_form"):
                return
            _push_undo()
            data = _form_payload()
            save_form_snapshot(data)
            try:
                from nicegui import app as _app

                store = getattr(_app.storage, "user", None)
                if store is not None:
                    store["sim_form"] = data
            except Exception:
                pass

        def _restore_form():
            data = None
            try:
                from nicegui import app as _app

                store = getattr(_app.storage, "user", None)
                if store:
                    data = store.get("sim_form")
            except Exception:
                data = None
            if not data:
                data = load_last_simulator_constraints()
            if data:
                _apply_form_payload(data)
            try:
                _refresh_lock_strip()
            except Exception:
                pass
            try:
                _refresh_space_estimate()
            except Exception:
                pass

        def copy_summary():
            text = ""
            try:
                # last summary is in state if we track it
                text = state.get("last_summary") or ""
            except Exception:
                text = ""
            if not text and state.get("opt_result"):
                text = "\n".join(explain_staffing_result(state["opt_result"]))
            if not text:
                ui.notify("Nothing to copy", type="warning")
                return
            try:
                ui.clipboard.write(text)
                ui.notify("Summary copied", type="positive")
            except Exception:
                # Fallback path for environments without clipboard API
                set_why(text)
                ui.notify("Summary shown in Why panel (clipboard unavailable)", type="info")

        def export_config():
            r = export_form_config_json(_form_payload())
            if r.get("success"):
                ui.notify(f"Config: {r.get('path')}", type="positive")
                set_summary(f"Exported config:\n{r.get('path')}")
            else:
                ui.notify("Export failed", type="negative")

        def import_config():
            with (
                ui.dialog() as dlg,
                ui.card().classes("q-pa-md").style("min-width:20rem;background:#0C1A2E;color:#E8EDF4"),
            ):
                ui.label("Import Config JSON Path").style("font-weight:700")
                path_in = ui.input(
                    label="Full path to .json",
                    value="",
                ).classes("w-full")

                def _go():
                    from logic.optimizer_features import import_form_config_json

                    r = import_form_config_json((path_in.value or "").strip())
                    if not r.get("success"):
                        ui.notify(r.get("message") or "Import failed", type="negative")
                        return
                    _apply_form_payload(r.get("config") or {})
                    _persist_form()
                    dlg.close()
                    ui.notify("Config imported", type="positive")

                ui.button("Import", on_click=_go).classes("btn-primary").props("no-caps unelevated")
                ui.button("Cancel", on_click=dlg.close).classes("btn-ghost").props("no-caps outline")
            dlg.open()

        # Track last summary text for copy
        _orig_set_summary = set_summary

        def set_summary(text: str):  # type: ignore[no-redef]
            state["last_summary"] = text or ""
            _orig_set_summary(text)

        try:
            _restore_form()
        except Exception:
            pass
        # Throttle form persist — typing storms hurt NiceGUI WS payload / storage
        _persist_throttled = throttled(_persist_form, 0.45)
        try:
            for w in (length, annual, annual_var, variations, officers, starts, min_ps):
                w.on_value_change(lambda e: _persist_throttled())
        except Exception:
            pass

        btn_gen.on_click(run_sim)
        btn_opt.on_click(run_opt)
        btn_compare.on_click(run_compare)
        btn_min_n.on_click(run_min_n)
        btn_whatif.on_click(run_whatif)

        # Quick-start question buttons (step 1) reuse the same flows.
        async def _q_min_officers():
            go_step(2)
            await run_min_n()

        async def _q_whatif():
            go_step(2)
            await run_whatif()

        def _q_will_n():
            with (
                ui.dialog() as qdlg,
                ui.card()
                .classes("q-pa-md")
                .style("min-width:20rem;background:#0C1A2E;color:#E8EDF4;border:1px solid rgba(91,141,239,0.45)"),
            ):
                ui.label("Will N officers work?").style("font-weight:700;font-size:1.05rem;color:#F8FAFC")
                n_in = ui.input(label="Officer count", value=(officers.value or "8")).classes("w-full")

                async def _q_go():
                    raw = (n_in.value or "").strip()
                    try:
                        n = int(raw)
                    except ValueError:
                        ui.notify("Enter a whole number of officers", type="warning")
                        return
                    if n < 1:
                        ui.notify("Officer count must be at least 1", type="warning")
                        return
                    officers.value = str(n)
                    use_officers.value = True
                    _en_off(True)
                    qdlg.close()
                    go_step(2)
                    await run_opt()

                with ui.row().classes("gap-2 q-mt-sm"):
                    ui.button("Search", on_click=_q_go).classes("btn-primary").props("no-caps unelevated")
                    ui.button("Cancel", on_click=qdlg.close).classes("btn-ghost").props("no-caps outline")
            qdlg.open()

        btn_q_min.on_click(_q_min_officers)
        btn_q_will.on_click(_q_will_n)
        btn_q_plus.on_click(_q_whatif)

        def export_memo():
            r = export_staffing_memo(
                result=state.get("result"),
                config=state.get("config"),
                ranked=state.get("ranked") or ((state.get("opt_result") or {}).get("ranked")),
                conflicts=detect_constraint_conflicts(_constraint_context()),
            )
            if r.get("success"):
                set_summary((r.get("text") or "")[:4000])
                ui.notify(f"Memo: {r.get('path')}", type="positive")
            else:
                ui.notify("Memo export failed", type="negative")

        # (Secondary tools now wired inline in the 4 dropdown menus above.)
        btn_apply_month.on_click(run_apply_winner_month)
        btn_impl.on_click(implement_plan)
        btn_preview.on_click(preview_publish)
        btn_apply_stay.on_click(apply_stay)
        btn_apply_pub.on_click(apply_and_publish_step)
        btn_save.on_click(save_scenario)
        btn_csv.on_click(export_csv)
        if btn_bid is not None:
            btn_bid.on_click(bid_from_sim)

        go_step(1)

    layout("simulator", body)
