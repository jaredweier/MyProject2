import os
import tempfile
import unittest
from datetime import date

from permissions import role_has_permission
from tests.helpers import get_any_officer, test_database


class TimecardScheduleTests(unittest.TestCase):
    def test_permissions_stub(self):
        self.assertTrue(role_has_permission("Officer", "timecard.edit_own"))
        self.assertFalse(role_has_permission("Officer", "schedule.base.publish"))
        self.assertFalse(role_has_permission("Officer", "reports.view"))
        self.assertFalse(role_has_permission("Officer", "database.backup"))
        self.assertTrue(role_has_permission("Supervisor", "database.backup"))
        self.assertTrue(role_has_permission("Administration", "schedule.base.publish"))
        self.assertTrue(role_has_permission("Supervisor", "reports.view"))
        self.assertTrue(role_has_permission("Administration", "holidays.manage"))
        self.assertFalse(role_has_permission("Supervisor", "holidays.manage"))
        self.assertFalse(role_has_permission("Officer", "holidays.manage"))

    def test_pay_period_history(self):
        with test_database():
            import logic

            officer = get_any_officer("A")
            period_start, _ = logic.get_pay_period()
            logic.save_timecard_entry(
                officer["id"],
                period_start.isoformat(),
                8.0,
            )
            history = logic.get_pay_period_history(3)
            self.assertTrue(history["success"])
            self.assertGreaterEqual(len(history["periods"]), 1)
            self.assertEqual(history["periods"][0]["period_start"], period_start.isoformat())

    def test_pay_period_history_officer_scope(self):
        with test_database():
            import logic

            officer = get_any_officer("A")
            period_start, _ = logic.get_pay_period()
            logic.save_timecard_entry(officer["id"], period_start.isoformat(), 6.0)
            scoped = logic.get_pay_period_history(3, officer_id=officer["id"])
            self.assertEqual(len(scoped["periods"]), 1)
            self.assertEqual(scoped["periods"][0]["officer_count"], 1)
            self.assertEqual(scoped["periods"][0]["total_hours"], 6.0)

    def test_dodgeville_pay_period_anchor(self):
        with test_database():
            from datetime import date

            import logic

            start, end = logic.get_pay_period(date(2026, 6, 30))
            self.assertEqual(start, date(2026, 6, 22))
            self.assertEqual(end, date(2026, 7, 5))
            rot_start, _ = logic.get_current_cycle_window(date(2026, 6, 30))
            self.assertNotEqual(start, rot_start)

    def test_pay_period_navigation(self):
        with test_database():
            from datetime import date

            import logic

            start, end = logic.get_pay_period(date(2026, 6, 30))
            prev_start, prev_end = logic.get_adjacent_pay_period(start, -1)
            self.assertEqual((prev_end - prev_start).days, 13)
            self.assertEqual(prev_start, date(2026, 6, 8))
            next_start, _ = logic.get_adjacent_pay_period(start, 1)
            self.assertEqual(next_start, date(2026, 7, 6))
            ref = date(2026, 6, 30)
            self.assertFalse(logic.is_future_pay_period(start, reference=ref))
            self.assertTrue(logic.is_future_pay_period(next_start, reference=ref))

    def test_overnight_shift_counts_in_start_period(self):
        with test_database():
            from datetime import date

            import logic

            officer = get_any_officer("A")
            period_end = date(2026, 7, 5)
            result = logic.save_timecard_entry(
                officer["id"],
                period_end.isoformat(),
                11.0,
                time_in="19:00",
                time_out="06:00",
            )
            self.assertTrue(result["success"], result.get("message"))
            self.assertTrue(result.get("overnight"))

            data = logic.get_timecard_period(officer["id"], date(2026, 6, 22))
            july5 = next(d for d in data["days"] if d["entry_date"] == period_end.isoformat())
            self.assertTrue(july5.get("overnight"))
            self.assertEqual(july5["hours_worked"], 11.0)

    def test_timecard_save_and_import(self):
        with test_database():
            import logic

            officer = get_any_officer("A")
            period_start, _ = logic.get_pay_period()
            result = logic.save_timecard_entry(
                officer["id"],
                period_start.isoformat(),
                4.0,
                entry_type="Overtime Earned",
                notes="Test OT",
            )
            self.assertTrue(result["success"], result.get("message"))

            imported = logic.import_timecard_to_payroll(officer["id"], period_start.isoformat())
            self.assertTrue(imported["success"], imported.get("message"))
            entries = logic.get_payroll_entries(officer_id=officer["id"], limit=5)
            self.assertTrue(any(e["entry_type"] == "Overtime Earned" for e in entries))

    def test_multiple_timecard_entries_same_day(self):
        with test_database():
            import logic

            officer = get_any_officer("A")
            period_start, _ = logic.get_pay_period()
            day = period_start.isoformat()

            regular = logic.save_timecard_entry(
                officer["id"],
                day,
                8.0,
                entry_type="Regular Hours",
            )
            self.assertTrue(regular["success"], regular.get("message"))
            regular_id = regular["timecard_id"]

            ot = logic.save_timecard_entry(
                officer["id"],
                day,
                2.0,
                entry_type="Overtime Earned",
                notes="Court OT",
            )
            self.assertTrue(ot["success"], ot.get("message"))
            self.assertNotEqual(ot["timecard_id"], regular_id)

            data = logic.get_timecard_period(officer["id"], period_start)
            day_row = next(d for d in data["days"] if d["entry_date"] == day)
            self.assertEqual(len(day_row["entries"]), 2)
            types = {e["entry_type"] for e in day_row["entries"]}
            self.assertEqual(types, {"Regular Hours", "Overtime Earned"})

            update = logic.save_timecard_entry(
                officer["id"],
                day,
                8.5,
                entry_type="Regular Hours",
                timecard_id=regular_id,
            )
            self.assertTrue(update["success"], update.get("message"))

            removed = logic.delete_timecard_entry(ot["timecard_id"], officer["id"])
            self.assertTrue(removed["success"], removed.get("message"))
            data = logic.get_timecard_period(officer["id"], period_start)
            day_row = next(d for d in data["days"] if d["entry_date"] == day)
            self.assertEqual(len(day_row["entries"]), 1)
            self.assertEqual(day_row["entries"][0]["hours_worked"], 8.5)

    def test_ensure_original_monthly_schedule_auto_generates(self):
        with test_database():
            import logic

            year, month = 2026, 8
            before = logic.get_schedule_snapshot(year, month, "base")
            self.assertIsNone(before)

            result = logic.ensure_original_monthly_schedule(year, month)
            self.assertTrue(result["success"], result.get("message"))
            self.assertTrue(result.get("created"))

            snapshot = logic.get_schedule_snapshot(year, month, "base")
            self.assertIsNotNone(snapshot)
            self.assertEqual(snapshot["locked"], 1)
            self.assertGreater(len(snapshot["rows"]), 0)

            officer = logic.get_officers_by_seniority()[0]
            work_rows = [r for r in snapshot["rows"] if r["officer_id"] == officer["id"] and r["status"] == "working"]
            self.assertGreater(len(work_rows), 0)
            for row in work_rows:
                self.assertEqual(row["shift_start"], officer["shift_start"])
                self.assertEqual(row["shift_end"], officer["shift_end"])

            again = logic.ensure_original_monthly_schedule(year, month)
            self.assertTrue(again["success"])
            self.assertFalse(again.get("created"))

    def test_publish_base_and_sync_updated(self):
        with test_database():
            import logic
            from seed_data import seed_users_if_empty

            seed_users_if_empty()
            users = logic.list_login_users()
            admin = next(u for u in users if u["role"] == "Administration")

            year, month = date.today().year, date.today().month
            pub = logic.publish_base_schedule(year, month, admin["id"])
            self.assertTrue(pub["success"], pub.get("message"))

            base = logic.get_schedule_snapshot(year, month, "base")
            self.assertIsNotNone(base)
            self.assertEqual(base["locked"], 1)
            self.assertGreater(len(base["rows"]), 0)

            sync = logic.sync_updated_schedule(year, month, admin["id"])
            self.assertTrue(sync["success"], sync.get("message"))
            updated = logic.get_schedule_snapshot(year, month, "updated")
            self.assertIsNotNone(updated)

    def test_base_summary_without_snapshot(self):
        with test_database():
            import logic

            summary = logic.get_monthly_summary_from_snapshot(None, 2026, 6, "base")
            self.assertEqual(len(summary), 30)
            self.assertGreater(summary[0]["working_officers"], 0)

    def test_compare_base_updated_no_diff_after_sync(self):
        with test_database():
            import logic
            from seed_data import seed_users_if_empty

            seed_users_if_empty()
            admin = next(u for u in logic.list_login_users() if u["role"] == "Administration")
            year, month = date.today().year, date.today().month

            logic.publish_base_schedule(year, month, admin["id"])
            logic.sync_updated_schedule(year, month, admin["id"])
            result = logic.compare_base_updated_schedule(year, month)
            self.assertTrue(result["success"], result.get("message"))
            self.assertEqual(result["diff_count"], 0)

    def test_compare_base_updated_detects_manual_edit(self):
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
            self.assertIsNotNone(work_day, "Need a working day in first half of month")

            logic.publish_base_schedule(year, month, admin["id"])
            logic.sync_updated_schedule(year, month, admin["id"])
            logic.set_snapshot_assignment(
                year,
                month,
                "updated",
                work_day.isoformat(),
                officer["id"],
                "off",
                notes="Manual day off",
            )
            result = logic.compare_base_updated_schedule(year, month)
            self.assertTrue(result["success"], result.get("message"))
            self.assertGreaterEqual(result["diff_count"], 1)
            match = next(
                (d for d in result["diffs"] if d["officer_id"] == officer["id"]),
                None,
            )
            self.assertIsNotNone(match)
            self.assertEqual(match["base_status"], "working")
            self.assertEqual(match["updated_status"], "off")

    def test_compare_base_updated_officer_filter(self):
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
                notes="Officer filter test",
            )
            all_result = logic.compare_base_updated_schedule(year, month)
            scoped = logic.compare_base_updated_schedule(year, month, officer_id=officer["id"])
            self.assertTrue(scoped["success"])
            self.assertGreaterEqual(all_result["diff_count"], scoped["diff_count"])
            self.assertGreaterEqual(scoped["diff_count"], 1)
            self.assertTrue(all(d["officer_id"] == officer["id"] for d in scoped["diffs"]))

    def test_export_schedule_diff_csv_officer_scope(self):
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
                notes="Scoped CSV",
            )
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "scoped_diff.csv")
                result = logic.export_schedule_diff_csv(
                    year,
                    month,
                    path,
                    officer_id=officer["id"],
                )
                self.assertTrue(result["success"], result.get("message"))
                self.assertGreaterEqual(result["count"], 1)
                with open(path, encoding="utf-8") as fh:
                    content = fh.read()
                self.assertIn(officer["name"], content)

    def test_export_pay_period_history_csv(self):
        with test_database():
            import logic

            officer = get_any_officer("A")
            period_start, _ = logic.get_pay_period()
            logic.save_timecard_entry(officer["id"], period_start.isoformat(), 6.0)
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "history.csv")
                result = logic.export_pay_period_history_csv(
                    limit=3,
                    officer_id=officer["id"],
                    output_path=path,
                )
                self.assertTrue(result["success"], result.get("message"))
                self.assertGreaterEqual(result["count"], 1)
                with open(path, encoding="utf-8") as fh:
                    content = fh.read()
                self.assertIn("period_start", content)
                from validators import format_date

                self.assertIn(format_date(period_start), content)

    def test_export_timecard_csv(self):
        with test_database():
            import logic

            officer = get_any_officer("A")
            period_start, _ = logic.get_pay_period()
            logic.save_timecard_entry(
                officer["id"],
                period_start.isoformat(),
                8.0,
            )
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "timecard.csv")
                result = logic.export_timecard_csv(
                    period_start=period_start,
                    officer_id=officer["id"],
                    output_path=path,
                )
                self.assertTrue(result["success"], result.get("message"))
                self.assertGreaterEqual(result["count"], 1)
                with open(path, encoding="utf-8") as fh:
                    content = fh.read()
                self.assertIn("officer_name", content)
                self.assertIn(officer["name"], content)


if __name__ == "__main__":
    unittest.main()
