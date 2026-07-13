"""Session lifecycle — login, permissions, shell teardown."""

from __future__ import annotations

import os
from typing import Optional

from config import AUTO_LOGIN_ENABLED, AUTO_LOGIN_SKIP_PASSWORD_CHANGE, AUTO_LOGIN_USERNAME
from database import init_database
from logic import log_audit_action
from permissions import role_has_permission
from ui.branding import get_department_branding
from ui.display import apply_main_window_layout, clear_login_window_layout, show_login_window
from ui.login import LoginFrame
from ui.window_layout import reset_main_window_layout_guard


class SessionMixin:
    def can(self, permission: str) -> bool:
        if not self.current_user:
            return False
        return role_has_permission(self.current_user["role"], permission)

    def _linked_officer_id(self) -> Optional[int]:
        if not self.current_user:
            return None
        return self.current_user.get("officer_id")

    def _is_officer_role(self) -> bool:
        return bool(self.current_user and self.current_user.get("role") == "Officer")

    def _remember_brand_image(self, image) -> None:
        if image is not None and image not in self._brand_images:
            self._brand_images.append(image)

    def _bootstrap_session(self) -> None:
        init_database()
        if os.environ.get("SCHEDULER_UI_TEST", "").strip() == "1":
            return
        if AUTO_LOGIN_ENABLED and self._try_dev_auto_login():
            return
        self._show_login()
        show_login_window(self.root)

    def _try_dev_auto_login(self) -> bool:
        from logic import authenticate_user, list_all_users

        candidates = [AUTO_LOGIN_USERNAME]
        for u in list_all_users():
            if u.get("role") == "Administration" and u.get("active") == 1 and u["username"] not in candidates:
                candidates.append(u["username"])
        for username in candidates:
            for password in ("admin", "supervisor", "officer"):
                auth = authenticate_user(username, password)
                if not auth.get("success"):
                    continue
                user = auth["user"]
                if user.get("role") != "Administration":
                    continue
                if AUTO_LOGIN_SKIP_PASSWORD_CHANGE:
                    user["must_change_password"] = 0
                self._on_login_success(user)
                return True
        return False

    def _show_login(self) -> None:
        self.login_frame = LoginFrame(self.root, on_success=self._on_login_success)
        self.login_frame.pack(fill="both", expand=True)

    def _on_login_success(self, user: dict) -> None:
        self.current_user = user
        clear_login_window_layout(self.root)
        if getattr(self, "login_frame", None):
            self.login_frame.destroy()
            self.login_frame = None
        if user.get("must_change_password"):
            if not self._prompt_forced_password_change():
                self.sign_out()
                return
            self.current_user["must_change_password"] = 0
        import customtkinter as ctk

        from ui.theme import UI_BG, UI_TEXT_MUTED, font

        loading = ctk.CTkLabel(
            self.root, text="Loading scheduler…", font=font("subheading"), text_color=UI_TEXT_MUTED, fg_color=UI_BG
        )
        loading.pack(expand=True)
        try:
            self.root.update_idletasks()
        except Exception:
            pass
        self.root.after(10, lambda: self._finish_login_shell(loading))

    def _finish_login_shell(self, loading=None) -> None:
        self._login_loading = loading
        self._pending_initial_dashboard = bool(self.current_user)
        self._build_shell()

    def _finalize_login_shell(self) -> None:
        loading = getattr(self, "_login_loading", None)
        if loading is not None:
            try:
                loading.destroy()
            except Exception:
                pass
            self._login_loading = None
        # Headless tests hang on maximize/focus — skip window chrome layout in UI test mode.
        if os.environ.get("SCHEDULER_UI_TEST", "").strip() != "1":
            apply_main_window_layout(self.root)
        branding = get_department_branding()
        self.root.title(f"{branding['name']} Scheduler")
        if getattr(self, "_pending_initial_dashboard", False):
            self._pending_initial_dashboard = False
            self.show_page("dashboard")

    def _prompt_forced_password_change(self) -> bool:
        from tkinter import simpledialog

        from logic import change_own_password

        current = simpledialog.askstring("Password change required", "Current password:", show="*", parent=self.root)
        new_pw = simpledialog.askstring("Password change required", "New password:", show="*", parent=self.root)
        if not current or not new_pw:
            return False
        result = change_own_password(self.current_user["id"], current, new_pw)
        return bool(result.get("success"))

    def sign_out(self) -> None:
        if self.current_user:
            log_audit_action("user.logout", "app_user", self.current_user.get("id"), self.current_user.get("id"), "")
        self._teardown_shell_state()
        reset_main_window_layout_guard(self.root)
        self.current_user = None
        self.current_page = None
        if os.environ.get("SCHEDULER_UI_TEST", "").strip() == "1":
            return
        self._show_login()
        show_login_window(self.root)

    def _teardown_shell_state(self) -> None:
        shell = getattr(self, "shell", None)
        if shell is not None:
            try:
                shell.destroy()
            except Exception:
                pass
        self.shell = None
        self.pages = {}
        self.page_controllers = {}
        self.nav_buttons = {}
        self.stat_cards = {}
        for w in list(self.root.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass
