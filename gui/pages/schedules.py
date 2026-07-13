"""Scheduling pages — My Schedule, Monthly, Live (SOC heat board)."""

from __future__ import annotations

from nicegui import ui

from config import GANTT_COLORS
from gui import session
from gui.clock import today_local
from gui.shell import layout, page_header, panel, scheduling_subnav
from logic import (
    build_schedule_matrix,
    compare_base_updated_schedule,
    create_manual_coverage_override,
    ensure_original_monthly_schedule,
    export_officer_schedule_ical,
    get_adjacent_cycle_window,
    get_current_cycle_window,
    get_cycle_day,
    get_monthly_summary_from_snapshot,
    get_officers_by_seniority,
    get_schedule_snapshot,
    is_future_cycle_window,
    sync_updated_schedule,
)
from validators import format_date, parse_date  # M/D/YY e.g. 7/9/26

STATUS_HEX = {
    "working": GANTT_COLORS.get("working", "#2ecc71"),
    "off": GANTT_COLORS.get("off", "#2a3544"),
    "bumped": GANTT_COLORS.get("bumped", "#f0b429"),
    "covering": GANTT_COLORS.get("covering", "#c9a227"),
    "swapped": GANTT_COLORS.get("swapped", "#3d8bfd"),
    "training": GANTT_COLORS.get("training", "#7c6af7"),
    "court": GANTT_COLORS.get("court", "#c45c9a"),
    "leave": GANTT_COLORS.get("leave", "#c45c7a"),
}


def matrix_html(matrix, days, *, show_cycle: bool = False) -> str:
    if not matrix:
        return '<div class="alert alert-warn">No Schedule Rows For This Window.</div>'
    cw, ch = 32, 16
    parts = [
        '<div class="sched-wrap" style="background:rgba(0,0,0,0.25);border-radius:12px;'
        'padding:14px;border:1px solid rgba(120,160,220,0.1)">'
    ]
    if show_cycle:
        parts.append('<div style="display:flex;gap:3px;margin-bottom:6px;align-items:flex-end">')
        parts.append('<div style="width:148px"></div>')
        for d in days:
            parts.append(
                f'<div style="width:{cw}px;text-align:center;font-size:9px;color:#5e6f8a;'
                f'letter-spacing:0.04em">D{get_cycle_day(d)}</div>'
            )
        parts.append("</div>")
    parts.append('<div style="display:flex;gap:3px;align-items:center;margin-bottom:8px">')
    parts.append(
        '<div style="width:148px;color:#5e6f8a;font-size:10px;letter-spacing:0.08em;'
        'font-weight:600">Unit / Officer</div>'
    )
    today = today_local()
    for d in days:
        col = "#22d3ee" if d == today else "#5e6f8a"
        glow = "text-shadow:0 0 8px rgba(34,211,238,0.5);" if d == today else ""
        # User-facing calendar date: format_date (M/D/YY). Weekday abbr is locale label only.
        full = format_date(d)
        weekday = d.strftime("%a")  # intentional: day-name, not a date policy field
        parts.append(
            f'<div style="width:{cw + 8}px;text-align:center;font-size:8px;color:{col};{glow};'
            f'line-height:1.25" title="{full}">'
            f'{weekday}<br/><strong style="font-size:9px">{full}</strong></div>'
        )
    parts.append("</div>")
    for entry in matrix:
        officer = entry["officer"]
        parts.append('<div style="display:flex;gap:3px;align-items:center;margin-bottom:3px;padding:2px 0">')
        shift = officer.get("shift_start") or ""
        label = f"{officer['name'][:18]}"
        if shift:
            label += f" · {shift}"
        parts.append(
            f'<div style="width:148px;font-size:11px;color:#e2e8f0;white-space:nowrap;'
            f'overflow:hidden;text-overflow:ellipsis;font-weight:500" title="{officer["name"]}">{label}</div>'
        )
        for d in days:
            status = entry["days"][d]
            color = STATUS_HEX.get(status, "#1e293b")
            if d == today:
                ring = "box-shadow:0 0 0 1px #22d3ee,0 0 10px rgba(34,211,238,0.35);"
            else:
                ring = "box-shadow:inset 0 0 0 1px rgba(0,0,0,0.35);"
            parts.append(
                f'<div class="sched-cell" title="{status} · {format_date(d)}" '
                f'style="width:{cw}px;height:{ch}px;background:{color};{ring}"></div>'
            )
        parts.append("</div>")
    legend = " ".join(
        f'<span style="display:inline-flex;align-items:center;gap:5px;margin-right:12px">'
        f'<span style="width:11px;height:11px;background:{c};border-radius:3px;'
        f'box-shadow:0 0 6px {c}55"></span>{k.title()}</span>'
        for k, c in STATUS_HEX.items()
    )
    parts.append(
        f'<div style="margin-top:14px;padding-top:12px;border-top:1px solid rgba(120,160,220,0.1);'
        f'color:#5e6f8a;font-size:10px">{legend}</div>'
    )
    parts.append("</div>")
    return "".join(parts)


