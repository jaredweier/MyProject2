"""Master plan §9 — strict Pydantic contracts for typed API endpoints.

First slice: read-only officer roster. Excludes PII (email/phone/address)
until auth/tenant scoping (master plan §9, §12) lands on this router.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict


class OfficerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    seniority_rank: int
    squad: str
    shift_start: str
    shift_end: str
    active: bool


class SimulationJobRequest(BaseModel):
    """Typed subset of `run_staffing_optimizer`'s params (master plan §9).

    Covers the common search inputs; `extra_params` is a documented escape
    hatch for the remaining ~20 advanced knobs until the full contract is
    typed — never a substitute for typing fields as they get real endpoint
    traffic.
    """

    officer_counts: Optional[List[int]] = None
    shift_length_hours: Optional[float] = None
    coverage_247: int = 0
    rotation_variations: Optional[List[str]] = None
    simulation_days: int = 28
    annual_hours_target: Optional[float] = None
    annual_hours_variance: float = 40.0
    annual_hours_hard: bool = False
    max_consecutive_work_days: int = 0
    min_rest_hours: float = 0.0
    time_budget_seconds: Optional[float] = None
    extra_params: Optional[Dict[str, Any]] = None

    def to_kwargs(self) -> Dict[str, Any]:
        kwargs = self.model_dump(exclude={"extra_params"}, exclude_none=True)
        if self.extra_params:
            kwargs.update(self.extra_params)
        return kwargs


class SimulationJobOut(BaseModel):
    id: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
