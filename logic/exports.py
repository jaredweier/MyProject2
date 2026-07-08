"""PDF, CSV, and iCal export wrappers (exports-ical slice)."""

import os
from datetime import date
from typing import Dict, Optional

from logic.officers import get_officer_by_id
from logic.payroll import get_pay_period, get_pay_stub_preview, get_payroll_entries
from logic.scheduling import build_schedule_matrix, get_current_cycle_window
from logic.snapshots import get_officer_schedule_window
from validators import format_date


def export_schedule_pdf(
    start_date: date,
    end_date: date,
    officer_id: Optional[int] = None,
    output_path: Optional[str] = None,
) -> Dict:
    from exports import generate_schedule_pdf
    from paths import data_path, ensure_data_dirs

    ensure_data_dirs()
    matrix, days = build_schedule_matrix(start_date, end_date)
    if officer_id:
        matrix = [e for e in matrix if e["officer"]["id"] == officer_id]
    if not matrix:
        return {"success": False, "message": "No schedule data for export"}
    if not output_path:
        suffix = f"_officer_{officer_id}" if officer_id else ""
        output_path = data_path(f"exports/schedule_{format_date(start_date)}_{format_date(end_date)}{suffix}.pdf")
    title = f"Dodgeville PD Schedule {format_date(start_date)} – {format_date(end_date)}"
    if officer_id:
        officer = get_officer_by_id(officer_id)
        if officer:
            title = f"{officer['name']} — {title}"
    return generate_schedule_pdf(matrix, days, output_path, title=title)


def export_audit_csv(
    output_path: Optional[str] = None,
    limit: int = 500,
    action_filter: Optional[str] = None,
) -> Dict:
    from logic.analytics import export_audit_csv as _export

    return _export(output_path, limit, action_filter=action_filter)


def export_coverage_pdf(
    start_date: date,
    end_date: date,
    output_path: Optional[str] = None,
) -> Dict:
    from exports import generate_coverage_pdf
    from logic.dashboard import get_coverage_report
    from paths import data_path, ensure_data_dirs

    ensure_data_dirs()
    report = get_coverage_report(start_date, end_date)
    if not report.get("success"):
        return report
    if not output_path:
        output_path = data_path(f"exports/coverage_{format_date(start_date)}_{format_date(end_date)}.pdf")
    return generate_coverage_pdf(report, output_path)


def export_officer_schedule_ical(
    officer_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    output_path: Optional[str] = None,
) -> Dict:
    from paths import data_path, ensure_data_dirs

    officer = get_officer_by_id(officer_id)
    if not officer:
        return {"success": False, "message": "Officer not found"}

    if start_date is None or end_date is None:
        start_date, end_date = get_current_cycle_window(start_date)

    days_count = (end_date - start_date).days + 1
    window = get_officer_schedule_window(officer_id, start_date, days_count)
    if not window.get("success"):
        return window
    ensure_data_dirs()
    if not output_path:
        output_path = data_path(f"exports/schedule_{officer_id}_{format_date(start_date)}_{format_date(end_date)}.ics")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Dodgeville PD Scheduler//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{officer['name']} Schedule",
    ]
    for day in window.get("days", []):
        if day.get("status") not in ("working", "covering"):
            continue
        day_date = day["date"]
        shift_start = officer["shift_start"]
        shift_end = officer["shift_end"]
        uid = f"dpd-{officer_id}-{day_date}@dodgeville.local"
        dt = day_date.replace("-", "")
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTART;VALUE=DATE:{dt}",
                f"SUMMARY:{officer['name']} — {day.get('status', 'shift').title()} {shift_start}-{shift_end}",
                f"DESCRIPTION:Squad {officer['squad']} · {day.get('status', '')}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("\r\n".join(lines) + "\r\n")
    return {"success": True, "path": output_path, "message": "Calendar exported"}


def export_pay_period_history_csv(
    limit: int = 12,
    officer_id: Optional[int] = None,
    output_path: Optional[str] = None,
) -> Dict:
    from logic.analytics import export_pay_period_history_csv as _export

    return _export(limit, officer_id, output_path)


