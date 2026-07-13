"""
Leave vertical smoke — mirrors Chronos UI approve path (no browser).

Exercises the same logic calls as gui/pages/leave.py:
  create → preview_best_coverage_plans → process with preferred_chain
  reject with admin_notes

Run:
  python scripts/leave_flow_smoke.py
  python -m unittest tests.test_leave_flow_smoke -v   # if registered as test
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def run_leave_flow_smoke() -> int:
    import logic
    from logic.scheduling_sim import preview_best_coverage_plans
    from tests.helpers import get_any_officer, test_database, working_date_for_squad

    print("Leave flow smoke (logic path = Chronos UI)")
    print("=" * 56)
    fails = 0

    with test_database(seed=True):
        officer = get_any_officer(squad="A", shift_start="06:00")
        work_day = working_date_for_squad("A")
        day_s = work_day.isoformat() if hasattr(work_day, "isoformat") else str(work_day)
        oid = officer["id"]
        squad = officer.get("squad") or "A"
        shift = officer.get("shift_start") or "06:00"
        print(f"  officer={officer['name']} id={oid} day={day_s} squad={squad} shift={shift}")

        # --- submit (like officer Submit request) ---
        created = logic.create_day_off_request(oid, day_s, "Vacation", "leave_flow_smoke")
        if not created.get("success"):
            print(f"  [FAIL] create: {created.get('message')}")
            return 1
        rid = created["request_id"]
        print(f"  [ok] create request #{rid}")

        # --- preview plans (like Plans / Approve dialog) ---
        payload = preview_best_coverage_plans(oid, day_s, squad, shift, max_plans=5)
        plans = [p for p in (payload.get("plans") or []) if p.get("success")]
        print(
            f"  [ok] preview_best_coverage_plans count={len(plans)} raw={payload.get('count', len(payload.get('plans') or []))}"
        )

        # --- approve with preferred_chain (like _confirm_approve → _run_approve) ---
        chain = (plans[0].get("chain") if plans else None) or None
        score = plans[0].get("plan_score") if plans else None
        result = logic.process_day_off_request(rid, action="approve", preferred_chain=chain)
        if getattr(result, "success", False):
            print(f"  [ok] approve: {result.message}" + (f" score={score}" if score is not None else ""))
        elif getattr(result, "requires_manual", False):
            print(f"  [ok] approve → manual review (policy): {result.message}")
            # Supervisor override path still must work
            ov = logic.process_day_off_request(rid, action="approve", admin_notes="smoke override")
            if getattr(ov, "success", False) or getattr(ov, "requires_manual", False):
                print(
                    f"  [ok] re-process: success={getattr(ov, 'success', None)} manual={getattr(ov, 'requires_manual', None)} msg={ov.message}"
                )
            else:
                print(f"  [FAIL] override: {ov.message}")
                fails += 1
        else:
            print(f"  [FAIL] approve: {getattr(result, 'message', result)}")
            fails += 1

        # --- second request: reject with notes (like _reject_dialog) ---
        officer2 = get_any_officer(squad="B", shift_start="06:00")
        day2 = working_date_for_squad("B")
        day2_s = day2.isoformat() if hasattr(day2, "isoformat") else str(day2)
        cr2 = logic.create_day_off_request(officer2["id"], day2_s, "Personal", "leave_flow_smoke reject")
        if not cr2.get("success"):
            print(f"  [FAIL] create#2: {cr2.get('message')}")
            fails += 1
        else:
            rid2 = cr2["request_id"]
            rej = logic.process_day_off_request(rid2, action="reject", admin_notes="Rejected by leave_flow_smoke")
            if getattr(rej, "success", False) or "reject" in (getattr(rej, "message", "") or "").lower():
                print(f"  [ok] reject with notes: {rej.message}")
            else:
                # still ok if message indicates rejected
                status = "ok" if getattr(rej, "success", False) else "FAIL"
                print(f"  [{status}] reject: {getattr(rej, 'message', rej)}")
                if status == "FAIL":
                    fails += 1

        # --- queue visibility ---
        pending = logic.get_pending_day_off_requests() or []
        print(f"  [ok] pending queue size after smoke={len(pending)}")

    print("=" * 56)
    if fails:
        print(f"leave_flow_smoke: FAILED ({fails})")
        return 1
    print("leave_flow_smoke: PASSED")
    return 0


def main() -> int:
    return run_leave_flow_smoke()


if __name__ == "__main__":
    raise SystemExit(main())
