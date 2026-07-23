"""
Day-off requests, shift swaps, and in-app notifications.
"""

import json
from contextlib import nullcontext
from typing import Dict, List, Optional, Set, Tuple

from config import REQUEST_STATUS, is_high_risk_night, logger
from database import connection
from logic.officers import (
    describe_day_off_request,
    get_officer_by_id,
    get_officers_by_seniority,
    get_request_reviewer_officer_ids,
)
from logic.scheduling import (
    _rotation_only_status,
    get_shift_coverage_counts_for_range,
    officer_meets_minimum_rest,
    resolve_officer_shift_band,
)
from logic.snapshots import _insert_override_record
from models import ProcessRequestResult, ProcessSwapResult, SwapValidationResult
from validators import (
    applies_night_minimum,
    format_date,
    night_minimum_violation,
    parse_date,
    parse_date_filter,
    storage_date,
    storage_date_str,
    validate_day_off_request,
    validate_process_day_off,
    validate_process_shift_swap,
)


def validate_swap_feasibility(officer1_id: int, officer2_id: int, swap_date: str) -> SwapValidationResult:
    req_date = parse_date(swap_date)
    date_key = storage_date(req_date)

    if officer1_id == officer2_id:
        return SwapValidationResult(
            success=False,
            officer1_id=officer1_id,
            officer2_id=officer2_id,
            swap_date=req_date,
            message="Cannot swap with yourself",
        )

    officer1 = get_officer_by_id(officer1_id)
    officer2 = get_officer_by_id(officer2_id)

    if not officer1 or not officer2:
        return SwapValidationResult(
            success=False,
            officer1_id=officer1_id,
            officer2_id=officer2_id,
            swap_date=req_date,
            message="Officer not found",
        )

    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM schedule_overrides
            WHERE override_date = ?
            AND (original_officer_id IN (?, ?) OR replacement_officer_id IN (?, ?))
        """,
            (date_key, officer1_id, officer2_id, officer1_id, officer2_id),
        )
        if cursor.fetchone()[0] > 0:
            return SwapValidationResult(
                success=False,
                officer1_id=officer1_id,
                officer2_id=officer2_id,
                swap_date=req_date,
                message="Double-booking conflict",
            )

        if (
            _rotation_only_status(officer1, req_date) != "working"
            or _rotation_only_status(officer2, req_date) != "working"
        ):
            return SwapValidationResult(
                success=False,
                officer1_id=officer1_id,
                officer2_id=officer2_id,
                swap_date=req_date,
                message="One or both officers not scheduled to work",
            )

        if is_high_risk_night(req_date):
            date_str = req_date.strftime("%Y-%m-%d")
            coverage = get_shift_coverage_counts_for_range(req_date, req_date)
            c1 = coverage.get((date_str, officer1["squad"], officer1["shift_start"]), 0)
            c2 = coverage.get((date_str, officer2["squad"], officer2["shift_start"]), 0)
            night1 = applies_night_minimum(req_date, officer1["shift_start"], is_high_risk_night)
            night2 = applies_night_minimum(req_date, officer2["shift_start"], is_high_risk_night)
            if (night1 and night_minimum_violation(c1)) or (night2 and night_minimum_violation(c2)):
                return SwapValidationResult(
                    success=False,
                    officer1_id=officer1_id,
                    officer2_id=officer2_id,
                    swap_date=req_date,
                    message="Night coverage violation",
                    requires_manual=True,
                )

        from config import MIN_REST_HOURS_BETWEEN_SHIFTS

        rest_violations = []
        if not officer_meets_minimum_rest(
            officer1_id,
            req_date,
            officer2["shift_start"],
            officer2["shift_end"],
        ):
            rest_violations.append(officer1["name"])
        if not officer_meets_minimum_rest(
            officer2_id,
            req_date,
            officer1["shift_start"],
            officer1["shift_end"],
        ):
            rest_violations.append(officer2["name"])
        if rest_violations:
            return SwapValidationResult(
                success=False,
                officer1_id=officer1_id,
                officer2_id=officer2_id,
                swap_date=req_date,
                message=(
                    f"Minimum rest violation: {', '.join(rest_violations)} "
                    f"(minimum {MIN_REST_HOURS_BETWEEN_SHIFTS:.0f}h) — supervisor override required"
                ),
                requires_manual=True,
            )

        return SwapValidationResult(
            success=True,
            officer1_id=officer1_id,
            officer2_id=officer2_id,
            swap_date=req_date,
            can_proceed=True,
        )


def create_shift_swap_request(officer1_id: int, officer2_id: int, swap_date: str) -> Dict:
    swap_date = storage_date_str(swap_date)
    validation = validate_swap_feasibility(officer1_id, officer2_id, swap_date)
    if not validation.success and not validation.requires_manual:
        return {
            "success": False,
            "message": validation.message,
            "requires_manual": validation.requires_manual,
        }

    status = "Pending Manual Review" if validation.requires_manual else "Pending"
    with connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO shift_swaps (swap_date, officer1_id, officer2_id, status, admin_notes)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    swap_date,
                    officer1_id,
                    officer2_id,
                    status,
                    validation.message if validation.requires_manual else None,
                ),
            )
            swap_id = cursor.lastrowid
            conn.commit()
            officer1 = get_officer_by_id(officer1_id)
            officer2 = get_officer_by_id(officer2_id)
            if officer1 and officer2:
                _notify_shift_swap_submitted(swap_id, officer1, officer2, swap_date, status)
            return {
                "success": True,
                "swap_id": swap_id,
                "status": status,
                "requires_manual": validation.requires_manual,
            }
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": str(e)}


def process_shift_swap(swap_id: int, action: str = "approve", admin_notes: str = "") -> ProcessSwapResult:
    with connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM shift_swaps WHERE id = ?", (swap_id,))
            swap = cursor.fetchone()
            if not swap:
                return ProcessSwapResult(success=False, message="Swap request not found")

            swap = dict(swap)
            precheck = validate_process_shift_swap(swap, action)
            if not precheck.ok:
                return ProcessSwapResult(success=False, message=precheck.message)

            officer1 = get_officer_by_id(swap["officer1_id"])
            officer2 = get_officer_by_id(swap["officer2_id"])
            if not officer1 or not officer2:
                return ProcessSwapResult(success=False, message="Officer not found")

            if action == "reject":
                cursor.execute(
                    """
                    UPDATE shift_swaps
                    SET status = 'Rejected', admin_notes = ?, processed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """,
                    (admin_notes, swap_id),
                )
                conn.commit()
                _notify_shift_swap_processed(swap_id, officer1, officer2, swap["swap_date"], "Rejected")
                return ProcessSwapResult(success=True, status="Rejected", message="Swap rejected.")

            if action != "approve":
                return ProcessSwapResult(success=False, message=f"Unknown action: {action}")

            manual_override = swap["status"] == "Pending Manual Review"
            if not manual_override:
                validation = validate_swap_feasibility(swap["officer1_id"], swap["officer2_id"], swap["swap_date"])
                if validation.requires_manual or not validation.success:
                    cursor.execute(
                        """
                        UPDATE shift_swaps
                        SET status = 'Pending Manual Review', admin_notes = ?, processed_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """,
                        (admin_notes or validation.message, swap_id),
                    )
                    conn.commit()
                    _notify_supervisors(
                        "shift_swap",
                        "Swap Needs Review",
                        f"Swap #{swap_id} on {format_date(swap['swap_date'])} requires manual review.",
                        swap_id,
                        "shift_swap",
                    )
                    return ProcessSwapResult(
                        success=False,
                        status="Pending Manual Review",
                        message=validation.message,
                        requires_manual=True,
                    )

            swap_date = swap["swap_date"]
            _insert_override_record(
                cursor,
                swap_date,
                officer1["id"],
                officer2["id"],
                "Shift Swap",
                officer1["shift_start"],
            )
            _insert_override_record(
                cursor,
                swap_date,
                officer2["id"],
                officer1["id"],
                "Shift Swap",
                officer2["shift_start"],
            )
            cursor.execute(
                """
                UPDATE shift_swaps
                SET status = 'Approved', admin_notes = ?, processed_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = ?
            """,
                (admin_notes, swap_id, swap.get("status")),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                return ProcessSwapResult(
                    success=False,
                    status=swap.get("status"),
                    message="Approval not applied: swap changed after preview",
                )
            conn.commit()

            from logic.snapshots import apply_live_schedule_for_date

            apply_live_schedule_for_date(swap_date, None)
            msg = "Swap approved — shifts exchanged for one day."
            if manual_override:
                msg = "Swap approved (supervisor override) — shifts exchanged for one day."
            _notify_shift_swap_processed(swap_id, officer1, officer2, swap_date, "Approved")
            return ProcessSwapResult(success=True, status="Approved", message=msg, overrides_created=True)
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to process swap: {e}")
            return ProcessSwapResult(success=False, message=str(e))


def get_shift_swap_requests(
    status_filter: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    pending_only: bool = False,
    officer_id: Optional[int] = None,
) -> List[Dict]:
    date_from = parse_date_filter(date_from)
    date_to = parse_date_filter(date_to)
    query = """
        SELECT s.*,
               o1.name AS officer1_name, o1.squad AS officer1_squad, o1.shift_start AS officer1_shift,
               o2.name AS officer2_name, o2.squad AS officer2_squad, o2.shift_start AS officer2_shift
        FROM shift_swaps s
        JOIN officers o1 ON s.officer1_id = o1.id
        JOIN officers o2 ON s.officer2_id = o2.id
    """
    conditions: List[str] = []
    params: List = []
    if pending_only:
        conditions.append("s.status IN ('Pending', 'Pending Manual Review')")
    elif status_filter:
        conditions.append("s.status = ?")
        params.append(status_filter)
    if date_from:
        conditions.append("s.swap_date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("s.swap_date <= ?")
        params.append(date_to)
    if officer_id:
        conditions.append("(s.officer1_id = ? OR s.officer2_id = ?)")
        params.extend([officer_id, officer_id])
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY s.swap_date ASC, s.created_at ASC"
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def get_pending_shift_swap_requests(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict]:
    return get_shift_swap_requests(
        date_from=date_from,
        date_to=date_to,
        pending_only=True,
    )


def create_notification(
    recipient_officer_id: int,
    notification_type: str,
    title: str,
    message: str,
    related_id: Optional[int] = None,
    related_type: Optional[str] = None,
) -> Dict:
    with connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO notifications
                (recipient_officer_id, type, title, message, related_id, related_type)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (recipient_officer_id, notification_type, title, message, related_id, related_type),
            )
            conn.commit()
            return {"success": True, "notification_id": cursor.lastrowid}
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": str(e)}


def get_notifications(
    officer_id: Optional[int] = None,
    unread_only: bool = False,
    type_filter: Optional[str] = None,
    limit: int = 100,
) -> List[Dict]:
    query = """
        SELECT n.*, o.name AS recipient_name
        FROM notifications n
        JOIN officers o ON n.recipient_officer_id = o.id
    """
    clauses = []
    params: List = []
    if officer_id:
        clauses.append("n.recipient_officer_id = ?")
        params.append(officer_id)
    if unread_only:
        clauses.append("n.is_read = 0")
    if type_filter and type_filter not in ("All Types", ""):
        clauses.append("n.type = ?")
        params.append(type_filter)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY n.created_at DESC LIMIT ?"
    params.append(limit)
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def mark_notification_read(notification_id: int) -> Dict:
    with connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE notifications SET is_read = 1 WHERE id = ?",
                (notification_id,),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return {"success": False, "message": "Notification not found"}
            return {"success": True}
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": str(e)}


def mark_all_notifications_read(officer_id: Optional[int] = None) -> Dict:
    with connection() as conn:
        cursor = conn.cursor()
        try:
            if officer_id:
                cursor.execute(
                    "UPDATE notifications SET is_read = 1 WHERE recipient_officer_id = ?",
                    (officer_id,),
                )
            else:
                cursor.execute("UPDATE notifications SET is_read = 1")
            conn.commit()
            return {"success": True, "updated": cursor.rowcount}
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": str(e)}


def resolve_notification_navigation(notification: Dict) -> Optional[Dict]:
    """Map a notification to a UI navigation target, or None if not navigable."""
    related_type = (notification.get("related_type") or "").strip()
    ntype = (notification.get("type") or "").strip()
    related_id = notification.get("related_id")

    if related_type == "day_off_request" or ntype == "day_off":
        title = notification.get("title") or ""
        if "Needs Review" in title:
            return {
                "page": "requests",
                "highlight": "request",
                "related_id": related_id,
                "request_view": "review",
            }
        if "New Day-Off" in title:
            return {
                "page": "requests",
                "highlight": "request",
                "related_id": related_id,
                "request_view": "queue",
            }
        request_filter = REQUEST_STATUS["pending_manual"] if "Manual Review" in title else "All"
        return {
            "page": "requests",
            "highlight": "request",
            "related_id": related_id,
            "request_view": "history",
            "request_filter": request_filter,
        }
    if related_type == "shift_swap" or ntype == "shift_swap":
        return {"page": "swaps", "highlight": "swap", "related_id": related_id}
    if related_type == "open_shift" or ntype == "Open Shift":
        return {
            "page": "availability",
            "highlight": "open_shift",
            "related_id": related_id,
            "refresh": "availability",
        }
    if related_type in ("shift_bid_slot", "shift_bid_event") or ntype == "Shift Bid":
        return {
            "page": "availability",
            "highlight": "shift_bid",
            "related_id": related_id,
            "refresh": "availability",
        }
    if related_type == "availability" or ntype == "availability":
        return {
            "page": "availability",
            "highlight": "availability",
            "related_id": related_id,
            "refresh": "availability",
        }
    if related_type == "pay_period" or ntype == "Payroll":
        return {"page": "timecard", "refresh": "timecard"}
    return None


def _evaluate_post_bump_coverage(
    request_date: str,
    vacating_officer_id: int,
    steps,
    *,
    min_247: int = 0,
    windows=None,
) -> Dict:
    """Build tentative wall-clock assignments after bump chain; check 24/7 + windows."""
    from datetime import timedelta

    from logic.coverage_timeline import evaluate_day_coverage
    from logic.officers import get_officers_by_seniority
    from logic.scheduling import officer_base_rotation_working

    req_date = parse_date(request_date)
    # Officers who are off after chain
    off_ids = {vacating_officer_id}
    cover_map = {}  # replacement_id -> covered shift start
    for step in steps or []:
        off_ids.add(step.original_officer_id)
        cover_map[step.replacement_officer_id] = step.original_shift

    assignments = []
    for officer in get_officers_by_seniority():
        if officer.get("active") != 1:
            continue
        oid = officer["id"]
        if oid in off_ids and oid not in cover_map:
            continue
        if not officer_base_rotation_working(officer, req_date) and oid not in cover_map:
            continue
        start = cover_map.get(oid) or officer.get("shift_start") or ""
        end = officer.get("shift_end") or ""
        if oid in cover_map:
            # covered shift: derive end from length if needed
            from logic.shift_assignment import shift_end_for_start

            end = shift_end_for_start(start)
        if not start:
            continue
        assignments.append((req_date, start, end))
        # overnight tails from prior day still on duty into req_date morning
        prior = req_date - timedelta(days=1)
        if officer_base_rotation_working(officer, prior) and officer.get("shift_start"):
            ps = officer.get("shift_start") or ""
            pe = officer.get("shift_end") or ""
            if pe and ps and pe <= ps:  # overnight
                if oid not in off_ids or oid in cover_map:
                    assignments.append((prior, ps, pe))

    result = evaluate_day_coverage(
        assignments,
        req_date,
        min_247=min_247,
        windows=windows or [],
    )
    if result.get("ok"):
        return {"ok": True, "message": "Coverage OK after bump"}
    failed = [c.get("message") for c in result.get("checks") or [] if not c.get("ok")]
    return {
        "ok": False,
        "message": "; ".join(failed) or "Coverage requirements not met after bump",
        "detail": result,
    }


def _ensure_leave_accrual_ledger(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS leave_accrual_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            officer_id INTEGER NOT NULL,
            request_id INTEGER,
            request_type TEXT,
            request_date TEXT,
            bank_column TEXT,
            hours REAL,
            balance_after REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by_user_id INTEGER
        )
        """
    )


