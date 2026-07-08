import os
import unittest

from tests.helpers import get_any_officer, test_database, working_date_for_squad


class TestNotificationsSwapsExports(unittest.TestCase):
    def test_day_off_creates_notifications(self):
        with test_database():
            import logic

            officer = get_any_officer("A")
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            cr = logic.create_day_off_request(officer["id"], work_day, "Vacation")
            self.assertTrue(cr["success"])

            notes = logic.get_notifications(officer_id=officer["id"])
            self.assertTrue(any(n["type"] == "day_off" for n in notes))
            self.assertGreater(logic.get_unread_notification_count(officer_id=officer["id"]), 0)

    def test_approve_day_off_notifies_replacement(self):
        with test_database():
            import logic

            officer = get_any_officer("A", "06:00")
            bump_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            cr = logic.create_day_off_request(officer["id"], bump_day, "Vacation")
            result = logic.process_day_off_request(cr["request_id"], "approve")
            self.assertTrue(result.success)

            all_notes = logic.get_notifications()
            self.assertTrue(any("Approved" in n["title"] or "Coverage" in n["title"] for n in all_notes))

    def test_process_shift_swap_creates_overrides(self):
        with test_database():
            import logic
            from database import get_connection

            o1 = get_any_officer("A", "06:00")
            o2 = get_any_officer("A", "10:00")
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            cr = logic.create_shift_swap_request(o1["id"], o2["id"], work_day)
            self.assertTrue(cr["success"])

            result = logic.process_shift_swap(cr["swap_id"], "approve")
            self.assertTrue(result.success)
            self.assertTrue(result.overrides_created)

            conn = get_connection()
            c = conn.cursor()
            c.execute(
                "SELECT COUNT(*) FROM schedule_overrides WHERE override_date = ? AND reason = 'Shift Swap'",
                (work_day,),
            )
            self.assertEqual(c.fetchone()[0], 2)
            conn.close()

    def test_mark_notification_read(self):
        with test_database():
            import logic

            officer = get_any_officer("A")
            logic.create_notification(officer["id"], "test", "Title", "Body")
            notes = logic.get_notifications(officer_id=officer["id"], unread_only=True)
            self.assertEqual(len(notes), 1)
            logic.mark_notification_read(notes[0]["id"])
            self.assertEqual(logic.get_unread_notification_count(officer_id=officer["id"]), 0)

    def test_export_schedule_pdf(self):
        with test_database():
            import logic
            from paths import data_path

            start, end = logic.get_current_cycle_window()
            out = data_path("exports/test_schedule.pdf")
            if os.path.exists(out):
                os.unlink(out)
            result = logic.export_schedule_pdf(start, end, output_path=out)
            self.assertTrue(result["success"])
            self.assertTrue(os.path.isfile(out))
            os.unlink(out)

    def test_export_schedule_pdf_officer_scope(self):
        with test_database():
            import logic
            from paths import data_path

            officer = get_any_officer("A")
            start, end = logic.get_current_cycle_window()
            out = data_path("exports/test_schedule_officer.pdf")
            if os.path.exists(out):
                os.unlink(out)
            result = logic.export_schedule_pdf(
                start,
                end,
                officer_id=officer["id"],
                output_path=out,
            )
            self.assertTrue(result["success"], result.get("message"))
            self.assertTrue(os.path.isfile(out))
            os.unlink(out)

    def test_export_payroll_pdf(self):
        with test_database():
            import logic
            from paths import data_path

            officer = get_any_officer("A")
            logic.create_payroll_entry(officer["id"], "2026-07-01", "Overtime Earned", 4.0)
            out = data_path("exports/test_payroll.pdf")
            if os.path.exists(out):
                os.unlink(out)
            result = logic.export_payroll_pdf(officer_id=officer["id"], output_path=out)
            self.assertTrue(result["success"])
            self.assertTrue(os.path.isfile(out))
            os.unlink(out)

    def test_export_payroll_pdf_period_start(self):
        with test_database():
            import logic
            from paths import data_path
            from validators import parse_date

            officer = get_any_officer("A")
            logic.create_payroll_entry(officer["id"], "2026-07-01", "Overtime Earned", 4.0)
            out = data_path("exports/test_payroll_period.pdf")
            if os.path.exists(out):
                os.unlink(out)
            result = logic.export_payroll_pdf(
                officer_id=officer["id"],
                period_start=parse_date("2026-07-01"),
                output_path=out,
            )
            self.assertTrue(result["success"], result.get("message"))
            self.assertTrue(os.path.isfile(out))
            os.unlink(out)

    def test_export_requests_pdf(self):
        with test_database():
            import logic
            from paths import data_path

            officer = get_any_officer("A")
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            logic.create_day_off_request(officer["id"], work_day, "Vacation")
            out = data_path("exports/test_requests.pdf")
            if os.path.exists(out):
                os.unlink(out)
            result = logic.export_requests_pdf(output_path=out)
            self.assertTrue(result["success"])
            self.assertTrue(os.path.isfile(out))
            os.unlink(out)

    def test_export_requests_csv(self):
        with test_database():
            import logic

            officer = get_any_officer("A")
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            logic.create_day_off_request(officer["id"], work_day, "Vacation")
            with __import__("tempfile").TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "requests.csv")
                result = logic.export_requests_csv(output_path=path)
                self.assertTrue(result["success"], result.get("message"))
                self.assertGreaterEqual(result["count"], 1)
                with open(path, encoding="utf-8") as fh:
                    content = fh.read()
                self.assertIn("officer_name", content)
                self.assertIn(officer["name"], content)

    def test_process_shift_swap_reject(self):
        with test_database():
            import logic

            o1 = get_any_officer("A", "06:00")
            o2 = get_any_officer("A", "10:00")
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            cr = logic.create_shift_swap_request(o1["id"], o2["id"], work_day)
            result = logic.process_shift_swap(cr["swap_id"], "reject")
            self.assertTrue(result.success)
            self.assertEqual(result.status, "Rejected")
            self.assertFalse(result.overrides_created)

            notes = logic.get_notifications()
            self.assertTrue(any("Rejected" in n["title"] for n in notes))

    def test_notifications_unread_filter(self):
        with test_database():
            import logic

            officer = get_any_officer("A")
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            logic.create_day_off_request(officer["id"], work_day, "Vacation")
            unread = logic.get_notifications(officer_id=officer["id"], unread_only=True)
            self.assertGreater(len(unread), 0)
            logic.mark_all_notifications_read(officer_id=officer["id"])
            unread_after = logic.get_notifications(officer_id=officer["id"], unread_only=True)
            self.assertEqual(len(unread_after), 0)
            all_notes = logic.get_notifications(officer_id=officer["id"])
            read_only = [n for n in all_notes if n.get("is_read")]
            self.assertGreater(len(read_only), 0)

    def test_resolve_notification_navigation(self):
        import logic

        cases = [
            (
                {"type": "day_off", "related_type": "day_off_request", "related_id": 7},
                {"page": "requests", "highlight": "request", "related_id": 7},
            ),
            (
                {
                    "type": "day_off",
                    "related_type": "day_off_request",
                    "related_id": 9,
                    "title": "Manual Review Required",
                },
                {
                    "page": "requests",
                    "highlight": "request",
                    "related_id": 9,
                    "request_filter": "Pending Manual Review",
                },
            ),
            (
                {
                    "type": "day_off",
                    "related_type": "day_off_request",
                    "related_id": 11,
                    "title": "Day-Off Needs Review",
                },
                {"page": "requests", "highlight": "request", "related_id": 11, "request_view": "review"},
            ),
            (
                {"type": "day_off", "related_type": "day_off_request", "related_id": 2, "title": "New Day-Off Request"},
                {"page": "requests", "highlight": "request", "related_id": 2, "request_view": "queue"},
            ),
            (
                {"type": "shift_swap", "related_type": "shift_swap", "related_id": 3},
                {"page": "swaps", "highlight": "swap", "related_id": 3},
            ),
            (
                {"type": "Open Shift", "related_type": "open_shift", "related_id": 12},
                {"page": "availability", "highlight": "open_shift", "related_id": 12},
            ),
            (
                {"type": "availability", "related_type": "availability", "related_id": 5},
                {"page": "availability", "highlight": "availability", "related_id": 5},
            ),
            ({"type": "Payroll", "related_type": "pay_period"}, {"page": "timecard", "refresh": "timecard"}),
            ({"type": "test", "related_type": ""}, None),
        ]
        for note, expected in cases:
            with self.subTest(note=note):
                target = logic.resolve_notification_navigation(note)
                if expected is None:
                    self.assertIsNone(target)
                else:
                    self.assertIsNotNone(target)
                    for key, value in expected.items():
                        self.assertEqual(target.get(key), value)

    def test_open_shift_notification_navigation_target(self):
        with test_database():
            import logic

            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            logic.create_open_shift(work_day, "06:00", "17:00", squad="A")
            note = next(
                n
                for n in logic.get_notifications()
                if n.get("type") == "Open Shift" and n.get("related_type") == "open_shift"
            )
            target = logic.resolve_notification_navigation(note)
            self.assertEqual(target["page"], "availability")
            self.assertEqual(target["highlight"], "open_shift")
            self.assertEqual(target["related_id"], note["related_id"])

    def test_shift_swap_date_filter(self):
        with test_database():
            import logic

            o1 = get_any_officer("A", "06:00")
            o2 = get_any_officer("A", "10:00")
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            logic.create_shift_swap_request(o1["id"], o2["id"], work_day)
            all_swaps = logic.get_shift_swap_requests()
            self.assertEqual(len(all_swaps), 1)
            filtered = logic.get_shift_swap_requests(date_from=work_day, date_to=work_day)
            self.assertEqual(len(filtered), 1)
            empty = logic.get_shift_swap_requests(date_from="2099-01-01")
            self.assertEqual(len(empty), 0)

    def test_export_shift_swaps_pdf(self):
        with test_database():
            import logic
            from paths import data_path

            o1 = get_any_officer("A", "06:00")
            o2 = get_any_officer("A", "10:00")
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            logic.create_shift_swap_request(o1["id"], o2["id"], work_day)
            out = data_path("exports/test_swaps.pdf")
            if os.path.exists(out):
                os.unlink(out)
            result = logic.export_shift_swaps_pdf(output_path=out)
            self.assertTrue(result["success"], result.get("message"))
            self.assertTrue(os.path.isfile(out))
            os.unlink(out)

    def test_export_shift_swaps_csv(self):
        with test_database():
            import logic

            o1 = get_any_officer("A", "06:00")
            o2 = get_any_officer("A", "10:00")
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            logic.create_shift_swap_request(o1["id"], o2["id"], work_day)
            with __import__("tempfile").TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "swaps.csv")
                result = logic.export_shift_swaps_csv(output_path=path)
                self.assertTrue(result["success"], result.get("message"))
                self.assertGreaterEqual(result["count"], 1)
                with open(path, encoding="utf-8") as fh:
                    content = fh.read()
                self.assertIn("officer1_name", content)
                self.assertIn(o1["name"], content)

    def test_shift_swap_officer_filter(self):
        with test_database():
            import logic

            o1 = get_any_officer("A", "06:00")
            o2 = get_any_officer("A", "10:00")
            o3 = get_any_officer("B", "06:00")
            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            logic.create_shift_swap_request(o1["id"], o2["id"], work_day)
            scoped = logic.get_shift_swap_requests(officer_id=o3["id"])
            self.assertEqual(len(scoped), 0)
            involved = logic.get_shift_swap_requests(officer_id=o1["id"])
            self.assertEqual(len(involved), 1)

    def test_export_requests_pdf_officer_scope(self):
        with test_database():
            import logic
            from paths import data_path

            officer_a = get_any_officer("A")
            officer_b = get_any_officer("B")
            work_a = working_date_for_squad("A").strftime("%Y-%m-%d")
            work_b = working_date_for_squad("B").strftime("%Y-%m-%d")
            logic.create_day_off_request(officer_a["id"], work_a, "Vacation")
            logic.create_day_off_request(officer_b["id"], work_b, "Sick")
            out = data_path("exports/test_scoped_requests.pdf")
            if os.path.exists(out):
                os.unlink(out)
            result = logic.export_requests_pdf(officer_id=officer_a["id"], output_path=out)
            self.assertTrue(result["success"], result.get("message"))
            self.assertTrue(os.path.isfile(out))
            os.unlink(out)

    def test_export_requests_csv_officer_scope(self):
        with test_database():
            import logic

            officer_a = get_any_officer("A")
            officer_b = get_any_officer("B")
            work_a = working_date_for_squad("A").strftime("%Y-%m-%d")
            work_b = working_date_for_squad("B").strftime("%Y-%m-%d")
            logic.create_day_off_request(officer_a["id"], work_a, "Vacation")
            logic.create_day_off_request(officer_b["id"], work_b, "Sick")
            with __import__("tempfile").TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "scoped.csv")
                result = logic.export_requests_csv(officer_id=officer_a["id"], output_path=path)
                self.assertTrue(result["success"], result.get("message"))
                self.assertEqual(result["count"], 1)
                with open(path, encoding="utf-8") as fh:
                    content = fh.read()
                self.assertIn(officer_a["name"], content)
                self.assertNotIn(officer_b["name"], content)


if __name__ == "__main__":
    unittest.main()
