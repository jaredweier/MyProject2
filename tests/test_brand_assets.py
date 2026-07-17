"""Agency-neutral brand storage — no shipped root logo/team defaults."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

from PIL import Image


class BrandAssetTests(unittest.TestCase):
    def test_paths_none_when_missing(self):
        import photos

        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(photos, "PHOTOS_DIR", td):
                self.assertIsNone(photos.chronos_logo_path())
                self.assertIsNone(photos.department_logo_path())
                self.assertIsNone(photos.department_photo_path())

    def test_chronos_and_dept_save_clear_roundtrip(self):
        import photos

        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(photos, "PHOTOS_DIR", td):
                # Tiny PNG
                buf = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                try:
                    img = Image.new("RGB", (32, 32), "#1E5AA8")
                    img.save(buf.name, "PNG")
                    with open(buf.name, "rb") as fh:
                        data = fh.read()
                finally:
                    buf.close()
                    try:
                        os.unlink(buf.name)
                    except OSError:
                        pass

                r = photos.save_chronos_logo_bytes(data)
                self.assertTrue(r.get("success"), r)
                self.assertTrue(os.path.isfile(photos.chronos_logo_path() or ""))

                r2 = photos.save_department_logo_bytes(data)
                self.assertTrue(r2.get("success"), r2)
                self.assertTrue(os.path.isfile(photos.department_logo_path() or ""))

                # JPEG path for photo
                buf2 = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                try:
                    Image.new("RGB", (64, 40), "#132A45").save(buf2.name, "JPEG")
                    with open(buf2.name, "rb") as fh:
                        jdata = fh.read()
                finally:
                    buf2.close()
                    try:
                        os.unlink(buf2.name)
                    except OSError:
                        pass
                r3 = photos.save_department_photo_bytes(jdata)
                self.assertTrue(r3.get("success"), r3)
                self.assertTrue(os.path.isfile(photos.department_photo_path() or ""))

                photos.clear_chronos_logo()
                photos.clear_department_logo()
                photos.clear_department_photo()
                self.assertIsNone(photos.chronos_logo_path())
                self.assertIsNone(photos.department_logo_path())
                self.assertIsNone(photos.department_photo_path())

    def test_no_root_fallback_to_project_logo(self):
        """Even if root logo.png exists, department_logo_path must not use it."""
        import photos

        with tempfile.TemporaryDirectory() as td:
            fake_root = os.path.join(td, "logo.png")
            Image.new("RGB", (8, 8), "red").save(fake_root, "PNG")
            with mock.patch.object(photos, "PHOTOS_DIR", os.path.join(td, "photos")):
                os.makedirs(photos.PHOTOS_DIR, exist_ok=True)
                # Root file exists but is not under PHOTOS_DIR
                self.assertIsNone(photos.department_logo_path())
                self.assertIsNone(photos.chronos_logo_path())


if __name__ == "__main__":
    unittest.main()
