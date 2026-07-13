"""CLI handlers — swap cmds."""

from __future__ import annotations

from logic import (
    create_shift_swap_request,
    get_pending_shift_swap_requests,
    get_shift_swap_requests,
    process_shift_swap,
)
from validators import format_date


def create_swap_cmd(args):
    result = create_shift_swap_request(args.officer1_id, args.officer2_id, args.date)
    if result.get("success"):
        print(f"Swap submitted (ID: {result['swap_id']}, status: {result.get('status')})")
    else:
        print(f"Error: {result.get('message', 'Unknown error')}")


def _print_swaps_table(swaps, empty_msg: str = "No shift swaps."):
    if not swaps:
        print(empty_msg)
        return
    print(f"{'ID':<5} {'Date':<12} {'Officer 1':<22} {'Officer 2':<22} {'Status':<20}")
    print("-" * 85)
    for s in swaps:
        print(
            f"{s['id']:<5} {format_date(s['swap_date']):<12} {s['officer1_name']:<22} "
            f"{s['officer2_name']:<22} {s['status']:<20}"
        )


def list_pending_swaps():
    _print_swaps_table(get_pending_shift_swap_requests(), "No pending shift swaps.")


def list_swaps(args):
    if args.status == "pending":
        swaps = get_pending_shift_swap_requests(date_from=args.from_date, date_to=args.to_date)
    elif args.status in (None, "all"):
        swaps = get_shift_swap_requests(date_from=args.from_date, date_to=args.to_date)
    else:
        swaps = get_shift_swap_requests(
            status_filter=args.status,
            date_from=args.from_date,
            date_to=args.to_date,
        )
    _print_swaps_table(swaps, "No matching shift swaps.")


def approve_swap(swap_id: int):
    result = process_shift_swap(swap_id, action="approve")
    if result.success:
        print(result.message)
    elif result.requires_manual:
        print(f"Manual review required: {result.message}")
    else:
        print(f"Failed: {result.message}")


def reject_swap(swap_id: int):
    result = process_shift_swap(swap_id, action="reject")
    print(result.message if result.success else f"Failed: {result.message}")
