"""Finance NiceGUI pages — split from monolith for maintainability."""

from __future__ import annotations

from nicegui import ui

from gui import session
from gui.shell import panel
from logic import (
    calculate_pay_for_entry,
    create_payroll_entry,
    get_officer_by_id,
    get_officers_by_seniority,
    get_pay_code_rules,
    get_payroll_entries,
    get_payroll_period_timesheets,
)
from validators import format_date, parse_date


def _payroll_entries_panel(period_start) -> None:
    """Line-item payroll_entries for the period (get_payroll_entries)."""
    can_view = session.can("payroll.view_all") or session.can("payroll.view_own") or session.can("payroll.edit")
    if not can_view:
        return
    with panel("Payroll entries (ledger lines)", glow=True):
        oid_filter = None
        if session.is_officer() and not session.can("payroll.view_all"):
            oid_filter = session.linked_officer_id()
        try:
            rows = get_payroll_entries(officer_id=oid_filter, limit=80, period_start=period_start) or []
        except Exception as exc:
            ui.label(str(exc)).classes("text-sm text-red-400")
            return
        if not rows:
            ui.html(
                '<div class="alert alert-ok">No payroll entry lines for this period yet.</div>',
                sanitize=False,
            )
            return
        grid_rows = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            grid_rows.append(
                {
                    "date": r.get("entry_date"),
                    "officer": r.get("officer_name") or r.get("officer_id"),
                    "type": r.get("entry_type"),
                    "hours": r.get("hours"),
                    "pay": r.get("calculated_pay"),
                    "notes": (r.get("notes") or "")[:36],
                }
            )
        try:
            from gui.tables import aggrid_from_dicts

            if grid_rows:
                aggrid_from_dicts(
                    grid_rows,
                    prefer_columns=["date", "officer", "type", "hours", "pay", "notes"],
                    height="320px",
                    csv_export=True,
                    csv_name="payroll_entries",
                )
                return
        except Exception:
            pass
        for r in grid_rows[:40]:
            with ui.element("div").classes("data-row"):
                ui.label(
                    f"{r.get('date')} · {r.get('officer')} · {r.get('type')} · {r.get('hours')}h · ${r.get('pay')}"
                ).classes("text-sm mono")


