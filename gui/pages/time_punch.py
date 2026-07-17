"""Time punch — officer clock + correction requests + supervisor policy/approvals."""

from __future__ import annotations

from nicegui import ui

from gui import session
from gui.shell import finance_subnav, layout, page_header, panel
from logic.geofence_clock import clock_status
from logic.time_punch import (
    approve_punch_edit,
    get_punch_policy,
    list_officer_punches,
    list_punch_edit_requests,
    officer_clock,
    reject_punch_edit,
    request_punch_edit,
    set_punch_required,
)


def render_time_punch() -> None:
    def body() -> None:
        page_header(
            "Time punch",
            "Clock in/out · correction requests · department punch policy",
            kicker="Chronos Command · Finance",
        )
        finance_subnav("time_punch")
        host = ui.element("div")

        def refresh():
            host.clear()
            with host:
                _policy_panel()
                oid = session.linked_officer_id()
                if oid:
                    _officer_clock_panel(int(oid), refresh)
                    _my_punches_and_edit(int(oid), refresh)
                elif session.is_officer():
                    ui.html(
                        '<div class="alert alert-warn">Link your user to an officer profile to punch.</div>',
                        sanitize=False,
                    )
                if (
                    session.can("timecard.approve")
                    or session.can("timecard.edit_all")
                    or session.can("payroll.edit")
                    or (not session.is_officer() and session.can("timecard.view_all"))
                ):
                    _supervisor_approvals(refresh)

        with ui.row().classes("gap-2 q-mb-md"):
            ui.button("Refresh", on_click=refresh).classes("btn-ghost").props("no-caps outline dense")
            ui.button("Timecards", on_click=lambda: ui.navigate.to("/timecards")).classes("btn-ghost").props(
                "no-caps outline dense"
            )
        refresh()

    layout("time_punch", body)


def _policy_panel() -> None:
    policy = get_punch_policy()
    can_set = (
        session.can("admin.settings")
        or session.can("settings.manage")
        or session.can("payroll.edit")
        or session.can("timecard.approve")
        or (not session.is_officer() and session.can("users.manage"))
    )
    with panel("Department policy", glow=True):
        ui.label(policy.get("mode_label") or "").classes("text-sm font-semibold")
        ui.label(policy.get("message") or "").classes("text-xs q-mb-sm").style("color: var(--dim)")
        ui.html(
            f'<div class="alert {"alert-warn" if policy.get("punch_required") else "alert-ok"}">'
            f"Punch required: <strong>{'ON' if policy.get('punch_required') else 'OFF (default)'}</strong> · "
            f"Manual officer time entry: "
            f"<strong>{'blocked' if policy.get('punch_required') else 'allowed'}</strong>"
            f"</div>",
            sanitize=False,
        )
        if can_set:
            sw = ui.switch(
                "Require staff to punch in/out (off = free time entry)",
                value=bool(policy.get("punch_required")),
            )

            def save_pol():
                uid = (session.current_user() or {}).get("id")
                r = set_punch_required(bool(sw.value), user_id=uid)
                ui.notify(r.get("message", "Saved"), type="positive" if r.get("success") else "negative")
                ui.navigate.to("/time-punch")

            ui.button("Save punch policy", on_click=save_pol).classes("btn-primary q-mt-sm").props("no-caps unelevated")
        else:
            ui.label("Only supervisors/admins can change this policy.").classes("text-xs").style("color: var(--dim)")


def _officer_clock_panel(oid: int, refresh) -> None:
    with panel("Clock in / out", glow=True):
        st = clock_status(oid)
        ui.label("Clocked IN" if st.get("clocked_in") else "Clocked OUT").classes("text-lg font-semibold q-mb-sm")
        ui.label("One tap — records the time now. Forgot a punch? Request a correction below.").classes(
            "text-xs q-mb-sm"
        ).style("color: var(--dim)")

        def do_in():
            uid = (session.current_user() or {}).get("id")
            r = officer_clock(oid, "in", user_id=uid, notes="time-punch page")
            ui.notify(r.get("message", "In"), type="positive" if r.get("success") else "negative")
            if r.get("success"):
                refresh()

        def do_out():
            uid = (session.current_user() or {}).get("id")
            r = officer_clock(oid, "out", user_id=uid, notes="time-punch page")
            ui.notify(r.get("message", "Out"), type="positive" if r.get("success") else "negative")
            if r.get("success"):
                refresh()

        with ui.row().classes("gap-3 flex-wrap"):
            ui.button("CLOCK IN", on_click=do_in).classes("btn-primary").props("no-caps unelevated size=lg")
            ui.button("CLOCK OUT", on_click=do_out).classes("btn-ghost").props("no-caps outline size=lg")

        # Optional geofence punch (uses station coords if fence configured)
        try:
            from logic.geofence_clock import get_geofence_config, record_geofence_punch

            gcfg = get_geofence_config()
            if gcfg.get("enabled") or gcfg.get("configured"):
                ui.label(
                    f"Geofence {'ON' if gcfg.get('enabled') else 'configured'} · "
                    f"station {gcfg.get('lat')},{gcfg.get('lon')} · r={gcfg.get('radius_m')}m"
                ).classes("text-xs q-mt-sm").style("color: var(--dim)")

                def geo_in():
                    r = record_geofence_punch(
                        oid,
                        "in",
                        lat=float(gcfg.get("lat") or 0),
                        lon=float(gcfg.get("lon") or 0),
                        notes="time-punch geofence",
                    )
                    ui.notify(
                        r.get("message", "In") if r.get("success") else r.get("message", "Blocked"),
                        type="positive" if r.get("success") else "warning",
                    )
                    if r.get("success"):
                        refresh()

                def geo_out():
                    r = record_geofence_punch(
                        oid,
                        "out",
                        lat=float(gcfg.get("lat") or 0),
                        lon=float(gcfg.get("lon") or 0),
                        notes="time-punch geofence",
                    )
                    ui.notify(
                        r.get("message", "Out") if r.get("success") else r.get("message", "Blocked"),
                        type="positive" if r.get("success") else "warning",
                    )
                    if r.get("success"):
                        refresh()

                with ui.row().classes("gap-2 q-mt-xs flex-wrap"):
                    ui.button("Geofence IN (station)", on_click=geo_in).classes("btn-ghost").props(
                        "no-caps outline dense"
                    )
                    ui.button("Geofence OUT (station)", on_click=geo_out).classes("btn-ghost").props(
                        "no-caps outline dense"
                    )
                    ui.button("Fence settings", on_click=lambda: ui.navigate.to("/deploy")).classes("btn-ghost").props(
                        "no-caps flat dense"
                    )
        except Exception:
            pass


