"""Shift bidding — annual/cycle bid events (Snap/Aladtec pattern).

Logic lives in logic/bidding.py. This page is Chronos wiring only.
"""

from __future__ import annotations

from nicegui import ui

from gui import session
from gui.shell import layout, page_header, panel
from gui.ui_patterns import empty_state
from logic import (
    auto_close_expired_shift_bid_events,
    cancel_shift_bid_event,
    create_shift_bid_event,
    finalize_shift_bid_event,
    get_officer_shift_bid_awards,
    get_officers_by_seniority,
    get_shift_bid_event,
    get_shift_bid_events,
    get_shift_bid_participation_report,
    preview_shift_bid_awards,
    publish_shift_bid_event,
    reassign_shift_bid_option,
    submit_shift_bid_rankings,
    update_shift_bid_assignments,
)
from validators import format_date


def render_bidding() -> None:
    def body() -> None:
        page_header(
            "Shift Bidding",
            "Season workflow: Draft → Publish → Officers rank → Preview awards → Finalize",
            kicker="Chronos Command · CBA pattern",
        )
        # Season wizard strip
        ui.html(
            '<div class="kpi-row q-mb-md">'
            '<div class="kpi g"><div class="kpi-l">1 · Draft</div><div class="kpi-v" style="font-size:16px">Create event</div></div>'
            '<div class="kpi"><div class="kpi-l">2 · Publish</div><div class="kpi-v" style="font-size:16px">Open rankings</div></div>'
            '<div class="kpi"><div class="kpi-l">3 · Rank</div><div class="kpi-v" style="font-size:16px">Officers bid</div></div>'
            '<div class="kpi"><div class="kpi-l">4 · Award</div><div class="kpi-v" style="font-size:16px">Preview · Finalize</div></div>'
            "</div>",
            sanitize=False,
        )
        host = ui.element("div")

        def refresh():
            host.clear()
            with host:
                if session.can("shift_bids.submit") or session.is_officer():
                    _officer_bid_form()
                _event_list()

        with ui.row().classes("gap-2 q-mb-md flex-wrap"):
            ui.button("Refresh", on_click=refresh).classes("btn-ghost").props("no-caps outline dense")
            if session.can("shift_bids.manage"):

                def auto_close():
                    n = auto_close_expired_shift_bid_events()
                    ui.notify(f"Closed {n} expired bid event(s)", type="positive" if n else "info")
                    refresh()

                ui.button("Auto-close expired", on_click=auto_close).classes("btn-ghost").props("no-caps outline dense")

        if session.can("shift_bids.manage"):
            with panel("Create bid season (supervisor)", glow=True):
                title = ui.input(label="Season title", value="Annual shift bid").classes("w-full")
                begins = ui.input(label="Shifts begin (M/D/YYYY or ISO)", value="8/1/2026").classes("w-full")
                due = ui.input(label="Bids due by", value="7/25/2026 17:00").classes("w-full")
                starts = ui.input(
                    label="Shift starts (comma)",
                    value="06:00,10:00,15:00,19:00",
                ).classes("w-full")
                n_shifts = ui.input(label="Number of shifts", value="4").classes("w-full")
                length = ui.input(label="Shift length (hours)", value="8").classes("w-full")
                notes = ui.input(label="Notes / CBA reference").classes("w-full")
                notify_on_pub = ui.switch("Notify officers when published (email/SMS if enabled)", value=True)

                def create():
                    uid = (session.current_user() or {}).get("id")
                    result = create_shift_bid_event(
                        title=(title.value or "Shift bid").strip(),
                        number_of_shifts=(n_shifts.value or "4").strip(),
                        shift_length=(length.value or "8").strip(),
                        rotation="A",
                        shift_start_times=(starts.value or "").strip(),
                        shifts_begin=(begins.value or "").strip(),
                        bids_due_by=(due.value or "").strip(),
                        notes=(notes.value or "").strip(),
                        user_id=uid,
                    )
                    if result.get("success"):
                        ui.notify(f"Draft bid event #{result.get('event_id')}", type="positive")
                        refresh()
                    else:
                        ui.notify(result.get("message", "Create failed"), type="negative")

                def create_and_publish():
                    uid = (session.current_user() or {}).get("id")
                    result = create_shift_bid_event(
                        title=(title.value or "Shift bid").strip(),
                        number_of_shifts=(n_shifts.value or "4").strip(),
                        shift_length=(length.value or "8").strip(),
                        rotation="A",
                        shift_start_times=(starts.value or "").strip(),
                        shifts_begin=(begins.value or "").strip(),
                        bids_due_by=(due.value or "").strip(),
                        notes=(notes.value or "").strip(),
                        user_id=uid,
                    )
                    if not result.get("success"):
                        ui.notify(result.get("message", "Create failed"), type="negative")
                        return
                    eid = result.get("event_id")
                    pub = publish_shift_bid_event(eid, user_id=uid)
                    if pub.get("success") and notify_on_pub.value:
                        try:
                            from logic import dispatch_template, get_officers_by_seniority

                            oids = [o["id"] for o in (get_officers_by_seniority() or []) if o.get("active", 1)]
                            dispatch_template(
                                "shift_bid_open",
                                officer_ids=oids[:80],
                                user_id=uid,
                                title=(title.value or "Shift bid").strip(),
                                due=(due.value or "").strip(),
                            )
                        except Exception:
                            pass
                    ui.notify(
                        pub.get("message", "Published") if pub.get("success") else pub.get("message", "Fail"),
                        type="positive" if pub.get("success") else "negative",
                    )
                    refresh()

                with ui.row().classes("gap-2 q-mt-sm flex-wrap"):
                    ui.button("1 · Create draft", on_click=create).classes("btn-ghost").props("no-caps outline")
                    ui.button("1+2 · Create & publish season", on_click=create_and_publish).classes(
                        "btn-primary"
                    ).props("no-caps unelevated")

        refresh()

    layout("bidding", body)


