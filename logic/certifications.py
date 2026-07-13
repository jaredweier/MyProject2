"""Officer certifications and shift-band gating."""

from datetime import date
from typing import Dict, List, Optional, Tuple

from database import get_connection
from logic.officers import get_officer_by_id
from logic.users import log_audit_action
from validators import parse_date, storage_date_str


def list_certification_types(
    *,
    active_only: bool = True,
    category: Optional[str] = None,
) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    clauses = []
    params: List = []
    if active_only:
        clauses.append("active = 1")
    if category:
        clauses.append("category = ?")
        params.append(category)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    try:
        cursor.execute(f"SELECT * FROM certification_types{where} ORDER BY name", params)
    except Exception:
        # Pre-migration DBs without category
        cursor.execute(
            "SELECT * FROM certification_types" + (" WHERE active = 1" if active_only else "") + " ORDER BY name"
        )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def list_immunization_types(*, active_only: bool = True) -> List[Dict]:
    """ESO-style medical readiness types (category=immunization)."""
    return list_certification_types(active_only=active_only, category="immunization")


def officer_immunization_status(officer_id: int, as_of: Optional[date] = None) -> Dict:
    """Summary of immunization/medical readiness for roster gates."""
    as_of = as_of or date.today()
    types = list_immunization_types(active_only=True)
    by_type = {c.get("cert_type_id"): c for c in get_officer_certifications(officer_id)}
    rows = []
    missing = 0
    expired = 0
    for t in types:
        tid = t["id"]
        rec = by_type.get(tid)
        if not rec:
            rows.append({"code": t.get("code"), "name": t.get("name"), "status": "missing"})
            missing += 1
            continue
        ok = _cert_is_valid(rec, as_of)
        st = "valid" if ok else "expired"
        if not ok:
            expired += 1
        rows.append(
            {
                "code": t.get("code"),
                "name": t.get("name"),
                "status": st,
                "expires_date": rec.get("expires_date"),
            }
        )
    return {
        "success": True,
        "officer_id": officer_id,
        "missing": missing,
        "expired": expired,
        "ok": missing == 0 and expired == 0,
        "items": rows,
    }


def get_officer_certifications(officer_id: int) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT c.*, t.code, t.name AS cert_name, t.description
        FROM officer_certifications c
        JOIN certification_types t ON c.cert_type_id = t.id
        WHERE c.officer_id = ?
        ORDER BY t.name
        """,
        (officer_id,),
    )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_shift_cert_requirements() -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT r.*, t.code, t.name AS cert_name
        FROM shift_cert_requirements r
        JOIN certification_types t ON r.cert_type_id = t.id
        ORDER BY r.shift_start, t.name
        """
    )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def _cert_is_valid(row: Dict, as_of: date) -> bool:
    expires = row.get("expires_date")
    if not expires:
        return True
    try:
        return parse_date(expires) >= as_of
    except ValueError:
        return True


def officer_meets_shift_cert_requirements(
    officer_id: int,
    shift_start: str,
    as_of: Optional[date] = None,
) -> Tuple[bool, str]:
    """Return (ok, message) for required certs on a shift band."""
    from validators import validate_officer_certifications

    check = validate_officer_certifications(officer_id, shift_start, as_of=as_of)
    if check.ok:
        return True, ""
    return False, check.message or "Missing required certification"


def assign_officer_certification(
    officer_id: int,
    cert_type_id: int,
    *,
    issued_date: Optional[str] = None,
    expires_date: Optional[str] = None,
    notes: str = "",
    user_id: Optional[int] = None,
) -> Dict:
    if not get_officer_by_id(officer_id):
        return {"success": False, "message": "Officer not found"}
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM certification_types WHERE id = ? AND active = 1", (cert_type_id,))
        if not cursor.fetchone():
            return {"success": False, "message": "Certification type not found"}
        issued = storage_date_str(issued_date) if issued_date else None
        expires = storage_date_str(expires_date) if expires_date else None
        cursor.execute(
            """
            INSERT INTO officer_certifications (officer_id, cert_type_id, issued_date, expires_date, notes)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(officer_id, cert_type_id) DO UPDATE SET
                issued_date = excluded.issued_date,
                expires_date = excluded.expires_date,
                notes = excluded.notes
            """,
            (officer_id, cert_type_id, issued, expires, notes or None),
        )
        conn.commit()
        log_audit_action("cert.assign", "officer_certification", officer_id, user_id, str(cert_type_id))
        return {"success": True}
    except ValueError as exc:
        return {"success": False, "message": str(exc)}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": str(exc)}
    finally:
        conn.close()


def set_shift_cert_requirement(shift_start: str, cert_type_id: int, *, user_id: Optional[int] = None) -> Dict:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO shift_cert_requirements (shift_start, cert_type_id)
            VALUES (?, ?)
            ON CONFLICT(shift_start, cert_type_id) DO NOTHING
            """,
            (shift_start, cert_type_id),
        )
        conn.commit()
        log_audit_action("cert.requirement", "shift_cert_requirement", cert_type_id, user_id, shift_start)
        return {"success": True}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": str(exc)}
    finally:
        conn.close()
