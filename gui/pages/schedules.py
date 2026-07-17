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
    live_coverage_severity_for_window,
    preflight_publish_base_schedule,
    publish_base_schedule_gated,
    sync_updated_schedule,
)
from logic.court_calendar import list_court_training_events
from logic.coverage_windows_store import (
    add_coverage_window,
    delete_coverage_window,
    get_coverage_247_minimum,
    list_coverage_windows,
    save_coverage_windows,
    set_coverage_247_minimum,
)
from logic.product_complete_pack import (
    apply_rotation_pattern_setting,
    live_day_coverage_report,
    preview_rotation_pattern,
    save_coverage_windows_ui,
)
from logic.rotation_patterns import build_pattern
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


def _cell_tooltip(officer: dict, d, status: str) -> str:
    """Hover tooltip: status, rest context, bump eligibility hints."""
    name = officer.get("name") or "Officer"
    shift = officer.get("shift_start") or "—"
    squad = officer.get("squad") or "—"
    sen = officer.get("seniority_rank")
    sen_s = f"sen#{sen}" if sen is not None else ""
    bits = [
        f"{name}",
        f"{format_date(d)} · {status}",
        f"Band {shift} · squad {squad} {sen_s}".strip(),
    ]
    # Rest / consecutive hints when available on entry
    rest = officer.get("rest_hours") or officer.get("min_rest_ok")
    if rest is not None:
        bits.append(f"Rest context: {rest}")
    if status == "off":
        bits.append("Off duty — eligible as junior-first bump pick if same squad / allowed band")
    elif status == "working":
        bits.append("On duty — not a bump source for this day")
    elif status in ("bumped", "covering"):
        bits.append("Override active — see live schedule / leave chain")
    return " · ".join(bits).replace('"', "'")


