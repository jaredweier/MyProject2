"""Minimal stroke icons for navigation — PIL-rendered, theme-aware."""

from __future__ import annotations

from typing import Callable, Dict, Tuple

import customtkinter as ctk
from PIL import Image, ImageDraw

from ui.assets import register_ui_image

Size = Tuple[int, int]
DrawFn = Callable[[ImageDraw.ImageDraw, int, str], None]

_cache: Dict[Tuple, ctk.CTkImage] = {}


def _stroke(draw: ImageDraw.ImageDraw, coords, fill: str, width: int = 2) -> None:
    draw.line(coords, fill=fill, width=width)


def _icon_dashboard(draw: ImageDraw.ImageDraw, s: int, color: str) -> None:
    pad = max(2, s // 6)
    gap = max(2, s // 8)
    cell = (s - 2 * pad - gap) // 2
    for row in range(2):
        for col in range(2):
            x0 = pad + col * (cell + gap)
            y0 = pad + row * (cell + gap)
            draw.rounded_rectangle((x0, y0, x0 + cell, y0 + cell), radius=2, outline=color, width=2)


def _icon_calendar(draw: ImageDraw.ImageDraw, s: int, color: str) -> None:
    pad = max(2, s // 6)
    draw.rounded_rectangle((pad, pad + 2, s - pad, s - pad), radius=3, outline=color, width=2)
    _stroke(draw, (pad, pad + s // 4, s - pad, pad + s // 4), color)
    for x in (pad + s // 5, s - pad - s // 5):
        _stroke(draw, (x, pad - 1, x, pad + 4), color, width=2)


def _icon_simulator(draw: ImageDraw.ImageDraw, s: int, color: str) -> None:
    pad = max(3, s // 5)
    mid = s // 2
    draw.polygon(
        [(pad, pad), (pad, s - pad), (s - pad, mid)],
        outline=color,
        width=2,
    )


def _icon_leave(draw: ImageDraw.ImageDraw, s: int, color: str) -> None:
    pad = max(3, s // 5)
    mid = s // 2
    _stroke(draw, (pad, mid, s - pad, mid), color)
    _stroke(draw, (pad + 2, mid - 4, pad, mid, pad + 2, mid + 4), color)
    _stroke(draw, (s - pad - 2, mid - 4, s - pad, mid, s - pad - 2, mid + 4), color)


def _icon_officers(draw: ImageDraw.ImageDraw, s: int, color: str) -> None:
    cx = s // 2
    draw.ellipse((cx - 4, 4, cx + 4, 12), outline=color, width=2)
    draw.arc((cx - 8, 12, cx + 8, s - 2), start=200, end=340, fill=color, width=2)


def _icon_payroll(draw: ImageDraw.ImageDraw, s: int, color: str) -> None:
    pad = max(3, s // 5)
    draw.rounded_rectangle((pad, pad + 2, s - pad, s - pad), radius=3, outline=color, width=2)
    cx = s // 2
    _stroke(draw, (cx, pad + 6, cx, s - pad - 3), color)
    _stroke(draw, (cx - 4, pad + 9, cx + 4, pad + 9), color)


def _icon_operations(draw: ImageDraw.ImageDraw, s: int, color: str) -> None:
    pad = max(3, s // 6)
    base = s - pad
    widths = (s // 5, s // 4, s // 6)
    x = pad
    for w in widths:
        h = pad + (s - 2 * pad) * w // max(widths)
        draw.rounded_rectangle((x, base - h, x + w, base), radius=2, outline=color, width=2)
        x += w + 3


def _icon_users(draw: ImageDraw.ImageDraw, s: int, color: str) -> None:
    draw.ellipse((s // 2 - 3, 3, s // 2 + 3, 9), outline=color, width=2)
    draw.arc((s // 2 - 6, 9, s // 2 + 6, s - 2), start=200, end=340, fill=color, width=2)
    draw.ellipse((4, 6, 10, 12), outline=color, width=2)
    draw.arc((2, 12, 12, s - 2), start=200, end=340, fill=color, width=2)


NAV_ICON_DRAWERS: Dict[str, DrawFn] = {
    "dashboard": _icon_dashboard,
    "schedules": _icon_calendar,
    "simulator": _icon_simulator,
    "leave": _icon_leave,
    "officers": _icon_officers,
    "payroll_hub": _icon_payroll,
    "operations": _icon_operations,
    "users": _icon_users,
}


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def render_icon(
    nav_key: str,
    *,
    size: int = 20,
    color: str = "#94A3B8",
) -> ctk.CTkImage | None:
    drawer = NAV_ICON_DRAWERS.get(nav_key)
    if drawer is None:
        return None
    cache_key = (nav_key, size, color)
    if cache_key in _cache:
        return _cache[cache_key]
    px = size + 8
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    drawer(draw, px, color)
    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    register_ui_image(ctk_img)
    _cache[cache_key] = ctk_img
    return ctk_img


def clear_icon_cache() -> None:
    _cache.clear()
