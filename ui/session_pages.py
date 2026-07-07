"""Login, permissions, and session lifecycle."""

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
from ui.login import LoginFrame
from ui.window_layout import apply_main_window_layout


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
        if hasattr(self, "_sidebar_mission_label"):
            self._sidebar_mission_label.configure(text=branding["tagline"])
        if hasattr(self, "_hero_dept_label"):
            self._hero_dept_label.configure(text=branding["name"])
        if hasattr(self, "_hero_mission_label"):
            self._hero_mission_label.configure(text=branding["tagline"])

    def _bootstrap_session(self) -> None:
        init_database()
        if AUTO_LOGIN_ENABLED and self._try_dev_auto_login():
            return
        self._show_login()
        self.root.after(50, lambda: apply_main_window_layout(self.root))

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
        if getattr(self, "login_frame", None):
            self.login_frame.destroy()
            self.login_frame = None
        self._build_shell()
        self.root.after_idle(self._run_post_login_flow)
        if not self.current_user:
            return
        self._refresh_department_branding()
        self._apply_dashboard_role_layout()
        self.root.bind("<F5>", lambda e: self._refresh_current_page())
        self._bind_keyboard_shortcuts()
        self.root.after(100, lambda: apply_main_window_layout(self.root))
        self.show_page("dashboard")
        name = user.get("officer_name") or user.get("username")
        nav_count = len(self.nav_buttons) if hasattr(self, "nav_buttons") else 0
        status = f"Signed in as {name}"
        if nav_count > 1:
            status += (
                f"  ·  Ctrl+0 dashboard  ·  Ctrl+1–{min(nav_count, 9)} pages  ·  F5 refresh  ·  Ctrl+Shift+Q sign out"
            )
        self.set_status(status)

    def _teardown_shell_state(self) -> None:
        self.current_user = None
        if hasattr(self, "shell") and self.shell.winfo_exists():
            self.shell.destroy()
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
        self._show_login()
