"""Master plan §9 — typed FastAPI endpoints mounted on the existing NiceGUI
app (NiceGUI's `app` is a FastAPI instance; no new process/dependency).

First slice only: one read-only, strictly-typed endpoint. No auth/tenant
scoping yet — do not expose fields beyond scheduling-relevant, non-PII data
until that lands (master plan §9 "tenant IDs, row-level security", §12 auth).
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException

from api.schemas import OfficerOut, SimulationJobOut, SimulationJobRequest

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
