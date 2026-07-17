"""Duty board — one hero decision surface + severity + deck (DESIGN B+D)."""

from __future__ import annotations

from nicegui import ui

from gui import session
from gui.clock import format_clock, format_local_date, today_local
from gui.shell import layout, page_header, panel
from gui.ui_patterns import empty_state, first_run_guide, shift_card
from logic import (
    get_coverage_gap_board,
    get_cycle_day,
    get_dashboard_kpis_fast,
    get_hours_watch,
    get_officer_schedule_window,
    get_open_shifts,
    get_shift_coverage_counts_for_range,
    get_squad_on_duty,
    get_unread_notification_count,
)
from logic.staffing_config import get_active_shift_times
from ui.helpers import active_officers
from validators import format_date


def render_dashboard() -> None:
    def body() -> None:
        today = today_local()
        name = session.display_name()
        cycle = get_cycle_day(today)
        squad = get_squad_on_duty(cycle)
        oid = session.linked_officer_id() if session.is_officer() else None
        insights = get_dashboard_kpis_fast(officer_id=oid) or {}
        if not isinstance(insights, dict):
            insights = {}

        n_off = len(active_officers())
        pending = insights.get("pending_requests", 0)
        swaps = insights.get("pending_swaps", 0)
        gaps = insights.get("coverage_gap_count", 0)
        issues = insights.get("coverage_issues", 0)

        try:
            n_open = len(get_open_shifts(status="open", limit=50) or [])
        except Exception:
            n_open = 0
        try:
            hw = get_hours_watch(officer_id=oid) or {}
            n_fat = int(hw.get("warning_count") or 0) + int(hw.get("critical_count") or 0)
        except Exception:
            n_fat = 0
        try:
            unread = get_unread_notification_count(officer_id=oid) or 0
        except Exception:
            unread = 0

        page_header(
            name,
            f"District duty ops · {format_local_date(today)} · {format_clock()} · "
            f"Cycle day {cycle} · Squad {squad} on duty · {n_off} officers active",
            kicker="Chronos Command · ops floor",
        )

        first_run_guide()

        # Pay period lock reminder (supervisor)
        if not session.is_officer():
            try:
                from logic import get_pay_period_lock_reminder

                rem = get_pay_period_lock_reminder() or {}
                if rem.get("remind") or rem.get("due_soon"):
                    ui.html(
                        f'<div class="alert alert-warn q-mb-sm">{rem.get("message") or "Pay period lock due soon."} '
                        f'<a href="/timecards" style="color:#6BA3F5">Open timecards</a></div>',
                        sanitize=False,
                    )
            except Exception:
                pass

        # —— ONE hero decision band (merged Command Post + staffing question) ——
        staffed = not gaps and not issues
        hero_metric = "STAFFED" if staffed else f"GAPS · {gaps}"
        primary_path = "/operations" if gaps or issues else ("/time-off" if pending else "/open-shifts")
        primary_label = (
            "Resolve gaps"
            if gaps or issues
            else ("Review leave" if pending else ("Claim / post vacancies" if n_open else "Ops desk"))
        )
        if session.is_officer():
            primary_path = "/my-week"
            primary_label = "My week"

        with ui.element("div").classes("panel panel-glow w-full hero-decision"):
            with ui.row().classes("w-full justify-between items-start"):
                with ui.element("div"):
                    ui.html('<div class="page-kicker">Next 24h staffing</div>', sanitize=False)
                    ui.html(f'<div class="kpi-v">{hero_metric}</div>', sanitize=False)

                # Dynamic Quasar telemetry status chips
                with ui.row().classes("gap-2 items-center flex-wrap"):
                    from gui.ui_patterns import ng_chip

                    ng_chip(f"Gaps: {gaps}", level="crit" if gaps else "ok", icon="warning" if gaps else "check_circle")
                    ng_chip(
                        f"Night Issues: {issues}",
                        level="crit" if issues else "ok",
                        icon="nights_stay" if issues else "bedtime",
                    )
                    ng_chip(f"Open: {n_open}", level="warn" if n_open else "ok", icon="add" if n_open else "check")
                    ng_chip(
                        f"Leave Queue: {pending}",
                        level="warn" if pending else "ok",
                        icon="pending_actions" if pending else "thumb_up",
                    )
                    if swaps:
                        ng_chip(f"Swaps: {swaps}", level="warn", icon="swap_horiz")
                    if n_fat:
                        ng_chip(f"Fatigue: {n_fat}", level="warn", icon="battery_alert")
                    if unread:
                        ng_chip(f"Alerts: {unread}", level="warn", icon="notifications_active")

            # Compact roster count inline (was separate panel)
            if not session.is_officer():
                try:
                    coverage = get_shift_coverage_counts_for_range(today, today)
                except Exception:
                    coverage = {}
                bands = list(get_active_shift_times().values()) if get_active_shift_times() else []
                parts = []
                total_on = 0
                for start, _end in bands:
                    c = int(coverage.get((today.isoformat(), squad, start), 0) or 0)
                    total_on += c
                    parts.append(f"{start}→{c}")

                with ui.row().classes("w-full gap-3 q-mt-md items-center text-xs text-slate-400 font-medium"):
                    ui.label(f"Squad {squad} today").classes("font-semibold text-slate-200")
                    ui.label(f"|  {total_on} assigned").classes("mono")
                    for p in parts[:6]:
                        ui.label(f"·  {p}").classes("mono")

                try:
                    from logic.staffing_insights import staffing_risk_snapshot

                    snap = staffing_risk_snapshot() or {}
                    lvl = snap.get("level") or "ok"
                    line0 = (snap.get("lines") or ["Risk nominal"])[0]
                    with ui.row().classes("w-full items-center q-mt-xs text-xs"):
                        ui.label("Staffing Risk:").classes("text-slate-400")
                        status_lvl = "crit" if lvl == "crit" else ("warn" if lvl == "warn" else "ok")
                        from gui.ui_patterns import status_chip

                        status_chip(lvl.upper(), level=status_lvl)
                        ui.label(f"· {line0}").classes("text-slate-300 font-medium")
                except Exception:
                    pass

            with ui.row().classes("gap-2 q-mt-md flex-wrap"):
                ui.button(primary_label, on_click=lambda: ui.navigate.to(primary_path)).classes("btn-primary").props(
                    "no-caps unelevated dense"
                )
                if not session.is_officer():
                    ui.button(
                        "Call-down board",
                        on_click=lambda: ui.navigate.to("/callbacks"),
                    ).classes("btn-ghost").props("no-caps outline dense")
                    ui.button(
                        "Open shifts",
                        on_click=lambda: ui.navigate.to("/open-shifts"),
                    ).classes("btn-ghost").props("no-caps outline dense")
                    ui.button(
                        "Ops desk",
                        on_click=lambda: ui.navigate.to("/ops-desk"),
                    ).classes("btn-ghost").props("no-caps outline dense")
                else:
                    ui.button(
                        "Open shifts",
                        on_click=lambda: ui.navigate.to("/open-shifts"),
                    ).classes("btn-ghost").props("no-caps outline dense")
                    ui.button(
                        "Time off",
                        on_click=lambda: ui.navigate.to("/time-off"),
                    ).classes("btn-ghost").props("no-caps outline dense")

        # Severity strip — click → filtered destinations
        try:
            from gui.tables import severity_strip

            severity_strip(
                [
                    {
                        "label": "Leave queue",
                        "count": pending,
                        "level": "warn" if pending else "ok",
                        "path": "/time-off",
                    },
                    {
                        "label": "Coverage gaps",
                        "count": gaps,
                        "level": "crit" if gaps else "ok",
                        "path": "/operations",
                    },
                    {
                        "label": "Night issues",
                        "count": issues,
                        "level": "crit" if issues else "ok",
                        "path": "/operations",
                    },
                    {
                        "label": "Open vacancies",
                        "count": n_open,
                        "level": "warn" if n_open else "ok",
                        "path": "/open-shifts",
                    },
                    {
                        "label": "Fatigue / hours",
                        "count": n_fat,
                        "level": "warn" if n_fat else "ok",
                        "path": "/payroll",
                    },
                    {
                        "label": "Swaps",
                        "count": swaps,
                        "level": "warn" if swaps else "ok",
                        "path": "/time-off",
                    },
                    {
                        "label": "Alerts",
                        "count": unread,
                        "level": "warn" if unread else "ok",
                        "path": "/notifications",
                    },
                ],
                title="Ops severity",
            )
        except Exception:
            pass

        # Deck: on-duty + watch / personal week (no competing command strips)
        with ui.element("div").classes("grid-2"):
            with panel("On-duty shifts", glow=True):
                if session.is_officer():
                    empty_state(
                        "Personal duty window",
                        "Open My schedule for your full cycle board.",
                        cta_label="My schedule",
                        cta_path="/my-schedule",
                    )
                else:
                    try:
                        coverage = get_shift_coverage_counts_for_range(today, today)
                    except Exception:
                        coverage = {}
                    day_str = today.isoformat()
                    ui.html(
                        f'<div style="font-family:var(--mono);font-size:11px;color:var(--dim);margin-bottom:10px">'
                        f"Squad {squad} · {format_clock()}</div>",
                        sanitize=False,
                    )
                    bands = list(get_active_shift_times().values()) if get_active_shift_times() else []
                    if not bands:
                        empty_state(
                            "No shift bands configured",
                            "Set staffing bands in deploy / settings.",
                            cta_label="Deploy",
                            cta_path="/deploy",
                        )
                    for start, end in bands:
                        count = coverage.get((day_str, squad, start), 0)
                        lvl = "ok" if count else "warn"
                        with ui.element("div").classes("shift-row"):
                            with ui.row().classes("items-center gap-3"):
                                ui.html(
                                    f'<span class="{"shift-dot" if count else "shift-dot warn"}"></span>',
                                    sanitize=False,
                                )
                                with ui.element("div"):
                                    ui.label(f"{start} – {end}").classes("text-sm font-semibold mono")
                                    ui.label("Patrol band").classes("text-xs").style("color: var(--dim)")
                            status_chip(f"{count} on", level=lvl)

            with panel("Watch status"):
                if issues:
                    ui.html(
                        f'<div class="alert alert-crit">Night minimum · {issues} issue(s) this cycle</div>',
                        sanitize=False,
                    )
                if gaps:
                    ui.html(
                        f'<div class="alert alert-warn">Coverage gaps in next 48h: {gaps}</div>',
                        sanitize=False,
                    )
                if not issues and not gaps:
                    ui.html(
                        '<div class="alert alert-ok">'
                        "<strong>All clear</strong> · No critical coverage flags on this watch."
                        "</div>",
                        sanitize=False,
                    )
                ui.html(
                    f'<div style="margin-top:12px;font-family:var(--mono);font-size:11px;color:var(--dim)">'
                    f"Unread alerts · <strong style='color:var(--text)'>{unread}</strong></div>",
                    sanitize=False,
                )
                ui.button("Open alerts", on_click=lambda: ui.navigate.to("/notifications")).classes(
                    "btn-ghost q-mt-sm"
                ).props("no-caps outline dense")

        with ui.element("div").classes("grid-2"):
            if session.is_officer() and oid:
                with panel("My week", glow=True):
                    try:
                        week = get_officer_schedule_window(oid, days=7) or {}
                    except Exception as exc:
                        week = {"success": False, "message": str(exc)}
                    days = week.get("days") or week.get("schedule") or week.get("rows") or []
                    if not days and week.get("message"):
                        ui.label(str(week.get("message"))).classes("text-sm text-gray-400")
                    elif not days:
                        empty_state(
                            "No week rows",
                            "Open My schedule for the full window.",
                            cta_label="My schedule",
                            cta_path="/my-schedule",
                        )
                    else:
                        for day in days[:7]:
                            if not isinstance(day, dict):
                                continue
                            raw = day.get("date") or day.get("day") or ""
                            status = day.get("status") or day.get("duty") or day.get("label") or "—"
                            shift = day.get("shift_start") or day.get("shift") or ""
                            is_today = str(raw)[:10] == today.isoformat()
                            cls = "mobile-day-card today" if is_today else "mobile-day-card"
                            with ui.element("div").classes(cls):
                                ui.label(
                                    f"{format_date(raw) if raw else '—'} · {status}" + (f" · {shift}" if shift else "")
                                ).classes("text-sm font-semibold")
                                if is_today:
                                    status_chip("Today", level="info")
            else:
                with panel("Coverage gap board (48h)", glow=True):
                    try:
                        board = get_coverage_gap_board(48) or {}
                    except Exception as exc:
                        board = {"success": False, "message": str(exc), "gaps": []}
                    gap_rows = board.get("gaps") or []
                    ui.label(
                        f"Gaps {board.get('gap_count', len(gap_rows))} · "
                        f"Critical {board.get('critical_count', 0)} · "
                        f"Warn {board.get('warning_count', 0)}"
                    ).classes("text-xs text-gray-500 q-mb-sm")
                    if not gap_rows:
                        empty_state(
                            "No coverage gaps",
                            "Next 48 hours look staffed.",
                            cta_label="Ops reports",
                            cta_path="/operations",
                        )
                    else:
                        for g in gap_rows[:12]:
                            if not isinstance(g, dict):
                                continue
                            raw = g.get("date") or g.get("day") or ""
                            band = g.get("shift_start") or g.get("band") or g.get("shift") or "—"
                            need = g.get("shortfall") or g.get("needed") or g.get("severity") or ""
                            sev = g.get("severity") or g.get("level") or ""
                            shift_card(
                                title=f"{format_date(raw) if raw else '—'} · {band}",
                                subtitle=f"{need} {sev}".strip(),
                                status=str(sev or "gap").upper()[:8] or "GAP",
                                status_level="crit",
                                primary_label="Ops",
                                on_primary=lambda: ui.navigate.to("/operations"),
                            )

            with panel("Open shifts · hours watch"):
                try:
                    opens = get_open_shifts(status="open", limit=8) or []
                except Exception:
                    opens = []
                if opens:
                    for sh in opens[:5]:
                        shift_card(
                            title=f"{format_date(sh.get('shift_date'))} · {sh.get('shift_start')}",
                            subtitle=f"Squad {sh.get('squad') or 'Any'}",
                            status="Open",
                            status_level="warn",
                            primary_label="Board",
                            on_primary=lambda: ui.navigate.to("/open-shifts"),
                        )
                else:
                    empty_state(
                        "Board clear",
                        "Post vacancies from Open shifts.",
                        cta_label="Open shift board",
                        cta_path="/open-shifts",
                    )

                try:
                    watch = get_hours_watch(officer_id=oid) or {}
                except Exception as exc:
                    watch = {"warnings": [], "message": str(exc)}
                warns = watch.get("warnings") or []
                ui.label(f"FLSA / hours · {watch.get('warning_count', len(warns))} warnings").classes(
                    "text-sm font-semibold q-mt-md q-mb-xs"
                )
                if warns:
                    for w in warns[:5]:
                        if isinstance(w, dict):
                            ui.label(
                                f"{w.get('officer_name') or w.get('name') or 'Officer'}: "
                                f"{w.get('message') or w.get('hours') or w}"
                            ).classes("text-xs text-gray-400")
                        else:
                            ui.label(str(w)).classes("text-xs text-gray-400")
                else:
                    ui.label("No officers near hours threshold.").classes("text-xs text-gray-500")

        # Outcome tiles — progressive, not a rainbow toolbar
        with panel("Quick actions", glow=False):
            if session.is_officer():
                tiles = [
                    ("/my-schedule", "My schedule", "14-day duty window"),
                    ("/time-off", "Time off", "Submit leave"),
                    ("/open-shifts", "Open shifts", "Claim vacancies"),
                    ("/notifications", "Alerts", "Inbox"),
                    ("/time-punch", "Time punch", "Clock in / out"),
                    ("/timecards", "Timecards", "Pay period hours"),
                    ("/banks", "Time banks", "Comp · sick · float"),
                    ("/availability", "Availability", "Blackout days"),
                    ("/bidding", "Shift bidding", "Rank preferences"),
                    ("/court", "Court & training", "Appearances"),
                    ("/certs", "Certifications", "My quals"),
                    ("/exports", "Exports", "iCal & downloads"),
                ]
            else:
                tiles = [
                    ("/ops-desk", "Ops desk", "Manual review · callout · gaps"),
                    ("/time-off", "Time off", "Approve with coverage plans"),
                    ("/open-shifts", "Open shifts", "Vacancy board"),
                    ("/callbacks", "Callbacks", "OT call-down"),
                    ("/live-schedule", "Live schedule", "Heat matrix"),
                    ("/roster", "Patrol roster", "Personnel"),
                    ("/exports", "Exports hub", "CSV · PDF · audit"),
                    ("/banks", "Time banks", "Comp · FLSA"),
                    ("/channels", "Notify channels", "SMS · email outbox"),
                    ("/access", "Access control", "Users · roles"),
                ]
                if session.can("simulator.use"):
                    tiles.append(("/simulator", "Simulator", "Best combination"))
            with ui.element("div").classes("grid-actions"):
                for path, title, sub in tiles:
                    with ui.element("div").classes("action-tile").on("click", lambda _e, p=path: ui.navigate.to(p)):
                        ui.html(f"<strong>{title}</strong><span>{sub}</span>", sanitize=False)

    layout("dashboard", body)
