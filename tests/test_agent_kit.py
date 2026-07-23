import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import agent_kit


class AgentKitTests(unittest.TestCase):
    def test_generated_kit_is_byte_bounded_and_names_active_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "latest.md"
            oversized = "Long context â†’ " * 2000
            with (
                mock.patch.object(agent_kit, "LATEST", output),
                mock.patch.object(agent_kit, "OUT_DIR", output.parent),
                mock.patch.object(agent_kit, "_run", return_value=oversized),
            ):
                code = agent_kit.run_agent_kit(task="test", quiet=True)

            self.assertEqual(code, 0)
            body = output.read_text(encoding="utf-8")
            self.assertLessEqual(len(body.encode("utf-8")), 4500)
            self.assertIn(r"C:\Users\Windows\Desktop\Chronos Command GPT", body)
            self.assertNotIn("Antigravity Chronos Command", body)


if __name__ == "__main__":
    unittest.main()
