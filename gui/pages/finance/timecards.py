"""Finance NiceGUI pages — split from monolith for maintainability."""

from __future__ import annotations

from nicegui import app, ui

from gui import session
from gui.pages.finance.banks import _banks
from gui.shell import finance_subnav, layout, page_header, panel
from logic import (
    convert_overtime_to_comp,
    format_pay_period_label,
    get_flsa_settings,
    get_officers_by_seniority,
    get_pay_code_rules,
    get_pay_period,
    get_pay_period_hours_summary,
    get_timecard_entries_for_scope,
    get_timecard_period,
    is_current_pay_period,
    is_pay_period_locked,
    list_pay_periods_catalog,
    lock_pay_period,
    prefill_timecard_from_schedule,
    save_timecard_entry,
    search_pay_period_by_date,
    unlock_pay_period,
)
from validators import format_date, parse_date

_TIMECARD_PERIOD_KEY = "timecard_period_start"


def _resolve_timecard_period():
    """Active pay period — optional user-storage jump from Find period."""
    raw = None
    try:
        raw = app.storage.user.get(_TIMECARD_PERIOD_KEY)
    except Exception:
        raw = None
    if raw:
        try:
            d = parse_date(str(raw).strip())
            if d:
                return get_pay_period(d)
        except Exception:
            pass
    return get_pay_period()


def render_timecards() -> None:
    def body() -> None:
        page_header(
            "Timecards",
            "Biweekly time entry · banked balances · FR pay codes",
            kicker="Finance",
        )
        finance_subnav("timecards")
        start, end = _resolve_timecard_period()
        locked = bool(is_pay_period_locked(start))
        cur = " · current" if is_current_pay_period(start) else ""
        lock_mark = " · LOCKED" if locked else ""
        ui.label(f"{format_pay_period_label(start, end)}{cur}{lock_mark}").classes("text-sm q-mb-md").style(
            "color: var(--muted)"
        )
        if locked:
            ui.html(
                '<div class="alert alert-warn">Pay period is locked — new entries and prefill are disabled. '
                "Unlock from Payroll if you have permission.</div>",
                sanitize=False,
            )

        # Period tools + 7(k)-style hours meter
        with ui.row().classes("gap-2 q-mb-sm flex-wrap items-end"):
            q_period = ui.input(label="Jump to period (date)", placeholder="7/9/26 or 07-09-2026").classes("w-48")

            def jump_period():
                r = search_pay_period_by_date((q_period.value or "").strip())
                if r.get("success") and r.get("period_start"):
                    try:
                        app.storage.user[_TIMECARD_PERIOD_KEY] = r["period_start"]
                    except Exception:
                        pass
                    ui.notify(
                        f"Period {format_date(r.get('period_start'))} – {format_date(r.get('period_end'))}",
                        type="info",
                    )
                    ui.navigate.to("/timecards")
                else:
                    ui.notify(r.get("message", "Not found"), type="warning")

            def jump_current():
                try:
                    app.storage.user.pop(_TIMECARD_PERIOD_KEY, None)
                except Exception:
                    pass
                ui.navigate.to("/timecards")

            ui.button("Find period", on_click=jump_period).classes("btn-ghost").props("no-caps outline dense")
            ui.button("Current period", on_click=jump_current).classes("btn-ghost").props("no-caps outline dense")

            def do_prefill():
                if is_pay_period_locked(start):
                    ui.notify("Pay period is locked — unlock before prefill", type="warning")
                    return
                oid = session.linked_officer_id()
                if not oid and session.can("timecard.edit_all"):
                    offs = [o for o in get_officers_by_seniority() if o.get("active") == 1]
                    oid = offs[0]["id"] if offs else None
                if not oid:
                    ui.notify("No officer for prefill", type="warning")
                    return
                r = prefill_timecard_from_schedule(oid, start)
                ui.notify(
                    r.get("message", "Prefill done") if r.get("success") else r.get("message", "Prefill failed"),
                    type="positive" if r.get("success") else "negative",
                )

            if (session.can("timecard.edit_own") or session.can("timecard.edit_all")) and not locked:
                ui.button("Prefill from schedule", on_click=do_prefill).classes("btn-primary").props(
                    "no-caps unelevated dense"
                )

            if session.can("payroll.lock_period") or session.can("payroll.edit"):

                def do_lock():
                    uid = (session.current_user() or {}).get("id")
                    r = lock_pay_period(start, user_id=uid)
                    ui.notify(
                        f"Locked {r.get('period_start')} – {r.get('period_end')}"
                        if r.get("success")
                        else r.get("message", "Lock failed"),
                        type="positive" if r.get("success") else "negative",
                    )
                    ui.navigate.to("/timecards")

                def do_unlock():
                    uid = (session.current_user() or {}).get("id")
                    r = unlock_pay_period(user_id=uid)
                    ui.notify(
                        r.get("message", "Unlocked") if r.get("success") else r.get("message", "Unlock failed"),
                        type="positive" if r.get("success") else "negative",
                    )
                    ui.navigate.to("/timecards")

                if locked:
                    ui.button("Unlock period", on_click=do_unlock).classes("btn-ghost").props("no-caps outline dense")
                else:
                    ui.button("Lock period", on_click=do_lock).classes("btn-ghost").props("no-caps outline dense")

        oid_meter = session.linked_officer_id()
        try:
            summary = get_pay_period_hours_summary(start, officer_id=oid_meter) or {}
        except Exception:
            summary = {}
        try:
            flsa = get_flsa_settings() or {}
            wpd = int(flsa.get("work_period_days") or flsa.get("flsa_work_period_days") or 14)
        except Exception:
            wpd = 14
        # Approximate LE 7(k) threshold for period length (14→86, 28→171)
        thr = round(171 * (wpd / 28.0)) if wpd else 86
        hours_val = summary.get("total_hours") or summary.get("hours") or summary.get("regular_hours")
        if hours_val is None and isinstance(summary.get("by_type"), dict):
            hours_val = sum(float(v or 0) for v in summary["by_type"].values())
        try:
            hours_f = float(hours_val or 0)
        except (TypeError, ValueError):
            hours_f = 0.0
        pct = min(100, int(100 * hours_f / thr)) if thr else 0
        with panel(f"Hours vs §7(k)-style threshold (~{thr}h / {wpd}d)", glow=False):
            ui.linear_progress(value=pct / 100.0).props(
                f"color={'negative' if pct >= 95 else 'warning' if pct >= 80 else 'positive'}"
            )
            ui.label(f"{hours_f:.1f}h recorded · {pct}% of ~{thr}h threshold").classes("text-xs text-gray-400 q-mt-xs")

        tab = ui.tabs().classes("q-mb-sm")
        with tab:
            t1 = ui.tab("Time Entries")
            t2 = ui.tab("Banked Time")
            t3 = ui.tab("Add Entry")
            t4 = ui.tab("Period catalog")
            t5 = ui.tab("Scoped ledger")
        with ui.tab_panels(tab, value=t1).classes("w-full"):
            with ui.tab_panel(t1):
                _timecard(start)
            with ui.tab_panel(t2):
                _banks()
            with ui.tab_panel(t3):
                _add_entry(start)
            with ui.tab_panel(t4):
                _period_catalog()
            with ui.tab_panel(t5):
                _timecard_scope_panel()

    layout("timecards", body)