def _filter_matrix(matrix):
    if session.is_officer():
        oid = session.linked_officer_id()
        return [e for e in matrix if e["officer"]["id"] == oid]
    return matrix


def render_my_schedule() -> None:
    """Personal / unit timeline (My Schedule)."""
    state: dict = {"start": None}

    def body() -> None:
        page_header(
            "My Schedule",
            "Your duty window for the current cycle (or full unit board for supervisors)",
            kicker="Scheduling",
        )
        scheduling_subnav("my_schedule")
        label = ui.label("").classes("text-sm q-mb-sm").style("color: var(--muted)")
        host = ui.element("div")

        def window():
            return get_current_cycle_window(state["start"] or today_local())

        def shift(direction: int):
            start, _ = window()
            nxt, _ = get_adjacent_cycle_window(start, direction)
            if direction > 0 and is_future_cycle_window(nxt):
                return
            state["start"] = nxt
            refresh()

        with ui.row().classes("gap-2 q-mb-md flex-wrap"):
            ui.button("◀ Previous", on_click=lambda: shift(-1)).classes("btn-ghost").props("no-caps outline dense")
            ui.button(
                "Today",
                on_click=lambda: (state.update(start=None), refresh()),
            ).classes("btn-ghost").props("no-caps outline dense")
            ui.button("Next ▶", on_click=lambda: shift(1)).classes("btn-ghost").props("no-caps outline dense")

            def export_ical():
                oid = session.linked_officer_id()
                if not oid:
                    ui.notify("Link an officer profile to export iCal", type="warning")
                    return
                start, end = window()
                result = export_officer_schedule_ical(oid, start_date=start, end_date=end)
                if result.get("success"):
                    path = result.get("path") or result.get("output_path") or result.get("file")
                    ui.notify(
                        f"iCal exported{(': ' + str(path)) if path else ''}",
                        type="positive",
                    )
                else:
                    ui.notify(result.get("message", "Export failed"), type="negative")

            if session.linked_officer_id() or session.is_officer():
                ui.button("Export iCal", on_click=export_ical).classes("btn-primary").props("no-caps unelevated dense")

        def refresh():
            start, end = window()
            label.set_text(f"Cycle Window: {format_date(start)} – {format_date(end)}")
            matrix, days = build_schedule_matrix(start, end)
            # Officers always personal; supervisors see full board here as unit view
            if session.is_officer():
                matrix = _filter_matrix(matrix)
            host.clear()
            with host:
                with panel("Duty Matrix", glow=True):
                    ui.html(matrix_html(matrix, days, show_cycle=True), sanitize=False)
                    # Always-visible LE status legend
                    with ui.row().classes("gap-3 q-mt-sm flex-wrap"):
                        for name, hex_c in (
                            ("Working", STATUS_HEX.get("working")),
                            ("Off", STATUS_HEX.get("off")),
                            ("Bumped", STATUS_HEX.get("bumped")),
                            ("Covering", STATUS_HEX.get("covering")),
                            ("Court", STATUS_HEX.get("court")),
                            ("Training", STATUS_HEX.get("training")),
                            ("Leave", STATUS_HEX.get("leave")),
                        ):
                            ui.html(
                                f'<span style="display:inline-flex;align-items:center;gap:6px;font-size:11px;color:#9aa8bc">'
                                f'<span style="width:10px;height:10px;border-radius:2px;background:{hex_c}"></span>{name}</span>',
                                sanitize=False,
                            )

        refresh()

    layout("my_schedule", body)


def _snapshot_status_line(year: int, month: int) -> str:
    """Publish/sync presence for base + updated snapshots."""
    base = get_schedule_snapshot(year, month, "base")
    updated = get_schedule_snapshot(year, month, "updated")
    b = "published" if base else "missing"
    u = "synced" if updated else "missing"
    return f"Snapshot {year}-{month:02d}: base {b} · live {u}"


