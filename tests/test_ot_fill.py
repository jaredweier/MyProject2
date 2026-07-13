import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers import get_any_officer, test_database, working_date_for_squad


class OtFillTests(unittest.TestCase):
    def setUp(self):
        self._db_cm = test_database()
        self._db_cm.__enter__()

    def tearDown(self):
        self._db_cm.__exit__(None, None, None)

    def test_fill_mode_save_and_candidates(self):
        from logic.ot_fill import (
            FILL_MODE_SENIORITY_ONLY,
            get_ot_fill_mode,
            list_ot_fill_candidates,
            set_ot_fill_mode,
        )

        r = set_ot_fill_mode(FILL_MODE_SENIORITY_ONLY)
        self.assertTrue(r.get("success"), r)
        self.assertEqual(get_ot_fill_mode(), FILL_MODE_SENIORITY_ONLY)

        off = get_any_officer(squad="A", shift_start="06:00")
        day = working_date_for_squad("A")
        cand = list_ot_fill_candidates(
            off["id"],
            day.isoformat(),
            "A",
            off.get("shift_start") or "06:00",
            mode=FILL_MODE_SENIORITY_ONLY,
        )
        self.assertTrue(cand.get("success"), cand)
        self.assertGreater(cand.get("count", 0), 0)
        ranks = [c["seniority_rank"] for c in cand["candidates"][:5]]
        self.assertEqual(ranks, sorted(ranks), "seniority_only should sort senior-first (low rank first)")

    def test_ordered_in_moves_to_end_of_call_list(self):
        from logic.bump_off_duty import get_bump_call_list, import_bump_call_list_text, reset_call_list_cursor
        from logic.officers import get_officers_by_seniority
        from logic.ot_fill import record_ordered_in

        officers = [o for o in get_officers_by_seniority() if o.get("active") == 1][:3]
        self.assertGreaterEqual(len(officers), 3)
        import_bump_call_list_text("\n".join(str(o["id"]) for o in officers))
        reset_call_list_cursor()
        first_id = officers[0]["id"]
        self.assertEqual(get_bump_call_list()[0]["officer_id"], first_id)

        rec = record_ordered_in(first_id, "2026-07-15", hours=8.0)
        self.assertTrue(rec.get("success"), rec)
        cl = get_bump_call_list()
        self.assertEqual(cl[-1]["officer_id"], first_id, "ordered officer must be furthest (end)")
        self.assertNotEqual(cl[0]["officer_id"], first_id)

    def test_turned_down_year_stats(self):
        from logic.ot_fill import get_officer_ot_fill_year_stats, record_turned_down

        off = get_any_officer(squad="A")
        r = record_turned_down(off["id"], "2026-03-01", notes="test decline")
        self.assertTrue(r.get("success"), r)
        r2 = record_turned_down(off["id"], "2026-04-01")
        self.assertTrue(r2.get("success"), r2)
        stats = get_officer_ot_fill_year_stats(off["id"], 2026)
        self.assertGreaterEqual(stats.get("turned_down", 0), 2)

    def test_yearly_caps_block_order_and_candidates(self):
        from logic.officers import get_officer_by_id, get_officers_by_seniority, update_officer
        from logic.ot_fill import (
            get_officer_ot_fill_year_stats,
            list_ot_fill_candidates,
            record_ordered_in,
        )
        from logic.roster_titles import resolve_officer_callin_limits
        from logic.scheduling import officer_base_rotation_working
        from validators import officer_uses_command_staff_schedule

        day = working_date_for_squad("A")
        squad_a = [o for o in get_officers_by_seniority() if o.get("active") == 1 and o.get("squad") == "A"]
        working = [
            o for o in squad_a if officer_base_rotation_working(o, day) and not officer_uses_command_staff_schedule(o)
        ]
        self.assertGreaterEqual(len(working), 2)
        cover, orig = working[0], working[1]
        update_officer(cover["id"], max_ordered_in_year=1, max_turn_downs_year=None)
        lim = resolve_officer_callin_limits(get_officer_by_id(cover["id"]))
        self.assertEqual(lim.get("max_ordered_in_year"), 1)
        self.assertTrue(record_ordered_in(cover["id"], day.isoformat(), hours=8).get("success"))
        blocked = record_ordered_in(cover["id"], day.isoformat(), hours=8)
        self.assertFalse(blocked.get("success"), blocked)
        cand = list_ot_fill_candidates(orig["id"], day.isoformat(), "A", orig.get("shift_start") or "06:00")
        row = next(c for c in cand["candidates"] if c["officer_id"] == cover["id"])
        self.assertTrue(row.get("ineligible_for_order"), row)
        self.assertGreaterEqual(get_officer_ot_fill_year_stats(cover["id"], day.year).get("ordered_in"), 1)

    def test_apply_ot_fill_selection_approve(self):
        import logic
        from logic.officers import get_officers_by_seniority
        from logic.ot_fill import apply_ot_fill_selection, get_officer_ot_fill_year_stats
        from logic.scheduling import officer_base_rotation_working

        day = working_date_for_squad("A")
        day_s = day.isoformat()
        squad_a = [o for o in get_officers_by_seniority() if o.get("active") == 1 and o.get("squad") == "A"]
        working = [o for o in squad_a if officer_base_rotation_working(o, day)]
        self.assertGreaterEqual(len(working), 2)
        orig, cover = working[0], working[1]
        cr = logic.create_day_off_request(orig["id"], day_s, "Vacation", "ot_fill_test")
        self.assertTrue(cr.get("success"), cr)
        rid = cr["request_id"]
        result = apply_ot_fill_selection(
            rid,
            cover["id"],
            response="ordered_in",
            is_partial=False,
            turned_down_ids=[],
        )
        self.assertTrue(result.get("success") or result.get("requires_manual"), result)
        stats = get_officer_ot_fill_year_stats(cover["id"], day.year)
        self.assertGreaterEqual(stats.get("ordered_in", 0), 1)


if __name__ == "__main__":
    unittest.main()
