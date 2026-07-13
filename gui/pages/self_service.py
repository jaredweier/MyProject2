"""LE self-service surfaces (open shift vacancy board).

Patterns from public-safety WFM products (Aladtec, Snap, Softworks) — ideas only.
"""

from __future__ import annotations

from nicegui import ui

from config import DATE_INPUT_HINT, OFFICER_SQUAD_OPTIONS
from gui import session
from gui.clock import today_local
from gui.shell import layout, page_header, panel
from logic import (
    create_open_shift,
    fill_open_shift,
    get_officers_by_seniority,
    get_open_shifts,
    rank_open_shift_candidates,
)
from logic.certifications import officer_meets_shift_cert_requirements
from logic.staffing_config import get_active_shift_times, get_officer_shift_options
from validators import format_date, parse_date


def render_open_shifts() -> None:
    def body() -> None:
        page_header(
            "Open Shifts",
            "Vacancy board · post coverage holes · claim or assign",
            kicker="Self-service · LE pattern",
        )
        host = ui.element("div")

        def refresh():
            host.clear()
            with host:
                _board()

        with ui.row().classes("gap-2 q-mb-md flex-wrap"):
            ui.button("Refresh board", on_click=refresh).classes("btn-ghost").props("no-caps outline dense")

            def run_digest():
                try:
                    from scripts.open_shift_digest import run_open_shift_digest

                    code = run_open_shift_digest(dry_run=False)
                    ui.notify(
                        "Vacancy digest sent to active officers" if code == 0 else "Digest finished with issues",
                        type="positive" if code == 0 else "warning",
                    )
                except Exception as exc:
                    ui.notify(str(exc), type="negative")

            if session.can("open_shifts.manage") or session.can("notifications.manage"):
                ui.button("Notify officers (digest)", on_click=run_digest).classes("btn-primary").props(
                    "no-caps unelevated dense"
                )

        can_post = session.can("open_shifts.manage") or session.can("schedule.updated.edit")
        if can_post:
            with panel("Post open shift (supervisor)", glow=True):
                starts: list[str] = []
                end_map: dict[str, str] = {}
                try:
                    for _k, (s, e) in get_active_shift_times().items():
                        starts.append(s)
                        end_map[s] = e
                except Exception:
                    starts = ["06:00", "10:00", "15:00", "19:00"]
                if not starts:
                    try:
                        starts = list(get_officer_shift_options()) or ["06:00"]
                    except Exception:
                        starts = ["06:00"]
                d_in = ui.input(
                    label=f"Date ({DATE_INPUT_HINT})",
                    value=format_date(today_local()),
                    placeholder=format_date(today_local()),
                ).classes("w-full")
                start = ui.select(starts, value=starts[-1], label="Shift start").classes("w-full")
                end = ui.input(
                    label="Shift end (HH:MM)",
                    value=end_map.get(starts[-1], "06:00"),
                ).classes("w-full")
                squad = ui.select(
                    ["Any"] + list(OFFICER_SQUAD_OPTIONS),
                    value="Any",
                    label="Squad",
                ).classes("w-full")
                notes = ui.input(label="Notes", value="Coverage needed").classes("w-full")

                def post():
                    dt = parse_date((d_in.value or "").strip())
                    if not dt:
                        ui.notify("Invalid date", type="negative")
                        return
                    se = (end.value or "").strip() or end_map.get(start.value, "06:00")
                    sq = None if squad.value == "Any" else squad.value
                    uid = (session.current_user() or {}).get("id")
                    result = create_open_shift(
                        dt.isoformat(),
                        start.value,
                        se,
                        squad=sq,
                        notes=(notes.value or "").strip(),
                        user_id=uid,
                    )
                    if result.get("success"):
                        ui.notify(f"Posted open shift #{result.get('shift_id')}", type="positive")
                        refresh()
                    else:
                        ui.notify(result.get("message", "Failed to post"), type="negative")

                ui.button("Post vacancy", on_click=post).classes("btn-primary q-mt-sm").props("no-caps unelevated")

        refresh()

    layout("open_shifts", body)


