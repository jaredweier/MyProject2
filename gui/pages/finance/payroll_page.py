"""Finance NiceGUI pages — split from monolith for maintainability."""

from __future__ import annotations

from nicegui import ui

from gui import session
from gui.pages.finance.ledger import _ledger, _payroll_entries_panel, _payroll_entry_form
from gui.shell import finance_subnav, layout, page_header, panel
from logic import (
    count_pay_periods_in_year,
    donate_leave_hours,
    export_adp_payroll_pack,
    export_pay_pack,
    export_payroll_pdf,
    flsa_period_banners,
    format_pay_period_label,
    get_flsa_settings,
    get_officers_by_seniority,
    get_overtime_alerts,
    get_pay_code_rules,
    get_pay_period,
    is_current_pay_period,
    list_leave_donations,
    list_payroll_exceptions,
    list_roster_accrual_balances,
    lock_pay_period,
    save_flsa_settings,
    save_pay_code_rules,
)


def render_payroll() -> None:
    def body() -> None:
        page_header(
            "Payroll",
            "Pay period ledger · FLSA work period · lock",
            kicker="Finance",
        )
        finance_subnav("payroll")
        start, end = get_pay_period()
        cur = " · current" if is_current_pay_period(start) else ""
        n_year = count_pay_periods_in_year(start.year)
        ui.label(f"{format_pay_period_label(start, end)}{cur} · {n_year} periods in {start.year}").classes(
            "text-sm q-mb-md"
        ).style("color: var(--muted)")

        # FLSA autopilot banners + exception queue + pay pack
        with panel("FLSA autopilot — hours to OT threshold", glow=True):
            banners = flsa_period_banners(reference=start) or []
            hot = [b for b in banners if b.get("level") in ("critical", "warning")][:10]
            if not hot:
                ui.label("All active officers under FLSA warn band for current period.").classes(
                    "text-xs text-gray-500"
                )
            for b in hot:
                sev = b.get("level")
                cls = "alert-danger" if sev == "critical" else "alert-warn"
                ui.html(f'<div class="alert {cls}">{b.get("message")}</div>', sanitize=False)

        with panel("Payroll exception queue"):
            ex = list_payroll_exceptions(reference=start)
            items = ex.get("items") or []
            ui.label(ex.get("message") or f"{len(items)} exception(s)").classes("text-xs q-mb-sm")
            for item in items[:15]:
                ui.label(item.get("message") or item.get("kind")).classes("text-xs")
            if not items:
                ui.html('<div class="alert alert-ok">No exceptions detected.</div>', sanitize=False)

        with panel("Accrual balances (roster)"):
            bal = list_roster_accrual_balances(as_of=start)
            for row in (bal.get("rows") or [])[:20]:
                ui.label(
                    f"{row.get('officer_name')}: sick {row.get('sick_hours')}h · "
                    f"comp {row.get('comp_hours')}h · float {row.get('float_holiday_hours')}h · "
                    f"holiday {row.get('holiday_hours')}h"
                ).classes("text-xs")

        with panel("Pay export pack"):

            def do_pay_pack():
                r = export_pay_pack(period_start=start.isoformat() if hasattr(start, "isoformat") else str(start))
                paths = r.get("paths") or []
                ui.notify(
                    r.get("message") or (f"{len(paths)} file(s)" if paths else "Failed"),
                    type="positive" if r.get("success") else "negative",
                )

            ui.button("Export full pay pack (ADP + dual OT + equity + exceptions)", on_click=do_pay_pack).classes(
                "btn-primary"
            ).props("no-caps unelevated dense")

        if session.can("payroll.lock_period") or session.can("payroll.edit"):
            from logic import is_pay_period_locked, unlock_pay_period

            locked_now = bool(is_pay_period_locked(start))
            with panel("Pay period lock (supervisor)", glow=False):
                ui.label("Lock freezes timecard edits for this period (common LE payroll close process).").classes(
                    "text-xs text-gray-500 q-mb-sm"
                )
                ui.label("Status: LOCKED — edits disabled" if locked_now else "Status: open — edits allowed").classes(
                    "text-sm font-semibold q-mb-sm"
                )

                def do_lock():
                    uid = (session.current_user() or {}).get("id")
                    r = lock_pay_period(start, user_id=uid)
                    ui.notify(
                        f"Locked {r.get('period_start')} – {r.get('period_end')}"
                        if r.get("success")
                        else r.get("message", "Lock failed"),
                        type="positive" if r.get("success") else "negative",
                    )
                    ui.navigate.to("/payroll")

                def do_unlock():
                    uid = (session.current_user() or {}).get("id")
                    r = unlock_pay_period(user_id=uid)
                    ui.notify(
                        "Pay period unlocked" if r.get("success") else r.get("message", "Unlock failed"),
                        type="positive" if r.get("success") else "negative",
                    )
                    ui.navigate.to("/payroll")

                with ui.row().classes("gap-2 flex-wrap"):
                    if locked_now:
                        ui.button("Unlock pay period", on_click=do_unlock).classes("btn-primary").props(
                            "no-caps unelevated dense"
                        )
                    else:
                        ui.button("Lock current pay period", on_click=do_lock).classes("btn-ghost").props(
                            "no-caps outline dense"
                        )
        if session.can("payroll.edit") or session.can("admin.settings") or session.can("settings.manage"):
            _flsa_panel()
            _pay_code_rules_panel()
        with panel("OT alerts this period"):
            try:
                alerts = get_overtime_alerts(period_start=start) or {}
            except Exception as exc:
                alerts = {"message": str(exc)}
            rows = alerts.get("alerts") or alerts.get("rows") or alerts.get("officers") or []
            if isinstance(alerts, list):
                rows = alerts
            if not rows:
                ui.html(
                    f'<div class="alert alert-ok">{alerts.get("message") or "No OT threshold alerts."}</div>',
                    sanitize=False,
                )
            else:
                for a in rows[:30]:
                    if isinstance(a, dict):
                        ui.label(
                            f"{a.get('officer_name') or a.get('name') or a.get('officer_id')} · "
                            f"{a.get('hours') or a.get('ot_hours') or '—'}h · "
                            f"{a.get('message') or a.get('level') or ''}"
                        ).classes("text-sm")
                    else:
                        ui.label(str(a)).classes("text-sm")
        _ledger(start)
        _payroll_entries_panel(start)
        if session.can("payroll.edit"):
            _payroll_entry_form(start)
        if session.can("payroll.view_all") or session.can("payroll.edit") or session.can("exports.run"):
            with panel("Payroll Export Pack", glow=False):
                ui.label("Schedule → timesheet → payroll export. PDF pack for finance review.").classes(
                    "text-xs text-gray-500 q-mb-sm"
                )

                def do_pdf():
                    oid = session.linked_officer_id() if session.is_officer() else None
                    r = export_payroll_pdf(officer_id=oid, period_start=start)
                    if r.get("success"):
                        path = r.get("path") or r.get("output_path") or r.get("file")
                        ui.notify(f"Payroll PDF{(': ' + str(path)) if path else ' ready'}", type="positive")
                    else:
                        ui.notify(r.get("message", "Export failed"), type="negative")

                def do_adp():
                    r = export_adp_payroll_pack(period_start=start)
                    if r.get("success"):
                        ui.notify(r.get("message") or f"Pack: {r.get('path')}", type="positive")
                    else:
                        ui.notify(r.get("message", "Export failed"), type="negative")

                def do_flsa_split():
                    from logic.labor_compliance import export_flsa_vs_contract_ot_csv

                    r = export_flsa_vs_contract_ot_csv(
                        period_start=start.isoformat() if hasattr(start, "isoformat") else str(start)
                    )
                    ui.notify(
                        r.get("message") or r.get("path") or "Exported"
                        if r.get("success")
                        else r.get("message", "Export failed"),
                        type="positive" if r.get("success") else "negative",
                    )

                with ui.row().classes("gap-2 flex-wrap"):
                    ui.button("Export Payroll PDF", on_click=do_pdf).classes("btn-primary").props(
                        "no-caps unelevated dense"
                    )
                    ui.button("ADP / Paychex CSV Pack", on_click=do_adp).classes("btn-ghost").props(
                        "no-caps outline dense"
                    )
                    ui.button("FLSA Vs Contract OT", on_click=do_flsa_split).classes("btn-ghost").props(
                        "no-caps outline dense"
                    )

        if session.can("payroll.edit") or session.can("timecard.edit_all"):
            with panel("Leave donation (NEOGOV)", glow=False):
                ui.label("Public-sector: transfer bank hours donor → recipient (comp/sick/holiday).").classes(
                    "text-xs text-gray-500 q-mb-sm"
                )
                officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
                names = [o["name"] for o in officers]
                omap = {o["name"]: o["id"] for o in officers}
                if len(names) < 2:
                    ui.html('<div class="alert alert-warn">Need two officers.</div>', sanitize=False)
                else:
                    donor = ui.select(names, value=names[0], label="Donor").classes("w-full")
                    recip = ui.select(names, value=names[1], label="Recipient").classes("w-full")
                    bank = ui.select(
                        ["comp", "sick", "float_holiday", "holiday"],
                        value="comp",
                        label="Bank",
                    ).classes("w-full")
                    hrs = ui.input(label="Hours", value="8").classes("w-full")
                    dnotes = ui.input(label="Notes").classes("w-full")

                    def do_donate():
                        try:
                            h = float((hrs.value or "0").strip())
                        except ValueError:
                            ui.notify("Hours numeric", type="negative")
                            return
                        did = omap.get(donor.value)
                        rid = omap.get(recip.value)
                        if not did or not rid:
                            ui.notify("Select donor and recipient", type="negative")
                            return
                        if did == rid:
                            ui.notify("Donor and recipient must differ", type="negative")
                            return
                        uid = (session.current_user() or {}).get("id")
                        r = donate_leave_hours(
                            did,
                            rid,
                            bank.value or "comp",
                            h,
                            notes=(dnotes.value or "").strip(),
                            user_id=uid,
                        )
                        ui.notify(
                            r.get("message", "Done") if r.get("success") else r.get("message", "Failed"),
                            type="positive" if r.get("success") else "negative",
                        )

                    ui.button("Donate leave hours", on_click=do_donate).classes("btn-primary q-mt-sm").props(
                        "no-caps unelevated dense"
                    )
                    try:
                        hist = list_leave_donations(limit=8) or {}
                        for d in hist.get("donations") or []:
                            ui.label(
                                f"{d.get('donor_name')} → {d.get('recipient_name')} · "
                                f"{d.get('hours')}h {d.get('bank_type')}"
                            ).classes("text-xs text-gray-400")
                    except Exception:
                        pass

    layout("payroll", body)


