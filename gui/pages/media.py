"""Department Media — stage uploads, then Save to disk."""

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
    department_logo_path,
    department_photo_path,
    officer_photo_path,
    save_department_logo_bytes,
    save_department_photo_bytes,
    save_officer_photo_bytes,
)


def _file_meta(path: str | None) -> str:
    if not path or not os.path.isfile(path):
        return "No File On Disk — Choose File Then Save"
    try:
        st = os.stat(path)
        kb = max(1, st.st_size // 1024)
        # File mtime → department-local display
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


def render_media() -> None:
    def body() -> None:
        if not (session.can("officers.manage") or session.can("admin.settings") or session.can("settings.manage")):
            page_header("Department Media", "Permission Required", kicker="Command")
            ui.html(
                '<div class="alert alert-warn">Department Media Requires Supervisor Or Administration Access.</div>',
                sanitize=False,
            )
            return

        page_header(
            "Department Media",
            "Choose Files, Preview, Then Save — Logo (Sidebar) · Photo (Login Hero) · Officer Portraits",
            kicker="Command",
        )

        # Pending staged bytes until user clicks Save
        pending: dict = {
            "logo": None,  # bytes
            "logo_preview": None,  # temp path
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

        with ui.element("div").classes("grid-2").style("margin-bottom: 18px"):
            # —— Logo ——
            with ui.element("div").classes("media-card"):
                logo_hero = ui.element("div").classes("media-card-hero logo-hero")
                with ui.element("div").classes("media-card-body"):
                    ui.html('<div class="media-card-title">Department Logo</div>', sanitize=False)
                    logo_meta = ui.label("").classes("media-card-meta")
                    logo_upload = (
                        ui.upload(label="Choose Logo File", auto_upload=True)
                        .props("accept=.png,.jpg,.jpeg,.webp flat dense color=cyan")
                        .classes("w-full")
                    )
                    logo_save_btn = (
                        ui.button("Save Logo").classes("btn-primary w-full q-mt-sm").props("no-caps unelevated")
                    )

                def paint_logo():
                    logo_hero.clear()
                    show_path = pending.get("logo_preview") or department_logo_path()
                    if pending.get("logo"):
                        logo_meta.set_text("Unsaved Logo Staged — Click Save Logo")
                    else:
                        logo_meta.set_text(_file_meta(department_logo_path()) + " · Sidebar Mark")
                    with logo_hero:
                        if show_path and os.path.isfile(show_path):
                            ui.image(show_path).style(
                                "max-height:150px;max-width:88%;object-fit:contain;border-radius:8px"
                            )
                        else:
                            ui.html('<div class="media-empty">No Logo Yet</div>', sanitize=False)

                async def stage_logo(e: events.UploadEventArguments):
                    data = await e.file.read()
                    pending["logo"] = data
                    if pending.get("logo_preview") and os.path.isfile(pending["logo_preview"]):
                        try:
                            os.remove(pending["logo_preview"])
                        except OSError:
                            pass
                    name = getattr(e.file, "name", "") or "logo.png"
                    suf = os.path.splitext(name)[1].lower() or ".png"
                    pending["logo_preview"] = _write_temp_preview(data, suf)
                    set_status("Logo Staged — Click Save Logo To Apply", pending_note=True)
                    paint_logo()

                def save_logo():
                    data = pending.get("logo")
                    if not data:
                        ui.notify("Choose A Logo File First", type="warning")
                        return
                    result = save_department_logo_bytes(data)
                    if result.get("success"):
                        try:
                            from gui.brand_assets import sync_brand_files

                            sync_brand_files()
                        except Exception:
                            pass
                        pending["logo"] = None
                        if pending.get("logo_preview") and os.path.isfile(pending["logo_preview"]):
                            try:
                                os.remove(pending["logo_preview"])
                            except OSError:
                                pass
                        pending["logo_preview"] = None
                        set_status("Department Logo Saved")
                        ui.notify("Department Logo Saved", type="positive")
                        paint_logo()
                    else:
                        ui.notify(result.get("message", "Save Failed"), type="negative")

                logo_upload.on_upload(stage_logo)
                logo_save_btn.on_click(save_logo)
                paint_logo()

            # —— Photo ——
            with ui.element("div").classes("media-card"):
                photo_hero = ui.element("div").classes("media-card-hero")
                with ui.element("div").classes("media-card-body"):
                    ui.html('<div class="media-card-title">Department Photo</div>', sanitize=False)
                    photo_meta = ui.label("").classes("media-card-meta")
                    photo_upload = (
                        ui.upload(label="Choose Photo File", auto_upload=True)
                        .props("accept=.png,.jpg,.jpeg,.webp flat dense color=cyan")
                        .classes("w-full")
                    )
                    photo_save_btn = (
                        ui.button("Save Photo").classes("btn-primary w-full q-mt-sm").props("no-caps unelevated")
                    )

                def paint_photo():
                    photo_hero.clear()
                    show_path = pending.get("photo_preview") or department_photo_path()
                    if pending.get("photo"):
                        photo_meta.set_text("Unsaved Photo Staged — Click Save Photo")
                    else:
                        photo_meta.set_text(_file_meta(department_photo_path()) + " · Login Hero")
                    with photo_hero:
                        if show_path and os.path.isfile(show_path):
                            ui.image(show_path).style("width:100%;height:100%;object-fit:cover")
                        else:
                            ui.html(
                                '<div class="media-empty">No Department Photo Yet</div>',
                                sanitize=False,
                            )

                async def stage_photo(e: events.UploadEventArguments):
                    data = await e.file.read()
                    pending["photo"] = data
                    if pending.get("photo_preview") and os.path.isfile(pending["photo_preview"]):
                        try:
                            os.remove(pending["photo_preview"])
                        except OSError:
                            pass
                    name = getattr(e.file, "name", "") or "photo.jpg"
                    suf = os.path.splitext(name)[1].lower() or ".jpg"
                    pending["photo_preview"] = _write_temp_preview(data, suf)
                    set_status("Photo Staged — Click Save Photo To Apply", pending_note=True)
                    paint_photo()

                def save_photo():
                    data = pending.get("photo")
                    if not data:
                        ui.notify("Choose A Photo File First", type="warning")
                        return
                    result = save_department_photo_bytes(data)
                    if result.get("success"):
                        try:
                            from gui.brand_assets import sync_brand_files

                            sync_brand_files()
                        except Exception:
                            pass
                        pending["photo"] = None
                        if pending.get("photo_preview") and os.path.isfile(pending["photo_preview"]):
                            try:
                                os.remove(pending["photo_preview"])
                            except OSError:
                                pass
                        pending["photo_preview"] = None
                        set_status("Department Photo Saved")
                        ui.notify("Department Photo Saved", type="positive")
                        paint_photo()
                    else:
                        ui.notify(result.get("message", "Save Failed"), type="negative")

                photo_upload.on_upload(stage_photo)
                photo_save_btn.on_click(save_photo)
                paint_photo()

        # —— Officers ——
        with ui.element("div").classes("panel w-full"):
            ui.html('<div class="panel-title">Officer Portraits</div>', sanitize=False)
            ui.label("Select A Tile, Choose File, Then Save Portrait").classes("text-xs q-mb-md").style(
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
                        ui.label("No Active Officers").classes("text-sm").style("color: var(--dim)")
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
                # Clear staged portrait when switching officers
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
                                ui.label("Unsaved Portrait Staged — Click Save Portrait").classes("text-xs").style(
                                    "color: #fbbf24"
                                )
                            else:
                                ui.label(_file_meta(officer_photo_path(oid))).classes("text-xs").style(
                                    "color: var(--dim)"
                                )
                        up = (
                            ui.upload(label="Choose Portrait File", auto_upload=True)
                            .props("accept=.png,.jpg,.jpeg,.webp flat dense color=cyan")
                            .classes("w-56")
                        )
                        save_btn = ui.button("Save Portrait").classes("btn-primary").props("no-caps unelevated")

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
                            set_status("Portrait Staged — Click Save Portrait", pending_note=True)
                            paint_grid()
                            paint_detail()

                        def save_off(officer_id=oid):
                            if pending.get("officer_id") != officer_id or not pending.get("officer"):
                                ui.notify("Choose A Portrait File First", type="warning")
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
                                set_status("Officer Portrait Saved")
                                ui.notify("Officer Portrait Saved", type="positive")
                                paint_grid()
                                paint_detail()
                            else:
                                ui.notify(result.get("message", "Save Failed"), type="negative")

                        up.on_upload(stage_off)
                        save_btn.on_click(save_off)

            paint_grid()
            paint_detail()

        # —— Global save all staged brand assets ——
        with ui.row().classes("gap-2 q-mt-md flex-wrap"):

            def save_all_brand():
                saved = []
                if pending.get("logo"):
                    r = save_department_logo_bytes(pending["logo"])
                    if r.get("success"):
                        pending["logo"] = None
                        if pending.get("logo_preview") and os.path.isfile(pending["logo_preview"]):
                            try:
                                os.remove(pending["logo_preview"])
                            except OSError:
                                pass
                        pending["logo_preview"] = None
                        saved.append("Logo")
                if pending.get("photo"):
                    r = save_department_photo_bytes(pending["photo"])
                    if r.get("success"):
                        pending["photo"] = None
                        if pending.get("photo_preview") and os.path.isfile(pending["photo_preview"]):
                            try:
                                os.remove(pending["photo_preview"])
                            except OSError:
                                pass
                        pending["photo_preview"] = None
                        saved.append("Photo")
                if pending.get("officer") and pending.get("officer_id"):
                    oid = pending["officer_id"]
                    r = save_officer_photo_bytes(oid, pending["officer"])
                    if r.get("success"):
                        try:
                            update_officer(oid, photo_path=r.get("photo_path"))
                        except Exception:
                            pass
                        pending["officer"] = None
                        if pending.get("officer_preview") and os.path.isfile(pending["officer_preview"]):
                            try:
                                os.remove(pending["officer_preview"])
                            except OSError:
                                pass
                        pending["officer_preview"] = None
                        saved.append("Portrait")
                try:
                    from gui.brand_assets import sync_brand_files

                    sync_brand_files()
                except Exception:
                    pass
                if saved:
                    set_status("Saved: " + ", ".join(saved))
                    ui.notify("Saved: " + ", ".join(saved), type="positive")
                    paint_logo()
                    paint_photo()
                    paint_grid()
                    paint_detail()
                else:
                    ui.notify("Nothing Staged To Save", type="warning")

            ui.button("Save All Staged Changes", on_click=save_all_brand).classes("btn-primary").props(
                "no-caps unelevated"
            )
            ui.label("Choose Files First, Then Save — Changes Are Not Applied Until Save.").classes("text-xs").style(
                "color: var(--dim)"
            )

    layout("media", body)