def export_pay_stub_pdf(
    officer_id: int,
    period_start: Optional[date] = None,
    output_path: Optional[str] = None,
) -> Dict:
    from exports import generate_pay_stub_pdf
    from paths import data_path, ensure_data_dirs

    ensure_data_dirs()
    stub = get_pay_stub_preview(officer_id, period_start)
    if not stub.get("success"):
        return stub
    officer = stub["officer"]
    if not output_path:
        output_path = data_path(f"exports/pay_stub_{officer['id']}_{stub['period_start']}.pdf")
    return generate_pay_stub_pdf(stub, output_path)


def export_payroll_csv(
    period_start: Optional[date] = None,
    officer_id: Optional[int] = None,
    output_path: Optional[str] = None,
) -> Dict:
    from logic.analytics import export_payroll_csv as _export

    return _export(period_start, officer_id, output_path)


def export_payroll_pdf(
    officer_id: Optional[int] = None,
    period_start: Optional[date] = None,
    output_path: Optional[str] = None,
) -> Dict:
    from exports import generate_payroll_pdf
    from paths import data_path, ensure_data_dirs

    ensure_data_dirs()
    entries = get_payroll_entries(
        officer_id=officer_id,
        limit=500,
        period_start=period_start,
    )
    if not output_path:
        start, end = get_pay_period(period_start)
        suffix = f"officer_{officer_id}" if officer_id else "all"
        output_path = data_path(f"exports/payroll_{suffix}_{format_date(start)}_{format_date(end)}.pdf")
    start, end = get_pay_period(period_start)
    title = f"Payroll Ledger — {format_date(start)} to {format_date(end)}"
    return generate_payroll_pdf(entries, output_path, title=title)


def export_requests_csv(
    status_filter: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    officer_id: Optional[int] = None,
    output_path: Optional[str] = None,
) -> Dict:
    from logic.analytics import export_requests_csv as _export

    return _export(status_filter, date_from, date_to, officer_id, output_path)


def export_requests_pdf(
    status_filter: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    officer_id: Optional[int] = None,
    output_path: Optional[str] = None,
) -> Dict:
    from exports import generate_requests_pdf
    from logic.requests import get_day_off_requests
    from paths import data_path, ensure_data_dirs

    ensure_data_dirs()
    requests = get_day_off_requests(
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        officer_id=officer_id,
    )
    if not output_path:
        output_path = data_path(f"exports/requests_{format_date(date.today())}.pdf")
    return generate_requests_pdf(requests, output_path)


def export_roster_csv(output_path: Optional[str] = None) -> Dict:
    from logic.analytics import export_roster_csv as _export

    return _export(output_path)


def export_schedule_diff_csv(
    year: int,
    month: int,
    output_path: Optional[str] = None,
    officer_id: Optional[int] = None,
) -> Dict:
    from logic.analytics import export_schedule_diff_csv as _export

    return _export(year, month, output_path, officer_id=officer_id)


def export_shift_swaps_csv(
    status_filter: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    officer_id: Optional[int] = None,
    pending_only: bool = False,
    output_path: Optional[str] = None,
) -> Dict:
    from logic.analytics import export_shift_swaps_csv as _export

    return _export(status_filter, date_from, date_to, officer_id, pending_only, output_path)


def export_shift_swaps_pdf(
    status_filter: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    officer_id: Optional[int] = None,
    pending_only: bool = False,
    output_path: Optional[str] = None,
) -> Dict:
    from exports import generate_shift_swaps_pdf
    from logic.requests import get_shift_swap_requests
    from paths import data_path, ensure_data_dirs

    ensure_data_dirs()
    swaps = get_shift_swap_requests(
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        pending_only=pending_only,
        officer_id=officer_id,
    )
    if not output_path:
        output_path = data_path(f"exports/shift_swaps_{format_date(date.today())}.pdf")
    return generate_shift_swaps_pdf(swaps, output_path)


def export_simulation_csv(
    result: Dict,
    output_path: Optional[str] = None,
) -> Dict:
    from logic.analytics import export_simulation_csv as _export

    return _export(result, output_path)


def export_timecard_csv(
    period_start: Optional[date] = None,
    officer_id: Optional[int] = None,
    output_path: Optional[str] = None,
) -> Dict:
    from logic.analytics import export_timecard_csv as _export

    return _export(period_start, officer_id, output_path)