def _pay_code_rules_panel() -> None:
    """CBA pay knobs — holiday multipliers, callback min (Aladtec/CBA payroll pattern)."""
    with panel("Pay codes & CBA multipliers", glow=True):
        ui.label(
            "Public-safety payroll: callback minimums (court/callout), holiday premiums (often 2.5–3.0×), "
            "OT mult. Not legal advice — match your CBA."
        ).classes("text-xs text-gray-500 q-mb-sm")
        try:
            rules = get_pay_code_rules() or {}
        except Exception as exc:
            ui.label(str(exc)).classes("text-sm text-red-400")
            return
        g = rules.get("global") or {}
        codes = rules.get("codes") or {}
        cb_min = ui.input(
            label="Callback minimum hours (court/callout)",
            value=str(g.get("callback_minimum_hours", 2.0)),
        ).classes("w-full")
        ot_mult = ui.input(
            label="Default OT multiplier",
            value=str(g.get("default_overtime_multiplier", 1.5)),
        ).classes("w-full")
        # Key LE codes editable
        key_codes = [
            "Overtime Earned",
            "Callback",
            "Holiday Pay",
            "Holiday Overtime",
            "Comp Earned",
            "Holiday Comp Earned",
        ]
        fields: dict = {}
        with ui.expansion("Edit rate / premium / comp ratios", icon="tune").classes("w-full q-mt-sm"):
            for name in key_codes:
                c = codes.get(name) or {}
                if not c and name not in codes:
                    continue
                ui.label(name).classes("text-xs text-gray-400 q-mt-sm")
                with ui.row().classes("gap-2 w-full flex-wrap"):
                    rm = ui.input(label="Rate ×", value=str(c.get("rate_multiplier", 1.0))).classes("w-28")
                    pm = ui.input(label="Premium ×", value=str(c.get("premium_multiplier", 0.0))).classes("w-28")
                    cr = ui.input(
                        label="Comp credit",
                        value=str(c.get("comp_bank_credit_ratio", 0.0)),
                    ).classes("w-28")
                    fields[name] = (rm, pm, cr)
                formula = c.get("formula") or ""
                if formula:
                    ui.label(formula).classes("text-xs text-gray-600")

        def save_rules():
            try:
                g_out = {
                    "callback_minimum_hours": float((cb_min.value or "2").strip()),
                    "default_overtime_multiplier": float((ot_mult.value or "1.5").strip()),
                }
            except ValueError:
                ui.notify("Global settings must be numeric", type="negative")
                return
            codes_out: dict = {}
            for name, (rm, pm, cr) in fields.items():
                try:
                    codes_out[name] = {
                        "rate_multiplier": float((rm.value or "1").strip()),
                        "premium_multiplier": float((pm.value or "0").strip() or "0"),
                        "comp_bank_credit_ratio": float((cr.value or "0").strip() or "0"),
                    }
                except ValueError:
                    ui.notify(f"{name}: numeric fields required", type="negative")
                    return
            uid = (session.current_user() or {}).get("id")
            r = save_pay_code_rules({"global": g_out, "codes": codes_out}, user_id=uid)
            ui.notify(
                r.get("message", "Saved") if r.get("success") else r.get("message", "Save failed"),
                type="positive" if r.get("success") else "negative",
            )

        ui.button("Save pay code rules", on_click=save_rules).classes("btn-primary q-mt-sm").props(
            "no-caps unelevated dense"
        )


