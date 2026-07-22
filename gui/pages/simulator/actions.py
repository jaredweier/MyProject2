"""Simulator step-2/3/4 action-button handlers.

Extracted from gui/pages/simulator/page.py's single render_simulator() closure
(stage 1 of a full split — see docs/NEXT_SESSION_BRIEF.md). Function BODIES
below are unchanged copies of the originals; only the surrounding wiring
(widget access, callback access) changed, to keep transcription risk low.

Callbacks are looked up in the `callbacks` dict AT CALL TIME via the thin
passthrough wrappers below, not captured as bound function objects at build
time. This matters for `set_summary` specifically: page.py redefines it
partway through body() (to also track state["last_summary"] for
copy_summary/export_config). Capturing the function object here at
build_action_handlers() call time would bind the pre-redefinition version and
silently break that tracking — the same "dropped helper" bug class already
documented multiple times in this repo's session history. Dict lookup at
call time always sees whatever page.py has set most recently.
"""

from __future__ import annotations

from nicegui import ui

from gui import session
from logic import (
    create_shift_bid_from_simulation,
    export_simulation_csv,
    preview_implement_plan,
    recommend_implement_dates,
    save_simulator_scenario,
)
from logic.optimizer_features import (
    diff_options,
    export_ranked_options_csv,
    export_search_audit_json,
    export_share_eml,
    fairness_report,
    fairness_report_with_roster,
    format_share_message,
    option_seed_from_row,
    pin_option,
    save_scenario_slot,
)
from logic.sim_product_pack import (
    apply_sim_winner_to_draft_month,
    fairness_report_full,
    import_live_department_constraints,
    plain_english_staffing_explain,
    sensitivity_headcount,
    sensitivity_relax_night_min,
    try_cpsat_when_small,
)


