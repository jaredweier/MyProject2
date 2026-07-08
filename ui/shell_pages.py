"""Application shell — sidebar, topbar, navigation, and page refresh orchestration."""

import os
from datetime import date
from tkinter import messagebox

import customtkinter as ctk

from database import backup_database, list_backup_files
from logic import get_cycle_day, get_squad_on_duty, get_unread_notification_count, log_audit_action
from ui.assets import load_logo
from ui.branding import get_department_branding
from ui.helpers import handle_export_result
from ui.profile_dialog import open_my_profile_dialog
from ui.theme import (
    CONTENT_PAD,
    NAV_HUBS,
    NAV_ITEMS,
    NAV_PERMISSIONS,
    OFFICER_PAGE_SUBTITLES,
    PAGE_SUBTITLES,
    SIDEBAR_NAV,
    SIDEBAR_WIDTH,
    TOPBAR_HEIGHT,
    UI_BG,
    UI_BORDER,
    UI_SIDEBAR,
    UI_SURFACE_LIGHT,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    font,
    hub_for_page,
    page_title,
    resolve_nav_target,
)
from ui.widgets import NavButton, NavSectionLabel, SubNavBar
from validators import format_date


class ShellPageMixin:
    """Main window chrome: nav, page routing, status bar, and global refresh."""

    def _page_build_steps(self) -> list:
        return [
            self._build_dashboard,
            self._build_base_schedule,
            self._build_live_schedule,
            self._build_timecard,
            self._build_banked_time,
            self._build_timeline,
            self._build_requests,
            self._build_swaps,
            self._build_notifications,
            self._build_officers,
            self._build_payroll,
            self._build_simulator,
            self._build_reports,
            self._build_availability,
            self._build_users,
        ]

    def _build_shell(self) -> None:
        self._shell_building = True
        self.shell = ctk.CTkFrame(self.root, fg_color=UI_BG, corner_radius=0)
        self.shell.pack(fill="both", expand=True)
        self.shell.grid_columnconfigure(1, weight=1)
        self.shell.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_chrome()

        if os.environ.get("SCHEDULER_UI_TEST", "").strip() == "1":
            for step in self._page_build_steps():
                step()
            self._shell_building = False
            self._complete_shell_build()
            return

        self._page_build_queue = list(self._page_build_steps())
        self._page_build_total = len(self._page_build_queue)
        self.root.after(1, self._build_next_page_batch)

    def _build_next_page_batch(self, batch_size: int = 1) -> None:
        loading = getattr(self, "_login_loading", None)
        for _ in range(batch_size):
            if not self._page_build_queue:
                break
            self._page_build_queue.pop(0)()
            try:
                self.root.update_idletasks()
            except Exception:
                pass
        if loading is not None and loading.winfo_exists():
            done = self._page_build_total - len(self._page_build_queue)
            loading.configure(text=f"Loading workspace… {done}/{self._page_build_total}")
        if self._page_build_queue:
            self.root.after(8, lambda: self._build_next_page_batch(batch_size))
            return
        self._shell_building = False
        self._complete_shell_build()

    def _complete_shell_build(self) -> None:
        if hasattr(self, "_finalize_login_shell"):
            self._finalize_login_shell()
        self._deferred_shell_refresh()

    def _deferred_shell_refresh(self) -> None:
        """Populate heavy payroll widgets after the shell exists (safe for headless tests)."""
        import os

        if os.environ.get("SCHEDULER_UI_TEST", "").strip() == "1":
            if getattr(self, "_pending_initial_dashboard", False):
                self._pending_initial_dashboard = False
                self._show_initial_dashboard()
            return
        if getattr(self, "_pending_initial_dashboard", False):
            self._pending_initial_dashboard = False
            self._show_initial_dashboard()

    def _cancel_deferred_refresh(self) -> None:
        """Cancel background refresh callbacks (prevents piled-up Tk work after sign-out)."""
        after_id = getattr(self, "_payroll_refresh_after_id", None)
        if after_id is not None:
            try:
                self.root.after_cancel(after_id)
            except Exception:
                pass
            self._payroll_refresh_after_id = None
        self._payroll_period_refreshing = False

    def _show_initial_dashboard(self) -> None:
        """First dashboard paint after deferred payroll widgets (avoids CTk deadlock in tests)."""
        if not self.current_user:
            return
        try:
            self.show_page("dashboard", defer_refresh=True)
            self.root.after(120, self._refresh_dashboard_safe)
            user = self.current_user
            name = user.get("officer_name") or user.get("username")
            nav_count = len(self.nav_buttons) if hasattr(self, "nav_buttons") else 0
            status = f"Signed in as {name}"
            if nav_count > 1:
                status += (
                    f"  ·  Ctrl+0 dashboard  ·  Ctrl+1–{min(nav_count, 9)} pages"
                    f"  ·  F5 refresh  ·  Ctrl+Shift+Q sign out"
                )
            self.set_status(status)
        except Exception:
            pass

    def _refresh_dashboard_safe(self) -> None:
        if getattr(self, "_shell_building", False):
            self.root.after(100, self._refresh_dashboard_safe)
            return
        if self.current_page != "dashboard":
            return
        try:
            self._refresh_dashboard()
        except Exception:
            pass

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

    def _visible_hub_tabs(self, hub_key: str) -> list[tuple[str, str]]:
        hub = NAV_HUBS[hub_key]
        visible: list[tuple[str, str]] = []
        for page_key, label in hub["tabs"]:
            perm = NAV_PERMISSIONS.get(page_key)
            if perm:
                perms = perm if isinstance(perm, tuple) else (perm,)
                if not any(self.can(p) for p in perms):
                    continue
            visible.append((page_key, label))
        return visible

    def _update_subnav(self, page_key: str) -> None:
        hub_key = hub_for_page(page_key)
        if not hub_key or not hasattr(self, "subnav"):
            return
        tabs = self._visible_hub_tabs(hub_key)
        if tabs:
            self.subnav.set_tabs(tabs, page_key)
            self.subnav.grid(row=1, column=0, sticky="ew")
        else:
            self.subnav.grid_remove()

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self.shell, width=SIDEBAR_WIDTH, fg_color=UI_SIDEBAR, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=16, pady=(18, 12))
        branding = get_department_branding()
        brand_row = ctk.CTkFrame(brand, fg_color="transparent")
        brand_row.pack(fill="x")
        logo_img = load_logo((32, 32))
        if logo_img:
            self._remember_brand_image(logo_img)
            ctk.CTkLabel(brand_row, text="", image=logo_img).pack(side="left", padx=(0, 10))
        text_col = ctk.CTkFrame(brand_row, fg_color="transparent")
        text_col.pack(side="left", fill="x", expand=True)
        short_name = branding["name"].replace(" Police Department", " PD")
        ctk.CTkLabel(
            text_col,
            text=short_name,
            font=font("subheading"),
            text_color=UI_TEXT_PRIMARY,
        ).pack(anchor="w")
        ctk.CTkLabel(
            text_col,
            text="Scheduler",
            font=font("small"),
            text_color=UI_TEXT_MUTED,
        ).pack(anchor="w", pady=(1, 0))
        self._sidebar_mission_label = None

        nav_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav_frame.pack(fill="x", padx=6, pady=2)
        for entry in SIDEBAR_NAV:
            if entry[0] == "section":
                NavSectionLabel(nav_frame, text=entry[1]).pack(anchor="w", padx=8, pady=(10, 4))
                continue
            key, label, icon = entry
            if not self._sidebar_entry_visible(key):
                continue
            btn = NavButton(
                nav_frame,
                label,
                icon,
                command=lambda k=key: self.show_page(resolve_nav_target(k)),
                nav_key=key,
            )
            btn.pack(fill="x", pady=2)
            self.nav_buttons[key] = btn

        ctk.CTkFrame(sidebar, fg_color=UI_BORDER, height=1).pack(fill="x", padx=16, pady=12)
        ctk.CTkButton(
            sidebar,
            text="Refresh all",
            height=34,
            corner_radius=8,
            fg_color=UI_SURFACE_LIGHT,
            hover_color=UI_BORDER,
            text_color=UI_TEXT_PRIMARY,
            command=self.refresh_all,
        ).pack(fill="x", padx=16, pady=(0, 6))
        if self.can("database.backup"):
            ctk.CTkButton(
                sidebar,
                text="Backup database",
                height=34,
                corner_radius=8,
                fg_color=UI_SURFACE_LIGHT,
                hover_color=UI_BORDER,
                text_color=UI_TEXT_PRIMARY,
                command=self.backup_database,
            ).pack(fill="x", padx=16, pady=(0, 4))
            ctk.CTkButton(
                sidebar,
                text="Restore backup",
                height=34,
                corner_radius=8,
                fg_color=UI_SURFACE_LIGHT,
                hover_color=UI_BORDER,
                text_color=UI_TEXT_PRIMARY,
                command=self.restore_database,
            ).pack(fill="x", padx=16, pady=(0, 6))
        ctk.CTkButton(
            sidebar,
            text="Sign out",
            height=34,
            corner_radius=8,
            fg_color="transparent",
            hover_color=UI_SURFACE_LIGHT,
            text_color=UI_TEXT_MUTED,
            command=self.sign_out,
        ).pack(fill="x", padx=16, pady=(0, 16))

        self.sidebar_date = ctk.CTkLabel(
            sidebar,
            text="",
            font=font("small"),
            text_color=UI_TEXT_MUTED,
        )
        self.sidebar_date.pack(side="bottom", pady=16)

    def _build_main_chrome(self) -> None:
        main = ctk.CTkFrame(self.shell, fg_color=UI_BG, corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew", padx=(0, 0), pady=0)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        topbar_wrap = ctk.CTkFrame(main, fg_color=UI_BG, corner_radius=0)
        topbar_wrap.grid(row=0, column=0, sticky="ew")
        topbar_wrap.grid_columnconfigure(0, weight=1)
        self.topbar = ctk.CTkFrame(
            topbar_wrap,
            fg_color=UI_BG,
            height=TOPBAR_HEIGHT,
            corner_radius=0,
            border_width=0,
        )
        ctk.CTkFrame(topbar_wrap, fg_color=UI_BORDER, height=1).grid(row=1, column=0, sticky="ew")
        self.topbar.grid(row=0, column=0, sticky="ew")
        self.topbar.grid_propagate(False)

        title_block = ctk.CTkFrame(self.topbar, fg_color="transparent")
        title_block.pack(side="left", fill="y", padx=CONTENT_PAD, pady=(12, 10))
        self.page_title = ctk.CTkLabel(title_block, text="", font=font("title"), text_color=UI_TEXT_PRIMARY, anchor="w")
        self.page_title.pack(fill="x")
        self.topbar_subtitle = ctk.CTkLabel(
            title_block,
            text="",
            font=font("small"),
            text_color=UI_TEXT_MUTED,
            anchor="w",
        )
        self.topbar_subtitle.pack(fill="x", pady=(2, 0))

        topbar_right = ctk.CTkFrame(self.topbar, fg_color="transparent")
        topbar_right.pack(side="right", fill="y", padx=(0, CONTENT_PAD), pady=10)
        self._user_avatar = ctk.CTkLabel(
            topbar_right,
            text="",
            width=32,
            height=32,
            corner_radius=16,
            fg_color=UI_SURFACE_LIGHT,
            text_color=UI_TEXT_PRIMARY,
            font=font("small"),
            cursor="hand2",
        )
        self._user_avatar.pack(side="right", padx=(10, 0))
        self._user_avatar.bind("<Button-1>", lambda e: open_my_profile_dialog(self))
        self.user_badge = ctk.CTkLabel(
            topbar_right,
            text="",
            font=font("small"),
            text_color=UI_TEXT_MUTED,
            cursor="hand2",
        )
        self.user_badge.pack(side="right")
        self.user_badge.bind("<Button-1>", lambda e: open_my_profile_dialog(self))

        self.subnav = SubNavBar(topbar_wrap, on_select=self.show_page)
        self.subnav.grid(row=1, column=0, sticky="ew")
        self.subnav.grid_remove()

        self.content = ctk.CTkFrame(main, fg_color=UI_BG, corner_radius=0)
        self.content.grid(row=1, column=0, sticky="nsew", padx=CONTENT_PAD, pady=(12, CONTENT_PAD))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        from config import APP_NAME, APP_VERSION
        from logic import rust_bridge

        engine = rust_bridge.backend_name()
        self.statusbar = ctk.CTkLabel(
            main,
            text=f"{APP_NAME} v{APP_VERSION} · {engine} engine",
            font=font("mono"),
            text_color=UI_TEXT_MUTED,
            anchor="w",
            height=28,
        )
        self.statusbar.grid(row=2, column=0, sticky="ew", padx=CONTENT_PAD, pady=(0, 10))

        for key, label, _ in NAV_ITEMS:
            frame = ctk.CTkFrame(self.content, fg_color=UI_BG)
            self.pages[key] = frame

    def show_page(self, key: str, *, defer_refresh: bool = False) -> None:
        if key == "notifications":
            key = "dashboard"
        if key == "updated_schedule":
            key = "live_schedule"
        key = resolve_nav_target(key)
        if key not in self.pages:
            return
        for k, frame in self.pages.items():
            frame.grid_forget()
        self.pages[key].grid(row=0, column=0, sticky="nsew")
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
        if defer_refresh:
            self.root.after(80, lambda k=key: self._refresh_page(k))
        else:
            self._refresh_page(key)
        self._update_sidebar_date()
        self._update_notification_badge()
        self._update_user_badge()

    def set_status(self, message: str) -> None:
        if not hasattr(self, "statusbar"):
            return
        text = message.strip()
        if text and not text.startswith("✓") and not text.startswith("✗"):
            text = f"✓ {text}"
        self.statusbar.configure(text=text)

    def _export_pdf_result(self, result, label: str) -> None:
        handle_export_result(result, label=label, set_status=self.set_status)

    def _update_notification_badge(self) -> None:
        officer_id = self._linked_officer_id() if self._is_officer_role() else None
        count = get_unread_notification_count(officer_id=officer_id)
        btn = self.nav_buttons.get("dashboard")
        if btn:
            btn.set_badge(count)

    def _update_user_badge(self) -> None:
        if not hasattr(self, "user_badge") or not self.current_user:
            return
        name = self.current_user.get("officer_name") or self.current_user.get("username")
        self.user_badge.configure(text=name)
        if hasattr(self, "_user_avatar"):
            parts = [p for p in str(name).split() if p]
            initials = "".join(p[0].upper() for p in parts[:2]) or str(name)[:2].upper()
            self._user_avatar.configure(text=initials)

    def _update_sidebar_date(self) -> None:
        today = date.today()
        cycle = get_cycle_day(today)
        squad = get_squad_on_duty(cycle)
        self.sidebar_date.configure(
            text=f"{format_date(today)}\nCycle Day {cycle} · Squad {squad}",
        )

    def refresh_all(self) -> None:
        self._refresh_page(self.current_page)
        if self.current_page != "dashboard":
            self._refresh_dashboard_data()
        self.set_status("Data refreshed")

    def backup_database(self) -> None:
        if not self.can("database.backup"):
            messagebox.showwarning("Permission", "Only Supervisor or Administration can backup.")
            return
        try:
            from logic import set_department_setting

            path = backup_database()
            uid = self.current_user.get("id") if self.current_user else None
            set_department_setting("last_manual_backup", date.today().isoformat(), user_id=uid)
            log_audit_action("database.backup", "database", None, uid, path)
            messagebox.showinfo("Backup Complete", f"Database saved to:\n{path}")
            self.set_status(f"Backup saved: {path}")
            if self.current_page == "dashboard":
                self._refresh_dashboard()
        except Exception as exc:
            messagebox.showerror("Backup Failed", str(exc))

    def restore_database(self) -> None:
        if not self.can("database.backup"):
            messagebox.showwarning("Permission", "Only Supervisor or Administration can restore.")
            return
        from tkinter import filedialog

        from logic import restore_database_from_backup

        initial = list_backup_files()
        initialdir = os.path.dirname(initial[0]) if initial else None
        path = filedialog.askopenfilename(
            title="Select backup to restore",
            initialdir=initialdir,
            filetypes=[("SQLite database", "*.db"), ("All files", "*.*")],
        )
        if not path:
            return
        if not messagebox.askyesno(
            "Confirm Restore",
            "This replaces the live database with the selected backup.\n\n"
            "A safety copy of the current database is saved first.\n\n"
            "Continue?",
            icon="warning",
        ):
            return
        uid = self.current_user.get("id") if self.current_user else None
        result = restore_database_from_backup(path, user_id=uid)
        if not result.get("success"):
            messagebox.showerror("Restore Failed", result.get("message", "Unknown error"))
            return
        messagebox.showinfo(
            "Restore Complete",
            f"Restored from:\n{path}\n\nSafety copy:\n{result.get('safety_backup')}\n\n"
            "Refresh open tabs if counts look stale.",
        )
        self.set_status("Database restored from backup")
        self.refresh_all()

    def _refresh_current_page(self) -> None:
        if self.current_page:
            self._refresh_page(self.current_page)
            self.set_status("Page refreshed")

    def _bind_keyboard_shortcuts(self) -> None:
        shortcuts: list[tuple[str, str]] = []
        for entry in SIDEBAR_NAV:
            if entry[0] == "section":
                continue
            nav_key = entry[0]
            if nav_key not in self.nav_buttons:
                continue
            shortcuts.append((nav_key, resolve_nav_target(nav_key)))
        self.root.bind("<Control-Key-0>", lambda e: self.show_page("dashboard"))
        self.root.bind("<Control-Shift-Q>", lambda e: self.sign_out())
        for index, (_nav_key, page_key) in enumerate(shortcuts[:9], start=1):
            self.root.bind(
                f"<Control-Key-{index}>",
                lambda e, page=page_key: self.show_page(page),
            )

    def _refresh_page(self, key: str) -> None:
        import os

        if os.environ.get("SCHEDULER_UI_TEST", "").strip() == "1":
            return
        refreshers = {
            "dashboard": self._refresh_dashboard,
            "base_schedule": lambda: self.refresh_monthly("base"),
            "live_schedule": lambda: self.refresh_monthly("updated"),
            "timecard": self.refresh_timecard,
            "banked_time": self.refresh_banked_time,
            "timeline": self.refresh_gantt,
            "requests": self.refresh_requests,
            "swaps": self.refresh_swaps,
            "notifications": lambda: (self.show_page("dashboard"), self.refresh_notifications()),
            "officers": self.refresh_officer_list,
            "payroll": self.refresh_payroll,
            "simulator": lambda: None,
            "reports": self.refresh_reports,
            "availability": self.refresh_availability,
            "users": self.refresh_users,
        }
        refreshers.get(key, lambda: None)()
