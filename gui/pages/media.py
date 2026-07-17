"""Department Media — Chronos logo, agency seal/photo, officer portraits."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime

from nicegui import events, ui

from gui import session
from gui.clock import department_tz, format_local_datetime
from gui.shell import layout, page_header
from logic import get_officers_by_seniority, update_officer
from photos import (
    chronos_logo_path,
    clear_chronos_logo,
    clear_department_logo,
    clear_department_photo,
    department_logo_path,
    department_photo_path,
    officer_photo_path,
    save_chronos_logo_bytes,
    save_department_logo_bytes,
    save_department_photo_bytes,
    save_officer_photo_bytes,
)


def _file_meta(path: str | None) -> str:
    if not path or not os.path.isfile(path):
        return "No file on disk — choose file then save"
    try:
        st = os.stat(path)
        kb = max(1, st.st_size // 1024)
        when = format_local_datetime(datetime.fromtimestamp(st.st_mtime, tz=department_tz()))
        return f"{os.path.basename(path)} · {kb} KB · Updated {when}"
    except OSError:
        return os.path.basename(path or "")


def _write_temp_preview(data: bytes, suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    with open(path, "wb") as fh:
        fh.write(data)
    return path


def _sync_brand() -> None:
    try:
        from gui.brand_assets import sync_brand_files

        sync_brand_files()
    except Exception:
        pass


def render_media() -> None:
    def body() -> None:
        if not (session.can("officers.manage") or session.can("admin.settings") or session.can("settings.manage")):
            page_header("Department Media", "Permission required", kicker="Command")
            ui.html(
                '<div class="alert alert-warn">Department Media requires supervisor or administration access.</div>',
                sanitize=False,
            )
            return

        page_header(
            "Branding & Media",
            "Chronos Command logo (upload before deploy) · agency seal & photo · officer portraits · Weierworks Technologies, LLC",
            kicker="Chronos Command",
        )
        ui.html(
            '<div class="alert alert-ok q-mb-md">'
            "<strong>Chronos Command</strong> product mark is shown in the sidebar and login. "
            "Upload PNG/JPG/WebP here before online or portable deployment. "
            "Agency seal is optional secondary branding."
            "</div>",
            sanitize=False,
        )

        pending: dict = {
            "chronos": None,
            "chronos_preview": None,
            "logo": None,
            "logo_preview": None,
            "photo": None,
            "photo_preview": None,
            "officer_id": None,
            "officer": None,
            "officer_preview": None,
        }
        status = ui.label("").classes("text-sm q-mb-md").style("color: var(--dim)")

        def set_status(msg: str, *, pending_note: bool = False):
            status.set_text(msg)
            status.style(f"color: {'#fbbf24' if pending_note else 'var(--dim)'}")

        def brand_card(
            *,
            title: str,
            subtitle: str,
            key: str,
            path_fn,
            save_fn,
            clear_fn,
            accept: str = ".png,.jpg,.jpeg,.webp",
            cover: bool = False,
            logo_style: bool = False,
        ):
            with ui.element("div").classes("media-card"):
                hero = ui.element("div").classes("media-card-hero" + (" logo-hero" if logo_style else ""))
                with ui.element("div").classes("media-card-body"):
                    ui.html(f'<div class="media-card-title">{title}</div>', sanitize=False)
                    meta = ui.label("").classes("media-card-meta")
                    ui.label(subtitle).classes("text-xs q-mb-sm").style("color: var(--dim)")
                    upload = (
                        ui.upload(label="Choose file", auto_upload=True)
                        .props(f"accept={accept} flat dense color=cyan")
                        .classes("w-full")
                    )
                    with ui.row().classes("gap-2 w-full q-mt-sm"):
                        save_btn = ui.button("Save").classes("btn-primary").props("no-caps unelevated dense")
                        clear_btn = ui.button("Clear").classes("btn-ghost").props("no-caps outline dense")

                def paint():
                    hero.clear()
                    show = pending.get(f"{key}_preview") or path_fn()
                    if pending.get(key):
                        meta.set_text(f"Unsaved {title.lower()} staged — click Save")
                    else:
                        meta.set_text(_file_meta(path_fn()))
                    with hero:
                        if show and os.path.isfile(show):
                            if cover:
                                ui.image(show).style("width:100%;height:100%;object-fit:cover")
                            else:
                                ui.image(show).style(
                                    "max-height:150px;max-width:88%;object-fit:contain;border-radius:8px"
                                )
                        else:
                            ui.html(
                                f'<div class="media-empty">No {title.lower()} yet</div>',
                                sanitize=False,
                            )

                async def stage(e: events.UploadEventArguments):
                    data = await e.file.read()
                    pending[key] = data
                    prev = pending.get(f"{key}_preview")
                    if prev and os.path.isfile(prev):
                        try:
                            os.remove(prev)
                        except OSError:
                            pass
                    name = getattr(e.file, "name", "") or "upload.png"
                    suf = os.path.splitext(name)[1].lower() or ".png"
                    pending[f"{key}_preview"] = _write_temp_preview(data, suf)
                    set_status(f"{title} staged — click Save", pending_note=True)
                    paint()

                def save():
                    data = pending.get(key)
                    if not data:
                        ui.notify("Choose a file first", type="warning")
                        return
                    result = save_fn(data)
                    if result.get("success"):
                        _sync_brand()
                        pending[key] = None
                        prev = pending.get(f"{key}_preview")
                        if prev and os.path.isfile(prev):
                            try:
                                os.remove(prev)
                            except OSError:
                                pass
                        pending[f"{key}_preview"] = None
                        set_status(f"{title} saved — refresh or re-open login to see landing page")
                        ui.notify(f"{title} saved", type="positive")
                        paint()
                    else:
                        ui.notify(result.get("message", "Save failed"), type="negative")

                def clear():
                    r = clear_fn()
                    _sync_brand()
                    pending[key] = None
                    prev = pending.get(f"{key}_preview")
                    if prev and os.path.isfile(prev):
                        try:
                            os.remove(prev)
                        except OSError:
                            pass
                    pending[f"{key}_preview"] = None
                    set_status(r.get("message", f"{title} cleared"))
                    ui.notify(r.get("message", "Cleared"), type="info")
                    paint()

                upload.on_upload(stage)
                save_btn.on_click(save)
                clear_btn.on_click(clear)
                paint()
                return paint

        with ui.element("div").classes("grid-2").style("margin-bottom: 18px"):
            paint_chronos = brand_card(
                title="Chronos Command logo",
                subtitle="Product mark — shown with Chronos Command on login and sidebar",
                key="chronos",
                path_fn=chronos_logo_path,
                save_fn=save_chronos_logo_bytes,
                clear_fn=clear_chronos_logo,
                logo_style=True,
            )
            paint_logo = brand_card(
                title="Department logo",
                subtitle="Your agency seal — login hero badge (optional)",
                key="logo",
                path_fn=department_logo_path,
                save_fn=save_department_logo_bytes,
                clear_fn=clear_department_logo,
                logo_style=True,
            )

        with ui.element("div").classes("grid-2").style("margin-bottom: 18px"):
            paint_photo = brand_card(
                title="Department photo",
                subtitle="Your agency team / facility photo — login hero background",
                key="photo",
                path_fn=department_photo_path,
                save_fn=save_department_photo_bytes,
                clear_fn=clear_department_photo,
                cover=True,
            )
            with ui.element("div").classes("media-card"):
                with ui.element("div").classes("media-card-body"):
                    ui.html('<div class="media-card-title">How branding works</div>', sanitize=False)
                    ui.html(
                        '<div class="media-card-meta" style="line-height:1.5">'
                        "<strong>Chronos logo</strong> = product identity (any agency).<br/>"
                        "<strong>Department logo + photo</strong> = your organization only — "
                        "uploaded here, never shipped as defaults.<br/>"
                        "Clear removes the file from this installation."
                        "</div>",
                        sanitize=False,
                    )

        # —— Officers ——
        with ui.element("div").classes("panel w-full"):
            ui.html('<div class="panel-title">Officer portraits</div>', sanitize=False)
            ui.label("Select a tile, choose file, then save portrait").classes("text-xs q-mb-md").style(
                "color: var(--dim)"
            )

            officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
            state: dict = {"oid": officers[0]["id"] if officers else None}
            grid = ui.element("div").classes("officer-media-grid q-mb-md")
            detail = ui.element("div")

            def paint_grid():
                grid.clear()
                with grid:
                    if not officers:
                        ui.label("No active officers").classes("text-sm").style("color: var(--dim)")
                        return
                    for o in officers:
                        oid = o["id"]
                        active = " active" if state["oid"] == oid else ""
                        tile = ui.element("div").classes(f"officer-media-tile{active}")
                        with tile:
                            with ui.element("div").classes("thumb"):
                                p = officer_photo_path(oid)
                                if state["oid"] == oid and pending.get("officer_preview"):
                                    p = pending["officer_preview"]
                                if p and os.path.isfile(p):
                                    ui.image(p).style("width:100%;height:100%;object-fit:cover")
                                else:
                                    ui.label((o.get("name") or "?")[:1].upper()).style(
                                        "font-size:28px;color:var(--dim);font-weight:700"
                                    )
                            ui.html(
                                f'<div class="cap">{o.get("name") or "Officer"}</div>',
                                sanitize=False,
                            )
                        tile.on("click", lambda _e, i=oid: select_officer(i))

            def select_officer(oid: int):
                state["oid"] = oid
                pending["officer"] = None
                if pending.get("officer_preview") and os.path.isfile(pending["officer_preview"]):
                    try:
                        os.remove(pending["officer_preview"])
                    except OSError:
                        pass
                pending["officer_preview"] = None
                pending["officer_id"] = oid
                paint_grid()
                paint_detail()

            def paint_detail():
                detail.clear()
                oid = state.get("oid")
                with detail:
                    if not oid:
                        return
                    o = next((x for x in officers if x["id"] == oid), None)
                    name = (o or {}).get("name") or f"Officer {oid}"
                    with ui.row().classes("items-center gap-4 flex-wrap w-full"):
                        p = pending.get("officer_preview") or officer_photo_path(oid)
                        if p and os.path.isfile(p):
                            ui.image(p).style(
                                "width:72px;height:72px;border-radius:12px;object-fit:cover;"
                                "border:1px solid var(--border)"
                            )
                        with ui.element("div").classes("flex-grow"):
                            ui.label(name).classes("text-sm font-semibold")
                            if pending.get("officer") and pending.get("officer_id") == oid:
                                ui.label("Unsaved portrait staged — click Save portrait").classes("text-xs").style(
                                    "color: #fbbf24"
                                )
                            else:
                                ui.label(_file_meta(officer_photo_path(oid))).classes("text-xs").style(
                                    "color: var(--dim)"
                                )
                        up = (
                            ui.upload(label="Choose portrait file", auto_upload=True)
                            .props("accept=.png,.jpg,.jpeg,.webp flat dense color=cyan")
                            .classes("w-56")
                        )
                        save_btn = ui.button("Save portrait").classes("btn-primary").props("no-caps unelevated")

                        async def stage_off(e: events.UploadEventArguments, officer_id=oid):
                            data = await e.file.read()
                            pending["officer"] = data
                            pending["officer_id"] = officer_id
                            if pending.get("officer_preview") and os.path.isfile(pending["officer_preview"]):
                                try:
                                    os.remove(pending["officer_preview"])
                                except OSError:
                                    pass
                            name_f = getattr(e.file, "name", "") or "portrait.jpg"
                            suf = os.path.splitext(name_f)[1].lower() or ".jpg"
                            pending["officer_preview"] = _write_temp_preview(data, suf)
                            set_status("Portrait staged — click Save portrait", pending_note=True)
                            paint_grid()
                            paint_detail()

                        def save_off(officer_id=oid):
                            if pending.get("officer_id") != officer_id or not pending.get("officer"):
                                ui.notify("Choose a portrait file first", type="warning")
                                return
                            result = save_officer_photo_bytes(officer_id, pending["officer"])
                            if result.get("success"):
                                try:
                                    update_officer(officer_id, photo_path=result.get("photo_path"))
                                except Exception:
                                    pass
                                pending["officer"] = None
                                if pending.get("officer_preview") and os.path.isfile(pending["officer_preview"]):
                                    try:
                                        os.remove(pending["officer_preview"])
                                    except OSError:
                                        pass
                                pending["officer_preview"] = None
                                set_status("Officer portrait saved")
                                ui.notify("Officer portrait saved", type="positive")
                                paint_grid()
                                paint_detail()
                            else:
                                ui.notify(result.get("message", "Save failed"), type="negative")

                        up.on_upload(stage_off)
                        save_btn.on_click(save_off)

            paint_grid()
            paint_detail()

        with ui.row().classes("gap-2 q-mt-md flex-wrap"):

            def save_all_brand():
                saved = []
                if pending.get("chronos"):
                    if save_chronos_logo_bytes(pending["chronos"]).get("success"):
                        pending["chronos"] = None
                        saved.append("Chronos logo")
                if pending.get("logo"):
                    if save_department_logo_bytes(pending["logo"]).get("success"):
                        pending["logo"] = None
                        saved.append("Department logo")
                if pending.get("photo"):
                    if save_department_photo_bytes(pending["photo"]).get("success"):
                        pending["photo"] = None
                        saved.append("Department photo")
                _sync_brand()
                try:
                    paint_chronos()
                    paint_logo()
                    paint_photo()
                except Exception:
                    pass
                if saved:
                    set_status("Saved: " + ", ".join(saved))
                    ui.notify("Saved: " + ", ".join(saved), type="positive")
                else:
                    ui.notify("Nothing staged to save", type="info")

            ui.button("Save all staged brand files", on_click=save_all_brand).classes("btn-primary").props(
                "no-caps unelevated dense"
            )

    layout("media", body)
