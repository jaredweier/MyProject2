"""Chronos Command — rebuilt UI (grid shell + modular pages)."""

from __future__ import annotations

import logging
import sys
from datetime import date
from typing import Optional

import customtkinter as ctk

from database import backup_database
from logic import get_cycle_day, get_squad_on_duty, get_unread_notification_count, log_audit_action
from ui.assets import load_logo_safe
from ui.branding import get_department_branding
from ui.display import configure_ctk_scaling
from ui.pages import PAGE_CLASSES
from ui.session import SessionMixin
from ui.theme import (
    CONTENT_PAD,
    DODGEVILLE_ACCENT,
    NAV_HUBS,
    NAV_ITEMS,
    NAV_PERMISSIONS,
    OFFICER_PAGE_SUBTITLES,
    PAGE_SUBTITLES,
    SIDEBAR_NAV,
    SIDEBAR_WIDTH,
    TOPBAR_HEIGHT,
    UI_ACCENT_GLOW,
    UI_BG,
    UI_BORDER,
    UI_BORDER_GLOW,
    UI_SIDEBAR,
    UI_SURFACE,
    UI_SURFACE_LIGHT,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    font,
    hub_for_page,
    micro_label,
    page_title,
    resolve_nav_target,
    tactical_stripe,
)
from ui.widgets import NavButton, NavSectionLabel, SearchBar, SecondaryButton, SubNavBar, ToastHost
from validators import format_date

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
configure_ctk_scaling()


