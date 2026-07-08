"""Login, permissions, and session lifecycle."""

import os
from typing import Optional

from config import (
    AUTO_LOGIN_ENABLED,
    AUTO_LOGIN_SKIP_PASSWORD_CHANGE,
    AUTO_LOGIN_USERNAME,
)
from database import init_database
from logic import log_audit_action
from permissions import role_has_permission
from ui.branding import get_department_branding
from ui.display import apply_main_window_layout, clear_login_window_layout, show_login_window
from ui.login import LoginFrame
from ui.window_layout import reset_main_window_layout_guard


class SessionPageMixin:
    """Authentication helpers and sign-in / sign-out flow."""

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

    def _refresh_department_branding(self) -> None:
        branding = get_department_branding()
        self.root.title(f"{branding['name']} Scheduler")
        if getattr(self, "_sidebar_mission_label", None) is not None:
            self._sidebar_mission_label.configure(text=branding["tagline"])
        if hasattr(self, "_hero_dept_label"):
            self._hero_dept_label.configure(text=branding["name"])
        if hasattr(self, "_hero_mission_label"):
            self._hero_mission_label.configure(text=branding["tagline"])

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
            if u.get("role") == "Administration" and u.get("active") == 1:
                if u["username"] not in candidates:
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
            self.root,
            text="Loading scheduler…",
            font=font("subheading"),
            text_color=UI_TEXT_MUTED,
            fg_color=UI_BG,
        )
        loading.pack(expand=True)
        self.root.update_idletasks()
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
        if not self.current_user:
            self._pending_initial_dashboard = False
            return
        self.root.after_idle(self._run_post_login_flow)
        self._refresh_department_branding()
        self._apply_dashboard_role_layout()
        self.root.bind("<F5>", lambda e: self._refresh_current_page())
        self._bind_keyboard_shortcuts()
        if os.environ.get("SCHEDULER_UI_TEST", "").strip() != "1":
            self.root.after(100, lambda: apply_main_window_layout(self.root))

    def _teardown_shell_state(self) -> None:
        if hasattr(self, "_cancel_deferred_refresh"):
            try:
                self._cancel_deferred_refresh()
            except Exception:
                pass
        from ui.helpers import cancel_pending_after

        try:
            cancel_pending_after(self.root)
        except Exception:
            pass
        self.current_user = None
        if hasattr(self, "shell") and self.shell is not None:
            try:
                if self.shell.winfo_exists():
                    self.shell.destroy()
            except Exception:
                try:
                    self.shell.grid_forget()
                except Exception:
                    pass
        self.shell = None
        self.pages = {}
        self.nav_buttons = {}
        self.current_page = None
        for attr in (
            "_officer_row_widgets",
            "_request_row_widgets",
            "_swap_row_widgets",
            "_notification_row_widgets",
            "_availability_row_widgets",
            "_open_shift_row_widgets",
            "_payroll_row_widgets",
            "_gantt_cells",
            "_monthly_cells",
            "_schedule_pages",
        ):
            if hasattr(self, attr):
                setattr(self, attr, {})
        self._gantt_spec = None
        self._monthly_spec = None

    def sign_out(self) -> None:
        if self.current_user:
            uid = self.current_user.get("id")
            log_audit_action(
                "user.logout",
                "app_user",
                uid,
                uid,
                self.current_user.get("username"),
            )
        self._teardown_shell_state()
        from ui.assets import reset_brand_image_cache

        reset_brand_image_cache()
        if getattr(self, "login_frame", None):
            try:
                self.login_frame.destroy()
            except Exception:
                pass
            self.login_frame = None
        reset_main_window_layout_guard(self.root)
        for attr in (
            "_login_layout_done",
            "_login_map_bound",
            "_login_center_bound",
            "_login_centering_active",
            "_login_configure_bind_id",
            "_login_map_bind_id",
        ):
            if hasattr(self.root, attr):
                delattr(self.root, attr)
        try:
            self.root.state("normal")
        except Exception:
            pass
        self._show_login()
        show_login_window(self.root)
