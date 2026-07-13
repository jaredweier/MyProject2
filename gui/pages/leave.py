"""Time off + shift exchange."""

from __future__ import annotations

from nicegui import ui

from config import DATE_INPUT_HINT, DAY_OFF_REQUEST_TYPES, REQUEST_STATUS
from gui import session
from gui.clock import today_local
from gui.shell import layout, page_header, panel
from logic import (
    apply_ot_fill_selection,
    bulk_approve_auto_ok_requests,
    bulk_reject_pending_requests,
    create_day_off_request,
    create_shift_swap_request,
    describe_day_off_request,
    format_bump_suggestion,
    get_day_off_requests,
    get_day_off_requests_for_viewer,
    get_officers_by_seniority,
    get_ot_fill_mode,
    get_pending_day_off_requests,
    get_pending_shift_swap_requests,
    get_shift_swap_requests,
    list_ot_fill_candidates,
    plan_bump_chain,
    preview_best_coverage_plans,
    process_day_off_request,
    process_shift_swap,
    suggest_bump_chain,
    validate_bump_feasibility,
    validate_swap_feasibility,
)
from validators import format_date, parse_date


def _active_officers():
    officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
    if session.is_officer():
        oid = session.linked_officer_id()
        officers = [o for o in officers if o["id"] == oid]
    return officers


def render_leave() -> None:
    def body() -> None:
        from gui.shell import scheduling_subnav

        page_header(
            "Time Off Requests",
            "Submit and review leave with coverage plans · shift exchanges",
            kicker="Scheduling",
        )
        scheduling_subnav("time_off")
        tab = ui.tabs().classes("q-mb-md")
        with tab:
            t_req = ui.tab("Time Off")
            t_swap = ui.tab("Shift Swaps")
        panels = ui.tab_panels(tab, value=t_req).classes("w-full")
        with panels:
            with ui.tab_panel(t_req):
                _requests_panel()
            with ui.tab_panel(t_swap):
                _swaps_panel()

    layout("time_off", body)


def _requests_panel() -> None:
    officers = _active_officers()
    names = [o["name"] for o in officers] or ["—"]
    omap = {o["name"]: o["id"] for o in officers}

    with ui.element("div").classes("grid-2"):
        with panel("New Time-Off Request"):
            off = ui.select(names, value=names[0], label="Officer").classes("w-full")
            d_in = ui.input(
                label=f"Date ({DATE_INPUT_HINT})",
                placeholder=format_date(today_local()),
            ).classes("w-full")
            rtype = ui.select(list(DAY_OFF_REQUEST_TYPES), value=DAY_OFF_REQUEST_TYPES[0], label="Type").classes(
                "w-full"
            )
            notes = ui.input(label="Notes").classes("w-full")
            cov = ui.label("Coverage: not checked").classes("text-xs text-gray-400")
            preview_box = (
                ui.textarea(value="Coverage plan appears after preview.")
                .classes("w-full")
                .props("readonly outlined dense dark rows=5")
            )

            def preview():
                oid = omap.get(off.value)
                ds = (d_in.value or "").strip()
                if not oid or not ds:
                    return
                try:
                    parse_date(ds)
                except ValueError:
                    cov.set_text("Invalid date")
                    return
                context = describe_day_off_request(oid, ds)
                suggestion = context.get("suggestion") if context.get("success") else None
                if suggestion is None:
                    officer = next((o for o in get_officers_by_seniority() if o["id"] == oid), None)
                    if officer:
                        suggestion = suggest_bump_chain(
                            oid, ds, officer.get("squad") or "A", officer.get("shift_start") or "06:00"
                        )
                if suggestion:
                    ok = bool(getattr(suggestion, "success", False))
                    cov.set_text("Coverage: auto-approve ready" if ok else "Coverage: needs review")
                    preview_box.value = format_bump_suggestion(suggestion)

            def submit():
                if not session.can("requests.submit") and not session.can("requests.submit_any"):
                    ui.notify("No permission to submit", type="negative")
                    return
                oid = omap.get(off.value)
                if session.is_officer() and oid != session.linked_officer_id():
                    ui.notify("Officers may only submit for themselves", type="warning")
                    return
                ds = (d_in.value or "").strip()
                try:
                    parse_date(ds)
                except ValueError:
                    ui.notify("Invalid date", type="negative")
                    return
                result = create_day_off_request(oid, ds, rtype.value, (notes.value or "").strip())
                if result.get("success"):
                    ui.notify(f"Request #{result['request_id']} submitted", type="positive")
                    notes.value = ""
                    _request_queue.refresh()
                else:
                    ui.notify(result.get("message", "Failed"), type="negative")

            with ui.row().classes("gap-2 q-mt-sm"):
                ui.button("Preview coverage", on_click=preview).classes("btn-ghost").props("no-caps outline")
                ui.button("Submit request", on_click=submit).classes("btn-primary").props("no-caps unelevated")

        with panel("Request Queue"):
            if session.can("requests.approve"):

                def bulk():
                    result = bulk_approve_auto_ok_requests()
                    msg = result.get("message") or (
                        f"Approved {result.get('approved', result.get('count', 0))}"
                        if result.get("success")
                        else result.get("message", "Bulk failed")
                    )
                    ui.notify(msg, type="positive" if result.get("success") else "warning")
                    _request_queue.refresh()

                def bulk_rej():
                    result = bulk_reject_pending_requests(admin_notes="Bulk rejected from Chronos")
                    ui.notify(
                        result.get("message", "Rejected") if result.get("success") else result.get("message", "Failed"),
                        type="info" if result.get("success") else "negative",
                    )
                    _request_queue.refresh()

                with ui.row().classes("gap-2 q-mb-sm flex-wrap"):
                    ui.button("Bulk approve auto-OK", on_click=bulk).classes("btn-ghost").props("no-caps outline dense")
                    ui.button("Bulk reject pending", on_click=bulk_rej).classes("btn-danger").props(
                        "no-caps outline dense"
                    )
                ui.label("Auto-OK = engine fully covered. Bulk reject clears pending queue with notes.").classes(
                    "text-xs text-gray-500 q-mb-sm"
                )
            _request_queue()


