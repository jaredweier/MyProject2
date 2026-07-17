"""Operational audit trail UI — exportable for municipal RFP / grievances."""

from __future__ import annotations

from nicegui import ui

from gui import session
from gui.shell import layout, page_header, panel
from logic import export_audit_csv, get_audit_log


def render_audit_trail() -> None:
    def body() -> None:
        if not (
            session.can("audit.view")
            or session.can("users.manage")
            or session.can("admin.settings")
            or session.can("reports.view")
        ):
            page_header("Audit trail", "Permission required", kicker="Chronos Command")
            ui.html(
                '<div class="alert alert-warn">Audit view requires elevated access.</div>',
                sanitize=False,
            )
            return

        page_header(
            "Audit trail",
            "Who approved leave, overrode rest, published schedules, changed notify settings",
            kicker="Security · Chronos Command",
        )

        filt = ui.input("Filter action contains", value="").classes("w-full q-mb-sm")
        host = ui.element("div")

        def refresh():
            host.clear()
            q = (filt.value or "").strip().lower()
            rows = get_audit_log(limit=100) or []
            if q:
                rows = [
                    r
                    for r in rows
                    if q in str(r.get("action") or "").lower() or q in str(r.get("details") or "").lower()
                ]
            with host:
                if not rows:
                    ui.label("No audit rows.").classes("text-sm").style("color: var(--dim)")
                    return
                with panel(f"{len(rows)} events"):
                    for r in rows:
                        with ui.element("div").classes("data-row"):
                            ui.label(
                                f"#{r.get('id')} · {r.get('action')} · "
                                f"{r.get('entity_type') or ''} {r.get('entity_id') or ''}"
                            ).classes("text-sm font-semibold")
                            ui.label(
                                f"{r.get('created_at') or ''} · user {r.get('user_id') or '—'} · "
                                f"{(r.get('details') or '')[:160]}"
                            ).classes("text-xs").style("color: var(--dim)")

        with ui.row().classes("gap-2 q-mb-md flex-wrap"):
            ui.button("Refresh", on_click=refresh).classes("btn-ghost").props("no-caps outline dense")

            def do_export():
                r = export_audit_csv()
                if r.get("success"):
                    ui.notify(f"Exported {r.get('path')}", type="positive")
                else:
                    ui.notify(r.get("message", "Export failed"), type="negative")

            ui.button("Export CSV", on_click=do_export).classes("btn-primary").props("no-caps unelevated dense")

        refresh()

    layout("audit", body)
