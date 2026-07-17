"""Simulator product pack — explain, sensitivity, fairness, import live constraints, apply winner."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from logic.operations import get_department_setting, set_department_setting
from logic.users import log_audit_action


def plain_english_staffing_explain(result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Full plain-language explain for simulator result."""
    from logic.optimizer_features import fairness_report, near_miss_deltas, why_best_lines
    from logic.plan_explain import explain_ranked_option, explain_staffing_result

    r = result or {}
    lines = list(explain_staffing_result(r) or [])
    best = r.get("best") or {}
    if best:
        lines.append("")
        lines.append("Best option detail:")
        lines.extend(explain_ranked_option(best) or [])
    try:
        lines.extend(why_best_lines(r) or [])
    except Exception:
        pass
    try:
        nm = near_miss_deltas(r) or []
        if nm:
            lines.append("")
            lines.append("Near misses:")
            lines.extend(str(x) for x in nm[:12])
    except Exception:
        pass
    try:
        fair = fairness_report(r) or []
        if fair:
            lines.append("")
            lines.append("Fairness:")
            lines.extend(str(x) for x in fair[:12])
    except Exception:
        pass

    # Explicit constraint failures in plain English
    failed = best.get("failed_constraints") or (r.get("metrics") or {}).get("failed_constraints") or []
    if failed:
        lines.append("")
        lines.append("What failed hard constraints:")
        for f in failed:
            if f in ("coverage_247", "gaps"):
                lines.append("  · Not enough officers on every hour (24/7 or min-per-shift)")
            elif f == "windows":
                lines.append("  · Extra window short (e.g. Fri/Sat night 19:00–03:00)")
            elif f == "annual":
                lines.append("  · Annual hours outside target band")
            elif f == "flsa":
                lines.append("  · FLSA OT pressure above preferred limit")
            else:
                lines.append(f"  · {f}")

    return {
        "success": True,
        "lines": lines,
        "text": "\n".join(lines),
        "message": lines[0] if lines else "No explain available",
    }


def _cheap_sensitivity_kwargs(base: Dict[str, Any], **overrides) -> Dict[str, Any]:
    """Clamp search for sensitivity — never full exhaustive by default."""
    kw = {k: v for k, v in dict(base or {}).items() if not str(k).startswith("_")}
    kw.update(overrides)
    # Hard caps for residual fix: sensitivity must stay interactive
    kw.setdefault("max_full_sims", 24)
    kw.setdefault("max_layouts", 80)
    kw.setdefault("time_budget_ms", 4000)
    kw.setdefault("simulation_days", min(int(kw.get("simulation_days") or 14), 14))
    kw["depth"] = kw.get("depth") or "shallow"
    kw["parallel"] = False
    return kw


def _headcount_from_result(res: Optional[Dict[str, Any]], n: int) -> Dict[str, Any]:
    res = res if isinstance(res, dict) else {}
    best = res.get("best") or {}
    hard = best.get("hard_constraints_ok")
    if hard is None:
        hard = (res.get("metrics") or {}).get("hard_constraints_ok")
    return {
        "success": bool(res.get("success")),
        "hard_ok": hard,
        "message": res.get("message") or "",
        "summary": (best.get("summary") or res.get("message") or "")[:200],
        "num_officers": n,
    }


def sensitivity_headcount(
    base_kwargs: Optional[Dict[str, Any]] = None,
    *,
    deltas: Optional[List[int]] = None,
    deep: bool = False,
) -> Dict[str, Any]:
    """What-if: +1 / +2 officers. Default = cheap (search-space + cached/shallow).

    deep=True runs limited optimizer; still time-capped.
    """
    from logic.scheduling_sim import estimate_staffing_search_space, what_if_staffing_delta

    deltas = deltas or [0, 1, 2]
    base = dict(base_kwargs or {})
    n0 = int(base.get("num_officers") or base.get("officer_count") or 8)
    rows = []
    mode = "deep" if deep else "cheap"

    for d in deltas:
        n = n0 + int(d)
        row: Dict[str, Any] = {
            "delta_officers": d,
            "num_officers": n,
            "mode": mode,
        }
        try:
            if d == 0 and base.get("_cached_result"):
                meta = _headcount_from_result(base.get("_cached_result"), n)
                row.update(meta)
                row["source"] = "cached_result"
            elif not deep:
                # Cheap: estimate search space + use cached hard_ok as baseline only
                est = estimate_staffing_search_space(
                    **_cheap_sensitivity_kwargs(base, num_officers=n, officer_counts=[n])
                )
                layouts = est.get("layouts") or est.get("estimated_layouts") or est.get("total") or "?"
                row.update(
                    {
                        "success": True,
                        "hard_ok": None,  # unknown without deep run
                        "message": f"Search space estimate ~{layouts} layouts (cheap mode)",
                        "summary": f"N={n}: ~{layouts} layouts · run deep sensitivity for hard OK",
                        "estimate": est,
                        "source": "estimate_only",
                    }
                )
                # If base cache hard-failed and Δ=0, surface that
                if d == 0 and base.get("_cached_result"):
                    meta = _headcount_from_result(base.get("_cached_result"), n)
                    row["hard_ok"] = meta.get("hard_ok")
                    row["summary"] = meta.get("summary") or row["summary"]
                    row["source"] = "cached+estimate"
            else:
                kw = _cheap_sensitivity_kwargs(base, num_officers=n, officer_counts=[n])
                try:
                    res = what_if_staffing_delta(base, num_officers=n, **{k: v for k, v in kw.items() if k not in base})
                except TypeError:
                    res = what_if_staffing_delta(base, num_officers=n)
                meta = _headcount_from_result(res, n)
                row.update(meta)
                row["source"] = "what_if_shallow"
        except Exception as exc:
            row.update({"success": False, "hard_ok": False, "message": str(exc), "summary": str(exc)[:200]})
        rows.append(row)

    lines = [f"Sensitivity — headcount ({mode})", ""]
    for row in rows:
        if row.get("hard_ok") is True:
            mark = "OK"
        elif row.get("hard_ok") is False:
            mark = "FAIL"
        else:
            mark = "EST"
        lines.append(
            f"  N={row['num_officers']} (Δ{row['delta_officers']:+d}): {mark} — "
            f"{row.get('summary') or row.get('message')}"
        )
    if not deep:
        lines.append("")
        lines.append("Cheap mode: no full beam search. Pass deep=True or use Find Best for hard proof.")

    return {
        "success": True,
        "mode": mode,
        "rows": rows,
        "text": "\n".join(lines),
        "message": f"{len(rows)} headcount scenarios ({mode})",
    }