@ui.refreshable
def _request_queue() -> None:
    if session.can("requests.approve"):
        # Full list API (status filter) + pending convenience
        all_pending = get_day_off_requests(status_filter=REQUEST_STATUS.get("pending") or "Pending")
        pending_manual = get_day_off_requests(
            status_filter=REQUEST_STATUS.get("pending_manual") or "Pending Manual Review"
        )
        by_id = {r["id"]: r for r in (all_pending or []) + (pending_manual or []) if r.get("id") is not None}
        requests = list(by_id.values()) or get_pending_day_off_requests()
    else:
        role = (session.current_user() or {}).get("role") or ""
        data = get_day_off_requests_for_viewer(role, linked_officer_id=session.linked_officer_id())
        requests = [
            r
            for r in (data.get("requests") or [])
            if r.get("status") in (REQUEST_STATUS["pending"], REQUEST_STATUS["pending_manual"])
        ]
    if not requests:
        ui.html('<div class="alert alert-ok">Queue clear — no pending time off.</div>', sanitize=False)
        return
    # Enterprise density: grid overview + action rows (AG Grid pattern from NiceGUI docs)
    if session.can("requests.approve") and len(requests) > 3:
        try:
            from gui.tables import aggrid_from_dicts

            grid_rows = [
                {
                    "id": r.get("id"),
                    "officer": r.get("officer_name") or r.get("officer_id"),
                    "type": r.get("request_type"),
                    "date": format_date(r.get("request_date")) if r.get("request_date") else "",
                    "squad": r.get("squad"),
                    "shift": r.get("shift_start"),
                    "status": r.get("status"),
                }
                for r in requests
                if isinstance(r, dict)
            ]
            aggrid_from_dicts(
                grid_rows,
                prefer_columns=["id", "officer", "type", "date", "squad", "shift", "status"],
                height="220px",
                csv_export=True,
                csv_name="leave_queue",
            )
        except Exception:
            pass
    for req in requests:
        with ui.element("div").classes("data-row"):
            with ui.element("div"):
                ui.label(f"{req.get('officer_name', 'Officer')} · {req.get('request_type', '')}").classes(
                    "text-sm font-semibold"
                )
                ui.label(
                    f"{format_date(req['request_date'])} · {req.get('squad', '')} {req.get('shift_start', '')} · {req.get('status')}"
                ).classes("text-xs text-gray-500")
            status = req.get("status") or ""
            if status == REQUEST_STATUS.get("pending_manual") or status == "Pending Manual Review":
                ui.badge("Manual review", color="orange").props("outline dense")
            if session.can("requests.approve") and status in (
                REQUEST_STATUS["pending"],
                REQUEST_STATUS["pending_manual"],
            ):
                with ui.row().classes("gap-1"):
                    ui.button("Plans", on_click=lambda r=req: _show_plans(r)).props("dense no-caps flat")
                    ui.button("Approve", on_click=lambda r=req: _confirm_approve(r)).classes("btn-primary").props(
                        "dense no-caps unelevated"
                    )
                    ui.button("Reject", on_click=lambda r=req: _reject_dialog(r)).classes("btn-danger").props(
                        "dense no-caps"
                    )


