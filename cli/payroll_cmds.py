"""CLI handlers — payroll cmds."""

from __future__ import annotations

from logic import (
    get_current_cycle_window,
    get_pay_period_history,
    is_pay_period_locked,
    lock_pay_period,
    unlock_pay_period,
)
from validators import format_date


def pay_period_status(_args):
    locked = is_pay_period_locked()
    start, end = get_current_cycle_window()
    state = "LOCKED" if locked else "open"
    print(f"Pay period {format_date(start)} – {format_date(end)}: {state}")


def pay_period_lock(_args):
    result = lock_pay_period()
    if result.get("success"):
        print(f"Locked pay period {format_date(result['period_start'])} – {format_date(result['period_end'])}")
    else:
        print(f"Error: {result.get('message')}")


def pay_period_unlock(_args):
    result = unlock_pay_period()
    if result.get("success"):
        print("Pay period unlocked")
    else:
        print(f"Error: {result.get('message')}")


def pay_period_history_cmd(args):
    data = get_pay_period_history(args.limit)
    if not data.get("periods"):
        print("No pay period history.")
        return
    for p in data["periods"]:
        lock = " locked" if p.get("locked") else ""
        print(
            f"{format_date(p['period_start'])} – {format_date(p['period_end'])}  "
            f"{p['total_hours']:.1f}h  ${p['total_pay']:,.2f}  "
            f"({p['officer_count']} officers){lock}"
        )
