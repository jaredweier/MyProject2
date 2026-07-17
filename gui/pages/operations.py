"""Ops reports + holidays."""

from __future__ import annotations

from nicegui import ui

from gui import session
from gui.clock import today_local
from gui.shell import layout, page_header, panel
from logic import (
    backup_database,
    create_extra_duty_event,
    export_duty_roster_for_cad,
    export_extra_duty_invoice_csv,
    export_requests_pdf,
    export_roster_csv,
    export_schedule_pdf,
    get_coverage_gap_board,
    get_coverage_report,
    get_dashboard_insights,
    get_equitable_ot_ledger,
    get_holidays,
    get_holidays_in_range,
    get_hours_watch,
    get_labor_budget_status,
    list_extra_duty_events,
    maybe_run_auto_backup,
    post_cad_webhook,
)
from logic.cad_rms_bridge import (
    cad_bidirectional_roundtrip_smoke,
    cad_bridge_status,
    get_cad_bridge_config,
    import_cad_duty_bidirectional,
    pull_cad_from_url,
    save_cad_bridge_config,
)
from logic.product_complete_pack import (
    get_court_min_hours,
    get_default_ot_election,
    get_holdover_reason_codes,
    import_cad_rms_duty_json,
    save_holdover_reason_codes,
    set_court_min_hours,
    set_default_ot_election,
)
from validators import format_date


