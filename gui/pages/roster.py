"""Patrol roster management."""

from __future__ import annotations

from nicegui import ui

from config import OFFICER_SQUAD_OPTIONS
from gui import session
from gui.shell import layout, page_header, panel
from logic import (
    add_custom_officer_title,
    add_officer,
    delete_officer,
    get_officer_by_id,
    get_officer_title_options,
    get_officers_by_seniority,
    get_pay_period,
    get_pay_period_hours_by_officer,
    import_roster_from_csv,
    monthly_pay_to_per_pay_period,
    suggested_hourly_rate_for_title,
    update_officer,
)
from logic.staffing_config import get_officer_shift_options
from validators import format_officer_shift_display, parse_officer_shift_ui


def render_roster() -> None:
    def body() -> None:
        if not session.can("officers.manage"):
            page_header("Patrol Roster", "Permission Required", kicker="Personnel")
            ui.html(
                '<div class="alert alert-warn">Roster Management Requires Supervisor Access.</div>',
                sanitize=False,
            )
            return

        page_header(
            "Patrol Roster",
            "Active Sworn Personnel · Titles, Squads, Shifts",
            kicker="Personnel",
        )
        state: dict = {"selected": None}

        with ui.element("div").classes("grid-2"):
            with panel("Roster"):
                search = (
                    ui.input(placeholder="Search name or squad…").classes("w-full q-mb-sm").props("outlined dense dark")
                )
                view_mode = ui.toggle(["list", "grid"], value="list").props("dense no-caps").classes("q-mb-sm")
                list_host = ui.element("div")
                grid_holder: dict = {"grid": None}

                def refresh_list():
                    q = (search.value or "").strip().lower()
                    officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
                    if q:
                        officers = [
                            o
                            for o in officers
                            if q in (o.get("name") or "").lower() or q in (o.get("squad") or "").lower()
                        ]
                    list_host.clear()
                    with list_host:
                        ui.label(f"{len(officers)} active").classes("text-xs text-gray-500 q-mb-sm")
                        if (view_mode.value or "list") == "grid":
                            from gui.tables import aggrid_from_dicts

                            rows = [
                                {
                                    "id": o["id"],
                                    "name": o.get("name"),
                                    "squad": o.get("squad"),
                                    "shift": o.get("shift_start"),
                                    "rank": o.get("seniority_rank"),
                                    "title": o.get("job_title") or "Officer",
                                }
                                for o in officers
                            ]
                            # always re-create inside cleared host (grid_holder tracks element)
                            grid_holder["grid"] = aggrid_from_dicts(
                                rows,
                                prefer_columns=["name", "squad", "shift", "rank", "title"],
                                height="360px",
                                csv_export=True,
                                csv_name="roster",
                            )
                            ui.label("Tip: switch to list to select an officer for edit").classes(
                                "text-xs text-gray-500 q-mt-sm"
                            )
                            return
                        grid_holder["grid"] = None
                        for o in officers:
                            with ui.element("div").classes("data-row").on("click", lambda _e, oid=o["id"]: load(oid)):
                                with ui.element("div"):
                                    ui.label(o["name"]).classes("text-sm font-semibold")
                                    ui.label(
                                        f"Squad {o.get('squad') or '—'} · {o.get('shift_start') or '—'} · "
                                        f"#{o.get('seniority_rank')} · {o.get('job_title') or 'Officer'}"
                                    ).classes("text-xs text-gray-500")

                search.on("update:model-value", lambda _: refresh_list())
                view_mode.on("update:model-value", lambda _: refresh_list())

                if session.can("officers.manage"):
                    with ui.expansion("Import roster CSV", icon="upload").classes("w-full q-mt-sm"):
                        ui.label(
                            "CSV columns typically: name, squad, shift_start, seniority_rank, job_title "
                            "(matches logic.import_roster_from_csv)."
                        ).classes("text-xs text-gray-500 q-mb-sm")
                        path_in = ui.input(label="Path to CSV on this machine").classes("w-full")

                        def do_import():
                            p = (path_in.value or "").strip()
                            if not p:
                                ui.notify("Enter a file path", type="warning")
                                return
                            result = import_roster_from_csv(p, update_existing=True)
                            if result.get("success"):
                                ui.notify(
                                    result.get("message") or f"Imported {result.get('count', result.get('added', ''))}",
                                    type="positive",
                                )
                                refresh_list()
                            else:
                                ui.notify(result.get("message", "Import failed"), type="negative")

                        ui.button("Import CSV", on_click=do_import).classes("btn-ghost").props("no-caps outline dense")

            with panel("Officer Detail"):
                titles = get_officer_title_options()
                shifts = list(get_officer_shift_options())
                photo_box = ui.element("div").classes("q-mb-sm")
                name = ui.input(label="Full Name").classes("w-full")
                title = ui.select(titles, value=titles[0] if titles else "Officer", label="Title").classes("w-full")
                squad = ui.select(list(OFFICER_SQUAD_OPTIONS), value="A", label="Squad").classes("w-full")
                shift = ui.select(shifts, value=shifts[1] if len(shifts) > 1 else shifts[0], label="Shift").classes(
                    "w-full"
                )
                rank = ui.input(label="Seniority Rank").classes("w-full")
                station = ui.input(label="Station / post (ESO-style)", value="").classes("w-full")
                workforce = ui.select(
                    ["sworn", "civilian"],
                    value="sworn",
                    label="Workforce class (Netchex dual OT)",
                ).classes("w-full")
                active = ui.checkbox("Active On Roster", value=True)

                def show_photo(oid):
                    photo_box.clear()
                    with photo_box:
                        if not oid:
                            return
                        try:
                            from photos import officer_photo_path

                            p = officer_photo_path(oid)
                            if p:
                                ui.image(p).style("max-height:100px;border-radius:10px;border:1px solid var(--border)")
                            else:
                                ui.label("No Photo — Upload Below Or Use Photos & Branding").classes("text-xs").style(
                                    "color: var(--dim)"
                                )
                        except Exception:
                            pass

                def load(oid: int):
                    o = get_officer_by_id(oid)
                    if not o:
                        return
                    state["selected"] = oid
                    name.value = o.get("name") or ""
                    title.value = o.get("job_title") or "Officer"
                    squad.value = o.get("squad") or OFFICER_SQUAD_OPTIONS[0]
                    shift.value = format_officer_shift_display(o.get("shift_start"), o.get("shift_end"))
                    rank.value = str(o.get("seniority_rank") or "")
                    station.value = o.get("station") or ""
                    workforce.value = o.get("workforce_class") or "sworn"
                    active.value = o.get("active") == 1
                    show_photo(oid)

                def clear_new():
                    state["selected"] = None
                    name.value = ""
                    title.value = "Officer"
                    squad.value = "A"
                    shift.value = shifts[1] if len(shifts) > 1 else shifts[0]
                    rank.value = ""
                    station.value = ""
                    workforce.value = "sworn"
                    active.value = True
                    show_photo(None)

                def save():
                    n = (name.value or "").strip()
                    if not n:
                        ui.notify("Name Required", type="negative")
                        return
                    start, end = parse_officer_shift_ui(shift.value)
                    try:
                        r = int((rank.value or "0").strip())
                    except ValueError:
                        ui.notify("Seniority Must Be A Number", type="negative")
                        return
                    fields = {
                        "name": n,
                        "job_title": title.value,
                        "squad": squad.value if squad.value != "Unassigned" else None,
                        "shift_start": start,
                        "shift_end": end,
                        "seniority_rank": r,
                        "station": (station.value or "").strip() or None,
                        "workforce_class": workforce.value or "sworn",
                    }
                    if state["selected"]:
                        fields["active"] = 1 if active.value else 0
                        result = update_officer(state["selected"], **fields)
                    else:
                        result = add_officer(
                            name=fields["name"],
                            seniority_rank=fields["seniority_rank"],
                            squad=fields["squad"],
                            shift_start=fields["shift_start"],
                            shift_end=fields["shift_end"],
                            job_title=fields["job_title"],
                        )
                    if result.get("success"):
                        ui.notify(result.get("message", "Saved"), type="positive")
                        if result.get("officer_id"):
                            state["selected"] = result["officer_id"]
                        refresh_list()
                        show_photo(state["selected"])
                    else:
                        ui.notify(result.get("message", "Failed"), type="negative")

                def on_photo(e):
                    oid = state.get("selected")
                    if not oid:
                        ui.notify("Select An Officer First", type="warning")
                        return
                    from photos import save_officer_photo_bytes

                    data = e.content.read() if hasattr(e.content, "read") else e.content
                    if isinstance(data, str):
                        data = data.encode()
                    result = save_officer_photo_bytes(oid, data)
                    if result.get("success"):
                        try:
                            update_officer(oid, photo_path=result.get("photo_path"))
                        except Exception:
                            pass
                        ui.notify("Officer Photo Saved", type="positive")
                        show_photo(oid)
                    else:
                        ui.notify(result.get("message", "Upload Failed"), type="negative")

                ui.upload(on_upload=on_photo, auto_upload=True, label="Upload Officer Photo").props(
                    "accept=.png,.jpg,.jpeg,.webp flat bordered dense"
                ).classes("w-full q-mb-sm")

                # CBA-style title rate helper (suggested_hourly_rate_for_title)
                rate_lbl = ui.label("").classes("text-xs text-gray-500")

                def on_title_change(_=None):
                    rate = suggested_hourly_rate_for_title(title.value)
                    if rate is not None:
                        rate_lbl.set_text(f"Suggested hourly for {title.value}: ${rate:.2f}/h")
                    else:
                        rate_lbl.set_text("No suggested rate for this title")

                title.on_value_change(on_title_change)
                on_title_change()

                with ui.expansion("Pay helpers (title rate · monthly → period)", icon="payments").classes(
                    "w-full q-mt-sm"
                ):
                    monthly_in = ui.input(label="Monthly pay $", value="").classes("w-full")
                    period_lbl = ui.label("").classes("text-xs text-gray-500")

                    def calc_period():
                        try:
                            m = float((monthly_in.value or "0").strip())
                        except ValueError:
                            period_lbl.set_text("Enter a number")
                            return
                        per = monthly_pay_to_per_pay_period(m)
                        period_lbl.set_text(f"≈ ${per:.2f} per 14-day pay period")

                    ui.button("Convert monthly → period", on_click=calc_period).classes("btn-ghost").props(
                        "no-caps outline dense"
                    )

                    with ui.expansion("Custom job title", icon="badge").classes("w-full q-mt-sm"):
                        new_title = ui.input(label="New title").classes("w-full")

                        def add_title():
                            uid = (session.current_user() or {}).get("id")
                            r = add_custom_officer_title((new_title.value or "").strip(), user_id=uid)
                            ok = r.get("success") if isinstance(r, dict) else bool(r)
                            ui.notify(
                                r.get("message", "Title added") if ok else r.get("message", "Failed"),
                                type="positive" if ok else "negative",
                            )
                            if ok:
                                ui.navigate.to("/roster")

                        ui.button("Add title", on_click=add_title).classes("btn-ghost").props("no-caps outline dense")

                with ui.row().classes("gap-2 q-mt-sm"):
                    ui.button("Save", on_click=save).classes("btn-primary").props("no-caps unelevated")
                    ui.button("New Officer", on_click=clear_new).classes("btn-ghost").props("no-caps outline")

                    def deactivate():
                        oid = state.get("selected")
                        if not oid:
                            ui.notify("Select an officer", type="warning")
                            return
                        r = delete_officer(oid)
                        ui.notify(
                            r.get("message", "Removed") if r.get("success") else r.get("message", "Failed"),
                            type="positive" if r.get("success") else "negative",
                        )
                        if r.get("success"):
                            clear_new()
                            refresh_list()

                    ui.button("Deactivate / delete", on_click=deactivate).classes("btn-danger").props(
                        "no-caps outline dense"
                    )

        # Period hours by officer (staffing cost / FLSA proximity helper)
        with panel("Pay-period hours by officer", glow=False):
            try:
                start, _end = get_pay_period()
                hours_map = get_pay_period_hours_by_officer(start) or {}
            except Exception as exc:
                hours_map = {}
                ui.label(str(exc)).classes("text-sm text-red-400")
            if not hours_map:
                ui.html(
                    '<div class="alert alert-ok">No period hours recorded yet (timecard/schedule).</div>',
                    sanitize=False,
                )
            else:
                # hours_map: officer_id -> float
                officers = {o["id"]: o for o in get_officers_by_seniority()}
                rows = []
                for oid, hrs in sorted(hours_map.items(), key=lambda kv: -float(kv[1] or 0))[:40]:
                    o = officers.get(oid) or {}
                    rows.append(
                        {
                            "name": o.get("name") or f"#{oid}",
                            "squad": o.get("squad"),
                            "hours": round(float(hrs or 0), 1),
                        }
                    )
                try:
                    from gui.tables import aggrid_from_dicts

                    if rows:
                        aggrid_from_dicts(
                            rows,
                            prefer_columns=["name", "squad", "hours"],
                            height="240px",
                        )
                except Exception:
                    for r in rows[:20]:
                        ui.label(f"{r['name']} · {r.get('squad')} · {r['hours']}h").classes("text-sm")

        refresh_list()

    layout("roster", body)
