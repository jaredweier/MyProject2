"""Chronos UI patterns — empty states, skeletons, shift cards, dock feed helpers.

NiceGUI research notes (applied here + simulator):
- Prefer ``ui.refreshable`` local scopes over clear()+rebuild when lists change often
- Throttle noisy ``on_value_change`` / persist (binding poll + WS payload cost)
- Use ``run.io_bound`` for blocking work (keep event loop free)
- Skeleton > spinner walls; progressive disclosure for dense ops UIs
- Modular helpers keep pages readable (official modularization example)
- Step rail + hero + chips + splitter + expansion = command-center workflow
- Full sim surface styles live in ``gui/theme.py`` (``.sim-*``)

Keep business rules in logic.*; this module is presentation only.
"""

from __future__ import annotations

import time
from typing import Any, Awaitable, Callable, Optional, TypeVar

from nicegui import ui

F = TypeVar("F", bound=Callable[..., Any])


def throttled(fn: Callable[..., Any], seconds: float = 0.4) -> Callable[..., Any]:
    """Drop rapid-fire UI callbacks (NiceGUI value_change storms on typing).

    Leading-edge throttle: at most one call per *seconds*. Reduces WebSocket
    traffic and storage writes while typing in dense forms (simulator, etc.).
    """
    last = {"t": 0.0}

    def wrapper(*args, **kwargs):
        now = time.monotonic()
        if now - float(last["t"]) < float(seconds):
            return None
        last["t"] = now
        return fn(*args, **kwargs)

    return wrapper


async def run_busy(
    work: Callable[[], Any] | Callable[[], Awaitable[Any]],
    *,
    label: str = "Working…",
    notify: bool = True,
) -> Any:
    """Run sync/async work with a lightweight toast (keeps perceived performance)."""
    if notify:
        try:
            ui.notify(label, type="ongoing", position="top", timeout=0, spinner=True)
        except Exception:
            try:
                ui.notify(label, type="info", position="top")
            except Exception:
                pass
    try:
        result = work()
        if hasattr(result, "__await__"):
            return await result  # type: ignore[misc]
        return result
    finally:
        try:
            # dismiss ongoing toasts by notifying completion is page-owned
            pass
        except Exception:
            pass


def empty_state(
    title: str,
    hint: str = "",
    *,
    cta_label: str = "",
    cta_path: str = "",
    on_cta: Optional[Callable[[], None]] = None,
) -> None:
    """Empty list / zero-data state with optional next-step CTA."""
    with ui.element("div").classes("empty-state"):
        ui.html(f'<div class="empty-state-title">{title}</div>', sanitize=False)
        if hint:
            ui.html(f'<div class="empty-state-hint">{hint}</div>', sanitize=False)
        if cta_label and (cta_path or on_cta):

            def _go():
                if on_cta:
                    on_cta()
                elif cta_path:
                    ui.navigate.to(cta_path)

            ui.button(cta_label, on_click=_go).classes("btn-primary q-mt-sm").props("no-caps unelevated dense")


def skeleton_block(*, rows: int = 4, label: str = "Loading…") -> None:
    """Calm skeleton placeholder (no spinner walls on primary roster)."""
    with ui.element("div").classes("skeleton-host").props(f'aria-busy="true" aria-label="{label}"'):
        ui.html(f'<div class="skeleton-label">{label}</div>', sanitize=False)
        for _ in range(max(1, rows)):
            ui.html('<div class="skeleton-row"></div>', sanitize=False)


def status_chip(label: str, *, level: str = "info") -> None:
    """Uppercase micro status chip — semantic only."""
    lvl = (level or "info").lower()
    cls = "status-chip"
    if lvl in ("ok", "success"):
        cls += " status-chip-ok"
    elif lvl in ("warn", "warning"):
        cls += " status-chip-warn"
    elif lvl in ("crit", "critical", "danger"):
        cls += " status-chip-crit"
    else:
        cls += " status-chip-info"
    ui.html(f'<span class="{cls}">{label}</span>', sanitize=False)


def ng_chip(label: str, *, level: str = "info", icon: str = "") -> Any:
    """Native NiceGUI/Quasar chip (prefer over raw HTML when interactivity needed)."""
    lvl = (level or "info").lower()
    color = "primary"
    if lvl in ("ok", "success"):
        color = "positive"
    elif lvl in ("warn", "warning"):
        color = "warning"
    elif lvl in ("crit", "critical", "danger"):
        color = "negative"
    props = f"dense outline color={color}"
    if icon:
        return ui.chip(label, icon=icon).props(props)
    return ui.chip(label).props(props)


