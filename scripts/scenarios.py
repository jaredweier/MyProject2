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
        from logic.coverage_optimizer import validate_bump_feasibility

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

        # S-03: Re-approve blocked; one override only (on-duty auto-approve first)
        day_officer = get_any_officer("A", "06:00")
        s03_officer = get_any_officer("A", "15:00")
        work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
        cr03 = logic.create_day_off_request(s03_officer["id"], work_day, "Vacation")
        logic.process_day_off_request(cr03["request_id"], "approve")
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            "SELECT COUNT(*) FROM schedule_overrides WHERE original_officer_id = ?",
            (s03_officer["id"],),
        )
        first_count = c.fetchone()[0]
        second = logic.process_day_off_request(cr03["request_id"], "approve")
        c.execute(
            "SELECT COUNT(*) FROM schedule_overrides WHERE original_officer_id = ?",
            (s03_officer["id"],),
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
        bump04 = validate_bump_feasibility(
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

        # S-06: No on-duty replacement → manual review, then supervisor override → Approved
        rest_day = off_date_for_squad("A").strftime("%Y-%m-%d")
        cr06 = logic.create_day_off_request(day_officer["id"], rest_day, "Vacation")
        pr06a = logic.process_day_off_request(cr06["request_id"], "approve")
        override_actor = next(
            user for user in logic.list_login_users() if user["role"] in ("Supervisor", "Administration")
        )
        pr06b = (
            logic.process_day_off_request(
                cr06["request_id"],
                "approve",
                actor_user_id=override_actor["id"],
                admin_notes="Scenario supervisor constraint exception",
            )
            if pr06a.requires_manual
            else None
        )
        s06_ok = (
            pr06a.requires_manual
            and pr06a.status == "Pending Manual Review"
            and pr06b is not None
            and pr06b.success
            and pr06b.status == "Approved"
        )
        results.append(
            ScenarioResult(
                "S-06",
                s06_ok,
                f"review={pr06a.status}, override={pr06b.status if pr06b else 'n/a'}",
            )
        )

        # S-07: Duplicate blocked while first request is Pending Manual Review
        dup_day = off_date_for_squad("B").strftime("%Y-%m-%d")
        dup_officer = get_any_officer("B", "06:00")
        cr07 = logic.create_day_off_request(dup_officer["id"], dup_day, "Sick")
        if not cr07.get("success"):
            results.append(
                ScenarioResult("S-07", False, cr07.get("message", "create failed")),
            )
        else:
            logic.process_day_off_request(cr07["request_id"], "approve")
            dup07 = logic.create_day_off_request(dup_officer["id"], dup_day, "Personal")
            results.append(
                ScenarioResult(
                    "S-07",
                    not dup07.get("success"),
                    dup07.get("message", "blocked"),
                )
            )

        # S-05: Fri night shift — auto-approve when a replacement is found
        night_officer = get_any_officer("A", "19:00")
        friday = date(2026, 7, 3)
        if logic.is_officer_working_on_day(night_officer["id"], friday):
            cr05 = logic.create_day_off_request(night_officer["id"], friday.isoformat(), "Vacation")
            pr05 = logic.process_day_off_request(cr05["request_id"], "approve")
            results.append(
                ScenarioResult(
                    "S-05",
                    pr05.success and pr05.status == "Approved",
                    pr05.message,
                )
            )
        else:
            results.append(ScenarioResult("S-05", False, "night officer not on duty Friday"))

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

        # S-09: On-duty same-squad replacement for day shift bump (squad working day)
        s09_date = working_date_for_squad("A").strftime("%Y-%m-%d")
        bump09 = validate_bump_feasibility(
            day_officer["id"],
            s09_date,
            day_officer["squad"],
            day_officer["shift_start"],
        )
        s09_ok = bump09.success and bool(bump09.replacement_name)
        detail09 = bump09.message or "no replacement"
        if bump09.replacement_name:
            detail09 = f"picked={bump09.replacement_name}, {detail09}"
        results.append(ScenarioResult("S-09", s09_ok, detail09))

        # S-10: Off-rotation day — no on-duty replacement → manual review
        s10_officer = get_any_officer("A", "19:00")
        s10_date = off_date_for_squad("A").strftime("%Y-%m-%d")
        cr10 = logic.create_day_off_request(s10_officer["id"], s10_date, "Vacation")
        pr10 = logic.process_day_off_request(cr10["request_id"], "approve")
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            "SELECT COUNT(*) FROM schedule_overrides WHERE override_date = ? AND original_officer_id = ?",
            (s10_date, s10_officer["id"]),
        )
        ov10 = c.fetchone()[0]
        conn.close()
        results.append(
            ScenarioResult(
                "S-10",
                pr10.requires_manual and pr10.status == "Pending Manual Review" and ov10 == 0,
                f"status={pr10.status}, overrides={ov10}",
            )
        )

        # S-11: Shift swap approval creates dual overrides
        o1 = get_any_officer("A", "06:00")
        o2 = get_any_officer("A", "10:00")
        swap_day = "2026-07-13"  # Squad A weekday; avoids earlier scenario overrides
        cr11 = logic.create_shift_swap_request(o1["id"], o2["id"], swap_day)
        if not cr11.get("success"):
            results.append(ScenarioResult("S-11", False, cr11.get("message", "swap create failed")))
        else:
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