def _plan_summary_text(plan: dict) -> str:
    """One-screen summary for approve confirm."""
    msg = (plan.get("message") or "").strip() or "Coverage plan"
    score = plan.get("plan_score")
    if score is not None:
        msg = f"{msg} · score {score}"
    steps = plan.get("steps") or []
    if steps:
        lines = []
        for s in steps[:8]:
            rep = s.get("replacement") or s.get("replacement_name") or "?"
            orig = s.get("original") or s.get("original_name") or "?"
            step_n = s.get("step", "")
            lines.append(f"  {step_n}. {rep} covers {orig}".strip())
        msg = msg + "\n" + "\n".join(lines)
    chain = plan.get("chain") or []
    if chain and not steps:
        msg = msg + "\n  Chain: " + " → ".join(f"{a}←{b}" for a, b in chain[:8])
    return msg


def _run_approve(req, preferred_chain=None, plan_score=None) -> None:
    result = process_day_off_request(req["id"], action="approve", preferred_chain=preferred_chain)
    if getattr(result, "success", False):
        extra = f" (plan score {plan_score})" if plan_score is not None else ""
        ui.notify(f"{result.message}{extra}", type="positive")
    elif getattr(result, "requires_manual", False):
        ui.notify(f"Manual review: {result.message}", type="warning")
    else:
        ui.notify(getattr(result, "message", "Failed"), type="negative")
    _request_queue.refresh()