def build_action_handlers(state: dict, widgets: dict, callbacks: dict) -> dict:
    """Return a dict of button handlers. `widgets` merges ui_elements +
    step4_elements (officers/length/starts/... + impl_date/apply_officers).
    `callbacks` carries the still-page.py-local closures these handlers need
    (set_action_log, set_summary, set_why, set_plan, _current_config,
    _refresh_space_estimate, go_step, _apply_ranked_option)."""

    officers = widgets["officers"]
    use_officers = widgets["use_officers"]
    length = widgets["length"]
    use_length = widgets["use_length"]
    starts = widgets["starts"]
    use_starts = widgets["use_starts"]
    min_ps = widgets["min_ps"]
    use_min_ps = widgets["use_min_ps"]
    variations = widgets["variations"]
    use_style = widgets["use_style"]
    rotation = widgets["rotation"]
    use_windows = widgets["use_windows"]
    impl_date = widgets["impl_date"]
    apply_officers = widgets["apply_officers"]

    # Late-bound passthroughs — see module docstring.
    def set_action_log(text: str, *, ok: bool | None = None):
        return callbacks["set_action_log"](text, ok=ok)

    def set_summary(text: str):
        return callbacks["set_summary"](text)

    def set_why(text: str = ""):
        return callbacks["set_why"](text)

    def set_plan(text: str):
        return callbacks["set_plan"](text)

    def _current_config():
        return callbacks["_current_config"]()

    def _refresh_space_estimate():
        return callbacks["_refresh_space_estimate"]()

    def go_step(n: int):
        return callbacks["go_step"](n)

    def _apply_ranked_option(row: dict):
        return callbacks["_apply_ranked_option"](row)

    def save_scenario():
        if not state.get("result"):
            ui.notify("Run Coverage First", type="warning")
            return
        uid = (session.current_user() or {}).get("id")
        name = f"Scenario {rotation.value} · {officers.value} Officers"
        tags = ["chronos"]
        if "8" in str(length.value or ""):
            tags.append("8h")
        if use_windows.value:
            tags.append("windows")
        r = save_simulator_scenario(
            name,
            config=state.get("config") or _current_config(),
            result=state.get("result"),
            user_id=uid,
            notes="Saved From Chronos Simulator",
            tags=tags,
        )
        if r.get("success"):
            set_action_log(f"Save OK\nScenario Id: {r.get('scenario_id')}", ok=True)
            ui.notify(f"Saved #{r.get('scenario_id')}", type="positive")
        else:
            set_action_log(f"Save Failed\n{r.get('message')}", ok=False)

    def preview_publish():
        from logic import get_last_optimized_plan

        res = state.get("result")
        cfg = state.get("config")
        if not res or not res.get("success"):
            stored = get_last_optimized_plan()
            if stored:
                res, cfg = stored.get("result"), stored.get("config")
        if not res:
            ui.notify("No plan to preview", type="warning")
            return
        r = preview_implement_plan(
            start_date=(impl_date.value or "").strip(),
            result=res,
            config=cfg or _current_config(),
            apply_officer_assignments=bool(apply_officers.value),
        )
        set_action_log(r.get("text") or r.get("message") or "Preview", ok=True)
        ui.notify("Publish preview (dry run)", type="info")

    def export_csv():
        if not state.get("result"):
            ui.notify("Run Coverage First", type="warning")
            return
        r = export_simulation_csv(state["result"])
        if r.get("success"):
            set_action_log(f"Export OK\nPath: {r.get('path')}", ok=True)
            ui.notify(f"Exported: {r.get('path')}", type="positive")
        else:
            set_action_log(f"Export Failed\n{r.get('message')}", ok=False)

    def bid_from_sim():
        if not state.get("result"):
            ui.notify("Run Coverage First", type="warning")
            return
        uid = (session.current_user() or {}).get("id")
        r = create_shift_bid_from_simulation(state["result"], publish=False, user_id=uid)
        if r.get("success"):
            set_action_log(f"Bid Draft OK\nEvent Id: {r.get('event_id')}", ok=True)
            ui.notify(f"Bid Draft #{r.get('event_id')}", type="positive")
        else:
            set_action_log(f"Bid Failed\n{r.get('message')}", ok=False)

    def export_options():
        ranked = state.get("ranked") or []
        if not ranked:
            ui.notify("No options to export", type="warning")
            return
        r = export_ranked_options_csv(ranked)
        if r.get("success"):
            ui.notify(f"Exported {r.get('path')}", type="positive")
            set_summary(f"Options CSV:\n{r.get('path')}")
        else:
            ui.notify("Export failed", type="negative")

    def export_audit():
        res = state.get("opt_result")
        if not res:
            ui.notify("Run Find Best first", type="warning")
            return
        r = export_search_audit_json(res)
        if r.get("success"):
            ui.notify(f"Audit: {r.get('path')}", type="positive")
            set_summary(f"Search audit JSON:\n{r.get('path')}")
        else:
            ui.notify("Audit export failed", type="negative")

    def run_diff_ab():
        a, b = state.get("compare_a"), state.get("compare_b")
        if not a or not b:
            ui.notify("Mark Option A and Option B first", type="warning")
            return
        lines = diff_options(a, b)
        set_summary("\n".join(lines))
        set_why("Side-by-side option comparison")

    def run_fairness():
        res = state.get("result") or state.get("opt_result") or {}
        full = fairness_report_full(res)
        lines = full.get("lines") or fairness_report_with_roster(res)
        if len(lines) < 3:
            lines = fairness_report(res)
        set_plan("\n".join(lines))
        set_summary("Fairness report in Plan Detail (roster names mapped)")
        ui.notify("Fairness report ready", type="info")

    def run_plain_explain():
        res = state.get("opt_result") or state.get("result") or {}
        exp = plain_english_staffing_explain(res)
        set_why(exp.get("text") or exp.get("message") or "")
        ui.notify("Plain-English explain ready", type="info")

    def run_sensitivity():
        from logic.optimizer_features import load_form_snapshot

        cfg = state.get("last_config") or state.get("form") or load_form_snapshot() or {}
        if not isinstance(cfg, dict):
            cfg = {}
        if state.get("opt_result"):
            cfg = dict(cfg)
            cfg["_cached_result"] = state.get("opt_result")
        sens = sensitivity_headcount(cfg, deep=False)
        night = sensitivity_relax_night_min(cfg, deep=False)
        text = (sens.get("text") or "") + "\n\n" + (night.get("text") or "")
        set_summary(text)
        ui.notify("Sensitivity complete (cheap mode)", type="info")

    def run_import_live():
        r = import_live_department_constraints()
        if r.get("success"):
            form = r.get("form") or {}
            state["form"] = form
            set_summary(
                "Loaded live department constraints (no invented defaults):\n"
                + "\n".join(f"  {k}: {v}" for k, v in list(form.items())[:20])
            )
            ui.notify(r.get("message") or "Loaded", type="positive")
        else:
            ui.notify(r.get("message") or "Import failed", type="negative")

    def run_apply_winner_month():
        res = state.get("opt_result") or state.get("result")
        cfg = state.get("last_config") or state.get("form") or {}
        rec = recommend_implement_dates()
        start = rec.get("recommended_date") or ""
        uid = (session.current_user() or {}).get("id")
        r = apply_sim_winner_to_draft_month(
            start_date=start,
            result=res,
            config=cfg if isinstance(cfg, dict) else {},
            user_id=uid,
        )
        ui.notify(
            r.get("message") or ("Applied" if r.get("success") else "Apply failed"),
            type="positive" if r.get("success") else "warning",
        )
        if r.get("success"):
            set_summary((r.get("preview") or {}).get("text") or r.get("message") or "Draft month applied")

    def run_cpsat_small():
        from logic.optimizer_features import load_form_snapshot

        cfg = state.get("last_config") or state.get("form") or load_form_snapshot() or {}
        if not isinstance(cfg, dict):
            cfg = {}
        r = try_cpsat_when_small(cfg)
        if r.get("skipped"):
            ui.notify(r.get("message") or "CP-SAT skipped", type="info")
            return
        if r.get("success"):
            state["opt_result"] = r
            exp = plain_english_staffing_explain(r)
            set_why(exp.get("text") or "")
            ui.notify("CP-SAT solved", type="positive")
        else:
            ui.notify(r.get("message") or "CP-SAT failed — use beam search", type="warning")

    def do_pin():
        row = state.get("selected_row")
        if not row:
            ranked = state.get("ranked") or []
            row = ranked[0] if ranked else None
        if not row:
            ui.notify("Select an option first", type="warning")
            return
        r = pin_option(row)
        ui.notify(f"Pinned: {r.get('label')}", type="positive")

    def do_share():
        res = state.get("opt_result") or {}
        if not res.get("best") and state.get("result"):
            res = {
                "best": state.get("selected_row") or (state.get("ranked") or [None])[0],
                "message": "Selected option",
                "scenarios_evaluated": (state.get("opt_result") or {}).get("scenarios_evaluated"),
                "wall_time_ms": (state.get("opt_result") or {}).get("wall_time_ms"),
            }
        body = format_share_message(res if res.get("best") else state.get("opt_result"))
        r = export_share_eml(state.get("opt_result") or res)
        try:
            ui.clipboard.write(body)
            ui.notify(f"Share text copied · .eml {r.get('path')}", type="positive")
        except Exception:
            set_why(body + f"\n\n.eml: {r.get('path')}")
            ui.notify("Share text in Why panel", type="info")

    def save_slot(letter: str):
        r = save_scenario_slot(
            letter,
            config=state.get("config") or _current_config(),
            result=state.get("result") or state.get("opt_result"),
            ranked_row=state.get("selected_row"),
        )
        ui.notify(f"Saved scenario slot {r.get('slot')}", type="positive")

    def lock_selected_seed():
        row = state.get("selected_row")
        if not row:
            ranked = state.get("ranked") or []
            row = ranked[0] if ranked else None
        if not row:
            ui.notify("Select an option first", type="warning")
            return
        seed = option_seed_from_row(row)
        if seed.get("num_officers") is not None:
            officers.value = str(seed["num_officers"])
            use_officers.value = True
        if seed.get("shift_length_hours") is not None:
            length.value = str(seed["shift_length_hours"])
            use_length.value = True
        if seed.get("shift_starts"):
            starts.value = ", ".join(seed["shift_starts"])
            use_starts.value = True
        if seed.get("min_per_shift") is not None:
            min_ps.value = str(seed["min_per_shift"])
            use_min_ps.value = True
        if seed.get("rotation_variations"):
            variations.value = " | ".join(seed["rotation_variations"])
            use_style.value = True
        try:
            _refresh_space_estimate()
        except Exception:
            pass
        ui.notify("Locked form from selected option (seed for re-search)", type="positive")

    def apply_stay():
        row = state.get("selected_row")
        if not row:
            ui.notify("Select an option on Coverage step", type="warning")
            return
        _apply_ranked_option(row)
        ui.notify("Option applied — still on Publish", type="positive")

    def apply_and_publish_step():
        row = state.get("selected_row")
        if row:
            _apply_ranked_option(row)
        go_step(4)
        ui.notify("Option loaded — review Publish", type="info")

    return {
        "save_scenario": save_scenario,
        "preview_publish": preview_publish,
        "export_csv": export_csv,
        "bid_from_sim": bid_from_sim,
        "export_options": export_options,
        "export_audit": export_audit,
        "run_diff_ab": run_diff_ab,
        "run_fairness": run_fairness,
        "run_plain_explain": run_plain_explain,
        "run_sensitivity": run_sensitivity,
        "run_import_live": run_import_live,
        "run_apply_winner_month": run_apply_winner_month,
        "run_cpsat_small": run_cpsat_small,
        "do_pin": do_pin,
        "do_share": do_share,
        "save_slot": save_slot,
        "lock_selected_seed": lock_selected_seed,
        "apply_stay": apply_stay,
        "apply_and_publish_step": apply_and_publish_step,
    }
