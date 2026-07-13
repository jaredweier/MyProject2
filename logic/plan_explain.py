"""
Explainable coverage plans — math-domain / supervisor trust.

Formats multi-plan optimizer output into human-readable score breakdowns.
Inspired by OR-Tools shift_scheduling_sat (print each penalty) and
Timefold ConstraintProvider (named hard/soft constraints).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def explain_score_weights(policy: Optional[Dict[str, Any]] = None) -> str:
    """Document soft-score formula (mirrors coverage_optimizer.list_scored_replacements)."""
    p = policy or {}
    w_j = p.get("w_junior", "w_junior")
    w_s = p.get("w_spare_capacity", "w_spare")
    w_same = p.get("w_same_start", "w_same")
    w_depth = p.get("w_shallow_chain", "w_shallow")
    return (
        "Soft score (higher better) ≈ "
        f"{w_j}×seniority_rank(junior-first) + "
        f"{w_s}×spare_bump_slots + "
        f"{w_same}×same_shift_band + "
        f"{w_depth}×(max_depth − chain_length)\n"
        "Hard gates (must pass before scoring): squad match, working that day, "
        "cover-allowed band, rest gap, consecutive-work limit, cert requirements, "
        "max bump assignments."
    )


def explain_replacement_components(
    officer: Dict[str, Any],
    *,
    policy: Optional[Dict[str, Any]] = None,
    assignment_used: int = 0,
    same_band: bool = True,
) -> str:
    """OR-Tools-style component print for one candidate."""
    p = policy or {}
    try:
        w_j = float(p.get("w_junior", 1.0))
        w_s = float(p.get("w_spare_capacity", 1.0))
        w_same = float(p.get("w_same_start", 1.0))
        max_bump = int(p.get("max_bump_assignments", 2) or 2)
    except (TypeError, ValueError):
        w_j, w_s, w_same, max_bump = 1.0, 1.0, 1.0, 2
    rank = int(officer.get("seniority_rank") or 0)
    spare = max(0, max_bump - assignment_used)
    same = 1.0 if same_band else 0.0
    total = w_j * rank + w_s * spare + w_same * same
    name = officer.get("name") or officer.get("id") or "?"
    return (
        f"{name}: score={total:.1f} "
        f"[junior={w_j}×{rank}={w_j * rank:.1f}; "
        f"spare={w_s}×{spare}={w_s * spare:.1f}; "
        f"same_band={w_same}×{same:g}={w_same * same:.1f}]"
    )


def explain_coverage_plans(payload: Dict[str, Any]) -> str:
    """Turn preview_best_coverage_plans result into multi-line supervisor text."""
    if not isinstance(payload, dict):
        return str(payload)
    if payload.get("success") is False:
        return payload.get("message") or "No viable plans"
    plans = payload.get("plans") or []
    if not plans:
        return payload.get("message") or "No plans returned"
    lines: List[str] = []
    pol = payload.get("policy") or {}
    if pol:
        lines.append(
            f"Policy: min_band={pol.get('min_per_shift', pol.get('min_per_band', '—'))} "
            f"night_min={pol.get('night_minimum', '—')} "
            f"rest={pol.get('min_rest_hours', '—')}h "
            f"max_depth={pol.get('max_cascade_depth', '—')}"
        )
        # Named weights (Timefold / OR-Tools style transparency)
        weight_bits = []
        for key in (
            "w_junior",
            "w_spare_capacity",
            "w_same_start",
            "w_shallow_chain",
            "beam_width",
            "max_plans",
        ):
            if key in pol:
                weight_bits.append(f"{key}={pol[key]}")
        if weight_bits:
            lines.append("Weights: " + " ".join(weight_bits))
        lines.append("")
        lines.append(explain_score_weights(pol))
        lines.append("")
    for i, plan in enumerate(plans, 1):
        if not isinstance(plan, dict):
            lines.append(f"Plan {i}: {plan}")
            continue
        score = plan.get("plan_score", plan.get("score", "—"))
        ok = plan.get("success")
        manual = plan.get("requires_manual")
        msg = plan.get("message") or ""
        flag = "MANUAL" if manual else ("OK" if ok else "FAIL")
        lines.append(f"── Plan {i} [{flag}] score={score}")
        if msg:
            lines.append(f"   {msg}")
        # Soft component list if present
        comps = plan.get("score_components") or plan.get("penalties") or []
        if comps:
            lines.append("   Score components (named, like OR-Tools penalties):")
            for c in comps[:12]:
                if isinstance(c, dict):
                    lines.append(f"     • {c.get('name') or c.get('id')}: {c.get('value') or c.get('delta') or c}")
                else:
                    lines.append(f"     • {c}")
        steps = plan.get("steps") or []
        if steps:
            for st in steps:
                if isinstance(st, dict):
                    step_score = st.get("score") or st.get("step_score")
                    score_bit = f" score={step_score}" if step_score is not None else ""
                    lines.append(
                        f"   Step {st.get('step', '?')}: "
                        f"{st.get('original', '?')} ← {st.get('replacement', '?')} "
                        f"({st.get('from_shift', '?')} → {st.get('to_shift', '?')})"
                        f"{score_bit}"
                    )
                    # Inline component breakdown when officers embedded
                    rep = st.get("replacement_officer") or st.get("replacement_detail")
                    if isinstance(rep, dict):
                        lines.append(
                            "     "
                            + explain_replacement_components(
                                rep,
                                policy=pol,
                                same_band=st.get("same_band", True),
                            )
                        )
                else:
                    lines.append(f"   {st}")
        elif plan.get("chain"):
            lines.append(f"   chain={plan.get('chain')}")
        if plan.get("failure_reason"):
            lines.append(f"   reason: {plan['failure_reason']}")
        lines.append("")
    lines.append(
        "Higher score preferred (junior bumps, shallower chains, spare capacity). "
        "Hard constraints never trade against soft scores."
    )
    return "\n".join(lines).strip()
