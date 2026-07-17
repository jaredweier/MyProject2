"""Callback / OT desired list rotation — inTime/Snap fairness pattern."""

from __future__ import annotations

from nicegui import ui

from gui import session
from gui.clock import today_local
from gui.shell import layout, page_header, panel
from logic import (
    get_callback_ledger,
    get_callback_rotation,
    get_next_callback_candidate,
    get_officers_by_seniority,
    record_callback_event,
    sync_callback_rotation_from_roster,
)
from logic.callbacks import (
    export_callback_equity_csv,
    record_callback_offer,
    run_callback_calldown,
)
from validators import format_date, parse_date


def render_callbacks() -> None:
    def body() -> None:
        page_header(
            "Callback Rotation",
            "Seniority call-down · auto offers · equity export",
            kicker="Ops",
        )
        if not (
            session.can("reports.view") or session.can("open_shifts.manage") or session.can("schedule.updated.edit")
        ):
            ui.html(
                '<div class="alert alert-warn">Callback board requires supervisor access.</div>',
                sanitize=False,
            )
            return

        host = ui.element("div")

        def refresh():
            host.clear()
            with host:
                _content()

        with ui.row().classes("gap-2 q-mb-md flex-wrap"):
            ui.button("Refresh", on_click=refresh).classes("btn-ghost").props("no-caps outline dense")

            def sync():
                uid = (session.current_user() or {}).get("id")
                r = sync_callback_rotation_from_roster(user_id=uid)
                ui.notify(
                    r.get("message", "Synced") if r.get("success") else r.get("message", "Fail"),
                    type="positive" if r.get("success") else "negative",
                )
                refresh()

            def auto_calldown():
                uid = (session.current_user() or {}).get("id")
                r = run_callback_calldown(
                    today_local().isoformat(),
                    max_offers=5,
                    notes="Auto call-down sequence",
                    user_id=uid,
                    notify=True,
                )
                ui.notify(
                    r.get("message", "Call-down done") if r.get("success") else r.get("message", "Failed"),
                    type="positive" if r.get("success") else "negative",
                )
                if r.get("success"):
                    refresh()

            def export_equity():
                r = export_callback_equity_csv()
                ui.notify(
                    r.get("message", r.get("path", "Exported"))
                    if r.get("success")
                    else r.get("message", "Export failed"),
                    type="positive" if r.get("success") else "negative",
                )

            ui.button("Sync From Roster", on_click=sync).classes("btn-primary").props("no-caps unelevated dense")
            ui.button("Auto Call-Down (Top 5)", on_click=auto_calldown).classes("btn-primary").props(
                "no-caps unelevated dense"
            )
            ui.button("Export Equity CSV", on_click=export_equity).classes("btn-ghost").props("no-caps outline dense")

        refresh()

    layout("callbacks", body)


