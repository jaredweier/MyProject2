"""Department logo / photo for Chronos Command UI.

Always mirrors assets into gui/static/brand/ and can emit data-URIs so images
show even if static routes fail.
"""

from __future__ import annotations

import base64
import mimetypes
import os
import shutil
from pathlib import Path
from typing import Optional, Tuple

_BRAND_DIR = Path(__file__).resolve().parent / "static" / "brand"


def brand_dir() -> Path:
    _BRAND_DIR.mkdir(parents=True, exist_ok=True)
    return _BRAND_DIR


def _mime(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    return mime or "image/png"


def data_uri(path: str) -> Optional[str]:
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
        if not raw:
            return None
        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:{_mime(path)};base64,{b64}"
    except OSError:
        return None


def sync_brand_files() -> dict:
    """Copy current department assets into /static/brand/. Returns paths dict."""
    from photos import department_logo_path, department_photo_path

    out: dict = {"logo_path": None, "photo_path": None, "logo_url": None, "photo_url": None}
    bdir = brand_dir()

    logo = department_logo_path()
    if logo and os.path.isfile(logo):
        ext = os.path.splitext(logo)[1].lower() or ".png"
        if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            ext = ".png"
        dest = bdir / f"dept_logo{ext}"
        try:
            shutil.copy2(logo, dest)
            # Canonical name used by CSS/HTML
            canon = bdir / "dept_logo.png"
            if dest != canon:
                # Also keep as png name for stable URL if source is png/jpeg
                try:
                    shutil.copy2(logo, canon)
                except OSError:
                    pass
            out["logo_path"] = str(dest if dest.is_file() else logo)
            mtime = int(os.path.getmtime(out["logo_path"]))
            name = dest.name if dest.is_file() else "dept_logo.png"
            out["logo_url"] = f"/static/brand/{name}?v={mtime}"
            out["logo_data_uri"] = data_uri(out["logo_path"])
        except OSError:
            out["logo_path"] = logo
            out["logo_data_uri"] = data_uri(logo)

    photo = department_photo_path()
    if photo and os.path.isfile(photo):
        dest = bdir / "dept_photo.jpg"
        try:
            shutil.copy2(photo, dest)
            out["photo_path"] = str(dest)
            mtime = int(os.path.getmtime(dest))
            out["photo_url"] = f"/static/brand/dept_photo.jpg?v={mtime}"
            out["photo_data_uri"] = data_uri(str(dest))
        except OSError:
            out["photo_path"] = photo
            out["photo_data_uri"] = data_uri(photo)

    return out


def logo_display() -> Tuple[Optional[str], Optional[str]]:
    """Return (data_uri_unused, static_url) for department logo.

    data_uri is always None — embedding base64 in NiceGUI messages overflows WebSocket limits.
    """
    assets = sync_brand_files()
    return None, assets.get("logo_url")


def photo_display() -> Tuple[Optional[str], Optional[str]]:
    """Return (data_uri_unused, static_url) for department / team photo."""
    assets = sync_brand_files()
    return None, assets.get("photo_url")
