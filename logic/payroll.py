"""Payroll entries, timecard, and pay-period management."""

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from config import (
    DATE_INPUT_HINT,
    FLOAT_HOLIDAY_ANNUAL_HOURS,
    HOLIDAY_ANNUAL_HOURS,
    PAY_PERIOD_BASE_DATE,
    PAY_PERIOD_LENGTH,
    PAYROLL_ENTRY_TYPES,
    ROTATION_CYCLE_LENGTH,
    SICK_MONTHLY_ACCRUAL_HOURS,
    TIMECARD_ENTRY_TYPES,
    TIMECARD_REGULAR_TYPE,
)
from database import get_connection
from logic.officers import get_officer_by_id, get_officers_by_seniority
from logic.operations import get_department_setting, set_department_setting
from logic.scheduling import (
    _officer_shift_hours,
    _officer_work_days_per_cycle,
    _shift_hours,
    get_current_cycle_window,
    is_officer_working_on_day,
)
from logic.users import log_audit_action
from models import PayCalculationResult
from validators import (
    format_date,
    is_overnight_shift,
    parse_date,
    storage_date_str,
)


def calculate_pay_for_entry(
    entry_type: str,
    hours: float,
    base_rate: float,
    night_differential_hours: float = 0.0,
    night_differential_rate: float = 1.0,
    is_holiday_overtime: bool = False,
    banks: Optional[Dict] = None,
) -> PayCalculationResult:
    result = PayCalculationResult(entry_type=entry_type)
    banks = banks or {}

    if entry_type == "Overtime Earned":
        result.overtime_hours = hours
        result.overtime_pay = round(hours * base_rate * 1.5, 2)
        result.total_pay = result.overtime_pay
    elif entry_type == "Comp Earned":
        result.regular_hours = hours
        result.base_pay = round(hours * base_rate, 2)
        result.comp_bank_delta = round(hours * 0.5, 2)
        result.total_pay = result.base_pay
    elif entry_type == "Comp Taken":
        if banks.get("comp_hours", 0) < hours:
            result.message = f"Insufficient comp bank ({banks.get('comp_hours', 0):.1f}h available)"
            return result
        result.regular_hours = hours
        result.base_pay = round(hours * base_rate, 2)
        result.comp_bank_delta = -hours
        result.total_pay = result.base_pay
    elif entry_type in ("Holiday Pay", "Holiday Overtime"):
        multiplier = 3.0 if (entry_type == "Holiday Overtime" and is_holiday_overtime) else 2.5
        result.overtime_hours = hours
        result.overtime_pay = round(hours * base_rate * multiplier, 2)
        result.total_pay = result.overtime_pay
    elif entry_type == "Holiday Comp Earned":
        result.regular_hours = hours
        result.base_pay = round(hours * base_rate, 2)
        result.comp_bank_delta = round(hours * 1.5, 2)
        result.total_pay = result.base_pay
    elif entry_type == "Holiday Overtime Comp Earned":
        result.regular_hours = hours
        result.base_pay = round(hours * base_rate, 2)
        result.comp_bank_delta = round(hours * 2.0, 2)
        result.total_pay = result.base_pay
    elif entry_type == "Sick Time Used":
        if banks.get("sick_hours", 0) < hours:
            result.message = f"Insufficient sick bank ({banks.get('sick_hours', 0):.1f}h available)"
            return result
        result.regular_hours = hours
        result.base_pay = round(hours * base_rate, 2)
        result.sick_bank_delta = -hours
        result.total_pay = result.base_pay
    elif entry_type == "Bereavement":
        result.regular_hours = hours
        result.base_pay = round(hours * base_rate, 2)
        result.total_pay = result.base_pay
    elif entry_type == "Training":
        result.regular_hours = hours
        result.base_pay = round(hours * base_rate, 2)
        result.total_pay = result.base_pay
    elif entry_type == "Unpaid":
        result.regular_hours = hours
        result.total_pay = 0.0
    elif entry_type == "Float Holiday Taken":
        if banks.get("float_holiday_hours", 0) < hours:
            result.message = f"Insufficient float holiday bank ({banks.get('float_holiday_hours', 0):.1f}h available)"
            return result
        result.regular_hours = hours
        result.base_pay = round(hours * base_rate, 2)
        result.float_holiday_bank_delta = -hours
        result.total_pay = result.base_pay
    elif entry_type == "Holiday Taken":
        if banks.get("holiday_hours", 0) < hours:
            result.message = f"Insufficient holiday bank ({banks.get('holiday_hours', 0):.1f}h available)"
            return result
        result.regular_hours = hours
        result.base_pay = round(hours * base_rate, 2)
        result.holiday_bank_delta = -hours
        result.total_pay = result.base_pay
    else:
        result.message = f"Unknown payroll entry type: {entry_type}"
        return result

    _apply_night_differential(result, night_differential_hours, base_rate, night_differential_rate)
    return result


