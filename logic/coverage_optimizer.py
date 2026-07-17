"""
**Optimizer brain** — coverage scoring, multi-plan bump search, staffing shim.

Works with any active staffing/rotation settings (shift count, lengths, starts,
night min, rest, consecutive caps). Explores multiple replacement chains and
returns the best complete plan under scored objectives:

  1. Complete coverage (success required)
  2. Prefer shorter cascades
  3. Prefer junior bumps (higher seniority_rank)
  4. Prefer officers with spare bump capacity
  5. Prefer covering from adjacent clock bands (already filtered by bump rules)

Rust `scheduler_core` remains the fast primary path when available; this module
powers the Python fallback and multi-plan "best option" APIs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import config
from models import BumpChainStep, BumpChainSuggestion
from validators import parse_date


@dataclass
class CoveragePolicy:
    """Department-agnostic knobs — filled from live settings + config defaults."""

    min_per_shift: int = 1
    # Per shift-start band minimums, e.g. {"06:00": 2, "19:00": 2}. Empty → use min_per_shift.
    min_by_band: Dict[str, int] = field(default_factory=dict)
    night_minimum: int = 2
    min_rest_hours: float = 8.0
    max_consecutive_work_days: int = 13
    max_cascade_depth: int = 8
    max_bump_assignments: int = 2
    beam_width: int = 6
    max_plans: int = 8
    # Scoring weights (higher = preferred)
    w_junior: float = 12.0
    w_shallow_chain: float = 25.0
    w_spare_capacity: float = 4.0
    w_same_start: float = 3.0
    # Timefold/CrewSense: prefer officers with lower recent OT (fairness)
    w_low_ot: float = 2.0
    # LE wellness: prefer lower fatigue score among otherwise equal candidates
    w_low_fatigue: float = 1.5
    # OR-Tools transition: prefer same band; soft hit for night→early
    w_transition_ok: float = 1.5

    def min_for_band(self, shift_start: str) -> int:
        if not shift_start:
            return self.min_per_shift
        if shift_start in self.min_by_band:
            return max(1, int(self.min_by_band[shift_start]))
        # Normalize loose keys ("6:00" vs "06:00")
        for key, val in self.min_by_band.items():
            if key.zfill(5) == shift_start.zfill(5) or key == shift_start:
                return max(1, int(val))
        return self.min_per_shift


def parse_min_staffing_by_band(raw: str) -> Dict[str, int]:
    """Parse JSON object or '06:00=2,19:00=2' text into band → min headcount."""
    import json
    import re

    if not raw or not str(raw).strip():
        return {}
    text = str(raw).strip()
    out: Dict[str, int] = {}
    if text.startswith("{"):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                for k, v in data.items():
                    try:
                        out[str(k).strip()] = max(1, int(v))
                    except (TypeError, ValueError):
                        continue
                return out
        except json.JSONDecodeError:
            pass
    for part in re.split(r"[,;\n]+", text):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
        elif ":" in part and part.count(":") >= 2:
            # "06:00:2"
            bits = part.rsplit(":", 1)
            k, v = bits[0], bits[1]
        else:
            continue
        try:
            out[k.strip()] = max(1, int(float(v.strip())))
        except (TypeError, ValueError):
            continue
    return out


def load_coverage_policy() -> CoveragePolicy:
    from logic.labor_compliance import get_max_consecutive_work_days
    from logic.operations import get_department_setting

    def _int(key: str, default: int) -> int:
        raw = get_department_setting(key, "")
        if raw in (None, ""):
            return default
        try:
            return int(float(raw))
        except (TypeError, ValueError):
            return default

    def _float(key: str, default: float) -> float:
        raw = get_department_setting(key, "")
        if raw in (None, ""):
            return default
        try:
            return float(raw)
        except (TypeError, ValueError):
            return default

    band_raw = get_department_setting("min_staffing_by_band", "") or ""
    min_by_band = parse_min_staffing_by_band(band_raw)
    return CoveragePolicy(
        min_per_shift=max(1, _int("min_staffing_per_shift", 1)),
        min_by_band=min_by_band,
        night_minimum=max(1, _int("night_minimum_officers", config.NIGHT_MINIMUM_OFFICERS)),
        min_rest_hours=_float("min_rest_hours_between_shifts", config.MIN_REST_HOURS_BETWEEN_SHIFTS),
        max_consecutive_work_days=get_max_consecutive_work_days(),
        max_cascade_depth=max(1, min(16, _int("max_bump_cascade_depth", 8))),
        max_bump_assignments=max(1, _int("bump_assignments_before_busy", config.BUMP_ASSIGNMENTS_BEFORE_BUSY)),
        beam_width=max(2, min(12, _int("coverage_beam_width", 6))),
        max_plans=max(1, min(20, _int("coverage_max_plans", 8))),
    )


@dataclass
class _SearchState:
    current_id: int
    current_shift: str
    steps: List[BumpChainStep] = field(default_factory=list)
    chain: List[Tuple[int, int]] = field(default_factory=list)
    assignment_counts: Dict[int, int] = field(default_factory=dict)
    score: float = 0.0


def list_scored_replacements(
    original_officer_id: int,
    request_date: str,
    squad: str,
    shift_start: str,
    schedule_context: Dict[int, Dict[str, str]],
    assignment_counts: Optional[Dict[int, int]] = None,
    chain_excluded_ids: Optional[Set[int]] = None,
    *,
    policy: Optional[CoveragePolicy] = None,
    enforce_minimum_rest: bool = True,
    enforce_consecutive_work: bool = True,
    limit: int = 12,
) -> List[Tuple[float, Dict]]:
    """All eligible replacements with multi-objective scores (best first)."""
    from logic.officers import get_officers_by_seniority
    from logic.scheduling import (
        normalize_shift_band,
        officer_meets_minimum_rest,
        officer_schedule_working,
        replacement_shift_start_for_rules,
        shift_end_for_start_active,
    )
    from logic.staffing_config import can_officer_cover_shift
    from validators import officer_uses_command_staff_schedule

    policy = policy or load_coverage_policy()
    coverage_date = parse_date(request_date)
    counts = dict(assignment_counts or {})
    excluded = set(chain_excluded_ids or set())
    excluded.add(original_officer_id)
    covered_band = normalize_shift_band(shift_start)
    scored: List[Tuple[float, Dict]] = []

    # Period OT map for fairness weight (CrewSense / Timefold load-balance analog)
    ot_by_id: Dict[int, float] = {}
    try:
        from logic.analytics import get_equitable_ot_ledger

        ledger = get_equitable_ot_ledger(coverage_date) or {}
        for row in ledger.get("ledger") or []:
            if isinstance(row, dict) and row.get("officer_id") is not None:
                ot_by_id[int(row["officer_id"])] = float(row.get("ot_hours") or 0)
    except Exception:
        ot_by_id = {}

    # Fatigue map (soft preference — hard stops still in callout/open-shift/manual cover)
    fatigue_by_id: Dict[int, float] = {}
    try:
        from logic.labor_compliance import compute_fatigue_score

        for o in get_officers_by_seniority():
            if o.get("active") != 1:
                continue
            try:
                fs = compute_fatigue_score(int(o["id"])) or {}
                fatigue_by_id[int(o["id"])] = float(fs.get("score") or 0)
            except Exception:
                pass
    except Exception:
        fatigue_by_id = {}

    from logic.bump_off_duty import load_off_duty_bump_policy, score_off_duty_candidate

    off_policy = load_off_duty_bump_policy()

    for officer in get_officers_by_seniority():
        if officer.get("active") != 1:
            continue
        if officer_uses_command_staff_schedule(officer):
            continue
        oid = officer["id"]
        if oid in excluded:
            continue
        if counts.get(oid, 0) >= policy.max_bump_assignments:
            continue

        day_context = schedule_context.get(oid, {})
        on_duty = officer_schedule_working(day_context)

        # --- On-duty path (existing) ---
        if on_duty:
            if officer.get("squad") != squad:
                continue
            rule_shift = replacement_shift_start_for_rules(officer, day_context)
            if not can_officer_cover_shift(rule_shift, covered_band):
                continue
            current_band = normalize_shift_band(rule_shift)
            if current_band != covered_band and enforce_minimum_rest:
                covered_end = shift_end_for_start_active(covered_band)
                if not officer_meets_minimum_rest(oid, coverage_date, covered_band, covered_end):
                    continue
            if enforce_consecutive_work:
                from logic.labor_compliance import would_exceed_consecutive_work_limit

                if would_exceed_consecutive_work_limit(oid, coverage_date, adding_work_day=False):
                    continue
            from logic.certifications import officer_meets_shift_cert_requirements

            cert_ok, _ = officer_meets_shift_cert_requirements(oid, covered_band, coverage_date)
            if not cert_ok:
                continue

            rank = int(officer.get("seniority_rank") or 0)
            used = counts.get(oid, 0)
            spare = max(0, policy.max_bump_assignments - used)
            same = 1.0 if current_band == covered_band else 0.0
            ot_h = float(ot_by_id.get(oid, officer.get("_period_ot_hours") or 0.0))
            low_ot = max(0.0, 40.0 - min(ot_h, 40.0))
            fat = float(fatigue_by_id.get(oid, 0.0))
            # 0–10 relief: rested officers score higher (soft; does not hard-block)
            low_fatigue = max(0.0, 100.0 - min(fat, 100.0)) / 10.0
            trans = same
            try:
                cov_h = int(str(covered_band or "0").split(":")[0])
                cur_h = int(str(current_band or "0").split(":")[0])
                if cur_h >= 19 and cov_h <= 10:
                    trans = 0.0
                elif same:
                    trans = 1.0
                else:
                    trans = 0.4
            except (TypeError, ValueError):
                trans = same
            score = (
                policy.w_junior * rank
                + policy.w_spare_capacity * spare
                + policy.w_same_start * same
                + policy.w_low_ot * low_ot
                + policy.w_low_fatigue * low_fatigue
                + policy.w_transition_ok * trans
            )
            if off_policy.prefer_on_duty_first:
                score += off_policy.w_on_duty_bonus
            officer = dict(officer)
            officer["_bump_on_duty"] = True
            officer["_fatigue_score"] = fat
            officer["_score_low_fatigue"] = low_fatigue
            scored.append((score, officer))
            continue

        # --- Off-duty / call-in path (optional) ---
        if not off_policy.allow_off_duty:
            continue
        if off_policy.same_squad_only and officer.get("squad") != squad:
            continue
        # Calling someone in adds a work day — consecutive limit applies
        if enforce_consecutive_work:
            from logic.labor_compliance import would_exceed_consecutive_work_limit

            if would_exceed_consecutive_work_limit(oid, coverage_date, adding_work_day=True):
                continue
        if enforce_minimum_rest:
            covered_end = shift_end_for_start_active(covered_band)
            if not officer_meets_minimum_rest(oid, coverage_date, covered_band, covered_end):
                continue
        from logic.certifications import officer_meets_shift_cert_requirements

        cert_ok, _ = officer_meets_shift_cert_requirements(oid, covered_band, coverage_date)
        if not cert_ok:
            continue

        ot_h = float(ot_by_id.get(oid, officer.get("_period_ot_hours") or 0.0))
        eligible, od_score, _detail = score_off_duty_candidate(
            officer,
            covered_shift_start=covered_band,
            request_squad=squad,
            coverage_date=coverage_date,
            policy=off_policy,
            ot_hours=ot_h,
        )
        if not eligible:
            continue
        fat = float(fatigue_by_id.get(oid, 0.0))
        low_fatigue = max(0.0, 100.0 - min(fat, 100.0)) / 10.0
        od_score = float(od_score) + policy.w_low_fatigue * low_fatigue
        officer = dict(officer)
        officer["_bump_on_duty"] = False
        officer["_off_duty_score_detail"] = _detail
        officer["_fatigue_score"] = fat
        officer["_score_low_fatigue"] = low_fatigue
        scored.append((od_score, officer))

    scored.sort(key=lambda x: (-x[0], -int(x[1].get("seniority_rank") or 0), x[1]["id"]))
    return scored[:limit]


def _plan_score(policy: CoveragePolicy, steps: List[BumpChainStep], step_scores: List[float]) -> float:
    depth_bonus = policy.w_shallow_chain * max(0, policy.max_cascade_depth - len(steps))
    return depth_bonus + sum(step_scores)


def score_components_for_plan(
    policy: CoveragePolicy,
    steps: List[BumpChainStep],
    step_scores: List[float],
) -> List[Dict]:
    """OR-Tools-style named soft components for supervisor audit."""
    depth_bonus = policy.w_shallow_chain * max(0, policy.max_cascade_depth - len(steps))
    comps: List[Dict] = [
        {
            "name": "shallow_chain_bonus",
            "value": round(depth_bonus, 2),
            "detail": f"w_shallow×(max_depth−{len(steps)})",
        },
        {
            "name": "step_scores_sum",
            "value": round(sum(step_scores), 2),
            "detail": "sum of junior/spare/same-band scores per assignment",
        },
    ]
    for i, (step, sc) in enumerate(zip(steps, step_scores), 1):
        comps.append(
            {
                "name": f"step_{i}_replacement",
                "value": round(sc, 2),
                "detail": f"{step.replacement_officer_name} covers {step.original_officer_name}",
            }
        )
    comps.append(
        {
            "name": "plan_total",
            "value": round(_plan_score(policy, steps, step_scores), 2),
            "detail": "higher is preferred (soft only; hard filters already passed)",
        }
    )
    return comps


def search_best_coverage_plans(
    original_officer_id: int,
    request_date: str,
    squad: str,
    shift_start: str,
    schedule_context: Dict[int, Dict[str, str]],
    *,
    policy: Optional[CoveragePolicy] = None,
    enforce_minimum_rest: bool = True,
    enforce_consecutive_work: bool = True,
) -> List[BumpChainSuggestion]:
    """Beam-search complete bump chains; return best plans first."""
    from logic.bump_optimizer import (
        _bump_assignment_counts_for_date,
        _chain_excluded_officer_ids,
        _night_minimum_uncovered_failure,
        _shift_retains_coverage_after_bump,
    )
    from logic.officers import get_officer_by_id
    from logic.scheduling import (
        normalize_shift_band,
        officer_schedule_working,
    )

    # ensure normalize available in loop (used for min_for_band)
    _ = normalize_shift_band

    policy = policy or load_coverage_policy()
    req_date = parse_date(request_date)
    base_counts = _bump_assignment_counts_for_date(request_date)
    root = _SearchState(
        current_id=original_officer_id,
        current_shift=normalize_shift_band(shift_start) or shift_start,
        assignment_counts=dict(base_counts),
        score=0.0,
    )

    beam: List[Tuple[float, _SearchState, List[float]]] = [(0.0, root, [])]
    complete: List[Tuple[float, BumpChainSuggestion]] = []
    explored = 0
    max_nodes = 400

    while beam and explored < max_nodes and len(complete) < policy.max_plans * 3:
        beam.sort(key=lambda x: -x[0])
        beam = beam[: policy.beam_width]
        next_beam: List[Tuple[float, _SearchState, List[float]]] = []

        for parent_score, state, step_scores in beam:
            explored += 1
            current = get_officer_by_id(state.current_id)
            if not current:
                continue

            # Already complete?
            coverage_excluded = _chain_excluded_officer_ids(state.steps, requesting_officer_id=original_officer_id)
            if state.steps and _shift_retains_coverage_after_bump(
                state.current_id,
                normalize_shift_band(state.current_shift),
                squad,
                schedule_context,
                coverage_excluded,
            ):
                # Should have closed on previous expand — skip
                continue

            chain_excluded = _chain_excluded_officer_ids(state.steps, requesting_officer_id=original_officer_id)
            candidates = list_scored_replacements(
                state.current_id,
                request_date,
                squad,
                state.current_shift,
                schedule_context,
                state.assignment_counts,
                chain_excluded,
                policy=policy,
                enforce_minimum_rest=enforce_minimum_rest,
                enforce_consecutive_work=enforce_consecutive_work,
                limit=policy.beam_width,
            )

            if not candidates:
                if not state.steps:
                    night_fail = _night_minimum_uncovered_failure(
                        req_date,
                        squad,
                        state.current_shift,
                        state.steps,
                        blocked_officer_name=current["name"],
                        blocked_shift=state.current_shift,
                    )
                    if night_fail:
                        complete.append((-1000.0, night_fail))
                continue

            for cand_score, replacement in candidates:
                if len(state.steps) >= policy.max_cascade_depth:
                    continue
                repl_context = schedule_context.get(replacement["id"], {})
                on_duty = replacement.get("_bump_on_duty")
                if on_duty is None:
                    on_duty = officer_schedule_working(repl_context)
                on_duty = bool(on_duty)
                repl_shift = repl_context.get("shift_start") or replacement.get("shift_start") or ""
                new_steps = list(state.steps)
                new_steps.append(
                    BumpChainStep(
                        step_number=len(new_steps) + 1,
                        original_officer_id=state.current_id,
                        original_officer_name=current["name"],
                        original_shift=state.current_shift,
                        replacement_officer_id=replacement["id"],
                        replacement_officer_name=replacement["name"],
                        replacement_shift=repl_shift if on_duty else (state.current_shift or repl_shift),
                        replacement_on_duty=on_duty,
                    )
                )
                new_chain = list(state.chain) + [(state.current_id, replacement["id"])]
                new_counts = dict(state.assignment_counts)
                new_counts[replacement["id"]] = new_counts.get(replacement["id"], 0) + 1
                new_step_scores = step_scores + [cand_score]

                # Off-duty call-in: no cascade (they were not staffing a band to vacate)
                if not on_duty:
                    plan_score = _plan_score(policy, new_steps, new_step_scores)
                    primary = get_officer_by_id(new_chain[0][1])
                    n_assign = len(new_chain)
                    suggestion = BumpChainSuggestion(
                        success=True,
                        chain=new_chain,
                        steps=new_steps,
                        primary_replacement_name=primary["name"] if primary else None,
                        message=(
                            f"Coverage via off-duty call-in — {n_assign} assignment{'s' if n_assign != 1 else ''}"
                        ),
                        plan_score=plan_score,
                        alternatives_considered=explored,
                        score_components=score_components_for_plan(policy, new_steps, new_step_scores),
                    )
                    complete.append((plan_score, suggestion))
                    continue

                # Stop if vacated band still meets per-band min staffing
                vacate_excluded = _chain_excluded_officer_ids(new_steps, requesting_officer_id=original_officer_id)
                min_rem = policy.min_for_band(normalize_shift_band(repl_shift) or repl_shift)
                if _shift_retains_coverage_after_bump(
                    replacement["id"],
                    repl_shift,
                    squad,
                    schedule_context,
                    vacate_excluded,
                    min_remaining=min_rem,
                ):
                    plan_score = _plan_score(policy, new_steps, new_step_scores)
                    primary = get_officer_by_id(new_chain[0][1])
                    n_assign = len(new_chain)
                    suggestion = BumpChainSuggestion(
                        success=True,
                        chain=new_chain,
                        steps=new_steps,
                        primary_replacement_name=primary["name"] if primary else None,
                        message=(f"Coverage plan ready — {n_assign} assignment{'s' if n_assign != 1 else ''}"),
                        plan_score=plan_score,
                        alternatives_considered=explored,
                        score_components=score_components_for_plan(policy, new_steps, new_step_scores),
                    )
                    complete.append((plan_score, suggestion))
                    continue

                child = _SearchState(
                    current_id=replacement["id"],
                    current_shift=repl_shift or state.current_shift,
                    steps=new_steps,
                    chain=new_chain,
                    assignment_counts=new_counts,
                    score=parent_score + cand_score,
                )
                next_beam.append((child.score, child, new_step_scores))

        beam = next_beam

    complete.sort(key=lambda x: -x[0])
    # De-dupe by chain signature
    seen: Set[Tuple[Tuple[int, int], ...]] = set()
    unique: List[BumpChainSuggestion] = []
    for score, plan in complete:
        if not plan.success:
            if not unique:
                unique.append(plan)
            continue
        sig = tuple(plan.chain)
        if sig in seen:
            continue
        seen.add(sig)
        plan.plan_score = score
        unique.append(plan)
        if len(unique) >= policy.max_plans:
            break

    # Tag option rank on complete plans (1 = best). Scores stay internal only.
    success_plans = [p for p in unique if p.success]
    total_ok = len(success_plans)
    for option_n, plan in enumerate(success_plans, 1):
        n_assign = len(plan.chain or [])
        off_duty = any(not s.replacement_on_duty for s in (plan.steps or []))
        if off_duty:
            plan.message = f"Option {option_n}: off-duty call-in — {n_assign} assignment{'s' if n_assign != 1 else ''}"
        else:
            plan.message = f"Option {option_n}: {n_assign} assignment{'s' if n_assign != 1 else ''}"
        plan.alternatives_considered = total_ok

    if unique:
        return unique

    # No complete plan
    return [
        BumpChainSuggestion(
            success=False,
            message="No complete coverage plan under current staffing and compliance rules",
            requires_manual=True,
            failure_reason="no_replacement",
            alternatives_considered=explored,
        )
    ]


def optimize_day_off_coverage(
    original_officer_id: int,
    request_date: str,
    squad: str,
    shift_start: str,
    *,
    supervisor_override: bool = False,
    max_depth: int = 8,
) -> BumpChainSuggestion:
    """Entry for day-off / bump: best complete chain or manual-review failure."""
    from logic.bump_optimizer import (
        _bump_assignment_counts_for_date,
        _consecutive_days_manual_failure,
        _minimum_rest_manual_failure,
    )
    from logic.officers import get_officer_by_id
    from logic.scheduling import (
        get_generated_schedule_day_context,
        normalize_shift_band,
    )

    policy = load_coverage_policy()
    policy.max_cascade_depth = max_depth
    req_date = parse_date(request_date)
    schedule_context = get_generated_schedule_day_context(req_date)
    enforce = not supervisor_override

    plans = search_best_coverage_plans(
        original_officer_id,
        request_date,
        squad,
        shift_start,
        schedule_context,
        policy=policy,
        enforce_minimum_rest=enforce,
        enforce_consecutive_work=enforce,
    )
    best = plans[0]
    if best.success:
        n = len([p for p in plans if p.success])
        n_assign = len(best.chain or [])
        if n > 1:
            best.message = f"Best of {n} options — {n_assign} assignment{'s' if n_assign != 1 else ''}"
        else:
            best.message = f"Auto-approve ready — {n_assign} assignment{'s' if n_assign != 1 else ''}"
        best.alternatives_considered = n
        return best

    # Soft failures → manual paths (rest / consecutive)
    officer = get_officer_by_id(original_officer_id)
    name = officer["name"] if officer else "Officer"
    band = normalize_shift_band(shift_start)
    counts = _bump_assignment_counts_for_date(request_date)
    excluded: Set[int] = {original_officer_id}
    if enforce:
        rest = _minimum_rest_manual_failure(
            request_date, band, schedule_context, counts, excluded, original_officer_id, squad, name, band
        )
        if rest:
            return rest
        consecutive = _consecutive_days_manual_failure(
            request_date, band, schedule_context, counts, excluded, original_officer_id, squad, name, band
        )
        if consecutive:
            return consecutive
    return best


def optimize_staffing_scenarios(**kwargs) -> Dict:
    """Shim → logic.staffing_optimizer (schedule sim search; NOT bump cascade)."""
    from logic.staffing_optimizer import optimize_staffing_scenarios as _opt

    return _opt(**kwargs)


# Public optimizer entrypoints for bump plans (implementation: bump_optimizer.py)
from logic.bump_optimizer import (  # noqa: E402,F401
    count_remaining_on_shift_band,
    find_replacement_officer,
    format_bump_suggestion,
    plan_bump_chain,
    suggest_bump_chain,
    validate_bump_feasibility,
)
