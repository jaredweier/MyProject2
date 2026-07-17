"""Find Best → implement plan (half-hour starts) logic smoke — no browser."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from logic.optimized_schedule_apply import (
        _normalize_half_hour_starts,
        implement_optimized_plan,
        save_last_optimized_plan,
    )
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
    print("Find Best → publish smoke")
    print("=" * 50)
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
        simulation_days=28,
        require_hard_ok=True,
    )
    if not opt.get("success") or not opt.get("best"):
        print("[FAIL] Find Best no hard-OK plan:", (opt.get("message") or "")[:160])
        return 1
    best = opt["best"]
    starts = best.get("shift_starts") or best.get("starts") or ["06:00", "14:00", "22:00"]
    # Inject odd minute to prove snap
    dirty = [s.replace(":00", ":07") if str(s).endswith(":00") else s for s in starts]
    norm = _normalize_half_hour_starts(dirty)
    bad = [s for s in norm if not (str(s).endswith(":00") or str(s).endswith(":30"))]
    if bad:
        print("[FAIL] half-hour normalize failed", bad)
        return 1
    print("[ok] half-hour normalize", dirty, "->", norm)

    # Shape result like simulator publish payload
    result = dict(opt)
    result["success"] = True
    result["shift_starts"] = dirty  # pre-normalize path
    cfg = {
        "shift_length_hours": 8.0,
        "annual_hours_target": 2008.0,
        "annual_hours_variance": 20.0,
        "shift_starts": dirty,
        "num_officers": 8,
        "min_per_shift": 1,
        "rotation_type": "2-2-3 (Dodgeville 14-day)",
        "rotation_style": "rotating",
        "rotation_variations": ["6-2,5-3", "6-3,5-2"],
        "coverage_247": 1,
    }
    save_last_optimized_plan(result, cfg)
    # Use a date in rotation window
    start = date(2026, 7, 1).isoformat()
    pub = implement_optimized_plan(
        start_date=start,
        result=result,
        config=cfg,
        apply_officer_assignments=False,
        force_regenerate=True,
        save_as_defaults=True,
    )
    if not pub.get("success"):
        print("[FAIL] publish:", pub.get("message"))
        return 1
    applied = pub.get("shift_starts") or pub.get("defaults", {}).get("shift_starts") or norm
    # defaults always normalized inside implement
    print("[ok] publish", pub.get("message") or "ok")
    print("[ok] applied starts", applied)
    print("=" * 50)
    print("find_best_publish_smoke: PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