def _period_catalog() -> None:
    with panel("Pay periods"):
        try:
            cat = list_pay_periods_catalog(limit=12) or {}
        except Exception as exc:
            ui.label(str(exc)).classes("text-sm text-red-400")
            return
        periods = cat.get("periods") or cat.get("rows") or []
        if not periods:
            ui.html('<div class="alert alert-ok">No catalog rows.</div>', sanitize=False)
            return
        for p in periods[:12]:
            if not isinstance(p, dict):
                continue
            mark = " · current" if p.get("is_current") else ""
            ui.label(
                f"{format_date(p.get('period_start') or p.get('start'))} – "
                f"{format_date(p.get('period_end') or p.get('end'))}{mark}"
            ).classes("text-sm q-mb-xs")


def _timecard_scope_panel() -> None:
    """Extra-hours style ledger by pay period / month / year (Aladtec Extra Hours pattern)."""
    with panel("Timecard entries by scope", glow=True):
        ui.label(
            "Industry pattern: unplanned OT / holdovers / variances visible by period. "
            "Uses get_timecard_entries_for_scope."
        ).classes("text-xs text-gray-500 q-mb-sm")
        oid = session.linked_officer_id()
        omap: dict = {}
        officer_sel = None
        if not session.is_officer() and session.can("timecard.view_all"):
            officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
            names = [o["name"] for o in officers]
            omap = {o["name"]: o["id"] for o in officers}
            officer_sel = ui.select(names, value=names[0] if names else None, label="Officer").classes("w-full")
            if oid is None and names:
                oid = omap.get(names[0])
        scope = ui.select(
            ["pay_period", "month", "year", "all"],
            value="pay_period",
            label="Scope",
        ).classes("w-full")
        host = ui.element("div")

        def refresh():
            nonlocal oid
            if officer_sel is not None and officer_sel.value:
                oid = omap.get(officer_sel.value)
            host.clear()
            with host:
                if not oid:
                    ui.html('<div class="alert alert-warn">No officer selected.</div>', sanitize=False)
                    return
                try:
                    data = get_timecard_entries_for_scope(oid, scope=scope.value or "pay_period") or {}
                except Exception as exc:
                    ui.label(str(exc)).classes("text-sm text-red-400")
                    return
                if isinstance(data, dict) and data.get("success") is False:
                    ui.html(
                        f'<div class="alert alert-warn">{data.get("message", "Unable to load")}</div>',
                        sanitize=False,
                    )
                    return
                rows = data.get("entries") or data.get("rows") or data.get("days") or []
                if isinstance(data, list):
                    rows = data
                ui.label(
                    f"{len(rows)} entr(ies) · {data.get('scope_label') or scope.value or ''}"
                    if isinstance(data, dict)
                    else f"{len(rows)} entr(ies)"
                ).classes("text-xs text-gray-500 q-mb-sm")
                if not rows:
                    ui.html('<div class="alert alert-ok">No entries in this scope.</div>', sanitize=False)
                    return
                grid_rows = []
                for e in rows[:120]:
                    if not isinstance(e, dict):
                        continue
                    grid_rows.append(
                        {
                            "date": e.get("work_date") or e.get("entry_date") or e.get("date"),
                            "type": e.get("entry_type") or e.get("type"),
                            "hours": e.get("hours") or e.get("total_hours"),
                            "notes": (e.get("notes") or "")[:40],
                        }
                    )
                try:
                    from gui.tables import aggrid_from_dicts

                    if grid_rows:
                        aggrid_from_dicts(
                            grid_rows,
                            prefer_columns=["date", "type", "hours", "notes"],
                            height="300px",
                        )
                        return
                except Exception:
                    pass
                for r in grid_rows[:40]:
                    with ui.element("div").classes("data-row"):
                        ui.label(f"{r.get('date')} · {r.get('type')} · {r.get('hours')}h").classes("text-sm mono")

        if officer_sel is not None:
            officer_sel.on_value_change(lambda _: refresh())
        scope.on_value_change(lambda _: refresh())
        ui.button("Load", on_click=refresh).classes("btn-ghost q-mb-sm").props("no-caps outline dense")
        refresh()


