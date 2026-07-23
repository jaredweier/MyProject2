"""Typed, auditable authority for relaxing one scheduling constraint."""

from datetime import datetime, timedelta
from typing import Dict, Optional

from permissions import role_has_permission

RELAXABLE_CONSTRAINTS = {
    "minimum_rest",
    "consecutive_days",
    "coverage_minimum",
    "qualification",
    "availability",
}
CONSTRAINT_ALIASES = {"no_replacement": "coverage_minimum"}


def build_relaxation_authority(
    *,
    constraint_code: str,
    actor_user_id: Optional[int],
    subject_type: str,
    subject_id: int,
    interval_start: str,
    reason: str,
    evidence: str,
) -> Dict:
    """Create and validate one constraint-specific, one-day relaxation."""
    start = datetime.fromisoformat(str(interval_start)[:10])
    payload = {
        "constraint_code": CONSTRAINT_ALIASES.get(
            str(constraint_code or "").strip().lower(),
            str(constraint_code or "").strip().lower(),
        ),
        "authority_user_id": actor_user_id,
        "subject_type": str(subject_type or "").strip(),
        "subject_id": int(subject_id),
        "interval_start": start.isoformat(),
        "interval_end": (start + timedelta(days=1)).isoformat(),
        "reason": str(reason or "").strip(),
        "expires_at": (start + timedelta(days=1)).isoformat(),
        "evidence": str(evidence or "").strip(),
    }
    error = validate_relaxation_authority(payload)
    if error:
        raise ValueError(error)
    return payload


def validate_relaxation_authority(payload: Dict) -> str:
    code = str(payload.get("constraint_code") or "").strip().lower()
    if code not in RELAXABLE_CONSTRAINTS:
        return f"Unsupported relaxed constraint: {code or 'missing'}"
    actor_id = payload.get("authority_user_id")
    if not actor_id:
        return "Supervisor authority is required for a constraint relaxation"
    from logic.users import get_user_by_id

    actor = get_user_by_id(int(actor_id))
    if not actor or not actor.get("active"):
        return "Override authority user is missing or inactive"
    if not role_has_permission(actor.get("role") or "", "requests.approve"):
        return "Override authority lacks requests.approve permission"
    for field in ("subject_type", "subject_id", "interval_start", "interval_end", "reason", "expires_at", "evidence"):
        if payload.get(field) in (None, ""):
            return f"Override {field} is required"
    if len(str(payload["reason"]).strip()) < 3:
        return "Override reason must be at least 3 characters"
    try:
        start = datetime.fromisoformat(str(payload["interval_start"]))
        end = datetime.fromisoformat(str(payload["interval_end"]))
        expires = datetime.fromisoformat(str(payload["expires_at"]))
    except ValueError:
        return "Override interval and expiration must be ISO timestamps"
    if end <= start or expires > end:
        return "Override expiration must fall within its exact interval"
    return ""
