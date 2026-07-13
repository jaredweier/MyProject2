"""Availability / blackout + holidays — LE self-service + admin calendar."""

from __future__ import annotations

from datetime import timedelta

from nicegui import ui

from gui import session
from gui.clock import today_local
from gui.shell import layout, page_header, panel
from logic import (
    add_holiday,
    add_officer_availability,
    delete_holiday,
    get_holidays,
    get_officers_by_seniority,
    get_schedule_conflicts,
    get_upcoming_holidays,
    is_officer_unavailable_on_date,
)
from validators import format_date, parse_date


def render_availability() -> None:
    def body() -> None:
        page_header(
            "Availability & blackouts",
            "Officer unavailability · department holidays",
            kicker="Self-service",
        )
        with ui.element("div").classes("grid-2"):
            with panel("Mark unavailable (blackout day)", glow=True):
                oid = session.linked_officer_id()
                omap = {}
                off_sel = None
                if session.can("availability.manage_all") or session.can("officers.manage"):
                    officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
                    names = [o["name"] for o in officers]
                    omap = {o["name"]: o["id"] for o in officers}
                    off_sel = ui.select(names, value=names[0] if names else None, label="Officer").classes("w-full")
                elif not oid:
                    ui.html(
                        '<div class="alert alert-warn">Link an officer profile to set your blackout dates.</div>',
                        sanitize=False,
                    )
                d_in = ui.input(
                    label="Date",
                    value=format_date(today_local()),
                    placeholder="M/D/YY or M-D-YYYY",
                ).classes("w-full")
                reason = ui.input(label="Reason", value="Unavailable").classes("w-full")

                def save_av():
                    nonlocal oid
                    if off_sel is not None and off_sel.value:
                        oid = omap.get(off_sel.value)
                    if not oid:
                        ui.notify("No officer selected", type="negative")
                        return
                    if session.is_officer() and oid != session.linked_officer_id():
                        if not session.can("availability.manage_all"):
                            ui.notify("Officers may only set their own availability", type="warning")
                            return
                    dt = parse_date((d_in.value or "").strip())
                    if not dt:
                        ui.notify("Invalid date", type="negative")
                        return
                    uid = (session.current_user() or {}).get("id")
                    r = add_officer_availability(oid, dt.isoformat(), reason=(reason.value or "").strip(), user_id=uid)
                    ui.notify(
                        r.get("message", "Saved") if r.get("success") else r.get("message", "Failed"),
                        type="positive" if r.get("success") else "negative",
                    )

                can = (
                    session.can("availability.manage_own")
                    or session.can("availability.manage_all")
                    or session.is_officer()
                )
                if can:
                    ui.button("Save blackout", on_click=save_av).classes("btn-primary q-mt-sm").props(
                        "no-caps unelevated"
                    )

                ui.separator()
                ui.label("Check unavailability").classes("text-xs text-gray-500")
                chk_date = ui.input(
                    label="Date to check",
                    value=format_date(today_local()),
                    placeholder="M/D/YY or M-D-YYYY",
                ).classes("w-full")
                chk_lbl = ui.label("").classes("text-sm q-mt-xs")

                def check_unavail():
                    nonlocal oid
                    if off_sel is not None and off_sel.value:
                        oid = omap.get(off_sel.value)
                    check_oid = oid or session.linked_officer_id()
                    if not check_oid:
                        chk_lbl.set_text("No officer")
                        return
                    try:
                        dt = parse_date((chk_date.value or "").strip())
                    except Exception:
                        dt = None
                    if not dt:
                        chk_lbl.set_text("Invalid date")
                        return
                    busy = is_officer_unavailable_on_date(check_oid, dt)
                    chk_lbl.set_text(f"{'Unavailable / blackout' if busy else 'Available'} on {format_date(dt)}")

                ui.button("Check date", on_click=check_unavail).classes("btn-ghost q-mt-sm").props(
                    "no-caps outline dense"
                )

            with panel("Upcoming holidays (60 days)"):
                try:
                    hols = get_upcoming_holidays(60) or []
                except Exception as exc:
                    hols = []
                    ui.label(str(exc)).classes("text-sm text-red-400")
                if not hols:
                    ui.html(
                        '<div class="alert alert-ok">No holidays in the next 60 days.</div>',
                        sanitize=False,
                    )
                for h in hols[:40]:
                    if isinstance(h, dict):
                        with ui.row().classes("items-center gap-2 q-mb-xs"):
                            ui.label(
                                f"{format_date(h.get('date') or h.get('holiday_date') or '')} · "
                                f"{h.get('name') or h.get('holiday_name') or 'Holiday'}"
                            ).classes("text-sm grow")
                            hid = h.get("id") or h.get("holiday_id")
                            if hid is not None and (session.can("holidays.manage") or session.can("admin.settings")):

                                def del_h(holiday_id=hid):
                                    uid = (session.current_user() or {}).get("id")
                                    r = delete_holiday(int(holiday_id), user_id=uid)
                                    ui.notify(
                                        r.get("message", "Deleted") if r.get("success") else r.get("message", "Failed"),
                                        type="positive" if r.get("success") else "negative",
                                    )
                                    if r.get("success"):
                                        ui.navigate.to("/availability")

                                ui.button("Delete", on_click=del_h).props("dense no-caps flat")
                    else:
                        ui.label(str(h)).classes("text-sm")

                if session.can("holidays.manage") or session.can("admin.settings"):
                    ui.separator()
                    ui.label("Add holiday").classes("text-xs text-gray-500")
                    hd = ui.input(label="Date", value="", placeholder="M/D/YY or M-D-YYYY").classes("w-full")
                    hn = ui.input(label="Name", value="Department Holiday").classes("w-full")

                    def add_h():
                        dt = parse_date((hd.value or "").strip())
                        if not dt:
                            ui.notify("Invalid date", type="negative")
                            return
                        uid = (session.current_user() or {}).get("id")
                        r = add_holiday(
                            name=(hn.value or "Holiday").strip(),
                            holiday_date=dt.isoformat(),
                            user_id=uid,
                        )
                        ok = r.get("success") if isinstance(r, dict) else bool(r)
                        ui.notify(
                            "Holiday added" if ok else (r.get("message") if isinstance(r, dict) else "Failed"),
                            type="positive" if ok else "negative",
                        )
                        if ok:
                            ui.navigate.to("/availability")

                    ui.button("Add holiday", on_click=add_h).classes("btn-ghost q-mt-sm").props("no-caps outline dense")

                    # Year catalog for delete when upcoming list is empty
                    with ui.expansion("All holidays this year", icon="event").classes("w-full q-mt-sm"):
                        try:
                            year_hols = get_holidays(today_local().year) or []
                        except Exception:
                            year_hols = []
                        for h in year_hols[:50]:
                            if not isinstance(h, dict):
                                continue
                            hid = h.get("id") or h.get("holiday_id")
                            with ui.row().classes("items-center gap-2"):
                                ui.label(
                                    f"{format_date(h.get('date') or h.get('holiday_date') or '')} · "
                                    f"{h.get('name') or h.get('holiday_name') or 'Holiday'}"
                                ).classes("text-sm grow")
                                if hid is not None:

                                    def del_y(holiday_id=hid):
                                        uid = (session.current_user() or {}).get("id")
                                        r = delete_holiday(int(holiday_id), user_id=uid)
                                        ui.notify(
                                            r.get("message", "Deleted")
                                            if r.get("success")
                                            else r.get("message", "Failed"),
                                            type="positive" if r.get("success") else "negative",
                                        )
                                        if r.get("success"):
                                            ui.navigate.to("/availability")

                                    ui.button("Del", on_click=del_y).props("dense no-caps flat")

        with panel("Schedule conflicts (next 14 days)", glow=False):
            start = today_local()
            end = start + timedelta(days=14)
            oid = session.linked_officer_id() if session.is_officer() else None
            try:
                conf = get_schedule_conflicts(start, end, officer_id=oid) or {}
            except Exception as exc:
                conf = {"conflicts": [], "message": str(exc)}
            rows = conf.get("conflicts") or []
            ui.label(f"{conf.get('conflict_count', len(rows))} conflict(s)").classes("text-xs text-gray-500 q-mb-sm")
            if not rows:
                ui.html(
                    '<div class="alert alert-ok">No availability/schedule conflicts in window.</div>',
                    sanitize=False,
                )
            for c in rows[:30]:
                if isinstance(c, dict):
                    ui.label(
                        f"{format_date(c.get('date') or c.get('day') or '')} · "
                        f"{c.get('officer_name') or c.get('officer_id') or ''} · "
                        f"{c.get('message') or c.get('reason') or c.get('type') or c}"
                    ).classes("text-sm q-mb-xs")
                else:
                    ui.label(str(c)).classes("text-sm")

    layout("availability", body)
