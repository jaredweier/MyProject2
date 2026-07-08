"""Display scaling and window placement (DPI, centering, login vs main layout)."""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import customtkinter as ctk

_DPI_AWARE = False

# Target physical pixel size for the login window (after DPI scaling).
_LOGIN_WIDTH = 1180
_LOGIN_HEIGHT = 740
_LOGIN_MIN_WIDTH = 1000
_LOGIN_MIN_HEIGHT = 680


def enable_windows_dpi_awareness() -> None:
    """Call before creating any Tk/CTk root (Win10/11, any display scale)."""
    global _DPI_AWARE
    if sys.platform != "win32":
        return
    try:
        import ctypes

        user32 = ctypes.windll.user32
        if hasattr(user32, "SetProcessDpiAwarenessContext"):
            if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
                _DPI_AWARE = True
                return
    except Exception:
        pass
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        _DPI_AWARE = True
    except Exception:
        try:
            import ctypes

            ctypes.windll.user32.SetProcessDPIAware()
            _DPI_AWARE = True
        except Exception:
            pass


def _env_ui_scale() -> float | None:
    raw = os.environ.get("SCHEDULER_UI_SCALE", "").strip()
    if not raw:
        return None
    try:
        return max(0.75, min(1.5, float(raw)))
    except ValueError:
        return None


def configure_ctk_scaling() -> float:
    """Apply CustomTkinter scaling. Returns effective widget scale."""
    import customtkinter as ctk

    override = _env_ui_scale()
    if override is not None:
        ctk.set_widget_scaling(override)
        ctk.set_window_scaling(override)
        return override

    ctk.set_widget_scaling(1.0)
    ctk.set_window_scaling(1.0)
    return 1.0


def _system_dpi_scale() -> float:
    """Display scale factor (1.0 = 100%, 1.25 = 125%, etc.)."""
    if sys.platform != "win32":
        return 1.0
    try:
        import ctypes

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        hdc = user32.GetDC(0)
        dpi = gdi32.GetDeviceCaps(hdc, 88)
        user32.ReleaseDC(0, hdc)
        return max(1.0, dpi / 96.0)
    except Exception:
        return 1.0


def _geometry_scale(root: "ctk.CTk") -> float:
    """
    Tk geometry() uses logical units; winfo_width/height are physical pixels.
    At 125% DPI, geometry 944x592 renders as 1180x740.
    """
    try:
        root.update_idletasks()
        size_part = root.geometry().split("+", 1)[0]
        gw_str, gh_str = size_part.split("x", 1)
        gw, gh = int(gw_str), int(gh_str)
        aw, ah = int(root.winfo_width()), int(root.winfo_height())
        if gw > 0 and aw > 50:
            return aw / gw
        if gh > 0 and ah > 50:
            return ah / gh
    except Exception:
        pass
    return _system_dpi_scale()


def _to_geometry_units(pixels: int, scale: float) -> int:
    return max(1, int(round(pixels / max(1.0, scale))))


def _root_hwnd(root: "ctk.CTk") -> int:
    import ctypes

    wid = int(root.winfo_id())
    return int(ctypes.windll.user32.GetAncestor(wid, 2))


def _monitor_work_area(hwnd: int) -> tuple[int, int, int, int]:
    """Return (left, top, width, height) for the monitor work area containing hwnd."""
    import ctypes
    from ctypes import wintypes

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    user32 = ctypes.windll.user32
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    monitor = user32.MonitorFromWindow(hwnd, 2)
    if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(mi)):
        work = mi.rcWork
        return (
            int(work.left),
            int(work.top),
            max(640, int(work.right - work.left)),
            max(480, int(work.bottom - work.top)),
        )

    rect = wintypes.RECT()
    if user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0):
        return (
            int(rect.left),
            int(rect.top),
            max(640, int(rect.right - rect.left)),
            max(480, int(rect.bottom - rect.top)),
        )
    return 0, 0, 1920, 1080


def _window_rect(hwnd: int) -> tuple[int, int, int, int]:
    import ctypes
    from ctypes import wintypes

    rect = wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)


def _window_is_maximized(root: "ctk.CTk") -> bool:
    try:
        if root.state() == "zoomed":
            return True
    except Exception:
        pass
    if sys.platform == "win32":
        try:
            import ctypes

            hwnd = _root_hwnd(root)
            return bool(ctypes.windll.user32.IsZoomed(hwnd))
        except Exception:
            pass
    return False


def clear_login_window_layout(root: "ctk.CTk") -> None:
    """Stop login-only centering handlers before maximizing the main shell."""
    setattr(root, "_login_centering_active", False)
    bind_id = getattr(root, "_login_configure_bind_id", None)
    if bind_id is not None:
        try:
            root.unbind("<Configure>", bind_id)
        except Exception:
            pass
    map_id = getattr(root, "_login_map_bind_id", None)
    if map_id is not None:
        try:
            root.unbind("<Map>", map_id)
        except Exception:
            pass
    for attr in ("_login_configure_bind_id", "_login_map_bind_id", "_login_center_bound"):
        if hasattr(root, attr):
            try:
                delattr(root, attr)
            except Exception:
                pass


