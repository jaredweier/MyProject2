"""Master plan §9 — strict Pydantic contracts for typed API endpoints.

First slice: read-only officer roster. Excludes PII (email/phone/address)
until auth/tenant scoping (master plan §9, §12) lands on this router.
"""

from __future__ import annotations

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
