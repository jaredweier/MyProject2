"""Monthly base publish contract — soft locks + cert warnings + diff."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import REQUEST_STATUS
from logic.operations import get_department_setting, set_department_setting
from logic.users import log_audit_action
from validators import format_date

SETTING_BLOCK_MANUAL = "publish_block_on_manual_review"


def get_publish_block_on_manual_review() -> bool:
    raw = (get_department_setting(SETTING_BLOCK_MANUAL, "1") or "1").strip().lower()
    return raw in ("1", "true", "yes", "on")


def set_publish_block_on_manual_review(enabled: bool, *, user_id: Optional[int] = None) -> Dict:
    r = set_department_setting(SETTING_BLOCK_MANUAL, "1" if enabled else "0", user_id=user_id)
    if not r.get("success"):
        return r
    return {
        "success": True,
        "enabled": bool(enabled),
        "message": f"Publish block on manual review: {'ON' if enabled else 'OFF'}",
    }


def _month_bounds(year: int, month: int):
    from calendar import monthrange
    from datetime import date

    last = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def unresolved_manual_reviews_in_month(year: int, month: int) -> List[Dict[str, Any]]:
    from logic.requests import get_day_off_requests

    start, end = _month_bounds(year, month)
    status = REQUEST_STATUS.get("pending_manual") or "Pending Manual Review"
    rows = get_day_off_requests(status_filter=status) or []
    out = []
    for r in rows:
        rd = str(r.get("request_date") or "")[:10]
        if not rd:
            continue
        try:
            from validators import parse_date

            d = parse_date(rd)
        except Exception:
            continue
        if start <= d <= end:
            out.append(r)
    return out


def cert_warnings_for_month(year: int, month: int) -> List[Dict[str, Any]]:
    """Officers with expired/missing certs (soft board for publish preflight)."""
    warnings: List[Dict[str, Any]] = []
    try:
        from logic.certifications import list_expiring_certifications

        exp = list_expiring_certifications(within_days=60) or []
        if isinstance(exp, dict):
            exp = exp.get("items") or exp.get("rows") or exp.get("certs") or []
        for row in exp or []:
            if isinstance(row, dict):
                warnings.append(row)
    except Exception:
        try:
            from logic.certifications import get_certification_alerts

            exp = get_certification_alerts() or []
            if isinstance(exp, dict):
                exp = exp.get("items") or exp.get("alerts") or []
            for row in exp or []:
                if isinstance(row, dict):
                    warnings.append(row)
        except Exception:
            pass
    return warnings


def preflight_publish_base_schedule(year: int, month: int) -> Dict[str, Any]:
    """Check before generate/publish original monthly."""
    from logic.snapshots import compare_base_updated_schedule, get_schedule_snapshot

    manual = unresolved_manual_reviews_in_month(year, month)
    certs = cert_warnings_for_month(year, month)
    block = get_publish_block_on_manual_review() and len(manual) > 0

    base = get_schedule_snapshot(year, month, "base")
    live = get_schedule_snapshot(year, month, "updated") or get_schedule_snapshot(year, month, "live")
    diff = {}
    try:
        diff = compare_base_updated_schedule(year, month) or {}
    except Exception as exc:
        diff = {"error": str(exc)}

    lines = [
        f"Publish preflight · {month:02d}/{year}",
        f"Base snapshot: {'exists' if base else 'none'} · Live: {'exists' if live else 'none'}",
        f"Unresolved manual review in month: {len(manual)}" + (" — BLOCKED" if block else " — OK"),
        f"Cert warnings: {len(certs)}",
    ]
    for r in manual[:8]:
        lines.append(
            f"  · Manual #{r.get('id')} {r.get('officer_name')} "
            f"{format_date(r['request_date']) if r.get('request_date') else r.get('request_date')}"
        )
    for c in certs[:8]:
        lines.append(
            f"  · Cert {c.get('officer_name') or c.get('officer_id')}: "
            f"{c.get('gaps') or c.get('cert_name') or c.get('message') or 'gap'}"
        )

    return {
        "success": True,
        "year": year,
        "month": month,
        "blocked": block,
        "block_on_manual_review": get_publish_block_on_manual_review(),
        "manual_reviews": manual,
        "manual_count": len(manual),
        "cert_warnings": certs,
        "cert_count": len(certs),
        "base_exists": bool(base),
        "live_exists": bool(live),
        "diff": diff,
        "text": "\n".join(lines),
        "message": (
            f"Publish blocked: {len(manual)} manual review(s) unresolved"
            if block
            else f"Ready · {len(manual)} manual · {len(certs)} cert warnings"
        ),
    }


def publish_base_schedule_gated(
    year: int,
    month: int,
    user_id: int,
    *,
    force: bool = False,
) -> Dict[str, Any]:
    """Publish/generate base month only if preflight passes (or force)."""
    from logic.snapshots import publish_base_schedule

    pre = preflight_publish_base_schedule(year, month)
    if pre.get("blocked") and not force:
        return {
            "success": False,
            "blocked": True,
            "message": pre.get("message"),
            "preflight": pre,
        }
    result = publish_base_schedule(year, month, user_id)
    result["preflight"] = pre
    if result.get("success") and user_id is not None:
        log_audit_action(
            user_id,
            "publish_base_gated",
            "schedule_snapshots",
            None,
            f"{year}-{month:02d} force={force} manual={pre.get('manual_count')}",
        )
    return result


def live_coverage_severity_for_window(start_date: str, end_date: str) -> Dict[str, Any]:
    """Per-day severity for Gantt strip: ok / warn / critical understaff."""
    from datetime import timedelta

    from logic.coverage_windows_store import get_coverage_247_minimum
    from logic.officers import get_officers_by_seniority
    from logic.scheduling import get_officer_day_status
    from validators import parse_date, storage_date

    try:
        start = parse_date(start_date)
        end = parse_date(end_date)
    except ValueError as exc:
        return {"success": False, "message": str(exc), "days": []}

    min_247 = int(get_coverage_247_minimum() or 1)
    officers = [o for o in (get_officers_by_seniority() or []) if o.get("active") == 1]
    days: List[Dict[str, Any]] = []
    d = start
    while d <= end:
        working = 0
        for off in officers:
            try:
                st = get_officer_day_status(int(off["id"]), d)
            except Exception:
                st = "off"
            if st in ("working", "covering", "swapped", "training"):
                working += 1
        severity = "ok"
        message = f"{working} working"
        if working < min_247:
            severity = "critical" if working == 0 else "warning"
            message = f"Understaffed: {working} working (min {min_247})"
        # Fri/Sat night risk flag (weekday 4=Fri, 5=Sat)
        if d.weekday() in (4, 5) and working < max(min_247, 2):
            severity = "critical" if working < 2 else severity
            message = f"Weekend risk: {working} working"
        days.append(
            {
                "date": storage_date(d),
                "date_display": format_date(d),
                "severity": severity,
                "message": message,
                "working": working,
            }
        )
        d += timedelta(days=1)

    critical = sum(1 for x in days if x["severity"] == "critical")
    warning = sum(1 for x in days if x["severity"] == "warning")
    return {
        "success": True,
        "days": days,
        "critical_count": critical,
        "warning_count": warning,
        "message": f"{critical} critical · {warning} warning · {len(days)} days",
    }
