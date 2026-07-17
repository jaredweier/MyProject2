"""Punch required policy (default off) + correction approval flow."""

from __future__ import annotations

import unittest

from tests.helpers import test_database


class TimePunchPolicyTests(unittest.TestCase):
    def test_default_punch_not_required(self):
        with test_database():
            from logic.time_punch import get_punch_policy, is_punch_required, set_punch_required

            self.assertFalse(is_punch_required())
            pol = get_punch_policy()
            self.assertFalse(pol.get("punch_required"))
            self.assertTrue(pol.get("manual_timecard_allowed_for_officers"))
            set_punch_required(True)
            self.assertTrue(is_punch_required())
            set_punch_required(False)
            self.assertFalse(is_punch_required())

    def test_clock_in_out(self):
        with test_database():
            from logic.geofence_clock import clock_status
            from logic.officers import get_officers_by_seniority
            from logic.time_punch import list_officer_punches, officer_clock

            oid = get_officers_by_seniority()[0]["id"]
            r = officer_clock(oid, "in")
            self.assertTrue(r.get("success"), r)
            self.assertTrue(clock_status(oid).get("clocked_in"))
            r2 = officer_clock(oid, "out")
            self.assertTrue(r2.get("success"), r2)
            self.assertFalse(clock_status(oid).get("clocked_in"))
            self.assertGreaterEqual(len(list_officer_punches(oid)), 2)

    def test_edit_request_notify_and_approve(self):
        with test_database():
            from database import get_connection
            from logic.officers import get_officers_by_seniority
            from logic.time_punch import (
                approve_punch_edit,
                list_punch_edit_requests,
                officer_clock,
                reject_punch_edit,
                request_punch_edit,
            )

            oid = get_officers_by_seniority()[0]["id"]
            cin = officer_clock(oid, "in")
            self.assertTrue(cin.get("success"))
            pid = cin.get("id")
            self.assertTrue(pid)
            # Request correction
            req = request_punch_edit(
                int(pid),
                oid,
                proposed_created_at="2026-07-16 07:55",
                proposed_punch_type="in",
                reason="Forgot — actually started early",
                user_id=1,
            )
            self.assertTrue(req.get("success"), req)
            rid = req.get("request_id")
            pending = list_punch_edit_requests(status="pending")
            self.assertTrue(any(p.get("id") == rid for p in pending))
            # Approve applies timestamp
            ap = approve_punch_edit(int(rid), user_id=1, review_notes="OK")
            self.assertTrue(ap.get("success"), ap)
            with get_connection() as conn:
                punch = dict(conn.execute("SELECT * FROM geofence_punches WHERE id = ?", (pid,)).fetchone())
            self.assertIn("07:55", str(punch.get("created_at")))
            self.assertEqual(int(punch.get("edited") or 0), 1)

            # Second punch + reject path
            officer_clock(oid, "out")
            cout = officer_clock(oid, "in")  # may fail if still in - get last
            # use list
            from logic.time_punch import list_officer_punches

            punches = list_officer_punches(oid)
            last = punches[0]
            req2 = request_punch_edit(
                int(last["id"]),
                oid,
                proposed_created_at="7/16/26 18:00",
                proposed_punch_type=last.get("punch_type") or "out",
                reason="Wrong time",
            )
            if req2.get("success"):
                rj = reject_punch_edit(int(req2["request_id"]), user_id=1, review_notes="No proof")
                self.assertTrue(rj.get("success"))

    def test_manual_timecard_blocked_when_required(self):
        with test_database():
            from logic.officers import get_officers_by_seniority
            from logic.payroll import save_timecard_entry
            from logic.time_punch import set_punch_required

            oid = get_officers_by_seniority()[0]["id"]
            set_punch_required(True)
            blocked = save_timecard_entry(oid, "2026-07-16", 8.0, notes="manual entry")
            self.assertFalse(blocked.get("success"))
            self.assertIn("clock", (blocked.get("message") or "").lower())
            # Supervisor override
            ok = save_timecard_entry(oid, "2026-07-16", 8.0, notes="sup entry", override_approval=True)
            self.assertTrue(ok.get("success"), ok)
            set_punch_required(False)
            free = save_timecard_entry(oid, "2026-07-17", 8.0, notes="free entry")
            self.assertTrue(free.get("success"), free)


if __name__ == "__main__":
    unittest.main()
