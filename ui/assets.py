"""Brand image loading for Chronos Command UI."""

import os
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw

from paths import resource_path

LOGO_FILE = "logo.png"
TEAM_PHOTO_FILE = "team_photo.jpg"

# Strong references — Tk/CTk GC will drop images otherwise.
_cache: Dict[Tuple, Tuple[object, Image.Image]] = {}
_image_registry: List[object] = []
_processed_cache: Dict[Tuple, str] = {}


def register_ui_image(image) -> None:
    if image is not None and image not in _image_registry:
        _image_registry.append(image)


def reset_brand_image_cache() -> None:
    """Drop CTk/PIL references when tearing down a Tk root (headless UI tests)."""
    _cache.clear()
    _image_registry.clear()
    _processed_cache.clear()
    try:
        from ui.icons import clear_icon_cache

        clear_icon_cache()
    except ImportError:
        pass


def _cover_crop(img: Image.Image, size: Tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    resized = img.resize((int(src_w * scale), int(src_h * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def _fit_contain(img: Image.Image, size: Tuple[int, int], bg: Tuple[int, int, int]) -> Image.Image:
    target_w, target_h = size
    src_w, src_h = img.size
    scale = min(target_w / src_w, target_h / src_h)
    new_w = max(1, int(src_w * scale))
    new_h = max(1, int(src_h * scale))
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, bg)
    left = (target_w - new_w) // 2
    top = (target_h - new_h) // 2
    canvas.paste(resized, (left, top))
    return canvas


def _trim_uniform_border(img: Image.Image, tolerance: int = 28) -> Image.Image:
    rgb = img.convert("RGB")
    w, h = rgb.size
    if w < 4 or h < 4:
        return rgb
    corners = [
        rgb.getpixel((0, 0)),
        rgb.getpixel((w - 1, 0)),
        rgb.getpixel((0, h - 1)),
        rgb.getpixel((w - 1, h - 1)),
    ]
    bg = max(set(corners), key=corners.count)

    def is_bg(px: Tuple[int, int, int]) -> bool:
        return all(abs(px[i] - bg[i]) <= tolerance for i in range(3))

    left, right, top, bottom = w, 0, h, 0
    for y in range(h):
        for x in range(w):
            if not is_bg(rgb.getpixel((x, y))):
                left = min(left, x)
                right = max(right, x)
                top = min(top, y)
                bottom = max(bottom, y)
    if right <= left or bottom <= top:
        return rgb
    pad = max(2, int(min(w, h) * 0.01))
    left = max(0, left - pad)
    top = max(0, top - pad)
    right = min(w - 1, right + pad)
    bottom = min(h - 1, bottom + pad)
    return rgb.crop((left, top, right + 1, bottom + 1))


def _rounded_mask(size: Tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def _apply_rounded_border(
    img: Image.Image,
    *,
    radius: int = 10,
    border: int = 2,
    border_color: Tuple[int, int, int] = (212, 175, 55),
) -> Image.Image:
    w, h = img.size
    outer = Image.new("RGB", (w + border * 2, h + border * 2), border_color)
    mask = _rounded_mask((w, h), radius)
    rounded = Image.new("RGB", (w, h), border_color)
    rounded.paste(img, (0, 0), mask)
    outer.paste(rounded, (border, border))
    return outer


def _prepare_image(
    filename: str,
    size: Tuple[int, int],
    *,
    cover: bool = False,
    logo: bool = False,
    rounded: bool = False,
    border: bool = False,
    bg: Tuple[int, int, int] = (5, 10, 18),
) -> Optional[Image.Image]:
    path = resource_path(filename)
    if not os.path.isfile(path):
        return None
    try:
        with Image.open(path) as src:
            pil = src.convert("RGB")
            if logo:
                pil = _trim_uniform_border(pil)
                pil = _fit_contain(pil, size, bg)
            elif cover:
                pil = _cover_crop(pil, size)
            else:
                pil = pil.copy()
                pil.thumbnail(size, Image.Resampling.LANCZOS)
            if border:
                pil = _apply_rounded_border(pil, radius=10, border=3, border_color=(244, 196, 48))
            elif rounded:
                mask = _rounded_mask(pil.size, 10)
                rounded_img = Image.new("RGB", pil.size, bg)
                rounded_img.paste(pil, (0, 0), mask)
                pil = rounded_img
            return pil
    except Exception:
        return None


def _to_ctk_image(pil: Image.Image, size: Tuple[int, int], *, cache_key: Tuple = ()) -> Optional[object]:
    import customtkinter as ctk

    if pil is None:
        return None
    display_size = pil.size if pil.size[0] > 0 and pil.size[1] > 0 else size
    # In-memory PIL is the most reliable path on Windows (file-path CTkImage often fails silently).
    try:
        img = ctk.CTkImage(light_image=pil, dark_image=pil, size=display_size)
        register_ui_image(img)
        register_ui_image(pil)
        return img
    except Exception:
        pass
    if cache_key:
        try:
            import hashlib

            from paths import data_path, ensure_data_dirs

            cached = _processed_cache.get(cache_key)
            if cached and os.path.isfile(cached):
                path = cached
            else:
                ensure_data_dirs()
                cache_dir = data_path(os.path.join("logs", "img_cache"))
                os.makedirs(cache_dir, exist_ok=True)
                digest = hashlib.sha256(repr(cache_key).encode()).hexdigest()[:16]
                path = os.path.join(cache_dir, f"ui_{digest}.png")
                pil.save(path, format="PNG")
                _processed_cache[cache_key] = path
            img = ctk.CTkImage(light_image=path, dark_image=path, size=display_size)
            register_ui_image(img)
            return img
        except Exception:
            return None
    return None


def make_monogram_badge(
    size: Tuple[int, int],
    initials: str = "PD",
    *,
    bg: Tuple[int, int, int] = (31, 111, 235),
    fg: Tuple[int, int, int] = (240, 243, 247),
):
    """Always-available circular monogram when logo.png fails to paint."""
    from PIL import ImageFont

    w, h = size
    key = ("monogram", w, h, initials, bg, fg)
    cached = _cache.get(key)
    if cached is not None:
        return cached[0]
    pil = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(pil)
    pad = max(1, min(w, h) // 16)
    draw.ellipse((pad, pad, w - pad - 1, h - pad - 1), fill=bg)
    text = (initials or "PD")[:2].upper()
    font_size = max(10, int(min(w, h) * 0.38))
    try:
        font = ImageFont.truetype("segoeui.ttf", font_size)
    except Exception:
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((w - tw) / 2 - bbox[0], (h - th) / 2 - bbox[1]), text, fill=fg, font=font)
    ctk_img = _to_ctk_image(pil, size, cache_key=key)
    if ctk_img is not None:
        _cache[key] = (ctk_img, pil)
    return ctk_img


def load_logo(size: Tuple[int, int], bg: Tuple[int, int, int] = (5, 10, 18)):
    """Department shield logo — trimmed and centered on dark background."""
    import os

    key = ("logo", size[0], size[1], bg)
    if os.environ.get("SCHEDULER_UI_TEST", "").strip() != "1":
        cached = _cache.get(key)
        if cached is not None:
            return cached[0]
    pil = _prepare_image(LOGO_FILE, size, logo=True, bg=bg)
    if pil is None:
        return None
    ctk_img = _to_ctk_image(pil, size, cache_key=key)
    if ctk_img is None:
        return None
    if os.environ.get("SCHEDULER_UI_TEST", "").strip() != "1":
        _cache[key] = (ctk_img, pil)
    return ctk_img


def load_logo_safe(size: Tuple[int, int], initials: str = "PD", bg: Tuple[int, int, int] = (5, 10, 18)):
    """Logo or monogram fallback — never None for sidebar/login chrome."""
    img = load_logo(size, bg=bg)
    if img is not None:
        return img
    return make_monogram_badge(size, initials=initials)


def load_team_photo(
    size: Tuple[int, int],
    *,
    cover: bool = True,
    rounded: bool = True,
    border: bool = True,
):
    """Department team photo — cover-cropped with optional gold border frame."""
    import os

    key = ("team", size[0], size[1], cover, rounded, border)
    if os.environ.get("SCHEDULER_UI_TEST", "").strip() != "1":
        cached = _cache.get(key)
        if cached is not None:
            return cached[0]
    pil = _prepare_image(
        TEAM_PHOTO_FILE,
        size,
        cover=cover,
        rounded=rounded,
        border=border,
    )
    if pil is None:
        return None
    ctk_img = _to_ctk_image(pil, pil.size, cache_key=key)
    if ctk_img is None:
        return None
    if os.environ.get("SCHEDULER_UI_TEST", "").strip() != "1":
        _cache[key] = (ctk_img, pil)
    return ctk_img


def load_brand_image(filename: str, size: Tuple[int, int], cover: bool = False):
    """Backward-compatible loader — prefer load_logo / load_team_photo."""
    if filename == LOGO_FILE:
        return load_logo(size)
    if filename == TEAM_PHOTO_FILE:
        return load_team_photo(size, cover=cover)
    key = (filename, size[0], size[1], cover)
    cached = _cache.get(key)
    if cached is not None:
        return cached[0]
    pil = _prepare_image(filename, size, cover=cover)
    if pil is None:
        return None
    ctk_img = _to_ctk_image(pil, size, cache_key=key)
    if ctk_img is None:
        return None
    _cache[key] = (ctk_img, pil)
    return ctk_img
