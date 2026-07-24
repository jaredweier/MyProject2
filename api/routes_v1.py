"""Master plan §9 — typed FastAPI endpoints mounted on the existing NiceGUI
app (NiceGUI's `app` is a FastAPI instance; no new process/dependency).

First slice only: one read-only, strictly-typed endpoint. No auth/tenant
scoping yet — do not expose fields beyond scheduling-relevant, non-PII data
until that lands (master plan §9 "tenant IDs, row-level security", §12 auth).
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter

from api.schemas import OfficerOut

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/officers", response_model=List[OfficerOut])
def list_officers() -> List[OfficerOut]:
    from logic.officers import get_officers_by_seniority

    return [OfficerOut.model_validate(row) for row in get_officers_by_seniority()]
