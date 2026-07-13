"""CLI handlers — export cmds."""

from __future__ import annotations

from datetime import date

from logic import (
    compare_base_updated_schedule,
    export_coverage_pdf,
    export_officer_schedule_ical,
    export_pay_period_history_csv,
    export_payroll_csv,
    export_payroll_pdf,
    export_requests_csv,
    export_requests_pdf,
    export_roster_csv,
    export_schedule_diff_csv,
    export_schedule_pdf,
    export_shift_swaps_csv,
    export_shift_swaps_pdf,
    export_timecard_csv,
    get_current_cycle_window,
)
from validators import parse_date


def export_coverage(args):
    if args.start and args.end:
        start, end = parse_date(args.start), parse_date(args.end)
    else:
        start, end = get_current_cycle_window()
    result = export_coverage_pdf(start, end, output_path=args.output)
    if result.get("success"):
        print(f"Coverage PDF: {result['path']}")
    else:
        print(f"Failed: {result.get('message')}")


def export_schedule(args):
    if args.start and args.end:
        start = parse_date(args.start)
        end = parse_date(args.end)
    else:
        start, end = get_current_cycle_window()
    result = export_schedule_pdf(
        start,
        end,
        officer_id=args.officer_id,
        output_path=args.output,
    )
    if result.get("success"):
        print(f"Schedule PDF: {result['path']}")
    else:
        print(f"Failed: {result.get('message')}")


def export_payroll(args):
    period_start = parse_date(args.period_start) if args.period_start else None
    result = export_payroll_pdf(
        officer_id=args.officer_id,
        period_start=period_start,
        output_path=args.output,
    )
    if result.get("success"):
        print(f"Payroll PDF: {result['path']}")
    else:
        print(f"Failed: {result.get('message')}")


def export_requests(args):
    result = export_requests_pdf(
        status_filter=args.status,
        date_from=args.from_date,
        date_to=args.to_date,
        officer_id=args.officer_id,
        output_path=args.output,
    )
    if result.get("success"):
        print(f"Requests PDF: {result['path']}")
    else:
        print(f"Failed: {result.get('message')}")


def export_swaps_pdf_cmd(args):
    status = None
    pending_only = False
    if args.status:
        val = args.status.lower()
        if val == "all":
            status = None
        elif val == "pending":
            pending_only = True
        else:
            status = args.status
    result = export_shift_swaps_pdf(
        status_filter=status,
        date_from=args.from_date,
        date_to=args.to_date,
        officer_id=args.officer_id,
        pending_only=pending_only,
        output_path=args.output,
    )
    if result.get("success"):
        print(f"Shift swaps PDF: {result['path']}")
    else:
        print(f"Failed: {result.get('message')}")


def export_roster(args):
    result = export_roster_csv(output_path=args.output)
    if result.get("success"):
        print(f"Roster CSV: {result['path']} ({result['count']} rows)")
    else:
        print(f"Failed: {result.get('message')}")


def schedule_diff_cmd(args):
    year = args.year or date.today().year
    month = args.month or date.today().month
    if args.output:
        result = export_schedule_diff_csv(
            year,
            month,
            args.output,
            officer_id=args.officer_id,
        )
        if result.get("success"):
            print(f"Schedule diff CSV: {result['path']} ({result['count']} rows)")
        else:
            print(f"Failed: {result.get('message')}")
        return
    result = compare_base_updated_schedule(year, month, officer_id=args.officer_id)
    if not result.get("success"):
        print(f"Failed: {result.get('message')}")
        return
    print(f"Base vs Updated — {year}-{month:02d}: {result['diff_count']} change(s)")
    for item in result.get("diffs", [])[: args.limit]:
        print(
            f"  {item['assignment_date']}  {item['officer_name']:<20}  "
            f"{item['base_status'] or '—'} → {item['updated_status'] or '—'}"
        )


def export_payroll_csv_cmd(args):
    period = parse_date(args.period_start) if args.period_start else None
    result = export_payroll_csv(
        period_start=period,
        officer_id=args.officer_id,
        output_path=args.output,
    )
    if result.get("success"):
        print(f"Payroll CSV: {result['path']} ({result['count']} rows)")
    else:
        print(f"Failed: {result.get('message')}")


def export_requests_csv_cmd(args):
    status = None if not args.status or args.status.lower() == "all" else args.status
    result = export_requests_csv(
        status_filter=status,
        date_from=args.from_date,
        date_to=args.to_date,
        officer_id=args.officer_id,
        output_path=args.output,
    )
    if result.get("success"):
        print(f"Requests CSV: {result['path']} ({result['count']} rows)")
    else:
        print(f"Failed: {result.get('message')}")


def export_pay_period_history_csv_cmd(args):
    result = export_pay_period_history_csv(
        limit=args.limit,
        officer_id=args.officer_id,
        output_path=args.output,
    )
    if result.get("success"):
        print(f"Pay period history CSV: {result['path']} ({result['count']} rows)")
    else:
        print(f"Failed: {result.get('message')}")


def export_timecard_csv_cmd(args):
    period = parse_date(args.period_start) if args.period_start else None
    result = export_timecard_csv(
        period_start=period,
        officer_id=args.officer_id,
        output_path=args.output,
    )
    if result.get("success"):
        print(f"Timecard CSV: {result['path']} ({result['count']} rows)")
    else:
        print(f"Failed: {result.get('message')}")


def export_shift_swaps_csv_cmd(args):
    status = None
    pending_only = False
    if args.status:
        val = args.status.lower()
        if val == "all":
            status = None
        elif val == "pending":
            pending_only = True
        else:
            status = args.status
    result = export_shift_swaps_csv(
        status_filter=status,
        date_from=args.from_date,
        date_to=args.to_date,
        officer_id=args.officer_id,
        pending_only=pending_only,
        output_path=args.output,
    )
    if result.get("success"):
        print(f"Shift swaps CSV: {result['path']} ({result['count']} rows)")
    else:
        print(f"Failed: {result.get('message')}")


def export_ical_cmd(args):
    if args.start and args.end:
        start = parse_date(args.start)
        end = parse_date(args.end)
    else:
        start, end = get_current_cycle_window()
    result = export_officer_schedule_ical(
        args.officer_id,
        start_date=start,
        end_date=end,
        output_path=args.output,
    )
    if result.get("success"):
        print(f"iCal: {result['path']}")
    else:
        print(f"Failed: {result.get('message')}")
