"""Phase 4 — coverage-plan preview endpoint (master plan §3 CoveragePlan).

Wraps logic.coverage_timeline.verify_schedule_candidate — a real, existing
independent verifier that had no caller yet — behind a typed, read-only
endpoint. Proves real feasible/infeasible verdicts, not a stub.
"""

from fastapi.testclient import TestClient
from nicegui import app

from gui.app import _register_api_routes


def _client() -> TestClient:
    _register_api_routes()
    return TestClient(app)


def test_preview_reports_feasible_when_coverage_holds():
    client = _client()
    body = {
        "assignments": [
            {"day": "2026-01-05", "start_time": "00:00", "end_time": "08:00"},
            {"day": "2026-01-05", "start_time": "08:00", "end_time": "16:00"},
            {"day": "2026-01-05", "start_time": "16:00", "end_time": "00:00"},
        ],
        "days": ["2026-01-05"],
        "min_247": 1,
    }
    resp = client.post("/api/v1/coverage/preview", json=body)
    assert resp.status_code == 200
    result = resp.json()
    assert result["verified"] is True
    assert result["status"] == "FEASIBLE"
    assert result["violations"] == []


def test_preview_reports_infeasible_with_real_violation_message():
    client = _client()
    body = {
        "assignments": [
            {"day": "2026-01-05", "start_time": "00:00", "end_time": "08:00"},
        ],
        "days": ["2026-01-05"],
        "min_247": 1,
    }
    resp = client.post("/api/v1/coverage/preview", json=body)
    assert resp.status_code == 200
    result = resp.json()
    assert result["verified"] is False
    assert result["status"] == "INFEASIBLE"
    assert len(result["violations"]) > 0
