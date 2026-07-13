"""App chrome — Chronos Command shell, status bar, nav."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from config import APP_NAME, APP_VERSION
from gui import session
from gui.clock import format_clock, format_local_date, timezone_label, today_local
from gui.theme import GLOBAL_CSS
from logic import get_cycle_day, get_squad_on_duty, rust_bridge

NAV = [
    ("section", "Overview"),
    ("/", "Duty Board", "dashboard", "◈"),
    ("/notifications", "Alerts", "notifications", "✦"),
    ("section", "Scheduling"),
    ("/my-schedule", "My Schedule", "my_schedule", "▣"),
    ("/monthly-schedule", "Monthly Schedule", "monthly", "▦"),
    ("/live-schedule", "Live Schedule", "live", "◈"),
    ("/time-off", "Time Off Requests", "time_off", "⇄"),
    ("/open-shifts", "Open Shifts", "open_shifts", "＋"),
    ("/bidding", "Shift Bidding", "bidding", "⇅"),
    ("/callbacks", "Callback Rotation", "callbacks", "↻"),
    ("/availability", "Availability", "availability", "◌"),
    ("section", "Personnel"),
    ("/roster", "Patrol Roster", "roster", "◉"),
    ("/certs", "Certifications", "certs", "✓"),
    ("section", "Finance"),
    ("/timecards", "Timecards", "timecards", "◷"),
    ("/payroll", "Payroll", "payroll", "$"),
    ("section", "Command"),
    ("/simulator", "Schedule Simulator", "simulator", "▶"),
    ("/operations", "Ops Reports", "operations", "☰"),
    ("/media", "Department Media", "media", "▣"),
    ("/security", "Security & Governance", "security", "⬡"),
    ("/access", "Access Control", "access", "⚙"),
]

ROUTE_PERMS: dict[str, str | tuple[str, ...]] = {
    "/simulator": "simulator.use",
    "/roster": "officers.manage",
    "/media": ("officers.manage", "admin.settings", "settings.manage"),
    "/operations": "reports.view",
    "/callbacks": ("reports.view", "open_shifts.manage", "schedule.updated.edit"),
    "/access": ("users.manage", "users.edit_role"),
}

ALIASES = {
    "/schedules": "/live-schedule",
    "/timeline": "/my-schedule",
    "/leave": "/time-off",
    "/finance": "/timecards",
}


def apply_theme() -> None:
    """Inject Chronos styles on every page via static CSS (keep payload small).

    Do NOT inline GLOBAL_CSS or base64 images here — large payloads break NiceGUI
    WebSocket ("Message too long" / blank UI).
    """
    ui.dark_mode().enable()
    ui.colors(
        primary="#22d3ee",
        secondary="#8b5cf6",
        accent="#22d3ee",
        dark="#05060b",
        positive="#22c55e",
        negative="#ef4444",
        info="#22d3ee",
        warning="#f59e0b",
    )
    # Ensure CSS file is current, then link only
    try:
        from pathlib import Path

        css_path = Path(__file__).resolve().parent / "static" / "chronos.css"
        css_path.parent.mkdir(parents=True, exist_ok=True)
        if not css_path.is_file() or css_path.stat().st_size < 1000:
            css_path.write_text(GLOBAL_CSS, encoding="utf-8")
        ver = int(css_path.stat().st_mtime)
    except Exception:
        ver = 1
    ui.add_head_html(
        f'<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />'
        f'<meta name="theme-color" content="#05060b" />'
        f'<meta name="apple-mobile-web-app-capable" content="yes" />'
        f'<link rel="stylesheet" href="/static/chronos.css?v={ver}" />',
        shared=False,
    )


def _nav_visible(path: str) -> bool:
    perm = ROUTE_PERMS.get(path)
    if not perm:
        return True
    if isinstance(perm, tuple):
        return any(session.can(p) for p in perm)
    return session.can(perm)


def page_header(title: str, subtitle: str = "", kicker: str = "Chronos Command") -> None:
    with ui.element("div").classes("top-bar"):
        with ui.element("div"):
            ui.html(f'<div class="page-kicker">{kicker}</div>', sanitize=False)
            ui.html(f'<h1 class="page-title">{title}</h1>', sanitize=False)
            if subtitle:
                ui.html(f'<p class="page-sub">{subtitle}</p>', sanitize=False)
        with ui.element("div").classes("user-pill"):
            ui.html(f'<div class="user-av">{session.initials()}</div>', sanitize=False)
            with ui.element("div"):
                ui.label(session.display_name()).classes("text-sm font-semibold")
                role = (session.current_user() or {}).get("role") or ""
                ui.label(str(role)).classes("text-xs").style("color: var(--dim)")


def panel(title: str = "", *, glow: bool = False):
    cls = "panel panel-glow w-full" if glow else "panel w-full"
    el = ui.element("div").classes(cls)
    with el:
        if title:
            ui.html(f'<div class="panel-title">{title}</div>', sanitize=False)
    return el


def scheduling_subnav(active: str) -> None:
    tabs = [
        ("/my-schedule", "My Schedule", "my_schedule"),
        ("/monthly-schedule", "Monthly Schedule", "monthly"),
        ("/live-schedule", "Live Schedule", "live"),
        ("/time-off", "Time Off Requests", "time_off"),
    ]
    with ui.row().classes("gap-2 q-mb-md flex-wrap"):
        for path, label, key in tabs:
            if key == active:
                ui.button(label, on_click=lambda _p=path: ui.navigate.to(_p)).classes("btn-primary").props(
                    "no-caps unelevated dense"
                )
            else:
                ui.button(label, on_click=lambda _p=path: ui.navigate.to(_p)).classes("btn-ghost").props(
                    "no-caps outline dense"
                )


def finance_subnav(active: str) -> None:
    tabs = [
        ("/timecards", "Timecards", "timecards"),
        ("/payroll", "Payroll", "payroll"),
    ]
    with ui.row().classes("gap-2 q-mb-md flex-wrap"):
        for path, label, key in tabs:
            if key == active:
                ui.button(label, on_click=lambda _p=path: ui.navigate.to(_p)).classes("btn-primary").props(
                    "no-caps unelevated dense"
                )
            else:
                ui.button(label, on_click=lambda _p=path: ui.navigate.to(_p)).classes("btn-ghost").props(
                    "no-caps outline dense"
                )


def _status_bar(engine: str) -> None:
    """Bottom product + compliance indicator strip + live local clock."""
    with ui.element("div").classes("status-bar"):
        ui.html(f'<span class="product">{APP_NAME}</span>', sanitize=False)
        ui.html('<span class="sep" style="width:1px;height:14px;background:var(--border)"></span>', sanitize=False)
        ui.html(
            '<span class="status-pill"><span class="glow-dot"></span>CJIS Compliant</span>',
            sanitize=False,
        )
        ui.html(
            '<span class="status-pill"><span class="glow-dot"></span>FIPS 140-2</span>',
            sanitize=False,
        )

        def _bar_text() -> str:
            # M/D/YY e.g. 7/9/26 — not day/month
            date_str = format_local_date()
            return (
                f'<span style="margin-left:auto;opacity:0.9">'
                f"{date_str} · {format_clock(seconds=True)} {timezone_label()} · "
                f"v{APP_VERSION} · {engine}</span>"
            )

        bar_clock = ui.html(_bar_text(), sanitize=False)

        def _tick_bar():
            try:
                bar_clock.set_content(_bar_text())
            except Exception:
                pass

        ui.timer(1.0, _tick_bar)


def _render_brand_mark() -> None:
    """Circular mark: department logo via NiceGUI local file route."""
    import os

    logo_path = None
    try:
        from gui.brand_assets import sync_brand_files
        from photos import department_logo_path

        sync_brand_files()
        logo_path = department_logo_path()
    except Exception:
        logo_path = None

    with ui.element("div").classes("dc-logo-mark"):
        if logo_path and os.path.isfile(logo_path):
            # Path-based ui.image is the most reliable NiceGUI media path
            ui.image(logo_path).style("width:100%;height:100%;object-fit:cover;border-radius:50%;display:block")
        else:
            ui.element("div").classes("dc-orb")


def layout(active: str, build: Callable[[], None]) -> None:
    apply_theme()
    user = session.current_user()
    if not user:
        ui.navigate.to("/login")
        return

    today = today_local()
    try:
        cycle = get_cycle_day(today)
        squad = get_squad_on_duty(cycle)
    except Exception:
        cycle, squad = "—", "—"
    try:
        engine = rust_bridge.backend_name()
    except Exception:
        engine = "python"
    tz_lbl = timezone_label()

    with ui.element("div").classes("dc-shell"):
        with ui.element("div").classes("dc-shell-body"):
            with ui.element("aside").classes("dc-sidebar"):
                with ui.element("div").classes("dc-brand"):
                    _render_brand_mark()
                    ui.html(f'<div class="dc-brand-name">{APP_NAME}</div>', sanitize=False)

                for item in NAV:
                    if item[0] == "section":
                        ui.html(f'<div class="nav-sec">{item[1]}</div>', sanitize=False)
                        continue
                    path, label, key, ico = item
                    if not _nav_visible(path):
                        continue
                    cls = "nav-link active" if active == key else "nav-link"
                    with ui.element("div").classes(cls).on("click", lambda _e, p=path: ui.navigate.to(p)):
                        ui.html(f'<span class="nav-ico">{ico}</span>', sanitize=False)
                        ui.label(label)

                with ui.element("div").classes("nav-foot"):
                    ui.label("Authorized Personnel Only")
                    ui.label(f"{APP_NAME} · v{APP_VERSION}")
                    ui.button("Sign Out", on_click=_sign_out).props("flat dense no-caps").classes(
                        "btn-ghost w-full q-mt-sm"
                    )

            with ui.element("div").classes("dc-main"):
                with ui.element("div").classes("cmd-strip"):
                    ui.html('<span class="live-badge">SYSTEM LIVE</span>', sanitize=False)
                    ui.html('<span class="sep"></span>', sanitize=False)
                    ui.html(f'<span class="cmd-title">{APP_NAME}</span>', sanitize=False)
                    ui.html('<span class="sep"></span>', sanitize=False)
                    clock_lbl = ui.html(
                        f"<span>Time <strong>{format_clock(seconds=True)}</strong> {tz_lbl}</span>",
                        sanitize=False,
                    )
                    ui.html('<span class="sep"></span>', sanitize=False)
                    ui.html(f"<span>Cycle Day <strong>{cycle}</strong></span>", sanitize=False)
                    ui.html('<span class="sep"></span>', sanitize=False)
                    ui.html(f"<span>Squad <strong>{squad}</strong> Active</span>", sanitize=False)
                    ui.html('<span class="sep"></span>', sanitize=False)
                    # M/D/YY e.g. 7/9/26 (July 9) — never 9/7/26
                    date_str = format_local_date(today)
                    ui.html(
                        f'<span>Date <strong class="date-mdy">{date_str}</strong></span>',
                        sanitize=False,
                    )

                    def _tick_clock():
                        try:
                            clock_lbl.set_content(
                                f"<span>Time <strong>{format_clock(seconds=True)}</strong> {timezone_label()}</span>"
                            )
                        except Exception:
                            pass

                    # Live local clock (department timezone)
                    ui.timer(1.0, _tick_clock)

                with ui.element("main").classes("dc-content"):
                    build()

        _status_bar(engine)
        _install_command_palette()


def _install_command_palette() -> None:
    """Ctrl+K jump — Linear/ops-console pattern (ui-domain brainstorm)."""
    destinations = []
    for item in NAV:
        if item[0] == "section":
            continue
        path, label, _key, _ico = item
        if _nav_visible(path):
            destinations.append((label, path))
    # Extra power jumps
    for label, path in (
        ("Open Shifts board", "/open-shifts"),
        ("Shift Bidding", "/bidding"),
        ("Callback rotation", "/callbacks"),
        ("Availability / blackouts", "/availability"),
        ("Alerts inbox", "/notifications"),
        ("Certifications", "/certs"),
        ("Ops Reports", "/operations"),
    ):
        if path not in {p for _, p in destinations} and _nav_visible(path):
            destinations.append((label, path))

    with ui.dialog() as dlg, ui.card().classes("w-full").style("min-width:min(420px,92vw);max-width:520px"):
        ui.label("Jump to…").classes("text-sm font-semibold q-mb-sm")
        ui.label("Ctrl+K · type to filter").classes("text-xs text-gray-500 q-mb-sm")
        search = ui.input(placeholder="Page name…").classes("w-full").props("autofocus dense outlined dark")
        list_host = ui.element("div").classes("q-mt-sm")

        def render_list(q: str = ""):
            list_host.clear()
            qq = (q or "").strip().lower()
            with list_host:
                shown = 0
                for label, path in destinations:
                    if qq and qq not in label.lower() and qq not in path.lower():
                        continue
                    shown += 1
                    ui.button(
                        f"{label}  ·  {path}",
                        on_click=lambda _e=None, p=path: (dlg.close(), ui.navigate.to(p)),
                    ).classes("btn-ghost w-full q-mb-xs").props("no-caps outline dense align=left")
                if not shown:
                    ui.label("No matches").classes("text-xs text-gray-500")

        def _on_search(_=None):
            render_list(search.value or "")

        try:
            search.on_value_change(_on_search)
        except Exception:
            search.on("update:model-value", lambda: _on_search())
        render_list()
        ui.button("Close", on_click=dlg.close).classes("btn-ghost q-mt-sm").props("no-caps flat dense")

    def open_palette():
        try:
            search.value = ""
        except Exception:
            pass
        render_list("")
        dlg.open()

    try:
        ui.keyboard(
            on_key=lambda e: (
                open_palette()
                if getattr(e, "key", None) == "k"
                and (
                    getattr(getattr(e, "modifiers", None), "ctrl", False)
                    or getattr(getattr(e, "modifiers", None), "meta", False)
                )
                and getattr(getattr(e, "action", None), "keydown", True)
                else None
            )
        )
    except Exception:
        pass
    try:
        with ui.page_sticky(position="bottom-right", x_offset=18, y_offset=48):
            ui.button("⌘K", on_click=open_palette).props("fab-mini outline color=cyan dense").tooltip(
                "Jump to page (Ctrl+K)"
            )
    except Exception:
        ui.button("Jump ⌘K", on_click=open_palette).classes("btn-ghost").props("dense no-caps outline")


def _sign_out() -> None:
    user = session.current_user()
    if user:
        try:
            from logic import log_audit_action

            log_audit_action(
                "user.logout",
                "app_user",
                user.get("id"),
                user.get("id"),
                details="chronos_command",
            )
        except Exception:
            pass
    session.set_user(None)
    ui.navigate.to("/login")
