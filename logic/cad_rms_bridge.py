"""CAD/RMS bidirectional bridge — Chronos remains system of record.

Outbound: export_duty_roster_for_cad + post_cad_webhook (cad_rms_export).
Inbound: receive payload → validate → store audit → optional apply cover rows.
Pull: GET from configured CAD URL.

Not a full Mark43/Tyler integration — honest boundary with apply path for cover pairs.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from paths import data_path
from validators import parse_date, storage_date_str

SETTING_CAD_PULL_URL = "cad_rms_pull_url"
SETTING_CAD_INBOUND_TOKEN = "cad_rms_inbound_token"
SETTING_CAD_APPLY_ON_IMPORT = "cad_rms_apply_on_import"


def _imports_dir() -> Path:
    d = Path(data_path("imports"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _audits_dir() -> Path:
    d = Path(data_path("cad_audits"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_cad_bridge_config() -> Dict[str, Any]:
    from logic.operations import get_department_setting

    pull = (get_department_setting(SETTING_CAD_PULL_URL, "") or "").strip()
    env_pull = (os.environ.get("SCHEDULER_CAD_PULL_URL") or "").strip()
    token = (get_department_setting(SETTING_CAD_INBOUND_TOKEN, "") or "").strip()
    env_token = (os.environ.get("SCHEDULER_CAD_INBOUND_TOKEN") or "").strip()
    apply_raw = (get_department_setting(SETTING_CAD_APPLY_ON_IMPORT, "0") or "0").strip().lower()
    return {
        "pull_url": pull or env_pull,
        "inbound_token_set": bool(token or env_token),
        "inbound_token": token or env_token,
        "apply_on_import": apply_raw in ("1", "true", "yes", "on"),
        "webhook_url_set": bool((os.environ.get("SCHEDULER_CAD_WEBHOOK_URL") or "").strip()),
        "message": "CAD bridge config loaded",
    }


def save_cad_bridge_config(
    *,
    pull_url: str = "",
    inbound_token: str = "",
    apply_on_import: bool = False,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    from logic.operations import set_department_setting

    set_department_setting(SETTING_CAD_PULL_URL, (pull_url or "").strip(), user_id=user_id)
    if (inbound_token or "").strip():
        set_department_setting(SETTING_CAD_INBOUND_TOKEN, inbound_token.strip(), user_id=user_id)
    set_department_setting(
        SETTING_CAD_APPLY_ON_IMPORT,
        "1" if apply_on_import else "0",
        user_id=user_id,
    )
    return {"success": True, "message": "CAD bridge settings saved", "config": get_cad_bridge_config()}


def _normalize_payload(data: Any) -> Dict[str, Any]:
    if isinstance(data, (str, Path)):
        p = Path(data)
        if p.is_file():
            data = json.loads(p.read_text(encoding="utf-8"))
        else:
            data = json.loads(str(data))
    if not isinstance(data, dict):
        raise ValueError("CAD payload must be a JSON object")
    return data


def _extract_rows(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract cover/duty rows — generic + Mark43/Tyler vendor adapters."""
    try:
        from logic.cad_vendors import normalize_cad_payload

        vendor = (data.get("vendor") or data.get("source_system") or "").strip()
        norm = normalize_cad_payload(data, vendor=vendor)
        rows = norm.get("rows") or []
        if rows:
            return [r for r in rows if isinstance(r, dict)]
    except Exception:
        pass
    rows = data.get("rows") or data.get("duty") or data.get("assignments") or data.get("covers") or []
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


def store_cad_inbound_audit(data: Dict[str, Any], *, source: str = "import") -> Dict[str, Any]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = _audits_dir() / f"cad_inbound_{source}_{stamp}.json"
    payload = {
        "received_at": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "product": "Chronos Command",
        "payload": data,
    }
    dest.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return {"success": True, "path": str(dest), "stamp": stamp}