def _apply_leave_accrual_in_transaction(cursor, request: Dict, actor_user_id: Optional[int]) -> Dict:
    from logic.leave_accruals import SETTING_DEDUCT, TYPE_TO_BANK, _shift_hours_for_officer
    from logic.payroll.banks import _ensure_officer_time_banks

    cursor.execute("SELECT value FROM department_settings WHERE key = ?", (SETTING_DEDUCT,))
    setting = cursor.fetchone()
    enabled = str(setting["value"] if setting else "1").strip().lower() in ("1", "true", "yes", "on")
    if not enabled:
        return {"success": True, "skipped": True}

    request_type = str(request.get("request_type") or "").strip()
    bank_col = TYPE_TO_BANK.get(request_type)
    if not bank_col:
        lower = request_type.lower()
        bank_col = "sick_hours" if lower in ("sick", "ill", "injury") else None
        if lower in ("vacation", "annual", "pto"):
            bank_col = "float_holiday_hours"
    if not bank_col:
        return {"success": True, "skipped": True}

    request_date = parse_date(str(request["request_date"]))
    hours = float(
        request.get("_leave_hours")
        if request.get("_leave_hours") is not None
        else _shift_hours_for_officer(int(request["officer_id"]), str(request["request_date"]))
    )
    if hours <= 0:
        return {"success": False, "message": "Leave accrual hours must be positive"}
    banks = _ensure_officer_time_banks(cursor, int(request["officer_id"]), request_date)
    new_balance = float(banks.get(bank_col) or 0) - hours
    cursor.execute(
        f"UPDATE officer_time_banks SET {bank_col} = ? WHERE officer_id = ?",
        (new_balance, int(request["officer_id"])),
    )
    _ensure_leave_accrual_ledger(cursor)
    cursor.execute(
        """
        INSERT INTO leave_accrual_ledger
        (officer_id, request_id, request_type, request_date, bank_column, hours, balance_after,
         created_by_user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(request["officer_id"]),
            int(request["id"]),
            request_type,
            storage_date(request_date),
            bank_col,
            -hours,
            new_balance,
            actor_user_id,
        ),
    )
    return {"success": True, "bank": bank_col, "hours": hours, "balance_after": new_balance}


def _move_call_list_in_transaction(cursor, officer_id: int) -> Dict:
    cursor.execute("SELECT value FROM department_settings WHERE key = 'bump_call_list_json'")
    row = cursor.fetchone()
    try:
        entries = json.loads(row["value"]) if row and row["value"] else []
    except (TypeError, json.JSONDecodeError):
        return {"success": False, "message": "Stored call list is invalid JSON"}
    if not isinstance(entries, list):
        return {"success": False, "message": "Stored call list is invalid"}
    normalized = []
    for item in entries:
        if isinstance(item, int):
            normalized.append({"officer_id": item})
        elif isinstance(item, dict) and item.get("officer_id") is not None:
            normalized.append(dict(item))
    oid = int(officer_id)
    moved = [entry for entry in normalized if int(entry["officer_id"]) == oid]
    rest = [entry for entry in normalized if int(entry["officer_id"]) != oid]
    if not moved:
        moved = [{"officer_id": oid, "name": "", "note": "added after order-in"}]
    updated = rest + moved
    for index, entry in enumerate(updated):
        entry["order"] = index
    cursor.execute(
        """
        INSERT INTO department_settings (key, value, updated_at)
        VALUES ('bump_call_list_json', ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
        """,
        (json.dumps(updated),),
    )

    cursor.execute("SELECT officer_id FROM callback_rotation WHERE active = 1 ORDER BY sort_order ASC")
    callback_ids = [int(item["officer_id"]) for item in cursor.fetchall()]
    if callback_ids:
        callback_ids = [item for item in callback_ids if item != oid] + [oid]
        for index, callback_id in enumerate(callback_ids, start=1):
            cursor.execute(
                """
                INSERT INTO callback_rotation (officer_id, sort_order, active)
                VALUES (?, ?, 1)
                ON CONFLICT(officer_id) DO UPDATE SET sort_order = excluded.sort_order, active = 1
                """,
                (callback_id, index),
            )
    return {"success": True}


def _queue_leave_approval_notifications_in_transaction(
    cursor,
    request: Dict,
    officer: Dict,
    replacement_id: Optional[int],
    replacement_name: Optional[str],
    plan_text: str,
    actor_user_id: Optional[int],
) -> Dict:
    display_date = format_date(request["request_date"])
    suffix = f" Coverage: {plan_text}." if plan_text else ""
    if replacement_name and not plan_text:
        suffix = f" Covered by {replacement_name}."
    notifications = [
        (
            int(officer["id"]),
            "Request Approved",
            f"Your time off request for {display_date} was approved.{suffix}",
        )
    ]
    if replacement_id:
        notifications.append(
            (
                int(replacement_id),
                "Coverage Assignment",
                f"You are covering {officer['name']}'s shift on {display_date}."
                + (f" Plan: {plan_text}" if plan_text else ""),
            )
        )
    for recipient_id, title, message in notifications:
        cursor.execute(
            """
            INSERT INTO notifications
            (recipient_officer_id, type, title, message, related_id, related_type)
            VALUES (?, 'day_off', ?, ?, ?, 'day_off_request')
            """,
            (recipient_id, title, message, int(request["id"])),
        )

    outbox = [
        (
            "email",
            "leave_approved",
            f"Leave approved {display_date}",
            f"Leave approved for {officer.get('name')} on {display_date}.{suffix}",
            int(officer["id"]),
        )
    ]
    if replacement_id:
        outbox.append(
            (
                "sms",
                "leave_cover",
                "Coverage assignment",
                f"You cover {officer.get('name')} on {display_date}.",
                int(replacement_id),
            )
        )
    for channel, template, subject, body, recipient_id in outbox:
        cursor.execute(
            """
            INSERT INTO notify_outbox
            (channel, template_key, subject, body, officer_id, status, meta_json, user_id)
            VALUES (?, ?, ?, ?, ?, 'queued', '{}', ?)
            """,
            (channel, template, subject, body, recipient_id, actor_user_id),
        )
    return {"success": True}


def process_day_off_request(
    request_id: int,
    action: str = "approve",
    admin_notes: str = "",
    actor_user_id: Optional[int] = None,
    *,
    preferred_chain: Optional[List[Tuple[int, int]]] = None,
    _transaction_conn=None,
    _base_schedule_ready: bool = False,
    _verified_suggestion=None,
    _batch_context: Optional[Dict] = None,
    relaxation_authority: Optional[Dict] = None,
) -> ProcessRequestResult:
    owns_transaction = _transaction_conn is None
    connection_scope = connection() if owns_transaction else nullcontext(_transaction_conn)
    with connection_scope as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT r.*, o.name AS officer_name, o.squad, o.shift_start, o.shift_end
                FROM day_off_requests r
                JOIN officers o ON r.officer_id = o.id
                WHERE r.id = ?
            """,
                (request_id,),
            )
            row = cursor.fetchone()
            if not row:
                return ProcessRequestResult(success=False, message="Request not found")

            request = dict(row)
            batch_context = _batch_context or {}
            officer = batch_context.get("officer") or get_officer_by_id(request["officer_id"])
            if batch_context.get("leave_hours") is not None:
                request["_leave_hours"] = batch_context["leave_hours"]
            precheck = validate_process_day_off(request, officer, action)
            if not precheck.ok:
                return ProcessRequestResult(success=False, message=precheck.message)

            if action == "reject":
                cursor.execute(
                    """
                    UPDATE day_off_requests
                    SET status = 'Rejected', admin_notes = ?, processed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """,
                    (admin_notes, request_id),
                )
                if owns_transaction:
                    conn.commit()
                    _notify_day_off_processed(request, officer, "Rejected")
                return ProcessRequestResult(success=True, status="Rejected", message="Request rejected.")

            if action != "approve":
                return ProcessRequestResult(success=False, message=f"Unknown action: {action}")

            from logic.snapshots import ensure_original_monthly_schedule

            request_day = parse_date(request["request_date"])
            if not _base_schedule_ready:
                base_result = ensure_original_monthly_schedule(request_day.year, request_day.month, actor_user_id)
                if not base_result.get("success"):
                    return ProcessRequestResult(
                        success=False,
                        message=f"Approval not applied: base schedule unavailable: {base_result.get('message')}",
                    )

            manual_override = request["status"] == REQUEST_STATUS["pending_manual"]
            covered_start = batch_context.get("covered_start")
            if covered_start is None:
                covered_start, _covered_end = resolve_officer_shift_band(
                    request["officer_id"],
                    parse_date(request["request_date"]),
                    home_shift_start=request.get("shift_start"),
                    home_shift_end=request.get("shift_end"),
                )
            suggestion = None
            steps = []
            if _verified_suggestion is not None:
                suggestion = _verified_suggestion
                steps = suggestion.steps or []
            elif preferred_chain is not None:
                # UI input is selection, not proof. Recompute against current
                # schedule state and accept only an exact complete plan.
                from logic.coverage_optimizer import search_best_coverage_plans
                from logic.scheduling import get_generated_schedule_day_context

                requested_chain = tuple(
                    (int(pair[0]), int(pair[1])) for pair in preferred_chain if pair and len(pair) == 2
                )
                current_context = get_generated_schedule_day_context(parse_date(request["request_date"]))
                current_plans = search_best_coverage_plans(
                    request["officer_id"],
                    request["request_date"],
                    request["squad"],
                    covered_start,
                    current_context,
                    required_first_replacement_id=(requested_chain[0][1] if requested_chain else None),
                )
                suggestion = next(
                    (plan for plan in current_plans if plan.success and tuple(plan.chain or []) == requested_chain),
                    None,
                )
                if suggestion is None:
                    return ProcessRequestResult(
                        success=False,
                        message="Selected coverage plan is stale or failed current independent checks",
                    )
                steps = suggestion.steps or []
            else:
                from logic.coverage_optimizer import suggest_bump_chain

                constraint_probe = suggest_bump_chain(
                    request["officer_id"],
                    request["request_date"],
                    request["squad"],
                    covered_start,
                    supervisor_override=False,
                )
                suggestion = (
                    suggest_bump_chain(
                        request["officer_id"],
                        request["request_date"],
                        request["squad"],
                        covered_start,
                        supervisor_override=True,
                        # Narrow the override to the one constraint that
                        # actually failed above, instead of relaxing both
                        # minimum-rest and consecutive-work blanket-style.
                        relaxed_constraint=constraint_probe.failure_reason,
                    )
                    if manual_override
                    else constraint_probe
                )
                if not manual_override and (not suggestion.success or suggestion.requires_manual):
                    cursor.execute(
                        """
                        UPDATE day_off_requests
                        SET status = 'Pending Manual Review', admin_notes = ?, processed_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """,
                        (admin_notes or suggestion.message, request_id),
                    )
                    if owns_transaction:
                        conn.commit()
                        request["status"] = REQUEST_STATUS["pending_manual"]
                        _notify_day_off_processed(request, officer, "Pending Manual Review")
                    return ProcessRequestResult(
                        success=False,
                        status="Pending Manual Review",
                        message=suggestion.message,
                        requires_manual=True,
                    )
                steps = suggestion.steps or []

            if manual_override:
                if relaxation_authority is None:
                    from logic.override_authority import build_relaxation_authority

                    constraint_code = str(getattr(constraint_probe, "failure_reason", "") or "").strip().lower()
                    try:
                        relaxation_authority = build_relaxation_authority(
                            constraint_code=constraint_code,
                            actor_user_id=actor_user_id,
                            subject_type="day_off_request",
                            subject_id=request_id,
                            interval_start=request["request_date"],
                            reason=admin_notes or f"Supervisor approved {constraint_code.replace('_', ' ')} relaxation",
                            evidence=getattr(constraint_probe, "message", "") or constraint_code,
                        )
                    except ValueError as exc:
                        return ProcessRequestResult(
                            success=False,
                            status=request.get("status"),
                            message=str(exc),
                            requires_manual=True,
                        )
                else:
                    from logic.override_authority import validate_relaxation_authority

                    authority_error = validate_relaxation_authority(relaxation_authority)
                    if authority_error:
                        return ProcessRequestResult(
                            success=False,
                            status=request.get("status"),
                            message=authority_error,
                            requires_manual=True,
                        )

            # Continuous coverage gate (24/7 + extra windows) after tentative bump chain
            if not manual_override and not batch_context.get("coverage_verified"):
                from logic.coverage_windows_store import get_active_coverage_windows, get_coverage_247_minimum

                min_247 = get_coverage_247_minimum()
                windows = get_active_coverage_windows()
                if min_247 > 0 or windows:
                    cov_check = _evaluate_post_bump_coverage(
                        request["request_date"],
                        request["officer_id"],
                        steps,
                        min_247=min_247,
                        windows=windows,
                    )
                    if not cov_check.get("ok"):
                        cursor.execute(
                            """
                            UPDATE day_off_requests
                            SET status = 'Pending Manual Review', admin_notes = ?, processed_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """,
                            (admin_notes or cov_check.get("message") or "Coverage window short", request_id),
                        )
                        if owns_transaction:
                            conn.commit()
                            request["status"] = REQUEST_STATUS["pending_manual"]
                            _notify_day_off_processed(request, officer, "Pending Manual Review")
                        return ProcessRequestResult(
                            success=False,
                            status="Pending Manual Review",
                            message=cov_check.get("message") or "Coverage requirements not met",
                            requires_manual=True,
                        )

            replacement_id = None
            replacement_name = None
            created_override_ids: List[int] = []
            for step in steps:
                _insert_override_record(
                    cursor,
                    request["request_date"],
                    step.original_officer_id,
                    step.replacement_officer_id,
                    f"Day-off: {request['request_type']}",
                    step.original_shift,
                    relaxation=relaxation_authority if manual_override else None,
                )
                created_override_ids.append(int(cursor.lastrowid))
                if replacement_id is None:
                    replacement_id = step.replacement_officer_id
                    replacement_name = step.replacement_officer_name

            cascade_note = f" ({len(steps)} overrides)" if len(steps) > 1 else ""
            if manual_override:
                override_reason = getattr(constraint_probe, "failure_reason", None) or (relaxation_authority or {}).get(
                    "constraint_code"
                )
                message = f"Approved (supervisor override). Replacement: {replacement_name}{cascade_note}"
                if override_reason == "minimum_rest":
                    message = f"Approved (minimum rest override). Replacement: {replacement_name}{cascade_note}"
                elif override_reason == "consecutive_days":
                    message = f"Approved (consecutive day override). Replacement: {replacement_name}{cascade_note}"
            else:
                message = f"Approved. Replacement: {replacement_name}{cascade_note}"

            cursor.execute(
                """
                UPDATE day_off_requests
                SET status = 'Approved', admin_notes = ?, processed_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = ?
            """,
                (admin_notes, request_id, request.get("status")),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                return ProcessRequestResult(
                    success=False,
                    status=request.get("status"),
                    message="Approval not applied: request changed after preview",
                )
            from logic.snapshots import apply_live_schedule_for_date_in_transaction

            live_result = apply_live_schedule_for_date_in_transaction(conn, request["request_date"], actor_user_id)
            if not live_result.get("success"):
                conn.rollback()
                return ProcessRequestResult(
                    success=False,
                    status=request.get("status"),
                    message=f"Approval not applied: live schedule rebuild failed: {live_result.get('message')}",
                )
            # Call list: ordered/off-duty cover moves officer to end (furthest from next call)
            for step in steps:
                if not getattr(step, "replacement_on_duty", True):
                    call_list_result = _move_call_list_in_transaction(cursor, int(step.replacement_officer_id))
                    if not call_list_result.get("success"):
                        conn.rollback()
                        return ProcessRequestResult(
                            success=False,
                            status=request.get("status"),
                            message=(
                                f"Approval not applied: call-list update failed: {call_list_result.get('message')}"
                            ),
                        )
                    break
            # Accrual debit (vacation/sick/comp) — non-blocking if bank short
            accrual_result = _apply_leave_accrual_in_transaction(cursor, request, actor_user_id)
            if not accrual_result.get("success"):
                conn.rollback()
                return ProcessRequestResult(
                    success=False,
                    status=request.get("status"),
                    message=f"Approval not applied: accrual update failed: {accrual_result.get('message')}",
                )
            # Plan text for notifications (who covers whom)
            plan_text = ""
            if steps:
                parts = []
                for step in steps[:6]:
                    parts.append(
                        f"{getattr(step, 'replacement_officer_name', '?')} covers "
                        f"{getattr(step, 'original_officer_name', '?')}"
                    )
                plan_text = "; ".join(parts)
            notify_result = _queue_leave_approval_notifications_in_transaction(
                cursor,
                request,
                officer,
                replacement_id,
                replacement_name,
                plan_text,
                actor_user_id,
            )
            if not notify_result.get("success"):
                conn.rollback()
                return ProcessRequestResult(
                    success=False,
                    status=request.get("status"),
                    message=f"Approval not applied: notification queue failed: {notify_result.get('message')}",
                )
            cursor.execute(
                """
                INSERT INTO audit_log (action, entity_type, entity_id, user_id, details)
                VALUES ('day_off.approve', 'day_off_request', ?, ?, ?)
                """,
                (
                    request_id,
                    actor_user_id,
                    f"replacement={replacement_id} overrides={len(created_override_ids)}",
                ),
            )
            if owns_transaction:
                conn.commit()
            return ProcessRequestResult(
                success=True,
                status="Approved",
                message=message,
                override_created=bool(steps),
            )
        except Exception as e:
            conn.rollback()
            logger.error(f"process_day_off_request failed: {e}")
            return ProcessRequestResult(success=False, message=str(e))


def _sort_for_vacation_granting(requests: List[Dict]) -> List[Dict]:
    """Vacation grants use seniority (lower rank = more senior); other types sort by date."""

    def sort_key(req: Dict):
        if req.get("request_type") == "Vacation":
            return (
                0,
                req.get("seniority_rank", 9999),
                req.get("request_date", ""),
                req.get("created_at", "") or "",
                req.get("id", 0),
            )
        return (1, req.get("request_date", ""), req.get("created_at", "") or "", req.get("id", 0))

    return sorted(requests, key=sort_key)


def bulk_approve_auto_ok_requests() -> Dict:
    """Atomically approve the priority-ordered set of currently auto-coverable requests."""
    pending = _sort_for_vacation_granting(get_pending_day_off_requests())
    skipped_manual = 0
    failed: List[str] = []
    candidates: List[Tuple[Dict, object, Dict]] = []

    for req in pending:
        if req["status"] != REQUEST_STATUS["pending"]:
            skipped_manual += 1
            continue
        covered_start, _covered_end = resolve_officer_shift_band(
            req["officer_id"],
            parse_date(req["request_date"]),
            home_shift_start=req.get("shift_start"),
            home_shift_end=req.get("shift_end"),
        )
        from logic.coverage_optimizer import suggest_bump_chain

        suggestion = suggest_bump_chain(
            req["officer_id"],
            req["request_date"],
            req["squad"],
            covered_start,
        )
        if not suggestion.success:
            skipped_manual += 1
            continue
        steps = suggestion.steps or []
        from logic.coverage_windows_store import get_active_coverage_windows, get_coverage_247_minimum

        min_247 = get_coverage_247_minimum()
        windows = get_active_coverage_windows()
        if min_247 > 0 or windows:
            cov_check = _evaluate_post_bump_coverage(
                req["request_date"],
                req["officer_id"],
                steps,
                min_247=min_247,
                windows=windows,
            )
            if not cov_check.get("ok"):
                skipped_manual += 1
                continue
        from logic.leave_accruals import _shift_hours_for_officer

        batch_context = {
            "officer": get_officer_by_id(req["officer_id"]),
            "covered_start": covered_start,
            "coverage_verified": True,
            "leave_hours": float(_shift_hours_for_officer(req["officer_id"], req["request_date"])),
        }
        candidates.append((req, suggestion, batch_context))

    if not candidates:
        return {
            "success": True,
            "approved": 0,
            "skipped_manual": skipped_manual,
            "failed": [],
            "message": f"Approved 0 request(s); {skipped_manual} need manual review",
        }

    # Base snapshots may create rows using their own connection. Prepare every
    # required month before opening the batch write transaction.
    from logic.snapshots import ensure_original_monthly_schedule

    months = sorted(
        {
            (parse_date(req["request_date"]).year, parse_date(req["request_date"]).month)
            for req, _suggestion, _context in candidates
        }
    )
    for year, month in months:
        base_result = ensure_original_monthly_schedule(year, month)
        if not base_result.get("success"):
            message = f"Base schedule unavailable for {year:04d}-{month:02d}: {base_result.get('message')}"
            return {
                "success": False,
                "approved": 0,
                "skipped_manual": skipped_manual,
                "failed": [message],
                "message": "Batch approval not applied",
            }

    # Avoid transactional schema changes after batch writes begin.
    with connection() as schema_conn:
        _ensure_leave_accrual_ledger(schema_conn.cursor())
        schema_conn.commit()

    approved = 0
    with connection() as conn:
        try:
            for req, suggestion, batch_context in candidates:
                result = process_day_off_request(
                    req["id"],
                    action="approve",
                    _transaction_conn=conn,
                    _base_schedule_ready=True,
                    _verified_suggestion=suggestion,
                    _batch_context=batch_context,
                )
                if not result.success:
                    conn.rollback()
                    failed.append(f"#{req['id']}: {result.message}")
                    return {
                        "success": False,
                        "approved": 0,
                        "skipped_manual": skipped_manual,
                        "failed": failed,
                        "message": "Batch approval rolled back; no request was approved",
                    }
                approved += 1
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.error(f"bulk_approve_auto_ok_requests failed: {exc}")
            return {
                "success": False,
                "approved": 0,
                "skipped_manual": skipped_manual,
                "failed": [str(exc)],
                "message": "Batch approval rolled back; no request was approved",
            }

    return {
        "success": True,
        "approved": approved,
        "skipped_manual": skipped_manual,
        "failed": failed,
        "message": f"Approved {approved} request(s); {skipped_manual} need manual review",
    }


def bulk_reject_pending_requests(admin_notes: str = "Bulk rejected") -> Dict:
    """Reject standard Pending requests; skips Pending Manual Review."""
    pending = get_pending_day_off_requests()
    rejected = 0
    skipped_manual = 0
    failed: List[str] = []

    for req in pending:
        if req["status"] != REQUEST_STATUS["pending"]:
            skipped_manual += 1
            continue
        result = process_day_off_request(req["id"], action="reject", admin_notes=admin_notes)
        if result.success:
            rejected += 1
        else:
            failed.append(f"#{req['id']}: {result.message}")

    return {
        "success": True,
        "rejected": rejected,
        "skipped_manual": skipped_manual,
        "failed": failed,
        "message": f"Rejected {rejected} request(s); {skipped_manual} need manual review",
    }


def create_day_off_request(
    officer_id: int,
    request_date: str,
    request_type: str,
    notes: str = "",
) -> Dict:
    from validators import validate_no_duplicate_pending, validate_request_type

    request_date = storage_date_str(request_date)
    officer = get_officer_by_id(officer_id)
    for check in (validate_day_off_request(officer, request_date), validate_request_type(request_type)):
        if not check.ok:
            return {"success": False, "message": check.message}

    with connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT 1 FROM day_off_requests
                WHERE officer_id = ? AND request_date = ?
                AND status IN ('Pending', 'Pending Manual Review')
            """,
                (officer_id, request_date),
            )
            if cursor.fetchone():
                dup = validate_no_duplicate_pending(True, officer["name"], request_date)
                return {"success": False, "message": dup.message}

            cursor.execute(
                """
                INSERT INTO day_off_requests (officer_id, request_date, request_type, notes, status)
                VALUES (?, ?, ?, ?, 'Pending')
            """,
                (officer_id, request_date, request_type, notes),
            )
            request_id = cursor.lastrowid
            cursor.execute(
                "SELECT created_at FROM day_off_requests WHERE id = ?",
                (request_id,),
            )
            created_row = cursor.fetchone()
            created_at = created_row["created_at"] if created_row else None
            conn.commit()
            _notify_day_off_submitted(request_id, officer, request_date, request_type)
            return {"success": True, "request_id": request_id, "created_at": created_at}
        except Exception as e:
            conn.rollback()
            return {"success": False, "message": str(e)}


def get_pending_day_off_requests() -> List[Dict]:
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.*, o.name AS officer_name, o.squad, o.shift_start, o.shift_end, o.seniority_rank
            FROM day_off_requests r
            JOIN officers o ON r.officer_id = o.id
            WHERE r.status IN ('Pending', 'Pending Manual Review')
            ORDER BY r.request_date ASC
        """)
        rows = cursor.fetchall()
    return _sort_for_vacation_granting([dict(row) for row in rows])


def get_day_off_requests(
    status_filter: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    officer_id: Optional[int] = None,
) -> List[Dict]:
    date_from = parse_date_filter(date_from)
    date_to = parse_date_filter(date_to)
    query = """
        SELECT r.*, o.name AS officer_name, o.squad, o.shift_start, o.shift_end
        FROM day_off_requests r
        JOIN officers o ON r.officer_id = o.id
    """
    conditions: List[str] = []
    params: List = []
    if status_filter and status_filter.lower() != "all":
        conditions.append("r.status = ?")
        params.append(status_filter)
    if date_from:
        conditions.append("r.request_date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("r.request_date <= ?")
        params.append(date_to)
    if officer_id is not None:
        conditions.append("r.officer_id = ?")
        params.append(officer_id)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY r.request_date DESC, r.created_at DESC"
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def get_day_off_request_created_at(request_id: int) -> Dict:
    """Return the stored created_at timestamp for a day-off request."""
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, created_at FROM day_off_requests WHERE id = ?",
            (request_id,),
        )
        row = cursor.fetchone()
    if not row:
        return {"success": False, "message": "Request not found"}
    return {
        "success": True,
        "request_id": row["id"],
        "created_at": row["created_at"],
    }


def get_day_off_requests_for_viewer(
    role: str,
    linked_officer_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict:
    """
    Day-off requests scoped by login role.
    Officers see only their own; Supervisor and Administration see all.
    """
    if role == "Officer":
        if not linked_officer_id:
            return {"success": True, "requests": [], "scope": "own"}
        requests = get_day_off_requests(
            status_filter=status_filter,
            date_from=date_from,
            date_to=date_to,
            officer_id=linked_officer_id,
        )
        return {"success": True, "requests": requests, "scope": "own"}
    if role in ("Supervisor", "Administration"):
        requests = get_day_off_requests(
            status_filter=status_filter,
            date_from=date_from,
            date_to=date_to,
        )
        return {"success": True, "requests": requests, "scope": "all"}
    return {"success": False, "message": f"Unknown role: {role}", "requests": []}


def _notify_availability_conflict(
    officer: Dict,
    entry_id: int,
    unavailable_date: str,
    schedule_status: str,
) -> None:
    create_notification(
        officer["id"],
        "availability",
        "Schedule Conflict",
        f"Your blackout on {unavailable_date} conflicts with a scheduled shift ({schedule_status}).",
        entry_id,
        "availability",
    )
    _notify_supervisors(
        "availability",
        "Availability Conflict",
        f"{officer['name']} is unavailable on {unavailable_date} but scheduled ({schedule_status}).",
        entry_id,
        "availability",
    )


def _notify_day_off_processed(
    request: Dict,
    officer: Dict,
    action: str,
    replacement_id: Optional[int] = None,
    replacement_name: Optional[str] = None,
    plan_text: str = "",
) -> None:
    request_id = request["id"]
    request_date = format_date(request["request_date"])
    if action == "Rejected":
        create_notification(
            officer["id"],
            "day_off",
            "Request Rejected",
            f"Your time off request for {request_date} was rejected.",
            request_id,
            "day_off_request",
        )
        return

    if action == "Pending Manual Review":
        create_notification(
            officer["id"],
            "day_off",
            "Manual Review Required",
            f"Your request for {request_date} needs supervisor review.",
            request_id,
            "day_off_request",
        )
        _notify_supervisors(
            "day_off",
            "Day-Off Needs Review",
            f"Request #{request_id} for {officer['name']} on {request_date} needs review. Open Ops Desk.",
            request_id,
            "day_off_request",
        )
        return

    plan_suffix = f" Coverage: {plan_text}." if plan_text else ""
    if replacement_name and not plan_text:
        plan_suffix = f" Covered by {replacement_name}."
    create_notification(
        officer["id"],
        "day_off",
        "Request Approved",
        f"Your time off request for {request_date} was approved.{plan_suffix}",
        request_id,
        "day_off_request",
    )
    if replacement_id and replacement_name:
        create_notification(
            replacement_id,
            "day_off",
            "Coverage Assignment",
            f"You are covering {officer['name']}'s shift on {request_date}."
            + (f" Plan: {plan_text}" if plan_text else ""),
            request_id,
            "day_off_request",
        )
    # Outbox for email/SMS when channels configured
    try:
        from logic.notify_queue import enqueue_notify

        body = f"Leave approved for {officer.get('name')} on {request_date}.{plan_suffix}"
        enqueue_notify(
            channel="email",
            subject=f"Leave approved {request_date}",
            body=body,
            officer_id=int(officer["id"]),
            template_key="leave_approved",
        )
        if replacement_id:
            enqueue_notify(
                channel="sms",
                subject="Coverage assignment",
                body=f"You cover {officer.get('name')} on {request_date}.",
                officer_id=int(replacement_id),
                template_key="leave_cover",
            )
    except Exception:
        pass


def _notify_day_off_submitted(request_id: int, officer: Dict, request_date: str, request_type: str) -> None:
    context = describe_day_off_request(officer["id"], request_date)
    summary = context.get("summary", "pending review")
    display_date = format_date(request_date)
    create_notification(
        officer["id"],
        "day_off",
        "Request Submitted",
        (
            f"Your {request_type} request for {display_date} was submitted. "
            f"A supervisor will approve or deny it ({summary})."
        ),
        request_id,
        "day_off_request",
    )
    _notify_supervisors(
        "day_off",
        "New Day-Off Request",
        (
            f"{officer['name']} submitted {request_type} for {display_date}. "
            f"{summary.capitalize()}. Review in Requests — use Bulk Approve Auto-OK or approve/deny individually."
        ),
        request_id,
        "day_off_request",
    )


def _notify_open_shift_filled(shift: Dict, officer: Dict) -> None:
    message = f"{officer['name']} claimed {shift['shift_date']} {shift['shift_start']}–{shift['shift_end']}"
    _notify_supervisors("Open Shift", "Open Shift Filled", message, shift.get("id"), "open_shift")
    create_notification(
        officer["id"],
        "Open Shift",
        "Shift claimed",
        f"You claimed {shift['shift_date']} {shift['shift_start']}–{shift['shift_end']}",
        related_id=shift.get("id"),
        related_type="open_shift",
    )
    try:
        from logic.notify_channels import dispatch_channel_hooks

        dispatch_channel_hooks(
            subject="Open Shift Filled",
            body=message,
            officer_ids=[officer["id"]],
            prefer_sms=True,
        )
    except Exception:
        pass


def _notify_open_shift_posted(
    shift_id: int,
    shift_date: str,
    shift_start: str,
    shift_end: str,
    squad: Optional[str],
) -> None:
    squad_note = f" (Squad {squad})" if squad else ""
    message = f"{shift_date}  ·  {shift_start}–{shift_end}{squad_note}"
    oids = []
    for officer in get_officers_by_seniority():
        if officer.get("active") != 1:
            continue
        if squad and officer["squad"] != squad:
            continue
        oids.append(officer["id"])
        create_notification(
            officer["id"],
            "Open Shift",
            "Open shift posted",
            message,
            related_id=shift_id,
            related_type="open_shift",
        )
    try:
        from logic.notify_channels import dispatch_template

        dispatch_template(
            "open_shift",
            officer_ids=oids,
            prefer_sms=True,
            date=shift_date,
            start=shift_start,
            end=shift_end,
            squad=squad or "",
            notes="",
        )
    except Exception:
        pass


def _notify_shift_bid_event_published(event_id: int, event: Dict) -> None:
    squad = event.get("squad")
    squad_note = f" (Squad {squad})" if squad else ""
    title = event.get("title") or "Shift bid"
    due = event.get("bids_due_by") or "see details"
    message = f"{title}{squad_note} — rank your shift preferences in Blackout Dates. Due by: {due}"
    for officer in get_officers_by_seniority():
        if officer.get("active") != 1:
            continue
        if squad and officer["squad"] != squad:
            continue
        create_notification(
            officer["id"],
            "Shift Bid",
            "Shift bid open",
            message,
            related_id=event_id,
            related_type="shift_bid_event",
        )


def _notify_shift_bid_event_finalized(
    event_id: int,
    event: Dict,
    awards: List[Dict],
) -> None:
    title = event.get("title") or "Shift bid"
    award_by_officer = {a["officer_id"]: a for a in awards}
    with connection() as cursor_conn:
        cursor = cursor_conn.cursor()
        cursor.execute(
            "SELECT DISTINCT officer_id FROM shift_bid_rankings WHERE event_id = ?",
            (event_id,),
        )
        respondents = [row["officer_id"] for row in cursor.fetchall()]

    for officer_id in respondents:
        award = award_by_officer.get(officer_id)
        if award:
            create_notification(
                officer_id,
                "Shift Bid",
                "Shift bid results",
                f"You were awarded {award['option_label']} in {title}",
                related_id=event_id,
                related_type="shift_bid_event",
            )
        else:
            create_notification(
                officer_id,
                "Shift Bid",
                "Shift bid results",
                f"Results posted for {title} — check your assignment",
                related_id=event_id,
                related_type="shift_bid_event",
            )
    summary = ", ".join(f"{a['officer_name']}→{a['option_label']}" for a in awards[:5])
    _notify_supervisors(
        "Shift Bid",
        "Shift bid finalized",
        f"{title}: {summary or 'no awards'}",
        event_id,
        "shift_bid_event",
    )


def _notify_shift_swap_processed(swap_id: int, officer1: Dict, officer2: Dict, swap_date: str, status: str) -> None:
    for officer in (officer1, officer2):
        create_notification(
            officer["id"],
            "shift_swap",
            f"Swap {status}",
            f"Shift swap on {format_date(swap_date)} was {status.lower()}.",
            swap_id,
            "shift_swap",
        )


def _notify_schedule_published(year: int, month: int, snapshot_id: int) -> None:
    # Display-friendly label; storage keys stay ISO elsewhere
    label = f"{month}/{year}"
    message = f"The current monthly schedule for {label} has been published."
    oids = []
    for officer in get_officers_by_seniority():
        if officer.get("active") != 1:
            continue
        oids.append(officer["id"])
        create_notification(
            officer["id"],
            "schedule",
            "Schedule Published",
            message,
            related_id=snapshot_id,
            related_type="schedule_snapshot",
        )
    try:
        from logic.notify_channels import dispatch_template

        dispatch_template(
            "schedule_published",
            officer_ids=oids,
            prefer_sms=False,
            label=label,
        )
    except Exception:
        pass


def _notify_shift_swap_submitted(swap_id: int, officer1: Dict, officer2: Dict, swap_date: str, status: str) -> None:
    for officer in (officer1, officer2):
        create_notification(
            officer["id"],
            "shift_swap",
            "Swap Submitted",
            f"Shift swap with {officer2['name'] if officer['id'] == officer1['id'] else officer1['name']} on {format_date(swap_date)} ({status}).",
            swap_id,
            "shift_swap",
        )
    _notify_supervisors(
        "shift_swap",
        "New Shift Swap",
        f"{officer1['name']} ⇄ {officer2['name']} on {format_date(swap_date)}.",
        swap_id,
        "shift_swap",
    )


def _notify_supervisors(
    notification_type: str,
    title: str,
    message: str,
    related_id: Optional[int] = None,
    related_type: Optional[str] = None,
) -> None:
    notified: Set[int] = set()
    for officer_id in get_request_reviewer_officer_ids():
        if officer_id in notified:
            continue
        notified.add(officer_id)
        create_notification(
            officer_id,
            notification_type,
            title,
            message,
            related_id,
            related_type,
        )


def get_notification_types() -> List[str]:
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT type FROM notifications ORDER BY type")
        types = [row["type"] for row in cursor.fetchall()]
    return types


def get_unread_notification_count(officer_id: Optional[int] = None) -> int:
    with connection() as conn:
        cursor = conn.cursor()
        if officer_id:
            cursor.execute(
                "SELECT COUNT(*) FROM notifications WHERE recipient_officer_id = ? AND is_read = 0",
                (officer_id,),
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM notifications WHERE is_read = 0")
        count = cursor.fetchone()[0]
    return count