def sensitivity_relax_night_min(
    base_kwargs: Optional[Dict[str, Any]] = None,
    *,
    deep: bool = False,
) -> Dict[str, Any]:
    """Cost of relaxing Fri/Sat night min 2 → 1. Default cheap (window rewrite only)."""
    base = dict(base_kwargs or {})
    variants = []
    mode = "deep" if deep else "cheap"

    for night_min in (2, 1):
        kw = dict(base)
        windows = list(kw.get("extra_windows") or [])
        new_windows = []
        for w in windows:
            if not isinstance(w, dict):
                continue
            ww = dict(w)
            if int(ww.get("min_officers") or 0) >= 2:
                ww["min_officers"] = night_min
            new_windows.append(ww)
        if new_windows:
            kw["extra_windows"] = new_windows
        entry: Dict[str, Any] = {"night_min": night_min, "mode": mode}
        if not deep:
            # Cheap: report constraint change only + optional cache compare at night_min=2
            entry.update(
                {
                    "success": True,
                    "hard_ok": None,
                    "message": f"Windows min_officers → {night_min} (cheap; no full search)",
                    "window_count": len(new_windows),
                }
            )
            if night_min == 2 and base.get("_cached_result"):
                meta = _headcount_from_result(base.get("_cached_result"), int(base.get("num_officers") or 0))
                entry["hard_ok"] = meta.get("hard_ok")
                entry["message"] = meta.get("summary") or entry["message"]
        else:
            try:
                from logic.scheduling_sim import optimize_staffing_scenarios

                res = optimize_staffing_scenarios(**_cheap_sensitivity_kwargs(kw))
                best = (res or {}).get("best") or {}
                entry.update(
                    {
                        "success": bool((res or {}).get("success")),
                        "hard_ok": best.get("hard_constraints_ok"),
                        "message": (res or {}).get("message") or "",
                        "num_officers": best.get("num_officers")
                        or ((res or {}).get("metrics") or {}).get("min_officers_required"),
                    }
                )
            except Exception as exc:
                entry.update({"success": False, "hard_ok": False, "message": str(exc)})
        variants.append(entry)

    lines = [f"Sensitivity — night minimum ({mode})", ""]
    for v in variants:
        if v.get("hard_ok") is True:
            mark = "OK"
        elif v.get("hard_ok") is False:
            mark = "FAIL"
        else:
            mark = "EST"
        lines.append(f"  Night min={v['night_min']}: {mark} — {v.get('message')}")
    if not deep:
        lines.append("")
        lines.append("Cheap mode: constraint rewrite only. deep=True runs shallow search (time-capped).")
    return {"success": True, "mode": mode, "variants": variants, "text": "\n".join(lines)}


