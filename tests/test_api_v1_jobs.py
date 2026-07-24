"""Phase 4 — typed simulation-job endpoints (POST + GET, master plan §9)."""

import time

from fastapi.testclient import TestClient
from nicegui import app

from gui.app import _register_api_routes
from tests.helpers import test_database


def _client() -> TestClient:
    _register_api_routes()
    return TestClient(app)


def test_create_and_poll_simulation_job(monkeypatch):
    def _fake_optimizer(**kwargs):
        return {"status": "feasible", "coverage_247": kwargs.get("coverage_247")}

    monkeypatch.setattr("logic.scheduling_sim.run_staffing_optimizer", _fake_optimizer)

    with test_database():
        client = _client()
        create_resp = client.post("/api/v1/jobs/simulations", json={"coverage_247": 2})
        assert create_resp.status_code == 202
        body = create_resp.json()
        assert body["status"] in ("queued", "running", "completed")
        job_id = body["id"]

        for _ in range(50):
            poll = client.get(f"/api/v1/jobs/simulations/{job_id}")
            assert poll.status_code == 200
            if poll.json()["status"] == "completed":
                break
            time.sleep(0.05)

        final = poll.json()
        assert final["status"] == "completed"
        assert final["result"] == {"status": "feasible", "coverage_247": 2}


def test_get_unknown_job_returns_404():
    with test_database():
        client = _client()
        resp = client.get("/api/v1/jobs/simulations/does-not-exist")
        assert resp.status_code == 404