def _my_punches_and_edit(oid: int, refresh) -> None:
    with panel("My punches · request a correction"):
        punches = list_officer_punches(oid, limit=25)
        if not punches:
            ui.label("No punches yet — use Clock In above.").classes("text-sm").style("color: var(--dim)")
            return
        labels = {
            f"#{p.get('id')} · {p.get('punch_type')} · {p.get('created_at')}"
            + (" · edited" if p.get("edited") else ""): p["id"]
            for p in punches
        }
        pick = ui.select(list(labels.keys()), value=list(labels.keys())[0], label="Punch to correct").classes("w-full")
        new_ts = ui.input(
            label="Correct date/time (M/D/YY HH:MM or YYYY-MM-DD HH:MM)",
            placeholder="7/16/26 08:00",
        ).classes("w-full")
        new_type = ui.select(["in", "out"], value="in", label="Correct type").classes("w-full")
        reason = ui.input(label="Reason (required)", placeholder="Forgot to clock out at end of shift").classes(
            "w-full"
        )

        def submit_edit():
            pid = labels.get(pick.value)
            if not pid:
                return
            uid = (session.current_user() or {}).get("id")
            r = request_punch_edit(
                int(pid),
                oid,
                proposed_created_at=(new_ts.value or "").strip(),
                proposed_punch_type=new_type.value or "in",
                reason=(reason.value or "").strip(),
                user_id=uid,
            )
            ui.notify(r.get("message", "Submitted"), type="positive" if r.get("success") else "negative")
            if r.get("success"):
                refresh()

        ui.button("Request correction (needs supervisor approval)", on_click=submit_edit).classes(
            "btn-primary q-mt-sm"
        ).props("no-caps unelevated")

        mine = list_punch_edit_requests(status="all", officer_id=oid, limit=10)
        if mine:
            ui.label("My recent correction requests").classes("text-xs q-mt-md font-semibold")
            for r in mine:
                ui.label(
                    f"#{r.get('id')} · {r.get('status')} · punch {r.get('punch_id')} · "
                    f"{r.get('proposed_created_at')} · {(r.get('reason') or '')[:50]}"
                ).classes("text-xs")

        ui.label("Recent punches").classes("text-xs q-mt-md font-semibold")
        for p in punches[:12]:
            ui.label(
                f"#{p.get('id')} · {p.get('punch_type')} · {p.get('created_at')}"
                + (" · (edited)" if p.get("edited") else "")
            ).classes("text-sm")


def _supervisor_approvals(refresh) -> None:
    with panel("Pending punch corrections (supervisor)", glow=True):
        pending = list_punch_edit_requests(status="pending", limit=40)
        if not pending:
            ui.html(
                '<div class="alert alert-ok">No pending punch corrections.</div>',
                sanitize=False,
            )
            return
        for req in pending:
            with ui.element("div").classes("data-row q-mb-sm"):
                ui.label(
                    f"#{req.get('id')} · {req.get('officer_name') or req.get('officer_id')} · "
                    f"punch #{req.get('punch_id')}"
                ).classes("text-sm font-semibold")
                ui.label(
                    f"{req.get('current_punch_type')} @ {req.get('current_created_at')} → "
                    f"{req.get('proposed_punch_type')} @ {req.get('proposed_created_at')}"
                ).classes("text-xs")
                ui.label(f"Reason: {req.get('reason') or '—'}").classes("text-xs").style("color: var(--dim)")
                notes = ui.input(label="Review notes", value="").classes("w-full")

                def approve(rid=req["id"], nwidget=notes):
                    uid = (session.current_user() or {}).get("id")
                    r = approve_punch_edit(int(rid), user_id=uid, review_notes=(nwidget.value or "").strip())
                    ui.notify(r.get("message", "OK"), type="positive" if r.get("success") else "negative")
                    refresh()

                def reject(rid=req["id"], nwidget=notes):
                    uid = (session.current_user() or {}).get("id")
                    r = reject_punch_edit(int(rid), user_id=uid, review_notes=(nwidget.value or "").strip())
                    ui.notify(r.get("message", "OK"), type="positive" if r.get("success") else "negative")
                    refresh()

                with ui.row().classes("gap-2 q-mt-xs"):
                    ui.button("Approve", on_click=approve).classes("btn-primary").props("dense no-caps unelevated")
                    ui.button("Reject", on_click=reject).classes("btn-ghost").props("dense no-caps outline")
