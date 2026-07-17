"""Finance NiceGUI pages — time banks / comp / sick / float."""

from __future__ import annotations

from nicegui import ui

from config import FLSA_COMP_TIME_MAX_HOURS
from gui import session
from gui.clock import today_local
from gui.shell import finance_subnav, layout, page_header, panel
from logic import (
    get_bank_transactions,
    get_banked_time_summary,
    get_officer_time_banks,
    get_officers_by_seniority,
)
from logic.labor_compliance import export_flsa_vs_contract_ot_csv, force_use_comp_time
from validators import format_date


def _resolve_bank_officer_id() -> int | None:
    oid = session.linked_officer_id()
    if oid:
        return oid
    if not session.is_officer() and (session.can("timecard.view_all") or session.can("payroll.view_all")):
        officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
        return officers[0]["id"] if officers else None
    return None


def _banks() -> None:
    oid = _resolve_bank_officer_id()
    officer_sel = None
    omap: dict = {}
    if not session.is_officer() and (session.can("timecard.view_all") or session.can("payroll.view_all")):
        officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
        names = [o["name"] for o in officers]
        omap = {o["name"]: o["id"] for o in officers}
        if names:
            officer_sel = ui.select(names, value=names[0], label="Officer").classes("w-full q-mb-sm")
            if oid is None:
                oid = omap.get(names[0])

    host = ui.element("div")

    def refresh():
        nonlocal oid
        if officer_sel is not None and officer_sel.value:
            oid = omap.get(officer_sel.value)
        host.clear()
        with host:
            if not oid:
                ui.html('<div class="alert alert-warn">No Officer Selected.</div>', sanitize=False)
                return
            # Enterprise summary (balances + period activity)
            summary = get_banked_time_summary(oid, scope="pay_period") or {}
            if summary.get("success") is False:
                ui.html(
                    f'<div class="alert alert-warn">{summary.get("message", "No bank summary")}</div>',
                    sanitize=False,
                )
            else:
                with panel(
                    f"Banked time · {summary.get('officer_name') or oid} · "
                    f"{summary.get('scope_label') or 'pay period'}",
                    glow=True,
                ):
                    # FLSA public-safety comp cap (default 480h) — DOL Fact Sheet #8
                    banks_raw = get_officer_time_banks(oid) or {}
                    comp_bal = 0.0
                    for ck in ("comp_hours", "comp", "comp_balance", "compensatory_hours"):
                        if ck in banks_raw:
                            try:
                                comp_bal = float(banks_raw[ck] or 0)
                                break
                            except (TypeError, ValueError):
                                pass
                    if not comp_bal:
                        for b in summary.get("banks") or []:
                            if isinstance(b, dict) and str(b.get("key") or "").lower() in (
                                "comp",
                                "comp_time",
                                "compensatory",
                            ):
                                try:
                                    comp_bal = float(b.get("balance") or 0)
                                except (TypeError, ValueError):
                                    pass
                                break
                    cap = float(FLSA_COMP_TIME_MAX_HOURS or 480)
                    pct = min(100, int(100 * comp_bal / cap)) if cap else 0
                    ui.label(
                        f"FLSA public-safety comp cap · {comp_bal:.1f}h / {cap:.0f}h ({pct}%) — "
                        "at cap, additional OT must be cash (not legal advice)"
                    ).classes("text-xs text-gray-400 q-mb-xs")
                    ui.linear_progress(value=pct / 100.0).props(
                        f"color={'negative' if pct >= 95 else 'warning' if pct >= 80 else 'positive'}"
                    )

                    if (
                        not session.is_officer()
                        and (session.can("payroll.edit") or session.can("timecard.edit_all"))
                        and pct >= 80
                    ):
                        with ui.row().classes("gap-2 flex-wrap q-mt-sm q-mb-sm items-end"):
                            force_hrs = ui.input(label="Force-Use Hours", value="8").classes("w-32")
                            force_date = ui.input(
                                label="Date (M/D/YY)",
                                value=format_date(today_local()),
                            ).classes("w-40")

                            def do_force():
                                from validators import parse_date

                                dt = parse_date((force_date.value or "").strip())
                                try:
                                    h = float((force_hrs.value or "0").strip())
                                except ValueError:
                                    ui.notify("Hours must be numeric", type="negative")
                                    return
                                if not dt:
                                    ui.notify("Valid date required", type="negative")
                                    return
                                uid = (session.current_user() or {}).get("id")
                                r = force_use_comp_time(
                                    int(oid),
                                    dt.isoformat(),
                                    h,
                                    user_id=uid,
                                )
                                ui.notify(
                                    r.get("message", "Done") if r.get("success") else r.get("message", "Failed"),
                                    type="positive" if r.get("success") else "negative",
                                )
                                if r.get("success"):
                                    refresh()

                            ui.button("Force Use Comp", on_click=do_force).classes("btn-primary").props(
                                "no-caps unelevated dense"
                            )

                    if not session.is_officer() and (
                        session.can("payroll.view_all") or session.can("exports.run") or session.can("reports.export")
                    ):

                        def do_flsa_split():
                            r = export_flsa_vs_contract_ot_csv()
                            ui.notify(
                                r.get("message") or r.get("path") or "Exported"
                                if r.get("success")
                                else r.get("message", "Export failed"),
                                type="positive" if r.get("success") else "negative",
                            )

                        ui.button("Export FLSA Vs Contract OT", on_click=do_flsa_split).classes(
                            "btn-ghost q-mb-sm"
                        ).props("no-caps outline dense")

                    bank_rows = summary.get("banks") or []
                    if bank_rows:
                        for b in bank_rows:
                            if not isinstance(b, dict):
                                continue
                            with ui.element("div").classes("data-row"):
                                ui.label(
                                    f"{b.get('label') or b.get('key')}: "
                                    f"{b.get('balance', 0)}h bal · "
                                    f"+{b.get('earned', 0)} earned · "
                                    f"-{b.get('used', 0)} used"
                                ).classes("text-sm")
                    else:
                        banks = banks_raw
                        for k, v in list(banks.items())[:12]:
                            if k in ("success", "message"):
                                continue
                            with ui.element("div").classes("data-row"):
                                ui.label(f"{str(k).replace('_', ' ').title()}: {v}").classes("text-sm")

            # Transaction drill-down per bank type
            bank_types = ("comp", "sick", "float_holiday", "holiday")
            with panel("Bank transactions (this pay period)"):
                bank_pick = ui.select(
                    {k: k.replace("_", " ").title() for k in bank_types},
                    value="comp",
                    label="Bank",
                ).classes("w-full q-mb-sm")
                tx_host = ui.element("div")

                def load_tx():
                    tx_host.clear()
                    with tx_host:
                        bt = bank_pick.value or "comp"
                        tx = get_bank_transactions(oid, bt, scope="pay_period") or {}
                        if tx.get("success") is False:
                            ui.html(
                                f'<div class="alert alert-warn">{tx.get("message", "No transactions")}</div>',
                                sanitize=False,
                            )
                            return
                        rows = tx.get("transactions") or []
                        if not rows:
                            ui.html(
                                '<div class="alert alert-ok">No movements this period for this bank.</div>',
                                sanitize=False,
                            )
                            return
                        grid_rows = []
                        for r in rows[:100]:
                            if not isinstance(r, dict):
                                continue
                            grid_rows.append(
                                {
                                    "date": r.get("entry_date_display") or r.get("entry_date"),
                                    "type": r.get("entry_type"),
                                    "delta": r.get("delta"),
                                    "earned": r.get("earned"),
                                    "used": r.get("used"),
                                    "source": r.get("source"),
                                    "notes": (r.get("notes") or "")[:40],
                                }
                            )
                        try:
                            from gui.tables import aggrid_from_dicts

                            if grid_rows:
                                aggrid_from_dicts(
                                    grid_rows,
                                    prefer_columns=["date", "type", "delta", "earned", "used", "source"],
                                    height="260px",
                                )
                                return
                        except Exception:
                            pass
                        for r in grid_rows[:30]:
                            with ui.element("div").classes("data-row"):
                                ui.label(f"{r.get('date')} · {r.get('type')} · Δ{r.get('delta')}h").classes(
                                    "text-sm mono"
                                )

                bank_pick.on_value_change(lambda _: load_tx())
                ui.button("Load transactions", on_click=load_tx).classes("btn-ghost q-mb-sm").props(
                    "no-caps outline dense"
                )
                load_tx()

    if officer_sel is not None:
        officer_sel.on_value_change(lambda _: refresh())
    refresh()


def render_banks() -> None:
    """Chronos route: Time banks (comp / sick / float)."""

    def body() -> None:
        page_header(
            "Time banks",
            "Comp · sick · float holiday balances and period movements",
            kicker="Finance",
        )
        finance_subnav("banks")
        _banks()

    layout("banks", body)
