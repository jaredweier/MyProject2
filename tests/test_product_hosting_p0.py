"""Product expansion: hosting, notify outbox, equity, stations, branding constants."""

from __future__ import annotations

import unittest

from tests.helpers import test_database


class ProductHostingP0Tests(unittest.TestCase):
    def test_company_and_product_branding(self):
        from config import APP_NAME, COMPANY_NAME, PRODUCT_NAME

        self.assertEqual(APP_NAME, "Chronos Command")
        self.assertEqual(PRODUCT_NAME, "Chronos Command")
        self.assertIn("Weierworks", COMPANY_NAME)

    def test_hosting_config(self):
        from logic.hosting import deployment_checklist, get_hosting_config

        cfg = get_hosting_config()
        self.assertIn("online", cfg)
        self.assertIn("tenant_id", cfg)
        cl = deployment_checklist()
        self.assertTrue(cl.get("success"))
        self.assertEqual(cl.get("vendor"), "Weierworks Technologies, LLC")

    def test_notify_outbox_queue_without_twilio(self):
        with test_database():
            from logic.notify_channels import dispatch_channel_hooks, get_notify_channel_config, test_notify_channels
            from logic.notify_queue import list_notify_outbox, notify_outbox_stats, process_notify_outbox
            from logic.operations import set_department_setting

            set_department_setting("notify_email_enabled", "1")
            set_department_setting("notify_sms_enabled", "1")
            # no SMTP / Twilio — should still queue
            r = dispatch_channel_hooks(
                subject="Test vacancy",
                body="Open shift tonight",
                officer_ids=None,
            )
            self.assertTrue(r.get("success"))
            stats = notify_outbox_stats()
            self.assertGreaterEqual(stats.get("total", 0), 1)
            proc = process_notify_outbox(limit=20)
            self.assertTrue(proc.get("success"))
            cfg = get_notify_channel_config()
            self.assertIn("twilio_ready", cfg)
            t = test_notify_channels()
            self.assertTrue(t.get("success"))
            rows = list_notify_outbox(limit=5)
            self.assertTrue(isinstance(rows, list))

    def test_notify_templates_p0(self):
        from logic.notify_channels import format_notify_template

        for key in (
            "open_shift",
            "shift_bid_open",
            "callback_offer",
            "vacancy_blast",
            "court_reminder",
            "leave_decision",
        ):
            t = format_notify_template(key, date="7/16/26", start="19:00", end="03:00", title="Bid", due="7/20")
            self.assertTrue(t.get("subject") or t.get("body"))

    def test_ot_equity_dual_ledger(self):
        with test_database():
            from logic.officers import get_officers_by_seniority
            from logic.ot_equity_ledger import (
                export_ot_equity_dual_csv,
                get_ot_equity_summary,
                record_ot_offer,
                record_ot_worked,
            )

            officers = get_officers_by_seniority()
            self.assertTrue(officers)
            oid = officers[0]["id"]
            self.assertTrue(record_ot_offer(oid, 4.0, event_date="2026-07-16").get("success"))
            self.assertTrue(record_ot_worked(oid, 4.0, event_date="2026-07-16").get("success"))
            s = get_ot_equity_summary()
            self.assertTrue(s.get("success"))
            self.assertGreaterEqual(s.get("count", 0), 1)
            ex = export_ot_equity_dual_csv()
            self.assertTrue(ex.get("success"))

    def test_stations_and_presets(self):
        with test_database():
            from logic.officers import get_officers_by_seniority, update_officer
            from logic.rotation_presets_catalog import apply_rotation_preset_metadata, list_rotation_presets
            from logic.stations import (
                assign_unassigned_to_station,
                bulk_set_station,
                ensure_default_hq_station,
                get_station_min_staffing_matrix,
                list_station_posts,
                station_staffing_board,
                upsert_station_post,
            )

            r = upsert_station_post("HQ", "Headquarters", min_staff=2)
            self.assertTrue(r.get("success"))
            self.assertTrue(list_station_posts())
            m = get_station_min_staffing_matrix()
            self.assertIn("HQ", m.get("matrix") or {})
            board = station_staffing_board()
            self.assertTrue(board.get("success"))
            # seed-style: ensure + bulk assign unassigned
            ensure_default_hq_station()
            assign_unassigned_to_station("HQ")
            bulk = bulk_set_station("HQ", only_unassigned=False, only_active=True)
            self.assertTrue(bulk.get("success"))
            board2 = station_staffing_board()
            hq = next((p for p in (board2.get("posts") or []) if p.get("code") == "HQ"), None)
            self.assertIsNotNone(hq)
            self.assertGreaterEqual(int(hq.get("assigned") or 0), 1)
            # explicit update still works
            oid = get_officers_by_seniority()[0]["id"]
            update_officer(oid, station="HQ")
            presets = list_rotation_presets()
            self.assertGreaterEqual(presets.get("count", 0), 3)
            self.assertTrue(apply_rotation_preset_metadata("pitman_2_2_3").get("success"))

    def test_dual_workforce_and_geofence(self):
        with test_database():
            from logic.dual_workforce import (
                flsa_profile_for_officer,
                get_dual_workforce_settings,
                save_dual_workforce_settings,
            )
            from logic.geofence_clock import get_geofence_config, record_geofence_punch, save_geofence_config
            from logic.officers import get_officers_by_seniority

            save_dual_workforce_settings(dual_flsa_enabled=True, civilian_weekly_threshold=40)
            s = get_dual_workforce_settings()
            self.assertTrue(s.get("dual_flsa_enabled"))
            prof = flsa_profile_for_officer({"workforce_class": "civilian"})
            self.assertEqual(prof.get("ot_basis"), "weekly_40")
            save_geofence_config(enabled=False, lat=43.0, lon=-89.0, radius_m=150)
            self.assertTrue(get_geofence_config().get("lat"))
            oid = get_officers_by_seniority()[0]["id"]
            # fence off → punch allowed
            p = record_geofence_punch(oid, "in", lat=43.0, lon=-89.0)
            self.assertTrue(p.get("success"))

    def test_impl_kit_and_cad_export(self):
        with test_database():
            from logic.cad_rms_export import export_duty_roster_for_cad
            from logic.product_impl_kit import export_implementation_kit, get_implementation_kit

            kit = get_implementation_kit()
            self.assertEqual(kit.get("vendor"), "Weierworks Technologies, LLC")
            self.assertGreaterEqual(len(kit.get("setup_steps") or []), 5)
            ex = export_implementation_kit()
            self.assertTrue(ex.get("success"))
            cad = export_duty_roster_for_cad(days=1)
            self.assertTrue(cad.get("success"))

    def test_fatigue_gate_api(self):
        with test_database():
            from logic.fatigue_gates import (
                check_rest_hard_stop,
                fatigue_watchlist,
                rest_fatigue_hard_stops_enabled,
            )
            from logic.officers import get_officers_by_seniority
            from logic.ops_desk import get_ops_desk_board

            self.assertTrue(isinstance(rest_fatigue_hard_stops_enabled(), bool))
            oid = get_officers_by_seniority()[0]["id"]
            r = check_rest_hard_stop(oid, work_date="2026-07-16")
            self.assertIn("success", r)
            wl = fatigue_watchlist(limit=5, min_score=0)
            self.assertTrue(wl.get("success"))
            self.assertIn("items", wl)
            board = get_ops_desk_board()
            self.assertIn("station_board", board)
            self.assertIn("fatigue_watch", board)
            self.assertIn("station_under", board.get("kpi") or {})
            self.assertIn("fatigue_flags", board.get("kpi") or {})

    def test_ot_fill_fatigue_annotation(self):
        with test_database():
            from logic.officers import get_officers_by_seniority
            from logic.ot_fill import list_ot_fill_candidates
            from tests.helpers import working_date_for_squad

            officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
            self.assertGreaterEqual(len(officers), 2)
            o = officers[0]
            wd = working_date_for_squad(o.get("squad") or "A")
            fill = list_ot_fill_candidates(
                int(o["id"]),
                wd.isoformat(),
                o.get("squad") or "A",
                o.get("shift_start") or "06:00",
            )
            self.assertTrue(fill.get("success"))
            cands = fill.get("candidates") or []
            self.assertTrue(cands)
            self.assertIn("fatigue_score", cands[0])

    def test_ldap_field_trial_export(self):
        with test_database():
            from logic.ldap_auth import export_ldap_field_trial_report, ldap_field_trial_checklist

            c = ldap_field_trial_checklist()
            self.assertFalse(c.get("production_ready"))
            r = export_ldap_field_trial_report()
            self.assertTrue(r.get("success"))
            self.assertTrue(r.get("md_path"))
            self.assertTrue(r.get("json_path"))


if __name__ == "__main__":
    unittest.main()