def create_payroll_entry(
    officer_id: int,
    entry_date: str,
    entry_type: str,
    hours: float,
    night_differential_hours: float = 0.0,
    notes: str = "",
    is_holiday_overtime: bool = False,
) -> Dict:
    officer = get_officer_by_id(officer_id)
    if not officer:
        return {"success": False, "message": "Officer not found"}
    if hours <= 0:
        return {"success": False, "message": "Hours must be greater than zero"}

    try:
        parsed_date = parse_date(entry_date)
    except ValueError:
        return {"success": False, "message": f"Date must be {DATE_INPUT_HINT}"}

    if is_pay_period_locked(parsed_date):
        return {"success": False, "message": "Pay period is locked — payroll entries disabled"}

    conn = get_connection()
    cursor = conn.cursor()
    try:
        banks = _ensure_officer_time_banks(cursor, officer_id, parsed_date)
        calc = calculate_pay_for_entry(
            entry_type,
            hours,
            officer["pay_rate"],
            night_differential_hours=night_differential_hours,
            night_differential_rate=officer.get("night_differential_rate", 1.0),
            is_holiday_overtime=is_holiday_overtime,
            banks=banks,
        )
        if calc.message:
            conn.rollback()
            return {"success": False, "message": calc.message}

        cursor.execute(
            """
            INSERT INTO payroll_entries
            (officer_id, entry_date, entry_type, hours, night_differential_hours, calculated_pay,
             comp_bank_delta, sick_bank_delta, float_holiday_bank_delta, holiday_bank_delta, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                officer_id,
                entry_date,
                entry_type,
                hours,
                night_differential_hours,
                calc.total_pay,
                calc.comp_bank_delta,
                calc.sick_bank_delta,
                calc.float_holiday_bank_delta,
                calc.holiday_bank_delta,
                notes,
            ),
        )
        cursor.execute(
            """
            UPDATE officer_time_banks
            SET comp_hours = comp_hours + ?,
                sick_hours = sick_hours + ?,
                float_holiday_hours = float_holiday_hours + ?,
                holiday_hours = holiday_hours + ?
            WHERE officer_id = ?
        """,
            (
                calc.comp_bank_delta,
                calc.sick_bank_delta,
                calc.float_holiday_bank_delta,
                calc.holiday_bank_delta,
                officer_id,
            ),
        )
        conn.commit()
        return {
            "success": True,
            "entry_id": cursor.lastrowid,
            "calculated_pay": calc.total_pay,
            "breakdown": calc,
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def get_payroll_entries(
    officer_id: Optional[int] = None,
    limit: int = 100,
    period_start: Optional[date] = None,
) -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT p.*, o.name AS officer_name
        FROM payroll_entries p
        JOIN officers o ON p.officer_id = o.id
    """
    conditions: List[str] = []
    params: List = []
    if officer_id:
        conditions.append("p.officer_id = ?")
        params.append(officer_id)
    if period_start:
        start, end = get_pay_period(period_start)
        conditions.append("p.entry_date >= ? AND p.entry_date <= ?")
        params.extend([start.isoformat(), end.isoformat()])
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY p.entry_date DESC, p.id DESC LIMIT ?"
    params.append(limit)
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_pay_period(reference: Optional[date] = None) -> Tuple[date, date]:
    """Return start/end for the biweekly pay period containing reference (default today)."""
    ref = reference or date.today()
    period_index = (ref - PAY_PERIOD_BASE_DATE).days // PAY_PERIOD_LENGTH
    start = PAY_PERIOD_BASE_DATE + timedelta(days=period_index * PAY_PERIOD_LENGTH)
    end = start + timedelta(days=PAY_PERIOD_LENGTH - 1)
    return start, end


def pay_period_for_shift_start(shift_start_date: date) -> Tuple[date, date]:
    """Hours belong to the pay period in which the shift started."""
    return get_pay_period(shift_start_date)


def get_adjacent_pay_period(period_start: date, direction: int) -> Tuple[date, date]:
    """Return the pay period before (-1) or after (+1) the period containing period_start."""
    start, end = get_pay_period(period_start)
    if direction < 0:
        return get_pay_period(start - timedelta(days=1))
    if direction > 0:
        return get_pay_period(end + timedelta(days=1))
    return start, end


def get_adjacent_cycle_window(cycle_start: date, direction: int) -> Tuple[date, date]:
    """Return the rotation cycle before (-1) or after (+1) the cycle containing cycle_start."""
    start, end = get_current_cycle_window(cycle_start)
    if direction < 0:
        return get_current_cycle_window(start - timedelta(days=1))
    if direction > 0:
        return get_current_cycle_window(end + timedelta(days=1))
    return start, end


def is_future_cycle_window(cycle_start: date, reference: Optional[date] = None) -> bool:
    current_start, _ = get_current_cycle_window(reference)
    return cycle_start > current_start


def is_future_pay_period(period_start: date, reference: Optional[date] = None) -> bool:
    current_start, _ = get_pay_period(reference)
    norm_start, _ = get_pay_period(period_start)
    return norm_start > current_start


def lock_pay_period(period_start: Optional[date] = None, user_id: Optional[int] = None) -> Dict:
    from logic.requests import _notify_supervisors

    start, end = get_pay_period(period_start)
    set_department_setting("locked_pay_period_start", start.isoformat(), user_id)
    set_department_setting("locked_pay_period_end", end.isoformat(), user_id)
    log_audit_action("pay_period.lock", "pay_period", None, user_id, start.isoformat())
    _notify_supervisors(
        "Payroll",
        "Pay period locked",
        f"{format_date(start)} – {format_date(end)} is locked for edits and imports",
        related_type="pay_period",
    )
    return {"success": True, "period_start": start.isoformat(), "period_end": end.isoformat()}


def unlock_pay_period(user_id: Optional[int] = None) -> Dict:
    from logic.requests import _notify_supervisors

    set_department_setting("locked_pay_period_start", "", user_id)
    set_department_setting("locked_pay_period_end", "", user_id)
    log_audit_action("pay_period.unlock", "pay_period", None, user_id)
    _notify_supervisors("Payroll", "Pay period unlocked", "Timecard edits and imports are re-enabled")
    return {"success": True}


def is_pay_period_locked(period_start: Optional[date] = None) -> bool:
    start, _ = get_pay_period(period_start)
    locked = get_department_setting("locked_pay_period_start", "")
    return bool(locked) and locked == start.isoformat()


def get_pay_period_history(limit: int = 6, officer_id: Optional[int] = None) -> Dict:
    """Summarize recent pay periods from timecard and payroll data."""
    conn = get_connection()
    cursor = conn.cursor()
    if officer_id:
        cursor.execute(
            """
            SELECT pay_period_start AS period_start,
                   SUM(hours_worked) AS total_hours,
                   1 AS officer_count
            FROM timecard_entries
            WHERE officer_id = ?
            GROUP BY pay_period_start
            ORDER BY pay_period_start DESC
            LIMIT ?
        """,
            (officer_id, limit),
        )
    else:
        cursor.execute(
            """
            SELECT pay_period_start AS period_start,
                   SUM(hours_worked) AS total_hours,
                   COUNT(DISTINCT officer_id) AS officer_count
            FROM timecard_entries
            GROUP BY pay_period_start
            ORDER BY pay_period_start DESC
            LIMIT ?
        """,
            (limit,),
        )
    rows = [dict(r) for r in cursor.fetchall()]
    for row in rows:
        p_start = row["period_start"]
        _, p_end = get_pay_period(parse_date(p_start))
        row["period_end"] = p_end.isoformat()
        if officer_id:
            cursor.execute(
                """
                SELECT COALESCE(SUM(calculated_pay), 0) AS total_pay
                FROM payroll_entries
                WHERE officer_id = ? AND entry_date >= ? AND entry_date <= ?
            """,
                (officer_id, p_start, p_end.isoformat()),
            )
        else:
            cursor.execute(
                """
                SELECT COALESCE(SUM(calculated_pay), 0) AS total_pay
                FROM payroll_entries
                WHERE entry_date >= ? AND entry_date <= ?
            """,
                (p_start, p_end.isoformat()),
            )
        row["total_pay"] = round(cursor.fetchone()["total_pay"] or 0, 2)
        row["total_hours"] = round(row["total_hours"] or 0, 2)
        row["locked"] = is_pay_period_locked(parse_date(p_start))
    conn.close()
    return {"success": True, "periods": rows}


def save_timecard_entry(
    officer_id: int,
    entry_date: str,
    hours_worked: float,
    entry_type: str = TIMECARD_REGULAR_TYPE,
    time_in: str = "",
    time_out: str = "",
    night_diff_hours: float = 0.0,
    notes: str = "",
    period_start: Optional[str] = None,
    timecard_id: Optional[int] = None,
) -> Dict:
    officer = get_officer_by_id(officer_id)
    if not officer:
        return {"success": False, "message": "Officer not found"}
    if entry_type not in TIMECARD_ENTRY_TYPES:
        return {"success": False, "message": f"Invalid entry type: {entry_type}"}

    try:
        parsed = parse_date(entry_date)
    except ValueError:
        return {"success": False, "message": f"Entry date must be {DATE_INPUT_HINT}"}

    pay_start, pay_end = pay_period_for_shift_start(parsed)
    if is_pay_period_locked(pay_start):
        return {"success": False, "message": "Pay period is locked — timecard edits are disabled"}

    if period_start and storage_date_str(period_start) != pay_start.isoformat():
        return {
            "success": False,
            "message": (
                f"Shift start {format_date(parsed)} belongs to pay period "
                f"{format_date(pay_start)} – {format_date(pay_end)}, not the selected period"
            ),
        }
    pay_start_str = pay_start.isoformat()

    conn = get_connection()
    cursor = conn.cursor()
    try:
        if timecard_id is not None:
            cursor.execute(
                """
                SELECT id, payroll_entry_id FROM timecard_entries
                WHERE id = ? AND officer_id = ?
            """,
                (timecard_id, officer_id),
            )
            existing = cursor.fetchone()
            if not existing:
                return {"success": False, "message": "Timecard entry not found"}
            if existing["payroll_entry_id"]:
                return {"success": False, "message": "Entry already imported to payroll — cannot edit"}
            cursor.execute(
                """
                UPDATE timecard_entries
                SET pay_period_start = ?, entry_date = ?, hours_worked = ?, time_in = ?, time_out = ?,
                    entry_type = ?, night_diff_hours = ?, notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (
                    pay_start_str,
                    entry_date,
                    hours_worked,
                    time_in or None,
                    time_out or None,
                    entry_type,
                    night_diff_hours,
                    notes or None,
                    timecard_id,
                ),
            )
            entry_id = timecard_id
        else:
            cursor.execute(
                """
                INSERT INTO timecard_entries
                (officer_id, pay_period_start, entry_date, hours_worked, time_in, time_out,
                 entry_type, night_diff_hours, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    officer_id,
                    pay_start_str,
                    entry_date,
                    hours_worked,
                    time_in or None,
                    time_out or None,
                    entry_type,
                    night_diff_hours,
                    notes or None,
                ),
            )
            entry_id = cursor.lastrowid
        conn.commit()
        result = {"success": True, "timecard_id": entry_id}
        if is_overnight_shift(time_in, time_out):
            result["overnight"] = True
            result["message"] = (
                f"Overnight shift saved — all hours count in pay period "
                f"{format_date(pay_start)} – {format_date(pay_end)} (shift start date)"
            )
        return result
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def delete_timecard_entry(timecard_id: int, officer_id: int) -> Dict:
    """Remove a timecard row (e.g. extra pay-type line on the same day)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, payroll_entry_id, pay_period_start FROM timecard_entries
            WHERE id = ? AND officer_id = ?
        """,
            (timecard_id, officer_id),
        )
        row = cursor.fetchone()
        if not row:
            return {"success": False, "message": "Timecard entry not found"}
        if row["payroll_entry_id"]:
            return {"success": False, "message": "Entry already imported to payroll — cannot delete"}
        if is_pay_period_locked(parse_date(row["pay_period_start"])):
            return {"success": False, "message": "Pay period is locked — timecard edits are disabled"}
        cursor.execute("DELETE FROM timecard_entries WHERE id = ?", (timecard_id,))
        conn.commit()
        return {"success": True, "message": "Timecard entry removed"}
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def _apply_night_differential(
    result: PayCalculationResult,
    night_differential_hours: float,
    base_rate: float,
    night_differential_rate: float,
) -> None:
    result.night_differential_hours = night_differential_hours
    result.night_differential_pay = round(night_differential_hours * (base_rate + night_differential_rate), 2)
    result.total_pay += result.night_differential_pay


