"""In-app alerts inbox — LE self-service pattern."""

from __future__ import annotations

from nicegui import ui

from gui import session
from gui.shell import layout, page_header, panel
from logic import (
    create_notification,
    get_notifications,
    get_officers_by_seniority,
    mark_all_notifications_read,
    mark_notification_read,
    resolve_notification_navigation,
)
from validators import format_date, parse_date

# Legacy page keys from resolve_notification_navigation → Chronos routes
_NAV_PAGE_TO_PATH = {
    "requests": "/time-off",
    "swaps": "/time-off",
    "availability": "/availability",
    "open_shift": "/open-shifts",
    "shift_bid": "/bidding",
    "schedule": "/live-schedule",
    "payroll": "/payroll",
    "timecard": "/timecards",
    "notifications": "/notifications",
    "dashboard": "/",
}


def chronos_path_for_notification(n: dict) -> str:
    """Map a notification row to a Chronos NiceGUI path (pure; no UI side effects).

    Logic still emits legacy CTk page keys (requests, availability, …). Chronos
    overrides open-shift / bidding / payroll to primary product routes.
    """
    try:
        nav = resolve_notification_navigation(n) or {}
    except Exception:
        nav = {}
    page = (nav.get("page") or "").strip()
    highlight = (nav.get("highlight") or "").strip()
    ntype = (n.get("type") or n.get("notification_type") or "").strip()
    related = (n.get("related_type") or "").strip()

    if related == "open_shift" or ntype in ("Open Shift", "open_shift") or highlight == "open_shift":
        return "/open-shifts"
    if related in ("shift_bid_slot", "shift_bid_event") or ntype == "Shift Bid" or highlight == "shift_bid":
        return "/bidding"
    if related == "pay_period" or ntype == "Payroll" or page in ("timecard", "payroll"):
        # Pay-period lock alerts land on payroll close UI
        if related == "pay_period" or ntype == "Payroll":
            return "/payroll"
        return _NAV_PAGE_TO_PATH.get(page) or "/timecards"
    if page in _NAV_PAGE_TO_PATH:
        return _NAV_PAGE_TO_PATH[page]
    return "/notifications"


def _format_when(raw) -> str:
    """US short date for inbox timestamps when parseable; else trim ISO."""
    if raw is None or raw == "":
        return ""
    s = str(raw).strip()
    try:
        # date-only or leading ISO date
        head = s[:10] if len(s) >= 10 and s[4] == "-" else s
        d = parse_date(head)
        if d:
            time_bit = ""
            if "T" in s or " " in s:
                tail = s.replace("T", " ").split(" ", 1)
                if len(tail) > 1:
                    time_bit = " " + tail[1][:5]
            return format_date(d) + time_bit
    except Exception:
        pass
    return s[:16]


def _open_related(n: dict) -> None:
    """Jump to Chronos page for this alert; mark read."""
    nid = n.get("id")
    if nid is not None:
        try:
            mark_notification_read(int(nid))
        except Exception:
            pass
    ui.navigate.to(chronos_path_for_notification(n))


def render_notifications() -> None:
    def body() -> None:
        page_header(
            "Alerts & notifications",
            "Inbox for schedule, leave, open-shift digests, and system messages",
            kicker="Self-service",
        )
        view_oid = session.linked_officer_id()
        host = ui.element("div")
        unread_only = ui.checkbox("Unread only", value=False).classes("q-mb-sm")

        def refresh():
            host.clear()
            with host:
                try:
                    rows = (
                        get_notifications(
                            officer_id=view_oid,
                            unread_only=bool(unread_only.value),
                            limit=80,
                        )
                        or []
                    )
                except Exception as exc:
                    ui.label(str(exc)).classes("text-sm text-red-400")
                    return
                if not rows:
                    ui.html(
                        '<div class="alert alert-ok">Inbox clear — no notifications.</div>',
                        sanitize=False,
                    )
                    return
                with panel(f"{len(rows)} message(s)", glow=True):
                    for n in rows:
                        if not isinstance(n, dict):
                            continue
                        unread = not n.get("is_read") and not n.get("read_at")
                        with ui.element("div").classes("data-row"):
                            with ui.element("div").classes("grow"):
                                title = n.get("title") or n.get("notification_type") or "Alert"
                                ui.label(("● " if unread else "") + str(title)).classes(
                                    "text-sm font-semibold" if unread else "text-sm"
                                )
                                ui.label((n.get("message") or "")[:500]).classes("text-xs text-gray-400")
                                ui.label(_format_when(n.get("created_at"))).classes("text-xs text-gray-600")
                            with ui.row().classes("gap-1"):
                                ui.button(
                                    "Open",
                                    on_click=lambda row=n: _open_related(row),
                                ).props("dense no-caps flat")
                                if unread:

                                    def mark(nid=n.get("id")):
                                        if nid is None:
                                            return
                                        mark_notification_read(int(nid))
                                        refresh()

                                    ui.button("Read", on_click=mark).props("dense no-caps flat")

        with ui.row().classes("gap-2 q-mb-md flex-wrap"):
            ui.button("Refresh", on_click=refresh).classes("btn-ghost").props("no-caps outline dense")

            def mark_all():
                r = mark_all_notifications_read(officer_id=view_oid)
                ok = r.get("success") is not False
                ui.notify(
                    r.get("message", "Marked read") if ok else r.get("message", "Failed"),
                    type="positive" if ok else "negative",
                )
                refresh()

            ui.button("Mark all read", on_click=mark_all).classes("btn-ghost").props("no-caps outline dense")

        # Supervisor: compose in-app alert (create_notification)
        if session.can("requests.approve") or session.can("payroll.edit") or session.can("admin.settings"):
            with panel("Send in-app alert", glow=False):
                officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
                names = [o["name"] for o in officers]
                omap = {o["name"]: o["id"] for o in officers}
                if not names:
                    ui.html('<div class="alert alert-warn">No officers.</div>', sanitize=False)
                else:
                    to_sel = ui.select(names, value=names[0], label="To officer").classes("w-full")
                    ntype = ui.select(
                        ["general", "coverage", "schedule", "payroll", "open_shift"],
                        value="general",
                        label="Type",
                    ).classes("w-full")
                    title_in = ui.input(label="Title", value="Department notice").classes("w-full")
                    msg_in = ui.textarea(label="Message").classes("w-full").props("outlined dense dark rows=3")

                    def send_alert():
                        oid = omap.get(to_sel.value)
                        if not oid:
                            ui.notify("Select officer", type="negative")
                            return
                        r = create_notification(
                            oid,
                            ntype.value or "general",
                            (title_in.value or "Notice").strip(),
                            (msg_in.value or "").strip() or "—",
                        )
                        ok = r is True or (isinstance(r, dict) and r.get("success") is not False)
                        if ok:
                            ui.notify("Alert sent", type="positive")
                            refresh()
                        else:
                            ui.notify(
                                (r.get("message") if isinstance(r, dict) else None) or "Send failed",
                                type="negative",
                            )

                    ui.button("Send alert", on_click=send_alert).classes("btn-primary q-mt-sm").props(
                        "no-caps unelevated dense"
                    )

        try:
            unread_only.on_value_change(lambda: refresh())
        except Exception:
            pass
        refresh()

    layout("notifications", body)
