"""Offline multi-page API snapshot — read-only JSON for PWA cache.

Honest: mutations still need network. This gives officers My Week / open shifts /
duty strip / ops KPI when shell is cached and snapshot was saved online.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from validators import format_date


def build_offline_snapshot(
    *,
    officer_id: Optional[int] = None,
    reference: Optional[date] = None,
) -> Dict[str, Any]:
    """Build multi-page offline payload (safe public structure)."""
    reference = reference or date.today()
    pages: Dict[str, Any] = {}

    # My Week / schedule window
    my_week: Dict[str, Any] = {"days": [], "officer_id": officer_id}
    if officer_id:
        try:
            from logic.snapshots import get_officer_schedule_window

            window = get_officer_schedule_window(int(officer_id), start_date=reference, days=7) or {}
            days = window.get("schedule_days") or window.get("days") or window.get("schedule") or []
            my_week["days"] = days if isinstance(days, (list, dict)) else []
            my_week["ok"] = True
        except Exception as exc:
            my_week["ok"] = False
            my_week["error"] = str(exc)[:120]
    pages["my_week"] = my_week
    pages["my_schedule"] = my_week

    # Open shifts
    try:
        from logic.operations import get_open_shifts

        shifts = get_open_shifts() or []
        if isinstance(shifts, dict):
            shifts = shifts.get("shifts") or shifts.get("rows") or []
        pages["open_shifts"] = {
            "ok": True,
            "count": len(shifts) if isinstance(shifts, list) else 0,
            "rows": (shifts[:30] if isinstance(shifts, list) else []),
        }
    except Exception as exc:
        pages["open_shifts"] = {"ok": False, "error": str(exc)[:120], "rows": []}

    # Live duty strip (today) — lightweight
    duty_rows: List[Dict[str, Any]] = []
    try:
        from logic.officers import get_officers_by_seniority
        from logic.scheduling import is_officer_working_on_day

        for o in get_officers_by_seniority() or []:
            if not o.get("active", 1):
                continue
            try:
                working = is_officer_working_on_day(int(o["id"]), reference, o.get("squad"))
            except Exception:
                working = False
            if working:
                duty_rows.append(
                    {
                        "officer_id": o.get("id"),
                        "name": o.get("name"),
                        "squad": o.get("squad"),
                        "shift_start": o.get("shift_start"),
                        "shift_end": o.get("shift_end"),
                    }
                )
        pages["duty_today"] = {
            "ok": True,
            "date": reference.isoformat(),
            "date_display": format_date(reference),
            "rows": duty_rows[:40],
            "count": len(duty_rows),
        }
    except Exception as exc:
        pages["duty_today"] = {"ok": False, "error": str(exc)[:120], "rows": []}

    # Ops KPI (supervisor offline glance)
    try:
        from logic.ops_desk import get_ops_desk_board

        board = get_ops_desk_board(reference=reference) or {}
        pages["ops_desk"] = {
            "ok": bool(board.get("success", True)),
            "kpi": board.get("kpi") or {},
            "date_display": board.get("date_display") or format_date(reference),
        }
    except Exception as exc:
        pages["ops_desk"] = {"ok": False, "error": str(exc)[:120], "kpi": {}}

    # Leave pending count
    try:
        from logic.requests import get_pending_day_off_requests

        pending = get_pending_day_off_requests() or []
        if isinstance(pending, dict):
            pending = pending.get("requests") or pending.get("rows") or []
        pages["time_off"] = {
            "ok": True,
            "pending_count": len(pending) if isinstance(pending, list) else 0,
        }
    except Exception as exc:
        pages["time_off"] = {"ok": False, "error": str(exc)[:120]}

    # Offline mutation queue — drafts while offline; flush to POST /api/offline/mutations when online
    pages["mutation_policy"] = {
        "queue_key": "chronos_offline_mutation_queue_v1",
        "apply_path": "/api/offline/mutations",
        "allowed_actions": [
            "claim_open_shift",
            "time_punch",
            "mark_notification_read",
            "mark_all_notifications_read",
            "create_day_off_request",
        ],
        "allowed_when_offline": [
            "claim_open_shift",
            "time_punch",
            "mark_notification_read",
            "mark_all_notifications_read",
            "create_day_off_request",
        ],
        "message": (
            "Queue mutations offline; on reconnect client POSTs /api/offline/mutations. "
            "Approve leave still requires supervisor + network (not queued for safety)."
        ),
        "mutations_apply": True,
    }

    text_lines = [
        f"Chronos offline snapshot · {format_date(reference)} · {datetime.now().isoformat(timespec='seconds')}",
        f"On duty today: {pages.get('duty_today', {}).get('count', 0)}",
        f"Open shifts: {pages.get('open_shifts', {}).get('count', 0)}",
        f"Pending leave: {pages.get('time_off', {}).get('pending_count', '—')}",
        f"Ops KPI: {pages.get('ops_desk', {}).get('kpi') or '{}'}",
    ]
    if officer_id and isinstance(my_week.get("days"), list):
        for d in my_week["days"][:7]:
            if isinstance(d, dict):
                text_lines.append(
                    f"  {d.get('date') or d.get('work_date')}: {d.get('status') or d.get('duty') or '—'} "
                    f"{d.get('shift_start') or ''}"
                )

    return {
        "success": True,
        "product": "Chronos Command",
        "vendor": "Weierworks Technologies, LLC",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "reference": reference.isoformat(),
        "officer_id": officer_id,
        "pages": pages,
        "text": "\n".join(text_lines),
        "offline_api": True,
        "message": "Multi-page offline snapshot ready (read-only)",
    }


def offline_snapshot_json(
    *,
    officer_id: Optional[int] = None,
    reference: Optional[date] = None,
) -> str:
    return json.dumps(build_offline_snapshot(officer_id=officer_id, reference=reference), default=str)


def list_offline_precached_paths() -> List[str]:
    """Paths SW should precache for multi-page offline shell + API."""
    return [
        "/",
        "/login",
        "/my-schedule",
        "/my-week",
        "/open-shifts",
        "/time-off",
        "/timecards",
        "/time-punch",
        "/notifications",
        "/bidding",
        "/ops-desk",
        "/live-schedule",
        "/dashboard",
        "/static/chronos.css",
        "/static/fonts.css",
        "/static/manifest.webmanifest",
        "/static/chronos_logo.png",
        "/static/sw.js",
        "/static/offline.html",
        "/static/offline-cache.js",
        "/api/offline/snapshot",
    ]


def apply_offline_mutations(
    items: List[Dict[str, Any]],
    *,
    user_id: Optional[int] = None,
    officer_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Apply queued offline mutations when client reconnects.

    Supported actions (idempotent best-effort):
      claim_open_shift · time_punch · mark_notification_read ·
      mark_all_notifications_read · create_day_off_request
    Approve leave is intentionally NOT supported offline (supervisor safety).
    """
    if not isinstance(items, list):
        return {"success": False, "message": "items must be a list", "results": []}

    results: List[Dict[str, Any]] = []
    applied = failed = skipped = 0

    for raw in items[:50]:
        if not isinstance(raw, dict):
            skipped += 1
            results.append({"success": False, "message": "bad item", "id": None})
            continue
        action = str(raw.get("action") or "").strip().lower()
        payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}
        mid = raw.get("id")
        try:
            if action in ("claim_open_shift", "claim_shift", "fill_open_shift"):
                from logic.operations import fill_open_shift

                sid = payload.get("shift_id") or payload.get("open_shift_id") or payload.get("id")
                oid = payload.get("officer_id") or officer_id
                if not sid or not oid:
                    raise ValueError("shift_id and officer_id required")
                r = fill_open_shift(int(sid), int(oid), user_id=user_id)
                ok = bool(r.get("success"))
                results.append({"id": mid, "action": action, "success": ok, "message": r.get("message")})
                applied += 1 if ok else 0
                failed += 0 if ok else 1
            elif action in ("time_punch", "punch", "clock"):
                from logic.time_punch import officer_clock

                oid = payload.get("officer_id") or officer_id
                ptype = payload.get("punch_type") or payload.get("type") or "in"
                if not oid:
                    raise ValueError("officer_id required")
                r = officer_clock(int(oid), str(ptype), user_id=user_id, notes=payload.get("notes") or "offline")
                ok = bool(r.get("success"))
                results.append({"id": mid, "action": action, "success": ok, "message": r.get("message")})
                applied += 1 if ok else 0
                failed += 0 if ok else 1
            elif action in ("mark_notification_read", "mark_read"):
                from logic import mark_notification_read

                nid = payload.get("notification_id") or payload.get("id")
                if nid is None:
                    raise ValueError("notification_id required")
                mark_notification_read(int(nid))
                results.append({"id": mid, "action": action, "success": True, "message": "marked read"})
                applied += 1
            elif action in ("mark_all_notifications_read", "mark_all_read"):
                from logic import mark_all_notifications_read

                oid = payload.get("officer_id") or officer_id
                r = mark_all_notifications_read(officer_id=oid)
                ok = r.get("success") is not False
                results.append(
                    {
                        "id": mid,
                        "action": action,
                        "success": ok,
                        "message": r.get("message") if isinstance(r, dict) else "ok",
                    }
                )
                applied += 1 if ok else 0
                failed += 0 if ok else 1
            elif action in ("create_day_off_request", "submit_leave"):
                from logic.requests import create_day_off_request

                oid = payload.get("officer_id") or officer_id
                ds = payload.get("date") or payload.get("request_date")
                rtype = payload.get("request_type") or payload.get("type") or "PTO"
                notes = payload.get("notes") or "offline queue"
                if not oid or not ds:
                    raise ValueError("officer_id and date required")
                r = create_day_off_request(int(oid), ds, rtype, notes)
                ok = bool(r.get("success"))
                results.append(
                    {
                        "id": mid,
                        "action": action,
                        "success": ok,
                        "message": r.get("message"),
                        "request_id": r.get("request_id"),
                    }
                )
                applied += 1 if ok else 0
                failed += 0 if ok else 1
            elif action in ("approve_leave", "process_day_off", "approve_day_off"):
                skipped += 1
                results.append(
                    {
                        "id": mid,
                        "action": action,
                        "success": False,
                        "skipped": True,
                        "message": "Approve leave not allowed offline — open Time Off online",
                    }
                )
            else:
                skipped += 1
                results.append({"id": mid, "action": action, "success": False, "message": f"unknown action: {action}"})
        except Exception as exc:
            failed += 1
            results.append({"id": mid, "action": action, "success": False, "message": str(exc)[:200]})

    return {
        "success": failed == 0,
        "applied": applied,
        "failed": failed,
        "skipped": skipped,
        "results": results,
        "message": f"Offline mutations: applied={applied} failed={failed} skipped={skipped}",
    }