def _confirm_approve(req) -> None:
    """Approve dialog: pick one cover + sticky actions (readable / clickable)."""
    try:
        oid = int(req["officer_id"])
        rdate = req["request_date"]
        squad = req.get("squad") or ""
        shift = req.get("shift_start") or ""
        officer = req.get("officer_name") or f"Officer #{oid}"
        date_s = format_date(rdate) if rdate else str(rdate)
        rid = int(req["id"])
        payload = preview_best_coverage_plans(oid, rdate, squad, shift, max_plans=3)
        plans = [p for p in (payload.get("plans") or []) if p.get("success")]
        fill = list_ot_fill_candidates(oid, rdate, squad, shift)
        candidates = fill.get("candidates") or [] if fill.get("success") else []
        mode_label = fill.get("mode_label") or get_ot_fill_mode()
        uid = (session.current_user() or {}).get("id")

        # Eligible covers only (order-in path). Cap list for readable select.
        eligible = [c for c in candidates if not c.get("ineligible_for_order") and c.get("officer_id") is not None][:12]
        by_id = {int(c["officer_id"]): c for c in eligible}
        # Use int keys only (NiceGUI select is happier than None keys).
        NONE_COVER = -1
        cover_options: dict[int, str] = {NONE_COVER: "— Select cover officer —"}
        for c in eligible:
            cid = int(c["officer_id"])
            duty = "ON" if c.get("on_duty") else "OFF"
            cover_options[cid] = (
                f"#{c.get('offer_order', '?')} · {c.get('name')} · {duty} · "
                f"rank {c.get('seniority_rank', '—')} · {c.get('shift_start') or '—'}"
            )
        default_cover = next(iter(by_id), NONE_COVER)
        plan_options: dict[int, str] = {0: "— No auto plan —"}
        for i, plan in enumerate(plans[:3], 1):
            score = plan.get("plan_score")
            plan_options[i] = f"Auto plan {i}" + (f" · score {score}" if score is not None else "")

        with ui.dialog().props("persistent") as dlg:
            with (
                ui.card()
                .classes("leave-approve-dlg w-full")
                .style(
                    "width:min(520px,94vw);max-height:85vh;display:flex;flex-direction:column;"
                    "padding:16px 18px;gap:8px;background:#0c1220;color:#e2e8f0;"
                )
            ):
                ui.label(f"Approve — {officer}").classes("text-base font-semibold").style("color:#f1f5f9")
                ui.label(f"{date_s} · {req.get('request_type', '')} · {squad} {shift}").classes("text-xs").style(
                    "color:#94a3b8"
                )
                ui.label(f"Fill mode: {mode_label}").classes("text-xs").style("color:#fbbf24")

                cover_sel = (
                    ui.select(
                        cover_options,
                        value=default_cover,
                        label="Cover officer",
                    )
                    .classes("w-full")
                    .props("dark dense options-dense emit-value map-options")
                )

                detail = ui.label("").classes("text-xs").style("color:#94a3b8;min-height:1.2em")

                def _refresh_detail(_e=None):
                    try:
                        cid = int(cover_sel.value) if cover_sel.value is not None else NONE_COVER
                    except (TypeError, ValueError):
                        cid = NONE_COVER
                    if cid == NONE_COVER or cid not in by_id:
                        detail.set_text("Pick a cover, or use auto plan / approve without cover.")
                        return
                    c = by_id[cid]
                    hint = str(c.get("fill_hint") or "").strip()
                    ytd = (
                        f"YTD ordered {c.get('year_ordered_in', 0)} · "
                        f"turned down {c.get('year_turned_down', 0)} · "
                        f"volunteered {c.get('year_volunteered', 0)}"
                    )
                    detail.set_text(f"{ytd}" + (f" · {hint}" if hint else ""))

                cover_sel.on_value_change(_refresh_detail)
                _refresh_detail()

                plan_sel = None
                if plans:
                    plan_sel = (
                        ui.select(
                            plan_options,
                            value=1,
                            label="Auto bump plan (optional)",
                        )
                        .classes("w-full")
                        .props("dark dense options-dense emit-value map-options")
                    )
                    best = _plan_summary_text(plans[0])
                    ui.textarea(value=best).classes("w-full").props("readonly outlined dense dark rows=3").style(
                        "font-size:12px"
                    )
                else:
                    ui.label("No auto-coverage plan scored for this day.").classes("text-xs").style("color:#fb923c")

                def _notify_result(r: dict) -> None:
                    ok = bool(r.get("success"))
                    ui.notify(
                        r.get("message", "Done") if ok else r.get("message", "Failed"),
                        type="positive" if ok else "warning",
                    )
                    _request_queue.refresh()

                def _selected_cover_id() -> int | None:
                    try:
                        cid = int(cover_sel.value) if cover_sel.value is not None else NONE_COVER
                    except (TypeError, ValueError):
                        return None
                    if cid == NONE_COVER or cid not in by_id:
                        return None
                    return cid

                def _close_dlg() -> None:
                    try:
                        dlg.close()
                    except Exception:
                        pass
                    try:
                        dlg.delete()
                    except Exception:
                        pass

                def do_order_in():
                    cid = _selected_cover_id()
                    if cid is None:
                        ui.notify("Select a cover officer first", type="warning")
                        return
                    r = apply_ot_fill_selection(
                        rid,
                        cid,
                        response="ordered_in",
                        is_partial=False,
                        turned_down_ids=[],
                        actor_user_id=uid,
                    )
                    _close_dlg()
                    _notify_result(r if isinstance(r, dict) else {"success": False, "message": str(r)})

                def do_volunteer():
                    cid = _selected_cover_id()
                    if cid is None:
                        ui.notify("Select a cover officer first", type="warning")
                        return
                    r = apply_ot_fill_selection(
                        rid,
                        cid,
                        response="volunteered",
                        is_partial=False,
                        turned_down_ids=[],
                        actor_user_id=uid,
                    )
                    _close_dlg()
                    _notify_result(r if isinstance(r, dict) else {"success": False, "message": str(r)})

                def do_auto_plan():
                    if not plans:
                        ui.notify("No auto plan available", type="warning")
                        return
                    idx = 1
                    if plan_sel is not None and plan_sel.value not in (None, 0, "0"):
                        try:
                            idx = int(plan_sel.value)
                        except (TypeError, ValueError):
                            idx = 1
                    plan = plans[min(max(idx, 1), len(plans)) - 1]
                    _run_approve(
                        req,
                        preferred_chain=plan.get("chain") or None,
                        plan_score=plan.get("plan_score"),
                    )
                    _close_dlg()

                def do_without_cover():
                    _run_approve(req, preferred_chain=None)
                    _close_dlg()

                # Sticky footer — always on screen, primary path for humans
                with (
                    ui.row()
                    .classes("w-full gap-2 flex-wrap q-mt-sm")
                    .style(
                        "border-top:1px solid rgba(148,163,184,0.25);padding-top:12px;"
                        "position:sticky;bottom:0;background:#0c1220;z-index:5;"
                    )
                ):
                    ui.button("Order in", on_click=do_order_in).classes("btn-primary").props("no-caps unelevated dense")
                    ui.button("Volunteer", on_click=do_volunteer).classes("btn-ghost").props("no-caps outline dense")
                    if plans:
                        ui.button("Use auto plan", on_click=do_auto_plan).classes("btn-ghost").props(
                            "no-caps outline dense"
                        )
                    ui.button("Approve no cover", on_click=do_without_cover).classes("btn-ghost").props(
                        "no-caps outline dense"
                    )
                    ui.button("Cancel", on_click=dlg.close).classes("btn-ghost").props("no-caps flat dense")

                if not eligible:
                    ui.label("No order-eligible covers ranked — use auto plan or Approve no cover.").classes(
                        "text-xs"
                    ).style("color:#fb923c")

        dlg.open()
    except Exception as exc:
        ui.notify(f"Approve dialog failed: {exc}", type="negative")


