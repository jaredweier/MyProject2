"""Dodgeville PD Duty Console — NiceGUI entry (web host + downloadable native window).

Modes:
  python main.py              # default: native window if available, else browser
  python main.py --web        # host online: bind 0.0.0.0
  python main.py --browser    # local browser (127.0.0.1)
  python main.py --native     # native window (pywebview)
"""

from __future__ import annotations

import argparse
import logging
import os
import secrets
import sys
from pathlib import Path

from nicegui import app, ui

from database import init_database
from gui.pages.access import render_access
from gui.pages.availability import render_availability
from gui.pages.bidding import render_bidding
from gui.pages.callbacks import render_callbacks
from gui.pages.certs import render_certs
from gui.pages.dashboard import render_dashboard
from gui.pages.finance import render_payroll, render_timecards
from gui.pages.leave import render_leave
from gui.pages.login import render_login
from gui.pages.media import render_media
from gui.pages.notifications import render_notifications
from gui.pages.operations import render_operations
from gui.pages.roster import render_roster
from gui.pages.schedules import render_live_schedule, render_monthly_schedule, render_my_schedule
from gui.pages.security import render_security
from gui.pages.self_service import render_open_shifts
from gui.pages.simulator import render_simulator

log = logging.getLogger("dodgeville.gui")


@ui.page("/login")
def page_login() -> None:
    render_login()


@ui.page("/")
def page_home() -> None:
    render_dashboard()


# —— Scheduling ——
@ui.page("/my-schedule")
def page_my_schedule() -> None:
    render_my_schedule()


@ui.page("/monthly-schedule")
def page_monthly() -> None:
    render_monthly_schedule()


@ui.page("/live-schedule")
def page_live() -> None:
    render_live_schedule()


@ui.page("/time-off")
def page_time_off() -> None:
    render_leave()


@ui.page("/open-shifts")
def page_open_shifts() -> None:
    render_open_shifts()


@ui.page("/bidding")
def page_bidding() -> None:
    render_bidding()


@ui.page("/callbacks")
def page_callbacks() -> None:
    render_callbacks()


@ui.page("/availability")
def page_availability() -> None:
    render_availability()


@ui.page("/notifications")
def page_notifications() -> None:
    render_notifications()


@ui.page("/certs")
def page_certs() -> None:
    render_certs()


# Legacy redirects
@ui.page("/schedules")
def page_schedules_legacy() -> None:
    ui.navigate.to("/live-schedule")


@ui.page("/timeline")
def page_timeline_legacy() -> None:
    ui.navigate.to("/my-schedule")


@ui.page("/leave")
def page_leave_legacy() -> None:
    ui.navigate.to("/time-off")


@ui.page("/finance")
def page_finance_legacy() -> None:
    ui.navigate.to("/timecards")


# —— Personnel ——
@ui.page("/roster")
def page_roster() -> None:
    render_roster()


@ui.page("/media")
def page_media() -> None:
    render_media()


# —— Finance ——
@ui.page("/timecards")
def page_timecards() -> None:
    render_timecards()


@ui.page("/payroll")
def page_payroll() -> None:
    render_payroll()


# —— Command ——
@ui.page("/simulator")
def page_simulator() -> None:
    render_simulator()


@ui.page("/operations")
def page_operations() -> None:
    render_operations()


@ui.page("/security")
def page_security() -> None:
    render_security()


@ui.page("/access")
def page_access() -> None:
    render_access()


def _storage_secret() -> str:
    env = os.environ.get("SCHEDULER_STORAGE_SECRET", "").strip()
    if env:
        return env
    try:
        from paths import data_path

        path = Path(data_path("storage_secret.txt"))
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
        path.parent.mkdir(parents=True, exist_ok=True)
        secret = secrets.token_hex(32)
        path.write_text(secret, encoding="utf-8")
        return secret
    except Exception:
        return secrets.token_hex(32)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Dodgeville PD Duty Console")
    p.add_argument("--web", action="store_true", help="Host for online access")
    p.add_argument("--browser", action="store_true", help="Local browser only")
    p.add_argument("--native", action="store_true", help="Native desktop window")
    p.add_argument("--host", default=None)
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--reload", action="store_true")
    return p.parse_args(argv)


def _resolve_mode(args: argparse.Namespace) -> str:
    env = os.environ.get("SCHEDULER_UI_MODE", "").strip().lower()
    if args.web or env == "web":
        return "web"
    if args.browser or env == "browser":
        return "browser"
    if args.native or env == "native":
        return "native"
    try:
        import webview  # noqa: F401

        return "native"
    except Exception:
        return "browser"


def _ensure_static_css() -> None:
    """Sync theme CSS to gui/static and mount /static for reliable stylesheet load."""
    from gui.theme import GLOBAL_CSS

    static_dir = Path(__file__).resolve().parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    css_path = static_dir / "chronos.css"
    try:
        css_path.write_text(GLOBAL_CSS, encoding="utf-8")
    except OSError as exc:
        log.warning("Could not write chronos.css: %s", exc)
    try:
        app.add_static_files("/static", str(static_dir))
    except Exception as exc:
        log.warning("Could not mount /static: %s", exc)


def run(argv: list[str] | None = None) -> None:
    from config import APP_NAME, APP_VERSION, configure_logging

    configure_logging()
    init_database()
    _ensure_static_css()

    args = _parse_args(argv if argv is not None else sys.argv[1:])
    mode = _resolve_mode(args)
    port = args.port or int(os.environ.get("SCHEDULER_PORT", "8080"))
    if mode == "web":
        host = args.host or os.environ.get("SCHEDULER_HOST", "0.0.0.0")
        show, native = False, False
    elif mode == "native":
        host = args.host or "127.0.0.1"
        show, native = False, True
    else:
        host = args.host or "127.0.0.1"
        show, native = True, False

    secret = _storage_secret()
    title = f"{APP_NAME}"
    log.info("Starting Chronos Command mode=%s host=%s port=%s v%s", mode, host, port, APP_VERSION)
    if mode == "web":
        print(f"\n=== {title} (ONLINE) ===\nListening http://{host}:{port}\n")
    elif mode == "native":
        print(f"\n=== {title} (DESKTOP) ===\n")
    else:
        print(f"\n=== {title} (BROWSER) ===\nhttp://{host}:{port}\n")

    ui.run(
        title=title,
        host=host,
        port=port,
        dark=True,
        reload=bool(args.reload),
        show=show,
        native=native,
        window_size=(1440, 900) if native else None,
        storage_secret=secret,
        favicon="🛡️",
        uvicorn_logging_level="warning",
        show_welcome_message=mode == "web",
    )


if __name__ in {"__main__", "__mp_main__"}:
    run()
