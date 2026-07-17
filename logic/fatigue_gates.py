"""Hard fatigue / rest gates with audited supervisor override."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def rest_fatigue_hard_stops_enabled() -> bool:
    from logic.operations import get_department_setting

    raw = (get_department_setting("rest_hard_stop_enabled", "1") or "1").strip().lower()
    return raw in ("1", "true", "yes", "on")


def fatigue_watchlist(*, limit: int = 10, min_score: Optional[float] = None) -> Dict[str, Any]:
    """Rank active officers by fatigue score for ops wellness strip (LE rest best practice).

    Soft board only — does not hard-block. Hard blocks use check_rest_hard_stop.
    """
    try:
        from logic.labor_compliance import compute_fatigue_score, get_fatigue_score_threshold
        from logic.officers import get_officers_by_seniority
    except Exception as exc:
        return {"success": False, "items": [], "message": str(exc)}

    try:
        thr = float(get_fatigue_score_threshold())
    except Exception:
        thr = 70.0
    floor = float(min_score) if min_score is not None else max(0.0, thr * 0.75)

    items: List[Dict[str, Any]] = []
    for o in get_officers_by_seniority() or []:
        if not o.get("active", 1):
            continue
        try:
            fs = compute_fatigue_score(int(o["id"])) or {}
        except Exception:
            continue
        score = float(fs.get("score") or 0)
        if score < floor:
            continue
        factors = fs.get("factors") or {}
        level = "critical" if score >= thr else "warning"
        items.append(
            {
                "officer_id": int(o["id"]),
                "name": o.get("name") or f"#{o['id']}",
                "squad": o.get("squad") or "",
                "score": round(score, 1),
                "threshold": thr,
                "level": level,
                "consecutive_days": factors.get("consecutive_days"),
                "weekly_hours": factors.get("weekly_hours"),
                "message": fs.get("message") or f"{o.get('name')}: fatigue {score:.0f}/{thr:.0f}",
            }
        )
    items.sort(key=lambda x: (-float(x["score"]), str(x.get("name") or "")))
    cap = max(1, min(50, int(limit or 10)))
    hot = items[:cap]
    return {
        "success": True,
        "threshold": thr,
        "min_score": floor,
        "count": len(hot),
        "total_flagged": len(items),
        "items": hot,
        "message": (
            f"{len(items)} officer(s) at/above fatigue floor {floor:.0f}"
            if items
            else f"No officers above fatigue floor {floor:.0f}"
        ),
    }


def check_rest_hard_stop(
    officer_id: int,
    *,
    work_date: str,
    shift_start: Optional[str] = None,
    shift_end: Optional[str] = None,
    override: bool = False,
    override_reason: str = "",
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Block assignment when min rest violated unless override with reason."""
    from config import MIN_REST_HOURS_BETWEEN_SHIFTS
    from logic.operations import get_department_setting

    try:
        min_rest = float(
            get_department_setting("min_rest_hours_between_shifts", str(MIN_REST_HOURS_BETWEEN_SHIFTS))
            or MIN_REST_HOURS_BETWEEN_SHIFTS
        )
    except (TypeError, ValueError):
        min_rest = float(MIN_REST_HOURS_BETWEEN_SHIFTS)

    # Prefer existing validator if present
    violation = None
    try:
        from validators import validate_minimum_rest_gap

        vr = validate_minimum_rest_gap(
            officer_id,
            work_date,
            shift_start=shift_start,
            shift_end=shift_end,
            min_hours=min_rest,
        )
        if isinstance(vr, dict) and not vr.get("ok", vr.get("success", True)):
            violation = vr.get("message") or "Minimum rest gap violated"
        elif isinstance(vr, tuple) and len(vr) >= 2 and not vr[0]:
            violation = str(vr[1])
        elif isinstance(vr, str) and vr:
            violation = vr
    except Exception:
        # Soft fallback: fatigue score threshold
        try:
            from logic.labor_compliance import compute_fatigue_score, get_fatigue_score_threshold

            fs = compute_fatigue_score(int(officer_id))
            score = float(fs.get("score") or 0)
            thr = float(get_fatigue_score_threshold())
            if score >= thr:
                violation = f"Fatigue score {score:.0f} ≥ threshold {thr:.0f}"
        except Exception:
            pass

    if not violation:
        return {"success": True, "blocked": False, "message": "Rest/fatigue OK"}

    if not rest_fatigue_hard_stops_enabled():
        return {
            "success": True,
            "blocked": False,
            "warning": violation,
            "message": f"Warning only (hard stop off): {violation}",
        }

    if override:
        reason = (override_reason or "").strip()
        if len(reason) < 3:
            return {
                "success": False,
                "blocked": True,
                "message": "Override requires a reason (min 3 characters)",
            }
        try:
            from logic.users import log_audit_action

            log_audit_action(
                "fatigue.rest_override",
                "officer",
                int(officer_id),
                user_id,
                f"date={work_date} reason={reason[:160]} violation={violation[:80]}",
            )
        except Exception:
            pass
        return {
            "success": True,
            "blocked": False,
            "overridden": True,
            "message": f"Override accepted: {violation}",
            "violation": violation,
        }

    return {
        "success": False,
        "blocked": True,
        "message": violation,
        "violation": violation,
        "requires_override": True,
    }
