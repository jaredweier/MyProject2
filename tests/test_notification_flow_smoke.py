"""Notification Open→route path map smoke."""

import unittest

from scripts.notification_flow_smoke import run_notification_flow_smoke


class NotificationFlowSmokeTests(unittest.TestCase):
    def test_path_map_and_create(self):
        self.assertEqual(run_notification_flow_smoke(), 0)


if __name__ == "__main__":
    unittest.main()