def _payroll_entry_form(period_start) -> None:
    """Create payroll entry with calculate_pay_for_entry preview."""
    with panel("Add payroll entry", glow=True):
        officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
        names = [o["name"] for o in officers]
        omap = {o["name"]: o["id"] for o in officers}
        if not names:
            ui.html('<div class="alert alert-warn">No active officers.</div>', sanitize=False)
            return
        officer_sel = ui.select(names, value=names[0], label="Officer").classes("w-full")
        codes = [
            "Regular Hours",
            "Overtime Earned",
            "Callback",
            "Comp Earned",
            "Comp Taken",
            "Holiday Pay",
            "Holiday Overtime",
            "Sick Time Used",
            "Training",
            "Unpaid",
        ]
        try:
            rules = get_pay_code_rules() or {}
            rule_codes = rules.get("codes") or {}
            if isinstance(rule_codes, dict) and rule_codes:
                codes = list(rule_codes.keys())
        except Exception:
            pass
        d_in = ui.input(
            label="Entry date",
            value=format_date(period_start),
            placeholder="M/D/YY or M-D-YYYY",
        ).classes("w-full")
        hours = ui.input(label="Hours", value="8").classes("w-full")
        etype = ui.select(codes, value=codes[0], label="Entry type").classes("w-full")
        night = ui.input(label="Night differential hours", value="0").classes("w-full")
        notes = ui.input(label="Notes").classes("w-full")
        preview_lbl = ui.label("").classes("text-sm q-mt-sm").style("color: var(--muted)")

        def _parse_hours():
            try:
                h = float((hours.value or "0").strip())
                nd = float((night.value or "0").strip() or "0")
            except ValueError:
                return None, None
            return h, nd

        def do_preview():
            oid = omap.get(officer_sel.value)
            officer = get_officer_by_id(oid) if oid else None
            if not officer:
                preview_lbl.set_text("Select an officer")
                return
            h, nd = _parse_hours()
            if h is None or h <= 0:
                preview_lbl.set_text("Hours must be > 0")
                return
            calc = calculate_pay_for_entry(
                etype.value or codes[0],
                h,
                float(officer.get("pay_rate") or 0),
                night_differential_hours=nd or 0,
                night_differential_rate=float(officer.get("night_differential_rate") or 1.0),
            )
            if getattr(calc, "message", None):
                preview_lbl.set_text(calc.message)
                return
            preview_lbl.set_text(
                f"Preview: ${getattr(calc, 'total_pay', 0):.2f} total · "
                f"reg {getattr(calc, 'regular_hours', 0)}h · "
                f"OT {getattr(calc, 'overtime_hours', 0)}h · "
                f"comp Δ{getattr(calc, 'comp_bank_delta', 0)}"
            )

        def do_save():
            oid = omap.get(officer_sel.value)
            if not oid:
                ui.notify("Select officer", type="negative")
                return
            raw = (d_in.value or "").strip()
            try:
                dt = parse_date(raw)
            except Exception:
                dt = None
            if not dt:
                ui.notify("Invalid date", type="negative")
                return
            h, nd = _parse_hours()
            if h is None or h <= 0:
                ui.notify("Hours must be > 0", type="negative")
                return
            date_str = dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
            r = create_payroll_entry(
                oid,
                date_str,
                etype.value or codes[0],
                h,
                night_differential_hours=nd or 0,
                notes=(notes.value or "").strip(),
            )
            if r.get("success"):
                pay = r.get("calculated_pay")
                ui.notify(
                    "Entry saved" + (f" · ${pay:.2f}" if pay is not None else ""),
                    type="positive",
                )
            else:
                ui.notify(r.get("message") or "Save failed", type="negative")

        with ui.row().classes("gap-2 q-mt-sm"):
            ui.button("Preview pay", on_click=do_preview).classes("btn-ghost").props("no-caps outline dense")
            ui.button("Save payroll entry", on_click=do_save).classes("btn-primary").props("no-caps unelevated dense")


def _ledger(period_start) -> None:
    with panel("Payroll Ledger", glow=True):
        if session.is_officer() and not session.can("payroll.view_all"):
            ui.html(
                '<div class="alert alert-ok">Use Timecards For Personal Totals. Supervisors See The Full Ledger.</div>',
                sanitize=False,
            )
            return
        data = get_payroll_period_timesheets(period_start)
        rows = data.get("rows") or data.get("timesheets") or data.get("officers") or []
        if isinstance(data, dict) and data.get("success") is False:
            ui.html(
                f'<div class="alert alert-warn">{data.get("message", "Unable To Load")}</div>',
                sanitize=False,
            )
            return
        if not rows:
            ui.html(
                '<div class="alert alert-ok">No Payroll Rows For This Period.</div>',
                sanitize=False,
            )
            return
        try:
            from gui.tables import aggrid_from_dicts

            grid_rows = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                grid_rows.append(
                    {
                        "name": row.get("officer_name") or row.get("name") or row.get("officer_id"),
                        "hours": row.get("total_hours") or row.get("hours"),
                        "ot": row.get("ot_hours") or row.get("overtime"),
                        "pay": row.get("gross_pay") or row.get("total_pay"),
                        "squad": row.get("squad"),
                    }
                )
            if grid_rows:
                aggrid_from_dicts(
                    grid_rows,
                    prefer_columns=["name", "squad", "hours", "ot", "pay"],
                    height="400px",
                )
                return
        except Exception:
            pass
        for row in rows[:60]:
            if isinstance(row, dict):
                name = row.get("officer_name") or row.get("name") or f"Officer {row.get('officer_id')}"
                hours = row.get("total_hours") or row.get("hours") or "—"
                pay = row.get("gross_pay") or row.get("total_pay") or ""
                text = f"{name}  ·  {hours}h" + (f"  ·  ${pay}" if pay != "" else "")
            else:
                text = str(row)
            with ui.element("div").classes("data-row"):
                ui.label(text).classes("text-sm")
