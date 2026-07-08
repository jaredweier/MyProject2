"""Fast integration smoke tests — core scheduling flows without the GUI."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _result(name: str, ok: bool, detail: str = "") -> tuple[bool, str]:
    status = "ok" if ok else "FAIL"
    line = f"  [{status}] {name}"
    if detail:
        line += f" — {detail}"
    return ok, line


def run_smoke() -> int:
    from tests.helpers import get_any_officer, off_date_for_squad, test_database, working_date_for_squad

    lines: list[str] = []
    all_ok = True

    with test_database():
        import logic

        squad_a = get_any_officer("A", "06:00")
        manual_day = working_date_for_squad("A").strftime("%Y-%m-%d")
        officers_a = [
            o
            for o in logic.get_officers_by_seniority()
            if o["squad"] == "A" and o["shift_start"] == "06:00" and o.get("active") == 1
        ]
        if len(officers_a) >= 2:
            original, replacement = officers_a[0], officers_a[1]
            mo = logic.create_manual_coverage_override(
                original["id"],
                replacement["id"],
                manual_day,
                reason="Smoke test coverage",
            )
            ok, line = _result(
                "manual coverage override",
                mo.get("success"),
                mo.get("message", ""),
            )
            lines.append(line)
            all_ok &= ok

        work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
        cr = logic.create_day_off_request(squad_a["id"], work_day, "Vacation")
        ok, line = _result(
            "create day-off request",
            cr.get("success"),
            cr.get("message", ""),
        )
        lines.append(line)
        all_ok &= ok

        if cr.get("success"):
            pr = logic.process_day_off_request(cr["request_id"], "approve")
            ok, line = _result("approve day-off", pr.success, pr.message)
            lines.append(line)
            all_ok &= ok

        squad_b = get_any_officer("B")
        off_day = off_date_for_squad("B").strftime("%Y-%m-%d")
        off_rot = logic.create_day_off_request(squad_b["id"], off_day, "Vacation")
        ok, line = _result(
            "off-rotation request allowed at creation",
            off_rot.get("success"),
            off_rot.get("message", ""),
        )
        lines.append(line)
        all_ok &= ok

        user = logic.create_app_user("smoke_user", "SmokePass1!", "Officer")
        ok, line = _result("create app user", user.get("success"), user.get("message", ""))
        lines.append(line)
        all_ok &= ok

        if user.get("success"):
            auth = logic.authenticate_user("smoke_user", "SmokePass1!")
            ok, line = _result("authenticate user", auth.get("success"), auth.get("message", ""))
            lines.append(line)
            all_ok &= ok

        ical = logic.export_officer_schedule_ical(squad_a["id"])
        ok, line = _result(
            "export officer iCal",
            ical.get("success"),
            ical.get("path") or ical.get("message", ""),
        )
        lines.append(line)
        all_ok &= ok

        start, end = logic.get_current_cycle_window()
        pdf = logic.export_schedule_pdf(start, end, officer_id=squad_a["id"])
        ok, line = _result(
            "export schedule PDF",
            pdf.get("success"),
            pdf.get("path") or pdf.get("message", ""),
        )
        lines.append(line)
        all_ok &= ok

        sim = logic.run_schedule_simulation(
            "4-on-4-off",
            8,
            10.0,
            2080.0,
            ["06:00", "16:00"],
            apply_department_rules=False,
            min_per_shift=1,
        )
        ok, line = _result("schedule simulation", sim.get("success"), sim.get("message", ""))
        lines.append(line)
        all_ok &= ok

        if sim.get("success"):
            bid = logic.create_shift_bid_from_simulation(sim, publish=True)
            ok, line = _result(
                "simulator to shift bid",
                bid.get("success"),
                bid.get("message", ""),
            )
            lines.append(line)
            all_ok &= ok
            if bid.get("success"):
                event = logic.get_shift_bid_event(bid["event_id"])
                opt_id = event["options"][0]["id"]
                rank = logic.submit_shift_bid_rankings(
                    bid["event_id"],
                    squad_a["id"],
                    [{"option_id": opt_id, "preference_rank": 1}],
                )
                ok, line = _result("shift bid ranking submit", rank.get("success"), rank.get("message", ""))
                lines.append(line)
                all_ok &= ok
                preview = logic.preview_shift_bid_awards(bid["event_id"])
                ok, line = _result("shift bid award preview", preview.get("success"), "")
                lines.append(line)
                all_ok &= ok

    print("Dodgeville PD Scheduler — smoke")
    print("-" * 40)
    for line in lines:
        print(line)
    print("-" * 40)
    if all_ok:
        print("smoke: ALL PASSED")
        return 0
    print("smoke: FAILURES")
    return 1


if __name__ == "__main__":
    raise SystemExit(run_smoke())
