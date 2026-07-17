"""Online hosting + implementation kit — purchasable deploy modes."""

from __future__ import annotations

from nicegui import ui

from config import APP_NAME, APP_VERSION, COMPANY_NAME
from gui import session
from gui.shell import layout, page_header, panel
from logic import (
    apply_geofence_punches_to_timecard,
    apply_rotation_preset_metadata,
    create_tenant,
    deployment_checklist,
    export_dual_ot_ledger_csv,
    export_duty_roster_for_cad,
    export_implementation_kit,
    export_ot_equity_dual_csv,
    get_dual_workforce_settings,
    get_geofence_config,
    get_hosting_config,
    get_implementation_kit,
    get_ot_equity_summary,
    get_tenant_info,
    list_geofence_punches,
    list_rotation_presets,
    list_station_posts,
    officers_by_station,
    run_dual_period_ot_ledger,
    save_dual_workforce_settings,
    save_geofence_config,
    station_staffing_board,
    upsert_station_post,
)


def render_deploy() -> None:
    def body() -> None:
        admin = (
            session.can("admin.settings")
            or session.can("settings.manage")
            or session.can("users.manage")
            or session.can("reports.view")
        )
        page_header(
            "Deploy & implement",
            f"{APP_NAME} by {COMPANY_NAME} · on-prem software or online host",
            kicker="Weierworks · Product",
        )

        kit = get_implementation_kit()
        host = get_hosting_config()
        check = deployment_checklist()

        with panel("Purchase modes", glow=True):
            for m in kit.get("modes") or []:
                ui.label(f"· {m.get('name')}").classes("text-sm font-semibold")
                ui.label(m.get("how") or "").classes("text-xs q-mb-sm").style("color: var(--dim)")
            tinfo = get_tenant_info()
            ui.html(
                f'<div class="alert alert-ok">Runtime: mode={host.get("mode")} online={host.get("online")} '
                f"host={host.get('host')}:{host.get('port')} · "
                f"tenant={tinfo.get('tenant_id')} · db={tinfo.get('db_path')}</div>",
                sanitize=False,
            )
            ui.label(
                "Online: python main.py --web · or Docker · set SCHEDULER_STORAGE_SECRET + TLS reverse proxy"
            ).classes("text-xs").style("color: var(--dim)")
            ui.label(
                "Multi-tenant: one process/container per agency with SCHEDULER_TENANT_ID=slug "
                "(isolated tenants/<slug>/ DB + photos)."
            ).classes("text-xs").style("color: var(--dim)")

        with panel("Go-live checklist"):
            for c in check.get("checks") or []:
                mark = "✓" if c.get("ok") else "○"
                ui.label(f"{mark} {c.get('key')}: {c.get('hint')}").classes("text-sm")
            with ui.row().classes("gap-2 q-mt-sm flex-wrap"):

                def exp_kit():
                    r = export_implementation_kit()
                    ui.notify(
                        f"Exported {r.get('md_path')}",
                        type="positive" if r.get("success") else "negative",
                    )

                def exp_cad():
                    r = export_duty_roster_for_cad(days=1)
                    ui.notify(r.get("message", str(r)), type="positive" if r.get("success") else "warning")

                ui.button("Export implementation kit", on_click=exp_kit).classes("btn-primary").props(
                    "no-caps unelevated"
                )
                ui.button("Export CAD/RMS duty roster", on_click=exp_cad).classes("btn-ghost").props("no-caps outline")

        with panel("Setup steps (in-app)"):
            for i, s in enumerate(kit.get("setup_steps") or [], 1):
                path = s.get("path") or "/"
                with ui.row().classes("items-center gap-2"):
                    ui.label(f"{i}. {s.get('title')}").classes("text-sm grow")
                    ui.button("Open", on_click=lambda _p=path: ui.navigate.to(_p)).props("dense flat no-caps")

        if not admin:
            ui.html(
                '<div class="alert alert-warn">Sign in as admin/supervisor for dual FLSA, stations, geofence.</div>',
                sanitize=False,
            )
            return

        # Dual workforce
        dw = get_dual_workforce_settings()
        with panel("Dual workforce FLSA (sworn + civilian)"):
            dual = ui.switch("Enable dual FLSA profiles", value=bool(dw.get("dual_flsa_enabled")))
            civ = ui.number("Civilian weekly OT threshold", value=dw.get("civilian_weekly_threshold") or 40).classes(
                "w-full"
            )
            cap_s = ui.number("Comp cap sworn (hours)", value=dw.get("comp_cap_sworn") or 480).classes("w-full")
            cap_c = ui.number("Comp cap civilian (hours)", value=dw.get("comp_cap_civilian") or 240).classes("w-full")

            def save_dw():
                uid = (session.current_user() or {}).get("id")
                r = save_dual_workforce_settings(
                    dual_flsa_enabled=bool(dual.value),
                    civilian_weekly_threshold=float(civ.value or 40),
                    comp_cap_sworn=float(cap_s.value or 480),
                    comp_cap_civilian=float(cap_c.value or 240),
                    user_id=uid,
                )
                ui.notify("Dual workforce saved" if r.get("success") else "Save failed", type="positive")

            def run_dual_ledger():
                led = run_dual_period_ot_ledger()
                ex = export_dual_ot_ledger_csv()
                ui.notify(
                    f"{led.get('count')} officers · sworn OT {led.get('sworn_ot_hours')}h · "
                    f"civ OT {led.get('civilian_ot_hours')}h · {ex.get('path')}",
                    type="positive" if ex.get("success") else "warning",
                    multi_line=True,
                )

            with ui.row().classes("gap-2 q-mt-sm flex-wrap"):
                ui.button("Save dual FLSA", on_click=save_dw).classes("btn-primary").props("no-caps unelevated")
                ui.button("Run dual OT engine / CSV", on_click=run_dual_ledger).classes("btn-ghost").props(
                    "no-caps outline"
                )

        # Tenants
        with panel("Agency tenants (online multi-dept)"):
            ui.label("Each tenant = separate SQLite + media folder. Not shared-schema.").classes(
                "text-xs q-mb-sm"
            ).style("color: var(--dim)")
            for t in (get_tenant_info().get("tenants") or [])[:12]:
                mark = "●" if t.get("active") else "○"
                ui.label(
                    f"{mark} {t.get('tenant_id')} · db={'yes' if t.get('db_exists') else 'no'} · {t.get('path')}"
                ).classes("text-sm")
            tid_in = ui.input("New tenant id", placeholder="city-pd").classes("w-full")
            tname = ui.input("Display name", placeholder="City PD").classes("w-full")

            def mk_tenant():
                r = create_tenant(tid_in.value or "", display_name=tname.value or "")
                ui.notify(r.get("message", "Done"), type="positive" if r.get("success") else "negative")

            ui.button("Create tenant folder", on_click=mk_tenant).classes("btn-ghost q-mt-sm").props("no-caps outline")

        # Stations
        with panel("Stations / posts", glow=True):
            board = station_staffing_board()
            level = board.get("level") or "info"
            cls = (
                "alert-danger"
                if level == "critical"
                else "alert-warn"
                if level == "warning"
                else "alert-ok"
                if level == "ok"
                else "alert-warn"
            )
            ui.html(
                f'<div class="alert {cls}">{board.get("message")}</div>',
                sanitize=False,
            )
            counts = officers_by_station().get("counts") or {}
            ui.label(f"Officers by station: {counts}").classes("text-xs q-mb-sm").style("color: var(--dim)")
            for u in board.get("understaffed") or []:
                ui.label(
                    f"Under: {u.get('code')} · {u.get('assigned')}/{u.get('min_staff')} (gap {u.get('gap')})"
                ).classes("text-sm text-orange-400")
            code = ui.input("Station code", value="HQ").classes("w-full")
            name = ui.input("Station name", value="Headquarters").classes("w-full")
            mins = ui.number("Min staff", value=1).classes("w-full")

            def add_st():
                r = upsert_station_post(
                    code.value or "HQ",
                    name.value or "Station",
                    min_staff=int(mins.value or 1),
                )
                ui.notify(r.get("message", "Saved"), type="positive" if r.get("success") else "negative")

            ui.button("Save station", on_click=add_st).classes("btn-ghost q-mt-sm").props("no-caps outline")
            for p in list_station_posts(active_only=False):
                # Merge live assigned count when known
                assigned = next(
                    (r.get("assigned") for r in (board.get("posts") or []) if r.get("code") == p.get("code")),
                    None,
                )
                assign_bit = f" · roster {assigned}" if assigned is not None else ""
                ui.label(
                    f"{p.get('code')} · {p.get('name')} · min {p.get('min_staff')}{assign_bit} · "
                    f"{'active' if p.get('active') else 'off'}"
                ).classes("text-sm")

        # Rotation presets
        with panel("Rotation presets (LE / fire / EMS)"):
            presets = (list_rotation_presets() or {}).get("presets") or []
            labels = {f"{p['name']} ({p['segment']})": p["id"] for p in presets}
            if labels:
                pick = ui.select(list(labels.keys()), value=list(labels.keys())[0], label="Preset").classes("w-full")

                def apply_p():
                    pid = labels.get(pick.value)
                    uid = (session.current_user() or {}).get("id")
                    r = apply_rotation_preset_metadata(pid, user_id=uid)
                    ui.notify(r.get("message", "Applied"), type="info")

                ui.button("Record preset selection", on_click=apply_p).classes("btn-ghost q-mt-sm").props(
                    "no-caps outline"
                )

        # Geofence — full map + test punch + ledger
        gf = get_geofence_config()
        with panel("Geofenced clock · map & test punch", glow=True):
            ui.label(
                "Station fence for mobile punches. Map uses OpenStreetMap embed (center = station lat/lon)."
            ).classes("text-xs q-mb-sm").style("color: var(--dim)")
            gen = ui.switch("Geofence enabled", value=bool(gf.get("enabled")))
            glat = ui.number("Station latitude", value=gf.get("lat") or 0, format="%.6f").classes("w-full")
            glon = ui.number("Station longitude", value=gf.get("lon") or 0, format="%.6f").classes("w-full")
            grad = ui.number("Radius (m)", value=gf.get("radius_m") or 200).classes("w-full")

            map_host = ui.element("div").classes("w-full q-mb-sm")

            def _render_map():
                map_host.clear()
                lat = float(glat.value or 0)
                lon = float(glon.value or 0)
                rad = float(grad.value or 200)
                with map_host:
                    if lat == 0 and lon == 0:
                        ui.label("Set non-zero station coordinates to preview map.").classes("text-xs").style(
                            "color: var(--dim)"
                        )
                        return
                    # OSM embed bbox ~ radius*3 as degrees (~111km per deg)
                    dlat = max(0.002, (rad * 3) / 111000.0)
                    dlon = max(
                        0.002,
                        (rad * 3) / (111000.0 * max(0.2, abs(__import__("math").cos(__import__("math").radians(lat))))),
                    )
                    bbox = f"{lon - dlon}%2C{lat - dlat}%2C{lon + dlon}%2C{lat + dlat}"
                    marker = f"{lat}%2C{lon}"
                    src = f"https://www.openstreetmap.org/export/embed.html?bbox={bbox}&layer=mapnik&marker={marker}"
                    ui.html(
                        f'<iframe title="Geofence map" src="{src}" '
                        f'style="width:100%;height:260px;border:1px solid rgba(197,206,217,0.2);'
                        f'border-radius:10px;background:#0a1220" loading="lazy"></iframe>'
                        f'<div class="text-xs" style="color:var(--dim);margin-top:6px">'
                        f"Center {lat:.5f},{lon:.5f} · radius {rad:.0f}m · "
                        f"{'ENABLED' if gen.value else 'disabled'}</div>",
                        sanitize=False,
                    )

            def save_gf():
                r = save_geofence_config(
                    enabled=bool(gen.value),
                    lat=float(glat.value or 0),
                    lon=float(glon.value or 0),
                    radius_m=float(grad.value or 200),
                )
                ui.notify("Geofence saved" if r.get("success") else "Failed", type="positive")
                _render_map()

            _render_map()
            try:
                glat.on_value_change(lambda _: _render_map())
                glon.on_value_change(lambda _: _render_map())
                grad.on_value_change(lambda _: _render_map())
            except Exception:
                pass

            ui.separator()
            ui.label("Recent geofence punches").classes("text-xs text-gray-500 q-mb-xs")
            punches = list_geofence_punches(limit=12) or []
            if not punches:
                ui.label("No geofence punches yet.").classes("text-xs").style("color: var(--dim)")
            for p in punches:
                within = p.get("within_fence")
                wlab = "IN" if within in (1, True) else ("OUT" if within in (0, False) else "—")
                ui.label(
                    f"#{p.get('id')} officer {p.get('officer_id')} · {p.get('punch_type')} · "
                    f"fence={wlab} · dist={p.get('distance_m') or '—'}m · {p.get('created_at')}"
                ).classes("text-xs mono")

            ui.separator()
            ui.label("Test punch (lab)").classes("text-xs text-gray-500 q-mb-xs")
            from logic import get_officers_by_seniority

            offs = [o for o in get_officers_by_seniority() if o.get("active") == 1]
            onames = [o["name"] for o in offs] or ["—"]
            omap = {o["name"]: o["id"] for o in offs}
            opick = ui.select(onames, value=onames[0], label="Officer").classes("w-full")
            ptype = ui.select(["in", "out"], value="in", label="Punch type").classes("w-full")
            tlat = ui.number("Punch lat (blank = station)", value=gf.get("lat") or 0, format="%.6f").classes("w-full")
            tlon = ui.number("Punch lon", value=gf.get("lon") or 0, format="%.6f").classes("w-full")

            def do_test_punch():
                from logic.geofence_clock import record_geofence_punch

                oid = omap.get(opick.value)
                if not oid:
                    ui.notify("Select officer", type="warning")
                    return
                r = record_geofence_punch(
                    int(oid),
                    str(ptype.value or "in"),
                    lat=float(tlat.value) if tlat.value is not None else None,
                    lon=float(tlon.value) if tlon.value is not None else None,
                    notes="deploy test punch",
                )
                ui.notify(
                    r.get("message", "Punch") if r.get("success") else r.get("message", "Blocked"),
                    type="positive" if r.get("success") else "warning",
                )

            oid_punch = ui.number("Officer id → apply punches to timecard", value=None).classes("w-full")

            def apply_tc():
                if not oid_punch.value:
                    ui.notify("Enter officer id", type="warning")
                    return
                uid = (session.current_user() or {}).get("id")
                r = apply_geofence_punches_to_timecard(int(oid_punch.value), user_id=uid)
                ui.notify(r.get("message", "Done"), type="positive" if r.get("success") else "negative")

            with ui.row().classes("gap-2 q-mt-sm flex-wrap"):
                ui.button("Save geofence", on_click=save_gf).classes("btn-primary").props("no-caps unelevated dense")
                ui.button("Refresh map", on_click=_render_map).classes("btn-ghost").props("no-caps outline dense")
                ui.button("Record test punch", on_click=do_test_punch).classes("btn-ghost").props(
                    "no-caps outline dense"
                )
                ui.button("Apply punches → timecard", on_click=apply_tc).classes("btn-ghost").props(
                    "no-caps outline dense"
                )
                ui.button("Time punch page", on_click=lambda: ui.navigate.to("/time-punch")).classes("btn-ghost").props(
                    "no-caps outline dense"
                )

        # OT equity dual
        with panel("OT equity dual ledger (offered vs worked)", glow=True):
            summary = get_ot_equity_summary(limit=50)
            rows = summary.get("rows") or []
            if not rows:
                ui.label("No equity rows yet — callback offers record into the ledger.").classes("text-xs").style(
                    "color: var(--dim)"
                )
            else:
                try:
                    from gui.tables import aggrid_from_dicts

                    grid_rows = [
                        {
                            "name": r.get("officer_name") or r.get("name"),
                            "offered_h": r.get("hours_offered"),
                            "worked_h": r.get("hours_worked"),
                            "delta": r.get("delta_offered_minus_worked"),
                            "offers": r.get("offer_count") or r.get("n_offers"),
                            "worked_n": r.get("worked_count") or r.get("n_worked"),
                        }
                        for r in rows
                        if isinstance(r, dict)
                    ]
                    aggrid_from_dicts(
                        grid_rows,
                        prefer_columns=["name", "offered_h", "worked_h", "delta", "offers", "worked_n"],
                        height="280px",
                        csv_export=True,
                        csv_name="ot_equity_dual",
                    )
                except Exception:
                    for row in rows[:15]:
                        ui.label(
                            f"{row.get('officer_name')}: offered {row.get('hours_offered')}h · "
                            f"worked {row.get('hours_worked')}h · Δ {row.get('delta_offered_minus_worked')}"
                        ).classes("text-sm")

            def exp_eq():
                r = export_ot_equity_dual_csv()
                ui.notify(
                    r.get("path") or r.get("message", "Export"), type="positive" if r.get("success") else "warning"
                )

            ui.button("Export dual equity CSV", on_click=exp_eq).classes("btn-primary q-mt-sm").props(
                "no-caps unelevated"
            )

        ui.label(f"{APP_NAME} v{APP_VERSION} · {COMPANY_NAME}").classes("text-xs q-mt-md").style("color: var(--dim)")

    layout("deploy", body)
