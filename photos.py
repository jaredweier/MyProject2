"""Officer photo storage and image helpers."""

import os
from typing import Dict, Optional, Tuple

from PIL import Image

from paths import data_path, ensure_data_dirs

PHOTOS_DIR = data_path("photos")
THUMB_SIZE = (120, 120)
PREVIEW_SIZE = (160, 160)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

# Department brand assets (writable copies under photos/ + project root for loaders)
DEPT_LOGO_NAME = "dept_logo.png"
DEPT_PHOTO_NAME = "dept_photo.jpg"
ROOT_LOGO = "logo.png"
ROOT_TEAM = "team_photo.jpg"

# (resolved_path, width, height, mtime) -> (CTkImage, PIL copy)
_thumbnail_cache: Dict[Tuple[str, int, int, float], Tuple[object, Image.Image]] = {}


def clear_thumbnail_cache(officer_id: Optional[int] = None) -> None:
    """Drop cached thumbnails; optionally scope to one officer's files."""
    if officer_id is None:
        _thumbnail_cache.clear()
        return
    prefix = f"officer_{officer_id}"
    stale = [key for key in _thumbnail_cache if os.path.basename(key[0]).startswith(prefix)]
    for key in stale:
        _thumbnail_cache.pop(key, None)


def _save_image_bytes(dest_path: str, data: bytes, *, max_side: int = 1600, jpeg: bool = False) -> dict:
    ensure_data_dirs()
    try:
        from io import BytesIO

        with Image.open(BytesIO(data)) as img:
            img = img.convert("RGB")
            img.thumbnail((max_side, max_side))
            if jpeg or dest_path.lower().endswith((".jpg", ".jpeg")):
                img.save(dest_path, "JPEG", quality=90)
            else:
                img.save(dest_path, "PNG")
        return {"success": True, "path": dest_path}
    except Exception as e:
        return {"success": False, "message": str(e)}


def save_department_logo_bytes(data: bytes) -> dict:
    """Save department seal/logo for Chronos Command chrome."""
    ensure_data_dirs()
    dest = os.path.join(PHOTOS_DIR, DEPT_LOGO_NAME)
    result = _save_image_bytes(dest, data, max_side=512, jpeg=False)
    if not result.get("success"):
        return result
    # Also write project-root logo.png for resource_path loaders
    try:
        from paths import app_dir

        root_logo = os.path.join(app_dir(), ROOT_LOGO)
        with Image.open(dest) as img:
            img.save(root_logo, "PNG")
        result["root_path"] = root_logo
    except Exception:
        pass
    # Mirror into NiceGUI static brand folder (sidebar mark)
    try:
        import shutil
        from pathlib import Path

        brand_dir = Path(__file__).resolve().parent / "gui" / "static" / "brand"
        brand_dir.mkdir(parents=True, exist_ok=True)
        # Prefer PNG in static; also copy root logo if present
        static_logo = brand_dir / "dept_logo.png"
        shutil.copy2(dest, static_logo)
        if result.get("root_path") and os.path.isfile(result["root_path"]):
            shutil.copy2(result["root_path"], static_logo)
        result["static_path"] = str(static_logo)
    except Exception:
        pass
    return result


def save_department_photo_bytes(data: bytes) -> dict:
    """Save department / team hero photo."""
    ensure_data_dirs()
    dest = os.path.join(PHOTOS_DIR, DEPT_PHOTO_NAME)
    result = _save_image_bytes(dest, data, max_side=1920, jpeg=True)
    if not result.get("success"):
        return result
    try:
        from paths import app_dir

        root_team = os.path.join(app_dir(), ROOT_TEAM)
        with Image.open(dest) as img:
            img.convert("RGB").save(root_team, "JPEG", quality=90)
        result["root_path"] = root_team
    except Exception:
        pass
    # Mirror for Chronos static brand (login hero)
    try:
        import shutil
        from pathlib import Path

        brand_dir = Path(__file__).resolve().parent / "gui" / "static" / "brand"
        brand_dir.mkdir(parents=True, exist_ok=True)
        static_photo = brand_dir / "dept_photo.jpg"
        shutil.copy2(dest, static_photo)
        if result.get("root_path") and os.path.isfile(result["root_path"]):
            shutil.copy2(result["root_path"], static_photo)
        result["static_path"] = str(static_photo)
    except Exception:
        pass
    return result


