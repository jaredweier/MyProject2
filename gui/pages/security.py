"""Security & Governance — honest compliance posture (not certification claims)."""

from __future__ import annotations

import os

from nicegui import ui

from config import APP_NAME, APP_VERSION  # APP_NAME = Chronos Command
from gui import session
from gui.clock import format_local_datetime, timezone_label
from gui.shell import layout, page_header, panel
from logic import get_audit_log
from permissions import PERMISSIONS, USER_ROLES, role_has_permission
from validators import format_datetime

# Honest posture: Active = implemented; Target = roadmap; Not Configured = absent
DISCLAIMER = (
    "Not FBI-Certified. Not A Substitute For Agency CJIS Assessment. "
    "FIPS 140-2 Requires Validated Crypto Modules In The Hosting Environment. "
    "This Page Reports Application Controls And Design Targets Only."
)

# Sensitive capability groups for RBAC display
SENSITIVE_PERMS = [
    ("Payroll · View All", "payroll.view_all"),
    ("Payroll · Edit", "payroll.edit"),
    ("Payroll · Lock Period", "payroll.lock_period"),
    ("Timecard · View All", "timecard.view_all"),
    ("Timecard · Approve", "timecard.approve"),
    ("Officers · Manage", "officers.manage"),
    ("Users · Manage", "users.manage"),
    ("Users · Edit Role", "users.edit_role"),
    ("Requests · Approve", "requests.approve"),
    ("Schedule · Publish Base", "schedule.base.publish"),
    ("Reports · View", "reports.view"),
    ("Audit · View", "audit.view"),
    ("Database · Backup", "database.backup"),
    ("Settings · Manage", "settings.manage"),
]


def _status_chip(label: str, state: str) -> str:
    """state: active | target | off"""
    colors = {
        "active": ("rgba(34,197,94,0.12)", "#4ade80", "rgba(34,197,94,0.4)"),
        "target": ("rgba(245,158,11,0.12)", "#fbbf24", "rgba(245,158,11,0.4)"),
        "off": ("rgba(148,163,184,0.08)", "#94a3b8", "rgba(148,163,184,0.25)"),
    }
    bg, fg, bd = colors.get(state, colors["off"])
    return (
        f'<span style="display:inline-flex;align-items:center;padding:4px 10px;border-radius:999px;'
        f"font-size:11px;font-weight:700;letter-spacing:0.04em;background:{bg};color:{fg};"
        f'border:1px solid {bd}">{label}</span>'
    )