def _board() -> None:
    oid = session.linked_officer_id()
    if session.is_officer() and oid:
        rows = get_open_shifts(status="open", limit=50, officer_id=oid)
    else:
        rows = get_open_shifts(status="open", limit=50)

    if not rows:
        ui.html(
            '<div class="alert alert-ok">No open vacancies. Supervisors post coverage holes above '
            "(Aladtec/Snap-style open-shift marketplace).</div>",
            sanitize=False,
        )
        return

    with panel(f"Open vacancies · {len(rows)}", glow=True):
        for sh in rows:
            with ui.element("div").classes("data-row"):
                with ui.element("div").classes("grow"):
                    d = format_date(sh.get("shift_date") or "")
                    ui.label(
                        f"{d} · {sh.get('shift_start') or '—'}–{sh.get('shift_end') or '—'} · "
                        f"Squad {sh.get('squad') or 'Any'}"
                    ).classes("text-sm font-semibold")
                    ui.label(sh.get("notes") or "No notes").classes("text-xs text-gray-500")

                if session.is_officer() and oid:
                    start_band = sh.get("shift_start") or ""
                    try:
                        ok_cert, cert_msg = officer_meets_shift_cert_requirements(oid, start_band)
                    except Exception:
                        ok_cert, cert_msg = True, ""
                    if not ok_cert:
                        ui.label(f"Cert: {cert_msg or 'requirements not met'}").classes("text-xs text-amber-400")

                    def claim(sid=sh["id"], officer=oid, band=start_band):
                        try:
                            meets, msg = officer_meets_shift_cert_requirements(officer, band or "")
                        except Exception:
                            meets, msg = True, ""
                        if not meets:
                            ui.notify(msg or "Missing required certification for this band", type="warning")
                            return
                        uid = (session.current_user() or {}).get("id")
                        result = fill_open_shift(sid, officer, user_id=uid)
                        if result.get("success"):
                            ui.notify("Shift claimed", type="positive")
                            ui.navigate.to("/open-shifts")
                        else:
                            ui.notify(result.get("message", "Claim failed"), type="negative")

                    claim_btn = (
                        ui.button("Claim", on_click=claim).classes("btn-primary").props("dense no-caps unelevated")
                    )
                    if start_band and not ok_cert:
                        claim_btn.props("disable")

        if not session.is_officer() and (session.can("open_shifts.manage") or session.can("schedule.updated.edit")):
            officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
            if officers:
                ui.separator()
                ui.label("Supervisor assign to officer").classes("text-xs text-gray-500 q-mb-xs")
                names = [o["name"] for o in officers]
                omap = {o["name"]: o["id"] for o in officers}
                labels = [f"#{r['id']} · {format_date(r.get('shift_date'))} · {r.get('shift_start')}" for r in rows]
                id_by_label = {
                    f"#{r['id']} · {format_date(r.get('shift_date'))} · {r.get('shift_start')}": r["id"] for r in rows
                }
                pick = ui.select(names, value=names[0], label="Officer").classes("w-full")
                vac = ui.select(labels, value=labels[0], label="Vacancy").classes("w-full")

                def assign():
                    off_id = omap.get(pick.value)
                    sid = id_by_label.get(vac.value)
                    if not off_id or not sid:
                        ui.notify("Select vacancy and officer", type="warning")
                        return
                    uid = (session.current_user() or {}).get("id")
                    result = fill_open_shift(int(sid), int(off_id), user_id=uid)
                    ok = result.get("success")
                    ui.notify(
                        result.get("message", "Assigned" if ok else "Failed"),
                        type="positive" if ok else "negative",
                    )
                    if ok:
                        ui.navigate.to("/open-shifts")

                ui.button("Assign selected", on_click=assign).classes("btn-ghost q-mt-sm").props(
                    "no-caps outline dense"
                )

                def show_rank():
                    sid = id_by_label.get(vac.value)
                    if not sid:
                        ui.notify("Select a vacancy", type="warning")
                        return
                    r = rank_open_shift_candidates(int(sid), limit=8) or {}
                    cands = r.get("candidates") or []
                    if not cands:
                        ui.notify(r.get("message") or "No ranked candidates", type="info")
                        return
                    lines = [
                        f"{c.get('officer_name')} · sen#{c.get('seniority_rank')} · "
                        f"OT {c.get('ot_hours')}h · score {c.get('score')}"
                        for c in cands
                    ]
                    with (
                        ui.dialog() as dlg,
                        ui.card().classes("w-full").style("min-width:min(420px,94vw);max-width:520px"),
                    ):
                        ui.label("Vacancy rank (TeleStaff-style)").classes("text-sm font-semibold q-mb-sm")
                        ui.textarea(value="\n".join(lines)).classes("w-full").props(
                            "readonly outlined dense dark rows=10"
                        )
                        ui.button("Close", on_click=dlg.close).classes("btn-ghost q-mt-sm").props("no-caps flat dense")
                    dlg.open()

                ui.button("Rank candidates", on_click=show_rank).classes("btn-ghost q-mt-sm").props(
                    "no-caps outline dense"
                )
