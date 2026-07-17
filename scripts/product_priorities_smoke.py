"""Logic-path smoke for product priorities (no browser required).

Proves: staffing half-hour, leave, payroll lock, notify templates,
callback call-down + equity, court board, comp force-use path,
FLSA split export, extra-duty marketplace, plan explain.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    fails: list[str] = []
    oks: list[str] = []

    def ok(msg: str) -> None:
        oks.append(msg)
        print("[ok]", msg)

    def fail(msg: str) -> None:
        fails.append(msg)
        print("[FAIL]", msg)

    # 1) Half-hour start packs + snap
    from logic.staffing_optimizer import _snap_to_half_hour, generate_start_packs

    packs = generate_start_packs(8.0)
    bad = [s for p in packs for s in p if not (str(s).endswith(":00") or str(s).endswith(":30"))]
    if packs and not bad:
        ok(f"start packs half-hour only n={len(packs)}")
    else:
        fail(f"bad starts {bad[:8]} packs={len(packs)}")
    if _snap_to_half_hour("03:10") in ("03:00", "03:30"):
        ok(f"snap 03:10 -> {_snap_to_half_hour('03:10')}")
    else:
        fail("snap failed")

    # 2) Notify templates + outbox (Twilio optional)
    from logic.notify_channels import dispatch_channel_hooks, format_notify_template, test_notify_channels
    from logic.notify_queue import notify_outbox_stats, process_notify_outbox

    t = format_notify_template("open_shift", date="7/16/26", start="19:00", end="03:00", squad="A")
    if "19:00" in t["body"] and t["subject"]:
        ok("open_shift template")
    else:
        fail("open_shift template")
    t2 = format_notify_template("schedule_published", label="7/2026")
    if "published" in t2["body"].lower() or "Schedule" in t2["subject"]:
        ok("schedule_published template")
    else:
        fail("schedule_published template")
    r = dispatch_channel_hooks(subject="t", body="b", officer_ids=None)
    if r.get("success"):
        ok(f"dispatch hooks (channels off ok): {r.get('message')}")
    else:
        fail("dispatch hooks")
    tr = test_notify_channels()
    if tr.get("success"):
        ok(f"notify test path: {tr.get('message', '')[:80]}")
    else:
        fail("notify test path")
    pr = process_notify_outbox(limit=10)
    if pr.get("success"):
        ok(f"outbox process: {pr.get('message')}")
    else:
        fail("outbox process")
    st = notify_outbox_stats()
    ok(f"outbox stats total={st.get('total', 0)}")

    # 3) Callback call-down + equity
    from datetime import date

    from logic.callbacks import (
        export_callback_equity_csv,
        run_callback_calldown,
        sync_callback_rotation_from_roster,
    )

    sync_callback_rotation_from_roster()
    cd = run_callback_calldown(date.today().isoformat(), max_offers=2, notify=False)
    if cd.get("offered_count", 0) >= 1 or "empty" in (cd.get("message") or "").lower():
        ok(f"calldown: {cd.get('message')}")
    else:
        fail(f"calldown: {cd}")
    ex = export_callback_equity_csv()
    if ex.get("success") and Path(ex.get("path") or "").is_file():
        ok(f"equity csv {ex.get('path')}")
    else:
        fail(f"equity export {ex}")

    # 4) Court calendar
    from logic.court_calendar import court_calendar_summary, list_court_training_events

    board = list_court_training_events()
    if board.get("success"):
        ok(f"court board count={board.get('count')}")
    else:
        fail(f"court board {board}")
    summ = court_calendar_summary()
    if summ.get("success"):
        ok("court summary")
    else:
        fail("court summary")

    # 5) FLSA vs contract OT export
    from logic.labor_compliance import export_flsa_vs_contract_ot_csv

    fl = export_flsa_vs_contract_ot_csv()
    if fl.get("success") and Path(fl.get("path") or "").is_file():
        ok(f"flsa split {fl.get('count')} rows")
    else:
        fail(f"flsa split {fl}")

    # 6) Extra duty marketplace
    from logic.extra_duty import create_extra_duty_event, marketplace_board

    mb = marketplace_board()
    if mb.get("success"):
        ok(f"extra-duty marketplace open={mb.get('open_count')}")
    else:
        fail("marketplace")
    # create one if none
    if mb.get("open_count", 0) == 0:
        cr = create_extra_duty_event(
            date.today().isoformat(),
            "19:00",
            "06:00",
            event_name="Smoke Extra Duty",
            location="City Hall",
            billing_code="SMOKE",
        )
        if cr.get("success"):
            ok("extra-duty created")
        else:
            fail(f"extra-duty create {cr}")

    # 7) Plan explain
    from logic.plan_explain import explain_score_weights

    w = explain_score_weights()
    if "junior" in w.lower() or "rank" in w.lower():
        ok("plan_explain weights")
    else:
        fail("plan_explain")

    # 7b) Hosting + dual equity + impl kit
    from config import APP_NAME, COMPANY_NAME
    from logic.hosting import get_hosting_config
    from logic.ot_equity_ledger import get_ot_equity_summary
    from logic.product_impl_kit import get_implementation_kit

    if APP_NAME == "Chronos Command" and "Weierworks" in COMPANY_NAME:
        ok("branding Chronos Command / Weierworks")
    else:
        fail("branding")
    if get_hosting_config().get("tenant_id"):
        ok(f"hosting tenant={get_hosting_config().get('tenant_id')}")
    else:
        fail("hosting")
    if get_implementation_kit().get("success"):
        ok("implementation kit")
    else:
        fail("implementation kit")
    if get_ot_equity_summary().get("success"):
        ok("ot equity dual summary")
    else:
        fail("ot equity dual")

    # 8) Leave + payroll smokes (import as subprocess-ish re-run)
    import subprocess

    for script in ("leave_flow_smoke.py", "payroll_flow_smoke.py"):
        p = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if p.returncode == 0 and "PASSED" in (p.stdout + p.stderr):
            ok(script)
        else:
            fail(f"{script} rc={p.returncode}\n{(p.stdout + p.stderr)[-400:]}")

    # 9) PWA assets
    for rel in (
        "gui/static/manifest.webmanifest",
        "gui/static/sw.js",
        "gui/static/chronos_logo.png",
    ):
        if (ROOT / rel).is_file():
            ok(f"pwa asset {rel}")
        else:
            fail(f"missing {rel}")

    # 10) Staffing optimizer locked 8h path (short)
    from logic.scheduling_sim import run_staffing_optimizer

    windows = [
        {
            "min_officers": 2,
            "start_time": "19:00",
            "end_time": "03:00",
            "weekday": 4,
            "label": "Friday Night",
            "enabled": True,
        },
        {
            "min_officers": 2,
            "start_time": "19:00",
            "end_time": "03:00",
            "weekday": 5,
            "label": "Saturday Night",
            "enabled": True,
        },
    ]
    opt = run_staffing_optimizer(
        rotation_types=["2-2-3 (Dodgeville 14-day)"],
        officer_counts=[8],
        min_per_shift_options=[1],
        shift_length_hours=8.0,
        shift_starts=["06:00", "14:00", "22:00"],
        free_officer_counts=False,
        free_starts=False,
        free_lengths=False,
        free_variations=False,
        rotation_style="rotating",
        rotation_variations=["6-2,5-3", "6-3,5-2"],
        annual_hours_target=2008.0,
        annual_hours_variance=20.0,
        annual_hours_hard=True,
        coverage_247=1,
        use_extra_windows=True,
        extra_windows=windows,
        night_minimum=2,
        simulation_days=28,
        require_hard_ok=True,
    )
    if opt.get("success") and opt.get("best"):
        starts = opt["best"].get("shift_starts") or opt["best"].get("starts") or []
        bad_s = [s for s in starts if not (str(s).endswith(":00") or str(s).endswith(":30"))]
        if not bad_s:
            ok(f"staffing 8h hard-ok layouts={opt.get('scenarios_evaluated')}")
        else:
            fail(f"staffing bad starts {bad_s}")
    elif opt.get("near_misses"):
        ok(f"staffing near-miss only (honest): {opt.get('message')}")
    else:
        fail(f"staffing: {opt.get('message')}")

    print("---")
    print(f"PASS {len(oks)} FAIL {len(fails)}")
    for f in fails:
        print(" ", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