def save_officer_photo_bytes(officer_id: int, data: bytes) -> dict:
    """Save officer photo from upload bytes (NiceGUI / web)."""
    ensure_data_dirs()
    dest_path = os.path.join(PHOTOS_DIR, f"officer_{officer_id}.jpg")
    thumb_path = os.path.join(PHOTOS_DIR, f"officer_{officer_id}_thumb.jpg")
    try:
        from io import BytesIO

        with Image.open(BytesIO(data)) as img:
            img = img.convert("RGB")
            img.thumbnail((800, 800))
            img.save(dest_path, "JPEG", quality=90)
            thumb = img.copy()
            thumb.thumbnail(THUMB_SIZE)
            thumb.save(thumb_path, "JPEG", quality=85)
        clear_thumbnail_cache(officer_id)
        return {"success": True, "photo_path": dest_path, "thumb_path": thumb_path}
    except Exception as e:
        return {"success": False, "message": str(e)}


def department_logo_path() -> Optional[str]:
    for p in (
        os.path.join(PHOTOS_DIR, DEPT_LOGO_NAME),
        data_path(ROOT_LOGO),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ROOT_LOGO),
    ):
        if os.path.isfile(p):
            return p
    try:
        from paths import resource_path

        rp = resource_path(ROOT_LOGO)
        if os.path.isfile(rp):
            return rp
    except Exception:
        pass
    return None


def department_photo_path() -> Optional[str]:
    for p in (
        os.path.join(PHOTOS_DIR, DEPT_PHOTO_NAME),
        data_path(ROOT_TEAM),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ROOT_TEAM),
    ):
        if os.path.isfile(p):
            return p
    try:
        from paths import resource_path

        rp = resource_path(ROOT_TEAM)
        if os.path.isfile(rp):
            return rp
    except Exception:
        pass
    return None


def officer_photo_path(officer_id: int) -> Optional[str]:
    path = os.path.join(PHOTOS_DIR, f"officer_{officer_id}.jpg")
    return path if os.path.isfile(path) else None


def save_officer_photo(officer_id: int, source_path: str) -> dict:
    ensure_data_dirs()
    if not source_path or not os.path.isfile(source_path):
        return {"success": False, "message": "File not found"}

    ext = os.path.splitext(source_path)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return {"success": False, "message": f"Unsupported image type: {ext}"}

    dest_path = os.path.join(PHOTOS_DIR, f"officer_{officer_id}.jpg")
    thumb_path = os.path.join(PHOTOS_DIR, f"officer_{officer_id}_thumb.jpg")

    try:
        with Image.open(source_path) as img:
            img = img.convert("RGB")
            img.thumbnail((800, 800))
            img.save(dest_path, "JPEG", quality=90)

        with Image.open(dest_path) as img:
            thumb = img.copy()
            thumb.thumbnail(THUMB_SIZE)
            thumb.save(thumb_path, "JPEG", quality=85)

        clear_thumbnail_cache(officer_id)
        return {"success": True, "photo_path": dest_path, "thumb_path": thumb_path}
    except Exception as e:
        return {"success": False, "message": str(e)}


def remove_officer_photo(officer_id: int, photo_path: Optional[str] = None) -> None:
    clear_thumbnail_cache(officer_id)
    for path in [photo_path, os.path.join(PHOTOS_DIR, f"officer_{officer_id}_thumb.jpg")]:
        if path and os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass
    for fname in os.listdir(PHOTOS_DIR):
        if fname.startswith(f"officer_{officer_id}"):
            try:
                os.remove(os.path.join(PHOTOS_DIR, fname))
            except OSError:
                pass


def resolve_photo_path(stored_path: Optional[str]) -> Optional[str]:
    if not stored_path:
        return None
    if os.path.isfile(stored_path):
        return stored_path
    candidate = data_path(stored_path)
    if os.path.isfile(candidate):
        return candidate
    return None


def load_thumbnail(stored_path: Optional[str], size: Tuple[int, int] = PREVIEW_SIZE):
    """Return (CTkImage, path) or (None, None). Import CTkImage lazily."""
    import customtkinter as ctk

    path = resolve_photo_path(stored_path)
    if not path:
        thumb_guess = None
        if stored_path:
            base = os.path.basename(stored_path)
            if base.startswith("officer_"):
                officer_part = base.split(".")[0]
                thumb_guess = os.path.join(PHOTOS_DIR, f"{officer_part}_thumb.jpg")
        if thumb_guess and os.path.isfile(thumb_guess):
            path = thumb_guess
        else:
            return None, None

    try:
        mtime = os.path.getmtime(path)
        cache_key = (path, size[0], size[1], mtime)
        cached = _thumbnail_cache.get(cache_key)
        if cached is not None:
            return cached[0], path

        with Image.open(path) as src:
            pil = src.convert("RGB")
        pil.thumbnail(size)
        pil = pil.copy()
        ctk_img = ctk.CTkImage(light_image=pil, dark_image=pil, size=size)
        _thumbnail_cache[cache_key] = (ctk_img, pil)
        return ctk_img, path
    except Exception:
        return None, None
