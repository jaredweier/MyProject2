"""CAD vendor adapters — Mark43 / Tyler-style normalize → Chronos cover rows.

Not a certified vendor product integration; transforms common payload shapes so
inbound/outbound can speak vendor-ish JSON while Chronos stays system of record.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def detect_cad_vendor(payload: Dict[str, Any]) -> str:
    """Heuristic vendor tag from payload keys / headers."""
    if not isinstance(payload, dict):
        return "generic"
    explicit = (payload.get("vendor") or payload.get("source_system") or payload.get("system") or "").strip().lower()
    if "mark43" in explicit or explicit in ("m43", "mark-43"):
        return "mark43"
    if "tyler" in explicit or "new world" in explicit or explicit in ("nws", "enterprisecad"):
        return "tyler"
    # Shape heuristics
    if any(k in payload for k in ("units", "unitStatuses", "cadUnits")):
        return "mark43"
    if any(k in payload for k in ("UnitAssignments", "CADEvents", "PersonnelAssignments")):
        return "tyler"
    if payload.get("rows") or payload.get("covers") or payload.get("duty"):
        return "generic"
    return "generic"


def _row_from_pair(
    *,
    date: Any,
    original: Any,
    replacement: Any = None,
    reason: str = "",
    extra: Optional[Dict] = None,
) -> Dict[str, Any]:
    r: Dict[str, Any] = {
        "date": date,
        "original_officer_id": original,
        "replacement_officer_id": replacement,
        "reason": reason or "CAD vendor import",
    }
    if extra:
        r.update({k: v for k, v in extra.items() if k not in r})
    return r


def normalize_mark43_payload(payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Mark43-style: units[] with officerId / coveringOfficerId / dutyDate."""
    rows: List[Dict[str, Any]] = []
    units = payload.get("units") or payload.get("unitStatuses") or payload.get("cadUnits") or []
    if isinstance(units, dict):
        units = list(units.values())
    for u in units if isinstance(units, list) else []:
        if not isinstance(u, dict):
            continue
        d = u.get("dutyDate") or u.get("date") or u.get("shiftDate") or payload.get("asOf")
        orig = u.get("officerId") or u.get("absentOfficerId") or u.get("primaryOfficerId")
        rep = u.get("coveringOfficerId") or u.get("replacementOfficerId") or u.get("coverOfficerId")
        if orig is None and u.get("personnel"):
            # nested personnel list
            for p in u.get("personnel") or []:
                if not isinstance(p, dict):
                    continue
                rows.append(
                    _row_from_pair(
                        date=d or p.get("date"),
                        original=p.get("officerId") or p.get("id"),
                        replacement=p.get("coverOfficerId"),
                        reason=str(u.get("status") or p.get("status") or "Mark43 unit"),
                        extra={"vendor": "mark43", "unit_id": u.get("id") or u.get("unitId")},
                    )
                )
            continue
        rows.append(
            _row_from_pair(
                date=d,
                original=orig,
                replacement=rep,
                reason=str(u.get("status") or u.get("disposition") or "Mark43 unit"),
                extra={"vendor": "mark43", "unit_id": u.get("id") or u.get("unitId")},
            )
        )
    # Also accept already-normalized rows inside mark43 wrapper
    for r in payload.get("rows") or []:
        if isinstance(r, dict):
            r = dict(r)
            r.setdefault("vendor", "mark43")
            rows.append(r)
    meta = {"vendor": "mark43", "unit_count": len(units) if isinstance(units, list) else 0}
    return rows, meta