def skip_to_main() -> None:
    """Accessibility: skip link into main content (UX + a11y best practice)."""
    try:
        ui.skip_link("Skip to main content")
    except Exception:
        # Older NiceGUI fallback
        ui.html(
            '<a class="skip-link" href="#chronos-main">Skip to main content</a>',
            sanitize=False,
        )


def shift_card(
    *,
    title: str,
    subtitle: str = "",
    meta: str = "",
    status: str = "",
    status_level: str = "info",
    primary_label: str = "",
    on_primary: Optional[Callable[[], None]] = None,
    secondary_label: str = "",
    on_secondary: Optional[Callable[[], None]] = None,
    disabled_primary: bool = False,
    card_id: str = "",
) -> Any:
    """Mobile-first / Deputy-style shift vacancy or day card."""
    el = ui.element("div").classes("shift-card")
    if card_id:
        el.props(f'id="{card_id}" data-card-id="{card_id}"')
    with el:
        with ui.row().classes("items-start justify-between w-full gap-2"):
            with ui.element("div").classes("grow"):
                ui.label(title).classes("text-sm font-semibold shift-card-title")
                if subtitle:
                    ui.label(subtitle).classes("text-xs").style("color: var(--dim)")
                if meta:
                    ui.label(meta).classes("text-xs mono q-mt-xs").style("color: var(--muted)")
            if status:
                status_chip(status, level=status_level)
        if primary_label or secondary_label:
            with ui.row().classes("gap-2 q-mt-sm flex-wrap"):
                if primary_label and on_primary:
                    btn = (
                        ui.button(primary_label, on_click=on_primary)
                        .classes("btn-primary")
                        .props("dense no-caps unelevated")
                    )
                    if disabled_primary:
                        btn.props("disable")
                if secondary_label and on_secondary:
                    ui.button(secondary_label, on_click=on_secondary).classes("btn-ghost").props(
                        "dense no-caps outline"
                    )
    return el


def dock_section(title: str, *, count: int | None = None):
    """Right-dock section header."""
    label = title if count is None else f"{title} · {count}"
    ui.html(f'<div class="dock-sec-title">{label}</div>', sanitize=False)


def dock_queue_card(
    title: str,
    body: str = "",
    *,
    path: str = "",
    level: str = "info",
) -> None:
    """Compact queue card for leave / alerts dock."""
    lvl = (level or "info").lower()
    border = "var(--border)"
    if lvl in ("warn", "warning"):
        border = "rgba(240,180,41,0.45)"
    elif lvl in ("crit", "critical", "danger"):
        border = "rgba(232,93,93,0.5)"
    elif lvl in ("ok", "success"):
        border = "rgba(45,212,160,0.35)"

    def go():
        if path:
            ui.navigate.to(path)

    el = ui.element("div").classes("dock-card").style(f"border-left:3px solid {border}")
    if path:
        el.on("click", lambda _e: go())
        el.style(f"border-left:3px solid {border};cursor:pointer")
    with el:
        ui.label(title).classes("text-xs font-semibold")
        if body:
            ui.label(body).classes("text-xs").style("color: var(--dim)")


def nav_badge(count: int) -> str:
    """HTML fragment for nav badge count (0 → empty)."""
    n = int(count or 0)
    if n <= 0:
        return ""
    shown = "99+" if n > 99 else str(n)
    return f'<span class="nav-badge">{shown}</span>'


def collect_nav_badges() -> dict[str, int]:
    """Counts for nav urgency chips (best-effort; never blocks shell)."""
    out: dict[str, int] = {}
    try:
        from gui import session
        from logic import (
            get_open_shifts,
            get_pending_day_off_requests,
            get_pending_shift_swap_requests,
            get_unread_notification_count,
        )

        oid = session.linked_officer_id() if session.is_officer() else None
        try:
            out["notifications"] = int(get_unread_notification_count(officer_id=oid) or 0)
        except Exception:
            out["notifications"] = 0
        try:
            if session.can("requests.approve"):
                out["time_off"] = len(get_pending_day_off_requests() or [])
                out["time_off"] += len(get_pending_shift_swap_requests() or [])
            else:
                out["time_off"] = 0
        except Exception:
            out["time_off"] = 0
        try:
            opens = (
                get_open_shifts(status="open", limit=50, officer_id=oid)
                if oid
                else get_open_shifts(status="open", limit=50)
            )
            out["open_shifts"] = len(opens or [])
        except Exception:
            out["open_shifts"] = 0
    except Exception:
        pass
    return out


