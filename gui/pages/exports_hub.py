"""Exports hub — one place for roster/schedule/payroll/coverage/audit/iCal downloads."""

from __future__ import annotations

from nicegui import ui

from gui import session
from gui.clock import today_local
from gui.shell import layout, page_header, panel
from gui.ui_patterns import empty_state
from validators import format_date


def _notify_export(r: dict, *, fallback: str = "Exported") -> None:
    ok = bool(r.get("success")) if isinstance(r, dict) else bool(r)
    path = None
    if isinstance(r, dict):
        path = r.get("path") or r.get("output_path") or r.get("file")
        msg = r.get("message") or (f"{fallback}: {path}" if path else fallback)
    else:
        msg = str(r) if r else "Failed"
    ui.notify(msg if ok else (msg or "Export failed"), type="positive" if ok else "negative")


def render_exports_hub() -> None:
    def body() -> None:
        page_header(
            "Exports hub",
            "CSV · PDF · iCal · audit — same paths as admin CLI",
            kicker="Command",
        )
        can_export = (
            session.can("reports.export")
            or session.can("reports.view")
            or session.can("exports.run")
            or session.can("schedule.base.view")
            or session.can("payroll.view_all")
            or session.can("officers.manage")
        )
        if not can_export and not session.linked_officer_id():
            empty_state(
                "Exports need permission",
                "Supervisors use full hub; officers can export personal iCal from My schedule.",
                cta_label="My schedule",
                cta_path="/my-schedule",
            )
            return

        today = today_local()
        y, m = today.year, today.month

        # —— Schedule & roster ——
        with panel("Schedule & roster", glow=True):
            with ui.row().classes("gap-2 flex-wrap"):
                if session.can("reports.view") or session.can("officers.manage") or session.can("reports.export"):

                    def do_roster():
                        from logic import export_roster_csv

                        _notify_export(export_roster_csv() or {}, fallback="Roster CSV")

                    def do_sched_pdf():
                        from logic import export_schedule_pdf

                        _notify_export(export_schedule_pdf(today, today) or {}, fallback="Schedule PDF")

                    def do_cov_pdf():
                        from logic.exports import export_coverage_pdf

                        try:
                            r = export_coverage_pdf(today, today)
                        except TypeError:
                            r = export_coverage_pdf()  # type: ignore[call-arg]
                        _notify_export(r if isinstance(r, dict) else {"success": bool(r), "message": str(r)})

                    def do_diff():
                        from logic import export_schedule_diff_csv

                        try:
                            r = export_schedule_diff_csv(y, m)
                        except TypeError:
                            r = export_schedule_diff_csv()  # type: ignore[call-arg]
                        _notify_export(r if isinstance(r, dict) else {"success": bool(r)})

                    ui.button("Roster CSV", on_click=do_roster).classes("btn-ghost").props("no-caps outline dense")
                    ui.button("Today schedule PDF", on_click=do_sched_pdf).classes("btn-ghost").props(
                        "no-caps outline dense"
                    )
                    ui.button("Coverage PDF", on_click=do_cov_pdf).classes("btn-ghost").props("no-caps outline dense")
                    ui.button("Schedule diff CSV", on_click=do_diff).classes("btn-ghost").props("no-caps outline dense")

                oid = session.linked_officer_id()
                if oid:

                    def do_ical():
                        from logic import export_officer_schedule_ical, get_current_cycle_window

                        start, end = get_current_cycle_window()
                        _notify_export(
                            export_officer_schedule_ical(int(oid), start_date=start, end_date=end) or {},
                            fallback="iCal",
                        )

                    ui.button("My iCal (cycle)", on_click=do_ical).classes("btn-primary").props(
                        "no-caps unelevated dense"
                    )
                else:
                    ui.label("Link an officer profile for personal iCal.").classes("text-xs").style("color: var(--dim)")

        # —— Leave & requests ——
        if session.can("requests.approve") or session.can("reports.view") or session.can("reports.export"):
            with panel("Leave & requests"):
                with ui.row().classes("gap-2 flex-wrap"):

                    def do_req_pdf():
                        from logic import export_requests_pdf

                        _notify_export(
                            export_requests_pdf(status_filter="Pending") or {},
                            fallback="Pending leave PDF",
                        )

                    def do_req_all():
                        from logic import export_requests_pdf

                        try:
                            r = export_requests_pdf(status_filter=None)
                        except TypeError:
                            r = export_requests_pdf()  # type: ignore[call-arg]
                        _notify_export(r if isinstance(r, dict) else {"success": bool(r)})

                    def do_req_csv():
                        from logic.exports import export_requests_csv

                        _notify_export(export_requests_csv(status_filter="Pending") or {}, fallback="Leave CSV")

                    def do_swap_csv():
                        from logic.exports import export_shift_swaps_csv

                        _notify_export(
                            export_shift_swaps_csv(pending_only=True) or {},
                            fallback="Swaps CSV",
                        )

                    ui.button("Pending leave PDF", on_click=do_req_pdf).classes("btn-ghost").props(
                        "no-caps outline dense"
                    )
                    ui.button("All requests PDF", on_click=do_req_all).classes("btn-ghost").props(
                        "no-caps outline dense"
                    )
                    ui.button("Leave requests CSV", on_click=do_req_csv).classes("btn-ghost").props(
                        "no-caps outline dense"
                    )
                    ui.button("Shift swaps CSV", on_click=do_swap_csv).classes("btn-ghost").props(
                        "no-caps outline dense"
                    )

        # —— Payroll ——
        if (
            session.can("payroll.view_all")
            or session.can("payroll.edit")
            or session.can("reports.export")
            or session.can("timecard.view_own")
            or session.linked_officer_id()
        ):
            with panel("Payroll · timecard · pay stub"):
                with ui.row().classes("gap-2 flex-wrap"):

                    def do_pay_csv():
                        from logic.exports import export_payroll_csv

                        try:
                            r = export_payroll_csv()
                        except TypeError:
                            r = export_payroll_csv(period_start=today)  # type: ignore[call-arg]
                        _notify_export(r if isinstance(r, dict) else {"success": bool(r)})

                    def do_pay_pdf():
                        from logic.exports import export_payroll_pdf

                        try:
                            r = export_payroll_pdf()
                        except TypeError:
                            r = {"success": False, "message": "payroll PDF needs period context"}
                        _notify_export(r if isinstance(r, dict) else {"success": bool(r)})

                    def do_flsa():
                        from logic.labor_compliance import export_flsa_vs_contract_ot_csv

                        _notify_export(export_flsa_vs_contract_ot_csv() or {})

                    def do_tc_csv():
                        from logic.exports import export_timecard_csv

                        oid = session.linked_officer_id()
                        _notify_export(
                            export_timecard_csv(period_start=today, officer_id=int(oid) if oid else None) or {},
                            fallback="Timecard CSV",
                        )

                    def do_stub():
                        oid = session.linked_officer_id()
                        if not oid:
                            ui.notify("Link an officer for pay stub", type="warning")
                            return
                        from logic.exports import export_pay_stub_pdf

                        _notify_export(
                            export_pay_stub_pdf(int(oid), period_start=today) or {},
                            fallback="Pay stub PDF",
                        )

                    def do_hist():
                        from logic.exports import export_pay_period_history_csv

                        oid = session.linked_officer_id()
                        _notify_export(
                            export_pay_period_history_csv(limit=12, officer_id=int(oid) if oid else None) or {},
                            fallback="Period history CSV",
                        )

                    if session.can("payroll.view_all") or session.can("payroll.edit") or session.can("reports.export"):
                        ui.button("Payroll CSV", on_click=do_pay_csv).classes("btn-ghost").props(
                            "no-caps outline dense"
                        )
                        ui.button("Payroll PDF", on_click=do_pay_pdf).classes("btn-ghost").props(
                            "no-caps outline dense"
                        )
                        ui.button("FLSA vs contract OT", on_click=do_flsa).classes("btn-ghost").props(
                            "no-caps outline dense"
                        )
                    ui.button("Timecard CSV", on_click=do_tc_csv).classes("btn-ghost").props("no-caps outline dense")
                    ui.button("Pay stub PDF", on_click=do_stub).classes("btn-ghost").props("no-caps outline dense")
                    ui.button("Period history CSV", on_click=do_hist).classes("btn-ghost").props(
                        "no-caps outline dense"
                    )

        # —— Audit / equity / CAD ——
        if session.can("audit.view") or session.can("reports.view") or session.can("admin.settings"):
            with panel("Audit · callbacks · CAD"):
                with ui.row().classes("gap-2 flex-wrap"):

                    def do_audit():
                        from logic import export_audit_csv

                        _notify_export(export_audit_csv() or {}, fallback="Audit CSV")

                    def do_equity():
                        from logic import export_callback_equity_csv

                        _notify_export(export_callback_equity_csv() or {}, fallback="Callback equity")

                    def do_cad():
                        from logic import export_duty_roster_for_cad

                        _notify_export(export_duty_roster_for_cad(days=1) or {}, fallback="CAD duty JSON")

                    if session.can("audit.view") or session.can("users.manage"):
                        ui.button("Audit log CSV", on_click=do_audit).classes("btn-ghost").props(
                            "no-caps outline dense"
                        )
                    ui.button("Callback equity CSV", on_click=do_equity).classes("btn-ghost").props(
                        "no-caps outline dense"
                    )
                    ui.button("CAD duty export", on_click=do_cad).classes("btn-ghost").props("no-caps outline dense")

        with panel("Also available in-product", glow=False):
            ui.label(
                f"Reference date {format_date(today)}. Simulator has its own option/CSV/memo exports. "
                "Payroll page has ADP/pay-pack when configured."
            ).classes("text-xs").style("color: var(--dim)")
            with ui.row().classes("gap-2 flex-wrap q-mt-sm"):
                ui.button("Ops reports", on_click=lambda: ui.navigate.to("/operations")).classes("btn-ghost").props(
                    "no-caps outline dense"
                )
                ui.button("Payroll", on_click=lambda: ui.navigate.to("/payroll")).classes("btn-ghost").props(
                    "no-caps outline dense"
                )
                ui.button("Simulator", on_click=lambda: ui.navigate.to("/simulator")).classes("btn-ghost").props(
                    "no-caps outline dense"
                )
                ui.button("My schedule", on_click=lambda: ui.navigate.to("/my-schedule")).classes("btn-ghost").props(
                    "no-caps outline dense"
                )

    layout("exports", body)
