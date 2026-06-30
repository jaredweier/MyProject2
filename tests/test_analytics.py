"""Tests for analytics, holidays, availability, and exports."""

import os
import tempfile
import unittest
from datetime import date

from tests.helpers import get_any_officer, test_database, working_date_for_squad


class AnalyticsTests(unittest.TestCase):
    def test_holiday_crud(self):
        with test_database():
            import logic

            result = logic.add_holiday("Test Day", "2026-10-15", notes="unittest")
            self.assertTrue(result["success"])
            holidays = logic.get_holidays(2026)
            names = [h["name"] for h in holidays]
            self.assertIn("Test Day", names)
            hid = next(h["id"] for h in holidays if h["name"] == "Test Day")
            updated = logic.update_holiday(
                hid,
                "Updated Day",
                "2026-10-16",
                is_paid=False,
                notes="revised",
            )
            self.assertTrue(updated["success"])
            in_range = logic.get_holidays_in_range(date(2026, 10, 1), date(2026, 10, 31))
            updated_rows = [h for h in in_range if h["name"] == "Updated Day"]
            self.assertEqual(len(updated_rows), 1)
            self.assertEqual(updated_rows[0]["holiday_date"], "2026-10-16")
            self.assertFalse(updated_rows[0]["is_paid"])
            dup = logic.add_holiday("Duplicate", "2026-10-16")
            self.assertFalse(dup["success"])
            deleted = logic.delete_holiday(hid)
            self.assertTrue(deleted["success"])
            remaining = [
                h
                for h in logic.get_holidays_in_range(date(2026, 10, 1), date(2026, 10, 31))
                if h["name"] in ("Test Day", "Updated Day")
            ]
            self.assertEqual(remaining, [])

    def test_add_availability_schedule_conflict_warning(self):
        with test_database():
            import logic

            officer = get_any_officer("A")
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            result = logic.add_officer_availability(officer["id"], work_day, "Training")
            self.assertTrue(result["success"], result.get("message"))
            self.assertTrue(result.get("schedule_conflict"))
            self.assertIn("warning", result)
            notes = logic.get_notifications(officer_id=officer["id"], unread_only=True)
            self.assertTrue(any(n["type"] == "availability" for n in notes))
            entries = logic.get_officer_availability(officer_id=officer["id"])
            logic.delete_officer_availability(entries[-1]["id"])

    def test_availability_and_conflicts(self):
        with test_database():
            import logic

            officer = get_any_officer("A")
            work_date = working_date_for_squad("A")
            add = logic.add_officer_availability(
                officer["id"],
                work_date.isoformat(),
                reason="Training conflict",
            )
            self.assertTrue(add["success"])
            entries = logic.get_officer_availability(officer_id=officer["id"])
            self.assertEqual(len(entries), 1)
            conflicts = logic.get_schedule_conflicts(work_date, work_date)
            self.assertGreaterEqual(conflicts["conflict_count"], 1)
            scoped = logic.get_schedule_conflicts(
                work_date,
                work_date,
                officer_id=officer["id"],
            )
            self.assertGreaterEqual(scoped["conflict_count"], 1)
            other = get_any_officer("B")
            empty = logic.get_schedule_conflicts(
                work_date,
                work_date,
                officer_id=other["id"],
            )
            self.assertEqual(empty["conflict_count"], 0)
            logic.delete_officer_availability(entries[0]["id"])

    def test_pay_period_hours_by_officer(self):
        with test_database():
            import logic

            hours_map = logic.get_pay_period_hours_by_officer()
            officers = [o for o in logic.get_officers_by_seniority() if o.get("active") == 1]
            self.assertEqual(len(hours_map), len(officers))
            for oid, hours in hours_map.items():
                self.assertGreaterEqual(hours, 0.0)

    def test_equitable_ot_ledger_structure(self):
        with test_database():
            import logic

            ledger = logic.get_equitable_ot_ledger()
            self.assertTrue(ledger["success"])
            self.assertIn("ledger", ledger)
            self.assertIn("department_ot_avg", ledger)
            self.assertEqual(ledger["officer_count"], len(ledger["ledger"]))

    def test_schedule_sync_notifies_officers(self):
        with test_database():
            import logic

            admin = next(u for u in logic.list_all_users() if u["role"] == "Administration")
            before = sum(
                len(logic.get_notifications(officer_id=o["id"]))
                for o in logic.get_officers_by_seniority()
                if o.get("active") == 1
            )
            result = logic.sync_updated_schedule(2026, 7, admin["id"])
            self.assertTrue(result["success"])
            after = sum(
                len(logic.get_notifications(officer_id=o["id"]))
                for o in logic.get_officers_by_seniority()
                if o.get("active") == 1
            )
            self.assertGreater(after, before)

    def test_minimum_rest_gap_computation(self):
        with test_database():
            import logic

            officer = get_any_officer("A", "06:00")
            work_day = working_date_for_squad("A")
            gap = logic.compute_minimum_rest_gap(
                officer["id"],
                work_day,
                officer["shift_start"],
                officer["shift_end"],
            )
            self.assertTrue(gap is None or gap >= 0)

    def test_hours_watch_structure(self):
        with test_database():
            import logic

            watch = logic.get_hours_watch()
            self.assertTrue(watch["success"])
            self.assertIn("warnings", watch)
            self.assertIn("warning_count", watch)
            self.assertIn("weekly_threshold", watch)
            self.assertIn("period_threshold", watch)
            self.assertEqual(watch["warning_count"], len(watch["warnings"]))

    def test_overtime_alerts_officer_filter(self):
        with test_database():
            import logic

            officer_a = get_any_officer("A")
            officer_b = get_any_officer("B")
            all_ot = logic.get_overtime_alerts()
            scoped_a = logic.get_overtime_alerts(officer_id=officer_a["id"])
            scoped_b = logic.get_overtime_alerts(officer_id=officer_b["id"])
            self.assertLessEqual(scoped_a["alert_count"], all_ot["alert_count"])
            self.assertLessEqual(scoped_b["alert_count"], all_ot["alert_count"])
            for alert in scoped_a["alerts"]:
                self.assertEqual(alert["officer_id"], officer_a["id"])

    def test_coverage_report_current_cycle(self):
        with test_database():
            import logic

            start, end = logic.get_current_cycle_window(date(2026, 7, 4))
            report = logic.get_coverage_report(start, end)
            self.assertTrue(report["success"])
            self.assertEqual(len(report["days"]), 14)

    def test_coverage_gap_board_structure(self):
        with test_database():
            import logic

            board = logic.get_coverage_gap_board()
            self.assertTrue(board["success"])
            self.assertIn("gaps", board)
            self.assertIn("gap_count", board)
            self.assertIn("critical_count", board)
            self.assertIn("warning_count", board)
            self.assertEqual(board["gap_count"], len(board["gaps"]))
            for gap in board["gaps"]:
                self.assertIn(gap["gap_type"], ("zero_coverage", "night_minimum"))
                self.assertIn(gap["severity"], ("critical", "warning"))
                self.assertIn("shift_label", gap)

    def test_payroll_ytd_and_labor_forecast(self):
        with test_database():
            import logic

            ytd = logic.get_payroll_ytd(2026)
            self.assertTrue(ytd["success"])
            self.assertIn("department_total_pay", ytd)
            forecast = logic.get_labor_cost_forecast(2)
            self.assertTrue(forecast["success"])
            self.assertEqual(len(forecast["forecast"]), 2)

    def test_export_roster_csv(self):
        with test_database():
            import logic

            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "roster.csv")
                result = logic.export_roster_csv(path)
                self.assertTrue(result["success"])
                self.assertTrue(os.path.exists(path))
                with open(path, encoding="utf-8") as fh:
                    content = fh.read()
                self.assertIn("name", content.lower())

    def test_department_settings(self):
        with test_database():
            import logic

            bad = logic.set_department_setting("BAD KEY", "x")
            self.assertFalse(bad["success"])
            ok = logic.set_department_setting("overtime_threshold", "80")
            self.assertTrue(ok["success"])
            self.assertEqual(logic.get_department_setting("overtime_threshold"), "80")
            all_settings = logic.get_all_department_settings()
            self.assertIn("overtime_threshold", all_settings)

    def test_export_audit_csv(self):
        with test_database():
            import os
            import tempfile

            import logic

            logic.log_audit_action("export.test", "test", 1, details="csv")
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "audit.csv")
                result = logic.export_audit_csv(path)
                self.assertTrue(result.get("success"))
                self.assertTrue(os.path.exists(path))

    def test_export_audit_csv_action_filter(self):
        with test_database():
            import os
            import tempfile

            import logic

            logic.log_audit_action("user.login", "app_user", 1)
            logic.log_audit_action("pay_period.lock", "pay_period", None)
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "login_audit.csv")
                result = logic.export_audit_csv(path, action_filter="login")
                self.assertTrue(result.get("success"))
                with open(path, encoding="utf-8") as fh:
                    content = fh.read()
                self.assertIn("login", content)
                self.assertNotIn("pay_period", content)

    def test_audit_log(self):
        with test_database():
            import logic

            logic.log_audit_action("test.action", "test", 1, details="unittest")
            entries = logic.get_audit_log(5)
            self.assertGreaterEqual(len(entries), 1)
            self.assertEqual(entries[0]["action"], "test.action")

    def test_audit_log_action_filter(self):
        with test_database():
            import logic

            logic.log_audit_action("user.login", "app_user", 1)
            logic.log_audit_action("pay_period.lock", "pay_period", None)
            login_only = logic.get_audit_log(10, action_filter="login")
            self.assertTrue(all("login" in e["action"] for e in login_only))
            self.assertGreaterEqual(len(login_only), 1)

    def test_pay_period_lock(self):
        with test_database():
            from datetime import date

            import logic

            ref = date(2026, 6, 30)
            self.assertFalse(logic.is_pay_period_locked(ref))
            locked = logic.lock_pay_period(ref)
            self.assertTrue(locked["success"])
            self.assertTrue(logic.is_pay_period_locked(ref))
            officer = get_any_officer("A")
            result = logic.save_timecard_entry(
                officer["id"],
                ref.isoformat(),
                8.0,
            )
            self.assertFalse(result["success"])
            logic.unlock_pay_period()
            self.assertFalse(logic.is_pay_period_locked(ref))

    def test_labor_budget_status(self):
        with test_database():
            import logic

            unconfigured = logic.get_labor_budget_status()
            self.assertTrue(unconfigured["success"])
            self.assertFalse(unconfigured.get("configured"))
            logic.set_department_setting("annual_labor_budget", "1000000")
            configured = logic.get_labor_budget_status()
            self.assertTrue(configured.get("configured"))
            self.assertEqual(configured["annual_budget"], 1000000.0)

    def test_open_shifts(self):
        with test_database():
            import logic

            work_date = working_date_for_squad("A")
            created = logic.create_open_shift(
                work_date.isoformat(),
                "06:00",
                "17:00",
                squad="A",
            )
            self.assertTrue(created["success"])
            shifts = logic.get_open_shifts()
            self.assertEqual(len(shifts), 1)
            notifs = logic.get_notifications()
            open_notifs = [n for n in notifs if n.get("type") == "Open Shift"]
            self.assertTrue(open_notifs)
            posted = next(n for n in open_notifs if n.get("related_type") == "open_shift")
            self.assertEqual(posted["related_id"], shifts[0]["id"])
            officer = get_any_officer("B")
            filled = logic.fill_open_shift(shifts[0]["id"], officer["id"])
            self.assertTrue(filled["success"])
            self.assertEqual(len(logic.get_open_shifts()), 0)

    def test_prefill_timecard_from_schedule(self):
        with test_database():
            import logic

            officer = get_any_officer("A")
            result = logic.prefill_timecard_from_schedule(officer["id"])
            self.assertTrue(result["success"])
            self.assertGreater(result["saved"], 0)

    def test_is_officer_unavailable_on_date(self):
        with test_database():
            import logic

            officer = get_any_officer("A")
            work = working_date_for_squad("A")
            self.assertFalse(logic.is_officer_unavailable_on_date(officer["id"], work))
            logic.add_officer_availability(officer["id"], work.isoformat())
            self.assertTrue(logic.is_officer_unavailable_on_date(officer["id"], work))

    def test_officer_schedule_window(self):
        with test_database():
            import logic

            officer = get_any_officer("A")
            week = logic.get_officer_schedule_window(officer["id"], days=7)
            self.assertTrue(week["success"])
            self.assertEqual(len(week["days"]), 7)
            statuses = {d["status"] for d in week["days"]}
            self.assertTrue(statuses.issubset({"working", "off", "bumped", "covering", "swapped"}))

    def test_copy_timecard_from_previous_period(self):
        with test_database():
            import logic

            officer = get_any_officer("A")
            prev_start, _ = logic.get_pay_period()
            prev_start = prev_start - __import__("datetime").timedelta(days=14)
            logic.save_timecard_entry(
                officer["id"],
                prev_start.isoformat(),
                7.5,
                entry_type="Overtime Earned",
                notes="prev period",
                period_start=prev_start.isoformat(),
            )
            result = logic.copy_timecard_from_previous_period(officer["id"])
            self.assertTrue(result["success"])
            self.assertGreaterEqual(result["copied"], 1)

    def test_export_coverage_pdf(self):
        with test_database():
            import os
            import tempfile

            import logic

            start, end = logic.get_current_cycle_window(date(2026, 7, 4))
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "coverage.pdf")
                result = logic.export_coverage_pdf(start, end, output_path=path)
                self.assertTrue(result.get("success"))
                self.assertTrue(os.path.exists(path))

    def test_export_pay_stub_pdf(self):
        with test_database():
            import os
            import tempfile

            import logic

            officer = get_any_officer("A")
            logic.save_timecard_entry(
                officer["id"],
                working_date_for_squad("A").isoformat(),
                8.0,
            )
            logic.create_payroll_entry(
                officer["id"],
                working_date_for_squad("A").isoformat(),
                "Overtime Earned",
                2.0,
            )
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "stub.pdf")
                result = logic.export_pay_stub_pdf(officer["id"], output_path=path)
                self.assertTrue(result.get("success"))
                self.assertTrue(os.path.exists(path))

    def test_dashboard_insights_includes_schedule_diff(self):
        with test_database():
            import logic

            insights = logic.get_dashboard_insights()
            self.assertTrue(insights["success"])
            self.assertIn("schedule_diff_count", insights)
            self.assertIsInstance(insights["schedule_diff_count"], int)
            self.assertIn("pending_swaps", insights)
            self.assertIsInstance(insights["pending_swaps"], int)
            self.assertIn("open_shifts", insights)
            self.assertIsInstance(insights["open_shifts"], int)

    def test_open_shifts_officer_squad_filter(self):
        with test_database():
            import logic

            officer_a = get_any_officer("A")
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            logic.create_open_shift(work_day, "06:00", "17:00", squad="A", notes="Squad A")
            logic.create_open_shift(work_day, "06:00", "17:00", squad="B", notes="Squad B")
            all_open = logic.get_open_shifts()
            self.assertGreaterEqual(len(all_open), 2)
            scoped = logic.get_open_shifts(officer_id=officer_a["id"])
            self.assertGreaterEqual(len(scoped), 1)
            self.assertTrue(all(not r.get("squad") or r["squad"] == "A" for r in scoped))

    def test_dashboard_insights_officer_scope(self):
        with test_database():
            import logic

            officer = get_any_officer("A")
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            logic.create_open_shift(work_day, "06:00", "17:00", squad="A")
            logic.create_open_shift(work_day, "06:00", "17:00", squad="B")
            dept = logic.get_dashboard_insights()
            scoped = logic.get_dashboard_insights(officer_id=officer["id"])
            self.assertTrue(scoped["success"])
            self.assertTrue(scoped.get("officer_scoped"))
            self.assertEqual(scoped.get("coverage_issues"), 0)
            self.assertLessEqual(scoped["pending_requests"], dept["pending_requests"])
            self.assertLessEqual(scoped["pending_swaps"], dept["pending_swaps"])
            self.assertIn("pending_manual_review", scoped)
            self.assertIsInstance(scoped["pending_manual_review"], int)
            self.assertGreaterEqual(dept.get("open_shifts", 0), 2)
            self.assertGreaterEqual(scoped.get("claimable_open_shifts", 0), 1)
            self.assertLess(scoped["claimable_open_shifts"], dept["open_shifts"])

    def test_export_schedule_diff_csv(self):
        with test_database():
            import logic
            from seed_data import seed_users_if_empty

            seed_users_if_empty()
            admin = next(u for u in logic.list_login_users() if u["role"] == "Administration")
            officer = get_any_officer("A")
            year, month = date.today().year, date.today().month
            work_day = None
            for day_num in range(1, 15):
                target = date(year, month, day_num)
                if logic.is_officer_working_on_day(officer["id"], target):
                    work_day = target
                    break
            self.assertIsNotNone(work_day)

            logic.publish_base_schedule(year, month, admin["id"])
            logic.sync_updated_schedule(year, month, admin["id"])
            logic.set_snapshot_assignment(
                year,
                month,
                "updated",
                work_day.isoformat(),
                officer["id"],
                "off",
                notes="CSV diff test",
            )
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "diff.csv")
                result = logic.export_schedule_diff_csv(year, month, path)
                self.assertTrue(result["success"], result.get("message"))
                self.assertGreaterEqual(result["count"], 1)
                with open(path, encoding="utf-8") as fh:
                    content = fh.read()
                self.assertIn("officer_name", content)
                self.assertIn(officer["name"], content)


if __name__ == "__main__":
    unittest.main()
