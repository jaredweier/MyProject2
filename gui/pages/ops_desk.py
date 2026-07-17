"""Ops Desk — today board: manual review · callout · gaps · FLSA · notify."""

from __future__ import annotations

from nicegui import ui

from gui import session
from gui.clock import today_local
from gui.shell import layout, page_header, panel
from logic import (
    build_callout_ladder,
    diagnose_manual_review,
    execute_callout_order,
    export_policy_pack,
    get_officers_by_seniority,
    get_ops_desk_board,
    get_ot_equity_sort_enabled,
    import_policy_pack,
    resolve_manual_review,
    set_ot_equity_sort_enabled,
)
from logic.bump_off_duty import (
    CRITERION_LABELS,
    get_off_duty_bump_settings_for_ui,
    load_off_duty_bump_policy,
    save_off_duty_bump_policy,
)
from logic.product_complete_pack import (
    fill_gap_click,
    gap_board_with_fill_actions,
    live_day_coverage_report,
    recover_all_manual_review,
)
from validators import format_date


def render_ops_desk() -> None:
    def body() -> None:
        if not (
            session.can("requests.approve")
            or session.can("reports.view")
            or session.can("schedule.updated.edit")
            or session.can("open_shifts.manage")
        ):
            page_header("Ops Desk", "Permission required", kicker="Command")
            ui.html(
                '<div class="alert alert-warn">Supervisor access required for Ops Desk.</div>',
                sanitize=False,
            )
            return

        page_header(
            "Ops Desk",
            "Today · manual review · callout ladder · gaps · FLSA · notify",
            kicker="Chronos Command",
        )

        status = ui.label("").classes("text-xs q-mb-sm").style("color: var(--dim)")
        host = ui.element("div")

        def refresh():
            board = get_ops_desk_board(reference=today_local())
            kpi = board.get("kpi") or {}
            status.set_text(
                f"{board.get('date_display')} · "
                f"Manual {kpi.get('manual_review', 0)} · "
                f"Pending leave {kpi.get('pending_leave', 0)} · "
                f"Gaps {kpi.get('gaps', 0)} · "
                f"Stations under {kpi.get('station_under', 0)} · "
                f"Fatigue {kpi.get('fatigue_flags', 0)} · "
                f"Open {kpi.get('open_shifts', 0)} · "
                f"Outbox queued {kpi.get('outbox_queued', 0)}"
            )
            host.clear()
            with host:
                with ui.element("div").classes("kpi-row q-mb-md"):
                    ui.html(
                        f'<div class="kpi g"><div class="kpi-l">Manual review</div>'
                        f'<div class="kpi-v">{kpi.get("manual_review", 0)}</div></div>'
                        f'<div class="kpi"><div class="kpi-l">Pending leave</div>'
                        f'<div class="kpi-v">{kpi.get("pending_leave", 0)}</div></div>'
                        f'<div class="kpi"><div class="kpi-l">Gaps</div>'
                        f'<div class="kpi-v">{kpi.get("gaps", 0)}</div></div>'
                        f'<div class="kpi"><div class="kpi-l">Stations under</div>'
                        f'<div class="kpi-v">{kpi.get("station_under", 0)}</div></div>'
                        f'<div class="kpi"><div class="kpi-l">Fatigue flags</div>'
                        f'<div class="kpi-v">{kpi.get("fatigue_flags", 0)}</div></div>'
                        f'<div class="kpi"><div class="kpi-l">Pay exceptions</div>'
                        f'<div class="kpi-v">{kpi.get("payroll_exceptions", 0)}</div></div>',
                        sanitize=False,
                    )

                # Station min-staff board (multi-post / ESO pattern)
                st_board = board.get("station_board") or {}
                under = st_board.get("understaffed") or []
                if st_board.get("configured_posts"):
                    with panel("Station / post min staff", glow=bool(under)):
                        level = st_board.get("level") or "ok"
                        cls = (
                            "alert-danger"
                            if level == "critical"
                            else "alert-warn"
                            if level == "warning"
                            else "alert-ok"
                        )
                        ui.html(
                            f'<div class="alert {cls}">{st_board.get("message")}</div>',
                            sanitize=False,
                        )
                        if st_board.get("unassigned"):
                            ui.label(
                                f"Unassigned roster: {st_board.get('unassigned')} (set officer station on Roster)"
                            ).classes("text-xs").style("color: var(--dim)")
                        for u in under[:8]:
                            ui.label(
                                f"· {u.get('code')} {u.get('name')} · "
                                f"{u.get('assigned')}/{u.get('min_staff')} "
                                f"(need {u.get('gap')} more)"
                            ).classes("text-sm")
                        ui.button(
                            "Open deploy stations",
                            on_click=lambda: ui.navigate.to("/deploy"),
                        ).props("dense flat no-caps").classes("q-mt-xs")

                # Fatigue wellness strip (soft — hard stop still on fill/cover)
                fatigue = board.get("fatigue_watch") or {}
                fat_items = fatigue.get("items") or []
                if fat_items:
                    with panel("Fatigue / rest watch", glow=True):
                        ui.label(fatigue.get("message") or "").classes("text-xs q-mb-xs").style("color: var(--dim)")
                        for f in fat_items[:8]:
                            sev = f.get("level") or "warning"
                            cls = "alert-danger" if sev == "critical" else "alert-warn"
                            consec = f.get("consecutive_days")
                            wh = f.get("weekly_hours")
                            extra = []
                            if consec is not None:
                                extra.append(f"{consec}d streak")
                            if wh is not None:
                                extra.append(f"{wh:g}h/wk" if isinstance(wh, (int, float)) else f"{wh}h/wk")
                            tail = (" · " + " · ".join(extra)) if extra else ""
                            ui.html(
                                f'<div class="alert {cls}">{f.get("name")} · '
                                f"score {f.get('score')}/{f.get('threshold')}{tail}</div>",
                                sanitize=False,
                            )

                # FLSA banners
                banners = board.get("flsa_banners") or []
                hot = [b for b in banners if b.get("level") in ("critical", "warning")][:8]
                if hot:
                    with panel("FLSA autopilot — hours to OT threshold", glow=True):
                        for b in hot:
                            sev = b.get("level") or "ok"
                            cls = (
                                "alert-warn"
                                if sev == "warning"
                                else "alert-danger"
                                if sev == "critical"
                                else "alert-ok"
                            )
                            ui.html(
                                f'<div class="alert {cls}">{b.get("message")}</div>',
                                sanitize=False,
                            )

                # Manual review recovery
                with panel("Manual review recovery", glow=True):
                    manual = board.get("manual_review") or []
                    if manual:

                        def recover_all():
                            uid = (session.current_user() or {}).get("id")
                            r = recover_all_manual_review(action="approve_override", user_id=uid)
                            ui.notify(r.get("message", "Done"), type="positive" if r.get("resolved") else "warning")
                            refresh()

                        ui.button(
                            "Recover all (override approve) — unblock publish",
                            on_click=recover_all,
                        ).classes("btn-primary q-mb-sm").props("no-caps unelevated dense")
                    if not manual:
                        ui.html(
                            '<div class="alert alert-ok">No Pending Manual Review items.</div>',
                            sanitize=False,
                        )
                    for item in manual:
                        rid = int(item["id"])
                        with ui.element("div").classes("data-row"):
                            with ui.element("div"):
                                ui.label(f"#{rid} · {item.get('officer_name')} · {item.get('request_type')}").classes(
                                    "text-sm font-semibold"
                                )
                                ui.label(
                                    f"{item.get('date_display')} · {item.get('squad')} "
                                    f"{item.get('shift_start')} · {(item.get('admin_notes') or '')[:80]}"
                                ).classes("text-xs text-gray-500")
                            with ui.row().classes("gap-1 flex-wrap"):
                                ui.button(
                                    "Diagnose",
                                    on_click=lambda r=rid: _show_diagnose(r, refresh),
                                ).props("dense no-caps flat")
                                ui.button(
                                    "Override approve",
                                    on_click=lambda r=rid: _quick_resolve(r, "approve_override", refresh),
                                ).classes("btn-primary").props("dense no-caps unelevated")
                                ui.button(
                                    "Order-in first",
                                    on_click=lambda r=rid: _quick_resolve(r, "order_in", refresh),
                                ).classes("btn-ghost").props("dense no-caps outline")
                                ui.button(
                                    "Open shift",
                                    on_click=lambda r=rid: _quick_resolve(r, "open_shift", refresh),
                                ).props("dense no-caps flat")
                                ui.button(
                                    "Reject",
                                    on_click=lambda r=rid: _quick_resolve(r, "reject", refresh),
                                ).classes("btn-danger").props("dense no-caps outline")

                # Same-day callout
                with panel("Same-day callout / sick ladder"):
                    officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
                    names = {o["name"]: o["id"] for o in officers} or {"—": 0}
                    off_sel = ui.select(
                        list(names.keys()), value=list(names.keys())[0], label="Absent officer"
                    ).classes("w-full")
                    reason = ui.select(
                        ["Sick", "Emergency", "Personal", "Other"],
                        value="Sick",
                        label="Reason",
                    ).classes("w-full")
                    ladder_box = (
                        ui.textarea(value="Build ladder to rank order-in candidates.")
                        .classes("w-full")
                        .props("readonly outlined dense dark rows=8")
                    )
                    cover_state: dict = {"eligible": [], "oid": None, "date": format_date(today_local())}

                    def build_ladder():
                        oid = names.get(off_sel.value)
                        if not oid:
                            return
                        r = build_callout_ladder(
                            int(oid),
                            format_date(today_local()),
                            reason=reason.value or "Sick",
                        )
                        ladder_box.value = r.get("text") or r.get("message") or ""
                        cover_state["eligible"] = r.get("eligible") or []
                        cover_state["oid"] = oid
                        if r.get("success"):
                            ui.notify(r.get("message", "Ladder ready"), type="positive")
                        else:
                            ui.notify(r.get("message", "Failed"), type="negative")

                    def order_first():
                        elig = cover_state.get("eligible") or []
                        orig = cover_state.get("oid")
                        if not elig or not orig:
                            ui.notify("Build ladder first", type="warning")
                            return
                        cover_id = int(elig[0]["officer_id"])
                        uid = (session.current_user() or {}).get("id")
                        r = execute_callout_order(
                            int(orig),
                            format_date(today_local()),
                            cover_id,
                            reason=reason.value or "Sick",
                            user_id=uid,
                        )
                        ui.notify(
                            r.get("message", "Done") if r.get("success") else r.get("message", "Failed"),
                            type="positive" if r.get("success") else "negative",
                        )
                        refresh()

                    with ui.row().classes("gap-2 flex-wrap"):
                        ui.button("Build ladder", on_click=build_ladder).classes("btn-ghost").props(
                            "no-caps outline dense"
                        )
                        ui.button("Order #1 eligible", on_click=order_first).classes("btn-primary").props(
                            "no-caps unelevated dense"
                        )
                    eq = get_ot_equity_sort_enabled()

                    def toggle_eq(e):
                        uid = (session.current_user() or {}).get("id")
                        set_ot_equity_sort_enabled(bool(e.value), user_id=uid)
                        ui.notify(f"OT equity sort: {'ON' if e.value else 'OFF'}", type="info")

                    ui.switch("OT equity sort on callout", value=eq, on_change=toggle_eq)

                # Day coverage + click-to-fill gaps
                with panel("Day coverage (evaluate_day_coverage)", glow=True):
                    cov = live_day_coverage_report(today_local())
                    ui.textarea(value=cov.get("text") or cov.get("message") or "").classes("w-full").props(
                        "readonly outlined dense dark rows=6"
                    )
                    fill = gap_board_with_fill_actions(reference=today_local())
                    ladder = (fill.get("ladder") or {}) if isinstance(fill, dict) else {}
                    elig = ladder.get("eligible") or []
                    if elig and fill.get("primary_officer_id"):
                        cover_opts = {
                            int(c["officer_id"]): f"{c.get('name')} · rank {c.get('seniority_rank')}"
                            for c in elig[:12]
                            if c.get("officer_id") is not None
                        }
                        if cover_opts:
                            csel = (
                                ui.select(cover_opts, value=next(iter(cover_opts)), label="Fill with")
                                .classes("w-full")
                                .props("dark dense emit-value map-options")
                            )

                            def do_fill():
                                uid = (session.current_user() or {}).get("id")
                                r = fill_gap_click(
                                    int(fill["primary_officer_id"]),
                                    int(csel.value),
                                    today_local(),
                                    reason="Ops Desk gap click-to-fill",
                                    user_id=uid,
                                )
                                ui.notify(
                                    r.get("message", "Done") if r.get("success") else r.get("message", "Failed"),
                                    type="positive" if r.get("success") else "negative",
                                )
                                refresh()

                            ui.button("Click-to-fill (order-in cover)", on_click=do_fill).classes(
                                "btn-primary q-mt-sm"
                            ).props("no-caps unelevated dense")

                # Gaps + open shifts + payroll exceptions
                with ui.element("div").classes("grid-2"):
                    with panel("Coverage gaps"):
                        gaps = board.get("gaps") or []
                        if not gaps:
                            ui.label("No gap board rows.").classes("text-xs text-gray-500")
                        for g in gaps[:12]:
                            if isinstance(g, dict):
                                ui.label(g.get("message") or g.get("label") or str(g)[:120]).classes("text-xs")
                            else:
                                ui.label(str(g)[:120]).classes("text-xs")
                    with panel("Payroll exceptions"):
                        ex = board.get("payroll_exceptions") or []
                        if not ex:
                            ui.label("No exceptions this period.").classes("text-xs text-gray-500")
                        for item in ex[:12]:
                            ui.label(item.get("message") or item.get("kind")).classes("text-xs")

                # Off-duty bump policy (load_off_duty_bump_policy parity)
                with panel("Off-duty bump policy", glow=False):
                    settings = get_off_duty_bump_settings_for_ui()
                    pol = settings.get("policy") or load_off_duty_bump_policy().to_dict()
                    allow = ui.switch("Allow off-duty call-in for bumps", value=bool(pol.get("allow_off_duty")))
                    same_sq = ui.switch("Same squad only", value=bool(pol.get("same_squad_only", True)))
                    on_first = ui.switch("Prefer on-duty first", value=bool(pol.get("prefer_on_duty_first", True)))
                    crit_ids = [c.get("id") for c in (settings.get("criteria_options") or []) if c.get("selected")]
                    crit_labels = {
                        c.get("id"): CRITERION_LABELS.get(c.get("id"), c.get("id"))
                        for c in (settings.get("criteria_options") or [])
                    }
                    crit_sel = (
                        ui.select(
                            crit_labels,
                            value=crit_ids or list(crit_labels.keys())[:1],
                            label="Criteria (multi)",
                            multiple=True,
                        )
                        .classes("w-full")
                        .props("dark dense emit-value map-options")
                    )

                    def save_pol():
                        uid = (session.current_user() or {}).get("id")
                        val = crit_sel.value
                        if isinstance(val, str):
                            val = [val]
                        r = save_off_duty_bump_policy(
                            {
                                "allow_off_duty": bool(allow.value),
                                "same_squad_only": bool(same_sq.value),
                                "prefer_on_duty_first": bool(on_first.value),
                                "criteria": list(val or []),
                            },
                            user_id=uid,
                        )
                        ui.notify(r.get("message", "Saved"), type="positive" if r.get("success") else "negative")

                    ui.button("Save off-duty policy", on_click=save_pol).classes("btn-ghost q-mt-sm").props(
                        "no-caps outline dense"
                    )

                # Notify strip
                outbox = board.get("notify_outbox") or {}
                with panel("Notify outbox"):
                    by = outbox.get("by_status") or {}
                    ui.label(
                        f"Total {outbox.get('total', 0)} · queued {by.get('queued', 0)} · "
                        f"sent {by.get('sent', 0)} · failed {by.get('failed', 0)}"
                    ).classes("text-sm")
                    ui.label("Live SMS/email only with real Twilio/SMTP creds — see Notify Channels.").classes(
                        "text-xs text-gray-500"
                    )
                    ui.button("Open channels", on_click=lambda: ui.navigate.to("/channels")).props("dense no-caps flat")

                with panel("Policy pack (CBA export / import)", glow=True):
                    ui.label(
                        "Export department CBA/settings pack as JSON; import to restore knobs on another host."
                    ).classes("text-xs q-mb-sm").style("color: var(--dim)")

                    def do_export():
                        uid = (session.current_user() or {}).get("id")
                        r = export_policy_pack(label="ops-desk", user_id=uid)
                        ui.notify(
                            r.get("message") or r.get("path") or "Exported",
                            type="positive" if r.get("success") else "negative",
                        )

                    pack_path = ui.input(
                        label="Import path (JSON file on server)",
                        placeholder=r"data\exports\cba_policy_pack_….json",
                    ).classes("w-full")
                    dry = ui.switch("Dry-run import (validate only)", value=True)

                    def do_import():
                        p = (pack_path.value or "").strip()
                        if not p:
                            ui.notify("Enter policy pack file path", type="warning")
                            return
                        uid = (session.current_user() or {}).get("id")
                        r = import_policy_pack(p, user_id=uid, dry_run=bool(dry.value))
                        ui.notify(
                            r.get("message") or ("OK" if r.get("success") else "Failed"),
                            type="positive" if r.get("success") else "negative",
                            multi_line=True,
                        )

                    # Optional browser upload → write temp → import
                    def on_upload(e):
                        try:
                            from pathlib import Path

                            from paths import data_path

                            raw = e.content.read() if hasattr(e, "content") else None
                            if raw is None and hasattr(e, "file"):
                                raw = e.file.read()
                            name = getattr(e, "name", None) or "policy_pack_upload.json"
                            dest = Path(data_path("imports")) / f"policy_{name}"
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            dest.write_bytes(raw if isinstance(raw, (bytes, bytearray)) else bytes(raw or b""))
                            pack_path.value = str(dest)
                            ui.notify(f"Uploaded → {dest}", type="info")
                        except Exception as exc:
                            ui.notify(f"Upload failed: {exc}", type="negative")

                    try:
                        ui.upload(on_upload=on_upload, auto_upload=True, max_files=1).props(
                            "accept=.json dense"
                        ).classes("q-mb-sm")
                    except Exception:
                        pass

                    with ui.row().classes("gap-2 flex-wrap"):
                        ui.button("Export CBA policy pack JSON", on_click=do_export).classes("btn-ghost").props(
                            "no-caps outline dense"
                        )
                        ui.button("Import policy pack", on_click=do_import).classes("btn-primary").props(
                            "no-caps unelevated dense"
                        )

                with ui.row().classes("gap-2 q-mt-sm"):
                    ui.button("Refresh board", on_click=refresh).classes("btn-primary").props(
                        "no-caps unelevated dense"
                    )
                    ui.button("Time off", on_click=lambda: ui.navigate.to("/time-off")).props("dense no-caps flat")
                    ui.button("Live schedule", on_click=lambda: ui.navigate.to("/live-schedule")).props(
                        "dense no-caps flat"
                    )

        refresh()

    layout("ops_desk", body)