def _officer_bid_form() -> None:
    """Submit preference ranks for open bid events (Aladtec/Snap officer participation)."""
    oid = session.linked_officer_id()
    if not oid:
        if session.is_officer():
            ui.html(
                '<div class="alert alert-warn">Link an officer profile to submit bid rankings.</div>',
                sanitize=False,
            )
        return
    open_events = [
        e
        for e in (get_shift_bid_events(status="open", officer_id=oid, limit=20) or [])
        if (e.get("status") or "").lower() == "open"
    ]
    # Fallback without status filter
    if not open_events:
        open_events = [
            e
            for e in (get_shift_bid_events(include_drafts=False, limit=20) or [])
            if (e.get("status") or "").lower() == "open"
        ]
    if not open_events:
        empty_state(
            "No open bid seasons",
            "When a supervisor publishes a season, rank your preferred shifts here.",
        )
        return

    with panel("Submit my bid rankings", glow=True):
        labels = {f"#{e['id']} · {e.get('title') or 'Bid'}": e["id"] for e in open_events}
        pick = ui.select(list(labels.keys()), value=list(labels.keys())[0], label="Open bid event").classes("w-full")
        form_host = ui.element("div")
        rank_inputs: dict = {"widgets": []}

        def load_options():
            form_host.clear()
            rank_inputs["widgets"] = []
            eid = labels.get(pick.value)
            if not eid:
                return
            try:
                detail = get_shift_bid_event(eid) or {}
            except Exception as exc:
                with form_host:
                    ui.label(f"Unable to load options: {exc}").classes("text-sm text-red-400")
                return
            options = detail.get("options") or []
            with form_host:
                if not options:
                    ui.label("No options on this event yet (publish creates slots).").classes("text-sm text-gray-500")
                    return
                ui.label("Enter preference rank for each option (1 = most preferred). Leave blank to skip.").classes(
                    "text-xs text-gray-500 q-mb-sm"
                )
                for opt in options:
                    with ui.row().classes("items-center gap-2 w-full"):
                        ui.label(opt.get("label") or f"Option {opt.get('id')}").classes("text-sm grow")
                        r = ui.number(
                            label="Rank",
                            value=None,
                            min=1,
                            max=max(len(options), 1),
                            format="%.0f",
                        ).classes("w-24")
                        rank_inputs["widgets"].append((opt["id"], r))

        pick.on("update:model-value", lambda _: load_options())
        load_options()

        def submit():
            eid = labels.get(pick.value)
            if not eid:
                return
            rankings = []
            for opt_id, widget in rank_inputs["widgets"]:
                val = widget.value
                if val is None or val == "":
                    continue
                try:
                    rankings.append({"option_id": int(opt_id), "preference_rank": int(val)})
                except (TypeError, ValueError):
                    ui.notify("Ranks must be whole numbers", type="negative")
                    return
            if not rankings:
                ui.notify("Enter at least one rank", type="warning")
                return
            uid = (session.current_user() or {}).get("id")
            r = submit_shift_bid_rankings(eid, oid, rankings, user_id=uid)
            ui.notify(
                r.get("message", "Submitted") if r.get("success") else r.get("message", "Failed"),
                type="positive" if r.get("success") else "negative",
            )

        ui.button("Submit rankings", on_click=submit).classes("btn-primary q-mt-sm").props("no-caps unelevated")


