"""Court / training calendar board."""

from __future__ import annotations

from datetime import timedelta

from nicegui import ui

from gui import session
from gui.clock import today_local
from gui.shell import layout, page_header, panel
from logic.court_calendar import (
    court_calendar_summary,
    create_court_or_training,
)
from logic.officers import get_officers_by_seniority
from validators import format_date, parse_date


def render_court() -> None:
    def body() -> None:
        page_header(
            "Court & Training",
            "Subpoena / court board · multi-day ranges · min hours note · leave pipeline",
            kicker="Chronos Command · Scheduling",
        )
        host = ui.element("div")

        def refresh():
            host.clear()
            with host:
                _content()

        with ui.row().classes("gap-2 q-mb-md flex-wrap"):
            ui.button("Refresh", on_click=refresh).classes("btn-ghost").props("no-caps outline dense")
        refresh()

    layout("court", body)


def _content() -> None:
    today = today_local()
    start = today - timedelta(days=7)
    end = today + timedelta(days=45)
    summary = court_calendar_summary(start=start.isoformat(), end=end.isoformat())
    events = summary.get("events") or []
    by_type = summary.get("by_type") or {}
    by_status = summary.get("by_status") or {}

    with panel("Window summary", glow=True):
        ui.label(f"{format_date(start)} → {format_date(end)} · {summary.get('count', 0)} event(s)").classes(
            "text-sm font-semibold"
        )
        ui.label(" · ".join(f"{k}: {v}" for k, v in sorted(by_type.items())) or "No court/training yet").classes(
            "text-xs text-gray-500"
        )
        if by_status:
            ui.label("Status: " + " · ".join(f"{k}={v}" for k, v in sorted(by_status.items()))).classes(
                "text-xs text-gray-500"
            )

    can_manage = session.can("schedule.updated.edit") or session.can("officers.manage") or not session.is_officer()
    if can_manage:
        with panel("Add court or training"):
            officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
            names = [o["name"] for o in officers]
            omap = {o["name"]: o["id"] for o in officers}
            pick = ui.select(names, value=names[0] if names else None, label="Officer").classes("w-full")
            rtype = ui.select(["Court", "Training"], value="Court", label="Type").classes("w-full")
            d_in = ui.input(
                label="Start date (M/D/YY)",
                value=format_date(today),
            ).classes("w-full")
            d_end = ui.input(
                label="End date (optional multi-day)",
                value="",
                placeholder="Leave blank for single day",
            ).classes("w-full")
            min_hrs = ui.input(label="Court min hours (CBA note)", value="3").classes("w-full")
            times = ui.input(label="Time window", value="08:00-12:00").classes("w-full")
            notes = ui.input(label="Notes / case #", value="").classes("w-full")
            notify_off = ui.switch("Notify officer (email/SMS if enabled)", value=True)

            def add():
                oid = omap.get(pick.value)
                dt = parse_date((d_in.value or "").strip())
                if not oid or not dt:
                    ui.notify("Officer and valid date required", type="negative")
                    return
                end_dt = parse_date((d_end.value or "").strip()) if (d_end.value or "").strip() else dt
                if end_dt and end_dt < dt:
                    ui.notify("End date before start", type="negative")
                    return
                uid = (session.current_user() or {}).get("id")
                day = dt
                created = 0
                last_r = {}
                while day <= (end_dt or dt):
                    note_bits = [
                        (notes.value or "").strip(),
                        f"window={times.value or ''}",
                        f"min_hours={min_hrs.value or '3'}",
                    ]
                    last_r = create_court_or_training(
                        int(oid),
                        day.isoformat(),
                        str(rtype.value or "Court"),
                        notes=" · ".join(b for b in note_bits if b),
                        user_id=uid,
                    )
                    if last_r.get("success"):
                        created += 1
                    day = day + timedelta(days=1)
                if created and notify_off.value:
                    try:
                        from logic import dispatch_template

                        dispatch_template(
                            "court_reminder",
                            officer_ids=[int(oid)],
                            user_id=uid,
                            date=format_date(dt),
                            start=(times.value or "").split("-")[0].strip() if times.value else "",
                            end=(times.value or "").split("-")[-1].strip() if times.value else "",
                            notes=(notes.value or "").strip(),
                        )
                    except Exception:
                        pass
                ui.notify(
                    f"Created {created} day(s)" if created else last_r.get("message", "Failed"),
                    type="positive" if created else "negative",
                )
                if created:
                    ui.navigate.to("/court")

            ui.button("Add to board", on_click=add).classes("btn-primary q-mt-sm").props("no-caps unelevated")

    with panel(f"Board · {len(events)}"):
        if not events:
            ui.html(
                '<div class="alert alert-ok">No court or training in this window.</div>',
                sanitize=False,
            )
            return
        for e in events:
            ui.label(
                f"{e.get('date_display') or e.get('request_date')} · "
                f"{e.get('request_type')} · {e.get('officer_name')} · "
                f"Squad {e.get('squad')} · {e.get('status')} · "
                f"{(e.get('notes') or '')[:60]}"
            ).classes("text-sm q-mb-xs")
