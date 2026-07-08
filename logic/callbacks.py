"""Call-back rotation list and event tracking."""

from datetime import date
from typing import Dict, List, Optional

from database import get_connection
from logic.officers import get_officer_by_id, get_officers_by_seniority
from logic.users import log_audit_action
from validators import is_officer_active, storage_date_str


def get_callback_rotation(*, active_only: bool = True) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT r.*, o.name AS officer_name, o.squad, o.seniority_rank
        FROM callback_rotation r
        JOIN officers o ON r.officer_id = o.id
    """
    if active_only:
        query += " WHERE r.active = 1 AND o.active = 1"
    query += " ORDER BY r.sort_order ASC, o.seniority_rank ASC"
    cursor.execute(query)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def sync_callback_rotation_from_roster(*, user_id: Optional[int] = None) -> Dict:
    """Ensure every active patrol officer appears on the callback list."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT MAX(sort_order) FROM callback_rotation")
        row = cursor.fetchone()
        next_order = (row[0] or 0) + 1
        added = 0
        for officer in get_officers_by_seniority():
            if not is_officer_active(officer):
                continue
            from validators import officer_uses_command_staff_schedule

            if officer_uses_command_staff_schedule(officer):
                continue
            cursor.execute(
                "SELECT id FROM callback_rotation WHERE officer_id = ?",
                (officer["id"],),
            )
            if cursor.fetchone():
                continue
            cursor.execute(
                "INSERT INTO callback_rotation (officer_id, sort_order, active) VALUES (?, ?, 1)",
                (officer["id"], next_order),
            )
            next_order += 1
            added += 1
        conn.commit()
        if added:
            log_audit_action("callback.sync_rotation", "callback_rotation", None, user_id, f"added={added}")
        return {"success": True, "added": added, "message": f"Added {added} officer(s) to callback rotation"}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": str(exc)}
    finally:
        conn.close()


def get_next_callback_candidate(*, as_of: Optional[date] = None) -> Dict:
    """Officer at top of rotation who has not been called back most recently."""
    rotation = get_callback_rotation(active_only=True)
    if not rotation:
        return {"success": True, "candidate": None, "message": "Callback rotation is empty"}

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT officer_id, MAX(event_date) AS last_call
        FROM callback_events
        GROUP BY officer_id
        """
    )
    last_calls = {r["officer_id"]: r["last_call"] for r in cursor.fetchall()}
    conn.close()

    def sort_key(entry: Dict):
        oid = entry["officer_id"]
        last = last_calls.get(oid) or "0000-01-01"
        return (last, entry["sort_order"])

    ordered = sorted(rotation, key=sort_key)
    top = ordered[0]
    return {
        "success": True,
        "candidate": {
            "officer_id": top["officer_id"],
            "officer_name": top["officer_name"],
            "squad": top.get("squad"),
            "sort_order": top["sort_order"],
            "last_callback": last_calls.get(top["officer_id"]),
        },
    }


def record_callback_event(
    officer_id: int,
    event_date: str,
    hours: float,
    *,
    notes: str = "",
    user_id: Optional[int] = None,
) -> Dict:
    officer = get_officer_by_id(officer_id)
    if not officer:
        return {"success": False, "message": "Officer not found"}
    try:
        event_date = storage_date_str(event_date)
    except ValueError as exc:
        return {"success": False, "message": str(exc)}
    if hours <= 0:
        return {"success": False, "message": "Hours must be positive"}

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO callback_events (officer_id, event_date, hours, notes, created_by_user_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (officer_id, event_date, hours, notes or None, user_id),
        )
        event_id = cursor.lastrowid
        conn.commit()
        log_audit_action(
            "callback.record",
            "callback_event",
            event_id,
            user_id,
            f"{officer['name']} {hours}h {event_date}",
        )
        return {"success": True, "event_id": event_id}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "message": str(exc)}
    finally:
        conn.close()


def get_callback_events(*, limit: int = 50, officer_id: Optional[int] = None) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    if officer_id is not None:
        cursor.execute(
            """
            SELECT e.*, o.name AS officer_name
            FROM callback_events e
            JOIN officers o ON e.officer_id = o.id
            WHERE e.officer_id = ?
            ORDER BY e.event_date DESC, e.id DESC
            LIMIT ?
            """,
            (officer_id, limit),
        )
    else:
        cursor.execute(
            """
            SELECT e.*, o.name AS officer_name
            FROM callback_events e
            JOIN officers o ON e.officer_id = o.id
            ORDER BY e.event_date DESC, e.id DESC
            LIMIT ?
            """,
            (limit,),
        )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_callback_ledger(limit: int = 30) -> Dict:
    """Summary for Ops Reports — rotation order + recent events."""
    rotation = get_callback_rotation(active_only=True)
    events = get_callback_events(limit=limit)
    next_up = get_next_callback_candidate()
    return {
        "success": True,
        "rotation": rotation,
        "recent_events": events,
        "next_candidate": next_up.get("candidate"),
        "rotation_count": len(rotation),
        "event_count": len(events),
    }