def center_window_win32(root: "ctk.CTk") -> None:
    """Center using actual on-screen pixel dimensions (correct at any DPI)."""
    if not getattr(root, "_login_centering_active", False):
        return
    if _window_is_maximized(root):
        return
    if sys.platform != "win32":
        return
    try:
        import ctypes

        root.update_idletasks()
        root.update()
        hwnd = _root_hwnd(root)
        left, top, right, bottom = _window_rect(hwnd)
        w = right - left
        h = bottom - top
        if w < 50 or h < 50:
            return

        area_left, area_top, area_w, area_h = _monitor_work_area(hwnd)
        x = area_left + max(0, (area_w - w) // 2)
        y = area_top + max(0, (area_h - h) // 2)
        # SWP_NOSIZE | SWP_NOZORDER
        ctypes.windll.user32.SetWindowPos(hwnd, 0, x, y, 0, 0, 0x0001 | 0x0004)
        root.update_idletasks()
    except Exception:
        pass


def set_window_size_pixels(root: "ctk.CTk", width_px: int, height_px: int) -> None:
    """Set outer window size in physical pixels (handles DPI geometry scaling)."""
    try:
        scale = _geometry_scale(root)
        if scale <= 1.01:
            scale = _system_dpi_scale()
        gw = _to_geometry_units(width_px, scale)
        gh = _to_geometry_units(height_px, scale)
        root.geometry(f"{gw}x{gh}")
        root.update_idletasks()
        root.update()
    except Exception:
        pass


def center_window(root: "ctk.CTk", width_px: int, height_px: int) -> None:
    """Size in physical pixels, then center with Win32 using actual rendered bounds."""
    try:
        hwnd = _root_hwnd(root) if sys.platform == "win32" else 0
        if hwnd:
            area_left, area_top, area_w, area_h = _monitor_work_area(hwnd)
        else:
            root.update_idletasks()
            area_w = max(800, int(root.winfo_screenwidth()))
            area_h = max(600, int(root.winfo_screenheight()))

        width_px = max(400, min(width_px, area_w - 24))
        height_px = max(400, min(height_px, area_h - 24))
        set_window_size_pixels(root, width_px, height_px)
        center_window_win32(root)
    except Exception:
        pass


def apply_login_window_layout(root: "ctk.CTk") -> None:
    """Centered login window sized to fit the full login layout."""
    if not getattr(root, "_login_centering_active", False):
        return
    try:
        root.state("normal")
    except Exception:
        pass

    try:
        scale = max(_system_dpi_scale(), _geometry_scale(root))
        hwnd = _root_hwnd(root) if sys.platform == "win32" else 0
        if hwnd:
            _, _, area_w, area_h = _monitor_work_area(hwnd)
        else:
            root.update_idletasks()
            area_w = max(800, int(root.winfo_screenwidth()))
            area_h = max(600, int(root.winfo_screenheight()))

        width_px = min(_LOGIN_WIDTH, area_w - 24)
        height_px = min(_LOGIN_HEIGHT, area_h - 24)
        width_px = max(_LOGIN_MIN_WIDTH, width_px)
        height_px = max(_LOGIN_MIN_HEIGHT, min(height_px, area_h - 24))

        center_window(root, width_px, height_px)

        min_gw = _to_geometry_units(min(_LOGIN_MIN_WIDTH, width_px), scale)
        min_gh = _to_geometry_units(min(_LOGIN_MIN_HEIGHT, height_px), scale)
        root.minsize(min_gw, min_gh)
        root.update_idletasks()
        center_window_win32(root)
    except Exception:
        pass


def _schedule_login_centering(root: "ctk.CTk") -> None:
    """Re-center after CTk/Tk finish layout (they can override the first geometry pass)."""
    root._login_centering_active = True

    def _on_configure(_event=None) -> None:
        if getattr(root, "_login_centering_active", False):
            root.after_idle(center_window_win32, root)

    def _on_map(_event=None) -> None:
        if getattr(root, "_login_centering_active", False):
            root.after_idle(apply_login_window_layout, root)

    try:
        if not getattr(root, "_login_center_bound", False):
            root._login_center_bound = True
            root._login_configure_bind_id = root.bind("<Configure>", _on_configure, add="+")
            root._login_map_bind_id = root.bind("<Map>", _on_map, add="+")
        for delay in (0, 50, 150, 350):
            root.after(delay, center_window_win32, root)
    except Exception:
        pass


def show_login_window(root: "ctk.CTk") -> None:
    """Apply login size/position and keep it centered on screen."""
    root._login_centering_active = True
    apply_login_window_layout(root)
    _schedule_login_centering(root)
    try:
        root.lift()
        root.after(100, lambda: root.focus_force())
    except Exception:
        pass


def apply_main_window_layout(root: "ctk.CTk") -> None:
    """Maximize once at startup. Re-entrant handlers must not call this repeatedly."""
    from ui.window_layout import apply_main_window_layout as _maximize

    _maximize(root)
