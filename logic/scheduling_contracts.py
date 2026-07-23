"""Canonical scheduling contracts (PRODUCT_MASTER_PLAN.md section 3).

Tier A definition. Do not weaken or bypass without explicit user authorization
per the master plan's protected-governance rule.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if callable(obj):
        # A bare str(obj) on a function/lambda/bound-method includes its
        # runtime memory address (e.g. "<function <lambda> at 0x7f...>"),
        # which differs across otherwise-identical calls (a fresh closure
        # built inline, or the same callback rebound each process run) and
        # would silently make the hash unreproducible. Use a stable
        # qualified name instead so identical logical input always hashes
        # the same regardless of which callable instance carried it.
        return f"<callable:{getattr(obj, '__qualname__', type(obj).__name__)}>"
    return str(obj)


def compute_input_hash(payload: Any) -> str:
    """Stable hash of a search's input payload (`SimulationReport.input_hash`).
    Sorted-key JSON so key order never changes the hash; non-JSON values
    (dates, dataclasses, etc.) fall back to `str()` rather than raising."""
    encoded = json.dumps(payload, sort_keys=True, default=_json_default)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


# Constraint/policy knobs shared by every search entry point that builds a
# SimulationReport (staffing_cpsat.py's 3 solvers + staffing_optimizer.py's
# optimize_staffing_scenarios). Deliberately excludes instance-only data
# (officer count, dates, patterns) and search-only knobs (time limits,
# solution-pool size, progress callbacks) so two runs against the same rule
# set hash identically even if the problem instance or search budget differs.
POLICY_KEYS = (
    "coverage_247",
    "extra_windows",
    "annual_hours_target",
    "annual_hours_variance",
    "annual_hours_hard",
    "max_consecutive_work_days",
    "min_rest_hours",
    "constraint_weights",
    "constraint_priority",
    "require_hard_ok",
)


def compute_policy_hash(kwargs: dict[str, Any]) -> str:
    """Stable hash of just the constraint/policy subset of a search's kwargs
    (`SimulationReport.policy_hash`) — same rule set, different instance or
    search budget, hashes the same."""
    payload = {k: kwargs[k] for k in POLICY_KEYS if k in kwargs}
    return compute_input_hash(payload)


class ScheduleStatus(str, Enum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"
    MODEL_INVALID = "MODEL_INVALID"
    ENGINE_UNAVAILABLE = "ENGINE_UNAVAILABLE"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


_LEGACY_STATUS_MAP = {
    "proven_optimal": ScheduleStatus.OPTIMAL,
    "feasible_time_limited": ScheduleStatus.FEASIBLE,
    "feasible": ScheduleStatus.FEASIBLE,
    "infeasible": ScheduleStatus.INFEASIBLE,
    "proven_infeasible": ScheduleStatus.INFEASIBLE,
    "unknown": ScheduleStatus.UNKNOWN,
    "unknown_or_time_limited": ScheduleStatus.UNKNOWN,
    "unknown_time_limited": ScheduleStatus.UNKNOWN,
    "feasible_search_complete": ScheduleStatus.FEASIBLE,
    "cancelled": ScheduleStatus.CANCELLED,
    "canceled": ScheduleStatus.CANCELLED,
    "error": ScheduleStatus.ERROR,
    "model_invalid": ScheduleStatus.MODEL_INVALID,
    "engine_unavailable": ScheduleStatus.ENGINE_UNAVAILABLE,
}


def to_canonical_status(raw: str | ScheduleStatus) -> ScheduleStatus:
    """Map an existing ad-hoc solver/status string to the canonical enum.

    Unknown input never collapses to INFEASIBLE (product law) — it maps to
    UNKNOWN so a caller cannot accidentally misreport a real result.
    """
    if isinstance(raw, ScheduleStatus):
        return raw
    key = str(raw).strip().lower()
    return _LEGACY_STATUS_MAP.get(key, ScheduleStatus.UNKNOWN)


@dataclass
class VerificationReport:
    """Output of an independent verifier that recalculates constraints
    rather than reusing the solver's own decision logic."""

    verified: bool
    status: ScheduleStatus
    violations: list[str] = field(default_factory=list)
    checked_constraints: list[str] = field(default_factory=list)
    notes: str = ""