def _flsa_panel() -> None:
    """§7(k) work-period knobs — full admin surface (days, base, dual, caps, 207k status)."""
    with panel("FLSA §7(k) / 207(k) work period (full knobs)", glow=True):
        try:
            settings = get_flsa_settings() or {}
        except Exception as exc:
            ui.label(f"Unable to load FLSA settings: {exc}").classes("text-sm text-red-400")
            return
        ui.label(
            "Law enforcement often uses a 14-day work period (~86h OT threshold) or 28-day (~171h). "
            "Dual workforce: sworn 7(k) + civilian weekly 40h. Not legal advice — match your CBA."
        ).classes("text-xs text-gray-500 q-mb-sm")
        # Current period strip
        ui.html(
            f'<div class="kpi-row q-mb-sm">'
            f'<div class="kpi g"><div class="kpi-l">Work period</div>'
            f'<div class="kpi-v" style="font-size:18px">{settings.get("work_period_days") or "—"}d</div></div>'
            f'<div class="kpi"><div class="kpi-l">Threshold</div>'
            f'<div class="kpi-v" style="font-size:18px">{settings.get("hours_threshold") or "—"}h</div></div>'
            f'<div class="kpi"><div class="kpi-l">Current FLSA window</div>'
            f'<div class="kpi-v" style="font-size:14px">{settings.get("current_period_start") or "—"} – '
            f"{settings.get('current_period_end') or '—'}</div></div>"
            f'<div class="kpi"><div class="kpi-l">Dual workforce</div>'
            f'<div class="kpi-v" style="font-size:16px">{"ON" if settings.get("dual_workforce") else "off"}</div></div>'
            f"</div>",
            sanitize=False,
        )
        # Netchex / NEOGOV dual workforce (sworn 7(k) vs civilian 40h)
        dual = ui.checkbox(
            "Dual workforce mode (sworn 7(k) + civilian weekly threshold)",
            value=bool(settings.get("dual_workforce")),
        )
        days = ui.input(
            label="Sworn work period days (7–28)",
            value=str(settings.get("work_period_days") or settings.get("flsa_work_period_days") or "14"),
        ).classes("w-full")
        raw_base = str(settings.get("base_date") or settings.get("flsa_base_date") or "")
        try:
            from validators import format_date as _fd
            from validators import parse_date as _pd

            _bd = _pd(raw_base) if raw_base else None
            base_disp = _fd(_bd) if _bd else raw_base
        except Exception:
            base_disp = raw_base
        base = ui.input(
            label="FLSA base date (M/D/YY · stored ISO)",
            value=base_disp,
            placeholder="e.g. 1/1/26",
        ).classes("w-full")
        civ_thr = ui.input(
            label="Civilian weekly OT threshold (hours)",
            value=str(settings.get("civilian_weekly_threshold") or 40),
        ).classes("w-full")
        sworn_cap = ui.input(
            label="Sworn comp bank cap (hours)",
            value=str(settings.get("sworn_comp_cap") or 480),
        ).classes("w-full")
        civ_cap = ui.input(
            label="Civilian comp bank cap (hours)",
            value=str(settings.get("civilian_comp_cap") or 240),
        ).classes("w-full")
        ui.label(
            f"Live sworn threshold this period: {settings.get('hours_threshold', '—')}h · "
            f"dual={'on' if settings.get('dual_workforce') else 'off'} · "
            f"sworn cap {settings.get('sworn_comp_cap')}h · civ cap {settings.get('civilian_comp_cap')}h"
        ).classes("text-xs text-gray-500 q-mb-sm")

        use_blend = ui.checkbox(
            "Use blended regular rate for OT calc (Netchex/FLSA pattern)",
            value=False,
        )
        try:
            from logic.operations import get_department_setting

            use_blend.value = get_department_setting("flsa_use_blended_rate", "0").strip() in (
                "1",
                "true",
                "yes",
                "on",
            )
        except Exception:
            pass

        def save():
            try:
                wpd = int((days.value or "14").strip())
                cthr = float((civ_thr.value or "40").strip())
                scap = float((sworn_cap.value or "480").strip())
                ccap = float((civ_cap.value or "240").strip())
            except ValueError:
                ui.notify("Numeric fields required", type="negative")
                return
            uid = (session.current_user() or {}).get("id")
            r = save_flsa_settings(
                wpd,
                base_date_text=(base.value or "").strip() or None,
                user_id=uid,
                dual_workforce=bool(dual.value),
                civilian_weekly_threshold=cthr,
                sworn_comp_cap=scap,
                civilian_comp_cap=ccap,
            )
            try:
                from logic.dual_workforce import save_dual_workforce_settings

                save_dual_workforce_settings(
                    dual_flsa_enabled=bool(dual.value),
                    civilian_weekly_threshold=cthr,
                    comp_cap_sworn=scap,
                    comp_cap_civilian=ccap,
                    user_id=uid,
                )
            except Exception:
                pass
            try:
                from logic.operations import set_department_setting

                set_department_setting(
                    "flsa_use_blended_rate",
                    "1" if use_blend.value else "0",
                    user_id=uid,
                )
            except Exception:
                pass
            ui.notify(
                r.get("message", "Saved") if r.get("success") else r.get("message", "Save failed"),
                type="positive" if r.get("success") else "negative",
            )

        with ui.row().classes("gap-2 q-mt-sm flex-wrap"):
            ui.button("Save FLSA settings", on_click=save).classes("btn-primary").props("no-caps unelevated")

            dual_grid_host = ui.element("div").classes("w-full q-mt-sm")

            def exp_dual():
                try:
                    from gui.tables import aggrid_from_dicts
                    from logic.dual_workforce import export_dual_ot_ledger_csv, run_dual_period_ot_ledger

                    led = run_dual_period_ot_ledger()
                    ex = export_dual_ot_ledger_csv()
                    dual_grid_host.clear()
                    with dual_grid_host:
                        rows = []
                        for r in led.get("rows") or []:
                            if not isinstance(r, dict):
                                continue
                            rows.append(
                                {
                                    "name": r.get("officer_name"),
                                    "class": r.get("workforce_class"),
                                    "basis": r.get("basis_label") or r.get("ot_basis"),
                                    "total_h": r.get("total_hours"),
                                    "regular_h": r.get("regular_hours"),
                                    "ot_h": r.get("overtime_hours"),
                                    "comp_cap": r.get("comp_cap"),
                                }
                            )
                        if rows:
                            aggrid_from_dicts(
                                rows,
                                prefer_columns=[
                                    "name",
                                    "class",
                                    "basis",
                                    "total_h",
                                    "regular_h",
                                    "ot_h",
                                    "comp_cap",
                                ],
                                height="320px",
                                csv_export=True,
                                csv_name="dual_ot_ledger",
                            )
                        else:
                            ui.label("No dual OT rows for this period.").classes("text-xs").style("color: var(--dim)")
                    ui.notify(
                        f"Dual OT ledger: {led.get('count')} officers · "
                        f"sworn OT {led.get('sworn_ot_hours')}h · civ OT {led.get('civilian_ot_hours')}h · "
                        f"{ex.get('path')}",
                        type="positive" if ex.get("success") else "warning",
                        multi_line=True,
                    )
                except Exception as exc:
                    ui.notify(str(exc)[:200], type="negative")

            ui.button("Run dual OT ledger / export", on_click=exp_dual).classes("btn-ghost").props("no-caps outline")
            ui.label("Grid fills after Run dual OT ledger / export.").classes("text-xs q-mt-xs").style(
                "color: var(--dim)"
            )

        # Officer-level §207(k) status + payroll summary
        ui.separator()
        ui.label("Officer §207(k) status & payroll summary").classes("text-xs text-gray-500 q-mb-xs")
        officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
        names = [o["name"] for o in officers] or ["—"]
        omap = {o["name"]: o["id"] for o in officers}
        flsa_off = ui.select(names, value=names[0], label="Officer").classes("w-full")
        flsa_host = ui.element("div")

        def load_207k():
            flsa_host.clear()
            oid = omap.get(flsa_off.value)
            with flsa_host:
                if not oid:
                    ui.label("No officer").classes("text-xs")
                    return
                try:
                    from logic.labor_compliance import get_flsa_207k_status, get_flsa_payroll_summary

                    st = get_flsa_207k_status(int(oid)) or {}
                    sm = get_flsa_payroll_summary(int(oid)) or {}
                except Exception as exc:
                    ui.label(str(exc)).classes("text-sm text-red-400")
                    return
                ui.label(st.get("message") or str(st)[:200]).classes("text-sm font-semibold")
                for k in (
                    "hours",
                    "threshold",
                    "ot_hours",
                    "period_start",
                    "period_end",
                    "percent",
                    "level",
                ):
                    if st.get(k) is not None:
                        ui.label(f"{k}: {st.get(k)}").classes("text-xs mono")
                if sm:
                    ui.label(sm.get("message") or "Payroll summary").classes("text-xs q-mt-sm").style(
                        "color: var(--muted)"
                    )
                    for k, v in list(sm.items())[:12]:
                        if k in ("success", "message"):
                            continue
                        ui.label(f"{k}: {v}").classes("text-xs mono")

        try:
            flsa_off.on_value_change(lambda _: load_207k())
        except Exception:
            pass
        ui.button("Load §207(k) status", on_click=load_207k).classes("btn-ghost q-mt-xs").props("no-caps outline dense")
        load_207k()
