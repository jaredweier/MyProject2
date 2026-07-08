"""
Schedule Simulator — generates and optimizes 24/7 patrol coverage plans.
Pure logic module; called from logic.py.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from config import (
    NIGHT_MINIMUM_OFFICERS,
    ROTATION_PRESETS,
    is_high_risk_night,
)
from validators import format_date

try:
    from logic import rust_bridge
except ImportError:
    rust_bridge = None  # type: ignore


@dataclass
class SimulatorConfig:
    rotation_type: str
    num_officers: int
    shift_length_hours: float
    annual_hours_target: float
    shift_starts: List[str]
    apply_department_rules: bool = True
    min_per_shift: int = 1
    simulation_days: int = 28
    night_minimum: int = NIGHT_MINIMUM_OFFICERS


@dataclass
class SimulatorSuggestion:
    severity: str
    title: str
    message: str
    recommendation: str = ""


@dataclass
class SimulatorOfficerSlot:
    slot_id: int
    label: str
    squad: str
    shift_start: str
    shift_end: str
    projected_annual_hours: float
    work_days_in_sim: int


@dataclass
class SimulatorResult:
    success: bool
    message: str = ""
    compute_backend: str = "python"
    shift_templates: List[Tuple[str, str]] = field(default_factory=list)
    officer_slots: List[SimulatorOfficerSlot] = field(default_factory=list)
    coverage_by_day: List[Dict] = field(default_factory=list)
    metrics: Dict = field(default_factory=dict)
    suggestions: List[SimulatorSuggestion] = field(default_factory=list)


def _parse_time_minutes(value: str) -> int:
    parts = value.strip().split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _format_minutes(total: int) -> str:
    total = total % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def _shift_end(start: str, hours: float) -> str:
    return _format_minutes(_parse_time_minutes(start) + int(hours * 60))


def _is_night_shift_start(start: str) -> bool:
    hour = int(start.split(":")[0])
    return hour >= 18 or hour < 6


def generate_shift_templates(
    shift_length_hours: float,
    shift_starts: Optional[List[str]] = None,
    use_department_shifts: bool = False,
) -> List[Tuple[str, str]]:
    if use_department_shifts:
        from logic.staffing_config import get_active_shift_times

        return list(get_active_shift_times().values())

    if shift_starts:
        cleaned = [s.strip() for s in shift_starts if s.strip()]
        if cleaned:
            return [(s, _shift_end(s, shift_length_hours)) for s in cleaned]

    templates = []
    length_minutes = int(shift_length_hours * 60)
    if length_minutes <= 0:
        return templates
    count = max(1, math.ceil((24 * 60) / length_minutes))
    spacing = (24 * 60) // count
    for i in range(count):
        start = _format_minutes(i * spacing)
        templates.append((start, _shift_end(start, shift_length_hours)))
    return templates


def _squad_working(rotation_type: str, squad: str, cycle_day: int, preset: Dict) -> bool:
    if "squad_a_days" in preset:
        on_a = cycle_day in preset["squad_a_days"]
        return on_a if squad == "A" else not on_a
    if "squad_patterns" in preset:
        pattern = preset["squad_patterns"].get(squad, preset["squad_patterns"].get("A", []))
        idx = (cycle_day - 1) % len(pattern)
        return pattern[idx] == 1
    work_days = preset.get("work_days_per_cycle", 7)
    half = work_days // preset.get("squads", 2)
    if squad == "A":
        return ((cycle_day - 1) % preset["cycle_length"]) < half
    offset = preset["cycle_length"] // preset.get("squads", 2)
    return ((cycle_day - 1 + offset) % preset["cycle_length"]) < half


def _assign_officers(
    num_officers: int,
    shift_templates: List[Tuple[str, str]],
    preset: Dict,
    roster_officers: Optional[List[Dict]] = None,
) -> List[SimulatorOfficerSlot]:
    squads = ["A", "B"] if preset.get("squads", 2) >= 2 else ["A"]
    slots = []
    roster = (roster_officers or [])[:num_officers]
    count = len(roster) if roster else num_officers
    for i in range(count):
        shift_start, shift_end = shift_templates[i % len(shift_templates)]
        if roster:
            officer = roster[i]
            slots.append(
                SimulatorOfficerSlot(
                    slot_id=officer["id"],
                    label=officer["name"],
                    squad=officer.get("squad") or squads[i % len(squads)],
                    shift_start=shift_start,
                    shift_end=shift_end,
                    projected_annual_hours=0.0,
                    work_days_in_sim=0,
                )
            )
        else:
            squad = squads[i % len(squads)]
            slots.append(
                SimulatorOfficerSlot(
                    slot_id=i + 1,
                    label=f"Officer {i + 1}",
                    squad=squad,
                    shift_start=shift_start,
                    shift_end=shift_end,
                    projected_annual_hours=0.0,
                    work_days_in_sim=0,
                )
            )
    return slots


def _optimize_assignments(
    slots: List[SimulatorOfficerSlot],
    shift_templates: List[Tuple[str, str]],
    coverage_gaps: Dict[Tuple[int, str], int],
) -> List[SimulatorOfficerSlot]:
    """Greedy rebalance — move officers to shifts with the worst gaps."""
    if not coverage_gaps or not shift_templates:
        return slots
    ranked = sorted(coverage_gaps.items(), key=lambda x: x[1])
    for idx, slot in enumerate(slots):
        worst_day, worst_shift = ranked[idx % len(ranked)][0]
        template = next(
            (t for t in shift_templates if t[0] == worst_shift), shift_templates[idx % len(shift_templates)]
        )
        slot.shift_start, slot.shift_end = template
    return slots


def simulate_schedule(config: SimulatorConfig) -> SimulatorResult:
    preset = ROTATION_PRESETS.get(config.rotation_type)
    if not preset:
        return SimulatorResult(success=False, message=f"Unknown rotation type: {config.rotation_type}")

    if config.num_officers < 1:
        return SimulatorResult(success=False, message="At least one officer is required")
    if config.shift_length_hours <= 0:
        return SimulatorResult(success=False, message="Shift length must be positive")

    shift_templates = generate_shift_templates(
        config.shift_length_hours,
        config.shift_starts,
        use_department_shifts=config.apply_department_rules,
    )
    if not shift_templates:
        return SimulatorResult(success=False, message="Could not build shift templates")

    roster_officers = None
    if config.apply_department_rules:
        from logic import get_officers_by_seniority

        roster_officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
    slots = _assign_officers(config.num_officers, shift_templates, preset, roster_officers)
    if config.apply_department_rules:
        from logic.rotation_config import get_active_rotation_cycle_length, get_active_squad_a_days

        cycle_length = get_active_rotation_cycle_length()
        squad_a_days = set(get_active_squad_a_days())
    else:
        cycle_length = preset["cycle_length"]
        squad_a_days = set(preset.get("squad_a_days", {1, 2, 5, 6, 7, 10, 11}))
    sim_start = date.today()

    compute_backend = rust_bridge.backend_name() if rust_bridge else "python"

    if rust_bridge and rust_bridge.available():
        rust_config = {
            "rotation_type": config.rotation_type,
            "num_officers": config.num_officers,
            "shift_length_hours": config.shift_length_hours,
            "simulation_days": config.simulation_days,
            "min_per_shift": config.min_per_shift,
            "apply_department_rules": config.apply_department_rules,
            "annual_hours_target": config.annual_hours_target,
            "night_minimum": config.night_minimum,
            "shift_templates": shift_templates,
            "squad_a_days": squad_a_days,
        }
        rust_out = rust_bridge.simulate_schedule_rust(rust_config, preset, sim_start)
        if rust_out and rust_out.get("success"):
            coverage = rust_out.get("coverage_by_day", [])
            metrics = _enrich_rust_sim_metrics(
                config,
                dict(rust_out.get("metrics", {})),
                coverage,
                slots,
            )
            metrics["compute_backend"] = "rust"
            gap_counter: Dict = {}
            suggestions = _build_suggestions(config, metrics, shift_templates, gap_counter)
            return SimulatorResult(
                success=True,
                message=rust_out.get("message", "Simulation complete"),
                compute_backend="rust",
                shift_templates=shift_templates,
                officer_slots=slots,
                coverage_by_day=coverage,
                metrics=metrics,
                suggestions=suggestions,
            )

    coverage_by_day: List[Dict] = []
    gap_counter: Dict[Tuple[int, str], int] = {}
    min_coverage = 999
    max_coverage = 0
    night_risk_gaps = 0
    total_gap_hours = 0

    for day_offset in range(config.simulation_days):
        target = sim_start + timedelta(days=day_offset)
        cycle_day = (day_offset % cycle_length) + 1
        shift_counts: Dict[str, int] = {t[0]: 0 for t in shift_templates}
        working_officers = []

        for slot in slots:
            if config.apply_department_rules:
                from logic.rotation_config import is_squad_working

                if not is_squad_working(slot.squad, cycle_day, preset):
                    continue
            elif not _squad_working(config.rotation_type, slot.squad, cycle_day, preset):
                continue
            slot.work_days_in_sim += 1
            shift_counts[slot.shift_start] = shift_counts.get(slot.shift_start, 0) + 1
            working_officers.append(slot)

        day_min = min(shift_counts.values()) if shift_counts else 0
        day_max = max(shift_counts.values()) if shift_counts else 0
        min_coverage = min(min_coverage, day_min)
        max_coverage = max(max_coverage, day_max)

        for shift_start, count in shift_counts.items():
            required = config.min_per_shift
            if config.apply_department_rules and _is_night_shift_start(shift_start) and is_high_risk_night(target):
                required = max(required, config.night_minimum)
            if count < required:
                gap = required - count
                gap_counter[(day_offset, shift_start)] = gap_counter.get((day_offset, shift_start), 0) + gap
                total_gap_hours += gap * config.shift_length_hours
                if _is_night_shift_start(shift_start) and is_high_risk_night(target):
                    night_risk_gaps += 1

        coverage_by_day.append(
            {
                "date": format_date(target),
                "cycle_day": cycle_day,
                "shift_counts": shift_counts,
                "working_officers": len(working_officers),
                "min_shift_coverage": day_min,
                "high_risk_night": is_high_risk_night(target),
            }
        )

    if gap_counter:
        slots = _optimize_assignments(slots, shift_templates, gap_counter)
        # Re-run quick metrics after optimization
        gap_counter.clear()
        total_gap_hours = 0
        night_risk_gaps = 0
        min_coverage = 999
        for slot in slots:
            slot.work_days_in_sim = 0
        for day_offset in range(config.simulation_days):
            target = sim_start + timedelta(days=day_offset)
            cycle_day = (day_offset % cycle_length) + 1
            shift_counts = {t[0]: 0 for t in shift_templates}
            for slot in slots:
                if _squad_working(config.rotation_type, slot.squad, cycle_day, preset):
                    slot.work_days_in_sim += 1
                    shift_counts[slot.shift_start] = shift_counts.get(slot.shift_start, 0) + 1
            day_min = min(shift_counts.values()) if shift_counts else 0
            min_coverage = min(min_coverage, day_min)
            for shift_start, count in shift_counts.items():
                required = config.min_per_shift
                if config.apply_department_rules and _is_night_shift_start(shift_start) and is_high_risk_night(target):
                    required = max(required, config.night_minimum)
                if count < required:
                    gap = required - count
                    gap_counter[(day_offset, shift_start)] = gap
                    total_gap_hours += gap * config.shift_length_hours
                    if _is_night_shift_start(shift_start) and is_high_risk_night(target):
                        night_risk_gaps += 1

    hours_per_work_day = config.shift_length_hours
    for slot in slots:
        annual_factor = 365 / max(config.simulation_days, 1)
        slot.projected_annual_hours = round(slot.work_days_in_sim * hours_per_work_day * annual_factor, 1)

    hours_list = [s.projected_annual_hours for s in slots]
    avg_hours = sum(hours_list) / len(hours_list) if hours_list else 0
    hours_variance = 0.0
    if hours_list and avg_hours:
        hours_variance = max(hours_list) / avg_hours - min(hours_list) / avg_hours

    slots_per_day = len(shift_templates)
    weekly_hours_needed = 24 * 7 * config.min_per_shift
    annual_hours_needed = weekly_hours_needed * 52
    fte_required = annual_hours_needed / max(config.annual_hours_target, 1)

    coverage_pct = 100.0
    if gap_counter:
        total_required = config.simulation_days * slots_per_day * config.min_per_shift
        total_met = total_required - sum(gap_counter.values())
        coverage_pct = round(100 * total_met / max(total_required, 1), 1)

    metrics = {
        "coverage_percent": coverage_pct,
        "min_shift_coverage": min_coverage if min_coverage != 999 else 0,
        "max_shift_coverage": max_coverage,
        "fte_required": round(fte_required, 2),
        "avg_annual_hours": round(avg_hours, 1),
        "hours_variance_ratio": round(hours_variance, 3),
        "gap_events": len(gap_counter),
        "night_risk_gaps": night_risk_gaps,
        "total_gap_hours": round(total_gap_hours, 1),
        "shifts_per_day": slots_per_day,
        "compute_backend": compute_backend,
    }

    suggestions = _build_suggestions(config, metrics, shift_templates, gap_counter)

    return SimulatorResult(
        success=True,
        message="Simulation complete",
        compute_backend=compute_backend,
        shift_templates=shift_templates,
        officer_slots=slots,
        coverage_by_day=coverage_by_day,
        metrics=metrics,
        suggestions=suggestions,
    )


def _enrich_rust_sim_metrics(
    config: SimulatorConfig,
    metrics: Dict,
    coverage_by_day: List[Dict],
    slots: List[SimulatorOfficerSlot],
) -> Dict:
    """Fill presentation metrics Rust omits (gap hours, night risk, annual hours)."""
    gap_events = int(metrics.get("gap_events", 0))
    total_gap_hours = gap_events * config.shift_length_hours
    night_risk_gaps = 0
    for day in coverage_by_day:
        if not day.get("high_risk_night"):
            continue
        shift_counts = day.get("shift_counts", {})
        for shift_start, count in shift_counts.items():
            required = config.min_per_shift
            if config.apply_department_rules and _is_night_shift_start(shift_start):
                required = max(required, config.night_minimum)
            if count < required:
                night_risk_gaps += 1

    annual_factor = 365 / max(config.simulation_days, 1)
    hours_list = []
    for slot in slots:
        slot.projected_annual_hours = round(slot.work_days_in_sim * config.shift_length_hours * annual_factor, 1)
        hours_list.append(slot.projected_annual_hours)
    avg_hours = sum(hours_list) / len(hours_list) if hours_list else 0.0
    hours_variance = 0.0
    if hours_list and avg_hours:
        hours_variance = max(hours_list) / avg_hours - min(hours_list) / avg_hours

    enriched = dict(metrics)
    enriched.setdefault("total_gap_hours", round(total_gap_hours, 1))
    enriched.setdefault("night_risk_gaps", night_risk_gaps)
    enriched.setdefault("avg_annual_hours", round(avg_hours, 1))
    enriched.setdefault("hours_variance_ratio", round(hours_variance, 3))
    return enriched


def _build_suggestions(
    config: SimulatorConfig,
    metrics: Dict,
    shift_templates: List[Tuple[str, str]],
    gap_counter: Dict,
) -> List[SimulatorSuggestion]:
    suggestions: List[SimulatorSuggestion] = []

    if metrics["fte_required"] > config.num_officers:
        need = math.ceil(metrics["fte_required"] - config.num_officers)
        suggestions.append(
            SimulatorSuggestion(
                severity="critical",
                title="Understaffed for 24/7 coverage",
                message=(
                    f"Estimated {metrics['fte_required']:.1f} FTE required; you have {config.num_officers} officers."
                ),
                recommendation=f"Add at least {need} officer(s) or extend shift overlap.",
            )
        )

    if metrics["coverage_percent"] < 100:
        suggestions.append(
            SimulatorSuggestion(
                severity="critical",
                title="Coverage gaps detected",
                message=(
                    f"{metrics['gap_events']} understaffed shift(s); "
                    f"{metrics['total_gap_hours']:.0f} gap hours in simulation."
                ),
                recommendation="Reassign officers to under-covered shifts or add a shift start time.",
            )
        )

    if config.apply_department_rules and metrics["night_risk_gaps"] > 0:
        suggestions.append(
            SimulatorSuggestion(
                severity="warning",
                title="Friday/Saturday night minimum at risk",
                message=f"{metrics['night_risk_gaps']} night shift(s) below department minimum.",
                recommendation=f"Assign {NIGHT_MINIMUM_OFFICERS}+ officers to each night shift on Fri/Sat.",
            )
        )

    if metrics["avg_annual_hours"] > config.annual_hours_target * 1.08:
        suggestions.append(
            SimulatorSuggestion(
                severity="warning",
                title="Annual hours exceed target",
                message=(
                    f"Average projected {metrics['avg_annual_hours']:.0f}h vs target {config.annual_hours_target:.0f}h."
                ),
                recommendation="Add officers, shorten shifts, or use a lighter rotation pattern.",
            )
        )
    elif metrics["avg_annual_hours"] < config.annual_hours_target * 0.85:
        suggestions.append(
            SimulatorSuggestion(
                severity="info",
                title="Room for additional duties",
                message=f"Average projected {metrics['avg_annual_hours']:.0f}h — below annual target.",
                recommendation="Officers have capacity for training, court, or special assignments.",
            )
        )

    if metrics["hours_variance_ratio"] > 0.2:
        suggestions.append(
            SimulatorSuggestion(
                severity="info",
                title="Uneven hour distribution",
                message="Projected annual hours vary significantly between officer slots.",
                recommendation="Rotate shift assignments or rebalance squads.",
            )
        )

    if len(shift_templates) < math.ceil(24 / config.shift_length_hours):
        suggestions.append(
            SimulatorSuggestion(
                severity="info",
                title="Consider additional shift bands",
                message=(f"{len(shift_templates)} shift band(s) for {config.shift_length_hours:.0f}-hour blocks."),
                recommendation="Add shift start times to reduce handoff gaps.",
            )
        )

    if not gap_counter and metrics["coverage_percent"] >= 99:
        suggestions.append(
            SimulatorSuggestion(
                severity="info",
                title="Strong coverage profile",
                message="Simulation meets minimum staffing across all shift bands.",
                recommendation="Export assignments to the roster or view Original Monthly Schedule.",
            )
        )

    return suggestions


def config_from_current_roster() -> SimulatorConfig:
    """Build simulator defaults from live department configuration."""
    from logic import get_officers_by_seniority
    from logic.rotation_config import get_active_rotation_preset_name
    from logic.staffing_config import (
        get_active_annual_hours_target,
        get_active_shift_length_hours,
        get_active_shift_starts,
    )

    officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
    shift_starts = get_active_shift_starts() or sorted({o["shift_start"] for o in officers})
    return SimulatorConfig(
        rotation_type=get_active_rotation_preset_name(),
        num_officers=max(len(officers), 1),
        shift_length_hours=get_active_shift_length_hours(),
        annual_hours_target=get_active_annual_hours_target(),
        shift_starts=shift_starts,
        apply_department_rules=True,
        min_per_shift=1,
    )