def normalize_tyler_payload(payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Tyler / New World-style: UnitAssignments or PersonnelAssignments."""
    rows: List[Dict[str, Any]] = []
    blocks = (
        payload.get("UnitAssignments")
        or payload.get("PersonnelAssignments")
        or payload.get("assignments")
        or payload.get("CADEvents")
        or []
    )
    if isinstance(blocks, dict):
        blocks = list(blocks.values())
    for b in blocks if isinstance(blocks, list) else []:
        if not isinstance(b, dict):
            continue
        d = b.get("DutyDate") or b.get("EventDate") or b.get("date") or b.get("shift_date")
        orig = b.get("AbsentEmployeeId") or b.get("OfficerId") or b.get("EmployeeId") or b.get("original_officer_id")
        rep = b.get("CoveringEmployeeId") or b.get("ReplacementId") or b.get("replacement_officer_id")
        rows.append(
            _row_from_pair(
                date=d,
                original=orig,
                replacement=rep,
                reason=str(b.get("Reason") or b.get("EventType") or "Tyler CAD"),
                extra={"vendor": "tyler", "event_id": b.get("EventId") or b.get("id")},
            )
        )
    for r in payload.get("rows") or []:
        if isinstance(r, dict):
            r = dict(r)
            r.setdefault("vendor", "tyler")
            rows.append(r)
    meta = {"vendor": "tyler", "assignment_count": len(blocks) if isinstance(blocks, list) else 0}
    return rows, meta


def normalize_generic_payload(payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    rows = payload.get("rows") or payload.get("duty") or payload.get("assignments") or payload.get("covers") or []
    if not isinstance(rows, list):
        rows = []
    clean = [r for r in rows if isinstance(r, dict)]
    return clean, {"vendor": "generic", "row_count": len(clean)}


def normalize_cad_payload(payload: Dict[str, Any], *, vendor: str = "") -> Dict[str, Any]:
    """Return {vendor, rows, meta} in Chronos cover-pair shape."""
    if not isinstance(payload, dict):
        return {"vendor": "unknown", "rows": [], "meta": {}, "success": False, "message": "payload not object"}
    v = (vendor or detect_cad_vendor(payload) or "generic").lower()
    if v == "mark43":
        rows, meta = normalize_mark43_payload(payload)
    elif v == "tyler":
        rows, meta = normalize_tyler_payload(payload)
    else:
        rows, meta = normalize_generic_payload(payload)
        # try vendor shapes if generic empty
        if not rows:
            m43, meta43 = normalize_mark43_payload(payload)
            if m43:
                rows, meta, v = m43, meta43, "mark43"
            else:
                ty, metaty = normalize_tyler_payload(payload)
                if ty:
                    rows, meta, v = ty, metaty, "tyler"
    return {
        "success": True,
        "vendor": v,
        "rows": rows,
        "meta": meta,
        "message": f"Normalized {len(rows)} row(s) as {v}",
    }


def export_duty_for_vendor(duty_rows: List[Dict[str, Any]], *, vendor: str = "generic") -> Dict[str, Any]:
    """Outbound shape for webhook/pull consumers."""
    v = (vendor or "generic").lower()
    if v == "mark43":
        units = []
        for r in duty_rows or []:
            if not isinstance(r, dict):
                continue
            units.append(
                {
                    "dutyDate": r.get("date") or r.get("shift_date"),
                    "officerId": r.get("officer_id") or r.get("original_officer_id"),
                    "coveringOfficerId": r.get("replacement_officer_id") or r.get("cover_officer_id"),
                    "status": r.get("status") or "assigned",
                    "unitId": r.get("unit_id"),
                }
            )
        return {"vendor": "mark43", "units": units, "row_count": len(units)}
    if v == "tyler":
        assigns = []
        for r in duty_rows or []:
            if not isinstance(r, dict):
                continue
            assigns.append(
                {
                    "DutyDate": r.get("date") or r.get("shift_date"),
                    "OfficerId": r.get("officer_id") or r.get("original_officer_id"),
                    "CoveringEmployeeId": r.get("replacement_officer_id"),
                    "Reason": r.get("reason") or r.get("status") or "Chronos export",
                }
            )
        return {"vendor": "tyler", "UnitAssignments": assigns, "row_count": len(assigns)}
    return {"vendor": "generic", "rows": list(duty_rows or []), "row_count": len(duty_rows or [])}