def build_dock_feed() -> dict[str, Any]:
    """Data for right dock: leave queue, alerts, certs, fatigue peek."""
    feed: dict[str, Any] = {
        "leave": [],
        "swaps": [],
        "alerts": [],
        "certs": [],
        "fatigue": 0,
    }
    try:
        from gui import session
        from logic import (
            get_hours_watch,
            get_notifications,
            get_pending_day_off_requests,
            get_pending_shift_swap_requests,
        )
        from validators import format_date

        if session.can("requests.approve") or session.can("reports.view"):
            for r in (get_pending_day_off_requests() or [])[:8]:
                if not isinstance(r, dict):
                    continue
                feed["leave"].append(
                    {
                        "title": f"{r.get('officer_name') or 'Officer'} · {r.get('request_type') or 'Leave'}",
                        "body": f"{format_date(r.get('request_date')) if r.get('request_date') else '—'} · "
                        f"{r.get('status') or 'Pending'}",
                        "path": "/time-off",
                        "level": "warn",
                    }
                )
            for s in (get_pending_shift_swap_requests() or [])[:4]:
                if not isinstance(s, dict):
                    continue
                feed["swaps"].append(
                    {
                        "title": f"Swap · {s.get('requester_name') or s.get('officer_name') or 'Officer'}",
                        "body": format_date(s.get("request_date") or s.get("shift_date") or "") or "Pending",
                        "path": "/time-off",
                        "level": "warn",
                    }
                )
        oid = session.linked_officer_id() if session.is_officer() else None
        for n in (get_notifications(officer_id=oid, unread_only=True, limit=8) or [])[:8]:
            if not isinstance(n, dict):
                continue
            feed["alerts"].append(
                {
                    "title": str(n.get("title") or n.get("notification_type") or "Alert")[:64],
                    "body": str(n.get("message") or "")[:80],
                    "path": "/notifications",
                    "level": "info",
                }
            )
        try:
            from logic.certifications import list_expiring_certifications

            for c in (list_expiring_certifications(within_days=60) or [])[:5]:
                if not isinstance(c, dict):
                    continue
                feed["certs"].append(
                    {
                        "title": f"{c.get('officer_name') or 'Officer'} · {c.get('cert_name') or c.get('cert_type') or 'Cert'}",
                        "body": f"Expires {format_date(c.get('expires_date')) if c.get('expires_date') else 'soon'}",
                        "path": "/certs",
                        "level": "warn",
                    }
                )
        except Exception:
            pass
        try:
            hw = get_hours_watch(officer_id=oid) or {}
            feed["fatigue"] = int(hw.get("warning_count") or 0) + int(hw.get("critical_count") or 0)
        except Exception:
            feed["fatigue"] = 0
    except Exception:
        pass
    return feed


def first_run_guide() -> None:
    """Empty-DB / empty-roster guided tiles."""
    try:
        from ui.helpers import active_officers

        n = len(active_officers() or [])
    except Exception:
        n = 0
    if n > 0:
        return
    with ui.element("div").classes("panel panel-glow w-full q-mb-md"):
        ui.html('<div class="page-kicker">Get started</div>', sanitize=False)
        ui.html(
            '<div class="kpi-hint" style="margin-top:6px">'
            "No active officers yet. Add personnel, then set rotation and publish the base schedule."
            "</div>",
            sanitize=False,
        )
        with ui.row().classes("gap-2 q-mt-sm flex-wrap"):
            ui.button("Add officers", on_click=lambda: ui.navigate.to("/roster")).classes("btn-primary").props(
                "no-caps unelevated dense"
            )
            ui.button("Deploy & implement", on_click=lambda: ui.navigate.to("/deploy")).classes("btn-ghost").props(
                "no-caps outline dense"
            )
            ui.button("Live schedule", on_click=lambda: ui.navigate.to("/live-schedule")).classes("btn-ghost").props(
                "no-caps outline dense"
            )