# --- Master plan section 3: canonical scheduling model ----------------------
#
# These typed contracts are the target shape for the simulator, bumping,
# leave, vacancy fill, overtime, live schedule, API, and independent
# verifier. They are additive definitions only — no existing call site has
# been rewired to produce or consume them yet. Do not assume any current
# function returns one of these; check the call site.


@dataclass
class ConstraintProfile:
    """Hard/soft rule set applied to a search: rest, consecutive-work,
    hour limits, CBA/seniority rules, qualification/certification
    requirements, and constraint priority order."""

    min_rest_hours: float | None = None
    max_consecutive_work_days: int | None = None
    max_hours_per_period: float | None = None
    annual_hours_target: float | None = None
    annual_hours_variance: float | None = None
    required_qualifications: list[str] = field(default_factory=list)
    required_certifications: list[str] = field(default_factory=list)
    cba_rules: dict[str, Any] = field(default_factory=dict)
    constraint_priority: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchProfile:
    """Search-time controls: time/step budget, solution-pool size,
    cancellation, and reproducibility seed."""

    time_limit_sec: float | None = None
    max_solutions: int = 1
    seed: int | None = None
    cancellable: bool = True
    exhaustive: bool = False


@dataclass
class CoverageDisruptionSpec:
    """A leave, callout, vacancy, or other event that breaks an existing
    coverage plan and must be resolved by bumping, OT-fill, or a new plan."""

    disruption_type: str
    affected_date: str
    affected_interval_start: str | None = None
    affected_interval_end: str | None = None
    officer_id: int | None = None
    post_id: str | None = None
    reason: str = ""


@dataclass
class StaffingProblemSpec:
    """One canonical problem definition shared by the simulator, bumping,
    leave, vacancy fill, overtime, and live-schedule paths."""

    tenant_id: str
    organization: str
    time_zone: str
    horizon_start: str
    horizon_end: str
    coverage_intervals: list[dict[str, Any]] = field(default_factory=list)
    posts: list[str] = field(default_factory=list)
    units: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    officers: list[int] = field(default_factory=list)
    availability: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    leave: list[CoverageDisruptionSpec] = field(default_factory=list)
    locked_assignments: list[dict[str, Any]] = field(default_factory=list)
    rotations: list[str] = field(default_factory=list)
    constraints: ConstraintProfile = field(default_factory=ConstraintProfile)
    search: SearchProfile = field(default_factory=SearchProfile)
    override_permissions: list[str] = field(default_factory=list)
    schema_version: str = "1"


@dataclass
class ScheduleCandidate:
    """One proposed assignment set, with the objective values and applied
    rules that produced it."""

    assignments: list[dict[str, Any]] = field(default_factory=list)
    objective_values: dict[str, float] = field(default_factory=dict)
    applied_hard_constraints: list[str] = field(default_factory=list)
    selected_soft_preferences: list[str] = field(default_factory=list)
    relaxations: list[str] = field(default_factory=list)


@dataclass
class ScheduleChangeSet:
    """A versioned diff against a prior schedule state, applied atomically."""

    base_version: str
    changes: list[dict[str, Any]] = field(default_factory=list)
    previewed: bool = False
    verified: bool = False


@dataclass
class CoveragePlan:
    """A verified resolution to one or more coverage disruptions."""

    disruption: CoverageDisruptionSpec
    change_set: ScheduleChangeSet
    verification: VerificationReport | None = None


@dataclass
class SimulationReport:
    """Full result of one simulator/optimizer run: status, candidates,
    proof strength, search statistics, and reproducibility metadata."""

    status: ScheduleStatus
    candidates: list[ScheduleCandidate] = field(default_factory=list)
    verification: VerificationReport | None = None
    solver: str = ""
    solver_version: str = ""
    input_hash: str = ""
    policy_hash: str = ""
    seed: int | None = None
    runtime_sec: float = 0.0
    search_statistics: dict[str, Any] = field(default_factory=dict)
    completeness: str = ""
    proof_strength: str = ""
    warnings: list[str] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CoverageDecisionReport:
    """Decision record for a supervisor-facing coverage action (bump,
    OT-fill, leave approval), carrying the same proof-carrying metadata
    as SimulationReport plus the specific relaxed-constraint authority."""

    status: ScheduleStatus
    plan: CoveragePlan | None = None
    relaxation_authority: dict[str, Any] | None = None
    verification: VerificationReport | None = None
    warnings: list[str] = field(default_factory=list)