def _render_monthly_headcount(year: int, month: int) -> None:
    """Day-level working headcount from published base snapshot."""
    snap = get_schedule_snapshot(year, month, "base")
    rows = get_monthly_summary_from_snapshot(snap, year, month, schedule_type="base") or []
    with panel(f"Monthly headcount · {year}-{month:02d}", glow=False):
        if not rows:
            ui.html('<div class="alert alert-warn">No summary rows.</div>', sanitize=False)
            return
        grid_rows = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            d = r.get("date")
            d_label = format_date(d) if d else "—"
            risk = "night" if r.get("high_risk_night") else ""
            grid_rows.append(
                {
                    "date": d_label,
                    "cycle": r.get("cycle_day"),
                    "squad": r.get("squad_on_duty"),
                    "working": r.get("working_officers"),
                    "risk": risk,
                }
            )
        try:
            from gui.tables import aggrid_from_dicts

            if grid_rows:
                aggrid_from_dicts(
                    grid_rows,
                    prefer_columns=["date", "cycle", "squad", "working", "risk"],
                    height="240px",
                )
                return
        except Exception:
            pass
        for r in grid_rows[:14]:
            with ui.element("div").classes("data-row"):
                ui.label(
                    f"{r.get('date')} · D{r.get('cycle')} · squad {r.get('squad')} · "
                    f"{r.get('working')} working {r.get('risk') or ''}"
                ).classes("text-sm mono")


def _render_schedule_diff_panel(year: int, month: int) -> None:
    """Base vs live row diffs (enterprise schedule compare)."""
    with panel(f"Base vs live · {year}-{month:02d}", glow=False):
        result = compare_base_updated_schedule(year, month)
        if not result.get("success"):
            ui.html(
                f'<div class="alert alert-warn">{result.get("message", "Unable to compare")}</div>',
                sanitize=False,
            )
            return
        n = int(result.get("diff_count") or 0)
        dates = result.get("dates_with_changes") or []
        ui.label(f"{n} change(s)" + (f" across {len(dates)} day(s)" if dates else "")).classes("text-sm q-mb-sm").style(
            "color: var(--muted)"
        )
        diffs = result.get("diffs") or []
        if not diffs:
            ui.html('<div class="alert alert-ok">Base and live match for this month.</div>', sanitize=False)
            return
        grid_rows = []
        for d in diffs[:200]:
            if not isinstance(d, dict):
                continue
            grid_rows.append(
                {
                    "date": d.get("assignment_date"),
                    "officer": d.get("officer_name") or d.get("officer_id"),
                    "base": d.get("base_status"),
                    "live": d.get("updated_status"),
                    "base_shift": f"{d.get('base_shift_start') or '—'}–{d.get('base_shift_end') or '—'}",
                    "live_shift": f"{d.get('updated_shift_start') or '—'}–{d.get('updated_shift_end') or '—'}",
                    "manual": "yes" if d.get("is_manual") else "",
                }
            )
        try:
            from gui.tables import aggrid_from_dicts

            if grid_rows:
                aggrid_from_dicts(
                    grid_rows,
                    prefer_columns=["date", "officer", "base", "live", "base_shift", "live_shift", "manual"],
                    height="280px",
                )
                return
        except Exception:
            pass
        for row in grid_rows[:40]:
            with ui.element("div").classes("data-row"):
                ui.label(f"{row.get('date')} · {row.get('officer')} · {row.get('base')} → {row.get('live')}").classes(
                    "text-sm mono"
                )


def _render_manual_coverage_panel(on_done) -> None:
    """Supervisor manual coverage assign (create_manual_coverage_override)."""
    if not session.can("schedule.updated.edit"):
        return
    officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
    if len(officers) < 2:
        with panel("Manual coverage"):
            ui.html('<div class="alert alert-warn">Need at least two active officers.</div>', sanitize=False)
        return
    names = [o["name"] for o in officers]
    omap = {o["name"]: o["id"] for o in officers}
    with panel("Manual coverage assignment", glow=True):
        ui.label("Assign a replacement to cover another officer's shift (writes override + notifies).").classes(
            "text-xs text-gray-500 q-mb-sm"
        )
        orig = ui.select(names, value=names[0], label="Original (off / covered)").classes("w-full")
        repl = ui.select(names, value=names[1] if len(names) > 1 else names[0], label="Replacement").classes("w-full")
        d_in = ui.input(label="Date", value=format_date(today_local()), placeholder="M/D/YY or M-D-YYYY").classes(
            "w-full"
        )
        reason = ui.input(label="Reason", value="Manual Coverage").classes("w-full")

        def assign():
            oid = omap.get(orig.value)
            rid = omap.get(repl.value)
            if not oid or not rid:
                ui.notify("Select both officers", type="negative")
                return
            if oid == rid:
                ui.notify("Original and replacement must differ", type="negative")
                return
            raw = (d_in.value or "").strip()
            try:
                dt = parse_date(raw)
            except Exception:
                dt = None
            if not dt:
                ui.notify("Invalid date", type="negative")
                return
            uid = (session.current_user() or {}).get("id")
            r = create_manual_coverage_override(
                oid,
                rid,
                dt.isoformat() if hasattr(dt, "isoformat") else str(dt),
                reason=(reason.value or "").strip() or "Manual Coverage",
                actor_user_id=uid,
            )
            if r.get("success"):
                ui.notify(r.get("message") or "Coverage assigned", type="positive")
                if on_done:
                    on_done()
            else:
                ui.notify(r.get("message") or "Assign failed", type="negative")

        ui.button("Assign coverage", on_click=assign).classes("btn-primary q-mt-sm").props("no-caps unelevated dense")