def _quick_resolve(request_id: int, action: str, refresh_cb) -> None:
    uid = (session.current_user() or {}).get("id")
    r = resolve_manual_review(request_id, action, user_id=uid)
    ui.notify(
        r.get("message", "Done") if r.get("success") else r.get("message", "Failed"),
        type="positive" if r.get("success") else "warning",
    )
    refresh_cb()


def _show_diagnose(request_id: int, refresh_cb) -> None:
    d = diagnose_manual_review(request_id)
    if not d.get("success"):
        ui.notify(d.get("message", "Not found"), type="negative")
        return
    with ui.dialog() as dlg, ui.card().classes("w-full").style("max-width:560px;background:#0c1220;color:#e2e8f0"):
        ui.label(f"Diagnose #{request_id}").classes("text-base font-semibold")
        ui.label(d.get("text") or "").classes("text-xs").style("white-space:pre-wrap;color:#94a3b8")
        eligible = (d.get("callout") or {}).get("eligible") or []
        cover_opts = {0: "— first eligible —"}
        for c in eligible[:12]:
            cover_opts[int(c["officer_id"])] = f"{c.get('name')} · rank {c.get('seniority_rank')}"
        cover_sel = (
            ui.select(cover_opts, value=0, label="Cover officer")
            .classes("w-full")
            .props("dark dense emit-value map-options")
        )
        plan_opts = {0: "— best override —"}
        for p in d.get("plans") or []:
            plan_opts[int(p["index"])] = f"Plan {p['index']}: {p.get('message', '')[:48]}"
        plan_sel = (
            ui.select(plan_opts, value=0, label="Ranked plan")
            .classes("w-full")
            .props("dark dense emit-value map-options")
        )
        notes = ui.input("Notes").classes("w-full")

        def run(action: str):
            uid = (session.current_user() or {}).get("id")
            cid = int(cover_sel.value or 0) or None
            pidx = int(plan_sel.value or 0) or None
            r = resolve_manual_review(
                request_id,
                action,
                cover_officer_id=cid,
                plan_index=pidx,
                admin_notes=(notes.value or "").strip(),
                user_id=uid,
            )
            ui.notify(
                r.get("message", "Done") if r.get("success") else r.get("message", "Failed"),
                type="positive" if r.get("success") else "warning",
            )
            dlg.close()
            refresh_cb()

        with ui.row().classes("gap-2 flex-wrap"):
            ui.button("Override approve", on_click=lambda: run("approve_override")).classes("btn-primary").props(
                "no-caps unelevated dense"
            )
            ui.button("Order-in", on_click=lambda: run("order_in")).props("no-caps outline dense")
            ui.button("Partial cover", on_click=lambda: run("partial_cover")).props("no-caps outline dense")
            ui.button("Reject", on_click=lambda: run("reject")).classes("btn-danger").props("no-caps outline dense")
            ui.button("Close", on_click=dlg.close).props("flat dense no-caps")
    dlg.open()
