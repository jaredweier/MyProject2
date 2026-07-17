"""
Notification Open→route smoke — pure path map + create/get/mark_read.

Run:
  python scripts/notification_flow_smoke.py
  python dev.py notification-flow-smoke
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


def run_notification_flow_smoke() -> int:
    import logic
    from gui.pages.notifications import chronos_path_for_notification
    from tests.helpers import get_any_officer, test_database

    print("Notification flow smoke (create + Open path map)")
    print("=" * 56)
    fails = 0

    cases = [
        (
            {
                "type": "day_off",
                "title": "New Day-Off Request",
                "related_type": "day_off_request",
                "related_id": 1,
            },
            "/time-off",
        ),
        (
            {
                "type": "day_off",
                "title": "Needs Review — coverage",
                "related_type": "day_off_request",
            },
            "/time-off",
        ),
        (
            {"type": "shift_swap", "title": "Swap", "related_type": "shift_swap"},
            "/time-off",
        ),
        (
            {"type": "Open Shift", "title": "Vacancy", "related_type": "open_shift"},
            "/open-shifts",
        ),
        (
            {"type": "Shift Bid", "title": "Bid open", "related_type": "shift_bid_event"},
            "/bidding",
        ),
        (
            {"type": "Payroll", "title": "Pay period locked", "related_type": "pay_period"},
            "/payroll",
        ),
        (
            {"type": "availability", "title": "Blackout", "related_type": "availability"},
            "/availability",
        ),
        ({"type": "general", "title": "Hello"}, "/notifications"),
    ]

    print("  path map:")
    for note, expected in cases:
        got = chronos_path_for_notification(note)
        if got != expected:
            print(f"  [FAIL] {note.get('type')}/{note.get('related_type')}: {got} != {expected}")
            fails += 1
        else:
            print(f"  [ok] {note.get('type') or note.get('related_type')} → {got}")

    with test_database(seed=True):
        officer = get_any_officer(squad="A", shift_start="06:00")
        oid = officer["id"]
        created = logic.create_notification(
            oid,
            "day_off",
            "New Day-Off Request",
            "Smoke notification body",
            related_id=99,
            related_type="day_off_request",
        )
        ok_create = created is True or (isinstance(created, dict) and created.get("success") is not False)
        if not ok_create and isinstance(created, dict) and created.get("success") is False:
            print(f"  [FAIL] create_notification: {created}")
            fails += 1
        else:
            print("  [ok] create_notification")

        rows = logic.get_notifications(officer_id=oid, unread_only=True, limit=20) or []
        if not rows:
            print("  [FAIL] no notifications returned")
            fails += 1
        else:
            row = rows[0]
            path = chronos_path_for_notification(row)
            if path != "/time-off":
                print(f"  [FAIL] live row path {path}")
                fails += 1
            else:
                print(f"  [ok] live row path {path}")
            nid = row.get("id")
            if nid is not None:
                logic.mark_notification_read(int(nid))
                unread = logic.get_notifications(officer_id=oid, unread_only=True, limit=20) or []
                still = [r for r in unread if r.get("id") == nid]
                if still:
                    print("  [FAIL] still unread after mark")
                    fails += 1
                else:
                    print("  [ok] mark_notification_read")

    print("=" * 56)
    if fails:
        print(f"notification_flow_smoke: FAILED ({fails})")
        return 1
    print("notification_flow_smoke: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_notification_flow_smoke())
