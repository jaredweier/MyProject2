"""
Payroll / timecard lock smoke — mirrors Chronos finance UI path (no browser).

  save_timecard_entry → lock_pay_period → save blocked → unlock → save ok

Run:
  python scripts/payroll_flow_smoke.py
  python dev.py payroll-flow-smoke
"""

from __future__ import annotations

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def run_payroll_flow_smoke() -> int:
    import logic
    from tests.helpers import get_any_officer, test_database, working_date_for_squad

    print("Payroll flow smoke (save → lock → block → unlock)")
    print("=" * 56)
    fails = 0

    with test_database(seed=True):
        officer = get_any_officer(squad="A", shift_start="06:00")
        oid = officer["id"]
        work_day = working_date_for_squad("A")
        day_s = work_day.isoformat()
        start, end = logic.get_pay_period(work_day)
        print(f"  officer={officer['name']} id={oid} day={day_s} period={start}–{end}")

        # Ensure unlocked
        logic.unlock_pay_period(user_id=1)
        if logic.is_pay_period_locked(start):
            print("  [FAIL] still locked after unlock")
            return 1
        print("  [ok] period open")

        # Save entry
        saved = logic.save_timecard_entry(
            oid,
            day_s,
            8.0,
            entry_type="Regular Hours",
            notes="payroll_flow_smoke",
            period_start=start.isoformat(),
        )
        if not saved.get("success"):
            print(f"  [FAIL] save open: {saved.get('message')}")
            fails += 1
        else:
            print(f"  [ok] save entry: {saved.get('message', 'ok')}")

        # Lock
        locked = logic.lock_pay_period(start, user_id=1)
        if not locked.get("success"):
            print(f"  [FAIL] lock: {locked}")
            fails += 1
        elif not logic.is_pay_period_locked(start):
            print("  [FAIL] is_pay_period_locked False after lock")
            fails += 1
        else:
            print(f"  [ok] lock period {locked.get('period_start')} – {locked.get('period_end')}")

        # Save must fail
        blocked = logic.save_timecard_entry(
            oid,
            day_s,
            1.0,
            entry_type="Overtime Earned",
            notes="should block",
            period_start=start.isoformat(),
        )
        if blocked.get("success"):
            print("  [FAIL] save succeeded while locked")
            fails += 1
        else:
            print(f"  [ok] save blocked while locked: {blocked.get('message')}")

        # Unlock
        un = logic.unlock_pay_period(user_id=1)
        if not un.get("success") or logic.is_pay_period_locked(start):
            print(f"  [FAIL] unlock: {un}")
            fails += 1
        else:
            print("  [ok] unlock")

        # Save again
        saved2 = logic.save_timecard_entry(
            oid,
            day_s,
            0.5,
            entry_type="Overtime Earned",
            notes="after unlock",
            period_start=start.isoformat(),
        )
        if not saved2.get("success"):
            print(f"  [FAIL] save after unlock: {saved2.get('message')}")
            fails += 1
        else:
            print("  [ok] save after unlock")

        # Summary still works
        try:
            summary = logic.get_pay_period_hours_summary(start, officer_id=oid) or {}
            print(f"  [ok] hours summary keys={list(summary.keys())[:8]}")
        except Exception as exc:
            print(f"  [FAIL] summary: {exc}")
            fails += 1

    print("=" * 56)
    if fails:
        print(f"payroll_flow_smoke: FAILED ({fails})")
        return 1
    print("payroll_flow_smoke: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_payroll_flow_smoke())
