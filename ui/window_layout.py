"""Main window placement — maximize and focus after login."""

import sys

import customtkinter as ctk

_applied_for: set[int] = set()


def apply_main_window_layout(root: ctk.CTk) -> None:
    """Maximize once at startup. Re-entrant Map/configure handlers must not call this."""
    key = id(root)
    if key in _applied_for:
        return
    _applied_for.add(key)
    try:
        root.update_idletasks()
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        if sys.platform == "win32":
            root.state("normal")
            root.geometry(f"{screen_w}x{screen_h}+0+0")
            root.update_idletasks()
            root.state("zoomed")
        else:
            try:
                root.attributes("-zoomed", True)
            except Exception:
                root.geometry(f"{screen_w}x{screen_h}+0+0")
        root.lift()
        root.focus_force()
        root.attributes("-topmost", True)
        root.after(250, lambda: root.attributes("-topmost", False))
    except Exception:
        _applied_for.discard(key)


def reset_main_window_layout_guard(root: ctk.CTk) -> None:
    """Allow maximize again after sign-out (new shell session)."""
    _applied_for.discard(id(root))
