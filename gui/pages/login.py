"""Secure access — Chronos Command login with department photo hero + logo."""

from __future__ import annotations

import os

from nicegui import ui

from config import APP_NAME
from gui import session
from gui.shell import apply_theme
from logic import authenticate_user


def render_login() -> None:
    apply_theme()
    ui.add_head_html(
        """
        <style>
          .q-header, .q-drawer, .nicegui-header { display: none !important; }
          .nicegui-content { padding: 0 !important; }
        </style>
        """,
        shared=False,
    )

    if session.current_user():
        ui.navigate.to("/")
        return

    logo_path = None
    photo_path = None
    try:
        from gui.brand_assets import sync_brand_files
        from photos import department_logo_path, department_photo_path

        sync_brand_files()
        logo_path = department_logo_path()
        photo_path = department_photo_path()
    except Exception:
        pass

    def submit() -> None:
        error.set_text("")
        auth = authenticate_user((username.value or "").strip(), password.value or "")
        if not auth.get("success"):
            error.set_text(auth.get("message") or "Invalid Credentials")
            return
        user = dict(auth["user"])
        if user.get("must_change_password"):
            ui.notify(
                "Password change recommended (demo accounts may require CLI reset).",
                type="warning",
                position="top",
            )
            user["must_change_password"] = 0
        session.set_user(user)
        try:
            from logic import log_audit_action

            log_audit_action(
                "user.login",
                "app_user",
                user.get("id"),
                user.get("id"),
                details="chronos_command",
            )
        except Exception:
            pass
        ui.navigate.to("/")

    with ui.element("div").classes("login-shell"):
        with ui.element("div").classes("login-hero"):
            # Full-bleed department photo behind copy
            if photo_path and os.path.isfile(photo_path):
                ui.image(photo_path).classes("login-hero-photo")
            if logo_path and os.path.isfile(logo_path):
                ui.image(logo_path).classes("login-hero-logo")
            ui.html(
                '<div class="page-kicker" style="margin-bottom:16px">Authorized Access Only</div>',
                sanitize=False,
            )
            ui.html(f"<h1>{APP_NAME}</h1>", sanitize=False)
            ui.html(
                "<p>Law Enforcement Duty Scheduling — Live Coverage, Leave, Roster, And Payroll.</p>",
                sanitize=False,
            )
            ui.html(
                '<div style="margin-top:28px;display:flex;gap:8px;flex-wrap:wrap">'
                '<span class="chip" style="border-color:rgba(34,197,94,0.4);color:#4ade80">'
                "● System Live</span>"
                '<span class="chip">Dark Ops</span>'
                '<span class="chip">Multi-User</span>'
                "</div>",
                sanitize=False,
            )

        with ui.element("div").classes("login-form-wrap"):
            with ui.element("div").classes("login-card"):
                ui.html('<div class="page-kicker">Secure Access</div>', sanitize=False)
                ui.html("<h2>Sign In</h2>", sanitize=False)
                ui.html(
                    '<p class="page-sub" style="margin-bottom:22px">Department Credentials Required.</p>',
                    sanitize=False,
                )
                with ui.element("div").classes("panel panel-glow"):
                    ui.label("Username").classes("text-xs mb-1").style("color: var(--dim)")
                    username = ui.input(placeholder="Username").classes("w-full").props("outlined dense dark autofocus")
                    ui.label("Password").classes("text-xs mb-1 q-mt-md").style("color: var(--dim)")
                    password = (
                        ui.input(placeholder="Password", password=True, password_toggle_button=True)
                        .classes("w-full")
                        .props("outlined dense dark")
                    )
                    error = ui.label("").classes("text-red-400 text-sm q-mt-sm")
                    password.on("keydown.enter", submit)
                    ui.button("Sign In", on_click=submit).classes("btn-primary w-full q-mt-md").props(
                        "no-caps unelevated"
                    )
