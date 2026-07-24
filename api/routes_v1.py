"""Master plan §9 — typed FastAPI endpoints mounted on the existing NiceGUI
app (NiceGUI's `app` is a FastAPI instance; no new process/dependency).

First slice only: one read-only, strictly-typed endpoint. No auth/tenant
scoping yet — do not expose fields beyond scheduling-relevant, non-PII data
until that lands (master plan §9 "tenant IDs, row-level security", §12 auth).
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException

from api.schemas import (
    CoveragePlanPreviewOut,
    CoveragePlanPreviewRequest,
    OfficerOut,
    ShiftSwapPreviewOut,
    SimulationJobOut,
    SimulationJobRequest,
)

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/officers", response_model=List[OfficerOut])
def list_officers() -> List[OfficerOut]:
    from logic.officers import get_officers_by_seniority

    return [OfficerOut.model_validate(row) for row in get_officers_by_seniority()]


@router.post("/jobs/simulations", response_model=SimulationJobOut, status_code=202)
def create_simulation_job(request: SimulationJobRequest) -> SimulationJobOut:
    from logic.optimizer_jobs import create_job

    job_id = create_job(request.to_kwargs())
    return SimulationJobOut(id=job_id, status="queued")


@router.get("/jobs/simulations/{job_id}", response_model=SimulationJobOut)
def get_simulation_job(job_id: str) -> SimulationJobOut:
    from logic.optimizer_jobs import get_job

    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return SimulationJobOut(id=job["id"], status=job["status"], result=job["result"], error=job["error"])


@router.post("/jobs/simulations/{job_id}/cancel", response_model=SimulationJobOut)
def cancel_simulation_job(job_id: str) -> SimulationJobOut:
    from logic.optimizer_jobs import cancel_job

    job = cancel_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return SimulationJobOut(id=job["id"], status=job["status"], result=job["result"], error=job["error"])


@router.post("/coverage/preview", response_model=CoveragePlanPreviewOut)
def preview_coverage_plan(request: CoveragePlanPreviewRequest) -> CoveragePlanPreviewOut:
    from logic.coverage_timeline import CoverageWindow, verify_schedule_candidate

    assignments = [(a.day, a.start_time, a.end_time) for a in request.assignments]
    windows = [CoverageWindow(**w.model_dump()) for w in (request.windows or [])]
    report = verify_schedule_candidate(
        assignments,
        request.days,
        min_247=request.min_247,
        windows=windows,
    )
    return CoveragePlanPreviewOut(
        verified=report.verified,
        status=report.status.value,
        violations=report.violations,
        checked_constraints=report.checked_constraints,
        notes=report.notes,
    )


@router.get("/swaps/preview", response_model=ShiftSwapPreviewOut)
def preview_shift_swap(officer1_id: int, officer2_id: int, swap_date: str) -> ShiftSwapPreviewOut:
    from logic.requests import validate_swap_feasibility

    result = validate_swap_feasibility(officer1_id, officer2_id, swap_date)
    return ShiftSwapPreviewOut(
        success=result.success,
        officer1_id=result.officer1_id,
        officer2_id=result.officer2_id,
        swap_date=result.swap_date,
        message=result.message,
        requires_manual=result.requires_manual,
        reason=result.reason,
        can_proceed=result.can_proceed,
    )
