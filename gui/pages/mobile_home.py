"""Officer mobile-first My Week — large taps, self-service first."""

from __future__ import annotations

from datetime import timedelta

from nicegui import ui

from gui import session
from gui.clock import format_local_date, today_local
from gui.shell import layout, page_header, panel
from gui.ui_patterns import empty_state, status_chip
from logic.product_complete_pack import flsa_meter_for_officer, giveaway_shift_as_open
from validators import format_date


def render_mobile_home() -> None:
    def body() -> None:
        oid = session.linked_officer_id()
        page_header(
            "My Week",
            "Schedule · open shifts · leave · banks — phone-friendly",
            kicker="Chronos Command",
        )
        ui.html(
            '<div class="offline-banner alert alert-ok" style="margin-bottom:8px">'
            "PWA: multi-page shell caches when online. Full multi-page API offline is not claimed — "
            "open critical pages once while online."
            "</div>",
            sanitize=False,
        )

        # Quick actions — 3 taps max paths
        with ui.element("div").classes("mobile-action-grid q-mb-md"):
            for label, path, hint in (
                ("My schedule", "/my-schedule", "This week"),
                ("Open shifts", "/open-shifts", "Claim OT"),
                ("Time off", "/time-off", "Request leave"),
                ("Time banks", "/banks", "Comp · sick"),
                ("Timecard", "/timecards", "Hours"),
                ("Shift bids", "/bidding", "Rank prefs"),
                ("Alerts", "/notifications", "Inbox"),
                ("Availability", "/availability", "Blackouts"),
            ):
                with ui.element("div").classes("mobile-action-tile").on("click", lambda _e, p=path: ui.navigate.to(p)):
                    ui.label(label).classes("text-sm font-semibold")
                    ui.label(hint).classes("text-xs").style("color: var(--dim)")

        today = today_local()
        if not oid:
            ui.html(
                '<div class="alert alert-warn">Link your user to an officer profile for personal schedule.</div>',
                sanitize=False,
            )
            return

        # 7-day card strip (Deputy-style status-first)
        with panel("Next 7 days", glow=True):
            try:
                from logic.snapshots import get_officer_schedule_window

                window = get_officer_schedule_window(int(oid), start_date=today, days=7) or {}
            except Exception as exc:
                window = {"error": str(exc)}

            days = (
                window.get("schedule_days") or window.get("days") or window.get("schedule") or window.get("rows") or []
            )
            if window.get("error"):
                ui.label(str(window["error"])).classes("text-sm text-red-400")
            elif isinstance(days, list) and days:
                for d in days[:7]:
                    if not isinstance(d, dict):
                        ui.label(str(d)[:80]).classes("text-sm")
                        continue
                    raw = d.get("date") or d.get("work_date") or ""
                    try:
                        dlabel = format_date(raw) if raw else str(raw)
                    except Exception:
                        dlabel = str(raw)
                    status = d.get("status") or d.get("duty") or d.get("label") or "—"
                    start = d.get("shift_start") or d.get("start") or ""
                    end = d.get("shift_end") or d.get("end") or ""
                    times = f"{start}–{end}" if start else ""
                    is_today = str(raw)[:10] == today.isoformat()
                    lvl = "ok" if str(status).lower() in ("working", "on", "duty") else "info"
                    if str(status).lower() in ("leave", "off"):
                        lvl = "warn"
                    cls = "mobile-day-card today" if is_today else "mobile-day-card"
                    with ui.element("div").classes(cls):
                        with ui.element("div"):
                            ui.label(f"{dlabel} · {status}").classes("text-sm font-semibold")
                            if times:
                                ui.label(times).classes("text-xs mono").style("color: var(--dim)")
                        with ui.row().classes("gap-1 items-center"):
                            if is_today:
                                status_chip("Today", level="info")
                            status_chip(str(status)[:12], level=lvl)
            elif isinstance(days, dict):
                for i in range(7):
                    d = today + timedelta(days=i)
                    key = d.isoformat()
                    val = days.get(key) or days.get(format_date(d)) or "—"
                    cls = "mobile-day-card today" if i == 0 else "mobile-day-card"
                    with ui.element("div").classes(cls):
                        ui.label(f"{format_local_date(d)} · {val}").classes("text-sm font-semibold")
            else:
                empty_state(
                    "No week rows yet",
                    "Open My schedule for the full duty window.",
                    cta_label="My schedule",
                    cta_path="/my-schedule",
                )
                for i in range(7):
                    d = today + timedelta(days=i)
                    with ui.element("div").classes("mobile-day-card" + (" today" if i == 0 else "")):
                        ui.label(format_local_date(d)).classes("text-sm")

        # FLSA meter
        with panel("FLSA hours meter", glow=True):
            meter = flsa_meter_for_officer(int(oid), reference=today)
            ui.label(meter.get("message") or "—").classes("text-sm font-semibold")
            for b in (meter.get("banners") or [])[:3]:
                ui.label(b.get("message") or str(b)).classes("text-xs").style("color: var(--dim)")

        # Giveaway today's shift
        with panel("Give away a shift"):
            gdate = ui.input(label="Date (M/D/YY)", value=format_date(today)).classes("w-full")
            gnotes = ui.input(label="Note", value="Giveaway").classes("w-full")

            def do_give():
                uid = (session.current_user() or {}).get("id")
                r = giveaway_shift_as_open(
                    int(oid),
                    gdate.value or today,
                    notes=(gnotes.value or "Giveaway").strip(),
                    user_id=uid,
                )
                ui.notify(
                    r.get("message", "Posted") if r.get("success") else r.get("message", "Failed"),
                    type="positive" if r.get("success") else "negative",
                )

            ui.button("Post as open shift", on_click=do_give).classes("btn-ghost").props("no-caps outline dense")

        # Comp / bank peek + jump to full banks page
        with panel("Time banks", glow=True):
            try:
                from logic import get_officer_time_banks

                banks = get_officer_time_banks(int(oid)) or {}
                if isinstance(banks, dict) and banks.get("success") is False:
                    ui.label(banks.get("message") or "Banks unavailable").classes("text-xs")
                else:
                    rows = banks.get("banks") or banks.get("rows") or banks
                    if isinstance(rows, dict):
                        for k, v in list(rows.items())[:8]:
                            if k in ("success", "message"):
                                continue
                            ui.label(f"{k}: {v}").classes("text-sm")
                    elif isinstance(rows, list):
                        for r in rows[:8]:
                            ui.label(str(r)[:100]).classes("text-sm")
                    else:
                        ui.label("No bank rows").classes("text-xs").style("color: var(--dim)")
            except Exception:
                ui.label("Banks module not available on this account.").classes("text-xs").style("color: var(--dim)")
            ui.button("Open time banks", on_click=lambda: ui.navigate.to("/banks")).classes(
                "btn-primary q-mt-sm"
            ).props("no-caps unelevated dense")

        # Easy punch — always available; policy on Time Punch page
        with panel("Clock in / out", glow=True):
            try:
                from logic.geofence_clock import clock_status
                from logic.time_punch import get_punch_policy, officer_clock

                pol = get_punch_policy()
                st = clock_status(int(oid))
                status_lbl = ui.label("Clocked IN" if st.get("clocked_in") else "Clocked OUT").classes(
                    "text-sm font-semibold"
                )
                ui.label(
                    "Required by department" if pol.get("punch_required") else "Optional (free time entry allowed)"
                ).classes("text-xs q-mb-sm").style("color: var(--dim)")

                def do_punch(ptype: str):
                    uid = (session.current_user() or {}).get("id")
                    r = officer_clock(int(oid), ptype, user_id=uid, notes="my-week")
                    ui.notify(
                        r.get("message", "Punch") if r.get("success") else r.get("message", "Blocked"),
                        type="positive" if r.get("success") else "negative",
                    )
                    if r.get("success"):
                        st2 = clock_status(int(oid))
                        status_lbl.set_text("Clocked IN" if st2.get("clocked_in") else "Clocked OUT")

                with ui.row().classes("gap-2 q-mt-sm flex-wrap"):
                    ui.button("CLOCK IN", on_click=lambda: do_punch("in")).classes("btn-primary").props(
                        "no-caps unelevated"
                    )
                    ui.button("CLOCK OUT", on_click=lambda: do_punch("out")).classes("btn-ghost").props(
                        "no-caps outline"
                    )
                ui.button(
                    "Fix a punch / corrections",
                    on_click=lambda: ui.navigate.to("/time-punch"),
                ).classes("btn-ghost q-mt-sm").props("no-caps flat dense")
            except Exception as exc:
                ui.label(f"Clock unavailable: {exc}").classes("text-xs text-red-400")

        with ui.row().classes("gap-2 flex-wrap q-mt-md"):
            ui.button("Time punch", on_click=lambda: ui.navigate.to("/time-punch")).classes("btn-primary").props(
                "no-caps unelevated"
            )
            ui.button("Full schedule", on_click=lambda: ui.navigate.to("/my-schedule")).classes("btn-ghost").props(
                "no-caps outline"
            )
            ui.button("Claim open shift", on_click=lambda: ui.navigate.to("/open-shifts")).classes("btn-ghost").props(
                "no-caps outline"
            )

    layout("my_week", body)
