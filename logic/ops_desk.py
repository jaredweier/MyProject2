"""Ops desk — manual-review recovery, today board, resolve actions.

Product policy: incomplete bump cascades route to Pending Manual Review.
This module gives supervisors a guided resolution desk (not a dead status).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Tuple

from config import REQUEST_STATUS
from logic.users import log_audit_action
from validators import format_date, storage_date


def _manual_status() -> str:
    return REQUEST_STATUS.get("pending_manual") or "Pending Manual Review"


def _pending_status() -> str:
    return REQUEST_STATUS.get("pending") or "Pending"


def diagnose_manual_review(request_id: int) -> Dict[str, Any]:
    """Why a request is stuck in manual review + recovery options."""
    from logic.callout_desk import build_callout_ladder
    from logic.coverage_optimizer import suggest_bump_chain
    from logic.officers import get_officer_by_id
    from logic.requests import get_day_off_requests
    from logic.scheduling_sim import preview_best_coverage_plans

    rows = get_day_off_requests() or []
    req = next((r for r in rows if int(r.get("id") or 0) == int(request_id)), None)
    if not req:
        # Try pending-only fetch
        for st in (_manual_status(), _pending_status(), "Approved", "Rejected"):
            for r in get_day_off_requests(status_filter=st) or []:
                if int(r.get("id") or 0) == int(request_id):
                    req = r
                    break
            if req:
                break
    if not req:
        return {"success": False, "message": f"Request #{request_id} not found"}

    oid = int(req["officer_id"])
    officer = get_officer_by_id(oid) or {}
    rdate = req.get("request_date")
    squad = req.get("squad") or officer.get("squad") or "A"
    shift = req.get("shift_start") or officer.get("shift_start") or "06:00"
    notes = (req.get("admin_notes") or "") + " " + (req.get("notes") or "")
    notes_l = notes.lower()

    stop_reasons: List[str] = []
    if "minimum rest" in notes_l or "rest" in notes_l:
        stop_reasons.append("minimum_rest")
    if "consecutive" in notes_l:
        stop_reasons.append("consecutive_days")
    if "night" in notes_l or "night minimum" in notes_l:
        stop_reasons.append("night_minimum")
    if "coverage" in notes_l or "window" in notes_l:
        stop_reasons.append("coverage_window")
    if "manual" in notes_l or "cascade" in notes_l or "depth" in notes_l:
        stop_reasons.append("cascade_incomplete")
    if not stop_reasons and (req.get("admin_notes") or "").strip():
        stop_reasons.append("engine_message")
    if not stop_reasons:
        stop_reasons.append("unknown_or_policy")

    reason_labels = {
        "minimum_rest": "Stopped: minimum rest between shifts",
        "consecutive_days": "Stopped: consecutive work-day limit",
        "night_minimum": "Stopped: Fri/Sat night minimum staffing",
        "coverage_window": "Stopped: coverage window / 24/7 short",
        "cascade_incomplete": "Stopped: partial bump cascade (needs manual cover)",
        "engine_message": "Engine notes require supervisor judgment",
        "unknown_or_policy": "No auto chain — supervisor must choose cover path",
    }
    why_lines = [reason_labels.get(r, r) for r in stop_reasons]
    if (req.get("admin_notes") or "").strip():
        why_lines.append(f"Notes: {req['admin_notes']}")

    suggestion = None
    try:
        suggestion = suggest_bump_chain(oid, rdate, squad, shift, supervisor_override=True)
    except Exception as exc:
        suggestion = type("S", (), {"success": False, "message": str(exc), "steps": []})()

    plans = []
    try:
        payload = preview_best_coverage_plans(oid, rdate, squad, shift, max_plans=5)
        plans = [p for p in (payload.get("plans") or []) if p.get("success")]
    except Exception:
        plans = []

    ladder = build_callout_ladder(
        oid, str(rdate), squad=squad, shift_start=shift, reason=req.get("request_type") or "Leave"
    )

    actions = [
        {
            "id": "approve_override",
            "label": "Approve with supervisor override",
            "description": "Force bump using best available plan (override rest/consecutive when needed)",
        },
        {
            "id": "order_in",
            "label": "OT order-in from callout ladder",
            "description": "Pick next eligible officer from fair OT / fill-mode ladder",
        },
        {
            "id": "open_shift",
            "label": "Publish open shift",
            "description": "Post vacancy for claim; leave stays manual until filled",
        },
        {
            "id": "partial_cover",
            "label": "Partial cover (order-in partial)",
            "description": "Adjacent-band partial cover via OT fill",
        },
        {
            "id": "reject",
            "label": "Reject leave",
            "description": "Deny request with notes — no coverage needed",
        },
    ]

    plan_summaries = []
    for i, p in enumerate(plans[:5], 1):
        steps = p.get("steps") or []
        chain = p.get("chain") or []
        plan_summaries.append(
            {
                "index": i,
                "message": p.get("message") or f"Option {i}",
                "step_count": len(steps) or len(chain),
                "chain": chain,
                "steps": steps,
            }
        )

    return {
        "success": True,
        "request": req,
        "officer": {"id": oid, "name": officer.get("name"), "squad": squad, "shift_start": shift},
        "date_display": format_date(rdate) if rdate else str(rdate),
        "stop_reasons": stop_reasons,
        "why_lines": why_lines,
        "suggestion_ok": bool(getattr(suggestion, "success", False)),
        "suggestion_message": getattr(suggestion, "message", "") or "",
        "plans": plan_summaries,
        "callout": ladder,
        "actions": actions,
        "text": "\n".join(
            [
                f"Manual review #{request_id} · {officer.get('name')} · {format_date(rdate) if rdate else rdate}",
                *why_lines,
                f"Override plan ready: {'yes' if getattr(suggestion, 'success', False) else 'no'}",
                f"Ranked plans: {len(plan_summaries)} · Callout eligible: {len(ladder.get('eligible') or [])}",
            ]
        ),
    }


def list_manual_review_queue() -> Dict[str, Any]:
    from logic.requests import get_day_off_requests

    rows = get_day_off_requests(status_filter=_manual_status()) or []
    items = []
    for r in rows:
        items.append(
            {
                "id": r.get("id"),
                "officer_id": r.get("officer_id"),
                "officer_name": r.get("officer_name"),
                "request_date": r.get("request_date"),
                "date_display": format_date(r["request_date"]) if r.get("request_date") else "",
                "request_type": r.get("request_type"),
                "squad": r.get("squad"),
                "shift_start": r.get("shift_start"),
                "admin_notes": r.get("admin_notes") or "",
                "status": r.get("status"),
            }
        )
    return {"success": True, "count": len(items), "items": items}


def resolve_manual_review(
    request_id: int,
    action: str,
    *,
    cover_officer_id: Optional[int] = None,
    preferred_chain: Optional[Sequence[Tuple[int, int]]] = None,
    plan_index: Optional[int] = None,
    admin_notes: str = "",
    hours: float = 8.0,
    is_partial: bool = False,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute one recovery path; audit the choice."""
    from logic.callout_desk import execute_callout_order
    from logic.requests import process_day_off_request

    diag = diagnose_manual_review(request_id)
    if not diag.get("success"):
        return diag
    req = diag["request"]
    oid = int(req["officer_id"])
    rdate = str(req["request_date"])
    action = (action or "").strip().lower()

    audit_note = admin_notes or f"ops_desk:{action}"

    if action == "reject":
        pr = process_day_off_request(
            request_id,
            action="reject",
            admin_notes=audit_note or "Rejected from ops desk",
            actor_user_id=user_id,
        )
        ok = bool(getattr(pr, "success", False))
        if user_id is not None:
            log_audit_action(
                user_id,
                "manual_review_reject",
                "day_off_requests",
                request_id,
                getattr(pr, "message", "") or audit_note,
            )
        return {
            "success": ok,
            "action": action,
            "message": getattr(pr, "message", "Rejected" if ok else "Reject failed"),
        }

    if action == "approve_override":
        chain = list(preferred_chain) if preferred_chain else None
        if chain is None and plan_index is not None:
            plans = diag.get("plans") or []
            idx = int(plan_index) - 1
            if 0 <= idx < len(plans):
                p = plans[idx]
                if p.get("chain"):
                    chain = [(int(a), int(b)) for a, b in p["chain"]]
                elif p.get("steps"):
                    chain = []
                    for s in p["steps"]:
                        o = s.get("original_officer_id") or s.get("original_id")
                        r = s.get("replacement_officer_id") or s.get("replacement_id")
                        if o is not None and r is not None:
                            chain.append((int(o), int(r)))
        if chain is None and cover_officer_id:
            chain = [(oid, int(cover_officer_id))]
        pr = process_day_off_request(
            request_id,
            action="approve",
            preferred_chain=chain,
            admin_notes=audit_note or "Supervisor override from ops desk",
            actor_user_id=user_id,
        )
        # Manual status allows override even without preferred chain
        if not getattr(pr, "success", False) and req.get("status") == _manual_status():
            pr = process_day_off_request(
                request_id,
                action="approve",
                preferred_chain=chain,
                admin_notes=audit_note or "Supervisor override (retry)",
                actor_user_id=user_id,
            )
        ok = bool(getattr(pr, "success", False))
        if user_id is not None:
            log_audit_action(
                user_id,
                "manual_review_approve_override",
                "day_off_requests",
                request_id,
                getattr(pr, "message", "") or audit_note,
            )
        return {
            "success": ok,
            "action": action,
            "message": getattr(pr, "message", "Approved" if ok else "Approve failed"),
            "requires_manual": bool(getattr(pr, "requires_manual", False)),
        }

    if action in ("order_in", "partial_cover"):
        if not cover_officer_id:
            # Default: first eligible on ladder
            eligible = (diag.get("callout") or {}).get("eligible") or []
            if not eligible:
                return {"success": False, "message": "No eligible callout candidates"}
            cover_officer_id = int(eligible[0]["officer_id"])
        # Prefer leave approve with chain (keeps accrual + live sync)
        chain = [(oid, int(cover_officer_id))]
        pr = process_day_off_request(
            request_id,
            action="approve",
            preferred_chain=chain,
            admin_notes=audit_note or f"Order-in cover #{cover_officer_id}",
            actor_user_id=user_id,
        )
        if getattr(pr, "success", False):
            try:
                from logic.ot_equity_ledger import record_ot_offer, record_ot_worked
                from logic.ot_fill import EVENT_PARTIAL_COVER, record_ordered_in, record_ot_fill_event

                if action == "partial_cover" or is_partial:
                    record_ot_fill_event(
                        int(cover_officer_id),
                        rdate,
                        EVENT_PARTIAL_COVER,
                        request_id=request_id,
                        hours=float(hours),
                        is_partial=True,
                        is_ordered=True,
                        notes=audit_note,
                        user_id=user_id,
                        update_call_list=True,
                    )
                else:
                    record_ordered_in(
                        int(cover_officer_id),
                        rdate,
                        request_id=request_id,
                        hours=float(hours),
                        notes=audit_note,
                        user_id=user_id,
                    )
                record_ot_offer(
                    int(cover_officer_id),
                    float(hours),
                    event_date=rdate,
                    source="manual_review",
                    source_id=request_id,
                    user_id=user_id,
                )
                record_ot_worked(
                    int(cover_officer_id),
                    float(hours),
                    event_date=rdate,
                    source="manual_review",
                    source_id=request_id,
                    user_id=user_id,
                )
            except Exception:
                pass
            if user_id is not None:
                log_audit_action(
                    user_id,
                    "manual_review_order_in",
                    "day_off_requests",
                    request_id,
                    getattr(pr, "message", ""),
                )
            return {
                "success": True,
                "action": action,
                "message": getattr(pr, "message", "Ordered in and approved"),
                "cover_officer_id": int(cover_officer_id),
            }
        # Fallback callout without re-creating leave
        cr = execute_callout_order(
            oid,
            rdate,
            int(cover_officer_id),
            reason=req.get("request_type") or "Sick",
            hours=float(hours),
            is_partial=bool(is_partial or action == "partial_cover"),
            create_leave_request=False,
            user_id=user_id,
            notes=audit_note,
        )
        if cr.get("success"):
            # Still try approve
            pr2 = process_day_off_request(
                request_id,
                action="approve",
                preferred_chain=chain,
                admin_notes=audit_note,
                actor_user_id=user_id,
            )
            return {
                "success": bool(getattr(pr2, "success", False) or cr.get("success")),
                "action": action,
                "message": getattr(pr2, "message", None) or cr.get("message"),
                "cover_officer_id": int(cover_officer_id),
            }
        return {
            "success": False,
            "action": action,
            "message": getattr(pr, "message", None) or cr.get("message") or "Order-in failed",
        }

    if action == "open_shift":
        try:
            from logic.operations import create_open_shift

            officer = diag.get("officer") or {}
            start = officer.get("shift_start") or req.get("shift_start") or "06:00"
            end = req.get("shift_end") or officer.get("shift_end") or ""
            if not end:
                try:
                    from logic.shift_assignment import shift_end_for_start

                    end = shift_end_for_start(start) or "14:00"
                except Exception:
                    end = "14:00"
            osr = create_open_shift(
                rdate,
                start,
                end,
                squad=officer.get("squad") or req.get("squad"),
                notes=f"Manual review leave #{request_id}: {req.get('officer_name') or oid}",
                user_id=user_id,
            )
            if user_id is not None:
                log_audit_action(
                    user_id,
                    "manual_review_open_shift",
                    "day_off_requests",
                    request_id,
                    osr.get("message") or "open shift posted",
                )
            return {
                "success": bool(osr.get("success")),
                "action": action,
                "message": osr.get("message") or ("Open shift posted" if osr.get("success") else "Failed"),
                "open_shift": osr,
                "note": "Leave remains in manual review until filled or resolved",
            }
        except Exception as exc:
            return {"success": False, "action": action, "message": str(exc)}

    return {"success": False, "message": f"Unknown action: {action}"}