def apply_cad_cover_rows(
    rows: List[Dict[str, Any]],
    *,
    user_id: Optional[int] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """Apply cover pairs from CAD: original_officer_id + replacement_officer_id + date.

    Rows without a replacement are stored as notes only (no auto open-shift spam).
    """
    from logic.snapshots import create_manual_coverage_override

    applied = []
    skipped = []
    failed = []
    for row in rows[: max(1, min(int(limit), 100))]:
        orig = row.get("original_officer_id") or row.get("absent_officer_id") or row.get("officer_id")
        rep = row.get("replacement_officer_id") or row.get("cover_officer_id") or row.get("covering_officer_id")
        draw = row.get("date") or row.get("override_date") or row.get("shift_date") or row.get("work_date")
        if not draw:
            skipped.append({"reason": "no_date", "row": {k: row.get(k) for k in list(row)[:6]}})
            continue
        try:
            d = parse_date(str(draw)) or date.fromisoformat(storage_date_str(str(draw)))
            d_s = storage_date_str(d.isoformat())
        except Exception:
            skipped.append({"reason": "bad_date", "date": draw})
            continue
        # Cover apply requires both IDs and they must differ
        if orig is None or rep is None:
            skipped.append(
                {
                    "reason": "no_cover_pair",
                    "date": d_s,
                    "note": "status-only rows are audited, not applied as overrides",
                }
            )
            continue
        try:
            oid, rid = int(orig), int(rep)
        except (TypeError, ValueError):
            failed.append({"reason": "bad_ids", "orig": orig, "rep": rep})
            continue
        if oid == rid:
            skipped.append({"reason": "same_officer", "officer_id": oid})
            continue
        reason = str(row.get("reason") or row.get("notes") or "CAD inbound cover")[:200]
        r = create_manual_coverage_override(oid, rid, d_s, reason=reason, actor_user_id=user_id)
        if r.get("success"):
            applied.append({"original": oid, "replacement": rid, "date": d_s})
        else:
            failed.append({"original": oid, "replacement": rid, "date": d_s, "message": r.get("message")})

    return {
        "success": True,
        "applied": applied,
        "skipped": skipped[:30],
        "failed": failed[:30],
        "message": f"CAD apply: {len(applied)} overrides · {len(skipped)} skipped · {len(failed)} failed",
    }


def import_cad_duty_bidirectional(
    path_or_json: Any,
    *,
    dry_run: bool = False,
    apply: Optional[bool] = None,
    user_id: Optional[int] = None,
    source: str = "import",
) -> Dict[str, Any]:
    """Validate + store inbound CAD duty; optionally apply cover pairs."""
    try:
        data = _normalize_payload(path_or_json)
    except Exception as exc:
        return {"success": False, "message": f"Invalid CAD payload: {exc}"}

    rows = _extract_rows(data)
    cfg = get_cad_bridge_config()
    do_apply = cfg["apply_on_import"] if apply is None else bool(apply)

    if dry_run:
        cover_pairs = sum(
            1
            for r in rows
            if (r.get("replacement_officer_id") or r.get("cover_officer_id"))
            and (r.get("original_officer_id") or r.get("absent_officer_id") or r.get("officer_id"))
        )
        return {
            "success": True,
            "dry_run": True,
            "row_count": len(rows),
            "cover_pair_count": cover_pairs,
            "would_apply": do_apply,
            "message": (
                f"Validated CAD inbound · {len(rows)} rows · {cover_pairs} cover pairs · "
                f"apply={'yes' if do_apply else 'no'} (dry-run)"
            ),
        }

    audit = store_cad_inbound_audit(data, source=source)
    # Always write imports copy
    imp = _imports_dir() / f"cad_import_{audit.get('stamp')}.json"
    imp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    apply_result = None
    if do_apply:
        apply_result = apply_cad_cover_rows(rows, user_id=user_id)

    try:
        from logic.users import log_audit_action

        log_audit_action(
            "cad.inbound",
            "cad_rms",
            None,
            user_id,
            f"rows={len(rows)} apply={do_apply} path={audit.get('path')}",
        )
    except Exception:
        pass

    return {
        "success": True,
        "dry_run": False,
        "row_count": len(rows),
        "audit_path": audit.get("path"),
        "import_path": str(imp),
        "applied": bool(do_apply),
        "apply_result": apply_result,
        "message": (
            f"CAD inbound stored · {len(rows)} rows"
            + (f" · {apply_result.get('message')}" if apply_result else " · apply off (audit only)")
        ),
    }


def receive_cad_inbound(
    payload: Any,
    *,
    token: str = "",
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """HTTP inbound entry — checks optional shared token."""
    cfg = get_cad_bridge_config()
    expected = (cfg.get("inbound_token") or "").strip()
    if expected and (token or "").strip() != expected:
        return {"success": False, "message": "Invalid CAD inbound token", "http_status": 401}
    return import_cad_duty_bidirectional(payload, dry_run=False, user_id=user_id, source="webhook")


def pull_cad_from_url(
    url: Optional[str] = None,
    *,
    dry_run: bool = False,
    apply: Optional[bool] = None,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Pull duty JSON from CAD/RMS HTTP endpoint (GET)."""
    cfg = get_cad_bridge_config()
    url = (url or cfg.get("pull_url") or "").strip()
    if not url:
        return {
            "success": False,
            "message": "No CAD pull URL — set Ops Reports CAD pull URL or SCHEDULER_CAD_PULL_URL",
        }
    try:
        import urllib.request

        req = urllib.request.Request(
            url,
            method="GET",
            headers={"Accept": "application/json", "User-Agent": "ChronosCommand/CAD-Pull"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
    except Exception as exc:
        return {"success": False, "message": f"CAD pull failed: {str(exc)[:200]}"}

    return import_cad_duty_bidirectional(
        data,
        dry_run=dry_run,
        apply=apply,
        user_id=user_id,
        source="pull",
    )


def cad_bidirectional_roundtrip_smoke(*, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Export → dry import → synthetic cover apply dry path (no live CAD required)."""
    from logic.cad_rms_export import export_duty_roster_for_cad
    from logic.officers import get_officers_by_seniority

    exp = export_duty_roster_for_cad(as_of=date(2026, 7, 10), days=1)
    if not exp.get("success"):
        return {"success": False, "message": f"export failed: {exp}"}

    dry = import_cad_duty_bidirectional(exp.get("json_path"), dry_run=True, source="roundtrip")
    if not dry.get("success"):
        return {"success": False, "message": f"dry import failed: {dry}"}

    # Synthetic cover-pair payload (apply dry via dry_run=True still counts pairs)
    offs = [o for o in (get_officers_by_seniority() or []) if o.get("active") == 1][:2]
    synth = {
        "export_type": "duty_roster_cad",
        "rows": exp.get("count") and json.loads(Path(exp["json_path"]).read_text(encoding="utf-8")).get("rows", [])[:3],
    }
    if len(offs) >= 2:
        synth["rows"] = list(synth.get("rows") or []) + [
            {
                "original_officer_id": int(offs[0]["id"]),
                "replacement_officer_id": int(offs[1]["id"]),
                "date": "2026-07-15",
                "reason": "CAD roundtrip smoke cover",
            }
        ]
    dry2 = import_cad_duty_bidirectional(synth, dry_run=True, apply=True, source="roundtrip_synth")
    # Real store without apply (safe)
    stored = import_cad_duty_bidirectional(synth, dry_run=False, apply=False, user_id=user_id, source="roundtrip")

    # Vendor adapters (Mark43 / Tyler shapes) — normalize + dry import
    vendor_results = {}
    try:
        from logic.cad_vendors import normalize_cad_payload

        if len(offs) >= 2:
            m43 = {
                "vendor": "mark43",
                "units": [
                    {
                        "dutyDate": "2026-07-16",
                        "officerId": int(offs[0]["id"]),
                        "coveringOfficerId": int(offs[1]["id"]),
                        "status": "covered",
                    }
                ],
            }
            ty = {
                "vendor": "tyler",
                "UnitAssignments": [
                    {
                        "DutyDate": "2026-07-17",
                        "AbsentEmployeeId": int(offs[0]["id"]),
                        "CoveringEmployeeId": int(offs[1]["id"]),
                        "Reason": "Tyler smoke",
                    }
                ],
            }
            for name, payload in (("mark43", m43), ("tyler", ty)):
                norm = normalize_cad_payload(payload)
                dry_v = import_cad_duty_bidirectional(payload, dry_run=True, source=f"vendor_{name}")
                vendor_results[name] = {
                    "normalize_rows": len(norm.get("rows") or []),
                    "dry_ok": bool(dry_v.get("success")),
                    "cover_pairs": dry_v.get("cover_pair_count"),
                }
    except Exception as exc:
        vendor_results["error"] = str(exc)[:120]

    vendors_ok = (
        all(
            (vendor_results.get(k) or {}).get("dry_ok") and (vendor_results.get(k) or {}).get("normalize_rows", 0) >= 1
            for k in ("mark43", "tyler")
            if "error" not in vendor_results
        )
        if vendor_results and "error" not in vendor_results
        else len(offs) < 2
    )

    return {
        "success": bool(dry.get("success") and stored.get("success") and (vendors_ok or len(offs) < 2)),
        "export": exp,
        "dry": dry,
        "synth_dry": dry2,
        "stored": stored,
        "vendors": vendor_results,
        "message": (
            f"CAD bidirectional smoke: export={exp.get('count')} · "
            f"dry_rows={dry.get('row_count')} · stored={stored.get('row_count')} · "
            f"cover_pairs={dry2.get('cover_pair_count', 0)} · "
            f"vendors={vendor_results}"
        ),
    }


def cad_bridge_status() -> Dict[str, Any]:
    cfg = get_cad_bridge_config()
    audits = sorted(_audits_dir().glob("cad_inbound_*.json"), reverse=True) if _audits_dir().is_dir() else []
    return {
        "success": True,
        "config": {k: v for k, v in cfg.items() if k != "inbound_token"},
        "recent_audits": [str(p.name) for p in audits[:5]],
        "bidirectional": True,
        "message": (
            "CAD bridge: export + webhook out · inbound receive/apply + pull URL in. "
            "Full vendor CAD adapter is agency-specific."
        ),
    }
