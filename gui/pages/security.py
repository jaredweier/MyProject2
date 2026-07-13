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
