"""Phase 4 — shift-swap feasibility preview endpoint (read-only)."""

from fastapi.testclient import TestClient
from nicegui import app

from gui.app import _register_api_routes
from tests.helpers import test_database


def _client() -> TestClient:
    _register_api_routes()
    return TestClient(app)


def test_preview_rejects_swap_with_self():
    with test_database():
        client = _client()
        resp = client.get(
            "/api/v1/swaps/preview", params={"officer1_id": 1, "officer2_id": 1, "swap_date": "2026-07-01"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert "yourself" in body["message"].lower()


def test_preview_rejects_unknown_officer():
    with test_database():
        client = _client()
        resp = client.get(
            "/api/v1/swaps/preview", params={"officer1_id": 999999, "officer2_id": 999998, "swap_date": "2026-07-01"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
