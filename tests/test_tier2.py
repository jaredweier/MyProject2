"""Tier 2 features — bidding, callbacks, certifications, fatigue score."""

import unittest
from datetime import date, timedelta

from tests.helpers import get_any_officer, test_database, working_date_for_squad


class Tier2FeatureTests(unittest.TestCase):
    def test_shift_bid_rankings_and_finalize_by_seniority(self):
        with test_database():
            import logic

            work_day = working_date_for_squad("A").strftime("%d-%m-%Y")
            officer_a = get_any_officer("A", "06:00")
            officer_b = get_any_officer("A", "10:00")
            created = logic.create_shift_bid_event(
                title="Test Bid",
                number_of_shifts="2",
                shift_length="10 hours",
                rotation="4/4",
                shift_start_times="06:00",
                shifts_begin=work_day,
                bids_due_by="2099-12-31 23:59",
                squad="A",
            )
            self.assertTrue(created.get("success"), created.get("message"))
            event_id = created["event_id"]
            published = logic.publish_shift_bid_event(event_id)
            self.assertTrue(published.get("success"), published.get("message"))
            self.assertEqual(published.get("option_count"), 2)

            event = logic.get_shift_bid_event(event_id)
            options = event["options"]
            opt1, opt2 = options[0]["id"], options[1]["id"]

            # Both officers want shift 1 first; senior officer_a should win it
            self.assertTrue(
                logic.submit_shift_bid_rankings(
                    event_id,
                    officer_b["id"],
                    [{"option_id": opt1, "preference_rank": 1}, {"option_id": opt2, "preference_rank": 2}],
                ).get("success")
            )
            self.assertTrue(
                logic.submit_shift_bid_rankings(
                    event_id,
                    officer_a["id"],
                    [{"option_id": opt1, "preference_rank": 1}, {"option_id": opt2, "preference_rank": 2}],
                ).get("success")
            )

            finalized = logic.finalize_shift_bid_event(event_id)
            self.assertTrue(finalized.get("success"), finalized.get("message"))
            awards = {a["officer_id"]: a for a in finalized.get("awards", [])}
            self.assertEqual(awards[officer_a["id"]]["option_id"], opt1)
            self.assertEqual(awards[officer_b["id"]]["option_id"], opt2)

    def test_supervisor_can_reassign_after_finalize(self):
        with test_database():
            import logic

            work_day = working_date_for_squad("A").strftime("%d-%m-%Y")
            officer_a = get_any_officer("A", "06:00")
            officer_b = get_any_officer("A", "10:00")
            created = logic.create_shift_bid_event(
                number_of_shifts="2",
                shifts_begin=work_day,
                bids_due_by="2099-12-31",
                squad="A",
            )
            event_id = created["event_id"]
            logic.publish_shift_bid_event(event_id)
            event = logic.get_shift_bid_event(event_id)
            opt1, opt2 = event["options"][0]["id"], event["options"][1]["id"]
            logic.submit_shift_bid_rankings(event_id, officer_a["id"], [{"option_id": opt1, "preference_rank": 1}])
            logic.submit_shift_bid_rankings(event_id, officer_b["id"], [{"option_id": opt1, "preference_rank": 1}])
            logic.finalize_shift_bid_event(event_id)

            swap = logic.update_shift_bid_assignments(
                event_id,
                [
                    {"option_id": opt1, "officer_id": officer_b["id"]},
                    {"option_id": opt2, "officer_id": officer_a["id"]},
                ],
            )
            self.assertTrue(swap.get("success"), swap.get("message"))
            self.assertEqual(swap.get("changed"), 2)

            updated = logic.get_shift_bid_event(event_id)
            by_option = {o["id"]: o["awarded_officer_id"] for o in updated["options"]}
            self.assertEqual(by_option[opt1], officer_b["id"])
            self.assertEqual(by_option[opt2], officer_a["id"])

    def test_create_shift_bid_from_simulation(self):
        with test_database():
            import logic
            from logic.scheduling_sim import run_schedule_simulation

            sim = run_schedule_simulation(
                "4-on-4-off",
                8,
                10.0,
                2080.0,
                ["06:00", "16:00"],
                apply_department_rules=False,
                min_per_shift=1,
            )
            self.assertTrue(sim.get("success"))
            payload = logic.build_shift_bid_payload_from_simulation(sim)
            self.assertTrue(payload.get("success"))
            self.assertEqual(payload["number_of_shifts"], "2")
            self.assertIn("06:00", payload["shift_start_times"])
            self.assertIn("simulator", payload["notes"].lower())

            created = logic.create_shift_bid_from_simulation(sim, publish=True)
            self.assertTrue(created.get("success"), created.get("message"))
            event = logic.get_shift_bid_event(created["event_id"])
            self.assertEqual(event["status"], "open")
            self.assertEqual(len(event["options"]), 2)

    def test_shift_bid_calendar_preview_staggers_options(self):
        with test_database():
            import logic

            created = logic.create_shift_bid_event(
                number_of_shifts="2",
                rotation="4 on 4 off",
                shift_start_times="06:00, 14:00",
                shifts_begin="01-07-2026",
            )
            event_id = created["event_id"]
            logic.publish_shift_bid_event(event_id)
            event = logic.get_shift_bid_event(event_id)
            opt1, opt2 = event["options"][0], event["options"][1]
            cal1 = logic.build_shift_bid_option_calendar(event, opt1, weeks=2)
            cal2 = logic.build_shift_bid_option_calendar(event, opt2, weeks=2)
            self.assertTrue(cal1.get("success"))
            self.assertTrue(cal2.get("success"))
            self.assertEqual(cal1["shift_start"], "06:00")
            self.assertEqual(cal2["shift_start"], "14:00")
            self.assertNotEqual(cal1["days"][0]["on"], cal2["days"][0]["on"])

    def test_officer_only_sees_active_bid_events(self):
        with test_database():
            import logic

            officer = get_any_officer("A", "06:00")
            self.assertFalse(logic.officer_has_active_shift_bid(officer["id"]))

            created = logic.create_shift_bid_event(number_of_shifts="1", squad="A")
            event_id = created["event_id"]
            self.assertFalse(logic.officer_has_active_shift_bid(officer["id"]))

            logic.publish_shift_bid_event(event_id)
            self.assertTrue(logic.officer_has_active_shift_bid(officer["id"]))

    def test_callback_rotation_and_record(self):
        with test_database():
            import logic
            from logic.callbacks import record_callback_offer

            sync = logic.sync_callback_rotation_from_roster()
            self.assertTrue(sync.get("success"))
            next_up = logic.get_next_callback_candidate()
            self.assertTrue(next_up.get("success"))
            self.assertIsNotNone(next_up.get("candidate"))

            cand = next_up["candidate"]
            # Call-down offer uses 0h (equity log only) — must not reject
            offer = record_callback_offer(
                cand["officer_id"],
                date.today().isoformat(),
                notes="OT offer (call-down)",
            )
            self.assertTrue(offer.get("success"), offer.get("message"))
            declined = record_callback_offer(
                cand["officer_id"],
                date.today().isoformat(),
                notes="declined",
                accepted=False,
            )
            self.assertTrue(declined.get("success"), declined.get("message"))
            rec = logic.record_callback_event(
                cand["officer_id"],
                date.today().isoformat(),
                2.5,
                notes="test",
            )
            self.assertTrue(rec.get("success"), rec.get("message"))
            events = logic.get_callback_events(limit=5)
            self.assertGreaterEqual(len(events), 1)

    def test_certification_gating_blocks_open_shift_claim(self):
        with test_database():
            import logic

            officer = get_any_officer("A", "19:00")
            types = logic.list_certification_types()
            firearms = next(t for t in types if t["code"] == "FIREARMS")
            logic.set_shift_cert_requirement("19:00", firearms["id"])

            work_day = working_date_for_squad("A").strftime("%Y-%m-%d")
            shift = logic.create_open_shift(work_day, "19:00", "06:00", squad="A")
            self.assertTrue(shift.get("success"))
            blocked = logic.fill_open_shift(shift["shift_id"], officer["id"])
            self.assertFalse(blocked.get("success"))

            logic.assign_officer_certification(
                officer["id"],
                firearms["id"],
                expires_date=(date.today() + timedelta(days=365)).isoformat(),
            )
            ok = logic.fill_open_shift(shift["shift_id"], officer["id"])
            self.assertTrue(ok.get("success"), ok.get("message"))

    def test_parse_bids_due_datetime_formats(self):
        from validators import parse_bids_due_datetime

        self.assertIsNotNone(parse_bids_due_datetime("2099-12-31 23:59"))
        self.assertIsNotNone(parse_bids_due_datetime("31-12-2099 17:00"))
        self.assertIsNotNone(parse_bids_due_datetime("01-07-2026"))
        self.assertIsNone(parse_bids_due_datetime(""))

    def test_preview_shift_bid_awards(self):
        with test_database():
            import logic

            work_day = working_date_for_squad("A").strftime("%d-%m-%Y")
            officer_a = get_any_officer("A", "06:00")
            officer_b = get_any_officer("A", "10:00")
            created = logic.create_shift_bid_event(
                number_of_shifts="2",
                shifts_begin=work_day,
                bids_due_by="2099-12-31",
                squad="A",
            )
            event_id = created["event_id"]
            logic.publish_shift_bid_event(event_id)
            event = logic.get_shift_bid_event(event_id)
            opt1, opt2 = event["options"][0]["id"], event["options"][1]["id"]
            logic.submit_shift_bid_rankings(event_id, officer_b["id"], [{"option_id": opt1, "preference_rank": 1}])
            logic.submit_shift_bid_rankings(event_id, officer_a["id"], [{"option_id": opt1, "preference_rank": 1}])
            preview = logic.preview_shift_bid_awards(event_id)
            self.assertTrue(preview.get("success"))
            awards = {a["officer_id"]: a for a in preview.get("awards", [])}
            self.assertEqual(awards[officer_a["id"]]["option_id"], opt1)

    def test_participation_report_lists_missing(self):
        with test_database():
            import logic

            created = logic.create_shift_bid_event(number_of_shifts="1", squad="A")
            event_id = created["event_id"]
            logic.publish_shift_bid_event(event_id)
            report = logic.get_shift_bid_participation_report(event_id)
            self.assertTrue(report.get("success"))
            self.assertGreaterEqual(report.get("eligible_count", 0), 1)
            self.assertEqual(report.get("respondent_count"), 0)
            self.assertGreaterEqual(len(report.get("missing_officers", [])), 1)

    def test_save_and_import_simulator_scenario(self):
        with test_database():
            import logic
            from logic.scheduling_sim import run_schedule_simulation

            sim = run_schedule_simulation(
                "4-on-4-off", 8, 10.0, 2080.0, ["06:00"], apply_department_rules=False, min_per_shift=1
            )
            saved = logic.save_simulator_scenario("Test scenario", config=sim.get("simulation_config", {}), result=sim)
            self.assertTrue(saved.get("success"))
            loaded = logic.load_simulator_scenario_for_bid(saved["scenario_id"])
            self.assertTrue(loaded.get("success"))

    def test_officer_finalized_awards_visible(self):
        with test_database():
            import logic

            work_day = working_date_for_squad("A").strftime("%d-%m-%Y")
            officer = get_any_officer("A", "06:00")
            created = logic.create_shift_bid_event(number_of_shifts="1", shifts_begin=work_day, squad="A")
            event_id = created["event_id"]
            logic.publish_shift_bid_event(event_id)
            opt = logic.get_shift_bid_event(event_id)["options"][0]["id"]
            logic.submit_shift_bid_rankings(event_id, officer["id"], [{"option_id": opt, "preference_rank": 1}])
            logic.finalize_shift_bid_event(event_id)
            awards = logic.get_officer_shift_bid_awards(officer["id"])
            self.assertEqual(len(awards), 1)
            self.assertEqual(awards[0]["option_id"], opt)

    def test_fatigue_score_in_valid_range(self):
        with test_database():
            import logic

            officer = get_any_officer("A")
            score = logic.compute_fatigue_score(officer["id"])
            self.assertTrue(score.get("success"))
            self.assertGreaterEqual(score["score"], 0.0)
            self.assertLessEqual(score["score"], 100.0)

            board = logic.get_fatigue_scoreboard(limit=5)
            self.assertTrue(board.get("success"))
            self.assertGreaterEqual(len(board.get("officers", [])), 1)


if __name__ == "__main__":
    unittest.main()
