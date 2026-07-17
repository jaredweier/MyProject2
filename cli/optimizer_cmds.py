"""CLI — staffing optimizer (headless Find Best / min-N / compare)."""

from __future__ import annotations

import json

from logic.optimizer_features import (
    export_ranked_options_csv,
    export_search_audit_json,
    get_real_world_8h_preset,
)
from logic.scheduling_sim import (
    compare_shift_length_scenarios,
    find_min_officers_hard,
    run_staffing_optimizer,
)


def optimize_find_best_cmd(args):
    p = get_real_world_8h_preset()
    n = int(getattr(args, "officers", 0) or 0)
    result = run_staffing_optimizer(
        rotation_types=[p["rotation_type"]],
        officer_counts=[n] if n else p["officer_counts"],
        min_per_shift_options=[int(p["min_per_shift"])],
        shift_length_hours=float(getattr(args, "length", None) or p["shift_length_hours"]),
        shift_starts=list(p["shift_starts"]),
        annual_hours_target=float(p["annual_hours_target"]),
        annual_hours_variance=float(p["annual_hours_variance"]),
        annual_hours_hard=True,
        coverage_247=int(p["coverage_247"]),
        use_extra_windows=True,
        extra_windows=list(p["extra_windows"]),
        require_hard_ok=not bool(getattr(args, "soft", False)),
        rotation_style="rotating",
        rotation_variations=list(p["rotation_variations"]),
        free_officer_counts=n <= 0,
        free_starts=bool(getattr(args, "free_starts", False)),
    )
    print(result.get("message") or ("OK" if result.get("success") else "FAILED"))
    print(
        f"evaluated={result.get('scenarios_evaluated')} "
        f"full_sims={result.get('full_sims_run')} "
        f"kept={result.get('scenarios_kept')} "
        f"ms={result.get('wall_time_ms')}"
    )
    best = result.get("best") or {}
    if best:
        print(
            f"best: N={best.get('num_officers')} starts={best.get('shift_starts')} "
            f"hard={best.get('hard_constraints_ok')}"
        )
    if getattr(args, "export_csv", False) and result.get("ranked"):
        r = export_ranked_options_csv(result["ranked"])
        print(f"csv={r.get('path')}")
    if getattr(args, "export_audit", False):
        r = export_search_audit_json(result)
        print(f"audit={r.get('path')}")
    if getattr(args, "json", False):
        print(json.dumps({"success": result.get("success"), "best": best}, default=str))


def optimize_min_n_cmd(args):
    p = get_real_world_8h_preset()
    result = find_min_officers_hard(
        lo=int(getattr(args, "lo", 4) or 4),
        hi=int(getattr(args, "hi", 16) or 16),
        shift_length_hours=float(p["shift_length_hours"]),
        annual_hours_target=float(p["annual_hours_target"]),
        annual_hours_variance=float(p["annual_hours_variance"]),
        rotation_variations=list(p["rotation_variations"]),
        shift_starts=list(p["shift_starts"]),
        coverage_247=int(p["coverage_247"]),
        extra_windows=list(p["extra_windows"]),
    )
    print(result.get("message"))
    for t in result.get("trials") or []:
        print(f"  N={t.get('num_officers')}: {'OK' if t.get('success') else 'NO'}")


def optimize_compare_cmd(args):
    p = get_real_world_8h_preset()
    n = int(getattr(args, "officers", 8) or 8)
    result = compare_shift_length_scenarios(
        officer_count=n,
        annual_hours_target=float(p["annual_hours_target"]),
        annual_hours_variance=float(p["annual_hours_variance"]),
        rotation_variations=list(p["rotation_variations"]),
        coverage_247=int(p["coverage_247"]),
        extra_windows=list(p["extra_windows"]),
    )
    for line in result.get("table_lines") or []:
        print(line)
    print(result.get("message"))