def _ensure_officer_time_banks(cursor, officer_id: int, as_of: date) -> Dict:
    cursor.execute("SELECT * FROM officer_time_banks WHERE officer_id = ?", (officer_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute(
            """
            INSERT INTO officer_time_banks
            (officer_id, comp_hours, sick_hours, float_holiday_hours, holiday_hours,
             sick_accrual_month, annual_accrual_year)
            VALUES (?, 0, 0, 0, 0, NULL, NULL)
        """,
            (officer_id,),
        )
        cursor.execute("SELECT * FROM officer_time_banks WHERE officer_id = ?", (officer_id,))
        row = cursor.fetchone()

    banks = dict(row)
    month_key = as_of.strftime("%Y-%m")
    year_key = as_of.year

    sick_delta = 0.0
    last_month = banks.get("sick_accrual_month")
    if last_month is None:
        sick_delta = SICK_MONTHLY_ACCRUAL_HOURS
        banks["sick_accrual_month"] = month_key
    elif last_month < month_key:
        sick_delta = SICK_MONTHLY_ACCRUAL_HOURS * _months_between(last_month, month_key)
        banks["sick_accrual_month"] = month_key

    float_delta = 0.0
    holiday_delta = 0.0
    last_year = banks.get("annual_accrual_year")
    if last_year is None:
        float_delta = FLOAT_HOLIDAY_ANNUAL_HOURS
        holiday_delta = HOLIDAY_ANNUAL_HOURS
        banks["annual_accrual_year"] = year_key
    elif last_year < year_key:
        years = year_key - last_year
        float_delta = FLOAT_HOLIDAY_ANNUAL_HOURS * years
        holiday_delta = HOLIDAY_ANNUAL_HOURS * years
        banks["annual_accrual_year"] = year_key

    if sick_delta or float_delta or holiday_delta:
        cursor.execute(
            """
            UPDATE officer_time_banks
            SET sick_hours = sick_hours + ?,
                float_holiday_hours = float_holiday_hours + ?,
                holiday_hours = holiday_hours + ?,
                sick_accrual_month = ?,
                annual_accrual_year = ?
            WHERE officer_id = ?
        """,
            (
                sick_delta,
                float_delta,
                holiday_delta,
                banks["sick_accrual_month"],
                banks["annual_accrual_year"],
                officer_id,
            ),
        )
        cursor.execute("SELECT * FROM officer_time_banks WHERE officer_id = ?", (officer_id,))
        banks = dict(cursor.fetchone())

    return banks


def _months_between(start_ym: str, end_ym: str) -> int:
    start_year, start_month = map(int, start_ym.split("-"))
    end_year, end_month = map(int, end_ym.split("-"))
    return (end_year - start_year) * 12 + (end_month - start_month)


def bulk_adjust_pay_rates(
    percent_change: float = 0.0,
    flat_amount: float = 0.0,
    squad: Optional[str] = None,
) -> Dict:
    if percent_change == 0 and flat_amount == 0:
        return {"success": False, "message": "Provide a percent change or flat amount"}

    conn = get_connection()
    cursor = conn.cursor()
    try:
        if squad in ("A", "B"):
            cursor.execute(
                """
                UPDATE officers
                SET pay_rate = ROUND(pay_rate * ? + ?, 2)
                WHERE active = 1 AND squad = ?
            """,
                (1 + percent_change / 100, flat_amount, squad),
            )
        else:
            cursor.execute(
                """
                UPDATE officers
                SET pay_rate = ROUND(pay_rate * ? + ?, 2)
                WHERE active = 1
            """,
                (1 + percent_change / 100, flat_amount),
            )
        updated = cursor.rowcount
        conn.commit()
        return {"success": True, "updated": updated, "message": f"Updated pay rates for {updated} officer(s)"}
    except Exception as e:
        conn.rollback()
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def copy_timecard_from_previous_period(
    officer_id: int,
    period_start: Optional[date] = None,
) -> Dict:
    """Copy prior pay period timecard rows into the current period (same cycle offsets)."""
    start, end = get_pay_period(period_start)
    if is_pay_period_locked(start):
        return {"success": False, "message": "Pay period is locked"}

    prev_start, _ = get_adjacent_pay_period(start, -1)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM timecard_entries
        WHERE officer_id = ? AND pay_period_start = ?
        ORDER BY entry_date
    """,
        (officer_id, prev_start.isoformat()),
    )
    prev_rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    if not prev_rows:
        return {"success": False, "message": "No timecard data in previous pay period"}

    copied = 0
    skipped = 0
    for row in prev_rows:
        src = parse_date(row["entry_date"])
        target = src + timedelta(days=PAY_PERIOD_LENGTH)
        if target > end or target < start:
            skipped += 1
            continue
        target_str = target.isoformat()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT payroll_entry_id FROM timecard_entries
            WHERE officer_id = ? AND entry_date = ?
        """,
            (officer_id, target_str),
        )
        existing = cursor.fetchone()
        conn.close()
        if existing and existing["payroll_entry_id"]:
            skipped += 1
            continue
        result = save_timecard_entry(
            officer_id,
            target_str,
            row.get("hours_worked") or 0.0,
            row.get("entry_type") or TIMECARD_REGULAR_TYPE,
            row.get("time_in") or "",
            row.get("time_out") or "",
            row.get("night_diff_hours") or 0.0,
            row.get("notes") or "",
            period_start=start.isoformat(),
        )
        if result.get("success"):
            copied += 1

    return {
        "success": True,
        "copied": copied,
        "skipped": skipped,
        "message": f"Copied {copied} day(s) from previous pay period",
    }


def get_pay_stub_preview(officer_id: int, period_start: Optional[date] = None) -> Dict:
    from analytics import get_pay_stub_preview as _stub

    return _stub(officer_id, period_start)


def _summarize_pay_period_hours(
    timecard_rows: List[Dict],
    payroll_rows: List[Dict],
) -> Dict:
    """Aggregate hours from timecard rows plus payroll-only entries (not imported from timecard)."""
    by_type = {entry_type: 0.0 for entry_type in TIMECARD_ENTRY_TYPES}
    imported_payroll_ids = {row["payroll_entry_id"] for row in timecard_rows if row.get("payroll_entry_id")}
    total_hours = 0.0
    night_diff_hours = 0.0

    for row in timecard_rows:
        entry_type = row.get("entry_type") or TIMECARD_REGULAR_TYPE
        hours = float(row.get("hours_worked") or 0)
        if entry_type not in by_type:
            by_type[entry_type] = 0.0
        by_type[entry_type] += hours
        total_hours += hours
        night_diff_hours += float(row.get("night_diff_hours") or 0)

    for row in payroll_rows:
        if row.get("id") in imported_payroll_ids:
            continue
        entry_type = row.get("entry_type") or TIMECARD_REGULAR_TYPE
        hours = float(row.get("hours") or 0)
        if entry_type not in by_type:
            by_type[entry_type] = 0.0
        by_type[entry_type] += hours
        total_hours += hours
        night_diff_hours += float(row.get("night_differential_hours") or 0)

    return {
        "total_hours": round(total_hours, 2),
        "night_diff_hours": round(night_diff_hours, 2),
        "by_entry_type": {key: round(value, 2) for key, value in by_type.items()},
    }


def get_pay_period_hours_summary(
    period_start: Optional[date] = None,
    officer_id: Optional[int] = None,
) -> Dict:
    """Hour totals for a pay period, broken down by classification and night differential."""
    start, end = get_pay_period(period_start)
    start_str = start.isoformat()
    end_str = end.isoformat()

    conn = get_connection()
    cursor = conn.cursor()
    if officer_id:
        cursor.execute(
            """
            SELECT hours_worked, entry_type, night_diff_hours, payroll_entry_id
            FROM timecard_entries
            WHERE pay_period_start = ? AND officer_id = ?
        """,
            (start_str, officer_id),
        )
    else:
        cursor.execute(
            """
            SELECT hours_worked, entry_type, night_diff_hours, payroll_entry_id
            FROM timecard_entries
            WHERE pay_period_start = ?
        """,
            (start_str,),
        )
    timecard_rows = [dict(row) for row in cursor.fetchall()]

    if officer_id:
        cursor.execute(
            """
            SELECT id, hours, entry_type, night_differential_hours
            FROM payroll_entries
            WHERE officer_id = ? AND entry_date >= ? AND entry_date <= ?
        """,
            (officer_id, start_str, end_str),
        )
    else:
        cursor.execute(
            """
            SELECT id, hours, entry_type, night_differential_hours
            FROM payroll_entries
            WHERE entry_date >= ? AND entry_date <= ?
        """,
            (start_str, end_str),
        )
    payroll_rows = [dict(row) for row in cursor.fetchall()]
    conn.close()

    summary = _summarize_pay_period_hours(timecard_rows, payroll_rows)
    return {
        "success": True,
        "period_start": start_str,
        "period_end": end_str,
        **summary,
    }


def get_payroll_period_timesheets(period_start: Optional[date] = None) -> Dict:
    start, end = get_pay_period(period_start)
    start_str = start.isoformat()
    end_str = end.isoformat()
    officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
    sheets = []
    grand_hours = 0.0
    grand_pay = 0.0

    conn = get_connection()
    cursor = conn.cursor()
    for officer in officers:
        cursor.execute(
            """
            SELECT * FROM timecard_entries
            WHERE officer_id = ? AND pay_period_start = ?
            ORDER BY entry_date
        """,
            (officer["id"], start_str),
        )
        timecard_rows = [dict(r) for r in cursor.fetchall()]
        cursor.execute(
            """
            SELECT * FROM payroll_entries
            WHERE officer_id = ? AND entry_date >= ? AND entry_date <= ?
            ORDER BY entry_date
        """,
            (officer["id"], start_str, end_str),
        )
        payroll_rows = [dict(r) for r in cursor.fetchall()]
        total_hours = sum(r.get("hours_worked") or 0 for r in timecard_rows)
        total_pay = sum(r.get("calculated_pay") or 0 for r in payroll_rows)
        grand_hours += total_hours
        grand_pay += total_pay
        sheets.append(
            {
                "officer": officer,
                "total_hours": round(total_hours, 2),
                "total_pay": round(total_pay, 2),
                "timecard_rows": timecard_rows,
                "payroll_rows": payroll_rows,
            }
        )
    conn.close()

    return {
        "success": True,
        "period_start": start_str,
        "period_end": end_str,
        "sheets": sheets,
        "grand_total_hours": round(grand_hours, 2),
        "grand_total_pay": round(grand_pay, 2),
    }


def get_timecard_period(
    officer_id: int,
    period_start: Optional[date] = None,
) -> Dict:
    officer = get_officer_by_id(officer_id)
    if not officer:
        return {"success": False, "message": "Officer not found"}

    start, end = get_pay_period(period_start)
    start_str = start.isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM timecard_entries
        WHERE officer_id = ? AND pay_period_start = ?
        ORDER BY entry_date, id
    """,
        (officer_id, start_str),
    )
    saved_by_date: Dict[str, List[Dict]] = {}
    for row in cursor.fetchall():
        saved_by_date.setdefault(row["entry_date"], []).append(dict(row))
    conn.close()

    def _entry_payload(row: Dict, scheduled: bool, default_hours: float) -> Dict:
        time_in = row.get("time_in") or (officer["shift_start"] if scheduled else "")
        time_out = row.get("time_out") or (officer["shift_end"] if scheduled else "")
        return {
            "timecard_id": row.get("id"),
            "hours_worked": row.get("hours_worked", default_hours if scheduled else 0.0),
            "time_in": time_in,
            "time_out": time_out,
            "overnight": is_overnight_shift(time_in, time_out),
            "entry_type": row.get("entry_type") or TIMECARD_REGULAR_TYPE,
            "night_diff_hours": row.get("night_diff_hours") or 0.0,
            "notes": row.get("notes") or "",
            "imported": bool(row.get("payroll_entry_id")),
        }

    days = []
    current = start
    while current <= end:
        key = current.isoformat()
        scheduled = is_officer_working_on_day(officer_id, current)
        default_hours = _shift_hours(officer["shift_start"], officer["shift_end"]) if scheduled else 0.0
        saved_rows = saved_by_date.get(key, [])
        if saved_rows:
            entries = [_entry_payload(row, scheduled, default_hours) for row in saved_rows]
        else:
            entries = [_entry_payload({}, scheduled, default_hours)]
        primary = entries[0]
        days.append(
            {
                "entry_date": key,
                "day_label": f"{current.strftime('%a')} {format_date(current)}",
                "scheduled": scheduled,
                "entries": entries,
                "hours_worked": primary["hours_worked"],
                "time_in": primary["time_in"],
                "time_out": primary["time_out"],
                "overnight": primary["overnight"],
                "entry_type": primary["entry_type"],
                "night_diff_hours": primary["night_diff_hours"],
                "notes": primary["notes"],
                "imported": primary["imported"],
                "timecard_id": primary.get("timecard_id"),
            }
        )
        current += timedelta(days=1)

    return {
        "success": True,
        "officer": officer,
        "period_start": start_str,
        "period_end": end.isoformat(),
        "days": days,
    }


def import_timecard_to_payroll(
    officer_id: int,
    period_start: Optional[str] = None,
) -> Dict:
    start, _ = get_pay_period(parse_date(period_start) if period_start else None)
    if is_pay_period_locked(start):
        return {"success": False, "message": "Pay period is locked — import disabled"}
    start_str = start.isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM timecard_entries
        WHERE officer_id = ? AND pay_period_start = ?
          AND payroll_entry_id IS NULL
          AND entry_type != ?
          AND hours_worked > 0
    """,
        (officer_id, start_str, TIMECARD_REGULAR_TYPE),
    )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    if not rows:
        return {"success": False, "message": "No payable timecard rows to import"}

    imported = 0
    errors = []
    for row in rows:
        if row["entry_type"] not in PAYROLL_ENTRY_TYPES:
            continue
        result = create_payroll_entry(
            officer_id,
            row["entry_date"],
            row["entry_type"],
            row["hours_worked"],
            night_differential_hours=row.get("night_diff_hours") or 0.0,
            notes=row.get("notes") or "Imported from timecard",
        )
        if not result.get("success"):
            errors.append(f"{row['entry_date']}: {result.get('message')}")
            continue
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE timecard_entries
            SET payroll_entry_id = ?, imported_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (result["entry_id"], row["id"]),
        )
        conn.commit()
        conn.close()
        imported += 1

    if imported == 0:
        return {"success": False, "message": errors[0] if errors else "Import failed"}
    return {
        "success": True,
        "imported": imported,
        "message": f"Imported {imported} row(s) to payroll",
        "errors": errors,
    }


