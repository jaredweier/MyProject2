from nicegui import ui

from gui.pages.simulator.helpers import (
    _DOW_NAME_TO_WEEKDAY,
    _DOW_NAMES,
    _HINT,
    _MULTI_BLOCK_LABELS,
    _MULTI_BY_LABEL,
    _ROTATION_OPTIONS,
    _STYLE_OPTIONS,
    _WEEKDAY_TO_NAME,
    _set_enabled,
    given_solve_toggle,
)
from gui.shell import panel
from logic.optimizer_features import get_window_template, list_window_templates
from logic.staffing_insights import court_board_to_demand_windows, get_demand_template, list_demand_templates
from validators import parse_date, storage_date_str

_ROW_CLASSES = "w-full grid sim-option-card"
_ROW_STYLE = "grid-template-columns: minmax(200px, 1fr) 2fr; align-items: center; gap: 1.5rem;"


def _row():
    return ui.element("div").classes(_ROW_CLASSES).style(_ROW_STYLE)


def render_options_panel(
    state: dict,
    placeholder_rot: str,
    _persist_form,
    _refresh_space_estimate,
    _show_constraint_suggestions,
):
    ui_elements = {}

    # ── Scenario Setup — when the simulation clock starts; not a search axis ──
    with panel("Scenario Setup"):
        with _row():
            use_start_date = ui.checkbox("Target Start Date", value=False)
            with ui.element("div"):
                sim_start_date = ui.input(
                    label="YYYY-MM-DD",
                    value="",
                    placeholder="e.g. 2026-07-17",
                ).classes("w-full")
        use_start_date.on_value_change(lambda e: _set_enabled([sim_start_date], bool(e.value)))
        _set_enabled([sim_start_date], False)

    # ── Search Axes — the only things that change how many schedules get
    # checked. Locking one to an exact value shrinks the search; leaving it on
    # "Solve for" makes the engine try a range of values for it. Ordered
    # biggest-range-first so locking the top ones gives the largest speedup. ──
    with panel("Search Axes (locking these narrows the search)"):
        with _row():
            use_officers = given_solve_toggle(ui, "Officer Count")
            with ui.element("div"):
                officers = ui.input(
                    label="Exact Officer Count",
                    value="",
                    placeholder="e.g. 8",
                ).classes("w-full")
                with ui.row().classes("w-full gap-2"):
                    officers_range_lo = ui.input(label="Range Min", value="4", placeholder="4").classes("w-full")
                    officers_range_hi = ui.input(label="Range Max", value="20", placeholder="20").classes("w-full")
                hint_officers = ui.label(
                    "Given: search only this exact headcount. Solve for: enter a Range Min/Max below "
                    "(any size) and we'll test every headcount in that range."
                ).classes("sim-free-hint")

        def _on_lock_officers(e=None):
            locked = bool(use_officers.value)
            _set_enabled([officers], locked)
            _set_enabled([officers_range_lo, officers_range_hi], not locked)
            try:
                _refresh_space_estimate()
            except Exception:
                pass

        use_officers.on_value_change(_on_lock_officers)
        _set_enabled([officers], False)
        _set_enabled([officers_range_lo, officers_range_hi], True)

        with _row():
            use_rotation = given_solve_toggle(ui, "Rotation Pattern")
            with ui.element("div"):
                rotation = (
                    ui.select(
                        _ROTATION_OPTIONS,
                        value=placeholder_rot,
                        label="Pattern",
                    )
                    .classes("w-full")
                    .props("outlined dense dark")
                )
                hint_rotation = ui.label(
                    "Preset library only. Has no effect once you enter custom Patterns in "
                    "Rotation Style / Multi-Block below — those override this. If unchecked "
                    "(and no custom Patterns are given), we'll try every preset to find the best fit."
                ).classes("sim-free-hint")
        use_rotation.on_value_change(lambda e: _set_enabled([rotation], bool(e.value)))
        _set_enabled([rotation], False)

        with _row():
            use_length = given_solve_toggle(ui, "Shift Length")
            with ui.element("div"):
                length = ui.input(
                    label="Hours (0.5 Steps)",
                    value="",
                    placeholder="e.g. 8",
                ).classes("w-full")
                hint_length = ui.label(
                    "If unchecked: quick search tries 8/10/12-hour shifts; thorough search tries every half-hour length from 8 to 12."
                ).classes("sim-free-hint")

        def _on_lock_length(e=None):
            _set_enabled([length], bool(use_length.value))
            try:
                _refresh_space_estimate()
            except Exception:
                pass

        use_length.on_value_change(_on_lock_length)
        _set_enabled([length], False)

        with _row():
            use_style = given_solve_toggle(ui, "Rotation Style / Multi-Block")
            with ui.element("div"):
                hint_style = ui.label(
                    "Use this for custom on/off block patterns (e.g. 6-2,5-3) — filling in "
                    "Patterns below overrides the Rotation Pattern preset above entirely. "
                    "If unchecked, we'll try fixed and rotating multi-block styles."
                ).classes("sim-free-hint")
                rot_style = (
                    ui.select(_STYLE_OPTIONS, value="Rotating", label="Style")
                    .classes("w-full")
                    .props("outlined dense dark")
                )
                multi_catalog = (
                    ui.select(
                        _MULTI_BLOCK_LABELS,
                        value=_MULTI_BLOCK_LABELS[0],
                        label="Common Police Pattern",
                    )
                    .classes("w-full")
                    .props("outlined dense dark")
                )
                variations = ui.textarea(
                    label="Patterns (| Separates Variations, One Line Per Set To Try)",
                    value="",
                    placeholder="e.g. 6-2,5-3 | 6-3,5-2\n4-4,3-3",
                ).classes("w-full")
                ui.label(
                    "Each line is one rotation set the search will try. Add more lines to "
                    "have the solver consider several different multi-block combos, not just one."
                ).classes("sim-free-hint")

                def _apply_multi_catalog(e=None):
                    cat = _MULTI_BY_LABEL.get(multi_catalog.value or "")
                    if not cat:
                        return
                    if cat.get("variations"):
                        existing = (variations.value or "").strip()
                        variations.value = f"{existing}\n{cat['variations']}" if existing else cat["variations"]
                    st = (cat.get("style") or "rotating").lower()
                    rot_style.value = "Rotating" if st == "rotating" else "Fixed"
                    use_style.value = True
                    _set_enabled([rot_style, multi_catalog, variations], True)
                    _persist_form()

                multi_catalog.on_value_change(_apply_multi_catalog)
        use_style.on_value_change(lambda e: _set_enabled([rot_style, multi_catalog, variations], bool(e.value)))
        _set_enabled([rot_style, multi_catalog, variations], False)

        with _row():
            use_starts = given_solve_toggle(ui, "Shift Start Times")
            with ui.element("div"):
                starts = ui.input(
                    label="Starts (Comma-Separated)",
                    value="",
                    placeholder="e.g. 06:00, 14:00, 19:00, 22:00",
                ).classes("w-full")
                hint_starts = ui.label(
                    "If unchecked, we'll try common start-time combinations (e.g. 6am/2pm/10pm) for each shift length."
                ).classes("sim-free-hint")

        def _on_lock_starts(e=None):
            _set_enabled([starts], bool(use_starts.value))
            try:
                _refresh_space_estimate()
            except Exception:
                pass

        use_starts.on_value_change(_on_lock_starts)
        _set_enabled([starts], False)

    # ── Coverage Requirements — pass/fail checks on top of whatever schedule
    # the search axes produce; these don't change how many schedules are
    # tried, only whether a given one is accepted. ──
    with panel("Coverage Requirements"):
        with _row():
            use_min_ps = ui.checkbox("Require: Minimum Officers Per Shift", value=False)
            with ui.element("div"):
                min_ps = ui.input(
                    label="Minimum Officers Per Shift",
                    value="",
                    placeholder="e.g. 1",
                ).classes("w-full")

        def _on_lock_min_ps(e=None):
            _set_enabled([min_ps], bool(use_min_ps.value))
            try:
                _refresh_space_estimate()
            except Exception:
                pass

        use_min_ps.on_value_change(_on_lock_min_ps)
        _set_enabled([min_ps], False)

        with _row():
            use_247 = ui.checkbox("Require: 24/7 Continuous Minimum", value=False)
            with ui.element("div"):
                cov247 = ui.input(
                    label="Minimum On Duty At All Times",
                    value="",
                    placeholder="e.g. 1",
                ).classes("w-full")
        use_247.on_value_change(lambda e: _set_enabled([cov247], bool(e.value)))
        _set_enabled([cov247], False)

    # ── Hours & Fairness — total-hours math, not per-day coverage ──
    with panel("Hours & Fairness"):
        with _row():
            use_annual = ui.checkbox("Require: Annual Hours Target", value=False)
            with ui.element("div"):
                annual = ui.input(
                    label="Annual Hours Target",
                    value="",
                    placeholder="e.g. 2008",
                ).classes("w-full")
                annual_var = ui.input(
                    label="Allowed Variance (± Hours)",
                    value="",
                    placeholder="e.g. 20",
                ).classes("w-full")
        use_annual.on_value_change(lambda e: _set_enabled([annual, annual_var], bool(e.value)))
        _set_enabled([annual, annual_var], False)

        with _row():
            use_flsa = ui.checkbox("Require: Avoid FLSA Overtime", value=False)
            with ui.element("div"):
                flsa_days = (
                    ui.input(
                        label="FLSA Work Period Days (Set Automatically)",
                        value="",
                        placeholder="Rotation cycle length, capped at 28",
                    )
                    .props("readonly")
                    .classes("w-full")
                )
                ui.label(
                    "The §207(k) work period is your rotation's own cycle length (capped at 28 days, "
                    "the statutory max) — not something you set by hand."
                ).style(_HINT)
        use_flsa.on_value_change(lambda e: None)
        _set_enabled([flsa_days], False)

    # ── Fatigue & Flexibility — how a candidate schedule is built day-to-day ──
    with panel("Fatigue & Flexibility"):
        with _row():
            use_fatigue = ui.checkbox("Require: Fatigue / Rest Rules", value=False)
            with ui.element("div"):
                min_rest = ui.input(
                    label="Min Rest Hours Between Work Days",
                    value="",
                    placeholder="e.g. 8",
                ).classes("w-full")
                max_consec = ui.input(
                    label="Max Consecutive Work Days (0=off)",
                    value="",
                    placeholder="e.g. 6",
                ).classes("w-full")
                ui.label(
                    "Optional hard fatigue: rest between consecutive duty days; cap multi-block ON streaks."
                ).style(_HINT)
        use_fatigue.on_value_change(lambda e: _set_enabled([min_rest, max_consec], bool(e.value)))
        _set_enabled([min_rest, max_consec], False)

        with _row():
            use_nearby = ui.checkbox("Allow: Shift Flexibility (Work Days)", value=False)
            with ui.element("div"):
                nearby_hops = ui.input(
                    label="How Many Shift Slots An Officer Can Shift",
                    value="",
                    placeholder="e.g. 1",
                ).classes("w-full")
                ui.label("Example: an officer normally starting at 7pm could instead start at 2pm or 10pm.").style(
                    _HINT
                )
        use_nearby.on_value_change(lambda e: _set_enabled([nearby_hops], bool(e.value)))
        _set_enabled([nearby_hops], False)

        with _row():
            allow_offday = ui.checkbox("Allow Off-Day Coverage (OT Call-In)", value=False)
            with ui.element("div"):
                ui.label("Only when checked: multi-block OFF days may fill windows.").style(_HINT)

        with _row():
            use_certs = ui.checkbox("Require: Cert Codes (Fill Gate)", value=False).disable()
            with ui.element("div"):
                cert_codes = (
                    ui.input(
                        label="Cert Codes (Comma-Separated)",
                        value="",
                        placeholder="e.g. FTO, K9, EMT",
                    )
                    .classes("w-full")
                    .disable()
                )
                ui.label(
                    "Not available yet — the simulator does not model individual officer certifications. "
                    "This control has no effect on search results."
                ).style(_HINT)
        _set_enabled([cert_codes], False)

    with panel("Extra Minimum Staffing Windows"):
        ui.label(
            "When checked, every window below is a hard minimum. "
            "Windows are empty until you add them or restore a saved form. "
            "Demand templates convert peak-risk hours into windows."
        ).style(_HINT)
        use_windows = ui.checkbox("Require: Extra Minimum Staffing Windows", value=False)
        with ui.row().classes("gap-2 flex-wrap q-mb-sm"):
            for tmpl in list_demand_templates():

                def _apply_demand(tid=tmpl["id"], lab=tmpl["label"]):
                    if tid == "from_court_board":
                        r = court_board_to_demand_windows()
                        wins = list(r.get("windows") or [])
                        if not wins:
                            ui.notify(r.get("message") or "No court events", type="warning")
                            return
                        msg = r.get("message") or lab
                    else:
                        wins = get_demand_template(tid)
                        msg = lab
                    if not wins:
                        ui.notify("Unknown template", type="warning")
                        return
                    state["windows"] = list(wins)
                    use_windows.value = True
                    try:
                        _refresh_win_list()
                    except Exception:
                        pass
                    _persist_form()
                    ui.notify(f"Demand windows: {msg}", type="positive")
                    try:
                        _show_constraint_suggestions("windows")
                    except Exception:
                        pass

                ui.button(tmpl["label"][:32], on_click=_apply_demand).classes("btn-ghost").props(
                    "dense no-caps outline"
                )
        win_body = ui.column().classes("w-full")
        win_list_col = ui.column().classes("w-full gap-1 q-mb-sm")

        def _refresh_win_list():
            win_list_col.clear()
            with win_list_col:
                if not state["windows"]:
                    ui.label("No Windows Added Yet.").style("color:#7A8FA8;font-size:0.9rem")
                    return
                for i, w in enumerate(state["windows"]):
                    if w.get("specific_date"):
                        when = f"Date {w.get('specific_date')}"
                    elif w.get("weekday") is not None:
                        when = _WEEKDAY_TO_NAME.get(w.get("weekday"), f"Weekday {w.get('weekday')}")
                    else:
                        when = "Any Day"
                    line = (
                        f"#{i + 1} · Min {w.get('min_officers')} · "
                        f"{w.get('start_time')}–{w.get('end_time')} · "
                        f"{when} · {w.get('label') or 'Window'}"
                    )
                    with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                        ui.label(line).classes("text-sm").style("color:#E8EDF4;flex:1")

                        def _del(idx=i):
                            if 0 <= idx < len(state["windows"]):
                                state["windows"].pop(idx)
                                _refresh_win_list()

                        ui.button("Remove", on_click=_del).classes("btn-ghost").props("dense no-caps outline")

        with win_body:
            _refresh_win_list()
            w_min = ui.input(label="Min Officers", value="2").classes("w-full")
            w_start = ui.input(label="Start Time (HH:MM)", value="19:00").classes("w-full")
            w_end = ui.input(label="End Time (HH:MM)", value="03:00").classes("w-full")
            w_dow = (
                ui.select(_DOW_NAMES, value="Friday", label="Day Of Week")
                .classes("w-full")
                .props("outlined dense dark")
            )
            w_date = ui.input(label="Or Specific Date (M/D/YY, Optional)", value="").classes("w-full")
            w_label = ui.input(label="Label", value="Friday Night").classes("w-full")
            win_inputs = [w_min, w_start, w_end, w_dow, w_date, w_label]

            def add_window():
                if not use_windows.value:
                    ui.notify("Enable Extra Windows First", type="warning")
                    return
                try:
                    mn = int((w_min.value or "1").strip())
                except ValueError:
                    ui.notify("Min Officers Must Be A Number", type="negative")
                    return
                start = (w_start.value or "").strip()
                end = (w_end.value or "").strip()
                if not start or not end:
                    ui.notify("Start And End Times Required", type="negative")
                    return
                day_name = (w_dow.value or "Any Day").strip()
                weekday = _DOW_NAME_TO_WEEKDAY.get(day_name)
                specific_iso = None
                raw_d = (w_date.value or "").strip()
                if raw_d:
                    try:
                        specific_iso = storage_date_str(parse_date(raw_d))
                    except Exception:
                        ui.notify("Date Must Be M/D/YY", type="negative")
                        return
                state["windows"].append(
                    {
                        "min_officers": mn,
                        "start_time": start,
                        "end_time": end,
                        "weekday": weekday if not specific_iso else None,
                        "specific_date": specific_iso,
                        "label": (w_label.value or "").strip() or "Window",
                        "enabled": True,
                    }
                )
                _refresh_win_list()
                ui.notify(f"Window Added ({day_name})", type="positive")

            def load_dept_windows():
                try:
                    from logic import list_coverage_windows

                    n = 0
                    for row in list_coverage_windows() or []:
                        if row.get("enabled") is False:
                            continue
                        state["windows"].append(
                            {
                                "min_officers": row.get("min_officers") or 1,
                                "start_time": row.get("start_time"),
                                "end_time": row.get("end_time"),
                                "weekday": row.get("weekday"),
                                "specific_date": row.get("specific_date"),
                                "label": row.get("label") or "Window",
                                "enabled": True,
                            }
                        )
                        n += 1
                    _refresh_win_list()
                    ui.notify(f"Loaded {n} Department Window(s)", type="info")
                except Exception as exc:
                    ui.notify(f"Could Not Load: {exc}", type="negative")

            def apply_window_template(tid: str):
                wins = get_window_template(tid)
                if not wins:
                    ui.notify("Unknown template", type="warning")
                    return
                use_windows.value = True
                state["windows"] = list(wins)
                _refresh_win_list()
                ui.notify(f"Loaded window template ({len(wins)})", type="positive")

            with ui.row().classes("gap-2 flex-wrap q-mt-sm"):
                btn_add_win = (
                    ui.button("Add Window", on_click=add_window)
                    .classes("btn-primary")
                    .props("no-caps unelevated dense")
                )
                btn_load_win = (
                    ui.button("Load From Operations", on_click=load_dept_windows)
                    .classes("btn-ghost")
                    .props("no-caps outline dense")
                )
                for tmpl in list_window_templates():
                    tid = tmpl["id"]
                    ui.button(
                        tmpl["label"][:28],
                        on_click=lambda t=tid: apply_window_template(t),
                    ).classes("btn-ghost").props("no-caps outline dense")
                win_inputs.extend([btn_add_win, btn_load_win])

        def _sync_win_enabled(e=None):
            _set_enabled(win_inputs, bool(use_windows.value))

        use_windows.on_value_change(_sync_win_enabled)

    ui_elements = {
        "use_start_date": use_start_date,
        "sim_start_date": sim_start_date,
        "use_rotation": use_rotation,
        "rotation": rotation,
        "use_officers": use_officers,
        "officers": officers,
        "officers_range_lo": officers_range_lo,
        "officers_range_hi": officers_range_hi,
        "use_length": use_length,
        "length": length,
        "use_annual": use_annual,
        "annual": annual,
        "annual_var": annual_var,
        "use_starts": use_starts,
        "starts": starts,
        "use_min_ps": use_min_ps,
        "min_ps": min_ps,
        "use_247": use_247,
        "cov247": cov247,
        "use_style": use_style,
        "rot_style": rot_style,
        "multi_catalog": multi_catalog,
        "variations": variations,
        "use_nearby": use_nearby,
        "nearby_hops": nearby_hops,
        "allow_offday": allow_offday,
        "use_certs": use_certs,
        "cert_codes": cert_codes,
        "use_fatigue": use_fatigue,
        "min_rest": min_rest,
        "max_consec": max_consec,
        "use_flsa": use_flsa,
        "flsa_days": flsa_days,
        "use_windows": use_windows,
        "_refresh_win_list": _refresh_win_list,
        "hint_rotation": hint_rotation,
        "hint_officers": hint_officers,
        "hint_length": hint_length,
        "hint_starts": hint_starts,
        "hint_style": hint_style,
        "win_inputs": win_inputs,
    }
    return ui_elements
