"""Residuals 2–5: CAD bidirectional, offline API, walkthrough helpers, LDAP field trial."""

from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path

from tests.helpers import get_any_officer, test_database


class Residuals25Tests(unittest.TestCase):
    def test_cad_bidirectional_roundtrip(self):
        with test_database():
            from logic.cad_rms_bridge import (
                cad_bidirectional_roundtrip_smoke,
                receive_cad_inbound,
                save_cad_bridge_config,
            )

            save_cad_bridge_config(apply_on_import=False, inbound_token="trial-token")
            r = cad_bidirectional_roundtrip_smoke()
            self.assertTrue(r.get("success"), r)
            # Token gate
            bad = receive_cad_inbound({"rows": []}, token="wrong")
            self.assertFalse(bad.get("success"))
            good = receive_cad_inbound({"rows": [{"date": "2026-07-10", "officer_id": 1}]}, token="trial-token")
            self.assertTrue(good.get("success"), good)

    def test_cad_apply_cover_pair(self):
        with test_database():
            from logic.cad_rms_bridge import apply_cad_cover_rows
            from logic.officers import get_officers_by_seniority

            offs = [o for o in get_officers_by_seniority() if o.get("active") == 1][:2]
            if len(offs) < 2:
                self.skipTest("need 2 officers")
            # Use a far date to reduce collision
            rows = [
                {
                    "original_officer_id": int(offs[0]["id"]),
                    "replacement_officer_id": int(offs[1]["id"]),
                    "date": "2026-08-20",
                    "reason": "unit CAD apply",
                }
            ]
            r = apply_cad_cover_rows(rows)
            self.assertTrue(r.get("success"), r)
            # either applied or failed with existing coverage — path must run
            self.assertTrue(r.get("applied") is not None or r.get("failed") is not None)

    def test_offline_multi_page_snapshot(self):
        with test_database():
            from logic.offline_api import build_offline_snapshot, list_offline_precached_paths

            off = get_any_officer()
            snap = build_offline_snapshot(officer_id=int(off["id"]), reference=date(2026, 7, 10))
            self.assertTrue(snap.get("success"), snap)
            self.assertIn("pages", snap)
            self.assertIn("open_shifts", snap["pages"])
            self.assertIn("duty_today", snap["pages"])
            self.assertIn("ops_desk", snap["pages"])
            pol = snap["pages"].get("mutation_policy") or {}
            self.assertTrue(pol.get("mutations_apply"))
            self.assertEqual(pol.get("apply_path"), "/api/offline/mutations")
            paths = list_offline_precached_paths()
            self.assertIn("/api/offline/snapshot", paths)

    def test_offline_mutations_apply(self):
        with test_database():
            from logic import create_notification, get_notifications
            from logic.offline_api import apply_offline_mutations

            off = get_any_officer()
            oid = int(off["id"])
            create_notification(oid, "general", "Residual mut", "body")
            notes = get_notifications(officer_id=oid, unread_only=True, limit=3) or []
            self.assertTrue(notes, "need unread notification")
            nid = notes[0]["id"]
            r = apply_offline_mutations(
                [
                    {"id": "a", "action": "mark_notification_read", "payload": {"notification_id": nid}},
                    {"id": "b", "action": "approve_leave", "payload": {"request_id": 1}},
                ],
                officer_id=oid,
                user_id=1,
            )
            self.assertGreaterEqual(int(r.get("applied") or 0), 1)
            self.assertTrue(any(x.get("skipped") for x in r.get("results") or []))

    def test_cad_vendor_adapters(self):
        with test_database():
            from logic.cad_rms_bridge import import_cad_duty_bidirectional
            from logic.cad_vendors import detect_cad_vendor, normalize_cad_payload

            m43 = {
                "vendor": "mark43",
                "units": [{"dutyDate": "2026-08-01", "officerId": 1, "coveringOfficerId": 2, "status": "covered"}],
            }
            self.assertEqual(detect_cad_vendor(m43), "mark43")
            n = normalize_cad_payload(m43)
            self.assertGreaterEqual(len(n.get("rows") or []), 1)
            dry = import_cad_duty_bidirectional(m43, dry_run=True, source="unit_m43")
            self.assertTrue(dry.get("success"), dry)
            ty = {"UnitAssignments": [{"DutyDate": "2026-08-02", "AbsentEmployeeId": 1, "CoveringEmployeeId": 2}]}
            self.assertEqual(detect_cad_vendor(ty), "tyler")
            dry2 = import_cad_duty_bidirectional(ty, dry_run=True, source="unit_tyler")
            self.assertTrue(dry2.get("success"), dry2)

    def test_notify_file_sink_delivery(self):
        with test_database():
            from logic.notify_queue import enqueue_notify, list_notify_outbox, process_notify_outbox
            from logic.operations import set_department_setting

            set_department_setting("notify_email_enabled", "1")
            set_department_setting("notify_delivery_sink", "file")
            rid = enqueue_notify(
                channel="email",
                subject="sink test",
                body="hello",
                recipient="lab@example.test",
            )
            proc = process_notify_outbox(limit=10, dry_run=False)
            self.assertGreaterEqual(int(proc.get("sent") or 0), 1, proc)
            rows = [r for r in list_notify_outbox(limit=20) if r.get("id") == rid]
            self.assertTrue(rows)
            self.assertEqual(rows[0].get("status"), "sent")
            self.assertEqual(rows[0].get("provider_ref"), "file_sink")

    def test_ldap_field_trial_honest(self):
        with test_database():
            from logic.ldap_auth import (
                get_ldap_field_trial_config,
                ldap_auth_enabled,
                ldap_field_trial_checklist,
                ldap_health_check,
                save_ldap_field_trial_settings,
                try_ldap_authenticate,
            )

            # Default off
            self.assertFalse(ldap_auth_enabled())
            skipped = try_ldap_authenticate("x", "y")
            self.assertTrue(skipped.get("skipped") or not skipped.get("success"))

            r = save_ldap_field_trial_settings(
                {
                    "enabled": False,
                    "server": "ldap://lab.example.invalid",
                    "base_dn": "DC=example,DC=com",
                    "sandbox": True,
                }
            )
            self.assertTrue(r.get("success"), r)
            cfg = get_ldap_field_trial_config()
            self.assertEqual(cfg.get("server"), "ldap://lab.example.invalid")
            check = ldap_field_trial_checklist()
            self.assertTrue(check.get("success"))
            self.assertFalse(check.get("production_ready"))
            health = ldap_health_check()
            # unreachable invalid host is OK
            self.assertIn("message", health)

    def test_walkthrough_script_imports(self):
        # Ensure walkthrough module loads
        from scripts import product_walkthrough_smoke as pws

        self.assertTrue(callable(pws.main))

    def test_sw_v6_offline_api(self):
        root = Path(__file__).resolve().parents[1]
        sw = (root / "gui" / "static" / "sw.js").read_text(encoding="utf-8")
        self.assertIn("chronos-shell-v6", sw)
        self.assertIn("/api/offline/snapshot", sw)
        self.assertIn("/api/offline/mutations", sw)
        app = (root / "gui" / "app.py").read_text(encoding="utf-8")
        self.assertIn("/api/offline/snapshot", app)
        self.assertIn("/api/offline/mutations", app)
        self.assertIn("/api/cad/inbound", app)
        fonts = root / "gui" / "static" / "fonts.css"
        self.assertTrue(fonts.is_file())


if __name__ == "__main__":
    unittest.main()
