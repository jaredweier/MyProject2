"""CAD / RMS boundary exports — WFM stays ownership of duty roster.

Does not implement CAD. Exports duty snapshot + optional webhook POST for
Mark43 / Tyler / CivicEye-class integration later.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from paths import data_path


def export_duty_roster_for_cad(
    *,
    as_of: Optional[date] = None,
    days: int = 1,
) -> Dict[str, Any]:
    """JSON + CSV duty roster for CAD/RMS import."""
    from logic.officers import get_officers_by_seniority
    from logic.snapshots import get_officer_schedule_window

    as_of = as_of or date.today()
    days = max(1, min(int(days or 1), 14))
    officers = get_officers_by_seniority() or []
    rows: List[Dict[str, Any]] = []
    for o in officers:
        if not o.get("active", 1):
            continue
        oid = o.get("id")
        if not oid:
            continue
        try:
            window = get_officer_schedule_window(int(oid), start_date=as_of, days=days) or {}
        except Exception:
            window = {}
        days_map = window.get("days") or window.get("schedule") or window.get("schedule_days") or []
        if isinstance(days_map, list):
            for d in days_map:
                if isinstance(d, dict):
                    rows.append(
                        {
                            "officer_id": oid,
                            "officer_name": o.get("name"),
                            "badge": o.get("badge") or o.get("badge_number"),
                            "squad": o.get("squad"),
                            "station": o.get("station"),
                            "workforce_class": o.get("workforce_class") or "sworn",
                            "date": d.get("date"),
                            "status": d.get("status"),
                            "shift_start": d.get("shift_start"),
                            "shift_end": d.get("shift_end"),
                            "duty": d.get("duty") or d.get("status"),
                        }
                    )
        elif isinstance(days_map, dict):
            for dkey, dval in days_map.items():
                if isinstance(dval, dict):
                    rows.append(
                        {
                            "officer_id": oid,
                            "officer_name": o.get("name"),
                            "squad": o.get("squad"),
                            "station": o.get("station"),
                            "date": dkey,
                            **dval,
                        }
                    )
                else:
                    rows.append(
                        {
                            "officer_id": oid,
                            "officer_name": o.get("name"),
                            "squad": o.get("squad"),
                            "station": o.get("station"),
                            "date": dkey,
                            "duty": dval,
                        }
                    )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(data_path("exports"))
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "product": "Chronos Command",
        "vendor": "Weierworks Technologies, LLC",
        "export_type": "duty_roster_cad",
        "as_of": as_of.isoformat(),
        "days": days,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "rows": rows,
    }
    jpath = out_dir / f"cad_duty_roster_{stamp}.json"
    jpath.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    cpath = out_dir / f"cad_duty_roster_{stamp}.csv"
    headers = ["officer_id", "officer_name", "squad", "station", "date", "status", "shift_start", "shift_end", "duty"]
    lines = [",".join(headers)]
    for r in rows:
        lines.append(",".join(str(r.get(h, "") or "").replace(",", " ") for h in headers))
    cpath.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "success": True,
        "json_path": str(jpath),
        "csv_path": str(cpath),
        "count": len(rows),
        "message": f"Exported {len(rows)} duty rows for CAD/RMS",
    }


def post_cad_webhook(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Optional webhook — set SCHEDULER_CAD_WEBHOOK_URL. Never raises."""
    url = (os.environ.get("SCHEDULER_CAD_WEBHOOK_URL") or "").strip()
    if not url:
        return {"success": True, "sent": False, "message": "No SCHEDULER_CAD_WEBHOOK_URL configured"}
    if payload is None:
        exp = export_duty_roster_for_cad(days=1)
        if not exp.get("success"):
            return exp
        try:
            payload = json.loads(Path(exp["json_path"]).read_text(encoding="utf-8"))
        except Exception as exc:
            return {"success": False, "message": str(exc)[:200]}
    try:
        import urllib.request

        data = json.dumps(payload, default=str).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "ChronosCommand/CAD"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return {"success": True, "sent": True, "http_status": resp.status}
    except Exception as exc:
        return {"success": False, "sent": False, "message": str(exc)[:200]}