def get_ops_desk_board(*, reference: Optional[date] = None) -> Dict[str, Any]:
    """Single board: gaps · pending leave · manual review · open shifts · OT call list · notify."""
    ref = reference or date.today()
    from logic.callout_desk import list_today_vacancies
    from logic.notify_queue import notify_outbox_stats
    from logic.requests import get_day_off_requests, get_pending_shift_swap_requests

    vac = list_today_vacancies(reference=ref)
    manual = list_manual_review_queue()
    pending = get_day_off_requests(status_filter=_pending_status()) or []
    swaps = []
    try:
        swaps = get_pending_shift_swap_requests() or []
    except Exception:
        swaps = []

    open_shifts = []
    try:
        from logic.operations import get_open_shifts

        open_shifts = get_open_shifts(status="open") or get_open_shifts() or []
        if isinstance(open_shifts, dict):
            open_shifts = open_shifts.get("shifts") or open_shifts.get("items") or []
    except Exception:
        open_shifts = []

    outbox = {}
    try:
        outbox = notify_outbox_stats() or {}
    except Exception:
        outbox = {}

    flsa_banner = []
    try:
        from logic.payroll_exceptions import flsa_period_banners

        flsa_banner = flsa_period_banners(reference=ref) or []
    except Exception:
        flsa_banner = []

    exceptions = []
    try:
        from logic.payroll_exceptions import list_payroll_exceptions

        pe = list_payroll_exceptions(reference=ref)
        exceptions = pe.get("items") or []
    except Exception:
        exceptions = []

    stations = {}
    try:
        from logic.stations import station_staffing_board

        stations = station_staffing_board() or {}
    except Exception:
        stations = {"success": False, "understaffed_count": 0, "understaffed": []}

    fatigue = {}
    try:
        from logic.fatigue_gates import fatigue_watchlist

        fatigue = fatigue_watchlist(limit=8) or {}
    except Exception:
        fatigue = {"success": False, "count": 0, "items": []}

    return {
        "success": True,
        "reference": storage_date(ref),
        "date_display": format_date(ref),
        "manual_review": manual.get("items") or [],
        "manual_count": manual.get("count") or 0,
        "pending_leave": pending,
        "pending_count": len(pending),
        "same_day_leave": vac.get("same_day_leave") or [],
        "gaps": vac.get("gaps") or [],
        "gap_count": vac.get("gap_count") or 0,
        "open_shifts": open_shifts if isinstance(open_shifts, list) else [],
        "pending_swaps": swaps,
        "notify_outbox": outbox,
        "flsa_banners": flsa_banner,
        "payroll_exceptions": exceptions,
        "station_board": stations,
        "fatigue_watch": fatigue,
        "kpi": {
            "manual_review": manual.get("count") or 0,
            "pending_leave": len(pending),
            "gaps": vac.get("gap_count") or 0,
            "open_shifts": len(open_shifts) if isinstance(open_shifts, list) else 0,
            "swaps": len(swaps),
            "outbox_queued": (outbox.get("by_status") or {}).get("queued", 0),
            "payroll_exceptions": len(exceptions),
            "station_under": int(stations.get("understaffed_count") or 0),
            "fatigue_flags": int(fatigue.get("count") or 0),
        },
    }
