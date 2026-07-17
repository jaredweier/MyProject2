"""Patrol roster management."""

from __future__ import annotations

from nicegui import ui

from config import OFFICER_SQUAD_OPTIONS
from gui import session
from gui.shell import layout, page_header, panel
from logic import (
    add_custom_officer_title,
    add_officer,
    bulk_set_station,
    delete_officer,
    get_officer_by_id,
    get_officer_title_options,
    get_officers_by_seniority,
    get_pay_period,
    get_pay_period_hours_by_officer,
    get_title_callin_limits,
    import_roster_from_csv,
    list_station_posts,
    monthly_pay_to_per_pay_period,
    set_title_callin_limit,
    station_staffing_board,
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
            "Active sworn personnel · titles, squads, shifts",
            kicker="Personnel",
        )
        with ui.row().classes("gap-2 q-mb-sm flex-wrap"):
            ui.button("Exports hub", on_click=lambda: ui.navigate.to("/exports")).classes("btn-ghost").props(
                "no-caps outline dense"
            )
            ui.button("Certifications", on_click=lambda: ui.navigate.to("/certs")).classes("btn-ghost").props(
                "no-caps outline dense"
            )
            ui.button("Branding & media", on_click=lambda: ui.navigate.to("/media")).classes("btn-ghost").props(
                "no-caps outline dense"
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
                                    "station": o.get("station") or "—",
                                    "shift": o.get("shift_start"),
                                    "rank": o.get("seniority_rank"),
                                    "title": o.get("job_title") or "Officer",
                                }
                                for o in officers
                            ]
                            # always re-create inside cleared host (grid_holder tracks element)
                            grid_holder["grid"] = aggrid_from_dicts(
                                rows,
                                prefer_columns=["name", "squad", "station", "shift", "rank", "title"],
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
                                        f"Squad {o.get('squad') or '—'} · stn {o.get('station') or '—'} · "
                                        f"{o.get('shift_start') or '—'} · "
                                        f"#{o.get('seniority_rank')} · {o.get('job_title') or 'Officer'}"
                                    ).classes("text-xs text-gray-500")

                search.on("update:model-value", lambda _: refresh_list())
                view_mode.on("update:model-value", lambda _: refresh_list())

                if session.can("officers.manage"):
                    with ui.expansion("Stations · bulk assign", icon="apartment").classes("w-full q-mt-sm"):
                        board = station_staffing_board()
                        ui.label(board.get("message") or "Station board").classes("text-xs q-mb-xs").style(
                            "color: var(--dim)"
                        )
                        posts = list_station_posts(active_only=False) or []
                        codes = [p.get("code") for p in posts if p.get("code")] or ["HQ"]
                        bulk_st = ui.select(codes, value=codes[0], label="Station code").classes("w-full")
                        only_blank = ui.checkbox("Only unassigned officers", value=True)

                        def do_bulk_station():
                            uid = (session.current_user() or {}).get("id")
                            r = bulk_set_station(
                                bulk_st.value or "HQ",
                                only_unassigned=bool(only_blank.value),
                                only_active=True,
                                user_id=uid,
                            )
                            ui.notify(
                                r.get("message", "Done"),
                                type="positive" if r.get("success") else "negative",
                            )
                            refresh_list()

                        ui.button("Apply station to roster", on_click=do_bulk_station).classes(
                            "btn-ghost q-mt-xs"
                        ).props("no-caps outline dense")
                        ui.label("Tip: create posts under Deploy → Stations first.").classes("text-xs q-mt-xs").style(
                            "color: var(--dim)"
                        )

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
                rot_pattern = ui.input(
                    label="Rotation pattern (blank=squad A/B; e.g. 5-2 or 5-3,6-2)",
                    value="",
                ).classes("w-full")
                rot_phase = ui.input(label="Rotation phase (days offset)", value="0").classes("w-full")
                max_td = ui.input(
                    label="Max turn-downs / year (blank = title default / unlimited)",
                    value="",
                ).classes("w-full")
                max_oi = ui.input(
                    label="Max ordered-in / year (blank = title default / unlimited)",
                    value="",
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
                    rot_pattern.value = o.get("rotation_pattern") or ""
                    rot_phase.value = str(o.get("rotation_phase") or 0)
                    max_td.value = (
                        "" if o.get("max_turn_downs_year") in (None, "") else str(o.get("max_turn_downs_year"))
                    )
                    max_oi.value = (
                        "" if o.get("max_ordered_in_year") in (None, "") else str(o.get("max_ordered_in_year"))
                    )
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
                    rot_pattern.value = ""
                    rot_phase.value = "0"
                    max_td.value = ""
                    max_oi.value = ""
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
                    try:
                        phase = int((rot_phase.value or "0").strip() or "0")
                    except ValueError:
                        ui.notify("Rotation phase must be a number", type="negative")
                        return

                    def _opt_int(raw):
                        s = (raw or "").strip()
                        if not s:
                            return None
                        return int(s)

                    try:
                        td_val = _opt_int(max_td.value)
                        oi_val = _opt_int(max_oi.value)
                    except ValueError:
                        ui.notify("Max turn-downs / ordered-in must be whole numbers or blank", type="negative")
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
                        "rotation_pattern": (rot_pattern.value or "").strip() or None,
                        "rotation_phase": phase,
                        "max_turn_downs_year": td_val,
                        "max_ordered_in_year": oi_val,
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

                    with ui.expansion("Title defaults · max turn-downs / ordered-in per year", icon="rule").classes(
                        "w-full q-mt-sm"
                    ):
                        ui.label(
                            "Applied when officer fields are blank. Used by call list next-up and OT order board."
                        ).classes("text-xs text-gray-500 q-mb-sm")
                        t_limits = get_title_callin_limits()
                        cur = t_limits.get(title.value or "") or {}
                        t_max_td = ui.input(
                            label="Title max turn-downs / year",
                            value="" if cur.get("max_turn_downs_year") is None else str(cur.get("max_turn_downs_year")),
                        ).classes("w-full")
                        t_max_oi = ui.input(
                            label="Title max ordered-in / year",
                            value="" if cur.get("max_ordered_in_year") is None else str(cur.get("max_ordered_in_year")),
                        ).classes("w-full")

                        def save_title_limits():
                            def _opt(raw):
                                s = (raw or "").strip()
                                if not s:
                                    return None
                                return int(s)

                            try:
                                td = _opt(t_max_td.value)
                                oi = _opt(t_max_oi.value)
                            except ValueError:
                                ui.notify("Limits must be whole numbers or blank", type="negative")
                                return
                            uid = (session.current_user() or {}).get("id")
                            r = set_title_callin_limit(
                                title.value or "Officer",
                                max_turn_downs_year=td,
                                max_ordered_in_year=oi,
                                user_id=uid,
                            )
                            ui.notify(
                                r.get("message", "Saved") if r.get("success") else r.get("message", "Fail"),
                                type="positive" if r.get("success") else "negative",
                            )

                        ui.button("Save title call-in limits", on_click=save_title_limits).classes("btn-ghost").props(
                            "no-caps outline dense"
                        )

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
