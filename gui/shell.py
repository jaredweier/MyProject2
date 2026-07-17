"""App chrome — Chronos Command shell, status bar, nav."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from config import APP_NAME, APP_VERSION, COMPANY_NAME
from gui import session
from gui.clock import format_clock, format_local_date, timezone_label, today_local
from gui.theme import GLOBAL_CSS
from logic import get_cycle_day, get_squad_on_duty, rust_bridge

NAV = [
    ("section", "Overview"),
    # UAT Lab injected in layout when SCHEDULER_UAT_LAB=1 (see _nav_items)
    ("/", "Duty Board", "dashboard", "◈"),
    ("/my-week", "My Week", "my_week", "▣"),
    ("/notifications", "Alerts", "notifications", "✦"),
    ("section", "Scheduling"),
    ("/my-schedule", "My Schedule", "my_schedule", "▣"),
    ("/monthly-schedule", "Monthly Schedule", "monthly", "▦"),
    ("/live-schedule", "Live Schedule", "live", "◈"),
    ("/time-off", "Time Off Requests", "time_off", "⇄"),
    ("/open-shifts", "Open Shifts", "open_shifts", "＋"),
    ("/bidding", "Shift Bidding", "bidding", "⇅"),
    ("/callbacks", "Callback Rotation", "callbacks", "↻"),
    ("/court", "Court & Training", "court", "⚖"),
    ("/availability", "Availability", "availability", "◌"),
    ("section", "Personnel"),
    ("/roster", "Patrol Roster", "roster", "◉"),
    ("/certs", "Certifications", "certs", "✓"),
    ("section", "Finance"),
    ("/timecards", "Timecards", "timecards", "◷"),
    ("/time-punch", "Time Punch", "time_punch", "◉"),
    ("/banks", "Time Banks", "banks", "▣"),
    ("/payroll", "Payroll", "payroll", "$"),
    ("section", "Command"),
    ("/ops-desk", "Ops Desk", "ops_desk", "⚡"),
    ("/simulator", "Schedule Simulator", "simulator", "▶"),
    ("/operations", "Ops Reports", "operations", "☰"),
    ("/exports", "Exports Hub", "exports", "⇩"),
    ("/channels", "Notify Channels", "channels", "✉"),
    ("/audit", "Audit Trail", "audit", "☰"),
    ("/deploy", "Deploy & Implement", "deploy", "⇪"),
    ("/media", "Branding & Media", "media", "▣"),
    ("/security", "Security & Governance", "security", "⬡"),
    ("/access", "Access Control", "access", "⚙"),
]

ROUTE_PERMS: dict[str, str | tuple[str, ...]] = {
    "/simulator": "simulator.use",
    "/roster": "officers.manage",
    "/media": ("officers.manage", "admin.settings", "settings.manage"),
    "/operations": "reports.view",
    "/ops-desk": ("requests.approve", "reports.view", "schedule.updated.edit", "open_shifts.manage"),
    "/callbacks": ("reports.view", "open_shifts.manage", "schedule.updated.edit"),
    "/access": ("users.manage", "users.edit_role"),
    "/channels": ("admin.settings", "settings.manage", "notifications.manage", "users.manage"),
    "/audit": ("audit.view", "users.manage", "admin.settings", "reports.view"),
    "/deploy": ("admin.settings", "settings.manage", "users.manage", "reports.view"),
    "/exports": (
        "reports.export",
        "reports.view",
        "exports.run",
        "schedule.base.view",
        "payroll.view_all",
        "officers.manage",
    ),
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

    CTA system (locked): primary = command blue; silver = chrome accent (nav/selected).
    Fonts: Rajdhani + IBM Plex (CDN) with system fallbacks for offline.
    """
    ui.dark_mode().enable()
    # Quasar primary drives unelevated buttons + checkbox ticks.
    # Command blue primary — silver CTAs failed contrast on deep navy.
    ui.colors(
        primary="#3B7DD8",
        secondary="#1E5AA8",
        accent="#6BA3F5",
        dark="#060D18",
        positive="#2DD4A0",
        negative="#E85D5D",
        info="#5B8DEF",
        warning="#F0B429",
    )
    # Sync static CSS from GLOBAL_CSS only when content changes (avoids mtime thrash
    # that used to restart always-on UAT every health tick — see always_on_uat.ps1).
    try:
        from pathlib import Path

        css_path = Path(__file__).resolve().parent / "static" / "chronos.css"
        css_path.parent.mkdir(parents=True, exist_ok=True)
        existing = ""
        if css_path.is_file():
            try:
                existing = css_path.read_text(encoding="utf-8")
            except Exception:
                existing = ""
        if existing != GLOBAL_CSS:
            css_path.write_text(GLOBAL_CSS, encoding="utf-8")
        ver = int(css_path.stat().st_mtime)
    except Exception:
        ver = 1
    ui.add_head_html(
        f'<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />'
        f'<meta name="theme-color" content="#060D18" />'
        f'<meta name="apple-mobile-web-app-capable" content="yes" />'
        f'<meta name="mobile-web-app-capable" content="yes" />'
        f'<link rel="manifest" href="/static/manifest.webmanifest" />'
        f'<link rel="apple-touch-icon" href="/static/chronos_logo.png" />'
        f'<link rel="stylesheet" href="/static/fonts.css?v={ver}" />'
        f'<link rel="preconnect" href="https://fonts.googleapis.com" />'
        f'<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />'
        f'<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&family=Rajdhani:wght@600;700&display=swap" rel="stylesheet" media="print" onload="this.media=\'all\'" />'
        f'<link rel="stylesheet" href="/static/chronos.css?v={ver}" />'
        f'<script src="/static/offline-cache.js?v={ver}" defer></script>'
        f"<script>"
        f'if("serviceWorker" in navigator){{'
        f'navigator.serviceWorker.register("/static/sw.js").then(function(r){{'
        f"try{{r.update();}}catch(e){{}}"
        f"}}).catch(function(){{}});"
        f"}}"
        f"try{{"
        f'if(localStorage.getItem("chronos_rail_collapsed")==="1")'
        f'document.documentElement.classList.add("pre-rail-collapsed");'
        f"}}catch(e){{}}"
        f"</script>",
        shared=False,
    )


