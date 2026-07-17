"""UAT tester hub — full product map for remote virtual testing."""

from __future__ import annotations

from nicegui import ui

from gui import session
from gui.shell import layout, page_header, panel
from logic.uat_lab import uat_feature_map, uat_lab_enabled


def render_uat_hub() -> None:
    def body() -> None:
        page_header(
            "UAT Lab",
            "Full product map — open any page. Administration sees everything in the left nav.",
            kicker="Virtual test",
        )
        role = str((session.current_user() or {}).get("role") or "")
        is_admin = role == "Administration"

        with panel("How to test everything", glow=True):
            if is_admin:
                ui.label(
                    "You are Administration — left nav is the full product. "
                    "Use the tiles below or the rail. Sign out → supervisor/officer only to check limited roles."
                ).classes("text-sm")
            else:
                ui.label(
                    f"Signed in as {role}. Officer/Supervisor nav is intentionally limited. "
                    "Sign out and use admin / admin for full product access."
                ).classes("text-sm")

                def _to_login() -> None:
                    session.set_user(None)
                    ui.navigate.to("/login")

                ui.button("Sign out → full product (admin)", on_click=_to_login).classes("btn-primary q-mt-sm").props(
                    "no-caps unelevated"
                )

            ui.html(
                "<ul class='text-sm' style='margin:12px 0 0 18px;opacity:0.9'>"
                "<li><b>Leave</b> — Time Off: submit, preview coverage, approve / reject</li>"
                "<li><b>Coverage</b> — Ops Desk, Live Schedule, Open Shifts, Callbacks</li>"
                "<li><b>Finance</b> — Timecards, Payroll, Banks, Time Punch</li>"
                "<li><b>Admin</b> — Roster, Access Control, Security, Deploy, Audit</li>"
                "<li><b>Not live SMS/email</b> — Channels uses file/in-app sink until carriers configured</li>"
                "</ul>",
                sanitize=False,
            )

        if uat_lab_enabled():
            ui.badge("UAT lab mode on").props("color=primary outline").classes("q-mb-sm")

        areas: dict[str, list] = {}
        for item in uat_feature_map():
            areas.setdefault(item["area"], []).append(item)

        for area, items in areas.items():
            ui.label(area).classes("text-xs q-mt-md q-mb-xs").style(
                "letter-spacing:0.08em;text-transform:uppercase;opacity:0.7"
            )
            with (
                ui.element("div")
                .classes("w-full")
                .style("display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px")
            ):
                for item in items:
                    path = item["path"]
                    title = item["title"]

                    def _go(p: str = path) -> None:
                        ui.navigate.to(p)

                    with (
                        ui.element("div")
                        .classes("panel w-full")
                        .style("padding:12px;cursor:pointer;min-height:72px")
                        .on("click", _go)
                    ):
                        ui.label(title).classes("text-sm font-semibold")
                        ui.label(path).classes("text-xs").style("opacity:0.55")

        ui.label("Tip: stay on the public tunnel URL — do not switch to localhost.").classes("text-xs q-mt-lg").style(
            "opacity:0.65"
        )

    layout("/uat", body)