def _add_entry(period_start) -> None:
    """Quick timecard line — Regular / OT cash / Comp / Night diff (FR pay-code set)."""
    can_edit = session.can("timecard.edit_own") or session.can("timecard.edit_all")
    if not can_edit:
        ui.html('<div class="alert alert-warn">No permission to add timecard entries.</div>', sanitize=False)
        return
    if is_pay_period_locked(period_start):
        ui.html(
            '<div class="alert alert-warn">Pay period is locked — unlock on Timecards or Payroll before adding entries.</div>',
            sanitize=False,
        )
        return
    with panel("Add timecard entry", glow=True):
        oid = session.linked_officer_id()
        omap = {}
        officer_sel = None
        if session.can("timecard.edit_all") and not session.is_officer():
            officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
            names = [o["name"] for o in officers]
            omap = {o["name"]: o["id"] for o in officers}
            officer_sel = ui.select(names, value=names[0] if names else None, label="Officer").classes("w-full")
        # Pay codes from rules or FR defaults
        codes = [
            "Regular Hours",
            "Overtime Earned",
            "Comp Time Earned",
            "Comp Time Used",
            "Holiday Worked",
            "Night Differential",
            "Court",
            "Training",
        ]
        try:
            rules = get_pay_code_rules() or {}
            extra = rules.get("codes") or rules.get("pay_codes") or rules.get("types") or []
            if isinstance(extra, list) and extra:
                for c in extra:
                    if isinstance(c, str) and c not in codes:
                        codes.append(c)
                    elif isinstance(c, dict):
                        n = c.get("name") or c.get("code")
                        if n and n not in codes:
                            codes.append(str(n))
        except Exception:
            pass
        from config import DATE_INPUT_HINT

        d_in = ui.input(
            label=f"Work date ({DATE_INPUT_HINT})",
            value=format_date(period_start),
            placeholder=format_date(period_start),
        ).classes("w-full")
        hours = ui.input(label="Hours", value="8").classes("w-full")
        etype = ui.select(codes, value=codes[0], label="Pay code / entry type").classes("w-full")
        ui.label(
            "Cash vs comp (NEOGOV-style election): pick Overtime Earned (cash) or "
            "Comp Earned / Comp Time Earned (bank) — public-sector choice per entry."
        ).classes("text-xs text-gray-500")
        ui.label(
            "Extra duty / special detail (TeleStaff/Netchex): use Callback or notes "
            "tagged 'extra duty' / 'detail' for off-duty events; invoice billing is separate."
        ).classes("text-xs text-gray-500")
        night = ui.input(label="Night differential hours", value="0").classes("w-full")
        notes = ui.input(
            label="Notes (holdover · Extra Hours · extra duty / detail reason)",
            value="",
        ).classes("w-full")

        def save():
            nonlocal oid
            if is_pay_period_locked(period_start):
                ui.notify("Pay period is locked — unlock before saving", type="warning")
                return
            if officer_sel is not None and officer_sel.value:
                oid = omap.get(officer_sel.value)
            if not oid:
                ui.notify("No officer selected / linked", type="negative")
                return
            dt = parse_date((d_in.value or "").strip())
            if not dt:
                ui.notify("Invalid date", type="negative")
                return
            try:
                h = float((hours.value or "0").strip())
                nd = float((night.value or "0").strip() or "0")
            except ValueError:
                ui.notify("Hours must be numeric", type="negative")
                return
            r = save_timecard_entry(
                oid,
                dt.isoformat(),
                h,
                entry_type=etype.value or "Regular Hours",
                night_diff_hours=nd,
                notes=(notes.value or "").strip(),
                period_start=period_start.isoformat(),
            )
            ui.notify(
                r.get("message", "Saved") if r.get("success") else r.get("message", "Failed"),
                type="positive" if r.get("success") else "negative",
            )

        ui.button("Save entry", on_click=save).classes("btn-primary q-mt-sm").props("no-caps unelevated")

        def convert_comp():
            """NEOGOV-style OT → comp conversion (uses convert_overtime_to_comp)."""
            nonlocal oid
            if officer_sel is not None and officer_sel.value:
                oid = omap.get(officer_sel.value)
            if not oid:
                ui.notify("No officer selected / linked", type="negative")
                return
            try:
                dt = parse_date((d_in.value or "").strip())
            except Exception:
                dt = None
            if not dt:
                ui.notify("Invalid date", type="negative")
                return
            try:
                h = float((hours.value or "0").strip())
                nd = float((night.value or "0").strip() or "0")
            except ValueError:
                ui.notify("Hours must be numeric", type="negative")
                return
            r = convert_overtime_to_comp(
                oid,
                dt.isoformat() if hasattr(dt, "isoformat") else str(dt),
                h,
                notes=(notes.value or "").strip() or "OT converted to comp",
                night_differential_hours=nd,
            )
            ui.notify(
                r.get("message", "Converted") if r.get("success") else r.get("message", "Failed"),
                type="positive" if r.get("success") else "negative",
            )

        ui.button("Convert hours → comp bank", on_click=convert_comp).classes("btn-ghost q-mt-sm").props(
            "no-caps outline dense"
        )