def render_security() -> None:
    def body() -> None:
        page_header(
            "Security & Governance",
            "Role-Based Access, Operational Audit Trails, And Compliance Design Targets",
            kicker="Command",
        )

        ui.html(
            f'<div class="alert alert-warn" style="margin-bottom:16px">{DISCLAIMER}</div>',
            sanitize=False,
        )

        # —— Database backup (functional — was only on Ops Reports) ——
        if session.can("database.backup") or session.can("admin.settings") or session.can("settings.manage"):
            with panel("Database backup & restore", glow=True):
                try:
                    from logic import get_backup_status

                    bst = get_backup_status() or {}
                except Exception:
                    bst = {}
                ui.label(
                    f"Backups: {bst.get('backup_count', '—')} · age days={bst.get('latest_age_days', '—')} · "
                    f"{'needs backup' if bst.get('needs_backup') else 'fresh enough'} · "
                    f"dir {bst.get('backup_dir') or 'data/backups'}"
                ).classes("text-xs q-mb-sm").style("color: var(--dim)")
                if bst.get("latest_path"):
                    ui.label(f"Latest: {bst.get('latest_path')}").classes("text-xs mono q-mb-sm").style(
                        "color: var(--muted)"
                    )

                def do_backup():
                    try:
                        from logic import backup_database

                        path = backup_database()
                        ui.notify(f"Backup written: {path}", type="positive")
                    except Exception as exc:
                        ui.notify(str(exc), type="negative")

                def do_auto():
                    try:
                        from logic import maybe_run_auto_backup

                        r = maybe_run_auto_backup()
                        if isinstance(r, dict):
                            ui.notify(r.get("message") or str(r), type="info")
                        else:
                            ui.notify(str(r) if r else "Auto-backup checked", type="info")
                    except Exception as exc:
                        ui.notify(str(exc), type="negative")

                restore_path = ui.input(
                    label="Restore from path (danger — overwrites live DB)",
                    value=str(bst.get("latest_path") or ""),
                ).classes("w-full")

                def do_restore():
                    p = (restore_path.value or "").strip()
                    if not p:
                        ui.notify("Enter a backup file path", type="warning")
                        return
                    uid = (session.current_user() or {}).get("id")
                    try:
                        from logic import restore_database_from_backup

                        r = restore_database_from_backup(p, user_id=uid)
                    except Exception as exc:
                        r = {"success": False, "message": str(exc)}
                    ui.notify(
                        r.get("message", "Restore") if r.get("success") else r.get("message", "Failed"),
                        type="warning" if r.get("success") else "negative",
                        multi_line=True,
                    )

                with ui.row().classes("gap-2 flex-wrap"):
                    ui.button("Run backup now", on_click=do_backup).classes("btn-primary").props(
                        "no-caps unelevated dense"
                    )
                    ui.button("Maybe auto-backup", on_click=do_auto).classes("btn-ghost").props("no-caps outline dense")
                    ui.button("Restore from path", on_click=do_restore).classes("btn-danger").props(
                        "no-caps outline dense"
                    )
                    ui.button("Exports hub", on_click=lambda: ui.navigate.to("/exports")).classes("btn-ghost").props(
                        "no-caps outline dense"
                    )

        # —— Posture matrix ——
        tls_hint = "Require TLS Termination In Production (Reverse Proxy / Hosting)"
        secret_set = bool(os.environ.get("SCHEDULER_STORAGE_SECRET", "").strip())
        session_secret = "Active (Env Secret)" if secret_set else "Local Dev Secret File"

        ui.html(
            f"""
            <div class="kpi-row q-mb-md">
              <div class="kpi g">
                <div class="kpi-l">Role-Based Access</div>
                <div class="kpi-v" style="font-size:18px;margin-top:10px">Active</div>
                <div class="kpi-hint">Application RBAC Enforced</div>
              </div>
              <div class="kpi g">
                <div class="kpi-l">Application Audit Log</div>
                <div class="kpi-v" style="font-size:18px;margin-top:10px">Available</div>
                <div class="kpi-hint">Operational Trail · Not CJIS Seal</div>
              </div>
              <div class="kpi w">
                <div class="kpi-l">Encryption In Transit</div>
                <div class="kpi-v" style="font-size:16px;margin-top:10px">Deploy Target</div>
                <div class="kpi-hint">{tls_hint}</div>
              </div>
              <div class="kpi d">
                <div class="kpi-l">FIPS 140-2 At Rest</div>
                <div class="kpi-v" style="font-size:16px;margin-top:10px">Not Configured</div>
                <div class="kpi-hint">Hosting / KMS Target</div>
              </div>
              <div class="kpi w">
                <div class="kpi-l">CJIS Alignment</div>
                <div class="kpi-v" style="font-size:16px;margin-top:10px">Design Target</div>
                <div class="kpi-hint">Requires Agency ATO</div>
              </div>
            </div>
            """,
            sanitize=False,
        )

        with ui.element("div").classes("grid-2"):
            with panel("Control Status", glow=True):
                rows = [
                    (
                        "Role-Based Access Control (RBAC)",
                        "Active",
                        "active",
                        "Permissions Map Roles To Sensitive Actions (Payroll, Roster, Approvals).",
                    ),
                    (
                        "Session Binding",
                        session_secret,
                        "active" if secret_set else "target",
                        "Multi-User Browser Sessions Use Signed Storage. Set SCHEDULER_STORAGE_SECRET In Production.",
                    ),
                    (
                        "Application Audit Trail",
                        "Available",
                        "active",
                        "Schedule, Auth, And Admin Actions Can Be Written To Audit_Log. Append-Only In App Logic; DB Admins Can Still Alter Rows.",
                    ),
                    (
                        "Encryption In Transit (TLS)",
                        "Deploy Target",
                        "target",
                        "Use HTTPS Reverse Proxy (IIS, Nginx, Caddy, Cloud LB) For Online Access. Local Dev May Use HTTP.",
                    ),
                    (
                        "Encryption At Rest / FIPS 140-2",
                        "Not Configured",
                        "off",
                        "Not Validated. Production Should Use OS BitLocker / Volume Encryption Or Cloud KMS With FIPS Modules.",
                    ),
                    (
                        "CJIS Compliance",
                        "Design Target — Not Certified",
                        "target",
                        "Policy, Personnel, Network, Media, And Incident Controls Are Outside This Application Alone.",
                    ),
                    (
                        "Background Screening / Training",
                        "Agency Responsibility",
                        "off",
                        "CJIS Requires Agency Processes For Personnel With Access To Criminal Justice Information.",
                    ),
                ]
                for title, status, state, detail in rows:
                    with ui.element("div").classes("data-row"):
                        with ui.element("div").classes("w-full"):
                            with ui.row().classes("items-center justify-between w-full gap-2"):
                                ui.label(title).classes("text-sm font-semibold")
                                ui.html(_status_chip(status, state), sanitize=False)
                            ui.label(detail).classes("text-xs q-mt-xs").style("color: var(--dim)")

            with panel("Your Access Profile"):
                user = session.current_user() or {}
                role = str(user.get("role") or "—")
                uname = str(user.get("username") or "—")
                ui.html(
                    f"""
                    <div style="margin-bottom:12px">
                      <div class="kpi-l">Signed In As</div>
                      <div style="font-size:16px;font-weight:700;margin-top:4px">{uname}</div>
                      <div class="kpi-hint">Role · {role}</div>
                    </div>
                    """,
                    sanitize=False,
                )
                ui.label("Sensitive Capabilities For This Role").classes("text-sm font-semibold q-mb-sm")
                granted = 0
                for label, perm in SENSITIVE_PERMS:
                    ok = role_has_permission(role, perm)
                    if ok:
                        granted += 1
                    chip = _status_chip("Allowed", "active") if ok else _status_chip("Denied", "off")
                    with ui.element("div").classes("data-row"):
                        ui.label(label).classes("text-sm")
                        ui.html(chip, sanitize=False)
                ui.label(f"{granted} Of {len(SENSITIVE_PERMS)} Listed Sensitive Capabilities Allowed").classes(
                    "text-xs q-mt-sm"
                ).style("color: var(--dim)")

                ui.separator().classes("q-my-md")
                ui.label("Defined Application Roles").classes("text-sm font-semibold q-mb-sm")
                for r in USER_ROLES:
                    n = sum(1 for p, roles in PERMISSIONS.items() if r in roles)
                    with ui.element("div").classes("data-row"):
                        ui.label(r).classes("text-sm font-semibold")
                        ui.label(f"{n} Permission Keys").classes("text-xs").style("color: var(--dim)")

        # —— Audit trail ——
        with panel("Operational Audit Trail", glow=False):
            if not session.can("audit.view"):
                ui.html(
                    '<div class="alert alert-warn">'
                    "Audit Log Viewer Requires The Audit.View Permission "
                    "(Supervisor Or Administration)."
                    "</div>",
                    sanitize=False,
                )
            else:
                ui.label("Recent Application Events · Newest First · For Accountability Reviews").classes(
                    "text-xs q-mb-sm"
                ).style("color: var(--dim)")
                filt = (
                    ui.input(placeholder="Filter Action (Optional)…")
                    .classes("w-full q-mb-sm")
                    .props("outlined dense dark")
                )
                host = ui.element("div")

                def refresh():
                    host.clear()
                    q = (filt.value or "").strip() or None
                    try:
                        rows = get_audit_log(40, action_filter=q)
                    except Exception as exc:
                        with host:
                            ui.html(
                                f'<div class="alert alert-crit">Unable To Load Audit Log: {exc}</div>',
                                sanitize=False,
                            )
                        return
                    with host:
                        if not rows:
                            ui.html(
                                '<div class="alert alert-ok">No Audit Entries Match This Filter.</div>',
                                sanitize=False,
                            )
                            return
                        for row in rows:
                            action = row.get("action") or "—"
                            entity = row.get("entity_type") or ""
                            eid = row.get("entity_id")
                            user_n = row.get("username") or f"User {row.get('user_id') or '—'}"
                            when = format_datetime(row.get("created_at") or "")
                            details = (row.get("details") or "")[:120]
                            with ui.element("div").classes("data-row"):
                                with ui.element("div").classes("w-full"):
                                    ui.label(f"{action}").classes("text-sm font-semibold")
                                    meta = f"{when} · {user_n}" if when else user_n
                                    if entity:
                                        meta += f" · {entity}"
                                        if eid is not None:
                                            meta += f" #{eid}"
                                    ui.label(meta).classes("text-xs").style("color: var(--dim)")
                                    if details:
                                        ui.label(str(details)).classes("text-xs q-mt-xs").style("color: var(--muted)")

                ui.button("Refresh Audit Log", on_click=refresh).classes("btn-ghost q-mb-sm").props(
                    "no-caps outline dense"
                )
                filt.on("keydown.enter", lambda: refresh())
                refresh()

        # Notify channels: in-app always; email SMTP optional; SMS via Twilio when SID/token set
        if session.can("settings.manage") or session.can("notifications.manage") or session.can("admin.settings"):
            with panel("Notification Channels", glow=True):
                ui.label(
                    "In-app always on. Email when SMTP host set. SMS sends via Twilio when SID + token + from set "
                    "(or TWILIO_* env vars)."
                ).classes("text-xs text-gray-500 q-mb-sm")
                try:
                    from logic.operations import get_department_setting

                    def _on(key: str) -> bool:
                        return get_department_setting(key, "0").strip().lower() in (
                            "1",
                            "true",
                            "yes",
                            "on",
                        )

                    email_on = _on("notify_email_enabled")
                    sms_on = _on("notify_sms_enabled")
                    email_from = get_department_setting("notify_email_from", "") or ""
                    sms_from = get_department_setting("notify_sms_from", "") or ""
                    smtp_host = get_department_setting("notify_smtp_host", "") or ""
                    smtp_port = get_department_setting("notify_smtp_port", "587") or "587"
                    smtp_user = get_department_setting("notify_smtp_user", "") or ""
                    raw_tls = (get_department_setting("notify_smtp_tls", "1") or "1").strip()
                    smtp_tls = raw_tls.lower() not in ("0", "false", "no", "off")
                    twilio_sid = get_department_setting("notify_twilio_account_sid", "") or ""
                except Exception:
                    email_on = sms_on = False
                    email_from = sms_from = smtp_host = smtp_port = smtp_user = ""
                    smtp_tls = True
                    twilio_sid = ""
                en_email = ui.checkbox("Enable Email (Schedule · Open Shifts)", value=email_on)
                en_sms = ui.checkbox("Enable SMS (Vacancies · Callbacks)", value=sms_on)
                from_email = ui.input(label="From Email", value=email_from).classes("w-full")
                from_sms = ui.input(label="SMS From (E.164, e.g. +16085551212)", value=sms_from).classes("w-full")
                smtp_h = ui.input(label="SMTP Host (Optional)", value=smtp_host).classes("w-full")
                smtp_p = ui.input(label="SMTP Port", value=smtp_port).classes("w-full")
                smtp_u = ui.input(label="SMTP User", value=smtp_user).classes("w-full")
                smtp_pw = ui.input(label="SMTP Password", value="", password=True, password_toggle_button=True).classes(
                    "w-full"
                )
                en_tls = ui.checkbox("SMTP STARTTLS", value=smtp_tls)
                tw_sid = ui.input(label="Twilio Account SID", value=twilio_sid).classes("w-full")
                tw_tok = ui.input(
                    label="Twilio Auth Token (leave blank to keep)",
                    value="",
                    password=True,
                    password_toggle_button=True,
                ).classes("w-full")

                def save_notify():
                    try:
                        from logic.operations import set_department_setting

                        uid = (session.current_user() or {}).get("id")
                        set_department_setting("notify_email_enabled", "1" if en_email.value else "0", user_id=uid)
                        set_department_setting("notify_sms_enabled", "1" if en_sms.value else "0", user_id=uid)
                        set_department_setting("notify_email_from", (from_email.value or "").strip(), user_id=uid)
                        set_department_setting("notify_sms_from", (from_sms.value or "").strip(), user_id=uid)
                        set_department_setting("notify_smtp_host", (smtp_h.value or "").strip(), user_id=uid)
                        set_department_setting(
                            "notify_smtp_port", (smtp_p.value or "587").strip() or "587", user_id=uid
                        )
                        set_department_setting("notify_smtp_user", (smtp_u.value or "").strip(), user_id=uid)
                        pw = (smtp_pw.value or "").strip()
                        if pw:
                            set_department_setting("notify_smtp_password", pw, user_id=uid)
                        set_department_setting("notify_smtp_tls", "1" if en_tls.value else "0", user_id=uid)
                        set_department_setting("notify_twilio_account_sid", (tw_sid.value or "").strip(), user_id=uid)
                        tok = (tw_tok.value or "").strip()
                        if tok:
                            set_department_setting("notify_twilio_auth_token", tok, user_id=uid)
                        ui.notify("Channel settings saved", type="positive")
                    except Exception as exc:
                        ui.notify(f"Save failed: {exc}", type="negative")

                ui.button("Save Channel Settings", on_click=save_notify).classes("btn-primary q-mt-sm").props(
                    "no-caps unelevated dense"
                )

        # —— Multi-factor authentication (self-service) ——
        with panel("Multi-Factor Authentication (Authenticator App)", glow=True):
            from logic.mfa_auth import (
                begin_mfa_enrollment,
                confirm_mfa_enrollment,
                disable_mfa,
                mfa_available,
                mfa_status,
            )

            user = session.current_user() or {}
            uid = user.get("id")
            if not uid:
                ui.label("Sign in to manage MFA.").classes("text-xs").style("color: var(--dim)")
            elif not mfa_available():
                ui.html(
                    '<div class="alert alert-warn">pyotp is not installed — MFA unavailable on this host.</div>',
                    sanitize=False,
                )
            else:
                status = mfa_status(uid)
                enrollment = {"secret": None}
                status_label = ui.label("").classes("text-sm q-mb-sm")
                qr_area = ui.element("div")
                code_input = (
                    ui.input(label="Enter code from authenticator app", placeholder="6-digit code")
                    .classes("w-full")
                    .props("outlined dense maxlength=6")
                )
                code_input.set_visibility(False)

                def refresh_mfa_status():
                    s = mfa_status(uid)
                    status_label.set_text("MFA: Enabled" if s.get("mfa_enabled") else "MFA: Not Enabled")

                def start_enroll():
                    result = begin_mfa_enrollment(uid)
                    if not result.get("success"):
                        ui.notify(result.get("message", "Enrollment failed"), type="negative")
                        return
                    enrollment["secret"] = result["secret"]
                    qr_area.clear()
                    with qr_area:
                        ui.label(f"Secret (enter manually if not scanning): {result['secret']}").classes(
                            "text-xs mono q-mb-xs"
                        ).style("color: var(--muted)")
                        ui.label(
                            "Add this account in Google Authenticator / Authy / 1Password, then enter the "
                            "6-digit code below to activate."
                        ).classes("text-xs").style("color: var(--dim)")
                    code_input.set_visibility(True)
                    ui.notify("Scan/enter the secret, then confirm with a code", type="info")

                def confirm_enroll():
                    result = confirm_mfa_enrollment(uid, (code_input.value or "").strip())
                    ui.notify(
                        result.get("message", "Confirm"), type="positive" if result.get("success") else "negative"
                    )
                    if result.get("success"):
                        code_input.set_visibility(False)
                        qr_area.clear()
                        refresh_mfa_status()

                def turn_off():
                    result = disable_mfa(uid, actor_user_id=uid)
                    ui.notify(
                        result.get("message", "Disable"), type="positive" if result.get("success") else "negative"
                    )
                    refresh_mfa_status()

                refresh_mfa_status()
                with ui.row().classes("gap-2 flex-wrap q-mt-sm"):
                    if not status.get("mfa_enabled"):
                        ui.button("Start enrollment", on_click=start_enroll).classes("btn-primary").props(
                            "no-caps unelevated dense"
                        )
                        ui.button("Confirm code", on_click=confirm_enroll).classes("btn-ghost").props(
                            "no-caps outline dense"
                        )
                    else:
                        ui.button("Turn off MFA", on_click=turn_off).classes("btn-danger").props(
                            "no-caps outline dense"
                        )

        # OIDC / SSO field trial — not production-validated
        if session.can("security.manage_sso") or session.can("settings.manage") or session.can("admin.settings"):
            with panel("OIDC / SSO field trial", glow=True):
                from logic.oidc_auth import (
                    get_oidc_field_trial_config,
                    oidc_field_trial_checklist,
                    oidc_health_check,
                    save_oidc_field_trial_settings,
                )

                cfg = get_oidc_field_trial_config()
                check = oidc_field_trial_checklist()
                ui.label(
                    "Optional OpenID Connect SSO. Links to existing Chronos accounts by username claim — "
                    "does not auto-provision users. Production-ready stays false until IT sign-off."
                ).classes("text-xs q-mb-sm").style("color: var(--dim)")
                ui.label(check.get("message") or "").classes("text-xs q-mb-sm").style("color: var(--muted)")
                for c in (check.get("checks") or [])[:10]:
                    mark = "OK" if c.get("ok") else "—"
                    ui.label(f"{mark} · {c.get('name')}: {c.get('detail')}").classes("text-xs")
                oidc_en = ui.switch("Enable OIDC auth", value=bool(cfg.get("enabled")))
                oidc_issuer = ui.input("Issuer URL", value=cfg.get("issuer") or "https://idp.example.com/").classes(
                    "w-full"
                )
                oidc_client_id = ui.input("Client ID", value=cfg.get("client_id") or "").classes("w-full")
                oidc_client_secret = ui.input("Client secret (leave blank to keep)", value="", password=True).classes(
                    "w-full"
                )
                oidc_redirect = ui.input("Redirect URI", value=cfg.get("redirect_uri") or "").classes("w-full")
                oidc_claim = ui.input(
                    "Username claim", value=cfg.get("username_claim") or "preferred_username"
                ).classes("w-full")
                if cfg.get("production_signoff"):
                    ui.label(f"IT sign-off on file · {cfg.get('signoff_by')} · {cfg.get('signoff_at')}").classes(
                        "text-xs text-green-400 q-mb-xs"
                    )

                def save_oidc():
                    uid = (session.current_user() or {}).get("id")
                    payload = {
                        "enabled": bool(oidc_en.value),
                        "issuer": oidc_issuer.value or "",
                        "client_id": oidc_client_id.value or "",
                        "redirect_uri": oidc_redirect.value or "",
                        "username_claim": oidc_claim.value or "",
                    }
                    if (oidc_client_secret.value or "").strip():
                        payload["client_secret"] = oidc_client_secret.value.strip()
                    r = save_oidc_field_trial_settings(payload, user_id=uid)
                    ui.notify(r.get("message", "Saved"), type="positive" if r.get("success") else "negative")

                def run_oidc_health():
                    h = oidc_health_check()
                    ui.notify(h.get("message", "Health"), type="positive" if h.get("success") else "warning")

                def run_oidc_checklist():
                    c = oidc_field_trial_checklist()
                    ui.notify(c.get("message", "Checklist"), type="info", multi_line=True)

                def record_oidc_signoff():
                    uid = (session.current_user() or {}).get("id")
                    name = session.display_name() or str(uid or "admin")
                    r = save_oidc_field_trial_settings(
                        {
                            "production_signoff": True,
                            "signoff_by": name,
                            "enabled": bool(oidc_en.value),
                            "issuer": oidc_issuer.value or "",
                            "client_id": oidc_client_id.value or "",
                            "redirect_uri": oidc_redirect.value or "",
                        },
                        user_id=uid,
                    )
                    c = oidc_field_trial_checklist()
                    ui.notify(
                        r.get("message", "Sign-off saved") + f" · production_ready={c.get('production_ready')}",
                        type="positive" if r.get("success") else "negative",
                        multi_line=True,
                    )

                def clear_oidc_signoff():
                    uid = (session.current_user() or {}).get("id")
                    r = save_oidc_field_trial_settings({"clear_production_signoff": True}, user_id=uid)
                    ui.notify(r.get("message", "Sign-off cleared"), type="info")

                with ui.row().classes("gap-2 flex-wrap q-mt-sm"):
                    ui.button("Save OIDC trial settings", on_click=save_oidc).classes("btn-primary").props(
                        "no-caps unelevated dense"
                    )
                    ui.button("Health check", on_click=run_oidc_health).classes("btn-ghost").props(
                        "no-caps outline dense"
                    )
                    ui.button("Refresh checklist", on_click=run_oidc_checklist).classes("btn-ghost").props(
                        "no-caps outline dense"
                    )
                    ui.button("Record IT production sign-off", on_click=record_oidc_signoff).classes("btn-ghost").props(
                        "no-caps outline dense"
                    )
                    ui.button("Clear sign-off", on_click=clear_oidc_signoff).classes("btn-danger").props(
                        "no-caps outline dense"
                    )

        # LDAP field trial (residual #5) — not production-validated
        if session.can("settings.manage") or session.can("users.manage") or session.can("admin.settings"):
            with panel("LDAP / AD field trial", glow=True):
                from logic.ldap_auth import (
                    export_ldap_field_trial_report,
                    get_ldap_field_trial_config,
                    ldap_field_trial_checklist,
                    ldap_health_check,
                    save_ldap_field_trial_settings,
                )

                cfg = get_ldap_field_trial_config()
                check = ldap_field_trial_checklist()
                ui.label(
                    "Optional Active Directory bind. Production-ready stays false until department IT sign-off. "
                    "Sandbox falls back to local password if LDAP host is down (lab only)."
                ).classes("text-xs q-mb-sm").style("color: var(--dim)")
                ui.label(check.get("message") or "").classes("text-xs q-mb-sm").style("color: var(--muted)")
                for c in (check.get("checks") or [])[:10]:
                    mark = "OK" if c.get("ok") else "—"
                    ui.label(f"{mark} · {c.get('name')}: {c.get('detail')}").classes("text-xs")
                en = ui.switch("Enable LDAP auth", value=bool(cfg.get("enabled")))
                sand = ui.switch("Sandbox fallback (lab only)", value=bool(cfg.get("sandbox")))
                use_ssl = ui.switch("Use SSL / LDAPS", value=bool(cfg.get("use_ssl")))
                server = ui.input("LDAP server", value=cfg.get("server") or "ldap://dc.example.com").classes("w-full")
                base = ui.input("Base DN", value=cfg.get("base_dn") or "").classes("w-full")
                bind = ui.input("Bind DN (optional)", value=cfg.get("bind_dn") or "").classes("w-full")
                bind_pw = ui.input("Bind password (leave blank to keep)", value="", password=True).classes("w-full")
                filt = ui.input(
                    "User filter",
                    value=cfg.get("user_filter") or "(sAMAccountName={username})",
                ).classes("w-full")
                if cfg.get("production_signoff"):
                    ui.label(f"IT sign-off on file · {cfg.get('signoff_by')} · {cfg.get('signoff_at')}").classes(
                        "text-xs text-green-400 q-mb-xs"
                    )

                def save_ldap():
                    uid = (session.current_user() or {}).get("id")
                    payload = {
                        "enabled": bool(en.value),
                        "sandbox": bool(sand.value),
                        "use_ssl": bool(use_ssl.value),
                        "server": server.value or "",
                        "base_dn": base.value or "",
                        "bind_dn": bind.value or "",
                        "user_filter": filt.value or "",
                    }
                    if (bind_pw.value or "").strip():
                        payload["bind_password"] = bind_pw.value.strip()
                    r = save_ldap_field_trial_settings(payload, user_id=uid)
                    ui.notify(r.get("message", "Saved"), type="positive" if r.get("success") else "negative")

                def run_health():
                    h = ldap_health_check()
                    ui.notify(h.get("message", "Health"), type="positive" if h.get("success") else "warning")

                def run_checklist():
                    c = ldap_field_trial_checklist()
                    ui.notify(c.get("message", "Checklist"), type="info", multi_line=True)

                def record_signoff():
                    uid = (session.current_user() or {}).get("id")
                    name = session.display_name() or str(uid or "admin")
                    if sand.value:
                        ui.notify("Turn off sandbox before production sign-off", type="warning")
                        return
                    r = save_ldap_field_trial_settings(
                        {
                            "production_signoff": True,
                            "signoff_by": name,
                            "enabled": bool(en.value),
                            "sandbox": False,
                            "use_ssl": bool(use_ssl.value),
                            "server": server.value or "",
                            "base_dn": base.value or "",
                        },
                        user_id=uid,
                    )
                    c = ldap_field_trial_checklist()
                    ui.notify(
                        r.get("message", "Sign-off saved") + f" · production_ready={c.get('production_ready')}",
                        type="positive" if r.get("success") else "negative",
                        multi_line=True,
                    )

                def clear_signoff():
                    uid = (session.current_user() or {}).get("id")
                    r = save_ldap_field_trial_settings({"clear_production_signoff": True}, user_id=uid)
                    ui.notify(r.get("message", "Sign-off cleared"), type="info")

                def export_trial_packet():
                    uid = (session.current_user() or {}).get("id")
                    r = export_ldap_field_trial_report(user_id=uid)
                    ui.notify(
                        r.get("message") or r.get("md_path") or "Exported",
                        type="positive" if r.get("success") else "negative",
                        multi_line=True,
                    )

                with ui.row().classes("gap-2 flex-wrap q-mt-sm"):
                    ui.button("Save LDAP trial settings", on_click=save_ldap).classes("btn-primary").props(
                        "no-caps unelevated dense"
                    )
                    ui.button("Health check", on_click=run_health).classes("btn-ghost").props("no-caps outline dense")
                    ui.button("Refresh checklist", on_click=run_checklist).classes("btn-ghost").props(
                        "no-caps outline dense"
                    )
                    ui.button("Export IT field-trial report", on_click=export_trial_packet).classes("btn-ghost").props(
                        "no-caps outline dense"
                    )
                    ui.button("Record IT production sign-off", on_click=record_signoff).classes("btn-ghost").props(
                        "no-caps outline dense"
                    )
                    ui.button("Clear sign-off", on_click=clear_signoff).classes("btn-danger").props(
                        "no-caps outline dense"
                    )

        with panel("Deployment Notes For Online Access"):
            ui.html(
                f"""
                <div class="data-row"><div class="w-full">
                  <div class="text-sm font-semibold">Product</div>
                  <div class="text-xs" style="color:var(--dim)">{APP_NAME} · v{APP_VERSION}</div>
                </div></div>
                <div class="data-row"><div class="w-full">
                  <div class="text-sm font-semibold">Online Mode</div>
                  <div class="text-xs" style="color:var(--dim)">
                    Run With --Web Behind HTTPS. Set SCHEDULER_STORAGE_SECRET. Restrict Network (VPN / Firewall).
                  </div>
                </div></div>
                <div class="data-row"><div class="w-full">
                  <div class="text-sm font-semibold">What This Application Does Not Claim</div>
                  <div class="text-xs" style="color:var(--dim)">
                    FBI CJIS Certification · FIPS 140-2 Module Validation · FedRAMP · SOC 2 Report
                  </div>
                </div></div>
                <div class="data-row"><div class="w-full">
                  <div class="text-sm font-semibold">Last Page Render</div>
                  <div class="text-xs" style="color:var(--dim)">{format_local_datetime()} ({timezone_label()})</div>
                </div></div>
                """,
                sanitize=False,
            )
            with ui.row().classes("gap-2 q-mt-sm"):
                if session.can("users.manage") or session.can("users.edit_role"):
                    ui.button(
                        "Open Access Control",
                        on_click=lambda: ui.navigate.to("/access"),
                    ).classes("btn-ghost").props("no-caps outline dense")
                ui.button(
                    "Return To Duty Board",
                    on_click=lambda: ui.navigate.to("/"),
                ).classes("btn-primary").props("no-caps unelevated dense")

    layout("security", body)
