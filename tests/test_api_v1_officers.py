"""Phase 4 first slice — typed FastAPI endpoint (master plan §9).

Proves the schema is strict (extra/PII fields never leak) and the endpoint
returns real roster data via the existing officers read path, not a mock.
"""

from fastapi.testclient import TestClient
from nicegui import app

from gui.app import _register_api_routes


def _client() -> TestClient:
    _register_api_routes()
    return TestClient(app)


def test_list_officers_returns_typed_roster(monkeypatch):
    def _fake_officers():
        return [
            {
                "id": 1,
                "name": "Test Officer",
                "seniority_rank": 1,
                "squad": "A",
                "shift_start": "07:00",
                "shift_end": "15:00",
                "active": True,
                "email": "should-not-appear@example.com",
                "phone": "555-0100",
            }
        ]

    monkeypatch.setattr("logic.officers.get_officers_by_seniority", _fake_officers)

    response = _client().get("/api/v1/officers")
    assert response.status_code == 200
    body = response.json()
    assert body == [
        {
            "id": 1,
            "name": "Test Officer",
            "seniority_rank": 1,
            "squad": "A",
            "shift_start": "07:00",
            "shift_end": "15:00",
            "active": True,
        }
    ]
    assert "email" not in body[0]
    assert "phone" not in body[0]