def _show_plans(req) -> None:
    try:
        oid = req["officer_id"]
        rdate = req["request_date"]
        squad = req.get("squad") or ""
        shift = req.get("shift_start") or ""
        payload = preview_best_coverage_plans(oid, rdate, squad, shift, max_plans=5)
        try:
            from logic.plan_explain import explain_coverage_plans

            text = explain_coverage_plans(payload if isinstance(payload, dict) else {})
        except Exception:
            text = str(payload)[:900]
        try:
            feas = validate_bump_feasibility(oid, rdate, squad, shift)
            feas_line = getattr(feas, "message", None) or str(feas)
        except Exception as exc:
            feas_line = f"Feasibility check unavailable: {exc}"
        try:
            chain, chain_msg = plan_bump_chain(oid, rdate, squad, shift)
            chain_line = f"Chain steps: {len(chain or [])}" + (f" · {chain_msg}" if chain_msg else "")
            if chain:
                chain_line += " · " + " → ".join(f"{a}←{b}" for a, b in chain[:8])
        except Exception as exc:
            chain_line = f"Chain plan unavailable: {exc}"
        text = f"Feasibility: {feas_line}\n{chain_line}\n\n{text or 'No scored plans'}"
        with ui.dialog() as dlg:
            with (
                ui.card()
                .classes("w-full")
                .style("width:min(480px,94vw);max-height:80vh;padding:16px;background:#0c1220;color:#e2e8f0;")
            ):
                ui.label("Coverage plans — explainable scores").classes("text-sm font-semibold q-mb-sm").style(
                    "color:#f1f5f9"
                )
                ui.textarea(value=text).classes("w-full").props("readonly outlined dense dark rows=12")
                ui.button("Close", on_click=dlg.close).classes("btn-ghost q-mt-sm").props("no-caps flat dense")
        dlg.open()
    except Exception as exc:
        ui.notify(f"Plans dialog failed: {exc}", type="negative")