def _content() -> None:
    nxt = get_next_callback_candidate() or {}
    cand = nxt.get("candidate") if nxt.get("success") else None
    rot = get_callback_rotation(active_only=True) or []
    officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
    names = [o["name"] for o in officers]
    omap = {o["name"]: o["id"] for o in officers}
    if cand and cand.get("officer_name") in omap:
        default = cand["officer_name"]
    else:
        default = names[0] if names else None

    with panel("Next callback candidate", glow=True):
        if cand:
            ui.label(
                f"{cand.get('officer_name')} · Squad {cand.get('squad')} · order #{cand.get('sort_order')}"
            ).classes("text-sm font-semibold")
            ui.label(f"Last callback: {format_date(cand.get('last_callback') or '') or 'none on file'}").classes(
                "text-xs text-gray-500"
            )
            ui.label("Offer the top candidate first, then log accept or decline.").classes(
                "text-xs text-gray-500 q-mt-xs"
            )

            def _oid():
                return cand.get("officer_id") or omap.get(cand.get("officer_name"))

            def offer_next():
                oid = _oid()
                if not oid:
                    ui.notify("No candidate officer id", type="warning")
                    return
                uid = (session.current_user() or {}).get("id")
                r = record_callback_offer(
                    int(oid),
                    today_local().isoformat(),
                    notes="OT offer (call-down) — pending accept",
                    user_id=uid,
                )
                ui.notify(
                    r.get("message", "Offer logged") if r.get("success") else r.get("message", "Failed"),
                    type="positive" if r.get("success") else "negative",
                )
                if r.get("success"):
                    ui.navigate.to("/callbacks")

            def decline_next():
                oid = _oid()
                if not oid:
                    ui.notify("No candidate officer id", type="warning")
                    return
                uid = (session.current_user() or {}).get("id")
                r = record_callback_offer(
                    int(oid),
                    today_local().isoformat(),
                    notes="OT offer declined — call next",
                    user_id=uid,
                    accepted=False,
                )
                ui.notify(
                    r.get("message", "Declined") if r.get("success") else r.get("message", "Failed"),
                    type="positive" if r.get("success") else "negative",
                )
                if r.get("success"):
                    ui.navigate.to("/callbacks")

            with ui.row().classes("gap-2 q-mt-sm flex-wrap"):
                ui.button("Log OT Offer To Next", on_click=offer_next).classes("btn-primary").props(
                    "no-caps unelevated dense"
                )
                ui.button("Decline / Call Next", on_click=decline_next).classes("btn-ghost").props(
                    "no-caps outline dense"
                )
        else:
            ui.html(
                f'<div class="alert alert-warn">{nxt.get("message") or "No candidate — sync roster."}</div>',
                sanitize=False,
            )

    with panel("Record callback / OT offer"):
        pick = ui.select(names, value=default, label="Officer").classes("w-full")
        d_in = ui.input(
            label="Event date (M/D/YY)",
            value=format_date(today_local()),
            placeholder=format_date(today_local()),
        ).classes("w-full")
        hours = ui.input(label="Hours offered/worked", value="4").classes("w-full")
        notes = ui.input(label="Notes", value="Callback OT").classes("w-full")

        def record():
            oid = omap.get(pick.value)
            dt = parse_date((d_in.value or "").strip())
            if not oid or not dt:
                ui.notify("Officer and valid date required", type="negative")
                return
            try:
                h = float((hours.value or "0").strip())
            except ValueError:
                ui.notify("Hours must be numeric", type="negative")
                return
            uid = (session.current_user() or {}).get("id")
            r = record_callback_event(oid, dt.isoformat(), h, notes=(notes.value or "").strip(), user_id=uid)
            ui.notify(
                r.get("message", "Recorded") if r.get("success") else r.get("message", "Failed"),
                type="positive" if r.get("success") else "negative",
            )
            if r.get("success"):
                ui.navigate.to("/callbacks")
            else:
                # Stay on page so supervisor can fix inputs
                pass

        ui.button("Record event", on_click=record).classes("btn-primary q-mt-sm").props("no-caps unelevated")

    with ui.element("div").classes("grid-2"):
        with panel(f"Call-down order · {len(rot)}"):
            if not rot:
                ui.html(
                    '<div class="alert alert-warn">Empty rotation. Click Sync from roster.</div>',
                    sanitize=False,
                )
            for i, row in enumerate(rot[:40]):
                mark = (
                    "→ NEXT"
                    if cand and row.get("officer_id") == cand.get("officer_id")
                    else f"#{row.get('sort_order')}"
                )
                last = format_date(row.get("last_callback") or "") or "—"
                ui.label(
                    f"{mark} · {row.get('officer_name')} · "
                    f"Squad {row.get('squad')} · rank {row.get('seniority_rank')} · last {last}"
                ).classes("text-sm q-mb-xs mono" if i == 0 and cand else "text-sm q-mb-xs")

        with panel("Recent callback ledger"):
            led = get_callback_ledger(limit=25) or {}
            rows = led.get("events") or led.get("rows") or led.get("ledger") or []
            if isinstance(led, list):
                rows = led
            if not rows:
                ui.html('<div class="alert alert-ok">No callback events yet.</div>', sanitize=False)
            for e in rows[:25]:
                if not isinstance(e, dict):
                    continue
                ui.label(
                    f"{format_date(e.get('event_date') or e.get('date') or '')} · "
                    f"{e.get('officer_name') or e.get('officer_id')} · "
                    f"{e.get('hours', '—')}h · {e.get('notes') or ''}"
                ).classes("text-sm q-mb-xs")
