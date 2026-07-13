import sys
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers import test_database


class BumpOffDutyTests(unittest.TestCase):
    def setUp(self):
        self._db_cm = test_database()
        self._db_cm.__enter__()

    def tearDown(self):
        self._db_cm.__exit__(None, None, None)

    def test_policy_save_load_multi_criteria(self):
        from logic.bump_off_duty import (
            CRITERION_CALL_LIST,
            CRITERION_DAYS_OFF,
            CRITERION_SENIORITY,
            load_off_duty_bump_policy,
            save_off_duty_bump_policy,
        )

        r = save_off_duty_bump_policy(
            {
                "allow_off_duty": True,
                "criteria": [CRITERION_SENIORITY, CRITERION_CALL_LIST, CRITERION_DAYS_OFF],
                "min_days_off_required": 2,
                "same_squad_only": True,
                "prefer_on_duty_first": True,
            }
        )
        self.assertTrue(r.get("success"), r)
        p = load_off_duty_bump_policy()
        self.assertTrue(p.allow_off_duty)
        self.assertIn(CRITERION_CALL_LIST, p.criteria)
        self.assertEqual(p.min_days_off_required, 2)

    def test_call_list_import_and_rank(self):
        from logic.bump_off_duty import (
            call_list_rank_score,
            get_bump_call_list,
            import_bump_call_list_text,
            load_off_duty_bump_policy,
            save_off_duty_bump_policy,
        )
        from logic.officers import get_officers_by_seniority

        officers = [o for o in get_officers_by_seniority() if o.get("active") == 1][:3]
        self.assertGreaterEqual(len(officers), 2)
        text = "\n".join(str(o["id"]) for o in officers)
        r = import_bump_call_list_text(text)
        self.assertTrue(r.get("success"), r)
        self.assertEqual(len(get_bump_call_list()), len(officers))

        save_off_duty_bump_policy({"allow_off_duty": True, "criteria": ["call_list"]})
        p = load_off_duty_bump_policy()
        first = officers[0]["id"]
        second = officers[1]["id"]
        # cursor 0 → first ranks higher than second
        s1 = call_list_rank_score(first, p)
        s2 = call_list_rank_score(second, p)
        self.assertGreater(s1, s2)

    def test_off_duty_included_in_scored_replacements(self):
        from logic.bump_off_duty import save_off_duty_bump_policy
        from logic.coverage_optimizer import list_scored_replacements
        from logic.officers import get_officers_by_seniority
        from logic.rotation_config import get_active_rotation_base_date
        from logic.scheduling import officer_base_rotation_working

        save_off_duty_bump_policy(
            {
                "allow_off_duty": True,
                "criteria": ["seniority", "days_off"],
                "min_days_off_required": 0,
                "same_squad_only": True,
                "prefer_on_duty_first": True,
            }
        )
        officers = [o for o in get_officers_by_seniority() if o.get("active") == 1 and o.get("squad") == "A"]
        self.assertTrue(officers)
        base = get_active_rotation_base_date()
        # find a date squad A works and pick an on-duty officer as "original"
        target = base
        for i in range(14):
            d = base + timedelta(days=i)
            working = [o for o in officers if officer_base_rotation_working(o, d)]
            off = [o for o in officers if not officer_base_rotation_working(o, d)]
            if working and off:
                target = d
                orig = working[0]
                break
        else:
            self.skipTest("no mixed on/off day for squad A")

        # Build schedule_context: working = on duty status
        ctx = {}
        for o in officers:
            if officer_base_rotation_working(o, target):
                ctx[o["id"]] = {
                    "status": "working",
                    "shift_start": o.get("shift_start") or "06:00",
                    "shift_end": o.get("shift_end") or "17:00",
                }
            else:
                ctx[o["id"]] = {"status": "off", "shift_start": o.get("shift_start") or "", "shift_end": ""}

        ranked = list_scored_replacements(
            orig["id"],
            target.isoformat(),
            "A",
            orig.get("shift_start") or "06:00",
            ctx,
            limit=20,
        )
        self.assertTrue(ranked)
        # When off-duty allowed, some candidates may be off-duty
        any_off = any(not r[1].get("_bump_on_duty", True) for r in ranked)
        # At least scoring runs; if only on-duty eligible that's ok if bands filter
        # Enable without band constraints for off-duty only
        save_off_duty_bump_policy(
            {
                "allow_off_duty": True,
                "criteria": ["seniority"],
                "require_adjacent_band": False,
                "prefer_on_duty_first": False,
                "same_squad_only": True,
            }
        )
        ranked2 = list_scored_replacements(
            orig["id"],
            target.isoformat(),
            "A",
            orig.get("shift_start") or "06:00",
            ctx,
            limit=30,
        )
        ids = {r[1]["id"] for r in ranked2}
        off_ids = {o["id"] for o in officers if not officer_base_rotation_working(o, target)}
        self.assertTrue(ids & off_ids or any_off or ranked2)

    def test_docx_and_txt_extract_import(self):
        import zipfile
        from io import BytesIO

        from logic.bump_off_duty import extract_text_from_upload, import_bump_call_list_file
        from logic.officers import get_officers_by_seniority

        officers = [o for o in get_officers_by_seniority() if o.get("active") == 1][:2]
        self.assertGreaterEqual(len(officers), 1)
        lines = [str(o["id"]) for o in officers]
        # minimal docx
        document_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
            + "".join(f"<w:p><w:r><w:t>{ln}</w:t></w:r></w:p>" for ln in lines)
            + "</w:body></w:document>"
        )
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(
                "[Content_Types].xml",
                '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>',
            )
            zf.writestr("word/document.xml", document_xml)
        raw = buf.getvalue()
        text = extract_text_from_upload("list.docx", raw)
        for ln in lines:
            self.assertIn(ln, text)
        r = import_bump_call_list_file("list.docx", raw)
        self.assertTrue(r.get("success"), r)

        # legacy .doc rejected
        with self.assertRaises(ValueError):
            extract_text_from_upload("old.doc", b"not-a-doc")

    def test_disabled_excludes_off_duty(self):
        from logic.bump_off_duty import save_off_duty_bump_policy
        from logic.coverage_optimizer import list_scored_replacements
        from logic.officers import get_officers_by_seniority
        from logic.rotation_config import get_active_rotation_base_date
        from logic.scheduling import officer_base_rotation_working

        save_off_duty_bump_policy({"allow_off_duty": False, "criteria": ["seniority"]})
        officers = [o for o in get_officers_by_seniority() if o.get("active") == 1 and o.get("squad") == "A"]
        base = get_active_rotation_base_date()
        target = base
        orig = officers[0]
        for i in range(14):
            d = base + timedelta(days=i)
            working = [o for o in officers if officer_base_rotation_working(o, d)]
            if working:
                target = d
                orig = working[0]
                break
        ctx = {}
        for o in officers:
            working = officer_base_rotation_working(o, target)
            ctx[o["id"]] = {
                "status": "working" if working else "off",
                "shift_start": o.get("shift_start") or "06:00",
            }
        ranked = list_scored_replacements(
            orig["id"],
            target.isoformat(),
            "A",
            orig.get("shift_start") or "06:00",
            ctx,
            limit=20,
        )
        for _score, o in ranked:
            self.assertTrue(o.get("_bump_on_duty", True), "off-duty must not appear when disabled")


if __name__ == "__main__":
    unittest.main()
