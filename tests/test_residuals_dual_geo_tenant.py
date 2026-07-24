"""Residuals: dual FLSA engine, geofence→timecard, multi-tenant paths."""

from __future__ import annotations

import os
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

from tests.helpers import test_database


class DualFlsaEngineTests(unittest.TestCase):
    def test_settings_key_sync(self):
        with test_database():
            from logic.dual_workforce import get_dual_workforce_settings, save_dual_workforce_settings
            from logic.labor_compliance import get_flsa_settings
            from logic.operations import get_department_setting

            r = save_dual_workforce_settings(
                dual_flsa_enabled=True,
                civilian_weekly_threshold=40,
                comp_cap_sworn=480,
                comp_cap_civilian=240,
            )
            self.assertTrue(r.get("success"))
            dw = get_dual_workforce_settings()
            self.assertTrue(dw.get("dual_flsa_enabled"))
            self.assertEqual(get_department_setting("flsa_dual_workforce"), "1")
            self.assertEqual(float(get_department_setting("flsa_comp_cap_sworn") or 0), 480.0)
            flsa = get_flsa_settings()
            self.assertTrue(flsa.get("dual_workforce"))

    def test_civilian_weekly_ot_split(self):
        with test_database():
            from logic.dual_workforce import (
                compute_officer_ot_split,
                run_dual_period_ot_ledger,
                save_dual_workforce_settings,
            )
            from logic.officers import get_officers_by_seniority, update_officer
            from logic.payroll import get_pay_period, save_timecard_entry

            save_dual_workforce_settings(dual_flsa_enabled=True, civilian_weekly_threshold=40)
            officers = get_officers_by_seniority()
            self.assertTrue(officers)
            oid = officers[0]["id"]
            update_officer(oid, workforce_class="civilian")
            ps, pe = get_pay_period(date(2026, 7, 16))
            # Seed ~48h in one week inside period
            d0 = max(ps, date(2026, 7, 13))  # Monday-ish window
            for i in range(6):
                day = d0 + timedelta(days=i)
                if day > pe:
                    break
                save_timecard_entry(oid, day.isoformat(), 8.0, notes="dual test", override_approval=True)
            split = compute_officer_ot_split(oid, period_start=ps, period_end=pe, reference=date(2026, 7, 16))
            self.assertTrue(split.get("success"))
            self.assertEqual(split.get("workforce_class"), "civilian")
            self.assertEqual(split.get("ot_basis"), "weekly_40")
            self.assertGreaterEqual(split.get("overtime_hours") or 0, 0)
            # 6*8=48 → OT at least 8 if all in one week
            if (split.get("total_hours") or 0) >= 48:
                self.assertGreaterEqual(split.get("overtime_hours") or 0, 7.9)
            led = run_dual_period_ot_ledger(reference=date(2026, 7, 16))
            self.assertTrue(led.get("success"))
            self.assertGreaterEqual(led.get("count") or 0, 1)

    def test_sworn_7k_profile(self):
        with test_database():
            from logic.dual_workforce import compute_officer_ot_split, flsa_profile_for_officer
            from logic.officers import get_officers_by_seniority

            o = get_officers_by_seniority()[0]
            prof = flsa_profile_for_officer(o)
            self.assertTrue(prof.get("uses_7k"))
            split = compute_officer_ot_split(int(o["id"]))
            self.assertTrue(split.get("success"))


class GeofenceTimecardTests(unittest.TestCase):
    def test_pair_and_apply(self):
        with test_database():
            from database import get_connection
            from logic.geofence_clock import (
                apply_geofence_punches_to_timecard,
                clock_status,
                pair_in_out_segments,
                record_geofence_punch,
            )
            from logic.officers import get_officers_by_seniority

            oid = get_officers_by_seniority()[0]["id"]
            # Fence off so coords not required
            r1 = record_geofence_punch(oid, "in", notes="t1")
            self.assertTrue(r1.get("success"))
            # Force out punch later via SQL for known duration
            r2 = record_geofence_punch(oid, "out", notes="t2")
            self.assertTrue(r2.get("success"))
            # Backdate timestamps for 8h span
            with get_connection() as conn:
                conn.execute(
                    "UPDATE geofence_punches SET created_at = ? WHERE id = ?",
                    ("2026-07-16 08:00:00", r1["id"]),
                )
                conn.execute(
                    "UPDATE geofence_punches SET created_at = ? WHERE id = ?",
                    ("2026-07-16 16:00:00", r2["id"]),
                )
                conn.commit()
            segs = pair_in_out_segments(
                [
                    {"id": r1["id"], "officer_id": oid, "punch_type": "in", "created_at": "2026-07-16 08:00:00"},
                    {"id": r2["id"], "officer_id": oid, "punch_type": "out", "created_at": "2026-07-16 16:00:00"},
                ]
            )
            self.assertEqual(len(segs), 1)
            self.assertAlmostEqual(segs[0]["hours"], 8.0, places=1)
            applied = apply_geofence_punches_to_timecard(oid)
            self.assertTrue(applied.get("success"))
            st = clock_status(oid)
            self.assertIn("clocked_in", st)


class TenantPathTests(unittest.TestCase):
    def test_create_tenant_and_info(self):
        from logic.tenant import create_tenant, get_tenant_info, list_local_tenants

        r = create_tenant("test-agency-residual", display_name="Test Agency")
        self.assertTrue(r.get("success"))
        self.assertTrue(Path(r["path"]).is_dir())
        tenants = list_local_tenants()
        ids = {t["tenant_id"] for t in tenants}
        self.assertIn("test-agency-residual", ids)
        info = get_tenant_info()
        self.assertIn("tenant_id", info)
        self.assertIn("db_path", info)

    def test_data_path_respects_tenant_env(self):
        import paths as paths_mod

        with mock.patch.dict(os.environ, {"SCHEDULER_TENANT_ID": "env-tenant-x"}):
            # re-read helper
            p = paths_mod.data_path("exports")
            self.assertIn("tenants", p.replace("\\", "/"))
            self.assertIn("env-tenant-x", p.replace("\\", "/"))

    def test_tenant_id_rejects_path_traversal(self):
        from logic.tenant import tenant_data_root

        root = tenant_data_root("../../../etc")
        resolved = str(root.resolve())
        self.assertNotIn("..", resolved)
        # slug strips traversal/separator chars; result stays under tenants/
        self.assertIn("tenants", resolved.replace("\\", "/"))

    def test_tenant_id_slug_strips_dangerous_characters(self):
        from logic.tenant import tenant_data_root

        root = tenant_data_root("../../windows/system32")
        parts = str(root).replace("\\", "/").split("/")
        self.assertIn("tenants", parts)
        # traversal/separators collapse into one safe slug segment, not nested escapes
        self.assertEqual(len(parts) - parts.index("tenants"), 2)
        self.assertNotIn("..", parts)


if __name__ == "__main__":
    unittest.main()
