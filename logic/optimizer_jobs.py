"""Phase 4 (master plan §9) — durable simulation-job registry.

`run_staffing_optimizer` (logic/scheduling_sim.py) runs synchronously today;
this module gives it an ID, a persisted row, and a background thread so the
typed API can hand back a job immediately and poll for status/result rather
than blocking an HTTP request on a potentially long CP-SAT search.

Rows persist in the existing SQLite `optimizer_jobs` table (no new DB engine
— see master plan §9's eventual PostgreSQL move, not done yet). This is a
single-process job runner: it does not survive a process restart mid-run
(a running job found orphaned on startup is not resumed — out of scope for
this slice, matches the "not durable across restarts yet" caveat).
"""

from __future__ import annotations

import json
import threading
import uuid
from typing import Any, Dict, Optional

from database import connection

_lock = threading.Lock()

# In-process only (matches the module's "single-process, not durable across
# restart" scope) — one cancellation Event per in-flight job, read by
# run_staffing_optimizer's own cancel_check plumbing (master plan §4 perf
# target: "cancellation observed within one second").
_cancel_events: Dict[str, threading.Event] = {}


def create_job(params: Dict[str, Any]) -> str:
    """Insert a queued job row and start it in a background thread. Returns the job id."""
    job_id = uuid.uuid4().hex
    with _lock, connection() as conn:
        conn.execute(
            "INSERT INTO optimizer_jobs (id, status, params_json) VALUES (?, 'queued', ?)",
            (job_id, json.dumps(params)),
        )
        conn.commit()

    cancel_event = threading.Event()
    with _lock:
        _cancel_events[job_id] = cancel_event

    thread = threading.Thread(target=_run_job, args=(job_id, params, cancel_event), daemon=True)
    thread.start()
    return job_id


def cancel_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Request cancellation. No-op (but not an error) if the job is already
    finished or unknown — returns the job's current state either way, or
    None if the job id doesn't exist."""
    with _lock:
        event = _cancel_events.get(job_id)
    if event is not None:
        event.set()
    return get_job(job_id)


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _lock, connection() as conn:
        cursor = conn.execute(
            "SELECT id, status, params_json, result_json, error_text, created_at, updated_at "
            "FROM optimizer_jobs WHERE id = ?",
            (job_id,),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "status": row["status"],
        "params": json.loads(row["params_json"]),
        "result": json.loads(row["result_json"]) if row["result_json"] else None,
        "error": row["error_text"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _set_status(job_id: str, status: str, *, result: Optional[Dict] = None, error: Optional[str] = None) -> None:
    with _lock, connection() as conn:
        conn.execute(
            "UPDATE optimizer_jobs SET status = ?, result_json = ?, error_text = ?, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, json.dumps(result) if result is not None else None, error, job_id),
        )
        conn.commit()


def _run_job(job_id: str, params: Dict[str, Any], cancel_event: threading.Event) -> None:
    from logic.scheduling_sim import run_staffing_optimizer

    _set_status(job_id, "running")
    try:
        result = run_staffing_optimizer(cancel_check=cancel_event.is_set, **params)
        final_status = "cancelled" if result.get("cancelled") else "completed"
        _set_status(job_id, final_status, result=result)
    except Exception as exc:  # never let a job crash the thread silently unrecorded
        _set_status(job_id, "failed", error=str(exc))
    finally:
        with _lock:
            _cancel_events.pop(job_id, None)