# Officer role: fewer top-level routes (self-service home). Supervisors/admins see full NAV.
OFFICER_NAV_PATHS = {
    "/",
    "/uat",
    "/my-week",
    "/notifications",
    "/my-schedule",
    "/monthly-schedule",
    "/live-schedule",
    "/time-off",
    "/open-shifts",
    "/bidding",
    "/court",
    "/availability",
    "/timecards",
    "/time-punch",
    "/banks",
    "/certs",
    "/exports",
}

# Mobile bottom bar (officer self-service — large tap targets)
OFFICER_MOBILE_NAV = [
    ("/my-week", "Week", "▣"),
    ("/time-punch", "Punch", "◉"),
    ("/open-shifts", "Open", "＋"),
    ("/time-off", "Leave", "⇄"),
    ("/banks", "Banks", "▣"),
    ("/timecards", "Time", "◷"),
]


def _nav_items():
    """NAV list; inject UAT Lab first when virtual lab mode is on."""
    items = list(NAV)
    try:
        from logic.uat_lab import uat_lab_enabled

        if uat_lab_enabled():
            items.insert(1, ("/uat", "UAT Lab", "uat", "⚑"))
    except Exception:
        pass
    return items


def _nav_visible(path: str) -> bool:
    if session.is_officer() and path not in OFFICER_NAV_PATHS:
        # Still allow if they have an elevated permission for that route
        perm = ROUTE_PERMS.get(path)
        if not perm:
            return False
        if isinstance(perm, tuple):
            if not any(session.can(p) for p in perm):
                return False
        elif not session.can(perm):
            return False
    perm = ROUTE_PERMS.get(path)
    if not perm:
        return True
    if isinstance(perm, tuple):
        return any(session.can(p) for p in perm)
    return session.can(perm)


