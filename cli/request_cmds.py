"""CLI handlers — request cmds."""

from __future__ import annotations

from logic import (
    create_day_off_request,
    get_day_off_requests,
    get_pending_day_off_requests,
    process_day_off_request,
)
from validators import format_date


def _print_requests_table(requests, empty_msg: str = "No requests."):
    if not requests:
        print(empty_msg)
        return
    print(f"{'ID':<5} {'Date':<12} {'Type':<18} {'Officer':<25} {'Squad':<6} {'Status':<20}")
    print("-" * 90)
    for r in requests:
        print(
            f"{r['id']:<5} {format_date(r['request_date']):<12} {r['request_type']:<18} "
            f"{r['officer_name']:<25} {r['squad']:<6} {r['status']:<20}"
        )


def list_pending_requests():
    _print_requests_table(get_pending_day_off_requests(), "No pending requests.")


def list_requests(args):
    status = None if args.status in (None, "all") else args.status
    requests = get_day_off_requests(
        status_filter=status,
        date_from=args.from_date,
        date_to=args.to_date,
    )
    _print_requests_table(requests, "No matching requests.")


def approve_request(request_id: int):
    result = process_day_off_request(request_id, action="approve")
    if result.success:
        print(result.message)
    elif result.requires_manual:
        print(f"Manual review required: {result.message}")
    else:
        print(f"Failed: {result.message}")


def reject_request(request_id: int):
    result = process_day_off_request(request_id, action="reject")
    print(result.message if result.success else f"Failed: {result.message}")


def submit_request_cmd(args):
    result = create_day_off_request(
        args.officer_id,
        args.date,
        args.type,
        notes=args.notes or "",
    )
    if result.get("success"):
        print(f"Request submitted (ID: {result['request_id']})")
    else:
        print(f"Error: {result.get('message', 'Unknown error')}")
