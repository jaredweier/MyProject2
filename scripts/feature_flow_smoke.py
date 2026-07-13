"""
Safe feature flow smoke — same logic paths as Chronos UI buttons.

NO NiceGUI server, NO browser, NO screenshots (crash-avoidance).

Covers: off-duty bump policy, call list (+ docx), replacements scoring,
day-off approve, coverage windows, implement optimized plan, officer pattern.

Run:
  python scripts/feature_flow_smoke.py
  python -m unittest tests.test_feature_flow_smoke -v
"""

from __future__ import annotations

import os
import sys
import zipfile
from datetime import timedelta
from io import BytesIO
from typing import List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _ok(msg: str) -> None:
    print(f"  [ok] {msg}")


def _fail(fails: List[str], msg: str) -> None:
    print(f"  [FAIL] {msg}")
    fails.append(msg)


def _make_minimal_docx(lines: List[str]) -> bytes:
    """Build a tiny valid docx in memory (stdlib)."""
    body_parts = []
    for line in lines:
        body_parts.append(f'<w:p><w:r><w:t xml:space="preserve">{line}</w:t></w:r></w:p>')
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{''.join(body_parts)}</w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)
    return buf.getvalue()


def run_feature_flow_smoke() -> int:
    print("Feature flow smoke (logic = Chronos UI paths; no GUI process)")
    print("=" * 56)
    fails: List[str] = []
    notes: List[str] = []

    from tests.helpers import get_any_officer, test_database, working_date_for_squad

    with test_database(seed=True):
        import logic
        from logic.bump_off_duty import (
            ALL_CRITERIA,
            CRITERION_CALL_LIST,
            CRITERION_DAYS_OFF,
            CRITERION_SENIORITY,
            advance_call_list_cursor,
            call_list_rank_score,
            extract_text_from_upload,
            get_bump_call_list,
            get_call_list_cursor,
            get_next_call_list_officer,
            import_bump_call_list_file,
            import_bump_call_list_text,
            load_off_duty_bump_policy,
            reset_call_list_cursor,
            save_off_duty_bump_policy,
        )
        from logic.coverage_optimizer import list_scored_replacements
        from logic.coverage_windows_store import (
            add_coverage_window,
            get_coverage_247_minimum,
            set_coverage_247_minimum,
        )
        from logic.officers import get_officer_by_id, get_officers_by_seniority, update_officer
        from logic.optimized_schedule_apply import (
            format_optimized_plan_view,
            get_schedule_builder_defaults,
            implement_optimized_plan,
        )
        from logic.rotation_config import get_active_rotation_base_date
        from logic.scheduling import officer_base_rotation_working
        from logic.scheduling_sim import run_schedule_simulation
        from logic.snapshots import get_schedule_snapshot

        # --- 1. Policy multi-criteria ---
        r = save_off_duty_bump_policy(
            {
                "allow_off_duty": True,
                "criteria": [CRITERION_SENIORITY, CRITERION_CALL_LIST, CRITERION_DAYS_OFF],
                "min_days_off_required": 0,
                "prefer_on_duty_first": True,
                "same_squad_only": True,
            }
        )
        if not r.get("success"):
            _fail(fails, f"save policy: {r.get('message')}")
        else:
            p = load_off_duty_bump_policy()
            if not p.allow_off_duty or CRITERION_CALL_LIST not in p.criteria:
                _fail(fails, "policy reload missing flags/criteria")
            else:
                _ok(f"off-duty policy save/load criteria={p.criteria}")

        # --- 2. Call list + rank + cursor ---
        officers = [o for o in get_officers_by_seniority() if o.get("active") == 1][:4]
        if len(officers) < 2:
            _fail(fails, "need ≥2 officers for call list")
        else:
            ids_text = "\n".join(str(o["id"]) for o in officers)
            ir = import_bump_call_list_text(ids_text)
            if not ir.get("success") or len(get_bump_call_list()) < 2:
                _fail(fails, f"call list import: {ir}")
            else:
                reset_call_list_cursor()
                p = load_off_duty_bump_policy()
                s0 = call_list_rank_score(officers[0]["id"], p)
                s1 = call_list_rank_score(officers[1]["id"], p)
                if s0 <= s1:
                    _fail(fails, f"call list rank: next-up should score higher ({s0} vs {s1})")
                else:
                    _ok("call list import + next-up ranks highest")
                c0 = get_call_list_cursor()
                advance_call_list_cursor()
                if get_call_list_cursor() == c0 and len(get_bump_call_list()) > 1:
                    _fail(fails, "cursor did not advance")
                else:
                    _ok(f"cursor advanced → {get_call_list_cursor()}")
                nxt = get_next_call_list_officer()
                if not nxt:
                    _fail(fails, "next call list officer missing")
                else:
                    _ok(f"next-up officer id={nxt.get('officer_id')}")

        # --- 3–4. Off-duty in replacements ---
        squad_a = [o for o in get_officers_by_seniority() if o.get("active") == 1 and o.get("squad") == "A"]
        base = get_active_rotation_base_date()
        target = None
        orig = None
        for i in range(14):
            d = base + timedelta(days=i)
            working = [o for o in squad_a if officer_base_rotation_working(o, d)]
            off = [o for o in squad_a if not officer_base_rotation_working(o, d)]
            if working and off:
                target, orig = d, working[0]
                break
        if not target or not orig:
            notes.append("skip off-duty scoring: no mixed on/off day for squad A")
        else:
            ctx = {}
            for o in squad_a:
                on = officer_base_rotation_working(o, target)
                ctx[o["id"]] = {
                    "status": "working" if on else "off",
                    "shift_start": o.get("shift_start") or "06:00",
                    "shift_end": o.get("shift_end") or "17:00",
                }
            save_off_duty_bump_policy(
                {
                    "allow_off_duty": True,
                    "criteria": [CRITERION_SENIORITY],
                    "require_adjacent_band": False,
                    "prefer_on_duty_first": True,
                    "same_squad_only": True,
                }
            )
            ranked = list_scored_replacements(
                orig["id"],
                target.isoformat(),
                "A",
                orig.get("shift_start") or "06:00",
                ctx,
                limit=25,
            )
            if not ranked:
                notes.append("no scored replacements (band/rest filters) — not a hard fail")
            else:
                on_scores = [s for s, o in ranked if o.get("_bump_on_duty", True)]
                off_scores = [s for s, o in ranked if not o.get("_bump_on_duty", True)]
                if on_scores and off_scores:
                    if min(on_scores) < max(off_scores):
                        _fail(
                            fails,
                            f"prefer_on_duty_first: on min {min(on_scores)} < off max {max(off_scores)}",
                        )
                    else:
                        _ok("prefer_on_duty_first: on-duty ranks above off-duty")
                else:
                    _ok(f"replacements n={len(ranked)} off_duty_count={len(off_scores)}")

            save_off_duty_bump_policy({"allow_off_duty": False})
            ranked_off = list_scored_replacements(
                orig["id"],
                target.isoformat(),
                "A",
                orig.get("shift_start") or "06:00",
                ctx,
                limit=25,
            )
            if any(not o.get("_bump_on_duty", True) for _, o in ranked_off):
                _fail(fails, "off-duty still in list when disabled")
            else:
                _ok("off-duty excluded when policy off")

        # --- 5. Day-off approve (same path as Leave UI) ---
        officer = get_any_officer(squad="A", shift_start="06:00")
        day = working_date_for_squad("A")
        day_s = day.isoformat() if hasattr(day, "isoformat") else str(day)
        save_off_duty_bump_policy(
            {
                "allow_off_duty": True,
                "criteria": [CRITERION_SENIORITY, CRITERION_CALL_LIST],
                "prefer_on_duty_first": True,
            }
        )
        cr = logic.create_day_off_request(officer["id"], day_s, "Vacation", "feature_flow_smoke")
        if not cr.get("success"):
            _fail(fails, f"create day-off: {cr.get('message')}")
        else:
            pr = logic.process_day_off_request(cr["request_id"], action="approve")
            if getattr(pr, "success", False) or getattr(pr, "requires_manual", False):
                _ok(
                    f"day-off approve path: success={getattr(pr, 'success', None)} manual={getattr(pr, 'requires_manual', None)}"
                )
            else:
                _fail(fails, f"day-off approve: {getattr(pr, 'message', pr)}")

        # --- 6. Coverage 24/7 setting (light) ---
        set_coverage_247_minimum(1)
        if get_coverage_247_minimum() != 1:
            _fail(fails, "coverage_247 not persisted")
        else:
            _ok("coverage 24/7 minimum set")
        wr = add_coverage_window(
            min_officers=2,
            start_time="19:00",
            end_time="03:00",
            weekday=4,
            label="smoke Fri night",
        )
        if not wr.get("success"):
            _fail(fails, f"add coverage window: {wr}")
        else:
            _ok("coverage window added")
        set_coverage_247_minimum(0)  # restore light default for later tests

        # --- 7. Implement optimized plan ---
        sim = run_schedule_simulation(
            rotation_type="2-2-3 (Dodgeville 14-day)",
            num_officers=10,
            shift_length_hours=11.0,
            annual_hours_target=2080,
            shift_starts=["06:00", "14:00", "22:00"],
            apply_department_rules=False,
            min_per_shift=1,
            simulation_days=14,
            auto_min_officers=False,
        )
        if not sim.get("success"):
            _fail(fails, f"simulation: {sim.get('message')}")
        else:
            view = format_optimized_plan_view(sim, sim.get("simulation_config"))
            if not view.get("success"):
                _fail(fails, "format plan view failed")
            else:
                _ok("format optimized plan view")
            cfg = {
                "rotation_type": "2-2-3 (Dodgeville 14-day)",
                "num_officers": 10,
                "shift_length_hours": 11.0,
                "annual_hours_target": 2080,
                "shift_starts": ["06:00", "14:00", "22:00"],
                "min_per_shift": 1,
            }
            impl = implement_optimized_plan(
                start_date="2026-10-01",
                result=sim,
                config=cfg,
                apply_officer_assignments=False,
                force_regenerate=True,
                save_as_defaults=True,
            )
            if not impl.get("success"):
                _fail(fails, f"implement plan: {impl.get('message')}")
            else:
                defaults = get_schedule_builder_defaults()
                base = get_schedule_snapshot(2026, 10, "base")
                live = get_schedule_snapshot(2026, 10, "updated")
                if not defaults.get("source") == "optimized_plan":
                    _fail(fails, "builder defaults not saved from optimized plan")
                elif not base or not live:
                    _fail(fails, "base/live missing after implement")
                else:
                    _ok("implement optimized plan → base+live+defaults")

        # --- 8. Officer pattern ---
        o = get_any_officer(squad="A")
        ur = update_officer(o["id"], rotation_pattern="5-2", rotation_phase=0)
        if not ur.get("success"):
            _fail(fails, f"update pattern: {ur.get('message')}")
        else:
            ref = get_officer_by_id(o["id"])
            b = get_active_rotation_base_date()
            if not officer_base_rotation_working(ref, b):
                _fail(fails, "pattern 5-2 day1 should work")
            elif officer_base_rotation_working(ref, b + timedelta(days=5)):
                _fail(fails, "pattern 5-2 day6 should be off")
            else:
                _ok("officer rotation_pattern duty bits")
            update_officer(o["id"], rotation_pattern="", rotation_phase=0)

        # --- 9. docx extract + import ---
        sample_ids = [str(o["id"]) for o in officers[:3]] if officers else []
        if sample_ids:
            docx_bytes = _make_minimal_docx(sample_ids)
            text = extract_text_from_upload("call_list.docx", docx_bytes)
            if not any(sid in text for sid in sample_ids):
                _fail(fails, f"docx extract missed ids: {text!r}")
            else:
                fr = import_bump_call_list_file("call_list.docx", docx_bytes)
                if not fr.get("success"):
                    _fail(fails, f"docx import: {fr.get('message')}")
                else:
                    _ok("docx call list extract+import")
            # txt path
            tr = import_bump_call_list_file("x.txt", "\n".join(sample_ids).encode("utf-8"))
            if not tr.get("success"):
                _fail(fails, f"txt file import: {tr}")
            else:
                _ok("txt call list file import")
            # pdf optional
            try:
                import pypdf  # noqa: F401

                notes.append("pypdf installed — PDF path available in UI; no PDF fixture in smoke")
            except ImportError:
                notes.append("pypdf not installed — PDF upload returns clear error (by design)")

        # ALL_CRITERIA non-empty for UI static pairing
        if len(ALL_CRITERIA) < 5:
            _fail(fails, "ALL_CRITERIA unexpectedly small")
        else:
            _ok(f"criteria count={len(ALL_CRITERIA)}")

    print("-" * 56)
    if notes:
        print("Notes / improvements:")
        for n in notes:
            print(f"  · {n}")
        print("  · Prefer logic smokes over browser E2E on this machine (crash history).")
        print("  · Optional: pip install pypdf for PDF call-list import.")
    if fails:
        print(f"FAILED ({len(fails)}):")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("feature_flow_smoke: ALL PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(run_feature_flow_smoke())