def page_header(title: str, subtitle: str = "", kicker: str = "Chronos Command") -> None:
    with ui.element("div").classes("top-bar"):
        with ui.element("div"):
            # Brand kickers render as CHRONOS COMMAND (CSS uppercase); other kickers stay Title Case
            kicker_cls = "page-kicker product-brand" if "chronos" in (kicker or "").lower() else "page-kicker"
            ui.html(f'<div class="{kicker_cls}">{kicker}</div>', sanitize=False)
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
        ("/time-punch", "Time Punch", "time_punch"),
        ("/banks", "Time Banks", "banks"),
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
        ui.html(f'<span class="product product-brand">{APP_NAME}</span>', sanitize=False)
        ui.html('<span class="sep" style="width:1px;height:14px;background:var(--border)"></span>', sanitize=False)
        ui.html(
            f'<span class="status-pill" style="opacity:0.9">{COMPANY_NAME}</span>',
            sanitize=False,
        )
        ui.html('<span class="sep" style="width:1px;height:14px;background:var(--border)"></span>', sanitize=False)
        ui.html(
            '<span class="status-pill"><span class="glow-dot"></span>CJIS design targets</span>',
            sanitize=False,
        )

        def _bar_text() -> str:
            # M/D/YY e.g. 7/9/26
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

        # Detach from layout slot so page navigation cannot raise parent_slot deleted
        _bar_timer = ui.timer(1.0, _tick_bar)
        _bar_timer._parent_slot = None


def _render_brand_mark() -> None:
    """Circular mark: Chronos product logo (preferred), else CC monogram orb."""
    import os

    logo_path = None
    try:
        from gui.brand_assets import sync_brand_files
        from photos import chronos_logo_path

        sync_brand_files()
        logo_path = chronos_logo_path()
    except Exception:
        logo_path = None

    with ui.element("div").classes("dc-logo-mark"):
        if logo_path and os.path.isfile(logo_path):
            ui.image(logo_path).style(
                "width:100%;height:100%;object-fit:contain;border-radius:50%;display:block;"
                "background:rgba(6,13,24,0.9);padding:4px"
            )
        else:
            # Product monogram — not an agency seal
            with (
                ui.element("div")
                .classes("dc-orb")
                .style("display:grid;place-items:center;font-weight:800;font-size:14px;color:#E8EDF4")
            ):
                ui.label("CC").style("letter-spacing:0.04em")


# Admin paths folded under progressive disclosure (NN/g)
_ADMIN_MORE_PATHS = {
    "/channels",
    "/audit",
    "/deploy",
    "/media",
    "/security",
    "/access",
    "/simulator",
    "/operations",
    "/exports",
}

# Nav key → badge map key
_BADGE_BY_KEY = {
    "notifications": "notifications",
    "time_off": "time_off",
    "open_shifts": "open_shifts",
}


def _remember_nav(path: str) -> None:
    """Record recent navigation for command palette (client localStorage)."""
    try:
        ui.run_javascript(
            f"""
            try {{
              const p = {path!r};
              let r = JSON.parse(localStorage.getItem('chronos_recent_pages') || '[]');
              r = r.filter(x => x !== p);
              r.unshift(p);
              localStorage.setItem('chronos_recent_pages', JSON.stringify(r.slice(0, 8)));
            }} catch (e) {{}}
            """
        )
    except Exception:
        pass