def render_operations() -> None:
    def body() -> None:
        if not session.can("reports.view"):
            page_header("Ops Reports", "Permission Required", kicker="Command")
            ui.html(
                '<div class="alert alert-warn">Ops Reports Require Supervisor Access.</div>',
                sanitize=False,
            )
            return

        page_header("Ops Reports", "Coverage · OT equity · labor budget · calendar", kicker="Chronos Command")
        # Prefer fast KPIs for first paint; expand heavy analytics only on demand
        from logic import get_dashboard_kpis_fast

        insights = get_dashboard_kpis_fast() or {}
        if not isinstance(insights, dict):
            insights = {}

        # Equitable OT ledger first (supervisor daily default)
        with panel("Equitable OT ledger", glow=True):
            try:
                ledger = get_equitable_ot_ledger() or {}
            except TypeError:
                ledger = get_equitable_ot_ledger(today_local()) or {}  # type: ignore[call-arg]
            except Exception as exc:
                ledger = {"success": False, "message": str(exc)}
            rows = ledger.get("rows") or ledger.get("officers") or ledger.get("ledger") or ledger.get("items") or []
            if isinstance(ledger, list):
                rows = ledger
            ui.label(ledger.get("message") or f"{len(rows) if isinstance(rows, list) else 0} officer rows").classes(
                "text-xs q-mb-sm"
            ).style("color: var(--dim)")
            # AG Grid when available
            if isinstance(rows, list) and rows and all(isinstance(r, dict) for r in rows[:3]):
                cols = [
                    {"headerName": k, "field": k, "filter": True, "sortable": True} for k in list(rows[0].keys())[:8]
                ]
                try:
                    ui.aggrid(
                        {
                            "columnDefs": cols,
                            "rowData": rows[:80],
                            "defaultColDef": {"resizable": True, "floatingFilter": True},
                        }
                    ).classes("w-full").style("height:280px")
                except Exception:
                    for r in rows[:15]:
                        ui.label(
                            f"{r.get('officer_name') or r.get('name') or r.get('officer_id')} · "
                            f"OT {r.get('ot_hours') or r.get('hours') or r.get('total') or '—'}"
                        ).classes("text-xs")
            elif isinstance(rows, list):
                for r in rows[:15]:
                    ui.label(str(r)[:120]).classes("text-xs")
            else:
                ui.label("No OT equity rows yet.").classes("text-xs text-gray-500")

        try:
            budget = get_labor_budget_status() or {}
        except Exception as exc:
            budget = {"success": False, "message": str(exc)}
        if budget.get("success") is not False or budget.get("projected_annual") is not None:
            with panel("Labor budget (year)", glow=False):
                configured = budget.get("configured")
                proj = budget.get("projected_annual") or budget.get("projected") or "—"
                spent = budget.get("spent") or budget.get("ytd") or budget.get("actual")
                ui.label(
                    f"Projected annual labor: {proj}"
                    + (f" · YTD/spent: {spent}" if spent is not None else "")
                    + ("" if configured else " · budget not configured (showing projection only)")
                ).classes("text-sm")
                if budget.get("message"):
                    ui.label(str(budget["message"])).classes("text-xs text-gray-500")

        with panel("CBA knobs · court min · holdover codes · OT election"):
            court_h = ui.input(label="Court appearance min hours", value=str(get_court_min_hours())).classes("w-full")
            codes = get_holdover_reason_codes()
            code_box = (
                ui.textarea(
                    value="\n".join(codes),
                    label="Holdover reason codes (one per line)",
                )
                .classes("w-full")
                .props("outlined dense dark rows=6")
            )
            ot_def = (
                ui.select(
                    {"cash": "Cash OT default", "comp": "Comp bank default"},
                    value=get_default_ot_election(),
                    label="Default OT election",
                )
                .classes("w-full")
                .props("dark dense emit-value map-options")
            )

            def save_cba():
                uid = (session.current_user() or {}).get("id")
                try:
                    set_court_min_hours(float(court_h.value or 2), user_id=uid)
                except ValueError:
                    pass
                lines = [ln.strip() for ln in (code_box.value or "").splitlines() if ln.strip()]
                save_holdover_reason_codes(lines, user_id=uid)
                set_default_ot_election(ot_def.value or "cash", user_id=uid)
                ui.notify("CBA knobs saved", type="positive")

            ui.button("Save CBA knobs", on_click=save_cba).classes("btn-primary").props("no-caps unelevated dense")

        with panel("CAD / RMS bidirectional bridge", glow=True):
            st = cad_bridge_status()
            cfg = get_cad_bridge_config()
            ui.label(st.get("message") or "").classes("text-xs q-mb-sm").style("color: var(--dim)")
            ui.label(
                f"Recent audits: {', '.join(st.get('recent_audits') or []) or 'none'} · "
                f"POST /api/cad/inbound · GET pull URL"
            ).classes("text-xs q-mb-sm").style("color: var(--muted)")
            pull_url = ui.input("CAD pull URL (GET JSON)", value=cfg.get("pull_url") or "").classes("w-full")
            inbound_tok = ui.input(
                "Inbound token (optional X-Chronos-CAD-Token)",
                value="",
                password=True,
            ).classes("w-full")
            apply_on = ui.switch(
                "Apply cover pairs on import (original + replacement IDs)",
                value=bool(cfg.get("apply_on_import")),
            )

            def save_cad_cfg():
                uid = (session.current_user() or {}).get("id")
                r = save_cad_bridge_config(
                    pull_url=pull_url.value or "",
                    inbound_token=inbound_tok.value or "",
                    apply_on_import=bool(apply_on.value),
                    user_id=uid,
                )
                ui.notify(r.get("message", "Saved"), type="positive" if r.get("success") else "negative")

            def do_cad_export():
                r = export_duty_roster_for_cad(days=1)
                ui.notify(r.get("message", "Exported"), type="positive" if r.get("success") else "negative")

            def _vendor_export(vendor: str):
                """Export duty roster reshaped for Mark43 / Tyler consumers."""
                from pathlib import Path

                from logic.cad_vendors import export_duty_for_vendor
                from paths import data_path

                exp = export_duty_roster_for_cad(days=1)
                if not exp.get("success"):
                    ui.notify(exp.get("message", "CAD export failed"), type="negative")
                    return
                rows = []
                jp = exp.get("json_path") or exp.get("path")
                if jp and Path(jp).is_file():
                    import json

                    try:
                        payload = json.loads(Path(jp).read_text(encoding="utf-8"))
                        rows = payload.get("rows") or payload.get("duty") or []
                    except Exception:
                        rows = []
                if not rows and isinstance(exp.get("rows"), list):
                    rows = exp["rows"]
                shaped = export_duty_for_vendor(rows or [], vendor=vendor)
                out_dir = Path(data_path("exports"))
                out_dir.mkdir(parents=True, exist_ok=True)
                from datetime import datetime

                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                out = out_dir / f"cad_{vendor}_{stamp}.json"
                import json

                out.write_text(json.dumps(shaped, indent=2, default=str), encoding="utf-8")
                ui.notify(f"{vendor} export → {out} · rows={shaped.get('row_count', 0)}", type="positive")

            def do_cad_hook():
                r = post_cad_webhook()
                ui.notify(r.get("message", "Webhook"), type="info")

            def do_cad_import_dry():
                from pathlib import Path

                from paths import data_path

                exp_dir = Path(data_path("exports"))
                files = sorted(exp_dir.glob("cad_duty_roster_*.json"), reverse=True) if exp_dir.is_dir() else []
                if not files:
                    r = export_duty_roster_for_cad(days=1)
                    if r.get("json_path"):
                        files = [Path(r["json_path"])]
                if not files:
                    ui.notify("No CAD export to validate", type="warning")
                    return
                r = import_cad_duty_bidirectional(files[0], dry_run=True)
                ui.notify(r.get("message", "Validated"), type="positive" if r.get("success") else "negative")

            def do_cad_import_store():
                from pathlib import Path

                from paths import data_path

                uid = (session.current_user() or {}).get("id")
                exp_dir = Path(data_path("exports"))
                files = sorted(exp_dir.glob("cad_duty_roster_*.json"), reverse=True) if exp_dir.is_dir() else []
                if not files:
                    ui.notify("Export first", type="warning")
                    return
                r = import_cad_duty_bidirectional(files[0], dry_run=False, user_id=uid)
                ui.notify(r.get("message", "Imported"), type="positive" if r.get("success") else "negative")

            def do_cad_pull():
                uid = (session.current_user() or {}).get("id")
                r = pull_cad_from_url(pull_url.value or None, dry_run=False, user_id=uid)
                ui.notify(r.get("message", "Pull"), type="positive" if r.get("success") else "warning")

            def do_cad_roundtrip():
                uid = (session.current_user() or {}).get("id")
                r = cad_bidirectional_roundtrip_smoke(user_id=uid)
                ui.notify(r.get("message", "Roundtrip"), type="positive" if r.get("success") else "negative")

            with ui.row().classes("gap-2 flex-wrap"):
                ui.button("Save CAD bridge", on_click=save_cad_cfg).classes("btn-primary").props(
                    "no-caps unelevated dense"
                )
                ui.button("Export duty for CAD", on_click=do_cad_export).classes("btn-ghost").props(
                    "no-caps outline dense"
                )
                ui.button("Export Mark43 shape", on_click=lambda: _vendor_export("mark43")).classes("btn-ghost").props(
                    "no-caps outline dense"
                )
                ui.button("Export Tyler shape", on_click=lambda: _vendor_export("tyler")).classes("btn-ghost").props(
                    "no-caps outline dense"
                )
                ui.button("POST CAD webhook", on_click=do_cad_hook).classes("btn-ghost").props("no-caps outline dense")
                ui.button("Dry import last export", on_click=do_cad_import_dry).classes("btn-ghost").props(
                    "no-caps outline dense"
                )
                ui.button("Store import (apply if enabled)", on_click=do_cad_import_store).classes("btn-ghost").props(
                    "no-caps outline dense"
                )
                ui.button("Pull from CAD URL", on_click=do_cad_pull).classes("btn-ghost").props("no-caps outline dense")
                ui.button("Roundtrip smoke", on_click=do_cad_roundtrip).classes("btn-ghost").props(
                    "no-caps outline dense"
                )
            # keep product pack helper referenced for parity
            _ = import_cad_rms_duty_json

        with panel("Exports (wall roster / schedule PDF)"):
            with ui.row().classes("gap-2 flex-wrap"):

                def do_roster():
                    r = export_roster_csv()
                    ok = bool(r.get("success"))
                    ui.notify(
                        (r.get("message") or r.get("path") or "Roster CSV exported")
                        if ok
                        else r.get("message", "Failed"),
                        type="positive" if ok else "negative",
                    )

                def do_pdf():
                    r = export_schedule_pdf(today, today)
                    ok = bool(r.get("success"))
                    ui.notify(
                        (r.get("message") or r.get("path") or "Schedule PDF exported")
                        if ok
                        else r.get("message", "Failed"),
                        type="positive" if ok else "negative",
                    )

                def do_req_pdf():
                    r = export_requests_pdf(status_filter="Pending")
                    ok = bool(r.get("success"))
                    path = r.get("path") or r.get("output_path") or r.get("file")
                    ui.notify(
                        (r.get("message") or (f"Requests PDF: {path}" if path else "Requests PDF ready"))
                        if ok
                        else r.get("message", "Failed"),
                        type="positive" if ok else "negative",
                    )

                ui.button("Export roster CSV", on_click=do_roster).classes("btn-ghost").props("no-caps outline dense")
                ui.button("Export today schedule PDF", on_click=do_pdf).classes("btn-ghost").props(
                    "no-caps outline dense"
                )
                ui.button("Export pending leave PDF", on_click=do_req_pdf).classes("btn-ghost").props(
                    "no-caps outline dense"
                )

                def do_cov():
                    try:
                        from logic.exports import export_coverage_pdf

                        r = export_coverage_pdf(today, today)
                    except Exception as exc:
                        r = {"success": False, "message": str(exc)}
                    ok = bool(r.get("success"))
                    ui.notify(
                        r.get("message") or r.get("path") or "Coverage PDF",
                        type="positive" if ok else "negative",
                    )

                def do_diff():
                    try:
                        from logic import export_schedule_diff_csv

                        r = export_schedule_diff_csv(today.year, today.month)
                    except Exception as exc:
                        r = {"success": False, "message": str(exc)}
                    ok = bool(r.get("success")) if isinstance(r, dict) else bool(r)
                    ui.notify(
                        (r.get("message") if isinstance(r, dict) else None) or "Diff CSV",
                        type="positive" if ok else "negative",
                    )

                def do_full_insights():
                    try:
                        ins = get_dashboard_insights() or {}
                        ui.notify(
                            f"Insights loaded · pending={ins.get('pending_requests')} gaps={ins.get('coverage_gap_count')}",
                            type="info",
                        )
                    except Exception as exc:
                        ui.notify(str(exc), type="negative")

                ui.button("Coverage PDF", on_click=do_cov).classes("btn-ghost").props("no-caps outline dense")
                ui.button("Schedule diff CSV", on_click=do_diff).classes("btn-ghost").props("no-caps outline dense")
                ui.button("Load full dashboard insights", on_click=do_full_insights).classes("btn-ghost").props(
                    "no-caps outline dense"
                )
                ui.button("Open exports hub", on_click=lambda: ui.navigate.to("/exports")).classes("btn-primary").props(
                    "no-caps unelevated dense"
                )

        # TeleStaff-style extra duty / special detail (evaluated from UKG + Netchex)
        if session.can("open_shifts.manage") or session.can("schedule.updated.edit"):
            with panel("Extra duty / special detail", glow=True):
                ui.label(
                    "Industry (TeleStaff/Netchex): plan off-duty events, staff via open vacancy, "
                    "track billing code for payroll export. Not full invoicing."
                ).classes("text-xs text-gray-500 q-mb-sm")
                ename = ui.input(label="Event name", value="Parade detail").classes("w-full")
                edate = ui.input(
                    label="Date",
                    value=format_date(today_local()),
                    placeholder="M/D/YY or M-D-YYYY",
                ).classes("w-full")
                estart = ui.input(label="Start", value="18:00").classes("w-full")
                eend = ui.input(label="End", value="23:00").classes("w-full")
                eloc = ui.input(label="Location", value="").classes("w-full")
                ebill = ui.input(label="Billing code", value="").classes("w-full")
                esquad = ui.select(["", "A", "B"], value="", label="Squad (optional)").classes("w-full")

                def post_extra():
                    uid = (session.current_user() or {}).get("id")
                    r = create_extra_duty_event(
                        (edate.value or "").strip(),
                        (estart.value or "").strip(),
                        (eend.value or "").strip(),
                        event_name=(ename.value or "Extra duty").strip(),
                        location=(eloc.value or "").strip(),
                        billing_code=(ebill.value or "").strip(),
                        squad=(esquad.value or None) or None,
                        user_id=uid,
                    )
                    ui.notify(
                        r.get("message", "Posted") if r.get("success") else r.get("message", "Failed"),
                        type="positive" if r.get("success") else "negative",
                    )

                ui.button("Post extra duty vacancy", on_click=post_extra).classes("btn-primary q-mt-sm").props(
                    "no-caps unelevated dense"
                )
                try:
                    listed = list_extra_duty_events(status="open", limit=12) or {}
                    events = listed.get("events") or []
                except Exception as exc:
                    events = []
                    ui.label(str(exc)).classes("text-xs text-red-400")
                if events:
                    ui.label(f"Open extra duty · {len(events)}").classes("text-xs text-gray-500 q-mt-sm")
                    for ev in events[:8]:
                        ui.label(
                            f"{ev.get('date_display') or ev.get('shift_date')} · "
                            f"{ev.get('event_name')} · {ev.get('shift_start')}–{ev.get('shift_end')} · "
                            f"{ev.get('location') or ''}"
                        ).classes("text-sm")
                else:
                    ui.label("No open extra-duty vacancies tagged yet.").classes("text-xs text-gray-500 q-mt-sm")

                def do_invoice():
                    r = export_extra_duty_invoice_csv(status="all")
                    if r.get("success"):
                        ui.notify(r.get("message") or f"Wrote {r.get('path')}", type="positive")
                    else:
                        ui.notify(r.get("message") or "Export failed", type="negative")

                ui.button("Export extra-duty invoice CSV", on_click=do_invoice).classes("btn-ghost q-mt-sm").props(
                    "no-caps outline dense"
                )

        heavy_host = ui.element("div")

        def load_full():
            heavy_host.clear()
            with heavy_host:
                ui.label("Loading Full Analytics…").classes("text-sm")
            try:
                full = get_dashboard_insights() or {}
            except Exception as exc:
                with heavy_host:
                    ui.html(
                        f'<div class="alert alert-crit">Analytics Failed: {exc}</div>',
                        sanitize=False,
                    )
                return
            with heavy_host:
                if not isinstance(full, dict):
                    full = {}
                ui.html(
                    f"""
                    <div class="kpi-row q-mb-md">
                      <div class="kpi"><div class="kpi-l">Coverage Gaps (Full)</div>
                      <div class="kpi-v">{full.get("coverage_gap_count", 0)}</div></div>
                      <div class="kpi"><div class="kpi-l">Overtime Alerts</div>
                      <div class="kpi-v">{full.get("overtime_alerts", 0)}</div></div>
                      <div class="kpi"><div class="kpi-l">Hours Watch</div>
                      <div class="kpi-v">{full.get("hours_watch_count", 0)}</div></div>
                      <div class="kpi"><div class="kpi-l">Labor Issues</div>
                      <div class="kpi-v">{full.get("labor_compliance_count", 0)}</div></div>
                    </div>
                    """,
                    sanitize=False,
                )

        ui.button("Load Full Labor & Coverage Analytics", on_click=load_full).classes("btn-ghost q-mb-md").props(
            "no-caps outline dense"
        )

        ui.html(
            f"""
            <div class="kpi-row q-mb-md">
              <div class="kpi warn"><div class="kpi-l">Pending Leave</div><div class="kpi-v">{insights.get("pending_requests", 0)}</div></div>
              <div class="kpi"><div class="kpi-l">Pending Swaps</div><div class="kpi-v">{insights.get("pending_swaps", 0)}</div></div>
              <div class="kpi danger"><div class="kpi-l">Coverage Gaps</div><div class="kpi-v">{insights.get("coverage_gap_count", 0)}</div></div>
              <div class="kpi danger"><div class="kpi-l">Night Issues</div><div class="kpi-v">{insights.get("coverage_issues", 0)}</div></div>
            </div>
            """,
            sanitize=False,
        )

        today = today_local()
        report = get_coverage_report(today, today) if callable(get_coverage_report) else {}
        if not isinstance(report, dict):
            report = {}

        with panel("Coverage Snapshot · Today"):
            start_d = report.get("start_date") or format_date(today)
            end_d = report.get("end_date") or format_date(today)
            # Analytics may already return display-formatted dates; normalize via format_date
            ui.label(f"Range {format_date(start_d)} – {format_date(end_d)}").classes("text-sm q-mb-sm").style(
                "color: var(--muted)"
            )
            text = report.get("message") or report.get("summary") or ""
            if text:
                ui.label(str(text)).classes("text-sm text-gray-300")
            days = report.get("days") or []
            if days:
                for day in days[:14]:
                    if not isinstance(day, dict):
                        continue
                    d_disp = format_date(day.get("date") or today)
                    squad = day.get("squad_on_duty") or "—"
                    shifts = day.get("shift_counts") or {}
                    shift_txt = " · ".join(f"{k}×{v}" for k, v in list(shifts.items())[:6]) or "—"
                    with ui.element("div").classes("data-row"):
                        ui.label(f"{d_disp} · Squad {squad} · {shift_txt}").classes("text-sm")
            elif not text:
                ui.label("Coverage Data Loaded.").classes("text-sm").style("color: var(--muted)")

        with ui.element("div").classes("grid-2"):
            with panel("Coverage gap board (48h)", glow=True):
                try:
                    board = get_coverage_gap_board(48) or {}
                except Exception as exc:
                    board = {"gaps": [], "message": str(exc)}
                ui.label(f"Count {board.get('gap_count', 0)} · critical {board.get('critical_count', 0)}").classes(
                    "text-xs text-gray-500 q-mb-sm"
                )
                for g in (board.get("gaps") or [])[:20]:
                    if not isinstance(g, dict):
                        continue
                    raw = g.get("date") or ""
                    band = g.get("shift_start") or g.get("band") or "—"
                    ui.label(
                        f"{format_date(raw) if raw else '—'} · {band} · "
                        f"{g.get('shortfall') or g.get('severity') or g.get('message') or ''}"
                    ).classes("text-sm")
                if not board.get("gaps"):
                    ui.html('<div class="alert alert-ok">No gaps in window.</div>', sanitize=False)

            with panel("FLSA / hours watch"):
                try:
                    watch = get_hours_watch() or {}
                except Exception as exc:
                    watch = {"warnings": [], "message": str(exc)}
                ui.label(
                    f"Period {format_date(watch.get('period_start'))} – "
                    f"{format_date(watch.get('period_end'))} · "
                    f"threshold {watch.get('period_threshold', '—')}h"
                ).classes("text-xs text-gray-500 q-mb-sm")
                warns = watch.get("warnings") or []
                if not warns:
                    ui.html('<div class="alert alert-ok">No hours-threshold warnings.</div>', sanitize=False)
                for w in warns[:25]:
                    if isinstance(w, dict):
                        ui.label(
                            f"{w.get('officer_name') or w.get('name') or 'Officer'} · "
                            f"{w.get('hours', w.get('period_hours', '—'))}h · "
                            f"{w.get('message') or w.get('level') or ''}"
                        ).classes("text-sm")
                    else:
                        ui.label(str(w)).classes("text-sm")

        with panel("Equitable OT ledger (period)", glow=True):
            try:
                ot = get_equitable_ot_ledger() or {}
            except Exception as exc:
                ot = {"ledger": [], "message": str(exc)}
            ui.label(
                f"Dept OT total {ot.get('department_ot_total', 0)}h · "
                f"avg {ot.get('department_ot_avg', 0)}h · officers {ot.get('officer_count', 0)}"
            ).classes("text-xs text-gray-500 q-mb-sm")
            ledger = ot.get("ledger") or []
            if not ledger:
                ui.html(
                    '<div class="alert alert-ok">No OT ledger rows this period.</div>',
                    sanitize=False,
                )
            else:
                try:
                    from gui.tables import aggrid_from_dicts

                    rows = [
                        {
                            "name": r.get("officer_name") or r.get("name"),
                            "squad": r.get("squad"),
                            "ot_hours": r.get("ot_hours"),
                            "hours_offered": r.get("hours_offered"),
                            "opportunity_gap": r.get("opportunity_gap"),
                            "vs_avg": r.get("vs_avg"),
                            "fairness": r.get("fairness"),
                        }
                        for r in ledger
                        if isinstance(r, dict)
                    ]
                    if ot.get("dual_ledger"):
                        ui.label(
                            "Dual ledger (CrewSense): hours_offered ≈ fill/callback opportunities · "
                            "ot_hours = worked OT load"
                        ).classes("text-xs text-gray-500 q-mb-xs")
                    aggrid_from_dicts(
                        rows,
                        prefer_columns=[
                            "name",
                            "squad",
                            "ot_hours",
                            "hours_offered",
                            "opportunity_gap",
                            "vs_avg",
                            "fairness",
                        ],
                        height="320px",
                        csv_export=True,
                        csv_name="ot_equity_dual_ledger",
                    )
                except Exception:
                    for r in ledger[:40]:
                        if not isinstance(r, dict):
                            continue
                        ui.label(
                            f"{r.get('officer_name')} · squad {r.get('squad')} · "
                            f"OT {r.get('ot_hours')}h · {r.get('fairness')}"
                        ).classes("text-sm")

        with panel("Holidays / Blackout (12 Months)"):
            end = today.replace(year=today.year + 1)
            try:
                holidays = get_holidays_in_range(today, end)
            except Exception:
                holidays = []
            if not holidays:
                # Fallback: full year catalog
                try:
                    holidays = get_holidays(today.year) or []
                except Exception:
                    holidays = []
            if isinstance(holidays, dict):
                holidays = holidays.get("holidays") or holidays.get("rows") or []
            if not holidays:
                ui.html(
                    '<div class="alert alert-ok">No Holidays Configured In Range.</div>',
                    sanitize=False,
                )
            else:
                for h in holidays[:40]:
                    if isinstance(h, dict):
                        raw = h.get("date") or h.get("holiday_date") or ""
                        line = (
                            f"{h.get('name') or h.get('holiday_name') or 'Holiday'} · "
                            f"{format_date(raw) if raw else '—'}"
                        )
                    else:
                        line = str(h)
                    with ui.element("div").classes("data-row"):
                        ui.label(line).classes("text-sm")

        if session.can("admin.settings") or session.can("settings.manage") or session.can("schedule.manage"):
            with panel("Bump · off-duty call-in"):
                from logic import (
                    get_bump_call_list,
                    get_next_call_list_officer,
                    get_off_duty_bump_settings_for_ui,
                    get_ot_fill_modes_for_ui,
                    get_ot_fill_year_leaderboard,
                    import_bump_call_list_file,
                    import_bump_call_list_text,
                    reset_call_list_cursor,
                    save_off_duty_bump_policy,
                    set_ot_fill_mode,
                )

                od = get_off_duty_bump_settings_for_ui()
                pol = od.get("policy") or {}
                fill_ui = get_ot_fill_modes_for_ui()
                fill_opts = {o["id"]: o["label"] for o in (fill_ui.get("options") or [])}
                fill_mode_sel = ui.select(
                    fill_opts,
                    value=fill_ui.get("mode") or list(fill_opts.keys())[0],
                    label="Day-off OT / fill offer order mode",
                ).classes("w-full")

                def save_fill_mode():
                    r = set_ot_fill_mode(
                        fill_mode_sel.value,
                        user_id=(session.current_user() or {}).get("id"),
                    )
                    ui.notify(
                        r.get("message", "Saved") if r.get("success") else r.get("message", "Fail"),
                        type="positive" if r.get("success") else "negative",
                    )

                ui.button("Save fill mode", on_click=save_fill_mode).classes("btn-ghost").props("no-caps outline dense")
                allow_od = ui.checkbox(
                    "Allow off-duty officers in bump / call-in logic",
                    value=bool(pol.get("allow_off_duty")),
                )
                prefer_on = ui.checkbox(
                    "Prefer on-duty officers first (recommended)",
                    value=bool(pol.get("prefer_on_duty_first", True)),
                )
                same_sq = ui.checkbox(
                    "Off-duty: same squad only",
                    value=bool(pol.get("same_squad_only", True)),
                )
                adj_band = ui.checkbox(
                    "Off-duty: require adjacent shift band",
                    value=bool(pol.get("require_adjacent_band", False)),
                )
                min_off = ui.input(
                    label="Minimum consecutive days off (hard filter when criterion on)",
                    value=str(pol.get("min_days_off_required") or 0),
                ).classes("w-full")
                ui.label("Ranking criteria (select any combination):").classes("text-sm text-gray-300 q-mt-sm")
                crit_checks = {}
                selected = set(pol.get("criteria") or [])
                for opt in od.get("criteria_options") or []:
                    crit_checks[opt["id"]] = ui.checkbox(
                        opt.get("label") or opt["id"],
                        value=opt["id"] in selected or bool(opt.get("selected")),
                    )

                def save_od_policy():
                    try:
                        mdo = int((min_off.value or "0").strip() or "0")
                    except ValueError:
                        ui.notify("Min days off must be a number", type="negative")
                        return
                    crits = [cid for cid, box in crit_checks.items() if box.value]
                    r = save_off_duty_bump_policy(
                        {
                            "allow_off_duty": bool(allow_od.value),
                            "prefer_on_duty_first": bool(prefer_on.value),
                            "same_squad_only": bool(same_sq.value),
                            "require_adjacent_band": bool(adj_band.value),
                            "min_days_off_required": mdo,
                            "criteria": crits,
                        },
                        user_id=(session.current_user() or {}).get("id"),
                    )
                    ui.notify(
                        r.get("message", "Saved") if r.get("success") else r.get("message", "Fail"),
                        type="positive" if r.get("success") else "negative",
                    )

                ui.button("Save off-duty bump settings", on_click=save_od_policy).classes("btn-primary").props(
                    "no-caps unelevated dense"
                )

                ui.label("Rotating call list (order = call order; paste names or IDs):").classes(
                    "text-sm text-gray-300 q-mt-md"
                )
                existing = get_bump_call_list()
                default_text = "\n".join(f"{e.get('officer_id')}  # {e.get('name') or ''}".strip() for e in existing)
                call_text = (
                    ui.textarea(value=default_text, label="Call list")
                    .classes("w-full")
                    .props("outlined dense dark rows=8")
                )
                next_off = get_next_call_list_officer()
                next_label = (
                    f"Next up: {next_off.get('name') or next_off.get('officer_id')} (index {od.get('call_list_cursor', 0)})"
                    if next_off
                    else f"Cursor index: {od.get('call_list_cursor', 0)} (list empty)"
                )
                cursor_lbl = ui.label(next_label).classes("text-xs text-gray-500")

                def _refresh_cursor_label():
                    n = get_next_call_list_officer()
                    if n:
                        cursor_lbl.set_text(
                            f"Next up: {n.get('name') or n.get('officer_id')} (index {n.get('order', 0)})"
                        )
                    else:
                        cursor_lbl.set_text("Call list empty")

                def save_call_list():
                    r = import_bump_call_list_text(
                        call_text.value or "",
                        user_id=(session.current_user() or {}).get("id"),
                    )
                    ui.notify(
                        r.get("message", "Saved") if r.get("success") else r.get("message", "Fail"),
                        type="positive" if r.get("success") else "negative",
                    )
                    if r.get("success"):
                        _refresh_cursor_label()

                def reset_cursor():
                    r = reset_call_list_cursor(user_id=(session.current_user() or {}).get("id"))
                    ui.notify(r.get("message", "Reset"), type="positive" if r.get("success") else "negative")
                    _refresh_cursor_label()

                def upload_call_list(e):
                    """txt/csv/docx/pdf via shared importer (no server crash on bad files)."""
                    try:
                        name = getattr(e, "name", None) or getattr(e, "file_name", None) or "upload.txt"
                        raw = None
                        if hasattr(e, "content"):
                            try:
                                e.content.seek(0)
                            except Exception:
                                pass
                            raw = e.content.read()
                        if raw is None and hasattr(e, "file"):
                            raw = e.file.read()
                        if raw is None:
                            ui.notify("Could not read upload", type="negative")
                            return
                        if isinstance(raw, str):
                            raw = raw.encode("utf-8")
                        r = import_bump_call_list_file(
                            str(name),
                            raw,
                            user_id=(session.current_user() or {}).get("id"),
                        )
                        if r.get("success") and r.get("extracted_preview"):
                            call_text.value = r["extracted_preview"]
                        ui.notify(
                            r.get("message", "Imported") if r.get("success") else r.get("message", "Fail"),
                            type="positive" if r.get("success") else "negative",
                        )
                        if r.get("success"):
                            _refresh_cursor_label()
                    except Exception as exc:
                        ui.notify(f"Upload failed: {exc}", type="negative")

                with ui.row().classes("gap-2 flex-wrap"):
                    ui.button("Save call list", on_click=save_call_list).classes("btn-ghost").props(
                        "no-caps outline dense"
                    )
                    ui.button("Reset next-up to top", on_click=reset_cursor).classes("btn-ghost").props(
                        "no-caps outline dense"
                    )
                    ui.upload(
                        label="Upload call list (.txt/.csv/.docx/.pdf)",
                        on_upload=upload_call_list,
                        auto_upload=True,
                    ).props("accept=.txt,.csv,.list,.docx,.pdf dense")

                ui.label("Year-to-date ordered-in / turned-down (top)").classes("text-sm text-gray-300 q-mt-md")
                board = get_ot_fill_year_leaderboard() or {}
                rows = board.get("rows") or []
                if not rows:
                    ui.label("No OT fill events recorded this year yet.").classes("text-xs text-gray-500")
                else:
                    for row in rows[:15]:
                        ui.label(
                            f"{row.get('name')} · ordered {row.get('ordered_in', 0)} · "
                            f"turned down {row.get('turned_down', 0)} · volunteered {row.get('volunteered', 0)}"
                        ).classes("text-sm")

            with panel("Additional min coverage windows + 24/7 floor"):
                from logic import (
                    add_coverage_window,
                    delete_coverage_window,
                    get_coverage_247_minimum,
                    list_coverage_windows,
                    set_coverage_247_minimum,
                )

                cov247_in = ui.input(
                    label="24/7 minimum officers (0=off)",
                    value=str(get_coverage_247_minimum()),
                ).classes("w-full")
                win_list = ui.column().classes("w-full gap-1")

                def refresh_windows():
                    win_list.clear()
                    with win_list:
                        rows = list_coverage_windows()
                        if not rows:
                            ui.label("No extra windows configured.").classes("text-sm text-gray-500")
                        for w in rows:
                            label = w.get("label") or f"{w.get('start_time')}–{w.get('end_time')}"
                            if w.get("specific_date"):
                                when = format_date(w.get("specific_date"))
                            elif w.get("weekday") is not None:
                                when = f"weekday {w.get('weekday')}"
                            else:
                                when = "any day"
                            with ui.row().classes("items-center gap-2"):
                                ui.label(f"#{w.get('id')} · min {w.get('min_officers')} · {label} · {when}").classes(
                                    "text-sm"
                                )
                                wid = int(w.get("id") or 0)

                                def _del(i=wid):
                                    r = delete_coverage_window(i, user_id=(session.current_user() or {}).get("id"))
                                    ui.notify(
                                        r.get("message", "Deleted"), type="positive" if r.get("success") else "negative"
                                    )
                                    refresh_windows()

                                ui.button("Delete", on_click=_del).props("btn-ghost").props("dense no-caps outline")

                refresh_windows()
                w_min = ui.input(label="Min officers", value="2").classes("w-full")
                w_start = ui.input(label="Start HH:MM", value="19:00").classes("w-full")
                w_end = ui.input(label="End HH:MM", value="03:00").classes("w-full")
                w_dow = ui.input(label="Weekday 0=Mon…6=Sun (blank=any)", value="4").classes("w-full")
                w_date = ui.input(label="Or specific date (M/D/YY)", value="", placeholder="7/9/26").classes("w-full")
                w_label = ui.input(label="Label", value="Fri night boost").classes("w-full")

                def save_247():
                    try:
                        n = int((cov247_in.value or "0").strip())
                    except ValueError:
                        ui.notify("Invalid 24/7 minimum", type="negative")
                        return
                    r = set_coverage_247_minimum(n, user_id=(session.current_user() or {}).get("id"))
                    ui.notify(
                        r.get("message", "Saved") if r.get("success") else r.get("message", "Fail"),
                        type="positive" if r.get("success") else "negative",
                    )

                def add_win():
                    try:
                        mn = int((w_min.value or "1").strip())
                    except ValueError:
                        ui.notify("Min officers must be a number", type="negative")
                        return
                    dow_raw = (w_dow.value or "").strip()
                    weekday = int(dow_raw) if dow_raw != "" else None
                    r = add_coverage_window(
                        min_officers=mn,
                        start_time=(w_start.value or "").strip(),
                        end_time=(w_end.value or "").strip(),
                        specific_date=(w_date.value or "").strip(),
                        weekday=weekday,
                        label=(w_label.value or "").strip(),
                        user_id=(session.current_user() or {}).get("id"),
                    )
                    ui.notify(
                        r.get("message", "Added") if r.get("success") else r.get("message", "Fail"),
                        type="positive" if r.get("success") else "negative",
                    )
                    if r.get("success"):
                        refresh_windows()

                with ui.row().classes("gap-2"):
                    ui.button("Save 24/7 floor", on_click=save_247).classes("btn-ghost").props("no-caps outline dense")
                    ui.button("Add window", on_click=add_win).classes("btn-primary").props("no-caps unelevated dense")

        if session.can("admin.settings") or session.can("settings.manage") or session.can("reports.view"):
            with panel("Database backup", glow=False):
                ui.label("Snapshot SQLite for DR / handoff (same as cli backup).").classes(
                    "text-xs text-gray-500 q-mb-sm"
                )

                def do_backup():
                    try:
                        path = backup_database()
                        ui.notify(f"Backup written: {path}", type="positive")
                    except Exception as exc:
                        ui.notify(str(exc), type="negative")

                def do_auto():
                    try:
                        r = maybe_run_auto_backup()
                        if isinstance(r, dict):
                            ui.notify(r.get("message") or str(r), type="info")
                        else:
                            ui.notify(str(r) if r else "Auto-backup checked", type="info")
                    except Exception as exc:
                        ui.notify(str(exc), type="negative")

                with ui.row().classes("gap-2"):
                    ui.button("Run backup now", on_click=do_backup).classes("btn-primary").props(
                        "no-caps unelevated dense"
                    )
                    ui.button("Maybe auto-backup", on_click=do_auto).classes("btn-ghost").props("no-caps outline dense")

    layout("operations", body)
