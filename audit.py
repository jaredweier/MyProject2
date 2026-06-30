"""
Regression audit for known scheduling bugs.
Run: python dev.py audit
"""

from dataclasses import dataclass
from typing import List

from config import ROTATION_BASE_DATE
from tests.helpers import get_any_officer, off_date_for_squad, test_database, working_date_for_squad


@dataclass
class AuditFinding:
    check_id: str
    passed: bool
    detail: str


def run_audit() -> List[AuditFinding]:
    findings: List[AuditFinding] = []

    with test_database():
        import logic
        from database import get_connection

        # AUD-001: Off-rotation day-off request allowed at creation
        squad_b = get_any_officer("B")
        off_day = off_date_for_squad("B").strftime("%Y-%m-%d")
        r = logic.create_day_off_request(squad_b["id"], off_day, "Vacation")
        findings.append(
            AuditFinding(
                "AUD-001-off-rotation-request-allowed",
                r.get("success"),
                "ok" if r.get("success") else r.get("message", "request rejected"),
            )
        )

        # AUD-002: Re-approve does not create duplicate overrides
        squad_a = get_any_officer("A", "06:00")
        work_day = off_date_for_squad("A").strftime("%Y-%m-%d")
        cr = logic.create_day_off_request(squad_a["id"], work_day, "Vacation")
        logic.process_day_off_request(cr["request_id"], "approve")
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            "SELECT COUNT(*) FROM schedule_overrides WHERE original_officer_id = ?",
            (squad_a["id"],),
        )
        overrides_after_first = c.fetchone()[0]
        logic.process_day_off_request(cr["request_id"], "approve")
        c.execute(
            "SELECT COUNT(*) FROM schedule_overrides WHERE original_officer_id = ?",
            (squad_a["id"],),
        )
        overrides_after_second = c.fetchone()[0]
        conn.close()
        findings.append(
            AuditFinding(
                "AUD-002-no-duplicate-override",
                overrides_after_second == overrides_after_first,
                f"overrides after first={overrides_after_first}, second={overrides_after_second}",
            )
        )

        # AUD-003: Day shift on Friday not blocked by night-minimum rule
        day_officer = get_any_officer("A", "06:00")
        bump = logic.validate_bump_feasibility(
            day_officer["id"], "2026-07-03", day_officer["squad"], day_officer["shift_start"]
        )
        night_blocked = bump.requires_manual and "night" in bump.message.lower()
        findings.append(
            AuditFinding(
                "AUD-003-day-shift-not-night-blocked",
                not night_blocked,
                bump.message or "ok",
            )
        )

        # AUD-004: Rejected request cannot be re-approved
        cr2 = logic.create_day_off_request(squad_a["id"], "2026-07-02", "Sick")
        logic.process_day_off_request(cr2["request_id"], "reject")
        rej = logic.process_day_off_request(cr2["request_id"], "approve")
        findings.append(
            AuditFinding(
                "AUD-004-reject-blocks-reapprove",
                not rej.success,
                rej.message,
            )
        )

        # AUD-005: Dates before rotation base are rejected
        before_base = (ROTATION_BASE_DATE - __import__("datetime").timedelta(days=10)).strftime("%Y-%m-%d")
        cr3 = logic.create_day_off_request(squad_a["id"], before_base, "Vacation")
        findings.append(
            AuditFinding(
                "AUD-005-before-base-date-blocked",
                not cr3.get("success"),
                cr3.get("message", "ok"),
            )
        )

        # AUD-006: Bump auto-resolves when cascade completes (off-rotation replacements)
        bump_test_day = off_date_for_squad("A").strftime("%Y-%m-%d")
        bump_ok = logic.validate_bump_feasibility(
            squad_a["id"], bump_test_day, squad_a["squad"], squad_a["shift_start"]
        )
        if bump_ok.replacement_name:
            from config import BUMP_RULES

            officers = logic.get_officers_by_seniority()
            replacement = next(o for o in officers if o["name"] == bump_ok.replacement_name)
            allowed = logic.get_shift_number(replacement["shift_start"]) in BUMP_RULES.get(
                logic.get_shift_number(squad_a["shift_start"]), ()
            )
            findings.append(
                AuditFinding(
                    "AUD-006-bump-finds-eligible-replacement",
                    replacement["squad"] == squad_a["squad"] and allowed,
                    f"replacement={replacement['name']} squad={replacement['squad']} shift={replacement['shift_start']}",
                )
            )
        else:
            findings.append(
                AuditFinding(
                    "AUD-006-bump-finds-eligible-replacement",
                    False,
                    "no replacement found for bump test",
                )
            )

        # AUD-007: Supervisor can approve/reject Pending Manual Review
        night_officer = get_any_officer("A", "19:00")
        friday = "2026-07-03"
        if logic.is_officer_working_on_day(night_officer["id"], __import__("datetime").date(2026, 7, 3)):
            cr_mr = logic.create_day_off_request(night_officer["id"], friday, "Vacation")
            logic.process_day_off_request(cr_mr["request_id"], "approve")
            forced = logic.process_day_off_request(cr_mr["request_id"], "approve")
            findings.append(
                AuditFinding(
                    "AUD-007-manual-review-approve",
                    forced.success and forced.status == "Approved",
                    forced.message,
                )
            )
        else:
            findings.append(
                AuditFinding(
                    "AUD-007-manual-review-approve",
                    False,
                    "night officer not working on Friday test date",
                )
            )

        # AUD-008 / S-07: Duplicate blocked while manual review pending
        dup_day = "2026-07-17"
        if logic.is_officer_working_on_day(night_officer["id"], __import__("datetime").date(2026, 7, 17)):
            cr_dup = logic.create_day_off_request(night_officer["id"], dup_day, "Vacation")
            logic.process_day_off_request(cr_dup["request_id"], "approve")
            dup = logic.create_day_off_request(night_officer["id"], dup_day, "Personal")
            findings.append(
                AuditFinding(
                    "AUD-008-duplicate-during-manual-review",
                    not dup.get("success"),
                    dup.get("message", "blocked"),
                )
            )
        else:
            findings.append(
                AuditFinding(
                    "AUD-008-duplicate-during-manual-review",
                    False,
                    "night officer not working on test date",
                )
            )

        # AUD-009 / S-10: Off-rotation cascade auto-approves
        s10_officer = get_any_officer("A", "06:00")
        if s10_officer["id"] == squad_a["id"]:
            officers_a6 = [
                o for o in logic.get_officers_by_seniority() if o["squad"] == "A" and o["shift_start"] == "06:00"
            ]
            s10_officer = officers_a6[1] if len(officers_a6) > 1 else s10_officer
        s10_date = "2026-07-01"
        cr_s10 = logic.create_day_off_request(s10_officer["id"], s10_date, "Vacation")
        pr_s10 = logic.process_day_off_request(cr_s10["request_id"], "approve")
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            "SELECT COUNT(*) FROM schedule_overrides WHERE override_date = ? AND original_officer_id = ?",
            (s10_date, s10_officer["id"]),
        )
        s10_overrides = c.fetchone()[0]
        conn.close()
        findings.append(
            AuditFinding(
                "AUD-009-s10-cascade-auto-approve",
                pr_s10.success and pr_s10.status == "Approved" and s10_overrides >= 1,
                f"status={pr_s10.status}, overrides={s10_overrides}",
            )
        )

        # AUD-010 / S-11: Shift swap creates dual overrides
        swap_o1 = get_any_officer("A", "06:00")
        swap_o2 = get_any_officer("A", "10:00")
        swap_day = working_date_for_squad("A").strftime("%Y-%m-%d")
        cr_swap = logic.create_shift_swap_request(swap_o1["id"], swap_o2["id"], swap_day)
        pr_swap = logic.process_shift_swap(cr_swap["swap_id"], "approve")
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            "SELECT COUNT(*) FROM schedule_overrides WHERE override_date = ? AND reason = 'Shift Swap'",
            (swap_day,),
        )
        swap_count = c.fetchone()[0]
        conn.close()
        findings.append(
            AuditFinding(
                "AUD-010-s11-shift-swap-overrides",
                pr_swap.success and swap_count == 2,
                f"swap={pr_swap.success}, overrides={swap_count}",
            )
        )

    return findings


def print_report(findings: List[AuditFinding]) -> int:
    passed = sum(1 for f in findings if f.passed)
    total = len(findings)
    print(f"Audit: {passed}/{total} passed\n")
    for f in findings:
        status = "PASS" if f.passed else "FAIL"
        print(f"  [{status}] {f.check_id}: {f.detail}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(print_report(run_audit()))
