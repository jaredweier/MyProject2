"""PWA offline residual — assets and service worker coverage."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class PwaOfflineAssetsTests(unittest.TestCase):
    def test_offline_assets_exist(self):
        static = ROOT / "gui" / "static"
        for name in (
            "sw.js",
            "offline.html",
            "offline-cache.js",
            "manifest.webmanifest",
            "chronos.css",
            "chronos_logo.png",
        ):
            p = static / name
            self.assertTrue(p.is_file(), name)
            self.assertGreater(p.stat().st_size, 50, name)

    def test_sw_precaches_offline_html(self):
        sw = (ROOT / "gui" / "static" / "sw.js").read_text(encoding="utf-8")
        self.assertIn("offline.html", sw)
        self.assertIn("offline-cache.js", sw)
        self.assertRegex(sw, r"chronos-shell-v[3456]")
        self.assertIn("/my-schedule", sw)
        # Multi-page shell + offline API snapshot
        for path in ("/my-week", "/open-shifts", "/ops-desk", "/live-schedule", "/api/offline/snapshot"):
            self.assertIn(path, sw)
        oc = (ROOT / "gui" / "static" / "offline-cache.js").read_text(encoding="utf-8")
        self.assertIn("chronos_offline_pages_v2", oc)
        self.assertIn("mutation_queue", oc)

    def test_manifest_shortcuts(self):
        man = (ROOT / "gui" / "static" / "manifest.webmanifest").read_text(encoding="utf-8")
        self.assertIn("offline.html", man)
        self.assertIn("standalone", man)

    def test_theme_has_redesign_tokens(self):
        from gui.theme import GLOBAL_CSS

        self.assertIn("2026-07 residual visual redesign", GLOBAL_CSS)
        self.assertIn("offline-banner", GLOBAL_CSS)
        self.assertIn("btn-primary", GLOBAL_CSS)

    def test_shell_registers_sw_and_offline_cache(self):
        shell = (ROOT / "gui" / "shell.py").read_text(encoding="utf-8")
        self.assertIn("serviceWorker", shell)
        self.assertIn("offline-cache.js", shell)
        self.assertIn("sw.js", shell)


if __name__ == "__main__":
    unittest.main()