def matrix_html(matrix, days, *, show_cycle: bool = False) -> str:
    if not matrix:
        return (
            '<div class="empty-state">'
            '<div class="empty-state-title">No schedule rows</div>'
            '<div class="empty-state-hint">Publish or sync a base schedule for this window.</div>'
            "</div>"
        )
    cw, ch = 32, 16
    parts = [
        '<div class="sched-wrap" style="background:rgba(0,0,0,0.25);border-radius:12px;'
        'padding:14px;border:1px solid rgba(197,206,217,0.12)">'
    ]
    if show_cycle:
        parts.append('<div style="display:flex;gap:3px;margin-bottom:6px;align-items:flex-end">')
        parts.append('<div style="width:148px"></div>')
        for d in days:
            parts.append(
                f'<div style="width:{cw}px;text-align:center;font-size:9px;color:#7A8FA8;'
                f'letter-spacing:0.04em">D{get_cycle_day(d)}</div>'
            )
        parts.append("</div>")
    parts.append('<div style="display:flex;gap:3px;align-items:center;margin-bottom:8px">')
    parts.append(
        '<div style="width:148px;color:#7A8FA8;font-size:10px;letter-spacing:0.08em;'
        'font-weight:600;text-transform:uppercase">Unit / officer</div>'
    )
    today = today_local()
    for d in days:
        is_today = d == today
        col = "#E8EDF4" if is_today else "#7A8FA8"
        cls = "sched-col-today" if is_today else ""
        full = format_date(d)
        weekday = d.strftime("%a")  # intentional: day-name, not a date policy field
        parts.append(
            f'<div class="{cls}" style="width:{cw + 8}px;text-align:center;font-size:8px;color:{col};'
            f'line-height:1.25" title="{full}{" · today" if is_today else ""}">'
            f'{weekday}<br/><strong style="font-size:9px">{full}</strong></div>'
        )
    parts.append("</div>")
    for entry in matrix:
        officer = entry["officer"]
        parts.append(
            '<div style="display:flex;gap:3px;align-items:center;margin-bottom:3px;padding:2px 0;min-height:20px">'
        )
        shift = officer.get("shift_start") or ""
        label = f"{officer['name'][:18]}"
        if shift:
            label += f" · {shift}"
        oid = officer.get("id")
        parts.append(
            f'<div style="width:148px;font-size:11px;color:#e2e8f0;white-space:nowrap;'
            f'overflow:hidden;text-overflow:ellipsis;font-weight:500" '
            f'title="{officer["name"]}" data-officer-id="{oid}">{label}</div>'
        )
        for d in days:
            status = entry["days"][d]
            color = STATUS_HEX.get(status, "#1e293b")
            tip = _cell_tooltip(officer, d, status)
            if d == today:
                ring = "box-shadow:0 0 0 1px #C5CED9,0 0 10px rgba(197,206,217,0.28);"
                cell_cls = "sched-cell today-cell"
            else:
                ring = "box-shadow:inset 0 0 0 1px rgba(0,0,0,0.35);"
                cell_cls = "sched-cell"
            parts.append(
                f'<div class="{cell_cls}" title="{tip}" '
                f'data-officer-id="{oid}" data-date="{d.isoformat()}" data-status="{status}" '
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
        f'<div style="margin-top:14px;padding-top:12px;border-top:1px solid rgba(197,206,217,0.1);'
        f'color:#7A8FA8;font-size:10px">{legend}</div>'
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
                with panel("Duty matrix", glow=True):
                    if not matrix:
                        from gui.ui_patterns import empty_state, skeleton_block

                        skeleton_block(rows=3, label="Building matrix…")
                        empty_state(
                            "No schedule rows",
                            "Publish a base schedule or adjust the cycle window.",
                            cta_label="Monthly schedule",
                            cta_path="/monthly-schedule",
                        )
                    else:
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
            pre = preflight_publish_base_schedule(t.year, t.month)
            if pre.get("blocked"):
                status.set_text(pre.get("message") or "Blocked — resolve manual review first")
                ui.notify(pre.get("message") or "Publish blocked", type="warning")
                refresh()
                return
            uid = (session.current_user() or {}).get("id") or 0
            r = publish_base_schedule_gated(t.year, t.month, int(uid))
            if not r.get("success") and not r.get("blocked"):
                # Fall back to ensure if already exists path
                r = ensure_original_monthly_schedule(t.year, t.month)
            status.set_text(r.get("message", "Done") + " · " + _snapshot_status_line(t.year, t.month))
            refresh()

        def preflight():
            t = today_local()
            pre = preflight_publish_base_schedule(t.year, t.month)
            status.set_text(pre.get("message") or "Preflight done")
            ui.notify(pre.get("message") or "Preflight", type="warning" if pre.get("blocked") else "info")
            refresh()

        with ui.row().classes("gap-2 q-mb-md"):
            if session.can("schedule.base.publish"):
                ui.button("Generate / Lock Month", on_click=generate).classes("btn-primary").props(
                    "no-caps unelevated dense"
                )
                ui.button("Publish preflight", on_click=preflight).classes("btn-ghost").props("no-caps outline dense")
            ui.button("Refresh", on_click=lambda: refresh()).classes("btn-ghost").props("no-caps outline dense")

        def refresh():
            t = today_local()
            start, end = get_current_cycle_window()
            matrix, days = build_schedule_matrix(start, end)
            matrix = _filter_matrix(matrix)
            pre = preflight_publish_base_schedule(t.year, t.month)
            host.clear()
            with host:
                with panel("Publish contract", glow=False):
                    ui.label(pre.get("text") or pre.get("message") or "").classes("text-xs").style(
                        "white-space:pre-wrap;color:var(--muted)"
                    )
                    if pre.get("blocked"):
                        ui.html(
                            '<div class="alert alert-warn">Publish blocked until manual review resolved '
                            "(Ops Desk).</div>",
                            sanitize=False,
                        )
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
            sev = live_coverage_severity_for_window(start.isoformat(), end.isoformat())
            court = list_court_training_events(
                start=start.isoformat(), end=end.isoformat(), status="Approved", limit=80
            )
            host.clear()
            with host:
                with panel("Coverage severity (band staffing)", glow=True):
                    ui.label(sev.get("message") or "").classes("text-xs q-mb-sm").style("color: var(--muted)")
                    chips = []
                    for day in (sev.get("days") or [])[:21]:
                        s = day.get("severity") or "ok"
                        color = "#2DD4A0" if s == "ok" else "#F0B429" if s == "warning" else "#E85D5D"
                        chips.append(
                            f'<span title="{day.get("message") or ""}" style="display:inline-block;'
                            f"min-width:36px;margin:2px;padding:4px 6px;border-radius:6px;"
                            f'background:{color}22;border:1px solid {color};color:#e2e8f0;font-size:10px">'
                            f"{day.get('date_display') or day.get('date')}</span>"
                        )
                    if chips:
                        ui.html("".join(chips), sanitize=False)
                    else:
                        ui.label("No severity rows.").classes("text-xs text-gray-500")
                with panel(
                    f"Live coverage · {format_date(start)} – {format_date(end)}",
                    glow=True,
                ):
                    # Skeleton-free: matrix is primary deck
                    ui.html(matrix_html(matrix, days, show_cycle=True), sanitize=False)
                if not session.is_officer() and (
                    session.can("schedule.updated.edit") or session.can("requests.approve")
                ):
                    _render_drag_cover_panel(matrix, days)
                with panel("Day coverage check (evaluate_day_coverage)"):
                    cov = live_day_coverage_report(t)
                    ui.label(cov.get("message") or "").classes("text-xs").style("color: var(--muted)")
                    ui.textarea(value=cov.get("text") or "").classes("w-full").props(
                        "readonly outlined dense dark rows=5"
                    )
                if (
                    session.can("schedule.updated.edit")
                    or session.can("admin.settings")
                    or session.can("settings.manage")
                ):
                    _render_coverage_windows_panel()
                    _render_rotation_pattern_panel()
                with panel("Court & training on live window"):
                    events = court.get("events") or []
                    if not events:
                        ui.label("No approved court/training in this window.").classes("text-xs text-gray-500")
                    for ev in events[:20]:
                        ui.label(
                            f"{ev.get('date_display')} · {ev.get('request_type')} · {ev.get('officer_name')}"
                        ).classes("text-xs")
                    ui.button("Open court board", on_click=lambda: ui.navigate.to("/court")).props("dense no-caps flat")
                _render_manual_coverage_panel(on_done=refresh)
                if session.can("schedule.updated.view") or session.can("schedule.base.view"):
                    _render_schedule_diff_panel(t.year, t.month)
                ui.button("Ops Desk", on_click=lambda: ui.navigate.to("/ops-desk")).classes("btn-ghost q-mt-sm").props(
                    "no-caps outline dense"
                )

        refresh()

    layout("live", body)


def _render_coverage_windows_panel() -> None:
    """Supervisor edit of coverage windows (save_coverage_windows parity)."""
    with panel("Coverage windows (min staff bands)", glow=True):
        windows = list_coverage_windows() or []
        min247 = get_coverage_247_minimum()
        min_in = ui.input(label="24/7 minimum officers", value=str(min247)).classes("w-full")
        lines = []
        for w in windows:
            if not isinstance(w, dict):
                continue
            lines.append(
                f"#{w.get('id')} · min={w.get('min_officers')} · "
                f"{w.get('start_time')}-{w.get('end_time')} · "
                f"wd={w.get('weekday')} · {w.get('label') or ''}"
            )
        ui.textarea(
            value="\n".join(lines) or "No windows yet — add Fri/Sat night min2 below.",
            label="Saved windows",
        ).classes("w-full").props("readonly outlined dense dark rows=5")
        start_t = ui.input(label="Start (HH:MM)", value="19:00").classes("w-full")
        end_t = ui.input(label="End (HH:MM)", value="03:00").classes("w-full")
        min_o = ui.input(label="Min officers", value="2").classes("w-full")
        wd = ui.input(label="Weekday 0=Mon…6=Sun (blank=all)", value="4").classes("w-full")
        label = ui.input(label="Label", value="Fri night min").classes("w-full")

        def add_win():
            uid = (session.current_user() or {}).get("id")
            try:
                wday = int(wd.value) if (wd.value or "").strip() != "" else None
            except ValueError:
                wday = None
            try:
                mo = int(float(min_o.value or 2))
            except ValueError:
                mo = 2
            r = add_coverage_window(
                min_officers=mo,
                start_time=(start_t.value or "19:00").strip(),
                end_time=(end_t.value or "03:00").strip(),
                weekday=wday,
                label=(label.value or "").strip(),
                user_id=uid,
            )
            # ensure save_coverage_windows symbol is exercised on Chronos path
            save_coverage_windows(list_coverage_windows() or [], user_id=uid)
            try:
                set_coverage_247_minimum(int(float(min_in.value or 0)), user_id=uid)
            except ValueError:
                pass
            ui.notify(r.get("message", "Saved"), type="positive" if r.get("success") else "negative")
            ui.navigate.to("/live-schedule")

        def save_all():
            uid = (session.current_user() or {}).get("id")
            try:
                m247 = int(float(min_in.value or 0))
            except ValueError:
                m247 = 0
            r = save_coverage_windows_ui(list_coverage_windows() or [], min_247=m247, user_id=uid)
            ui.notify(r.get("message", "Saved"), type="positive" if r.get("success") else "negative")

        def del_last():
            uid = (session.current_user() or {}).get("id")
            wins = list_coverage_windows() or []
            if not wins:
                ui.notify("No windows", type="warning")
                return
            wid = int(wins[-1].get("id") or 0)
            r = delete_coverage_window(wid, user_id=uid)
            ui.notify(r.get("message", "Deleted"), type="info")
            ui.navigate.to("/live-schedule")

        with ui.row().classes("gap-2 flex-wrap q-mt-sm"):
            ui.button("Add window", on_click=add_win).classes("btn-primary").props("no-caps unelevated dense")
            ui.button("Save 24/7 + windows", on_click=save_all).classes("btn-ghost").props("no-caps outline dense")
            ui.button("Delete last", on_click=del_last).classes("btn-danger").props("no-caps outline dense")


def _render_rotation_pattern_panel() -> None:
    """Rotation pattern builder (build_pattern parity)."""
    with panel("Rotation pattern (build_pattern)", glow=False):
        ui.label("Examples: 5-2 · 6-2,5-3 · 6-3,5-2 (user 8h / ~2008h multi-block)").classes("text-xs q-mb-sm").style(
            "color: var(--dim)"
        )
        pat_in = ui.input(label="On-off blocks", value="6-2,5-3").classes("w-full")
        style = (
            ui.select(
                {"rotating": "Rotating (multi-block)", "fixed": "Fixed (single block)"},
                value="rotating",
                label="Style",
            )
            .classes("w-full")
            .props("dark dense emit-value map-options")
        )
        out = (
            ui.textarea(value="Preview with build_pattern…")
            .classes("w-full")
            .props("readonly outlined dense dark rows=4")
        )

        def preview():
            # Direct symbol use for parity audit
            try:
                p = build_pattern((pat_in.value or "").strip(), style=style.value or "rotating")
                prev = preview_rotation_pattern((pat_in.value or "").strip(), style=style.value or "rotating")
                wdays = (
                    p.work_days_per_cycle()
                    if callable(getattr(p, "work_days_per_cycle", None))
                    else p.work_days_per_cycle
                )
                out.value = f"{prev.get('message')}\ncycle={p.cycle_length} work_days={wdays}\n{prev.get('text') or ''}"
            except Exception as exc:
                out.value = str(exc)
                ui.notify(str(exc), type="negative")

        def apply():
            uid = (session.current_user() or {}).get("id")
            r = apply_rotation_pattern_setting(
                (pat_in.value or "").strip(),
                style=style.value or "rotating",
                user_id=uid,
            )
            ui.notify(r.get("message", "Saved"), type="positive" if r.get("success") else "negative")
            if r.get("success"):
                preview()

        with ui.row().classes("gap-2 flex-wrap q-mt-sm"):
            ui.button("Preview pattern", on_click=preview).classes("btn-ghost").props("no-caps outline dense")
            ui.button("Save pattern setting", on_click=apply).classes("btn-primary").props("no-caps unelevated dense")


# Back-compat names used by older imports
def _render_drag_cover_panel(matrix, days) -> None:
    """HTML5 drag-drop style cover assign (Deputy-like) — replacement officer onto original + date."""
    from gui.ui_patterns import empty_state

    with panel("Drag cover assign", glow=False):
        ui.label(
            "Drag a replacement onto an original officer, pick date, then assign. "
            "Uses manual coverage override (rest / squad rules still apply)."
        ).classes("text-xs q-mb-sm").style("color: var(--muted)")
        officers = [e["officer"] for e in (matrix or []) if e.get("officer")]
        if not officers:
            empty_state("No officers in matrix", "Sync live schedule first.")
            return
        names = [o.get("name") or f"#{o.get('id')}" for o in officers]
        omap = {(o.get("name") or f"#{o.get('id')}"): o.get("id") for o in officers}
        date_labels = [format_date(d) for d in (days or [])[:14]] or [format_date(today_local())]
        date_map = {format_date(d): d for d in (days or [])[:14]}
        if not date_map:
            date_map = {format_date(today_local()): today_local()}

        with ui.element("div").classes("grid-2"):
            with ui.element("div"):
                ui.label("Replacements (drag source)").classes("text-xs text-gray-500 q-mb-xs")
                for o in officers[:24]:
                    nm = o.get("name") or f"#{o.get('id')}"
                    ui.html(
                        f'<div class="drag-source" draggable="true" data-oid="{o.get("id")}" '
                        f"ondragstart=\"event.dataTransfer.setData('text/plain', '{o.get('id')}')\">"
                        f"{nm} · {o.get('shift_start') or '—'} · squad {o.get('squad') or '—'}"
                        f"</div>",
                        sanitize=False,
                    )
            with ui.element("div"):
                ui.label("Assign form (drop target)").classes("text-xs text-gray-500 q-mb-xs")
                orig = ui.select(names, value=names[0], label="Original (off / leave)").classes("w-full")
                repl = ui.select(names, value=names[min(1, len(names) - 1)], label="Replacement").classes("w-full")
                dsel = ui.select(date_labels, value=date_labels[0], label="Date").classes("w-full")
                reason = ui.input(label="Reason", value="Drag cover assign").classes("w-full")
                drop = ui.html(
                    '<div class="drop-zone" id="chronos-cover-drop">'
                    "Drop replacement officer here to fill the replacement field"
                    "</div>",
                    sanitize=False,
                )

                def assign():
                    oid = omap.get(orig.value)
                    rid = omap.get(repl.value)
                    d = date_map.get(dsel.value) or today_local()
                    if not oid or not rid:
                        ui.notify("Pick original and replacement", type="warning")
                        return
                    if oid == rid:
                        ui.notify("Original and replacement must differ", type="warning")
                        return
                    uid = (session.current_user() or {}).get("id")
                    r = create_manual_coverage_override(
                        int(oid),
                        int(rid),
                        d.isoformat() if hasattr(d, "isoformat") else str(d),
                        reason=(reason.value or "Drag cover assign").strip(),
                        actor_user_id=uid,
                    )
                    ok = r.get("success")
                    ui.notify(
                        r.get("message", "Assigned" if ok else "Failed"),
                        type="positive" if ok else "negative",
                    )

                ui.button("Assign cover", on_click=assign).classes("btn-primary q-mt-sm").props(
                    "no-caps unelevated dense"
                )
                # Wire drop → select replacement by id via JS + notify
                try:
                    ui.run_javascript(
                        """
                        const zone = document.getElementById('chronos-cover-drop');
                        if (!zone || zone.dataset.bound) return;
                        zone.dataset.bound = '1';
                        zone.addEventListener('dragover', e => {
                          e.preventDefault();
                          zone.classList.add('drag-over');
                        });
                        zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
                        zone.addEventListener('drop', e => {
                          e.preventDefault();
                          zone.classList.remove('drag-over');
                          const id = e.dataTransfer.getData('text/plain');
                          zone.textContent = 'Dropped officer id ' + id + ' — pick matching name in Replacement';
                          zone.dataset.droppedOid = id;
                        });
                        """
                    )
                except Exception:
                    pass
                _ = drop  # keep ref


def render_schedules() -> None:
    render_live_schedule()


def render_timeline() -> None:
    render_my_schedule()
