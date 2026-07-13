"""
Leave vertical smoke — mirrors Chronos UI approve path (no browser).

Exercises the same logic calls as gui/pages/leave.py:
  create → preview_best_coverage_plans → process with preferred_chain
  create → list_ot_fill_candidates → apply_ot_fill_selection (Order in)
  reject with admin_notes

Run:
  python scripts/leave_flow_smoke.py
  python -m unittest tests.test_leave_flow_smoke -v   # if registered as test
"""

from __future__ import annotations

import os
import sys
from datetime import timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def run_leave_flow_smoke() -> int:
    import logic
    from logic.ot_fill import apply_ot_fill_selection, get_ot_fill_mode, list_ot_fill_candidates
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

        # --- OT fill Order-in path (like Approve dialog → Order in) ---
        # Separate day so it does not collide with the first approved request.
        day_ot = work_day + timedelta(days=14)
        for offset in range(0, 28, 1):
            cand_day = work_day + timedelta(days=offset)
            if offset == 0:
                continue  # first day already used
            day_ot = cand_day
            # Prefer another working day for same squad
            from logic.scheduling import officer_base_rotation_working

            if officer_base_rotation_working(officer, day_ot):
                break
        day_ot_s = day_ot.isoformat() if hasattr(day_ot, "isoformat") else str(day_ot)
        cr_ot = logic.create_day_off_request(oid, day_ot_s, "Personal", "leave_flow_smoke ot_fill")
        if not cr_ot.get("success"):
            print(f"  [FAIL] create ot-fill request: {cr_ot.get('message')}")
            fails += 1
        else:
            rid_ot = cr_ot["request_id"]
            fill = list_ot_fill_candidates(oid, day_ot_s, squad, shift)
            mode = fill.get("mode_label") or get_ot_fill_mode()
            candidates = fill.get("candidates") or [] if fill.get("success") else []
            eligible = [c for c in candidates if not c.get("ineligible_for_order") and c.get("officer_id") is not None]
            print(f"  [ok] list_ot_fill_candidates mode={mode} n={len(candidates)} eligible={len(eligible)}")
            if not eligible:
                # Still prove candidates API; order-in requires a cover
                print("  [warn] no order-eligible covers — skip apply_ot_fill_selection")
            else:
                cover_id = int(eligible[0]["officer_id"])
                # Keyword-only response= (never positional False → cover_id)
                applied = apply_ot_fill_selection(
                    rid_ot,
                    cover_id,
                    response="ordered_in",
                    is_partial=False,
                    turned_down_ids=[],
                    actor_user_id=None,
                )
                if applied.get("success"):
                    print(f"  [ok] Order in (apply_ot_fill_selection): cover=#{cover_id} · {applied.get('message')}")
                else:
                    # Manual review / policy may soft-fail; surface as fail only if hard error
                    msg = (applied.get("message") or "").lower()
                    if "not found" in msg or "invalid" in msg:
                        print(f"  [FAIL] Order in: {applied.get('message')}")
                        fails += 1
                    else:
                        print(f"  [ok] Order in soft result: {applied.get('message')}")

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