def prefill_timecard_from_schedule(
    officer_id: int,
    period_start: Optional[date] = None,
) -> Dict:
    """Save default scheduled hours for working days not yet imported to payroll."""
    start, _ = get_pay_period(period_start)
    if is_pay_period_locked(start):
        return {"success": False, "message": "Pay period is locked"}

    data = get_timecard_period(officer_id, start)
    if not data.get("success"):
        return data

    saved = 0
    skipped = 0
    for day in data["days"]:
        if any(e.get("imported") for e in day.get("entries", [])):
            skipped += 1
            continue
        if not day.get("scheduled"):
            continue
        if any(e.get("timecard_id") for e in day.get("entries", [])):
            continue
        primary = day["entries"][0]
        result = save_timecard_entry(
            officer_id,
            day["entry_date"],
            primary["hours_worked"],
            primary.get("entry_type") or TIMECARD_REGULAR_TYPE,
            primary.get("time_in") or "",
            primary.get("time_out") or "",
            primary.get("night_diff_hours") or 0.0,
            primary.get("notes") or "",
            period_start=start.isoformat(),
        )
        if result.get("success"):
            saved += 1

    return {
        "success": True,
        "saved": saved,
        "skipped_imported": skipped,
        "message": f"Prefilled {saved} scheduled day(s) from rotation",
    }


def project_officer_annual_pay(officer_id: int) -> Dict:
    officer = get_officer_by_id(officer_id)
    if not officer:
        return {"success": False, "message": "Officer not found"}

    shift_hours = _officer_shift_hours(officer)
    work_days = _officer_work_days_per_cycle(officer)
    annual_hours = round(work_days / ROTATION_CYCLE_LENGTH * 365 * shift_hours, 1)
    target = officer.get("annual_hours_target") or 2080.0
    base_pay = round(annual_hours * officer["pay_rate"], 2)
    ot_multiplier = officer.get("overtime_multiplier") or 1.5
    overtime_hours = max(0.0, annual_hours - target)
    overtime_pay = round(overtime_hours * officer["pay_rate"] * ot_multiplier, 2)

    return {
        "success": True,
        "officer_id": officer_id,
        "annual_hours": annual_hours,
        "annual_hours_target": target,
        "shift_hours": shift_hours,
        "work_days_per_cycle": work_days,
        "base_annual_pay": base_pay,
        "overtime_hours": round(overtime_hours, 1),
        "overtime_pay": overtime_pay,
        "total_annual_pay": round(base_pay + overtime_pay, 2),
        "hours_vs_target": round(annual_hours - target, 1),
    }
