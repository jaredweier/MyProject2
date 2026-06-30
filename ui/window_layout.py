"""Main window placement — maximize and focus on startup."""

import sys

import customtkinter as ctk


def apply_main_window_layout(root: ctk.CTk) -> None:
    """Center on screen, maximize, and bring the scheduler to the front."""
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
        pass
