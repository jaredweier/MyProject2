"""Same-day callout / sick-day vacancy desk.

Separate from planned vacation bump: builds an ordered call list using
OT fill mode + optional OT equity sort + fatigue hard stops + cert gates.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from logic.operations import get_department_setting, set_department_setting
from logic.users import log_audit_action
from validators import format_date, parse_date, storage_date

SETTING_OT_EQUITY_SORT = "ot_equity_sort_on_callout"


def get_ot_equity_sort_enabled() -> bool:
    raw = (get_department_setting(SETTING_OT_EQUITY_SORT, "1") or "1").strip().lower()
    return raw in ("1", "true", "yes", "on")


def set_ot_equity_sort_enabled(enabled: bool, *, user_id: Optional[int] = None) -> Dict:
    r = set_department_setting(SETTING_OT_EQUITY_SORT, "1" if enabled else "0", user_id=user_id)
    if not r.get("success"):
        return r
    return {
        "success": True,
        "enabled": bool(enabled),
        "message": f"OT equity sort on callout: {'ON' if enabled else 'OFF'}",
    }


def _equity_hours_map() -> Dict[int, float]:
    """Net offered−worked (or offered) for sort: lower equity first = fair next call."""
    try:
        from logic.ot_equity_ledger import get_ot_equity_summary

        summary = get_ot_equity_summary() or {}
        rows = summary.get("rows") or summary.get("officers") or summary.get("ledger") or []
        out: Dict[int, float] = {}
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                oid = row.get("officer_id") or row.get("id")
                if oid is None:
                    continue
                offered = float(row.get("hours_offered") or row.get("offered_hours") or row.get("offered") or 0)
                worked = float(row.get("hours_worked") or row.get("worked_hours") or row.get("worked") or 0)
                # Lower net (offered−worked) → next fair call
                out[int(oid)] = offered - worked
        return out
    except Exception:
        return {}


def build_callout_ladder(
    original_officer_id: int,
    event_date: str,
    *,
    squad: Optional[str] = None,
    shift_start: Optional[str] = None,
    reason: str = "Sick",
    include_fatigue: bool = True,
    use_ot_equity: Optional[bool] = None,
) -> Dict[str, Any]:
    """Ranked call list for same-day vacancy."""
    from logic.officers import get_officer_by_id
    from logic.ot_fill import list_ot_fill_candidates

    try:
        d = parse_date(event_date)
    except ValueError as exc:
        return {"success": False, "message": str(exc), "candidates": []}

    original = get_officer_by_id(original_officer_id)
    if not original:
        return {"success": False, "message": "Officer not found", "candidates": []}

    squad = squad or original.get("squad") or "A"
    shift_start = shift_start or original.get("shift_start") or "06:00"
    ds = storage_date(d)
    fill = list_ot_fill_candidates(
        original_officer_id,
        ds,
        squad,
        shift_start,
        include_year_stats=True,
    )
    if not fill.get("success"):
        return {
            "success": False,
            "message": fill.get("message") or "Could not build candidates",
            "candidates": [],
        }

    candidates = list(fill.get("candidates") or [])
    equity_on = get_ot_equity_sort_enabled() if use_ot_equity is None else bool(use_ot_equity)
    equity = _equity_hours_map() if equity_on else {}

    # Fatigue filter
    if include_fatigue:
        try:
            from logic.fatigue_gates import check_rest_hard_stop

            for c in candidates:
                oid = c.get("officer_id")
                if oid is None or c.get("ineligible_for_order"):
                    continue
                stop = check_rest_hard_stop(int(oid), work_date=ds, shift_start=shift_start)
                if stop and (stop.get("blocked") or stop.get("hard_stop") or not stop.get("ok", True)):
                    if stop.get("blocked") or stop.get("hard_stop") or stop.get("severity") == "block":
                        c["ineligible_for_order"] = True
                        c["fatigue_blocked"] = True
                        c["fill_hint"] = (c.get("fill_hint") or "") + " · fatigue hard stop"
                        c["fatigue_message"] = stop.get("message") or "Rest/fatigue block"
        except Exception:
            pass

    # Cert soft flag
    try:
        from logic.certifications import officer_meets_shift_cert_requirements

        for c in candidates:
            oid = c.get("officer_id")
            if oid is None:
                continue
            ok, msg = officer_meets_shift_cert_requirements(int(oid), shift_start)
            if not ok:
                c["cert_warning"] = msg or True
                c["fill_hint"] = (c.get("fill_hint") or "") + " · cert gap"
    except Exception:
        pass

    eligible = [c for c in candidates if not c.get("ineligible_for_order")]
    ineligible = [c for c in candidates if c.get("ineligible_for_order")]

    if equity_on and equity:

        def sort_key(c: Dict) -> tuple:
            oid = int(c.get("officer_id") or 0)
            return (
                float(equity.get(oid, 0.0)),
                int(c.get("seniority_rank") or 9999),
                oid,
            )

        eligible = sorted(eligible, key=sort_key)
        for i, c in enumerate(eligible, 1):
            c["offer_order"] = i
            c["equity_net_hours"] = equity.get(int(c.get("officer_id") or 0), 0.0)

    lines = [
        f"Callout ladder · {reason} · {original.get('name')} · {format_date(d)} · {squad} {shift_start}",
        f"Mode: {fill.get('mode_label') or fill.get('mode') or '—'}"
        + (" · OT equity sort ON" if equity_on else " · OT equity sort OFF"),
        f"Eligible: {len(eligible)} · Ineligible: {len(ineligible)}",
        "",
    ]
    for c in eligible[:20]:
        duty = "ON" if c.get("on_duty") else "OFF"
        eq = c.get("equity_net_hours")
        eq_s = f" · equity {eq:g}h" if eq is not None else ""
        lines.append(
            f"  #{c.get('offer_order', '?')} {c.get('name')} · {duty} · rank {c.get('seniority_rank', '—')}{eq_s}"
        )
        if c.get("fill_hint"):
            lines.append(f"      {c['fill_hint']}")

    return {
        "success": True,
        "original_officer_id": original_officer_id,
        "original_name": original.get("name"),
        "event_date": ds,
        "date_display": format_date(d),
        "squad": squad,
        "shift_start": shift_start,
        "reason": reason,
        "mode": fill.get("mode"),
        "mode_label": fill.get("mode_label"),
        "ot_equity_sort": equity_on,
        "candidates": eligible + ineligible,
        "eligible": eligible,
        "ineligible": ineligible,
        "text": "\n".join(lines),
        "message": f"{len(eligible)} eligible callout candidate(s)",
    }


def execute_callout_order(
    original_officer_id: int,
    event_date: str,
    cover_officer_id: int,
    *,
    squad: Optional[str] = None,
    shift_start: Optional[str] = None,
    reason: str = "Sick",
    hours: float = 8.0,
    is_partial: bool = False,
    create_leave_request: bool = True,
    user_id: Optional[int] = None,
    notes: str = "",
) -> Dict[str, Any]:
    """Order-in cover + optional sick leave request + OT equity + open-shift-style override."""
    from logic.officers import get_officer_by_id
    from logic.ot_equity_ledger import record_ot_offer, record_ot_worked
    from logic.snapshots import create_manual_coverage_override

    try:
        d = parse_date(event_date)
    except ValueError as exc:
        return {"success": False, "message": str(exc)}

    original = get_officer_by_id(original_officer_id)
    cover = get_officer_by_id(cover_officer_id)
    if not original or not cover:
        return {"success": False, "message": "Officer not found"}

    squad = squad or original.get("squad") or "A"
    shift_start = shift_start or original.get("shift_start") or "06:00"
    ds = storage_date(d)

    # Fatigue hard stop
    try:
        from logic.fatigue_gates import check_rest_hard_stop

        stop = check_rest_hard_stop(int(cover_officer_id), work_date=ds, shift_start=shift_start)
        if stop and (stop.get("blocked") or stop.get("hard_stop")):
            return {
                "success": False,
                "message": stop.get("message") or "Cover blocked by rest/fatigue policy",
                "fatigue_blocked": True,
            }
    except Exception:
        pass

    leave_id = None
    if create_leave_request:
        from logic.requests import create_day_off_request, process_day_off_request

        rtype = reason if reason in ("Sick", "Emergency", "Personal", "Vacation", "Other") else "Sick"
        cr = create_day_off_request(
            original_officer_id,
            ds,
            rtype,
            notes=notes or f"Same-day callout: {reason}",
        )
        if cr.get("success") and cr.get("request_id"):
            leave_id = int(cr["request_id"])
            # Approve with preferred cover chain (single hop)
            pr = process_day_off_request(
                leave_id,
                action="approve",
                preferred_chain=[(original_officer_id, cover_officer_id)],
                admin_notes=notes or f"Callout ordered: {cover.get('name')}",
                actor_user_id=user_id,
            )
            if not getattr(pr, "success", False):
                # Fall back to manual override if leave path can't auto-approve
                ov = create_manual_coverage_override(
                    original_officer_id,
                    cover_officer_id,
                    ds,
                    reason=f"Callout {reason}: {notes or cover.get('name')}",
                    actor_user_id=user_id,
                )
                if not ov.get("success"):
                    return {
                        "success": False,
                        "message": getattr(pr, "message", None) or ov.get("message") or "Could not place coverage",
                        "leave_request_id": leave_id,
                    }
        else:
            # Duplicate request etc. — still place override
            ov = create_manual_coverage_override(
                original_officer_id,
                cover_officer_id,
                ds,
                reason=f"Callout {reason}: {notes or cover.get('name')}",
                actor_user_id=user_id,
            )
            if not ov.get("success"):
                return {
                    "success": False,
                    "message": cr.get("message") or ov.get("message") or "Callout failed",
                }

    # Record OT fill + equity
    try:
        from logic.ot_fill import record_ordered_in

        record_ordered_in(
            cover_officer_id,
            ds,
            request_id=leave_id,
            hours=float(hours),
            is_partial=is_partial,
            covered_shift_start=shift_start,
            notes=notes or reason,
            user_id=user_id,
        )
    except Exception:
        pass

    try:
        record_ot_offer(
            cover_officer_id,
            float(hours),
            event_date=ds,
            source="callout",
            source_id=leave_id,
            notes=f"Ordered for {original.get('name')} {reason}",
            user_id=user_id,
        )
        record_ot_worked(
            cover_officer_id,
            float(hours),
            event_date=ds,
            source="callout",
            source_id=leave_id,
            notes="Callout worked",
            user_id=user_id,
        )
    except Exception:
        pass

    # Notify outbox
    try:
        from logic.notify_queue import enqueue_notify

        body = f"You are ordered in for {original.get('name')} on {format_date(d)} ({shift_start}). Reason: {reason}."
        enqueue_notify(
            channel="sms",
            subject="Ordered in",
            body=body,
            recipient=str(cover.get("name") or cover_officer_id),
            officer_id=int(cover_officer_id),
            template_key="callout_order",
            user_id=user_id,
            meta={"cover_id": cover_officer_id, "original_id": original_officer_id, "date": ds},
        )
        enqueue_notify(
            channel="email",
            subject=f"Ordered in {format_date(d)}",
            body=body,
            recipient=str(cover.get("name") or cover_officer_id),
            officer_id=int(cover_officer_id),
            template_key="callout_order",
            user_id=user_id,
            meta={"cover_id": cover_officer_id, "original_id": original_officer_id, "date": ds},
        )
    except Exception:
        pass

    if user_id is not None:
        log_audit_action(
            user_id,
            "callout_order",
            "schedule_overrides",
            leave_id,
            f"{cover.get('name')} ordered for {original.get('name')} on {ds} ({reason})",
        )

    return {
        "success": True,
        "message": f"Ordered {cover.get('name')} for {original.get('name')} on {format_date(d)}",
        "leave_request_id": leave_id,
        "cover_officer_id": cover_officer_id,
        "original_officer_id": original_officer_id,
        "event_date": ds,
    }


def list_today_vacancies(*, reference: Optional[date] = None, hours_ahead: int = 48) -> Dict[str, Any]:
    """Combine coverage gap board + pending leave for ops desk."""
    ref = reference or date.today()
    gaps = []
    try:
        from logic.dashboard import get_coverage_gap_board

        board = get_coverage_gap_board(hours_ahead=hours_ahead) or {}
        gaps = board.get("gaps") or board.get("rows") or board.get("items") or []
        if not isinstance(gaps, list):
            gaps = []
    except Exception:
        gaps = []

    pending_leave = []
    try:
        from config import REQUEST_STATUS
        from logic.requests import get_day_off_requests

        for status in (
            REQUEST_STATUS.get("pending") or "Pending",
            REQUEST_STATUS.get("pending_manual") or "Pending Manual Review",
        ):
            pending_leave.extend(get_day_off_requests(status_filter=status) or [])
    except Exception:
        pass

    # Same-day focus
    today_s = storage_date(ref)
    same_day = [r for r in pending_leave if str(r.get("request_date") or "")[:10] == today_s[:10]]

    return {
        "success": True,
        "reference": today_s,
        "gaps": gaps,
        "pending_leave": pending_leave,
        "same_day_leave": same_day,
        "gap_count": len(gaps),
        "pending_count": len(pending_leave),
        "same_day_count": len(same_day),
    }
