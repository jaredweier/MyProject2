"""Run SCHEDULING_RULES.md regression scenarios S-01 through S-11."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import date
from typing import Callable, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@dataclass
class ScenarioResult:
    scenario_id: str
    passed: bool
    detail: str


def _run_all() -> List[ScenarioResult]:
    from config import ROTATION_BASE_DATE
    from database import get_connection
    from tests.helpers import get_any_officer, off_date_for_squad, test_database, working_date_for_squad

    results: List[ScenarioResult] = []

    with test_database():
        import logic

        # S-01: Squad B requests off on Squad A day → Pending
        squad_b = get_any_officer("B")
        r01 = logic.create_day_off_request(squad_b["id"], "2026-06-28", "Vacation")
        results.append(
            ScenarioResult(
                "S-01",
                r01.get("success"),
                r01.get("message", "Pending"),
            )
        )

        # S-02: Squad A requests off on Squad A day → Pending
        squad_a = get_any_officer("A")
        r02 = logic.create_day_off_request(squad_a["id"], "2026-06-28", "Vacation")
        results.append(
            ScenarioResult(
                "S-02",
                r02.get("success"),
                r02.get("message", "Pending"),
            )
        )

        # S-03: Re-approve blocked; one override only
        day_officer = get_any_officer("A", "06:00")
        work_day = off_date_for_squad("A").strftime("%Y-%m-%d")
        cr03 = logic.create_day_off_request(day_officer["id"], work_day, "Vacation")
        logic.process_day_off_request(cr03["request_id"], "approve")
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            "SELECT COUNT(*) FROM schedule_overrides WHERE original_officer_id = ?",
            (day_officer["id"],),
        )
        first_count = c.fetchone()[0]
        second = logic.process_day_off_request(cr03["request_id"], "approve")
        c.execute(
            "SELECT COUNT(*) FROM schedule_overrides WHERE original_officer_id = ?",
            (day_officer["id"],),
        )
        after_count = c.fetchone()[0]
        conn.close()
        results.append(
            ScenarioResult(
                "S-03",
                not second.success and first_count == after_count == 1,
                f"2nd approve={second.success}, overrides={after_count}",
            )
        )

        # S-04: Day shift Friday not night-blocked
        bump04 = logic.validate_bump_feasibility(
            day_officer["id"],
            "2026-07-03",
            day_officer["squad"],
            day_officer["shift_start"],
        )
        night_blocked = bump04.requires_manual and "night" in (bump04.message or "").lower()
        results.append(
            ScenarioResult(
                "S-04",
                not night_blocked,
                bump04.message or "ok",
            )
        )

        # S-05: Night shift Friday → Pending Manual Review
        night_officer = get_any_officer("A", "19:00")
        friday = date(2026, 7, 3)
        if logic.is_officer_working_on_day(night_officer["id"], friday):
            cr05 = logic.create_day_off_request(night_officer["id"], friday.isoformat(), "Vacation")
            pr05 = logic.process_day_off_request(cr05["request_id"], "approve")
            results.append(
                ScenarioResult(
                    "S-05",
                    pr05.requires_manual and pr05.status == "Pending Manual Review",
                    pr05.message,
                )
            )
        else:
            results.append(ScenarioResult("S-05", False, "night officer not on duty Friday"))

        # S-06: Supervisor approves Manual Review → Approved
        if logic.is_officer_working_on_day(night_officer["id"], friday):
            pr06 = logic.process_day_off_request(cr05["request_id"], "approve")
            results.append(
                ScenarioResult(
                    "S-06",
                    pr06.success and pr06.status == "Approved",
                    pr06.message,
                )
            )
        else:
            results.append(ScenarioResult("S-06", False, "skipped (S-05 failed)"))

        # S-07: Duplicate during Manual Review → Rejected
        dup_day = "2026-07-17"
        if logic.is_officer_working_on_day(night_officer["id"], date.fromisoformat(dup_day)):
            cr07 = logic.create_day_off_request(night_officer["id"], dup_day, "Vacation")
            logic.process_day_off_request(cr07["request_id"], "approve")
            dup07 = logic.create_day_off_request(night_officer["id"], dup_day, "Personal")
            results.append(
                ScenarioResult(
                    "S-07",
                    not dup07.get("success"),
                    dup07.get("message", "blocked"),
                )
            )
        else:
            results.append(ScenarioResult("S-07", False, "night officer not on duty"))

        # S-08: Date before rotation base → Rejected
        before = (ROTATION_BASE_DATE - __import__("datetime").timedelta(days=10)).strftime("%Y-%m-%d")
        r08 = logic.create_day_off_request(day_officer["id"], before, "Vacation")
        results.append(
            ScenarioResult(
                "S-08",
                not r08.get("success"),
                r08.get("message", "blocked"),
            )
        )

        # S-09: Eligible same-squad replacement for day shift bump (off-rotation day)
        s09_date = "2026-07-05"
        bump09 = logic.validate_bump_feasibility(
            day_officer["id"],
            s09_date,
            day_officer["squad"],
            day_officer["shift_start"],
        )
        s09_ok = False
        detail09 = bump09.message or "no replacement"
        if bump09.replacement_name:
            officers = logic.get_officers_by_seniority()
            eligible = [
                o
                for o in officers
                if o["squad"] == day_officer["squad"]
                and o["id"] != day_officer["id"]
                and logic.get_shift_number(o["shift_start"])
                in __import__("config").BUMP_RULES.get(logic.get_shift_number(day_officer["shift_start"]), ())
            ]
            eligible_names = {o["name"] for o in eligible}
            s09_ok = bump09.replacement_name in eligible_names
            detail09 = f"picked={bump09.replacement_name}, eligible={len(eligible_names)}"
        results.append(ScenarioResult("S-09", s09_ok, detail09))

        # S-10: Off-rotation cascade auto-approves (one override)
        s10_date = "2026-07-01"  # Squad A off day (distinct from S-03 override date)
        cr10 = logic.create_day_off_request(day_officer["id"], s10_date, "Vacation")
        pr10 = logic.process_day_off_request(cr10["request_id"], "approve")
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            "SELECT COUNT(*) FROM schedule_overrides WHERE override_date = ? AND original_officer_id = ?",
            (s10_date, day_officer["id"]),
        )
        ov10 = c.fetchone()[0]
        conn.close()
        results.append(
            ScenarioResult(
                "S-10",
                pr10.success and pr10.status == "Approved" and ov10 == 1,
                f"status={pr10.status}, overrides={ov10}",
            )
        )

        # S-11: Shift swap approval creates dual overrides
        o1 = get_any_officer("A", "06:00")
        o2 = get_any_officer("A", "10:00")
        swap_day = working_date_for_squad("A").strftime("%Y-%m-%d")
        cr11 = logic.create_shift_swap_request(o1["id"], o2["id"], swap_day)
        pr11 = logic.process_shift_swap(cr11["swap_id"], "approve")
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            "SELECT COUNT(*) FROM schedule_overrides WHERE override_date = ? AND reason = 'Shift Swap'",
            (swap_day,),
        )
        swap_ov = c.fetchone()[0]
        conn.close()
        results.append(
            ScenarioResult(
                "S-11",
                pr11.success and swap_ov == 2,
                f"swap ok={pr11.success}, overrides={swap_ov}",
            )
        )

    return results


def run_scenarios() -> int:
    results = _run_all()
    passed = sum(1 for r in results if r.passed)
    print("Dodgeville PD Scheduler — scenarios S-01..S-11")
    print("=" * 60)
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.scenario_id}: {r.detail}")
    print("=" * 60)
    print(f"scenarios: {passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(run_scenarios())
