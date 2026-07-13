"""Certifications — LE/fire quals gate (PowerTime / Snap pattern)."""

from __future__ import annotations

from nicegui import ui

from gui import session
from gui.clock import today_local
from gui.shell import layout, page_header, panel
from logic import get_officers_by_seniority
from logic.certifications import (
    assign_officer_certification,
    get_officer_certifications,
    get_shift_cert_requirements,
    list_certification_types,
    list_immunization_types,
    officer_immunization_status,
    set_shift_cert_requirement,
)
from logic.staffing_config import get_active_shift_times
from validators import format_date, parse_date


def render_certs() -> None:
    def body() -> None:
        page_header(
            "Certifications",
            "Officer quals · band requirements for open-shift claim gates",
            kicker="Personnel · LE pattern",
        )
        can_manage = session.can("officers.manage") or session.can("admin.settings") or session.can("settings.manage")

        types = list_certification_types(active_only=True) or []
        type_labels = {f"{t.get('code')}: {t.get('name')}": t["id"] for t in types if t.get("id")}

        with ui.element("div").classes("grid-2"):
            with panel("Officer certifications", glow=True):
                officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
                if session.is_officer() and session.linked_officer_id():
                    officers = [o for o in officers if o["id"] == session.linked_officer_id()]
                names = [o["name"] for o in officers]
                omap = {o["name"]: o["id"] for o in officers}
                pick = ui.select(names, value=names[0] if names else None, label="Officer").classes("w-full")
                cert_host = ui.element("div")

                def show_certs():
                    cert_host.clear()
                    oid = omap.get(pick.value) if pick.value else None
                    with cert_host:
                        if not oid:
                            return
                        rows = get_officer_certifications(oid) or []
                        if not rows:
                            ui.label("No certifications on file.").classes("text-sm text-gray-500")
                        for c in rows:
                            if not isinstance(c, dict):
                                continue
                            exp = c.get("expires_date") or c.get("expires") or ""
                            ui.label(
                                f"{c.get('code') or c.get('cert_code') or ''} "
                                f"{c.get('name') or c.get('cert_name') or ''} · exp {format_date(exp) if exp else '—'}"
                            ).classes("text-sm q-mb-xs")

                # ESO-style immunization readiness
                with panel("Immunizations / medical readiness", glow=False):
                    ui.label(
                        "Fire/EMS pattern (ESO): track immunizations alongside certs for roster readiness."
                    ).classes("text-xs text-gray-500 q-mb-sm")
                    imm_host = ui.element("div")

                    def show_imm():
                        imm_host.clear()
                        oid = omap.get(pick.value) if pick.value else None
                        with imm_host:
                            if not oid:
                                return
                            try:
                                st = officer_immunization_status(oid) or {}
                            except Exception as exc:
                                ui.label(str(exc)).classes("text-sm text-red-400")
                                return
                            flag = "READY" if st.get("ok") else "GAPS"
                            ui.label(
                                f"{flag} · missing {st.get('missing', 0)} · expired {st.get('expired', 0)}"
                            ).classes("text-sm font-semibold q-mb-xs")
                            for it in st.get("items") or []:
                                ui.label(
                                    f"{it.get('code')} {it.get('name')}: {it.get('status')}"
                                    + (f" exp {it.get('expires_date')}" if it.get("expires_date") else "")
                                ).classes("text-xs text-gray-400")
                            imm_types = list_immunization_types() or []
                            if not imm_types:
                                ui.label("No immunization types yet — run app once to seed IMM_* types.").classes(
                                    "text-xs text-gray-500"
                                )

                    def refresh_officer_panels():
                        show_certs()
                        show_imm()

                    pick.on_value_change(lambda _: refresh_officer_panels())
                    refresh_officer_panels()

                if can_manage and type_labels:
                    ui.separator()
                    ui.label("Assign certification").classes("text-xs text-gray-500")
                    t_sel = ui.select(
                        list(type_labels.keys()), value=list(type_labels.keys())[0], label="Type"
                    ).classes("w-full")
                    issued = ui.input(label="Issued (optional)", value=today_local().isoformat()).classes("w-full")
                    expires = ui.input(label="Expires (optional)", value="").classes("w-full")

                    def assign():
                        oid = omap.get(pick.value)
                        tid = type_labels.get(t_sel.value)
                        if not oid or not tid:
                            ui.notify("Select officer and type", type="warning")
                            return
                        exp = (expires.value or "").strip()
                        exp_iso = None
                        if exp:
                            dt = parse_date(exp)
                            exp_iso = dt.isoformat() if dt else None
                        iss = parse_date((issued.value or "").strip())
                        uid = (session.current_user() or {}).get("id")
                        r = assign_officer_certification(
                            oid,
                            int(tid),
                            issued_date=iss.isoformat() if iss else None,
                            expires_date=exp_iso,
                            user_id=uid,
                        )
                        ui.notify(
                            r.get("message", "Assigned") if r.get("success") else r.get("message", "Failed"),
                            type="positive" if r.get("success") else "negative",
                        )
                        show_certs()

                    ui.button("Assign cert", on_click=assign).classes("btn-primary q-mt-sm").props("no-caps unelevated")

            with panel("Shift-band requirements"):
                reqs = get_shift_cert_requirements() or []
                if not reqs:
                    ui.html(
                        '<div class="alert alert-ok">No band requirements — open shifts accept any active officer '
                        "(after other rules).</div>",
                        sanitize=False,
                    )
                else:
                    for r in reqs:
                        if isinstance(r, dict):
                            ui.label(
                                f"{r.get('shift_start') or r.get('band')}: "
                                f"{r.get('cert_code') or r.get('code') or r.get('cert_type_id')}"
                            ).classes("text-sm q-mb-xs")
                if can_manage and type_labels:
                    ui.separator()
                    starts = []
                    try:
                        starts = [s for s, _e in get_active_shift_times().values()]
                    except Exception:
                        starts = ["06:00", "10:00", "15:00", "19:00"]
                    b_sel = ui.select(starts or ["19:00"], value=(starts or ["19:00"])[-1], label="Band").classes(
                        "w-full"
                    )
                    t2 = ui.select(
                        list(type_labels.keys()), value=list(type_labels.keys())[0], label="Required cert"
                    ).classes("w-full")

                    def set_req():
                        tid = type_labels.get(t2.value)
                        uid = (session.current_user() or {}).get("id")
                        r = set_shift_cert_requirement(b_sel.value, int(tid), user_id=uid)
                        ui.notify(
                            r.get("message", "Saved") if r.get("success") else r.get("message", "Failed"),
                            type="positive" if r.get("success") else "negative",
                        )
                        ui.navigate.to("/certs")

                    ui.button("Require cert on band", on_click=set_req).classes("btn-ghost q-mt-sm").props(
                        "no-caps outline dense"
                    )

    layout("certs", body)
