"""Secure access — Chronos Command login (Deep Chrome)."""

from __future__ import annotations

import os

from nicegui import ui

from config import APP_NAME, APP_VERSION, COMPANY_NAME, PRODUCT_TAGLINE
from gui import session
from gui.shell import apply_theme
from logic import authenticate_user, complete_mfa_login


def render_login() -> None:
    apply_theme()
    # Login-only CSS — do not depend on cache; force button + full-viewport center
    ui.add_head_html(
        """
        <style>
          .q-header, .q-drawer, .nicegui-header { display: none !important; }
          html, body, .q-layout, .q-page-container, .q-page, .nicegui-content {
            padding: 0 !important; margin: 0 !important;
            min-height: 100vh !important; min-height: 100dvh !important;
            width: 100% !important; max-width: none !important;
            background: #060D18 !important;
          }
          .nicegui-content { display: flex !important; flex-direction: column !important; }
          /* Beat Quasar primary on Sign In */
          .login-center-shell .q-btn.btn-primary,
          .login-submit.q-btn {
            background: linear-gradient(180deg, #6BA3F5 0%, #3B7DD8 50%, #1E5AA8 100%) !important;
            background-color: #3B7DD8 !important;
            color: #F0F7FF !important;
            border: 1px solid rgba(107, 163, 245, 0.6) !important;
            min-height: 46px !important;
            font-size: 15px !important;
            font-weight: 650 !important;
          }
          .login-submit.q-btn .q-btn__content {
            color: #F0F7FF !important; opacity: 1 !important;
          }
        </style>
        """,
        shared=False,
    )

    if session.current_user():
        ui.navigate.to("/")
        return

    chronos_path = None
    logo_path = None
    photo_path = None
    try:
        from gui.brand_assets import sync_brand_files
        from photos import chronos_logo_path, department_logo_path, department_photo_path

        sync_brand_files()
        chronos_path = chronos_logo_path()
        logo_path = department_logo_path()
        photo_path = department_photo_path()
    except Exception:
        pass

    error_label = {"el": None}
    mfa_state = {"pending_user_id": None}

    def _complete_login(user: dict) -> None:
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

    def submit() -> None:
        el = error_label["el"]
        if el is not None:
            el.set_text("")
        auth = authenticate_user((username.value or "").strip(), password.value or "")
        if auth.get("mfa_required"):
            mfa_state["pending_user_id"] = auth.get("user_id")
            username.set_visibility(False)
            password.set_visibility(False)
            sign_in_btn.set_visibility(False)
            mfa_row.set_visibility(True)
            mfa_code.run_method("focus")
            if el is not None:
                el.set_text(auth.get("message") or "Enter your authenticator code")
            return
        if not auth.get("success"):
            if el is not None:
                el.set_text(auth.get("message") or "Invalid credentials")
            return
        _complete_login(dict(auth["user"]))

    def submit_mfa() -> None:
        el = error_label["el"]
        if el is not None:
            el.set_text("")
        user_id = mfa_state["pending_user_id"]
        if not user_id:
            return
        result = complete_mfa_login(user_id, (mfa_code.value or "").strip())
        if not result.get("success"):
            if el is not None:
                el.set_text(result.get("message") or "Invalid code")
            return
        _complete_login(dict(result["user"]))

    # Centered card on full viewport (not a split that looks "off to the side")
    with ui.element("div").classes("login-center-shell"):
        if photo_path and os.path.isfile(photo_path):
            ui.image(photo_path).classes("login-center-bg")
        with ui.element("div").classes("login-card login-center-card"):
            with ui.element("div").classes("login-form-product"):
                if chronos_path and os.path.isfile(chronos_path):
                    ui.image(chronos_path).classes("login-mark-img")
                elif logo_path and os.path.isfile(logo_path):
                    ui.image(logo_path).classes("login-mark-img login-mark-img--seal")
                else:
                    ui.html('<div class="login-mark-fallback">CC</div>', sanitize=False)
                with ui.element("div"):
                    ui.html(
                        f'<div class="login-kicker">{PRODUCT_TAGLINE}</div>'
                        f'<h2 class="login-form-title product-brand" style="margin:0">{APP_NAME}</h2>'
                        f'<div class="login-vendor" style="font-size:12px;opacity:0.8;margin-top:4px">'
                        f"{COMPANY_NAME}</div>",
                        sanitize=False,
                    )
            uat_on = False
            try:
                import socket as _sock

                from logic.uat_lab import uat_lab_enabled

                def _is_loopback_only() -> bool:
                    """Return True only if server is bound to loopback (127.x / ::1)."""
                    try:
                        host = _sock.gethostbyname(_sock.gethostname())
                        return host.startswith("127.") or host == "::1"
                    except Exception:
                        return False  # fail safe: treat as public

                uat_on = uat_lab_enabled() and _is_loopback_only()
            except Exception:
                uat_on = False

            if uat_on:
                ui.html(
                    '<p class="login-form-sub" style="margin-bottom:8px">'
                    "<b>Remote UAT lab</b> — one click for full product (all pages). "
                    "Or sign in as supervisor / officer to check limited roles."
                    "</p>",
                    sanitize=False,
                )
            else:
                ui.html(
                    '<p class="login-form-sub">Department credentials required. Upload your Chronos logo under Branding &amp; Media before deployment.</p>',
                    sanitize=False,
                )

            username = (
                ui.input(label="Username", placeholder="Username")
                .classes("w-full login-field")
                .props('outlined dense dark autofocus stack-label data-testid="login-username"')
            )
            password = (
                ui.input(
                    label="Password",
                    placeholder="Password",
                    password=True,
                    password_toggle_button=True,
                )
                .classes("w-full login-field q-mt-sm")
                .props('outlined dense dark stack-label data-testid="login-password"')
            )
            error_label["el"] = ui.label("").classes("login-error").props('data-testid="login-error"')
            password.on("keydown.enter", submit)

            with ui.row().classes("w-full q-mt-sm") as mfa_row:
                mfa_code = (
                    ui.input(label="Authenticator code", placeholder="6-digit code")
                    .classes("w-full login-field")
                    .props('outlined dense dark maxlength=6 data-testid="login-mfa-code"')
                )
            mfa_row.set_visibility(False)
            mfa_code.on("keydown.enter", submit_mfa)
            if uat_on:

                def enter_full() -> None:
                    username.value = "admin"
                    password.value = "admin"
                    submit()

                ui.html(
                    '<div style="background:rgba(232,93,93,.15);border:1px solid rgba(232,93,93,.4);'
                    'border-radius:8px;padding:8px 12px;font-size:12px;color:#f87171;margin-bottom:8px">'
                    "⚠ UAT mode active — loopback only. Do not deploy with SCHEDULER_UAT_LAB=1 on a public host.</div>",
                    sanitize=False,
                )
                ui.button(
                    "Enter full product (Administration)",
                    on_click=enter_full,
                ).classes("btn-primary w-full login-submit q-mt-sm").props(
                    'no-caps unelevated data-testid="login-uat-full"'
                )
                ui.label("admin / admin · full left nav · every feature").classes("text-xs").style(
                    "opacity:0.75;margin:6px 0 8px"
                )
            sign_in_btn = (
                ui.button("Sign In", on_click=submit)
                .classes("btn-primary w-full login-submit")
                .props('no-caps unelevated data-testid="login-submit"')
            )
            ui.button("Verify code", on_click=submit_mfa).classes("btn-primary w-full login-submit q-mt-sm").props(
                'no-caps unelevated data-testid="login-mfa-submit"'
            ).bind_visibility_from(mfa_row)
            if uat_on:
                ui.html(
                    '<p class="login-form-sub" style="margin-top:10px;font-size:12px;opacity:0.8">'
                    "After login open <b>UAT Lab</b> in the nav (or /uat) for a map of every page. "
                    "Live SMS/email not required for this lab."
                    "</p>",
                    sanitize=False,
                )
            ui.html(
                f'<div class="login-foot"><span class="product-brand">{APP_NAME}</span>'
                f" · v{APP_VERSION}<br/>"
                f'<span style="opacity:0.75">{COMPANY_NAME}</span></div>',
                sanitize=False,
            )
