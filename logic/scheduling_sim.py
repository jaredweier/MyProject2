"""**Optimizer brain** — schedule simulation and coverage-plan preview.

Prefer importing from this module (or ``logic.coverage_optimizer`` for bumps).
``logic.scheduling`` re-exports remain for back-compat only.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from validators import parse_date

# --- Deterministic-job cache (master plan §4) --------------------------------
# In-process only (not durable across restarts/processes) — chosen over a
# SQLite-backed cache because `optimize_staffing_scenarios` results embed
# nested plain dict/list rows plus a `SimulationReport` dataclass
# (`simulation_report`); round-tripping that through JSON/pickle safely is a
# larger, separately-scoped effort. An in-process dict is smaller and safer
# for this slice — worst case on a miss is a cold re-solve, never a stale or
# malformed result. Keyed by a sha256 of the canonicalized deterministic
# inputs (sorted keys, `default=str` for any odd non-JSON value so hashing
# never raises). progress_callback/cancel_check are callables, not part of
# a job's deterministic identity, so they're excluded from the key.
_OPT_CACHE: Dict[str, Dict] = {}


def _optimizer_cache_key(inputs: Dict[str, Any]) -> str:
    payload = json.dumps(inputs, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def clear_optimizer_cache() -> None:
    """Test/debug hook — drop all cached optimizer results."""
    _OPT_CACHE.clear()


def run_schedule_simulation(
    rotation_type: str,
    num_officers: int,
    shift_length_hours: float,
    annual_hours_target: float,
    shift_starts: List[str],
    apply_department_rules: bool = False,
    min_per_shift: int = 1,
    simulation_days: int = 28,
    night_minimum: int | None = None,
    *,
    annual_hours_variance: float = 40.0,
    annual_hours_hard: bool = False,
    coverage_247: int = 0,
    avoid_flsa_overtime: bool = False,
    flsa_work_period_days: int = 28,
    rotation_style: str = "",
    rotation_variations: Optional[List[str]] = None,
    stagger_phases: bool = True,
    auto_min_officers: bool = True,
    use_extra_windows: bool = False,
    extra_windows: Optional[List[Dict]] = None,
    phase_overrides: Optional[List[int]] = None,
    pattern_slot_map: Optional[List[int]] = None,
    officer_home_starts: Optional[List[str]] = None,
    officer_cycle_starts: Optional[List[List[str]]] = None,
    flexible_daily_starts: bool = False,
    nearby_start_hops: int = 1,
    allow_offday_coverage: bool = False,
    min_rest_hours: float = 0.0,
    max_consecutive_work_days: int = 0,
) -> Dict:
    from config import NIGHT_MINIMUM_OFFICERS
    from simulator import SimulatorConfig, simulate_schedule

    config = SimulatorConfig(
        rotation_type=rotation_type,
        num_officers=num_officers if num_officers is not None else 0,
        shift_length_hours=shift_length_hours,
        annual_hours_target=annual_hours_target,
        shift_starts=shift_starts,
        apply_department_rules=apply_department_rules,
        min_per_shift=min_per_shift,
        simulation_days=simulation_days,
        night_minimum=night_minimum if night_minimum is not None else NIGHT_MINIMUM_OFFICERS,
        annual_hours_variance=annual_hours_variance,
        annual_hours_hard=annual_hours_hard,
        coverage_247=coverage_247,
        avoid_flsa_overtime=avoid_flsa_overtime,
        flsa_work_period_days=flsa_work_period_days,
        rotation_style=rotation_style,
        rotation_variations=list(rotation_variations or []),
        stagger_phases=stagger_phases,
        auto_min_officers=auto_min_officers,
        use_extra_windows=bool(use_extra_windows),
        extra_windows=list(extra_windows or []),
        phase_overrides=list(phase_overrides) if phase_overrides is not None else None,
        pattern_slot_map=list(pattern_slot_map) if pattern_slot_map is not None else None,
        officer_home_starts=list(officer_home_starts) if officer_home_starts is not None else None,
        officer_cycle_starts=(
            [list(days) for days in officer_cycle_starts] if officer_cycle_starts is not None else None
        ),
        flexible_daily_starts=bool(flexible_daily_starts),
        nearby_start_hops=int(nearby_start_hops),
        allow_offday_coverage=bool(allow_offday_coverage),
        min_rest_hours=float(min_rest_hours or 0),
        max_consecutive_work_days=int(max_consecutive_work_days or 0),
    )
    result = simulate_schedule(config)
    if not result.success:
        return {"success": False, "message": result.message or "Simulation failed"}
    coverage = result.coverage_by_day
    start_label = coverage[0]["date"] if coverage else None
    return {
        "success": True,
        "message": result.message or "Simulation complete",
        "compute_backend": result.compute_backend,
        "metrics": result.metrics,
        "officer_slots": [slot.__dict__ for slot in result.officer_slots],
        "coverage_by_day": coverage,
        "assignments": list(result.assignments or []),
        "suggestions": [
            {"severity": s.severity, "title": s.title, "message": s.message, "recommendation": s.recommendation}
            for s in result.suggestions
        ],
        "shift_templates": result.shift_templates,
        "simulation_start_date": start_label,
        "simulation_config": {
            "rotation_type": rotation_type,
            "num_officers": num_officers,
            "shift_length_hours": shift_length_hours,
            "annual_hours_target": annual_hours_target,
            "shift_starts": shift_starts,
            "apply_department_rules": apply_department_rules,
            "min_per_shift": min_per_shift,
            "simulation_days": simulation_days,
            "coverage_247": coverage_247,
            "avoid_flsa_overtime": avoid_flsa_overtime,
            "use_extra_windows": use_extra_windows,
            "extra_windows": list(extra_windows or []),
        },
    }


def run_staffing_optimizer(
    *,
    rotation_types: Optional[List[str]] = None,
    officer_counts: Optional[List[int]] = None,
    min_per_shift_options: Optional[List[int]] = None,
    shift_length_hours: Optional[float] = None,
    annual_hours_target: Optional[float] = None,
    shift_starts: Optional[List[str]] = None,
    simulation_days: int = 28,
    coverage_247: int = 0,
    avoid_flsa_overtime: bool = False,
    flsa_work_period_days: int = 28,
    annual_hours_variance: float = 40.0,
    annual_hours_hard: bool = False,
    use_extra_windows: bool = False,
    extra_windows: Optional[List[Dict]] = None,
    night_minimum: Optional[int] = None,
    require_hard_ok: bool = True,
    rotation_style: str = "",
    rotation_variations: Optional[List[str]] = None,
    rotation_variation_sets: Optional[List[List[str]]] = None,
    stagger_phases: bool = True,
    shift_starts_options: Optional[List[List[str]]] = None,
    shift_length_options: Optional[List[float]] = None,
    sim_start_date: Optional[str] = None,
    free_officer_counts: bool = False,
    free_starts: bool = False,
    free_lengths: bool = False,
    free_variations: bool = False,
    constraint_weights: Optional[Dict] = None,
    constraint_priority: Optional[List[str]] = None,
    nearby_start_hops: int = 1,
    allow_offday_coverage: bool = False,
    min_rest_hours: float = 0.0,
    max_consecutive_work_days: int = 0,
    max_start_variation_hours: Optional[float] = None,
    prefer_unique_daily_starts: bool = False,
    input_roles: Optional[Dict] = None,
    warm_start: Optional[Dict] = None,
    required_cert_codes: Optional[List[str]] = None,
    progress_callback=None,
    cancel_check=None,
    time_budget_seconds=None,
    **_compat,
) -> Dict:
    """Find best staffing plan via exhaustive constraint-space search (not bump logic).

    Identical deterministic inputs (everything below except progress_callback/
    cancel_check) hit an in-process cache and skip re-solving — see
    `_OPT_CACHE` / `_optimizer_cache_key` above. A cached job is only reused
    if the original run was `search_exhaustive` (proved complete, not stopped
    early by `time_budget_seconds` or cancellation) — a time-limited search's
    "best so far" isn't a reproducible answer for the same config, so those
    results are solved fresh every time rather than cached and silently
    replayed as if they were definitive (master plan §4 honesty rule, same
    spirit as `BumpChainSuggestion.search_complete`).
    """
    from logic.staffing_optimizer import optimize_staffing_scenarios

    call_kwargs = dict(
        rotation_types=rotation_types,
        officer_counts=officer_counts,
        min_per_shift_options=min_per_shift_options,
        shift_length_hours=shift_length_hours,
        annual_hours_target=annual_hours_target,
        shift_starts=shift_starts,
        simulation_days=simulation_days,
        coverage_247=coverage_247,
        avoid_flsa_overtime=avoid_flsa_overtime,
        flsa_work_period_days=flsa_work_period_days,
        annual_hours_variance=annual_hours_variance,
        annual_hours_hard=annual_hours_hard,
        use_extra_windows=use_extra_windows,
        extra_windows=extra_windows,
        night_minimum=night_minimum,
        require_hard_ok=require_hard_ok,
        rotation_style=rotation_style,
        rotation_variations=rotation_variations,
        rotation_variation_sets=rotation_variation_sets,
        stagger_phases=stagger_phases,
        shift_starts_options=shift_starts_options,
        shift_length_options=shift_length_options,
        sim_start_date=sim_start_date,
        free_officer_counts=free_officer_counts,
        free_starts=free_starts,
        free_lengths=free_lengths,
        free_variations=free_variations,
        constraint_weights=constraint_weights,
        constraint_priority=constraint_priority,
        nearby_start_hops=int(nearby_start_hops),
        allow_offday_coverage=bool(allow_offday_coverage),
        min_rest_hours=float(min_rest_hours or 0.0),
        max_consecutive_work_days=int(max_consecutive_work_days or 0),
        max_start_variation_hours=(float(max_start_variation_hours) if max_start_variation_hours is not None else None),
        prefer_unique_daily_starts=bool(prefer_unique_daily_starts),
        input_roles=input_roles,
        warm_start=warm_start,
        required_cert_codes=list(required_cert_codes or []),
        time_budget_seconds=time_budget_seconds,
    )

    cache_key = _optimizer_cache_key(call_kwargs)
    cached = _OPT_CACHE.get(cache_key)
    if cached is not None:
        return cached

    result = optimize_staffing_scenarios(
        **call_kwargs,
        progress_callback=progress_callback,
        cancel_check=cancel_check,
    )
    if result.get("search_exhaustive"):
        _OPT_CACHE[cache_key] = result
    return result


def estimate_staffing_search_space(**kwargs) -> Dict:
    """UI pre-flight: how many layouts / expected time for current free/locked dims."""
    from logic.staffing_optimizer import estimate_search_space

    return estimate_search_space(**kwargs)


# --- Process isolation for the coverage search (P0.4) -----------------------
# The enumeration in optimize_staffing_scenarios is pure-Python CPU work. Run
# on a thread it holds the GIL and starves NiceGUI's event loop — measured
# live 2026-07-22: a plain page load took 84s during a search vs 7ms after.
# So UI-launched searches run in a child process; the parent thread only
# blocks on IPC waits (which release the GIL).

_OPT_POOL = None
_OPT_MANAGER = None


def _optimizer_process_entry(kw: Dict, progress_q, cancel_ev) -> Dict:
    """Child-process entry. Throttles IPC: cancel polls are a proxy roundtrip,
    and the engine checks per layout — unthrottled that would dominate runtime."""
    import time as _t

    _st = {"prog_t": 0.0, "cancel_t": 0.0, "cancel_v": False}

    def _progress(info: Dict) -> None:
        now = _t.monotonic()
        if (info or {}).get("phase") == "done" or now - _st["prog_t"] >= 0.4:
            _st["prog_t"] = now
            try:
                progress_q.put_nowait(dict(info))
            except Exception:
                pass

    def _cancel() -> bool:
        now = _t.monotonic()
        if not _st["cancel_v"] and now - _st["cancel_t"] >= 0.25:
            _st["cancel_t"] = now
            try:
                _st["cancel_v"] = bool(cancel_ev.is_set())
            except Exception:
                pass
        return _st["cancel_v"]

    return run_staffing_optimizer(progress_callback=_progress, cancel_check=_cancel, **kw)


def run_staffing_optimizer_isolated(
    kw: Dict,
    *,
    progress_callback=None,
    cancel_check=None,
) -> Dict:
    """Blocking wrapper: run the search in a child process, relaying progress
    and cancellation. Call from a worker thread, never the event loop.

    Falls back to the in-process path if the pool can't start or breaks —
    slower UI but never a lost search.
    """
    import multiprocessing
    import queue as _queue
    from concurrent.futures import ProcessPoolExecutor
    from concurrent.futures import TimeoutError as _FutTimeout

    global _OPT_POOL, _OPT_MANAGER
    try:
        if _OPT_POOL is None:
            ctx = multiprocessing.get_context("spawn")
            _OPT_POOL = ProcessPoolExecutor(max_workers=1, mp_context=ctx)
            _OPT_MANAGER = ctx.Manager()
        prog_q = _OPT_MANAGER.Queue()
        cancel_ev = _OPT_MANAGER.Event()
        fut = _OPT_POOL.submit(_optimizer_process_entry, dict(kw), prog_q, cancel_ev)
    except Exception:
        _shutdown_opt_pool()
        return run_staffing_optimizer(progress_callback=progress_callback, cancel_check=cancel_check, **kw)

    def _drain() -> None:
        while True:
            try:
                info = prog_q.get_nowait()
            except _queue.Empty:
                return
            except Exception:
                return
            if progress_callback is not None:
                try:
                    progress_callback(info)
                except Exception:
                    pass

    try:
        while True:
            if cancel_check is not None and not cancel_ev.is_set():
                try:
                    if cancel_check():
                        cancel_ev.set()
                except Exception:
                    pass
            _drain()
            try:
                result = fut.result(timeout=0.3)
                _drain()
                return result
            except _FutTimeout:
                continue
    except Exception:
        # BrokenProcessPool or pickling issue — rebuild lazily next time and
        # fall back in-process so the user still gets an answer.
        _shutdown_opt_pool()
        return run_staffing_optimizer(progress_callback=progress_callback, cancel_check=cancel_check, **kw)


def _shutdown_opt_pool() -> None:
    global _OPT_POOL, _OPT_MANAGER
    try:
        if _OPT_POOL is not None:
            _OPT_POOL.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass
    try:
        if _OPT_MANAGER is not None:
            _OPT_MANAGER.shutdown()
    except Exception:
        pass
    _OPT_POOL = None
    _OPT_MANAGER = None


def find_min_officers_hard(**kwargs) -> Dict:
    """Binary-search minimum headcount for hard constraints."""
    from logic.optimizer_features import find_min_officers_hard as _fn

    return _fn(**kwargs)


def what_if_staffing_delta(base_kwargs: Dict, **kwargs) -> Dict:
    """Re-run with one delta (officers / windows / length)."""
    from logic.optimizer_features import what_if_delta

    return what_if_delta(base_kwargs, **kwargs)


def compare_shift_length_scenarios(
    *,
    lengths: Optional[List[float]] = None,
    officer_count: int = 8,
    annual_hours_target: float = 2008.0,
    annual_hours_variance: float = 20.0,
    rotation_variations: Optional[List[str]] = None,
    coverage_247: int = 1,
    extra_windows: Optional[List[Dict]] = None,
    night_minimum: Optional[int] = 2,
    simulation_days: int = 28,
    require_hard_ok: bool = True,
    progress_callback=None,
    cancel_check=None,
    parallel: bool = True,
    depth: str = "deep",
) -> Dict:
    """Compare locked shift lengths (default 8/10/12h) under same coverage constraints.

    Differentiator vs commercial auto-fill: wellness + coverage trade-off table.
    Lengths run in parallel by default (shared cancel_check) to cut wall time.

    depth:
      - "quick": 21-day sim, top LE packs + full multi-block vars (quality-first speed)
      - "deep": 28-day + full start pack set (default exhaustive)
    """
    import time as _time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    lengths = list(lengths or [8.0, 10.0, 12.0])
    rotation_variations = list(rotation_variations or ["6-2,5-3", "6-3,5-2"])
    quick = str(depth or "deep").strip().lower() in ("quick", "fast", "cheap")
    # Quick no longer strips quality: still multi-block + evening packs; shorter window only
    if quick:
        simulation_days = min(int(simulation_days or 28), 21)
    else:
        simulation_days = max(int(simulation_days or 28), 28)
    if extra_windows is None:
        # Fri+Sat 19:00–03:00 min 2 — same keys as Chronos simulator UI
        extra_windows = [
            {
                "min_officers": int(night_minimum or 2),
                "start_time": "19:00",
                "end_time": "03:00",
                "weekday": 4,
                "label": "Friday Night",
                "enabled": True,
            },
            {
                "min_officers": int(night_minimum or 2),
                "start_time": "19:00",
                "end_time": "03:00",
                "weekday": 5,
                "label": "Saturday Night",
                "enabled": True,
            },
        ]

    n_len = len(lengths)
    t0 = _time.perf_counter()

    def _one_length(idx: int, length: float) -> Dict:
        if cancel_check and cancel_check():
            return {
                "shift_length_hours": float(length),
                "success": False,
                "cancelled": True,
                "message": "Compare cancelled",
            }

        def _progress_wrap(info, _i=idx, _L=length):
            if progress_callback is None:
                return
            payload = dict(info) if isinstance(info, dict) else {"message": str(info)}
            payload["compare_index"] = _i
            payload["compare_length"] = float(_L)
            payload["compare_total"] = n_len
            msg = payload.get("message") or ""
            payload["message"] = f"Compare {_L:g}h ({_i + 1}/{n_len}) · {msg}"
            try:
                progress_callback(payload)
            except Exception:
                pass

        # Prefer LE evening pack first when length is 8h-class (hard night windows)
        starts = (
            ["06:00", "14:00", "19:00", "22:00"]
            if float(length) <= 9.0
            else (["06:00", "18:00"] if float(length) >= 11.5 else ["06:00", "14:00", "22:00"])
        )
        if float(length) <= 9.0:
            # Quality packs always (evening first) — residual 6 closed: quick keeps these
            start_opts = [
                ["06:00", "14:00", "19:00", "22:00"],
                ["06:00", "14:00", "22:00"],
            ]
            if not quick:
                start_opts.append(["07:00", "15:00", "19:00", "23:00"])
        elif float(length) >= 11.5:
            start_opts = [["06:00", "18:00"], ["07:00", "19:00"]]
            if not quick:
                start_opts.append(["06:00", "14:00", "22:00"])
        else:
            start_opts = [starts]
            if not quick:
                start_opts.append(["07:00", "15:00", "23:00"])
        vars_use = list(rotation_variations)  # full multi-block set for quick + deep

        result = run_staffing_optimizer(
            rotation_types=["2-2-3 (14-day)"],
            officer_counts=[int(officer_count)],
            min_per_shift_options=[1],
            shift_length_hours=float(length),
            shift_starts=starts,
            shift_starts_options=start_opts,
            free_lengths=False,
            free_officer_counts=False,
            free_starts=False,
            free_variations=False,
            rotation_style="rotating",
            rotation_variations=vars_use,
            annual_hours_target=float(annual_hours_target),
            annual_hours_variance=float(annual_hours_variance),
            annual_hours_hard=True,
            coverage_247=int(coverage_247),
            use_extra_windows=True,
            extra_windows=extra_windows,
            night_minimum=night_minimum,
            simulation_days=int(simulation_days),
            require_hard_ok=require_hard_ok,
            progress_callback=_progress_wrap if progress_callback else None,
            cancel_check=cancel_check,
        )
        best = result.get("best") or {}
        # Attach economics for memo / UI (same as Find Best ranked cards)
        try:
            from logic.staffing_insights import enrich_option_economics

            if best:
                best = enrich_option_economics(best)
        except Exception:
            pass
        hm = best.get("human_metrics") or {}
        m = best.get("metrics") or {}
        econ = best.get("economics") or {}
        return {
            "shift_length_hours": float(length),
            "success": bool(result.get("success") and best),
            "impossible": bool(result.get("impossible")),
            "cancelled": bool(result.get("cancelled")),
            "message": result.get("message"),
            "scenarios_evaluated": result.get("scenarios_evaluated"),
            "full_sims_run": result.get("full_sims_run"),
            "wall_time_ms": result.get("wall_time_ms"),
            "best_rank": best.get("rank"),
            "best_starts": best.get("shift_starts") or best.get("starts"),
            "best_variation": (
                best.get("rotation_variations") or best.get("rotation_variation") or best.get("variation")
            ),
            "annual_mean": (
                m.get("avg_annual_hours") or best.get("annual_hours_mean") or best.get("mean_annual_hours")
            ),
            "hard_ok": bool(best.get("hard_constraints_ok", result.get("success"))),
            "window_short": hm.get("extra_window_failures") or m.get("extra_window_failures"),
            "near_miss_count": len(result.get("near_misses") or []),
            "est_ot_hours": econ.get("est_ot_hours_total"),
            "est_ot_cost": econ.get("est_ot_cost_usd"),
            "flsa_period_pct": econ.get("flsa_period_pct"),
            "fairness_score": econ.get("fairness_score"),
            "economics": econ,
        }

    comparisons: List[Dict] = []
    use_parallel = bool(parallel) and n_len > 1
    if use_parallel:
        by_idx: Dict[int, Dict] = {}
        with ThreadPoolExecutor(max_workers=min(n_len, 3)) as pool:
            futs = {pool.submit(_one_length, idx, length): idx for idx, length in enumerate(lengths)}
            for fut in as_completed(futs):
                idx = futs[fut]
                try:
                    by_idx[idx] = fut.result()
                except Exception as exc:
                    by_idx[idx] = {
                        "shift_length_hours": float(lengths[idx]),
                        "success": False,
                        "message": f"Compare failed: {exc}",
                    }
        comparisons = [by_idx[i] for i in range(n_len) if i in by_idx]
    else:
        for idx, length in enumerate(lengths):
            if cancel_check and cancel_check():
                return {
                    "success": False,
                    "cancelled": True,
                    "message": "Compare cancelled",
                    "comparisons": comparisons,
                    "wall_time_ms": int((_time.perf_counter() - t0) * 1000),
                }
            comparisons.append(_one_length(idx, length))

    if cancel_check and cancel_check():
        return {
            "success": False,
            "cancelled": True,
            "message": "Compare cancelled",
            "comparisons": comparisons,
            "wall_time_ms": int((_time.perf_counter() - t0) * 1000),
            "parallel": use_parallel,
        }
    if any(c.get("cancelled") for c in comparisons):
        return {
            "success": False,
            "cancelled": True,
            "message": "Compare cancelled",
            "comparisons": comparisons,
            "wall_time_ms": int((_time.perf_counter() - t0) * 1000),
            "parallel": use_parallel,
        }

    viable = [c for c in comparisons if c.get("success")]
    from logic.optimizer_features import format_compare_table

    wall_ms = int((_time.perf_counter() - t0) * 1000)
    return {
        "success": True,
        "officer_count": int(officer_count),
        "annual_hours_target": float(annual_hours_target),
        "lengths": lengths,
        "comparisons": comparisons,
        "table_lines": format_compare_table(comparisons),
        "viable_count": len(viable),
        "wall_time_ms": wall_ms,
        "parallel": use_parallel,
        "depth": "quick" if quick else "deep",
        "message": (
            f"Compared {len(lengths)} length(s): {len(viable)} viable under hard constraints"
            f" · {wall_ms} ms" + (" · parallel" if use_parallel else "") + (" · quick" if quick else " · deep")
        ),
    }


def preview_best_coverage_plans(
    original_officer_id: int,
    request_date: str,
    squad: str,
    shift_start: str,
    *,
    max_plans: int = 5,
) -> Dict:
    """List ranked coverage plans for UI / supervisor review."""
    from logic.coverage_optimizer import load_coverage_policy, search_best_coverage_plans

    policy = load_coverage_policy()
    policy.max_plans = max_plans
    from logic.scheduling import get_generated_schedule_day_context

    ctx = get_generated_schedule_day_context(parse_date(request_date))
    plans = search_best_coverage_plans(
        original_officer_id,
        request_date,
        squad,
        shift_start,
        ctx,
        policy=policy,
    )
    # Plans already best-first from beam search. plan_score kept for tests/diagnostics only.
    return {
        "success": True,
        "count": len(plans),
        "plans": [
            {
                "success": p.success,
                "message": p.message,
                "rank": i,
                "plan_score": p.plan_score,  # internal ranking only
                "chain": p.chain,
                "score_components": getattr(p, "score_components", None) or [],
                "steps": [
                    {
                        "step": s.step_number,
                        "original": s.original_officer_name,
                        "replacement": s.replacement_officer_name,
                        "from_shift": s.replacement_shift,
                        "to_shift": s.original_shift,
                        "on_duty": s.replacement_on_duty,
                        "original_id": s.original_officer_id,
                        "replacement_id": s.replacement_officer_id,
                    }
                    for s in p.steps
                ],
                "requires_manual": p.requires_manual,
                "failure_reason": p.failure_reason,
            }
            for i, p in enumerate(plans, 1)
        ],
        "policy": {
            "min_per_shift": policy.min_per_shift,
            "min_by_band": dict(policy.min_by_band),
            "night_minimum": policy.night_minimum,
            "max_cascade_depth": policy.max_cascade_depth,
            "beam_width": policy.beam_width,
            "w_junior": policy.w_junior,
            "w_spare_capacity": policy.w_spare_capacity,
            "w_same_start": policy.w_same_start,
            "w_shallow_chain": policy.w_shallow_chain,
        },
    }


def get_simulator_defaults_from_roster() -> Dict:
    from simulator import config_from_current_roster

    cfg = config_from_current_roster()
    return {
        "success": True,
        "rotation_type": cfg.rotation_type,
        "num_officers": cfg.num_officers,
        "shift_length_hours": cfg.shift_length_hours,
        "annual_hours_target": cfg.annual_hours_target,
        "shift_starts": ", ".join(cfg.shift_starts),
        "apply_department_rules": cfg.apply_department_rules,
        "min_per_shift": cfg.min_per_shift,
    }