def _event_list() -> None:
    include_drafts = session.can("shift_bids.manage")
    events = get_shift_bid_events(include_drafts=include_drafts, limit=30)
    if not events:
        empty_state(
            "No bid events yet",
            "Supervisors create a draft, publish, then finalize awards (annual/cycle bidding).",
        )
        return

    # Officer awards strip
    oid_self = session.linked_officer_id()
    if oid_self:
        try:
            awards = get_officer_shift_bid_awards(int(oid_self)) or []
            if isinstance(awards, dict):
                awards = awards.get("awards") or awards.get("rows") or []
            if awards:
                with panel("My bid awards", glow=False):
                    for a in (awards if isinstance(awards, list) else [])[:8]:
                        if isinstance(a, dict):
                            ui.label(
                                f"{a.get('event_title') or a.get('title') or 'Event'} · "
                                f"{a.get('option_label') or a.get('shift') or a.get('status') or a}"
                            ).classes("text-sm q-mb-xs")
                        else:
                            ui.label(str(a)[:100]).classes("text-sm")
        except Exception:
            pass

    with panel(f"Bid events · {len(events)}"):
        for ev in events:
            with ui.element("div").classes("data-row"):
                with ui.element("div").classes("grow"):
                    ui.label(f"#{ev.get('id')} · {ev.get('title') or 'Bid'} · {ev.get('status') or '—'}").classes(
                        "text-sm font-semibold"
                    )
                    begin = format_date(ev.get("shifts_begin") or "") if ev.get("shifts_begin") else "—"
                    ui.label(
                        f"Begins {begin} · Due {ev.get('bids_due_by') or '—'} · "
                        f"Options {ev.get('option_count', 0)} · Bids {ev.get('respondent_count', 0)}"
                    ).classes("text-xs text-gray-500")
                if session.can("shift_bids.manage"):
                    with ui.row().classes("gap-1 flex-wrap"):
                        st = (ev.get("status") or "").lower()
                        if st == "draft":

                            def pub(eid=ev["id"]):
                                uid = (session.current_user() or {}).get("id")
                                r = publish_shift_bid_event(eid, user_id=uid)
                                ui.notify(
                                    r.get("message", "Published") if r.get("success") else r.get("message", "Fail"),
                                    type="positive" if r.get("success") else "negative",
                                )
                                ui.navigate.to("/bidding")

                            ui.button("Publish", on_click=pub).classes("btn-primary").props("dense no-caps unelevated")

                        if st in ("draft", "open", "published", "bidding"):

                            def cancel(eid=ev["id"]):
                                uid = (session.current_user() or {}).get("id")
                                r = cancel_shift_bid_event(int(eid), user_id=uid)
                                ui.notify(
                                    r.get("message", "Cancelled") if r.get("success") else r.get("message", "Fail"),
                                    type="info" if r.get("success") else "negative",
                                )
                                if r.get("success"):
                                    ui.navigate.to("/bidding")

                            ui.button("Cancel", on_click=cancel).classes("btn-danger").props("dense no-caps outline")

                        if st in ("open", "published", "closed", "bidding", "finalized", "awarded"):

                            def prev(eid=ev["id"]):
                                r = preview_shift_bid_awards(eid)
                                if not r.get("success") and "awards" not in r:
                                    ui.notify(r.get("message", "Preview failed"), type="warning")
                                    return
                                awards = r.get("awards") or r.get("preview") or r.get("rows") or []
                                lines = [str(a)[:120] for a in (awards[:8] if isinstance(awards, list) else [r])]
                                ui.notify("\n".join(lines) or str(r)[:300], type="info", multi_line=True)

                            def report(eid=ev["id"]):
                                """Seniority fairness participation (Snap/CBA bid season pattern)."""
                                r = get_shift_bid_participation_report(eid) or {}
                                if isinstance(r, dict) and r.get("success") is False:
                                    ui.notify(r.get("message", "Report failed"), type="warning")
                                    return
                                rows = (
                                    r.get("participants") or r.get("officers") or r.get("rows") or r.get("bids") or []
                                )
                                if isinstance(r, list):
                                    rows = r
                                summary = r.get("summary") or r.get("message") or ""
                                if not rows and summary:
                                    ui.notify(str(summary)[:400], type="info")
                                    return
                                if not rows:
                                    ui.notify(str(r)[:400], type="info")
                                    return
                                lines = []
                                for row in rows[:20]:
                                    if isinstance(row, dict):
                                        lines.append(
                                            f"{row.get('officer_name') or row.get('name') or row.get('officer_id')} · "
                                            f"rank/sen {row.get('seniority_rank') or row.get('seniority') or '—'} · "
                                            f"{row.get('status') or row.get('submitted') or row.get('bid_count') or ''}"
                                        )
                                    else:
                                        lines.append(str(row)[:100])
                                with (
                                    ui.dialog() as dlg,
                                    ui.card().classes("w-full").style("min-width:min(440px,94vw);max-width:560px"),
                                ):
                                    ui.label(f"Participation report · event #{eid}").classes(
                                        "text-sm font-semibold q-mb-sm"
                                    )
                                    if summary:
                                        ui.label(str(summary)).classes("text-xs text-gray-500 q-mb-sm")
                                    ui.textarea(value="\n".join(lines)).classes("w-full").props(
                                        "readonly outlined dense dark rows=14"
                                    )
                                    ui.button("Close", on_click=dlg.close).classes("btn-ghost q-mt-sm").props(
                                        "no-caps flat dense"
                                    )
                                dlg.open()

                            def apply_preview(eid=ev["id"]):
                                """Write preview awards via update_shift_bid_assignments (supervisor override path)."""
                                prev_r = preview_shift_bid_awards(eid) or {}
                                awards = (
                                    prev_r.get("awards")
                                    or prev_r.get("preview")
                                    or prev_r.get("assignments")
                                    or prev_r.get("rows")
                                    or []
                                )
                                assignments = []
                                for a in awards if isinstance(awards, list) else []:
                                    if not isinstance(a, dict):
                                        continue
                                    opt = a.get("option_id") or a.get("option") or a.get("shift_option_id")
                                    off = a.get("officer_id") or a.get("awarded_officer_id")
                                    if opt is None:
                                        continue
                                    try:
                                        assignments.append(
                                            {
                                                "option_id": int(opt),
                                                "officer_id": int(off) if off is not None else None,
                                            }
                                        )
                                    except (TypeError, ValueError):
                                        continue
                                if not assignments:
                                    ui.notify(
                                        "No preview assignments to apply — finalize or adjust ranks first",
                                        type="warning",
                                    )
                                    return
                                uid = (session.current_user() or {}).get("id")
                                r = update_shift_bid_assignments(eid, assignments, user_id=uid)
                                ui.notify(
                                    r.get("message", "Assignments updated")
                                    if r.get("success")
                                    else r.get("message", "Update failed"),
                                    type="positive" if r.get("success") else "negative",
                                )

                            def fin(eid=ev["id"]):
                                uid = (session.current_user() or {}).get("id")
                                r = finalize_shift_bid_event(eid, user_id=uid)
                                ui.notify(
                                    r.get("message", "Finalized") if r.get("success") else r.get("message", "Fail"),
                                    type="positive" if r.get("success") else "negative",
                                )
                                ui.navigate.to("/bidding")

                            def reassign_ui(eid=ev["id"], est=st):
                                """Manual reassign one option slot (finalized events only)."""
                                if est != "finalized" and est != "awarded":
                                    ui.notify(
                                        "Reassign works after Finalize (supervisor override of awards)",
                                        type="warning",
                                    )
                                detail = get_shift_bid_event(int(eid)) or {}
                                opts = detail.get("options") or []
                                if not opts:
                                    ui.notify("No options on this event", type="warning")
                                    return
                                officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
                                onames = ["(clear award)"] + [o["name"] for o in officers]
                                omap = {o["name"]: o["id"] for o in officers}
                                olabels = {
                                    f"#{o.get('id')} · {o.get('label') or o.get('shift_start') or 'opt'} · "
                                    f"award={o.get('awarded_officer_id') or '—'}": o["id"]
                                    for o in opts
                                    if o.get("id") is not None
                                }
                                if not olabels:
                                    ui.notify("No option ids", type="warning")
                                    return
                                with (
                                    ui.dialog() as dlg,
                                    ui.card().classes("w-full").style("min-width:min(420px,94vw);max-width:520px"),
                                ):
                                    ui.label(f"Reassign option · event #{eid} (finalized)").classes(
                                        "text-sm font-semibold q-mb-sm"
                                    )
                                    opick = ui.select(
                                        list(olabels.keys()),
                                        value=list(olabels.keys())[0],
                                        label="Option",
                                    ).classes("w-full")
                                    off_pick = ui.select(onames, value=onames[0], label="Officer").classes("w-full")

                                    def do_re():
                                        oid_opt = olabels.get(opick.value)
                                        if oid_opt is None:
                                            return
                                        off_id = None
                                        if off_pick.value and off_pick.value != "(clear award)":
                                            off_id = omap.get(off_pick.value)
                                        uid = (session.current_user() or {}).get("id")
                                        r = reassign_shift_bid_option(int(eid), int(oid_opt), off_id, user_id=uid)
                                        ui.notify(
                                            r.get("message", "Reassigned")
                                            if r.get("success")
                                            else r.get("message", "Failed"),
                                            type="positive" if r.get("success") else "negative",
                                        )
                                        if r.get("success"):
                                            dlg.close()
                                            ui.navigate.to("/bidding")

                                    ui.button("Apply reassignment", on_click=do_re).classes(
                                        "btn-primary q-mt-sm"
                                    ).props("no-caps unelevated dense")
                                    ui.button("Close", on_click=dlg.close).classes("btn-ghost").props(
                                        "no-caps flat dense"
                                    )
                                dlg.open()

                            ui.button("Preview", on_click=prev).props("dense no-caps flat")
                            ui.button("Participation", on_click=report).props("dense no-caps flat")
                            ui.button("Apply preview", on_click=apply_preview).props("dense no-caps flat")
                            ui.button("Reassign slot", on_click=reassign_ui).props("dense no-caps flat")
                            ui.button("Finalize", on_click=fin).classes("btn-ghost").props("dense no-caps outline")