def _timecard(period_start) -> None:
    oid = session.linked_officer_id()
    officer_sel = None
    omap = {}
    if not session.is_officer() and session.can("timecard.view_all"):
        officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
        names = [o["name"] for o in officers]
        omap = {o["name"]: o["id"] for o in officers}
        officer_sel = ui.select(names, value=names[0] if names else None, label="Officer").classes("w-full q-mb-sm")

    host = ui.element("div")

    def refresh():
        nonlocal oid
        if officer_sel is not None and officer_sel.value:
            oid = omap.get(officer_sel.value)
        host.clear()
        with host:
            if not oid:
                ui.html(
                    '<div class="alert alert-warn">No Officer Linked To This Login.</div>',
                    sanitize=False,
                )
                return
            data = get_timecard_period(oid, period_start)
            entries = data.get("entries") or data.get("days") or []
            if isinstance(data, dict) and data.get("success") is False:
                ui.html(
                    f'<div class="alert alert-warn">{data.get("message", "Unable To Load")}</div>',
                    sanitize=False,
                )
                return
            if not entries:
                ui.html(
                    '<div class="alert alert-ok">No Entries This Period Yet.</div>',
                    sanitize=False,
                )
                return
            for entry in entries[:40]:
                if isinstance(entry, dict):
                    raw = entry.get("work_date") or entry.get("date") or entry.get("entry_date") or ""
                    label = format_date(raw) if raw else "—"
                    hours = entry.get("hours") or entry.get("total_hours") or entry.get("regular_hours") or "—"
                    etype = entry.get("entry_type") or entry.get("type") or ""
                    text = f"{label}  ·  {hours}h  ·  {etype}"
                else:
                    text = str(entry)
                with ui.element("div").classes("data-row"):
                    ui.label(text).classes("text-sm mono")

    if officer_sel is not None:
        officer_sel.on_value_change(lambda _: refresh())
    with panel("Timecard Entries"):
        ui.button("Refresh", on_click=refresh).classes("btn-ghost q-mb-sm").props("no-caps outline dense")
        refresh()


def render_finance() -> None:
    """Legacy entry — open Timecards."""
    render_timecards()