class DodgevilleSchedulerApp(SessionMixin):
    """Single app object: session + pure-grid shell + page controllers."""

    def __init__(self):
        self.root = ctk.CTk()
        try:
            from config import APP_NAME

            self.root.title(APP_NAME)
        except Exception:
            self.root.title("Chronos Command")
        self.root.configure(fg_color=UI_BG)

        self.current_user = None
        self.selected_officer_id = None
        self.current_page = None
        self.shell = None
        self.nav_buttons = {}
        self.stat_cards = {}
        self.pages = {}
        self.page_controllers = {}
        self._brand_images = []
        self._gantt_cycle_start: Optional[date] = None
        self._gantt_cells = {}
        self._request_row_widgets = {}
        self._swap_row_widgets = {}
        self._schedule_mode = "base"
        self._request_view = "queue"
        self._payroll_period_start = None
        self._timecard_period_start = None

        self._bootstrap_session()

    # ------------------------------------------------------------------ shell
    def _build_shell(self) -> None:
        # Clear root
        for w in list(self.root.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass

        self.shell = ctk.CTkFrame(self.root, fg_color=UI_BG, corner_radius=0)
        self.shell.pack(fill="both", expand=True)
        self.shell.grid_columnconfigure(1, weight=1)
        self.shell.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()
        self._mount_pages()
        self._finalize_login_shell()

    def _sidebar_entry_visible(self, key: str) -> bool:
        if key in NAV_HUBS:
            for page_key in NAV_HUBS[key]["pages"]:
                perm = NAV_PERMISSIONS.get(page_key)
                if not perm:
                    return True
                perms = perm if isinstance(perm, tuple) else (perm,)
                if any(self.can(p) for p in perms):
                    return True
            return False
        perm = NAV_PERMISSIONS.get(key)
        if perm:
            perms = perm if isinstance(perm, tuple) else (perm,)
            return any(self.can(p) for p in perms)
        return True

    def _build_sidebar(self) -> None:
        wrap = ctk.CTkFrame(self.shell, width=SIDEBAR_WIDTH + 3, fg_color=UI_SIDEBAR, corner_radius=0)
        wrap.grid(row=0, column=0, sticky="nsew")
        wrap.grid_propagate(False)
        wrap.grid_columnconfigure(1, weight=1)
        wrap.grid_rowconfigure(0, weight=1)
        ctk.CTkFrame(wrap, width=3, fg_color=UI_ACCENT_GLOW, corner_radius=0).grid(row=0, column=0, sticky="ns")
        sidebar = ctk.CTkFrame(wrap, fg_color=UI_SIDEBAR, corner_radius=0)
        sidebar.grid(row=0, column=1, sticky="nsew")

        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=14, pady=(16, 8))
        branding = get_department_branding()
        micro_label(brand, "Tactical ops").pack(anchor="w", pady=(0, 6))
        row = ctk.CTkFrame(brand, fg_color="transparent")
        row.pack(fill="x")
        logo = load_logo_safe((36, 36), initials="PD")
        if logo:
            self._remember_brand_image(logo)
            ctk.CTkLabel(row, text="", image=logo).pack(side="left", padx=(0, 10))
        text = ctk.CTkFrame(row, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True)
        short = branding["name"].replace(" Police Department", " PD")
        ctk.CTkLabel(text, text=short, font=font("subheading"), text_color=UI_TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(text, text="Duty command center", font=font("small"), text_color=UI_TEXT_MUTED).pack(anchor="w")
        tactical_stripe(sidebar, pack_kwargs={"padx": 14, "pady": (8, 4)})

        # Footer first so nav can expand between brand and actions
        footer = ctk.CTkFrame(sidebar, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=14, pady=(8, 14))
        self.sidebar_date = ctk.CTkLabel(footer, text="", font=font("mono"), text_color=UI_TEXT_MUTED, justify="left")
        self.sidebar_date.pack(anchor="w", pady=(0, 10))
        ctk.CTkFrame(footer, fg_color=UI_BORDER, height=1).pack(fill="x", pady=(0, 10))
        SecondaryButton(footer, text="Refresh all", height=34, command=self.refresh_all).pack(fill="x", pady=(0, 6))
        if self.can("database.backup"):
            SecondaryButton(footer, text="Backup database", height=34, command=self.backup_database).pack(
                fill="x", pady=(0, 6)
            )
        ctk.CTkButton(
            footer,
            text="Sign out",
            height=34,
            corner_radius=8,
            fg_color="transparent",
            hover_color=UI_SURFACE_LIGHT,
            text_color=UI_TEXT_MUTED,
            command=self.sign_out,
        ).pack(fill="x")

        nav = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        nav.pack(fill="both", expand=True, padx=4, pady=2)
        self.nav_buttons = {}
        for entry in SIDEBAR_NAV:
            if entry[0] == "section":
                NavSectionLabel(nav, text=entry[1]).pack(anchor="w", padx=12, pady=(12, 4))
                continue
            key, label, icon = entry
            if not self._sidebar_entry_visible(key):
                continue
            btn = NavButton(
                nav,
                label,
                icon,
                command=lambda k=key: self.show_page(resolve_nav_target(k)),
                nav_key=key,
            )
            btn.pack(fill="x", pady=1)
            self.nav_buttons[key] = btn

    def _build_main(self) -> None:
        main = ctk.CTkFrame(self.shell, fg_color=UI_BG, corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        # row0 header · row1 content (expands) · row2 status
        main.grid_rowconfigure(1, weight=1)

        topbar_wrap = ctk.CTkFrame(main, fg_color=UI_BG, corner_radius=0)
        topbar_wrap.grid(row=0, column=0, sticky="ew")
        topbar_wrap.grid_columnconfigure(0, weight=1)
        self.topbar = ctk.CTkFrame(topbar_wrap, fg_color=UI_BG, height=TOPBAR_HEIGHT, corner_radius=0)
        self.topbar.grid(row=0, column=0, sticky="ew")
        self.topbar.grid_propagate(False)
        ctk.CTkFrame(topbar_wrap, fg_color=UI_BORDER, height=1).grid(row=1, column=0, sticky="ew")

        title_block = ctk.CTkFrame(self.topbar, fg_color="transparent")
        title_block.pack(side="left", fill="y", padx=CONTENT_PAD, pady=(10, 8))
        self.page_title = ctk.CTkLabel(title_block, text="", font=font("title"), text_color=UI_TEXT_PRIMARY, anchor="w")
        self.page_title.pack(fill="x")
        self.topbar_subtitle = ctk.CTkLabel(
            title_block, text="", font=font("small"), text_color=UI_TEXT_MUTED, anchor="w"
        )
        self.topbar_subtitle.pack(fill="x", pady=(2, 0))

        # Pack side=right: first widget is rightmost → jump | live | name | avatar (L→R)
        right = ctk.CTkFrame(self.topbar, fg_color="transparent")
        right.pack(side="right", fill="y", padx=(0, CONTENT_PAD), pady=10)
        jump = SearchBar(right, placeholder="Jump to…  Ctrl+K", width=200, height=32)
        jump.pack(side="right")
        jump.bind("<Return>", lambda _e: self._jump_to_page(jump.get()))
        self._jump_entry = jump
        try:
            self.root.bind_all("<Control-k>", lambda _e: self._focus_jump())
            self.root.bind_all("<Control-K>", lambda _e: self._focus_jump())
        except Exception:
            pass
        live = ctk.CTkFrame(
            right, fg_color=UI_SURFACE, corner_radius=14, border_width=1, border_color=UI_BORDER_GLOW, height=28
        )
        live.pack(side="right", padx=(0, 12))
        ctk.CTkFrame(live, fg_color=DODGEVILLE_ACCENT, width=7, height=7, corner_radius=4).pack(
            side="left", padx=(10, 6), pady=10
        )
        ctk.CTkLabel(live, text="SYSTEM LIVE", font=font("micro"), text_color=UI_ACCENT_GLOW).pack(
            side="left", padx=(0, 12)
        )
        self.user_badge = ctk.CTkLabel(right, text="", font=font("small"), text_color=UI_TEXT_MUTED)
        self.user_badge.pack(side="right", padx=(0, 12))
        self._user_avatar = ctk.CTkLabel(
            right,
            text="",
            width=34,
            height=34,
            corner_radius=17,
            fg_color=UI_SURFACE_LIGHT,
            text_color=UI_TEXT_PRIMARY,
            font=font("small"),
        )
        self._user_avatar.pack(side="right", padx=(0, 8))

        self.subnav = SubNavBar(topbar_wrap, on_select=self.show_page)
        self.subnav.grid(row=2, column=0, sticky="ew")
        self.subnav.grid_remove()

        self.content = ctk.CTkFrame(main, fg_color=UI_BG, corner_radius=0)
        self.content.grid(row=1, column=0, sticky="nsew", padx=CONTENT_PAD, pady=(10, 8))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        from config import APP_NAME, APP_VERSION
        from logic import rust_bridge

        self.statusbar = ctk.CTkLabel(
            main,
            text=f"{APP_NAME} v{APP_VERSION} · {rust_bridge.backend_name()} engine · rebuilt UI",
            font=font("mono"),
            text_color=UI_TEXT_MUTED,
            anchor="w",
            height=28,
        )
        self.statusbar.grid(row=2, column=0, sticky="ew", padx=CONTENT_PAD, pady=(0, 10))
        self.toast_host = ToastHost(self.shell)

    def _mount_pages(self) -> None:
        self.pages = {}
        self.page_controllers = {}
        for key, _, _ in NAV_ITEMS:
            cls = PAGE_CLASSES.get(key)
            if cls is None:
                frame = ctk.CTkFrame(self.content, fg_color=UI_BG)
            else:
                # notifications maps to DashboardPage — share instance with dashboard
                if key == "notifications" and "dashboard" in self.page_controllers:
                    self.pages[key] = self.pages["dashboard"]
                    self.page_controllers[key] = self.page_controllers["dashboard"]
                    continue
                page = cls(self.content, self)
                frame = page
                self.page_controllers[key] = page
            frame.grid(row=0, column=0, sticky="nsew")
            frame.grid_remove()
            self.pages[key] = frame

    def _visible_hub_tabs(self, hub_key: str) -> list[tuple[str, str]]:
        hub = NAV_HUBS[hub_key]
        visible = []
        for page_key, label in hub["tabs"]:
            perm = NAV_PERMISSIONS.get(page_key)
            if perm:
                perms = perm if isinstance(perm, tuple) else (perm,)
                if not any(self.can(p) for p in perms):
                    continue
            visible.append((page_key, label))
        return visible

    def _update_subnav(self, page_key: str) -> None:
        if not hasattr(self, "subnav"):
            return
        hub_key = hub_for_page(page_key)
        if not hub_key:
            self.subnav.grid_remove()
            return
        tabs = self._visible_hub_tabs(hub_key)
        if tabs:
            self.subnav.set_tabs(tabs, page_key)
            self.subnav.grid(row=2, column=0, sticky="ew")
        else:
            self.subnav.grid_remove()

    def show_page(self, key: str, *, defer_refresh: bool = False) -> None:
        if key == "notifications":
            key = "dashboard"
        if key == "updated_schedule":
            key = "live_schedule"
        key = resolve_nav_target(key)
        if key not in self.pages:
            return
        for k, frame in self.pages.items():
            try:
                frame.grid_remove()
            except Exception:
                pass
        page = self.pages[key]
        page.grid(row=0, column=0, sticky="nsew")
        ctrl = self.page_controllers.get(key)
        if ctrl is not None:
            try:
                ctrl.ensure_built()
            except Exception:
                logging.getLogger(__name__).exception("build page %s", key)
        self.page_title.configure(text=page_title(key))
        if self._is_officer_role():
            subtitle = OFFICER_PAGE_SUBTITLES.get(key, PAGE_SUBTITLES.get(key, ""))
        else:
            subtitle = PAGE_SUBTITLES.get(key, "")
        self.topbar_subtitle.configure(text=subtitle)
        for k, btn in self.nav_buttons.items():
            if k in NAV_HUBS:
                btn.set_active(key in NAV_HUBS[k]["pages"])
            else:
                btn.set_active(k == key)
        self._update_subnav(key)
        self.current_page = key
        if ctrl is not None:
            try:
                if defer_refresh:
                    self.root.after(80, ctrl.refresh)
                else:
                    ctrl.refresh()
            except Exception:
                logging.getLogger(__name__).exception("refresh page %s", key)
        self._update_sidebar_date()
        self._update_user_badge()
        self._update_notification_badge()

    def _refresh_page(self, key: str) -> None:
        ctrl = self.page_controllers.get(key)
        if ctrl is not None:
            try:
                ctrl.ensure_built()
                ctrl.refresh()
            except Exception:
                logging.getLogger(__name__).exception("refresh %s", key)

    def refresh_all(self) -> None:
        if self.current_page:
            self._refresh_page(self.current_page)
        self.set_status("Data refreshed", toast=False)

    def set_status(self, message: str, *, toast: bool = True, level: str = "info") -> None:
        if not hasattr(self, "statusbar"):
            return
        text = (message or "").strip()
        bar = text
        if bar and not bar.startswith("✓") and not bar.startswith("✗"):
            bar = f"✓ {bar}"
        self.statusbar.configure(text=bar or self.statusbar.cget("text"))
        if toast and text:
            self.show_toast(text, level=level)

    def show_toast(self, message: str, *, level: str = "info", ms: int = 3200) -> None:
        host = getattr(self, "toast_host", None)
        if host:
            host.show(message, level=level, ms=ms)

    def _focus_jump(self) -> None:
        entry = getattr(self, "_jump_entry", None)
        if entry is not None:
            entry.focus_set()
            entry.select_range(0, "end")

    def _jump_to_page(self, query: str) -> None:
        q = (query or "").strip().lower()
        if not q:
            return
        candidates = []
        for key, label, _ in NAV_ITEMS:
            candidates.append((key, label))
        for hub_key, hub in NAV_HUBS.items():
            candidates.append((hub_key, hub.get("label", hub_key)))
            for page_key, tab_label in hub.get("tabs", ()):
                candidates.append((page_key, tab_label))
        for key, label in candidates:
            if q == key or q == label.lower() or label.lower().startswith(q) or q in label.lower():
                self.show_page(key)
                if hasattr(self, "_jump_entry"):
                    self._jump_entry.delete(0, "end")
                return
        self.set_status(f"No page matches “{query}”", level="warning")

    def _update_sidebar_date(self) -> None:
        if not hasattr(self, "sidebar_date"):
            return
        today = date.today()
        cycle = get_cycle_day(today)
        squad = get_squad_on_duty(cycle)
        self.sidebar_date.configure(text=f"{format_date(today)}\nCycle Day {cycle} · Squad {squad}")

    def _update_user_badge(self) -> None:
        if not self.current_user or not hasattr(self, "user_badge"):
            return
        name = self.current_user.get("officer_name") or self.current_user.get("username")
        self.user_badge.configure(text=name)
        parts = [p for p in str(name).split() if p]
        initials = "".join(p[0].upper() for p in parts[:2]) or str(name)[:2].upper()
        self._user_avatar.configure(text=initials)

    def _update_notification_badge(self) -> None:
        officer_id = self._linked_officer_id() if self._is_officer_role() else None
        count = get_unread_notification_count(officer_id=officer_id)
        btn = self.nav_buttons.get("dashboard")
        if btn:
            btn.set_badge(count)

    def backup_database(self) -> None:
        from tkinter import messagebox

        if not self.can("database.backup"):
            messagebox.showwarning("Permission", "Backup requires supervisor permission.")
            return
        try:
            path = backup_database()
            uid = self.current_user.get("id") if self.current_user else None
            log_audit_action("database.backup", "database", None, uid, path)
            self.set_status(f"Backup saved: {path}", level="success")
        except Exception as exc:
            messagebox.showerror("Backup failed", str(exc))


def _install_tk_error_handler(root) -> None:
    log = logging.getLogger("DodgevilleScheduler")

    def _report(exc, val, tb):
        import traceback

        log.error("UI callback error:\n%s", "".join(traceback.format_exception(exc, val, tb)))

    try:
        root.report_callback_exception = _report
    except Exception:
        pass


def run():
    from config import configure_logging
    from paths import is_frozen

    configure_logging()
    try:
        app = DodgevilleSchedulerApp()
        _install_tk_error_handler(app.root)
        if not is_frozen():
            from scripts.startup_gates import gui_gate_warning_if_failed

            app.root.after(400, lambda: gui_gate_warning_if_failed(app.root))
        app.root.mainloop()
    except Exception:
        import traceback

        tb = traceback.format_exc()
        try:
            configure_logging()
            logging.getLogger("dodgeville").critical("Startup failed:\n%s", tb)
        except Exception:
            pass
        try:
            import tkinter as tk
            from tkinter import messagebox

            err = tk.Tk()
            err.withdraw()
            messagebox.showerror("Chronos Command — Startup Failed", tb[-3500:] if len(tb) > 3500 else tb)
            err.destroy()
        except Exception:
            print(tb, file=sys.stderr)
        raise
