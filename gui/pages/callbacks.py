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
from validators import format_date, parse_date


def render_callbacks() -> None:
    def body() -> None:
        page_header(
            "Callback rotation",
            "OT call-down order · next candidate · record offers (equity log)",
            kicker="Ops · LE fairness",
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

        with ui.row().classes("gap-2 q-mb-md"):
            ui.button("Refresh", on_click=refresh).classes("btn-ghost").props("no-caps outline dense")

            def sync():
                uid = (session.current_user() or {}).get("id")
                r = sync_callback_rotation_from_roster(user_id=uid)
                ui.notify(
                    r.get("message", "Synced") if r.get("success") else r.get("message", "Fail"),
                    type="positive" if r.get("success") else "negative",
                )
                refresh()

            ui.button("Sync from roster", on_click=sync).classes("btn-primary").props("no-caps unelevated dense")

        refresh()

    layout("callbacks", body)


def _content() -> None:
    nxt = get_next_callback_candidate() or {}
    cand = nxt.get("candidate") if nxt.get("success") else None
    with panel("Next callback candidate", glow=True):
        if cand:
            ui.label(
                f"{cand.get('officer_name')} · Squad {cand.get('squad')} · order #{cand.get('sort_order')}"
            ).classes("text-sm font-semibold")
            ui.label(f"Last callback: {cand.get('last_callback') or 'none on file'}").classes("text-xs text-gray-500")
        else:
            ui.html(
                f'<div class="alert alert-warn">{nxt.get("message") or "No candidate — sync roster."}</div>',
                sanitize=False,
            )

    with panel("Record callback / OT offer"):
        rot = get_callback_rotation(active_only=True) or []
        officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
        names = [o["name"] for o in officers]
        omap = {o["name"]: o["id"] for o in officers}
        if cand and cand.get("officer_name") in omap:
            default = cand["officer_name"]
        else:
            default = names[0] if names else None
        pick = ui.select(names, value=default, label="Officer").classes("w-full")
        d_in = ui.input(label="Event date", value=today_local().isoformat()).classes("w-full")
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
            ui.navigate.to("/callbacks")

        ui.button("Record event", on_click=record).classes("btn-primary q-mt-sm").props("no-caps unelevated")

    with ui.element("div").classes("grid-2"):
        with panel(f"Rotation order · {len(rot)}"):
            if not rot:
                ui.html(
                    '<div class="alert alert-warn">Empty rotation. Click Sync from roster.</div>',
                    sanitize=False,
                )
            for row in rot[:40]:
                ui.label(
                    f"#{row.get('sort_order')} · {row.get('officer_name')} · "
                    f"Squad {row.get('squad')} · rank {row.get('seniority_rank')}"
                ).classes("text-sm q-mb-xs")

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
