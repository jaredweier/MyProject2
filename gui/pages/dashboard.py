"""Duty board — SHIFTVOID / PULSE mockup layout."""

from __future__ import annotations

from nicegui import ui

from gui import session
from gui.clock import format_clock, format_local_date, today_local
from gui.shell import layout, page_header, panel
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
        name = session.display_name()  # full name only — no time-of-day greeting
        cycle = get_cycle_day(today)
        squad = get_squad_on_duty(cycle)
        oid = session.linked_officer_id() if session.is_officer() else None
        # Fast KPIs only — full get_dashboard_insights is multi-second and blocks the UI
        insights = get_dashboard_kpis_fast(officer_id=oid) or {}
        if not isinstance(insights, dict):
            insights = {}

        n_off = len(active_officers())
        pending = insights.get("pending_requests", 0)
        swaps = insights.get("pending_swaps", 0)
        gaps = insights.get("coverage_gap_count", 0)
        issues = insights.get("coverage_issues", 0)

        page_header(
            name,
            f"District Duty Ops · {format_local_date(today)} · {format_clock()} · "
            f"Cycle Day {cycle} · Squad {squad} On Duty · {n_off} Officers Active",
            kicker="Ops Floor",
        )

        # Severity strip — dark NOC / command-center pattern (admin dashboard UX 2026)
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
                ],
                title="Ops severity strip",
            )
        except Exception:
            pass

        # Clickable KPIs → deep-link (Mark43/Linear jump pattern)
        with ui.element("div").classes("kpi-row q-mb-md"):

            def kpi_card(title, value, hint, path, danger=False, warn=False):
                border = (
                    "border-color:rgba(239,68,68,0.45)"
                    if danger and value
                    else ("border-color:rgba(245,158,11,0.45)" if warn and value else "")
                )
                with (
                    ui.element("div")
                    .classes("kpi")
                    .style(f"cursor:pointer;{border}")
                    .on("click", lambda _e, p=path: ui.navigate.to(p))
                ):
                    ui.html(f'<div class="kpi-l">{title}</div>', sanitize=False)
                    ui.html(f'<div class="kpi-v">{value}</div>', sanitize=False)
                    ui.html(f'<div class="kpi-hint">{hint}</div>', sanitize=False)

            kpi_card("Active Officers", n_off, "Roster · click for personnel", "/roster")
            kpi_card("Pending Leave", pending, "Awaiting review · click", "/time-off", warn=True)
            kpi_card("Shift Swaps", swaps, "Exchange queue · click", "/time-off", warn=True)
            kpi_card("Coverage Gaps", gaps, "48h board · click ops", "/operations", danger=True)
            kpi_card("Night Min Issues", issues, "Staffing floor · click ops", "/operations", danger=True)
            kpi_card("Open Vacancies", n_open, "Claim / post · click", "/open-shifts", warn=True)
            kpi_card("Fatigue / hours", n_fat, "FLSA proximity · click payroll", "/payroll", warn=True)

        # First Due / PowerTime pattern: roster count strip for today
        if not session.is_officer():
            with panel("Today roster count (command strip)", glow=False):
                try:
                    coverage = get_shift_coverage_counts_for_range(today, today)
                except Exception:
                    coverage = {}
                bands = list(get_active_shift_times().values()) if get_active_shift_times() else []
                total_on = 0
                parts = []
                for start, end in bands:
                    c = int(coverage.get((today.isoformat(), squad, start), 0) or 0)
                    total_on += c
                    parts.append(f"{start}→{c}")
                ui.label(
                    f"Squad {squad} on duty · {total_on} assigned across bands · " + " · ".join(parts[:6])
                ).classes("text-sm mono")
                ui.label(
                    "Industry pattern (First Due roster count / PowerTime min staffing): glance staffing before gaps."
                ).classes("text-xs text-gray-500 q-mt-xs")

        with ui.element("div").classes("grid-2"):
            with panel("On-Duty Shifts", glow=True):
                if session.is_officer():
                    ui.html(
                        '<div class="alert alert-ok">Open My Schedule For Your Personal Duty Window.</div>',
                        sanitize=False,
                    )
                else:
                    coverage = get_shift_coverage_counts_for_range(today, today)
                    day_str = today.isoformat()
                    ui.html(
                        f'<div style="font-family:var(--mono);font-size:11px;color:var(--dim);margin-bottom:10px">'
                        f"SQUAD {squad} · {format_clock()}</div>",
                        sanitize=False,
                    )
                    for start, end in get_active_shift_times().values():
                        count = coverage.get((day_str, squad, start), 0)
                        dot = "shift-dot" if count else "shift-dot warn"
                        with ui.element("div").classes("shift-row"):
                            with ui.row().classes("items-center gap-3"):
                                ui.html(f'<span class="{dot}"></span>', sanitize=False)
                                with ui.element("div"):
                                    ui.label(f"{start} – {end}").classes("text-sm font-semibold")
                                    ui.label("Patrol Band").classes("text-xs").style("color: var(--dim)")
                            ui.badge(f"{count} On").props(f"outline color={'positive' if count else 'warning'}")

            with panel("Watch Status"):
                if issues:
                    ui.html(
                        f'<div class="alert alert-crit">⚠ Severity · Night Minimum · {issues} Issue(s) This Cycle</div>',
                        sanitize=False,
                    )
                if gaps:
                    ui.html(
                        f'<div class="alert alert-warn">Coverage Gaps In Next 48h: {gaps}</div>',
                        sanitize=False,
                    )
                if not issues and not gaps:
                    ui.html(
                        '<div class="alert alert-ok">'
                        "<strong>All Clear</strong> · No Critical Coverage Flags On This Watch. "
                        "Coverage Floor Met · System Integrity Nominal."
                        "</div>",
                        sanitize=False,
                    )
                unread = get_unread_notification_count(officer_id=oid)
                ui.html(
                    f'<div style="margin-top:12px;font-family:var(--mono);font-size:11px;color:var(--dim)">'
                    f"Unread Alerts · <strong style='color:var(--text)'>{unread}</strong></div>",
                    sanitize=False,
                )

        # —— LE product patterns: My Week · Gap board · Open shifts · Hours watch ——
        with ui.element("div").classes("grid-2"):
            if session.is_officer() and oid:
                with panel("My Week", glow=True):
                    try:
                        week = get_officer_schedule_window(oid, days=7) or {}
                    except Exception as exc:
                        week = {"success": False, "message": str(exc)}
                    days = week.get("days") or week.get("schedule") or week.get("rows") or []
                    if not days and week.get("message"):
                        ui.label(str(week.get("message"))).classes("text-sm text-gray-400")
                    elif not days:
                        ui.html(
                            '<div class="alert alert-ok">Open My Schedule for your full window.</div>',
                            sanitize=False,
                        )
                    else:
                        for day in days[:7]:
                            if not isinstance(day, dict):
                                continue
                            raw = day.get("date") or day.get("day") or ""
                            status = day.get("status") or day.get("duty") or day.get("label") or "—"
                            shift = day.get("shift_start") or day.get("shift") or ""
                            ui.label(
                                f"{format_date(raw) if raw else '—'} · {status}" + (f" · {shift}" if shift else "")
                            ).classes("text-sm q-mb-xs")
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
                        ui.html(
                            '<div class="alert alert-ok">No coverage gaps in the next 48 hours.</div>',
                            sanitize=False,
                        )
                    else:
                        for g in gap_rows[:12]:
                            if not isinstance(g, dict):
                                continue
                            raw = g.get("date") or g.get("day") or ""
                            band = g.get("shift_start") or g.get("band") or g.get("shift") or "—"
                            need = g.get("shortfall") or g.get("needed") or g.get("severity") or ""
                            sev = g.get("severity") or g.get("level") or ""
                            ui.label(f"{format_date(raw) if raw else '—'} · {band} · {need} {sev}").classes(
                                "text-sm q-mb-xs"
                            )
                    ui.button("Ops reports", on_click=lambda: ui.navigate.to("/operations")).classes(
                        "btn-ghost q-mt-sm"
                    ).props("no-caps outline dense")

            with panel("Open shifts · Hours watch"):
                try:
                    opens = get_open_shifts(status="open", limit=8) or []
                except Exception:
                    opens = []
                ui.label(f"Open vacancies: {len(opens)}").classes("text-sm font-semibold q-mb-xs")
                if opens:
                    for sh in opens[:5]:
                        ui.label(
                            f"{format_date(sh.get('shift_date'))} · {sh.get('shift_start')} "
                            f"Squad {sh.get('squad') or 'Any'}"
                        ).classes("text-xs text-gray-400")
                else:
                    ui.label("Board clear — post from Open Shifts.").classes("text-xs text-gray-500")
                ui.button("Open shift board", on_click=lambda: ui.navigate.to("/open-shifts")).classes(
                    "btn-ghost q-mt-sm q-mb-md"
                ).props("no-caps outline dense")

                try:
                    watch = get_hours_watch(officer_id=oid) or {}
                except Exception as exc:
                    watch = {"warnings": [], "message": str(exc)}
                warns = watch.get("warnings") or []
                ui.label(
                    f"FLSA / hours watch · {watch.get('warning_count', len(warns))} warnings · "
                    f"threshold {watch.get('period_threshold', '—')}h / period"
                ).classes("text-sm font-semibold q-mb-xs")
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

        with panel("Quick Actions", glow=False):
            tiles = []
            if session.is_officer():
                tiles = [
                    ("/my-schedule", "My Schedule", "14-Day Duty Window"),
                    ("/time-off", "Time Off Requests", "Submit Leave"),
                    ("/open-shifts", "Open Shifts", "Claim Vacancies"),
                    ("/notifications", "Alerts", "Inbox"),
                    ("/availability", "Availability", "Blackout Days"),
                    ("/live-schedule", "Live Schedule", "Coverage Matrix"),
                    ("/timecards", "Timecards", "Pay Period Hours"),
                    ("/bidding", "Shift Bidding", "Bid Cycles"),
                    ("/certs", "My Certs", "Qualifications"),
                ]
            else:
                tiles = [
                    ("/time-off", "Time Off Requests", "Approve With Coverage Plans"),
                    ("/open-shifts", "Open Shifts", "Vacancy Board"),
                    ("/bidding", "Shift Bidding", "Publish / Award"),
                    ("/callbacks", "Callbacks", "OT Call-Down"),
                    ("/notifications", "Alerts", "Inbox"),
                    ("/certs", "Certifications", "Qual Gates"),
                    ("/availability", "Availability", "Blackouts / Holidays"),
                    ("/my-schedule", "My Schedule", "Unit Duty Board"),
                    ("/live-schedule", "Live Schedule", "Live Heat Matrix"),
                    ("/monthly-schedule", "Monthly Schedule", "Original Plan"),
                    ("/roster", "Patrol Roster", "Personnel Command"),
                    ("/timecards", "Timecards", "Time Entry"),
                    ("/payroll", "Payroll", "Pay Period Ledger"),
                ]
                if session.can("simulator.use"):
                    tiles.append(("/simulator", "Schedule Simulator", "Best Combination"))
                if session.can("reports.view"):
                    tiles.append(("/operations", "Ops Reports", "Coverage & OT Equity"))
                tiles.append(("/security", "Security & Governance", "RBAC · Audit · Targets"))
            if session.is_officer():
                tiles.append(("/security", "Security & Governance", "Your Access Profile"))
            with ui.element("div").classes("grid-actions"):
                for path, title, sub in tiles:
                    with ui.element("div").classes("action-tile").on("click", lambda _e, p=path: ui.navigate.to(p)):
                        ui.html(f"<strong>{title}</strong><span>{sub}</span>", sanitize=False)

    layout("dashboard", body)
