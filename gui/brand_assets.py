"""Brand asset sync for Chronos Command UI.

Mirrors runtime uploads into gui/static/brand/ for stable URLs.
Does not embed base64 (NiceGUI WebSocket size limits).
"""

from __future__ import annotations

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
        import base64

        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:{_mime(path)};base64,{b64}"
    except OSError:
        return None


def _mirror(src: Optional[str], dest_name: str) -> dict:
    out: dict = {"path": None, "url": None}
    if not src or not os.path.isfile(src):
        return out
    bdir = brand_dir()
    dest = bdir / dest_name
    try:
        shutil.copy2(src, dest)
        out["path"] = str(dest)
        mtime = int(os.path.getmtime(dest))
        out["url"] = f"/static/brand/{dest_name}?v={mtime}"
    except OSError:
        out["path"] = src
    return out


def sync_brand_files() -> dict:
    """Copy current brand assets into /static/brand/. Returns paths/urls dict."""
    from photos import (
        CHRONOS_LOGO_NAME,
        DEPT_LOGO_NAME,
        DEPT_PHOTO_NAME,
        chronos_logo_path,
        department_logo_path,
        department_photo_path,
    )

    out: dict = {
        "chronos_path": None,
        "chronos_url": None,
        "logo_path": None,
        "logo_url": None,
        "photo_path": None,
        "photo_url": None,
    }

    c = _mirror(chronos_logo_path(), CHRONOS_LOGO_NAME)
    out["chronos_path"] = c.get("path")
    out["chronos_url"] = c.get("url")

    logo = _mirror(department_logo_path(), DEPT_LOGO_NAME)
    out["logo_path"] = logo.get("path")
    out["logo_url"] = logo.get("url")

    photo = _mirror(department_photo_path(), DEPT_PHOTO_NAME)
    out["photo_path"] = photo.get("path")
    out["photo_url"] = photo.get("url")

    return out


def logo_display() -> Tuple[Optional[str], Optional[str]]:
    """Return (None, static_url) for department logo."""
    assets = sync_brand_files()
    return None, assets.get("logo_url")


def photo_display() -> Tuple[Optional[str], Optional[str]]:
    """Return (None, static_url) for department photo."""
    assets = sync_brand_files()
    return None, assets.get("photo_url")


def chronos_display() -> Tuple[Optional[str], Optional[str]]:
    """Return (None, static_url) for Chronos product logo."""
    assets = sync_brand_files()
    return None, assets.get("chronos_url")
