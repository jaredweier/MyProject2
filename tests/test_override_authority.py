import unittest
from unittest.mock import patch

from logic.override_authority import build_relaxation_authority, validate_relaxation_authority


class OverrideAuthorityTests(unittest.TestCase):
    @patch(
        "logic.users.get_user_by_id",
        return_value={"id": 7, "role": "Supervisor", "active": 1},
    )
    def test_typed_relaxation_carries_exact_authority_scope_and_evidence(self, _user):
        payload = build_relaxation_authority(
            constraint_code="minimum_rest",
            actor_user_id=7,
            subject_type="day_off_request",
            subject_id=42,
            interval_start="2026-07-23",
            reason="Emergency minimum-rest exception",
            evidence="Replacement has 7 hours rest; policy requires 10",
        )
        self.assertEqual(payload["constraint_code"], "minimum_rest")
        self.assertEqual(payload["authority_user_id"], 7)
        self.assertEqual(payload["subject_id"], 42)
        self.assertEqual(payload["interval_start"], "2026-07-23T00:00:00")
        self.assertEqual(payload["expires_at"], payload["interval_end"])

    @patch(
        "logic.users.get_user_by_id",
        return_value={"id": 8, "role": "Officer", "active": 1},
    )
    def test_officer_cannot_authorize_relaxation(self, _user):
        error = validate_relaxation_authority(
            {
                "constraint_code": "minimum_rest",
                "authority_user_id": 8,
                "subject_type": "day_off_request",
                "subject_id": 42,
                "interval_start": "2026-07-23T00:00:00",
                "interval_end": "2026-07-24T00:00:00",
                "expires_at": "2026-07-24T00:00:00",
                "reason": "Emergency staffing",
                "evidence": "Minimum rest shortfall",
            }
        )
        self.assertIn("lacks", error)

    def test_missing_actor_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "authority"):
            build_relaxation_authority(
                constraint_code="minimum_rest",
                actor_user_id=None,
                subject_type="day_off_request",
                subject_id=42,
                interval_start="2026-07-23",
                reason="Emergency staffing",
                evidence="Minimum rest shortfall",
            )
