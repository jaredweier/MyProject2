"""Phase 4 — durable simulation-job registry (logic/optimizer_jobs.py)."""

import time

from logic import optimizer_jobs
from tests.helpers import test_database


def test_create_job_persists_and_completes(monkeypatch):
    def _fake_optimizer(**kwargs):
        assert kwargs["coverage_247"] == 1
        return {"status": "feasible", "echo": kwargs}

    monkeypatch.setattr("logic.scheduling_sim.run_staffing_optimizer", _fake_optimizer)

    with test_database():
        job_id = optimizer_jobs.create_job({"coverage_247": 1})
        job = optimizer_jobs.get_job(job_id)
        assert job["status"] in ("queued", "running", "completed")

        for _ in range(50):
            job = optimizer_jobs.get_job(job_id)
            if job["status"] == "completed":
                break
            time.sleep(0.05)

        assert job["status"] == "completed"
        assert job["result"]["status"] == "feasible"
        assert job["error"] is None


def test_job_failure_is_recorded_not_swallowed(monkeypatch):
    def _boom(**kwargs):
        raise ValueError("synthetic failure")

    monkeypatch.setattr("logic.scheduling_sim.run_staffing_optimizer", _boom)

    with test_database():
        job_id = optimizer_jobs.create_job({})
        job = None
        for _ in range(50):
            job = optimizer_jobs.get_job(job_id)
            if job["status"] == "failed":
                break
            time.sleep(0.05)

        assert job["status"] == "failed"
        assert "synthetic failure" in job["error"]


def test_get_job_returns_none_for_unknown_id():
    with test_database():
        assert optimizer_jobs.get_job("does-not-exist") is None