def _reject_dialog(req) -> None:
    """Reject with optional admin notes (logic already supports admin_notes)."""
    rid = req["id"]
    officer = req.get("officer_name") or f"#{rid}"
    with ui.dialog() as dlg, ui.card().classes("w-full").style("min-width:min(400px,92vw);max-width:480px"):
        ui.label(f"Reject request — {officer}").classes("text-sm font-semibold q-mb-sm")
        notes = ui.input(label="Notes (optional)", placeholder="Reason shown in audit / notify").classes("w-full")

        def do_reject():
            result = process_day_off_request(rid, action="reject", admin_notes=(notes.value or "").strip())
            dlg.close()
            ui.notify(getattr(result, "message", str(result)), type="info")
            _request_queue.refresh()

        with ui.row().classes("gap-2 q-mt-md w-full justify-end"):
            ui.button("Cancel", on_click=dlg.close).classes("btn-ghost").props("no-caps flat")
            ui.button("Confirm reject", on_click=do_reject).classes("btn-danger").props("no-caps outline")
    dlg.open()


def _swaps_panel() -> None:
    officers = _active_officers()
    names = [o["name"] for o in officers] or ["—"]
    omap = {o["name"]: o["id"] for o in officers}

    with ui.element("div").classes("grid-2"):
        with panel("New Shift Exchange"):
            o1 = ui.select(names, value=names[0], label="Officer 1").classes("w-full")
            o2 = ui.select(names, value=names[min(1, len(names) - 1)], label="Officer 2").classes("w-full")
            d_in = ui.input(
                label=f"Swap Date ({DATE_INPUT_HINT})",
                placeholder=format_date(today_local()),
            ).classes("w-full")
            prev = ui.label("Validation: not checked").classes("text-xs text-gray-400")

            def validate():
                a, b = omap.get(o1.value), omap.get(o2.value)
                ds = (d_in.value or "").strip()
                try:
                    parse_date(ds)
                except ValueError:
                    prev.set_text("Invalid date")
                    return
                result = validate_swap_feasibility(a, b, ds)
                ok = bool(getattr(result, "success", result.get("success") if isinstance(result, dict) else False))
                msg = getattr(result, "message", None) or (
                    result.get("message") if isinstance(result, dict) else str(result)
                )
                prev.set_text(msg or ("OK" if ok else "Not feasible"))

            def submit():
                a, b = omap.get(o1.value), omap.get(o2.value)
                ds = (d_in.value or "").strip()
                result = create_shift_swap_request(a, b, ds)
                if result.get("success"):
                    ui.notify(f"Swap #{result.get('swap_id')} submitted", type="positive")
                    _swap_queue.refresh()
                else:
                    ui.notify(result.get("message", "Failed"), type="negative")

            with ui.row().classes("gap-2 q-mt-sm"):
                ui.button("Validate", on_click=validate).classes("btn-ghost").props("no-caps outline")
                ui.button("Submit swap", on_click=submit).classes("btn-primary").props("no-caps unelevated")

        with panel("Swap Queue"):
            _swap_queue()


@ui.refreshable
def _swap_queue() -> None:
    swaps = get_pending_shift_swap_requests() if session.can("swaps.approve") else get_shift_swap_requests()
    if not swaps:
        ui.html('<div class="alert alert-ok">No pending shift exchanges.</div>', sanitize=False)
        return
    for swap in swaps[:50]:
        with ui.element("div").classes("data-row"):
            with ui.element("div"):
                ui.label(f"{swap.get('officer1_name')} ⇄ {swap.get('officer2_name')}").classes("text-sm font-semibold")
                ui.label(f"{format_date(swap.get('swap_date'))} · {swap.get('status')}").classes(
                    "text-xs text-gray-500"
                )
            if session.can("swaps.approve") and swap.get("status") in ("Pending", "Pending Manual Review"):
                with ui.row().classes("gap-1"):
                    ui.button(
                        "Approve",
                        on_click=lambda sid=swap["id"]: _handle_swap(sid, "approve"),
                    ).classes("btn-primary").props("dense no-caps unelevated")
                    ui.button(
                        "Reject",
                        on_click=lambda sid=swap["id"]: _handle_swap(sid, "reject"),
                    ).classes("btn-danger").props("dense no-caps")


def _handle_swap(sid, action) -> None:
    result = process_shift_swap(sid, action=action)
    ok = getattr(result, "success", False)
    msg = getattr(result, "message", str(result))
    ui.notify(msg, type="positive" if ok else "warning")
    _swap_queue.refresh()