def layout(active: str, build: Callable[[], None]) -> None:
    apply_theme()
    user = session.current_user()
    if not user:
        ui.navigate.to("/login")
        return

    # NiceGUI a11y + UX: skip link (keyboard / screen reader)
    try:
        from gui.ui_patterns import skip_to_main

        skip_to_main()
    except Exception:
        pass

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

    try:
        from gui.ui_patterns import collect_nav_badges, nav_badge

        badges = collect_nav_badges()
    except Exception:
        badges = {}
        nav_badge = lambda _n: ""  # noqa: E731

    shell_classes = "dc-shell"
    # Prefer expanded rail on first paint; JS restores collapse from localStorage
    with ui.element("div").classes(shell_classes):
        with ui.element("div").classes("dc-shell-body"):
            with ui.element("aside").classes("dc-sidebar"):
                with ui.element("div").classes("dc-brand"):
                    _render_brand_mark()
                    with ui.element("div").style("min-width:0;flex:1"):
                        ui.html(f'<div class="dc-brand-name">{APP_NAME}</div>', sanitize=False)
                        ui.html(
                            f'<div class="dc-brand-vendor">{COMPANY_NAME}</div>',
                            sanitize=False,
                        )
                        try:
                            import os as _os

                            from photos import department_logo_path as _dept_logo

                            _dl = _dept_logo()
                            if _dl and _os.path.isfile(_dl):
                                ui.image(_dl).style(
                                    "height:18px;width:auto;max-width:96px;object-fit:contain;"
                                    "margin-top:4px;opacity:0.85"
                                )
                        except Exception:
                            pass

                def _toggle_rail():
                    try:
                        ui.run_javascript(
                            """
                            const s = document.querySelector('.dc-shell');
                            if (!s) return;
                            s.classList.toggle('rail-collapsed');
                            try {
                              localStorage.setItem(
                                'chronos_rail_collapsed',
                                s.classList.contains('rail-collapsed') ? '1' : '0'
                              );
                            } catch (e) {}
                            """
                        )
                    except Exception:
                        pass

                ui.button("⟷ Rail", on_click=_toggle_rail).classes("btn-ghost rail-toggle").props(
                    "dense no-caps outline"
                ).tooltip("Collapse / expand nav (72px icons)")

                admin_more_items: list = []
                for item in _nav_items():
                    if item[0] == "section":
                        # Defer "Command" secondary under progressive disclosure for non-officers
                        if item[1] == "Command" and not session.is_officer():
                            ui.html('<div class="nav-sec">Command</div>', sanitize=False)
                            continue
                        ui.html(f'<div class="nav-sec">{item[1]}</div>', sanitize=False)
                        continue
                    path, label, key, ico = item
                    if not _nav_visible(path):
                        continue
                    if path in _ADMIN_MORE_PATHS and not session.is_officer():
                        # Keep ops-desk + callbacks top-level; fold the rest
                        if path not in ("/ops-desk", "/callbacks"):
                            admin_more_items.append(item)
                            continue
                    cls = "nav-link active" if active == key else "nav-link"
                    bkey = _BADGE_BY_KEY.get(key)
                    badge_html = nav_badge(badges.get(bkey, 0)) if bkey else ""

                    def _nav_click(_e=None, p=path):
                        _remember_nav(p)
                        ui.navigate.to(p)

                    with ui.element("div").classes(cls).on("click", _nav_click):
                        ui.html(f'<span class="nav-ico">{ico}</span>', sanitize=False)
                        ui.html(f'<span class="nav-link-label">{label}</span>', sanitize=False)
                        if badge_html:
                            ui.html(badge_html, sanitize=False)

                if admin_more_items and not session.is_officer():
                    with (
                        ui.expansion("More admin tools", icon="expand_more")
                        .classes("nav-admin-more w-full")
                        .props("dense dark")
                    ):
                        for path, label, key, ico in admin_more_items:
                            cls = "nav-link active" if active == key else "nav-link"

                            def _nav_more(_e=None, p=path):
                                _remember_nav(p)
                                ui.navigate.to(p)

                            with ui.element("div").classes(cls).on("click", _nav_more):
                                ui.html(f'<span class="nav-ico">{ico}</span>', sanitize=False)
                                ui.html(f'<span class="nav-link-label">{label}</span>', sanitize=False)

                with ui.element("div").classes("nav-foot"):
                    ui.label("Authorized personnel only")
                    ui.label(f"{APP_NAME} · v{APP_VERSION}")
                    ui.label(COMPANY_NAME).classes("text-xs").style("opacity:0.75;margin-top:2px")
                    ui.button("Sign out", on_click=_sign_out).props("flat dense no-caps").classes(
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
                    ui.html(f"<span>Cycle day <strong>{cycle}</strong></span>", sanitize=False)
                    ui.html('<span class="sep"></span>', sanitize=False)
                    ui.html(f"<span>Squad <strong>{squad}</strong> active</span>", sanitize=False)
                    ui.html('<span class="sep"></span>', sanitize=False)
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

                    _clk_timer = ui.timer(1.0, _tick_clock)
                    _clk_timer._parent_slot = None

                    def _toggle_dock():
                        try:
                            ui.run_javascript(
                                """
                                const s = document.querySelector('.dc-shell');
                                if (!s) return;
                                s.classList.toggle('dock-hidden');
                                try {
                                  localStorage.setItem(
                                    'chronos_dock_hidden',
                                    s.classList.contains('dock-hidden') ? '1' : '0'
                                  );
                                } catch (e) {}
                                """
                            )
                        except Exception:
                            pass

                    ui.button("Queue", on_click=_toggle_dock).classes("btn-ghost").props(
                        "dense no-caps outline"
                    ).tooltip("Toggle right dock (leave · alerts)")

                with ui.element("main").classes("dc-content").props('id="chronos-main" tabindex="-1"'):
                    build()

            # Right dock — leave queue, alerts, certs (DESIGN D)
            if not session.is_officer() or session.can("requests.approve"):
                _render_right_dock()
            else:
                # Officers: compact alerts dock
                _render_right_dock(officer_mode=True)

        if session.is_officer():
            with ui.element("div").classes("dc-mobile-nav"):
                for path, label, ico in OFFICER_MOBILE_NAV:
                    is_act = (
                        (path == "/my-week" and active == "my_week")
                        or (path == "/time-punch" and active == "time_punch")
                        or (path == "/my-schedule" and active == "my_schedule")
                        or (path == "/open-shifts" and active == "open_shifts")
                        or (path == "/time-off" and active == "time_off")
                        or (path == "/timecards" and active == "timecards")
                        or (path == "/banks" and active == "banks")
                        or (path == "/bidding" and active == "bidding")
                    )
                    item_cls = "dc-mobile-nav-item active" if is_act else "dc-mobile-nav-item"
                    with ui.element("div").classes(item_cls).on("click", lambda _e, p=path: ui.navigate.to(p)):
                        ui.html(f'<span class="nav-ico">{ico}</span>', sanitize=False)
                        ui.label(label)

        _status_bar(engine)
        _install_command_palette()
        try:
            ui.run_javascript(
                """
                try {
                  const s = document.querySelector('.dc-shell');
                  if (!s) return;
                  if (localStorage.getItem('chronos_rail_collapsed') === '1')
                    s.classList.add('rail-collapsed');
                  if (localStorage.getItem('chronos_dock_hidden') === '1')
                    s.classList.add('dock-hidden');
                } catch (e) {}
                """
            )
        except Exception:
            pass
        # Soft-refresh dock every 45s so new leave/alerts pulse in
        try:
            dock_host = getattr(layout, "_dock_host", None)
            if dock_host is not None:

                def _refresh_dock():
                    try:
                        _fill_dock_body(dock_host, officer_mode=session.is_officer())
                    except Exception:
                        pass

                t = ui.timer(45.0, _refresh_dock)
                t._parent_slot = None
        except Exception:
            pass


def _fill_dock_body(host, *, officer_mode: bool = False) -> None:
    from gui.ui_patterns import build_dock_feed, dock_queue_card, dock_section, empty_state

    host.clear()
    with host:
        feed = build_dock_feed()
        leave = feed.get("leave") or []
        swaps = feed.get("swaps") or []
        alerts = feed.get("alerts") or []
        certs = feed.get("certs") or []
        fatigue = int(feed.get("fatigue") or 0)

        if not officer_mode:
            dock_section("Leave queue", count=len(leave))
            if leave:
                for item in leave:
                    dock_queue_card(
                        item["title"],
                        item.get("body", ""),
                        path=item.get("path") or "/time-off",
                        level=item.get("level") or "warn",
                    )
            else:
                empty_state("Queue clear", "No pending leave.", cta_label="Open leave", cta_path="/time-off")
            if swaps:
                dock_section("Shift exchanges", count=len(swaps))
                for item in swaps:
                    dock_queue_card(
                        item["title"],
                        item.get("body", ""),
                        path="/time-off",
                        level="warn",
                    )
            dock_section("Readiness")
            if fatigue:
                dock_queue_card(
                    f"Fatigue / hours · {fatigue}",
                    "Officers near FLSA / hours threshold",
                    path="/payroll",
                    level="warn",
                )
            if certs:
                for item in certs:
                    dock_queue_card(
                        item["title"],
                        item.get("body", ""),
                        path="/certs",
                        level="warn",
                    )
            elif not fatigue:
                dock_queue_card("Certs & hours OK", "No expiring certs or fatigue flags", path="/certs", level="ok")

        dock_section("Alerts", count=len(alerts))
        if alerts:
            for item in alerts:
                dock_queue_card(
                    item["title"],
                    item.get("body", ""),
                    path=item.get("path") or "/notifications",
                    level=item.get("level") or "info",
                )
        else:
            empty_state("Inbox clear", "No unread alerts.", cta_label="Open alerts", cta_path="/notifications")

        with ui.row().classes("gap-2 q-mt-md flex-wrap"):
            if not officer_mode:
                ui.button("Ops desk", on_click=lambda: ui.navigate.to("/ops-desk")).classes("btn-ghost").props(
                    "dense no-caps outline"
                )
            ui.button("Open shifts", on_click=lambda: ui.navigate.to("/open-shifts")).classes("btn-ghost").props(
                "dense no-caps outline"
            )


def _render_right_dock(*, officer_mode: bool = False) -> None:
    with ui.element("aside").classes("dc-dock"):
        with ui.element("div").classes("dock-head"):
            ui.html('<div class="dock-head-title">Command queue</div>', sanitize=False)

            def _hide():
                try:
                    ui.run_javascript(
                        """
                        const s = document.querySelector('.dc-shell');
                        if (s) {
                          s.classList.add('dock-hidden');
                          try { localStorage.setItem('chronos_dock_hidden', '1'); } catch (e) {}
                        }
                        """
                    )
                except Exception:
                    pass

            ui.button("Hide", on_click=_hide).classes("btn-ghost").props("dense no-caps flat")
        body = ui.element("div").classes("dock-body")
        layout._dock_host = body  # type: ignore[attr-defined]
        _fill_dock_body(body, officer_mode=officer_mode)


def _install_command_palette() -> None:
    """Ctrl+K jump — Linear/ops-console pattern + recent/favorites."""
    destinations = []
    for item in _nav_items():
        if item[0] == "section":
            continue
        path, label, _key, _ico = item
        if _nav_visible(path):
            destinations.append((label, path))
    for label, path in (
        ("Open shifts board", "/open-shifts"),
        ("Shift bidding", "/bidding"),
        ("Callback rotation", "/callbacks"),
        ("Availability / blackouts", "/availability"),
        ("Alerts inbox", "/notifications"),
        ("Certifications", "/certs"),
        ("Ops reports", "/operations"),
        ("My week", "/my-week"),
        ("Duty board", "/"),
        ("Time banks", "/banks"),
        ("Exports hub", "/exports"),
    ):
        if path not in {p for _, p in destinations} and _nav_visible(path):
            destinations.append((label, path))

    with ui.dialog() as dlg, ui.card().classes("w-full").style("min-width:min(420px,92vw);max-width:520px"):
        ui.label("Jump to…").classes("text-sm font-semibold q-mb-sm")
        ui.html(
            '<div class="cmd-palette-meta">Ctrl+K · / focus · star = favorite · recent first</div>',
            sanitize=False,
        )
        search = ui.input(placeholder="Page name…").classes("w-full q-mt-sm").props("autofocus dense outlined dark")
        list_host = ui.element("div").classes("q-mt-sm")

        def _toggle_fav(path: str):
            try:
                ui.run_javascript(
                    f"""
                    try {{
                      let f = JSON.parse(localStorage.getItem('chronos_fav_pages') || '[]');
                      if (f.includes({path!r})) f = f.filter(x => x !== {path!r});
                      else f.unshift({path!r});
                      localStorage.setItem('chronos_fav_pages', JSON.stringify(f.slice(0, 12)));
                    }} catch (e) {{}}
                    """
                )
            except Exception:
                pass
            render_list(search.value or "")

        def _go(path: str):
            _remember_nav(path)
            dlg.close()
            ui.navigate.to(path)

        def render_list(q: str = ""):
            list_host.clear()
            qq = (q or "").strip().lower()
            ordered = list(destinations)
            # Favorites + recent bubble to top when no query (role-aware list already filtered)
            with list_host:
                ui.label("All pages").classes("text-xs text-gray-500 q-mb-xs")
                shown = 0
                for label, path in ordered:
                    if qq and qq not in label.lower() and qq not in path.lower():
                        continue
                    shown += 1
                    with ui.row().classes("w-full items-center gap-1 q-mb-xs"):
                        ui.button(
                            f"{label}  ·  {path}",
                            on_click=lambda _e=None, p=path: _go(p),
                        ).classes("btn-ghost").props("no-caps outline dense align=left").style(
                            "flex:1;justify-content:flex-start"
                        )
                        ui.button("☆", on_click=lambda _e=None, p=path: _toggle_fav(p)).classes("btn-ghost").props(
                            "dense flat"
                        ).tooltip("Toggle favorite")
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

    def _on_key(e):
        key = getattr(e, "key", None)
        mods = getattr(e, "modifiers", None)
        action = getattr(e, "action", None)
        if action is not None and not getattr(action, "keydown", True):
            return
        ctrl = bool(getattr(mods, "ctrl", False) or getattr(mods, "meta", False))
        # Ctrl+K palette
        if key == "k" and ctrl:
            open_palette()
            return
        # Ctrl+/ or bare / when not in input — open palette
        if key in ("/", "Slash") and (ctrl or True):
            # Avoid stealing typing: only with ctrl for slash
            if ctrl:
                open_palette()
                return
        # g then h → home (simple: Ctrl+H home)
        if key == "h" and ctrl:
            ui.navigate.to("/")
            return
        # Ctrl+B toggle rail
        if key == "b" and ctrl:
            try:
                ui.run_javascript(
                    """
                    const s = document.querySelector('.dc-shell');
                    if (!s) return;
                    s.classList.toggle('rail-collapsed');
                    try {
                      localStorage.setItem(
                        'chronos_rail_collapsed',
                        s.classList.contains('rail-collapsed') ? '1' : '0'
                      );
                    } catch (e) {}
                    """
                )
            except Exception:
                pass
            return
        # Ctrl+. toggle dock
        if key in (".", "Period") and ctrl:
            try:
                ui.run_javascript(
                    """
                    const s = document.querySelector('.dc-shell');
                    if (!s) return;
                    s.classList.toggle('dock-hidden');
                    try {
                      localStorage.setItem(
                        'chronos_dock_hidden',
                        s.classList.contains('dock-hidden') ? '1' : '0'
                      );
                    } catch (e) {}
                    """
                )
            except Exception:
                pass

    try:
        ui.keyboard(on_key=_on_key)
    except Exception:
        pass
    try:
        with ui.page_sticky(position="bottom-right", x_offset=18, y_offset=48):
            ui.button("⌘K", on_click=open_palette).props("fab-mini outline color=primary dense").tooltip(
                "Jump (Ctrl+K) · rail Ctrl+B · dock Ctrl+."
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
