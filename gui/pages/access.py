"""Access control — logins and roles (enterprise user admin)."""

from __future__ import annotations

from nicegui import ui

from gui import session
from gui.shell import layout, page_header, panel
from logic import (
    admin_reset_user_password,
    complete_initial_setup,
    create_app_user,
    list_login_users,
    update_app_user,
)
from permissions import USER_ROLES


def render_access() -> None:
    def body() -> None:
        if not (session.can("users.manage") or session.can("users.edit_role")):
            page_header("Access Control", "Permission Required", kicker="Command")
            ui.html(
                '<div class="alert alert-warn">User Administration Requires Elevated Access.</div>',
                sanitize=False,
            )
            return

        page_header("Access Control", "Logins, Roles, And Credentials", kicker="Command")
        ui.button(
            "Security & Governance",
            on_click=lambda: ui.navigate.to("/security"),
        ).classes("btn-ghost q-mb-md").props("no-caps outline dense")

        with ui.element("div").classes("grid-2"):
            list_host = ui.element("div")
            state: dict = {"selected": None}

            def refresh():
                list_host.clear()
                with list_host:
                    users = list_login_users()
                    if not users:
                        ui.html('<div class="alert alert-warn">No users.</div>', sanitize=False)
                        return
                    for u in users:
                        with ui.element("div").classes("data-row").on("click", lambda _e, row=u: select_user(row)):
                            with ui.element("div"):
                                ui.label(str(u.get("username", ""))).classes("text-sm font-semibold")
                                linked = u.get("officer_name")
                                active = "active" if u.get("active") else "inactive"
                                ui.label(
                                    f"{u.get('role') or 'Officer'} · {active}"
                                    + (f" · linked {linked}" if linked else "")
                                ).classes("text-xs text-gray-500")

            def select_user(row: dict):
                state["selected"] = row
                edit_user.value = row.get("username") or ""
                edit_role.value = row.get("role") or "Officer"
                sel_lbl.set_text(f"Selected #{row.get('id')} · {row.get('username')}")

            with panel("Users"):
                ui.button("Refresh", on_click=refresh).classes("btn-ghost q-mb-sm").props("no-caps outline dense")
                refresh()

            with panel("Create user"):
                uname = ui.input(label="Username").classes("w-full")
                pw = ui.input(label="Password", password=True).classes("w-full")
                role = ui.select(list(USER_ROLES), value="Officer", label="Role").classes("w-full")

                def create():
                    if not session.can("users.manage"):
                        ui.notify("Only administration can create users", type="warning")
                        return
                    actor = (session.current_user() or {}).get("id")
                    result = create_app_user(
                        (uname.value or "").strip(),
                        pw.value or "",
                        role.value,
                        actor_user_id=actor,
                    )
                    if result.get("success"):
                        ui.notify(result.get("message", "Created"), type="positive")
                        uname.value = ""
                        pw.value = ""
                        refresh()
                    else:
                        ui.notify(result.get("message", "Failed"), type="negative")

                ui.button("Create user", on_click=create).classes("btn-primary w-full q-mt-sm").props(
                    "no-caps unelevated"
                )

        # Enterprise mutators: role update + password reset (PowerTime/admin pattern)
        with panel("Edit selected user", glow=True):
            sel_lbl = ui.label("Click a user in the list").classes("text-xs text-gray-500 q-mb-sm")
            edit_user = ui.input(label="Username (read-only hint)").classes("w-full").props("readonly")
            edit_role = ui.select(list(USER_ROLES), value="Officer", label="Role").classes("w-full")
            new_pw = ui.input(label="New password (reset)", password=True).classes("w-full")

            def save_role():
                row = state.get("selected")
                if not row:
                    ui.notify("Select a user first", type="warning")
                    return
                actor = (session.current_user() or {}).get("id")
                r = update_app_user(int(row["id"]), role=edit_role.value, actor_user_id=actor)
                ui.notify(
                    r.get("message", "Updated") if r.get("success") else r.get("message", "Failed"),
                    type="positive" if r.get("success") else "negative",
                )
                if r.get("success"):
                    refresh()

            def reset_pw():
                row = state.get("selected")
                if not row:
                    ui.notify("Select a user first", type="warning")
                    return
                pw_val = new_pw.value or ""
                if len(pw_val) < 8:
                    ui.notify("Password must be at least 8 characters", type="negative")
                    return
                actor = (session.current_user() or {}).get("id")
                r = admin_reset_user_password(
                    int(row["id"]),
                    pw_val,
                    must_change_password=True,
                    actor_user_id=actor,
                )
                ui.notify(
                    r.get("message", "Password reset") if r.get("success") else r.get("message", "Failed"),
                    type="positive" if r.get("success") else "negative",
                )
                if r.get("success"):
                    new_pw.value = ""

            with ui.row().classes("gap-2 q-mt-sm flex-wrap"):
                ui.button("Save role", on_click=save_role).classes("btn-primary").props("no-caps unelevated dense")
                ui.button("Reset password", on_click=reset_pw).classes("btn-ghost").props("no-caps outline dense")

        if session.can("users.manage") or session.can("admin.settings") or session.can("settings.manage"):
            with panel("Department setup (initial)", glow=False):
                ui.label("First-run / re-brand: set department display name used in exports and headers.").classes(
                    "text-xs text-gray-500 q-mb-sm"
                )
                from config import DEFAULT_DEPARTMENT_NAME

                dept = ui.input(
                    label="Department name",
                    value=DEFAULT_DEPARTMENT_NAME,
                ).classes("w-full")

                def do_setup():
                    actor = (session.current_user() or {}).get("id")
                    r = complete_initial_setup((dept.value or "").strip(), actor_user_id=actor)
                    ui.notify(
                        r.get("message", "Setup saved") if r.get("success") else r.get("message", "Failed"),
                        type="positive" if r.get("success") else "negative",
                    )

                ui.button("Save department setup", on_click=do_setup).classes("btn-ghost").props(
                    "no-caps outline dense"
                )

    layout("access", body)