def import_live_department_constraints() -> Dict[str, Any]:
    """Load current dept staffing + coverage windows into a simulator form snapshot (no invent)."""
    from logic.optimizer_features import save_form_snapshot

    try:
        from logic.staffing_config import get_staffing_settings

        staff = get_staffing_settings() or {}
    except Exception:
        staff = {}

    try:
        from logic.coverage_windows_store import get_active_coverage_windows, get_coverage_247_minimum

        windows = get_active_coverage_windows() or []
        cov247 = get_coverage_247_minimum()
    except Exception:
        windows = []
        cov247 = 1

    form: Dict[str, Any] = {
        "source": "live_department",
        "shift_length_hours": float(staff.get("shift_length_hours") or 8),
        "annual_hours_target": float(staff.get("annual_hours_target") or 2008),
        "annual_hours_variance": float(staff.get("annual_hours_variance") or 20),
        "num_officers": int(staff.get("target_officer_count") or staff.get("num_officers") or 0),
        "shift_starts": staff.get("shift_starts") or [],
        "min_per_shift": int(staff.get("min_per_shift") or 1),
        "coverage_247": int(cov247 or 0),
        "use_extra_windows": bool(windows),
        "extra_windows": windows,
        "rotation_variations": [],
    }
    # Rotation variations from settings if present
    raw = get_department_setting("rotation_variations_json", "") or ""
    if raw.strip():
        try:
            form["rotation_variations"] = json.loads(raw)
        except json.JSONDecodeError:
            pass
    style = get_department_setting("rotation_style", "") or ""
    if style:
        form["rotation_style"] = style

    # If still empty officers, leave 0 (UI should not invent)
    save_form_snapshot(form)
    set_department_setting("last_simulator_constraints_json", json.dumps(form))
    return {
        "success": True,
        "form": form,
        "message": "Loaded live department constraints into simulator snapshot (no invented defaults)",
    }


def apply_sim_winner_to_draft_month(
    *,
    start_date: str,
    result: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
    force_regenerate: bool = True,
) -> Dict[str, Any]:
    """Apply best sim plan as department defaults + monthly base draft."""
    from logic.optimized_schedule_apply import (
        get_last_optimized_plan,
        implement_optimized_plan,
        preview_implement_plan,
        save_last_optimized_plan,
    )

    if result is None or config is None:
        last = get_last_optimized_plan()
        if last:
            result = result or last.get("result")
            config = config or last.get("config")
    if not result:
        return {"success": False, "message": "No simulator winner to apply — run search first"}

    # Normalize: staffing optimizer returns {success, best, ...}
    plan = dict(result)
    if plan.get("best") and not plan.get("officer_slots"):
        best = plan["best"]
        if isinstance(best, dict):
            plan.setdefault("officer_slots", best.get("officer_slots") or [])
            plan.setdefault("metrics", best.get("metrics") or plan.get("metrics") or {})
            plan.setdefault("shift_starts", best.get("shift_starts"))
            if best.get("success") is not None:
                plan["success"] = bool(best.get("success") or plan.get("success"))
    if not plan.get("success") and plan.get("best"):
        plan["success"] = True

    cfg = dict(config or plan.get("simulation_config") or {})
    save_last_optimized_plan(plan, cfg, user_id=user_id)
    preview = preview_implement_plan(start_date=start_date, result=plan, config=cfg)
    applied = implement_optimized_plan(
        start_date=start_date,
        result=plan,
        config=cfg,
        user_id=user_id,
        force_regenerate=force_regenerate,
        save_as_defaults=True,
    )
    applied["preview"] = preview
    if applied.get("success") and user_id is not None:
        log_audit_action(
            user_id,
            "sim_apply_draft_month",
            "schedule_snapshots",
            None,
            f"Applied sim winner from {start_date}",
        )
    return applied


def fairness_report_full(result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    from logic.optimizer_features import fairness_report, fairness_report_with_roster

    r = result or {}
    lines = []
    try:
        lines.extend(fairness_report(r) or [])
    except Exception:
        pass
    try:
        lines.extend(fairness_report_with_roster(r) or [])
    except Exception:
        pass
    return {
        "success": True,
        "lines": lines,
        "text": "\n".join(lines) if lines else "No fairness metrics on this result",
        "message": f"{len(lines)} fairness line(s)",
    }


def try_cpsat_when_small(
    constraints: Optional[Dict[str, Any]] = None,
    *,
    max_officers: int = 12,
) -> Dict[str, Any]:
    """Prefer CP-SAT exact search when N is small and ortools available."""
    c = dict(constraints or {})
    n = int(c.get("num_officers") or c.get("officer_count") or 0)
    counts = c.get("officer_counts") or []
    if not n and counts:
        try:
            n = max(int(x) for x in counts)
        except Exception:
            n = 0
    if n <= 0 or n > max_officers:
        return {
            "success": False,
            "skipped": True,
            "message": f"CP-SAT path only for 1–{max_officers} officers (N={n or 'unknown'})",
        }
    try:
        from logic.cp_sat_bridge import solve_staffing_cpsat

        res = solve_staffing_cpsat(**{k: v for k, v in c.items() if not str(k).startswith("_")})
        if isinstance(res, dict):
            res.setdefault("engine", "cp_sat")
            return res
        return {"success": bool(res), "engine": "cp_sat", "result": res}
    except ImportError:
        return {"success": False, "skipped": True, "message": "ortools / cp_sat_bridge not available"}
    except Exception as exc:
        # Fall back note — caller may run beam search
        return {"success": False, "message": str(exc), "engine": "cp_sat"}