def render_monthly_schedule() -> None:
    """Original monthly / base plan."""

    def body() -> None:
        page_header(
            "Monthly Schedule",
            "Original monthly plan fixed after generation",
            kicker="Scheduling",
        )
        scheduling_subnav("monthly")
        status = ui.label("").classes("text-xs q-mb-sm").style("color: var(--dim)")
        host = ui.element("div")
        t0 = today_local()
        status.set_text(_snapshot_status_line(t0.year, t0.month))

        def generate():
            t = today_local()
            r = ensure_original_monthly_schedule(t.year, t.month)
            status.set_text(r.get("message", "Done") + " · " + _snapshot_status_line(t.year, t.month))
            refresh()

        with ui.row().classes("gap-2 q-mb-md"):
            if session.can("schedule.base.publish"):
                ui.button("Generate / Lock Month", on_click=generate).classes("btn-primary").props(
                    "no-caps unelevated dense"
                )
            ui.button("Refresh", on_click=lambda: refresh()).classes("btn-ghost").props("no-caps outline dense")

        def refresh():
            t = today_local()
            start, end = get_current_cycle_window()
            matrix, days = build_schedule_matrix(start, end)
            matrix = _filter_matrix(matrix)
            host.clear()
            with host:
                with panel(
                    f"Original Monthly · {format_date(start)} – {format_date(end)}",
                    glow=True,
                ):
                    ui.html(matrix_html(matrix, days, show_cycle=True), sanitize=False)
                _render_monthly_headcount(t.year, t.month)
                if session.can("schedule.updated.view") or session.can("schedule.base.view"):
                    _render_schedule_diff_panel(t.year, t.month)

        refresh()

    layout("monthly", body)


def render_live_schedule() -> None:
    """Live coverage after leave, bumps, swaps."""

    def body() -> None:
        page_header(
            "Live Schedule",
            "Live coverage after leave, bumps, and swaps",
            kicker="Scheduling",
        )
        scheduling_subnav("live")
        status = ui.label("").classes("text-xs q-mb-sm").style("color: var(--dim)")
        host = ui.element("div")
        t0 = today_local()
        status.set_text(_snapshot_status_line(t0.year, t0.month))

        def sync():
            t = today_local()
            r = sync_updated_schedule(t.year, t.month)
            status.set_text(r.get("message", "Done") + " · " + _snapshot_status_line(t.year, t.month))
            refresh()

        with ui.row().classes("gap-2 q-mb-md"):
            if session.can("schedule.updated.sync"):
                ui.button("Sync Live", on_click=sync).classes("btn-primary").props("no-caps unelevated dense")
            ui.button("Refresh", on_click=lambda: refresh()).classes("btn-ghost").props("no-caps outline dense")

        def refresh():
            t = today_local()
            start, end = get_current_cycle_window()
            matrix, days = build_schedule_matrix(start, end)
            matrix = _filter_matrix(matrix)
            host.clear()
            with host:
                with panel(
                    f"Live Coverage · {format_date(start)} – {format_date(end)}",
                    glow=True,
                ):
                    ui.html(matrix_html(matrix, days, show_cycle=True), sanitize=False)
                _render_manual_coverage_panel(on_done=refresh)
                if session.can("schedule.updated.view") or session.can("schedule.base.view"):
                    _render_schedule_diff_panel(t.year, t.month)

        refresh()

    layout("live", body)


# Back-compat names used by older imports
def render_schedules() -> None:
    render_live_schedule()


def render_timeline() -> None:
    render_my_schedule()
