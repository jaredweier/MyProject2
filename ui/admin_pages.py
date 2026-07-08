"""Administration pages — user management, setup, and forced password changes."""

from tkinter import messagebox

import customtkinter as ctk

from config import AUTO_LOGIN_ENABLED
from logic import (
    admin_reset_user_password,
    allowed_roles_for_actor,
    change_own_password,
    complete_initial_setup,
    create_app_user,
    get_officers_by_seniority,
    is_setup_complete,
    list_all_users,
    set_app_user_active,
    update_app_user,
)
from permissions import USER_ROLES
from ui.theme import (
    CARD_PAD,
    CORNER_RADIUS,
    DODGEVILLE_ACCENT,
    DODGEVILLE_BLUE,
    DODGEVILLE_DANGER,
    DODGEVILLE_GOLD,
    DODGEVILLE_SUCCESS,
    UI_BG,
    UI_BORDER,
    UI_SURFACE,
    UI_TEXT_MUTED,
    font,
)
from ui.widgets import Card, FormField, SectionHeader, StatusBadge


class AdminPageMixin:
    """User accounts and first-run setup."""

    def _can_manage_users(self) -> bool:
        return self.can("users.manage")

    def _can_edit_user_roles(self) -> bool:
        return self.can("users.edit_role") or self.can("users.manage")

    def _build_users(self):
        page = self.pages["users"]
        page.grid_columnconfigure(0, weight=1)
        page.grid_columnconfigure(1, weight=2)
        page.grid_rowconfigure(0, weight=1)

        if self._can_manage_users():
            form_card = Card(page)
            form_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
            SectionHeader(form_card.body, "Create Login", "Link accounts to officers").pack(
                fill="x", padx=CARD_PAD, pady=(CARD_PAD, 8)
            )
            form = ctk.CTkFrame(form_card.body, fg_color="transparent")
            form.pack(fill="x", padx=CARD_PAD, pady=(0, CARD_PAD))

            self._user_username = FormField(
                form, "Username", lambda p: ctk.CTkEntry(p, height=36, placeholder_text="jsmith")
            ).widget
            self._user_password = FormField(
                form, "Temporary Password", lambda p: ctk.CTkEntry(p, height=36, show="•")
            ).widget
            self._user_role = FormField(
                form, "Role", lambda p: ctk.CTkComboBox(p, height=36, values=list(USER_ROLES))
            ).widget
            self._user_role.set(USER_ROLES[0])

            officers = get_officers_by_seniority()
            officer_labels = ["None"] + [o["name"] for o in officers]
            self._user_officer_map = {o["name"]: o["id"] for o in officers}
            self._user_officer = FormField(
                form,
                "Linked Officer",
                lambda p: ctk.CTkComboBox(p, height=36, values=officer_labels),
            ).widget
            self._user_officer.set(officer_labels[0])

            ctk.CTkButton(
                form,
                text="Create User",
                height=38,
                corner_radius=8,
                fg_color=DODGEVILLE_ACCENT,
                command=self._create_app_user,
            ).pack(fill="x", pady=(12, 0))

        list_card = Card(page)
        list_col = 1 if self._can_manage_users() else 0
        list_card.grid(
            row=0,
            column=list_col,
            sticky="nsew",
            columnspan=2 if not self._can_manage_users() else 1,
        )
        if not self._can_manage_users():
            page.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(list_card.body, fg_color="transparent")
        hdr.pack(fill="x", padx=CARD_PAD, pady=(CARD_PAD, 8))
        list_subtitle = (
            "Change roles for Officer and Supervisor accounts"
            if self._can_edit_user_roles() and not self._can_manage_users()
            else "Deactivate instead of delete"
        )
        SectionHeader(hdr, "User Accounts", list_subtitle).pack(side="left")
        ctk.CTkButton(
            hdr,
            text="Refresh",
            height=32,
            fg_color=UI_BORDER,
            command=self.refresh_users,
        ).pack(side="right")
        self._users_scroll = ctk.CTkScrollableFrame(list_card.body, fg_color="transparent")
        self._users_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._user_row_widgets = {}

    def _refresh_user_officer_dropdown(self):
        if getattr(self, "_shell_building", False):
            return
        if not hasattr(self, "_user_officer"):
            return
        officers = get_officers_by_seniority()
        labels = ["None"] + [o["name"] for o in officers]
        self._user_officer_map = {o["name"]: o["id"] for o in officers}
        if hasattr(self, "_user_officer"):
            self._user_officer.configure(values=labels)
            if self._user_officer.get() not in labels:
                self._user_officer.set(labels[0])

    def refresh_users(self):
        if not hasattr(self, "_users_scroll"):
            return
        self._refresh_user_officer_dropdown()
        for widget in self._users_scroll.winfo_children():
            widget.destroy()
        self._user_row_widgets.clear()

        users = list_all_users()
        if not users:
            ctk.CTkLabel(
                self._users_scroll,
                text="No users configured.",
                font=font("body"),
                text_color=UI_TEXT_MUTED,
            ).pack(pady=20)
            return

        for user in users:
            self._render_user_row(user)

    def _render_user_row(self, user: dict):
        row = ctk.CTkFrame(self._users_scroll, fg_color=UI_SURFACE, corner_radius=8)
        row.pack(fill="x", pady=4)
        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=10)

        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text=user["username"], font=font("subheading"), anchor="w").pack(side="left")
        badges = ctk.CTkFrame(top, fg_color="transparent")
        badges.pack(side="right")
        StatusBadge(badges, user["role"]).pack(side="right", padx=(0, 6))
        StatusBadge(badges, "Active" if user.get("active") else "Inactive").pack(side="right")

        officer_name = user.get("officer_name") or "None"
        must_change = " · must change password" if user.get("must_change_password") else ""
        ctk.CTkLabel(
            inner,
            text=f"Officer: {officer_name}{must_change}",
            font=font("small"),
            text_color=UI_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", pady=(4, 0))

        btns = ctk.CTkFrame(inner, fg_color="transparent")
        btns.pack(fill="x", pady=(8, 0))
        can_edit = (
            self._can_edit_user_roles()
            and user["id"] != self.current_user.get("id")
            and (self._can_manage_users() or user["role"] != "Administration")
        )
        if user.get("active"):
            if can_edit:
                ctk.CTkButton(
                    btns,
                    text="Change Role",
                    width=100,
                    height=28,
                    fg_color=DODGEVILLE_ACCENT,
                    command=lambda u=user: self._edit_app_user(u),
                ).pack(side="left", padx=(0, 6))
            if self._can_manage_users():
                ctk.CTkButton(
                    btns,
                    text="Edit",
                    width=70,
                    height=28,
                    fg_color=DODGEVILLE_ACCENT,
                    command=lambda u=user: self._edit_app_user(u, full_edit=True),
                ).pack(side="left", padx=(0, 6))
                ctk.CTkButton(
                    btns,
                    text="Reset Password",
                    width=110,
                    height=28,
                    fg_color=DODGEVILLE_GOLD,
                    command=lambda u=user: self._reset_user_password(u),
                ).pack(side="left", padx=(0, 6))
                if user["id"] != self.current_user.get("id"):
                    ctk.CTkButton(
                        btns,
                        text="Deactivate",
                        width=90,
                        height=28,
                        fg_color=DODGEVILLE_DANGER,
                        command=lambda u=user: self._toggle_user_active(u, False),
                    ).pack(side="left")
        elif self._can_manage_users():
            ctk.CTkButton(
                btns,
                text="Reactivate",
                width=90,
                height=28,
                fg_color=DODGEVILLE_SUCCESS,
                command=lambda u=user: self._toggle_user_active(u, True),
            ).pack(side="left")

    def _create_app_user(self):
        if not self.can("users.manage"):
            messagebox.showwarning("Permission", "Administration access required.")
            return
        officer_label = self._user_officer.get()
        officer_id = self._user_officer_map.get(officer_label)
        result = create_app_user(
            self._user_username.get().strip(),
            self._user_password.get(),
            self._user_role.get(),
            officer_id=officer_id,
            actor_user_id=self.current_user.get("id"),
        )
        if result.get("success"):
            self._user_password.delete(0, "end")
            self.refresh_users()
            self.set_status(result.get("message", "User created"))
        else:
            messagebox.showerror("Create User", result.get("message", "Failed"))

    def _reset_user_password(self, user: dict):
        if not self._can_manage_users():
            messagebox.showwarning("Permission", "Administration access required.")
            return
        dialog = ctk.CTkInputDialog(
            text=f"New temporary password for {user['username']}:",
            title="Reset Password",
        )
        new_pw = dialog.get_input()
        if not new_pw:
            return
        result = admin_reset_user_password(
            user["id"],
            new_pw,
            actor_user_id=self.current_user.get("id"),
        )
        if result.get("success"):
            messagebox.showinfo("Reset Password", "User must change password at next login.")
            self.refresh_users()
        else:
            messagebox.showerror("Reset Password", result.get("message", "Failed"))

    def _edit_app_user(self, user: dict, full_edit: bool = False):
        if not self._can_edit_user_roles():
            messagebox.showwarning("Permission", "You cannot change user roles.")
            return
        if full_edit and not self._can_manage_users():
            messagebox.showwarning("Permission", "Administration access required.")
            return

        role_choices = allowed_roles_for_actor(self.current_user.get("id"))
        if user["role"] == "Administration" and not self._can_manage_users():
            messagebox.showwarning(
                "Permission",
                "Only administrators can modify Administration accounts.",
            )
            return
        if not role_choices:
            messagebox.showwarning("Permission", "No roles available to assign.")
            return

        show_officer_link = full_edit and self._can_manage_users()
        dialog = ctk.CTkToplevel(self.root)
        dialog.title(f"Edit User: {user['username']}")
        dialog.geometry("420x340" if show_officer_link else "420x240")
        dialog.configure(fg_color=UI_BG)
        dialog.transient(self.root)
        dialog.grab_set()

        card = ctk.CTkFrame(dialog, fg_color=UI_SURFACE, corner_radius=CORNER_RADIUS)
        card.pack(fill="both", expand=True, padx=20, pady=20)
        ctk.CTkLabel(card, text=user["username"], font=font("subheading")).pack(
            padx=CARD_PAD,
            pady=(CARD_PAD, 12),
        )

        ctk.CTkLabel(card, text="Role", font=font("small"), text_color=UI_TEXT_MUTED, anchor="w").pack(
            fill="x",
            padx=CARD_PAD,
        )
        role_combo = ctk.CTkComboBox(card, values=role_choices, height=36)
        role_combo.set(user["role"] if user["role"] in role_choices else role_choices[0])
        role_combo.pack(fill="x", padx=CARD_PAD, pady=(4, 12))

        officer_combo = None
        officer_map = {}
        clear_link = None
        if show_officer_link:
            ctk.CTkLabel(card, text="Linked Officer", font=font("small"), text_color=UI_TEXT_MUTED, anchor="w").pack(
                fill="x",
                padx=CARD_PAD,
            )
            officers = get_officers_by_seniority()
            officer_labels = ["None"] + [o["name"] for o in officers]
            officer_map = {o["name"]: o["id"] for o in officers}
            officer_combo = ctk.CTkComboBox(card, values=officer_labels, height=36)
            current_name = user.get("officer_name")
            officer_combo.set(current_name if current_name in officer_labels else officer_labels[0])
            officer_combo.pack(fill="x", padx=CARD_PAD, pady=(4, 8))

            clear_link = ctk.CTkCheckBox(card, text="Remove officer link", font=font("body"))
            clear_link.pack(anchor="w", padx=CARD_PAD, pady=(0, 8))

        err = ctk.CTkLabel(card, text="", font=font("small"), text_color=DODGEVILLE_DANGER)
        err.pack(fill="x", padx=CARD_PAD)

        def save():
            if show_officer_link and clear_link.get():
                result = update_app_user(
                    user["id"],
                    role=role_combo.get(),
                    clear_officer_link=True,
                    actor_user_id=self.current_user.get("id"),
                )
            elif show_officer_link:
                officer_label = officer_combo.get()
                officer_id = officer_map.get(officer_label)
                result = update_app_user(
                    user["id"],
                    role=role_combo.get(),
                    officer_id=officer_id,
                    actor_user_id=self.current_user.get("id"),
                )
            else:
                result = update_app_user(
                    user["id"],
                    role=role_combo.get(),
                    actor_user_id=self.current_user.get("id"),
                )
            if not result.get("success"):
                err.configure(text=result.get("message", "Update failed"))
                return
            dialog.destroy()
            self.refresh_users()
            self.set_status(result.get("message", "User updated"))

        ctk.CTkButton(
            card,
            text="Save Changes",
            height=38,
            fg_color=DODGEVILLE_ACCENT,
            command=save,
        ).pack(fill="x", padx=CARD_PAD, pady=(12, CARD_PAD))

        dialog.wait_window()

    def _toggle_user_active(self, user: dict, active: bool):
        if not self._can_manage_users():
            messagebox.showwarning("Permission", "Administration access required.")
            return
        verb = "reactivate" if active else "deactivate"
        if not messagebox.askyesno("Confirm", f"{verb.title()} {user['username']}?"):
            return
        result = set_app_user_active(
            user["id"],
            active,
            actor_user_id=self.current_user.get("id"),
        )
        if result.get("success"):
            self.refresh_users()
            self.set_status(result.get("message", "Updated"))
        else:
            messagebox.showerror("User Update", result.get("message", "Failed"))

    def _run_post_login_flow(self):
        if self.can("admin.settings") and not is_setup_complete():
            if AUTO_LOGIN_ENABLED:
                from logic import get_department_setting

                complete_initial_setup(
                    get_department_setting("department_name", "Dodgeville Police Department"),
                    actor_user_id=self.current_user.get("id"),
                )
            else:
                self._prompt_setup_wizard()

        from logic import maybe_run_auto_backup

        backup_path = maybe_run_auto_backup()
        if backup_path:
            self.set_status(f"Auto-backup saved: {backup_path}")

    def _prompt_forced_password_change(self) -> bool:
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Change Password Required")
        dialog.geometry("440x360")
        dialog.configure(fg_color=UI_BG)
        dialog.transient(self.root)
        dialog.grab_set()

        result = {"ok": False}
        username = self.current_user.get("username", "")

        def on_close():
            if messagebox.askyesno(
                "Sign Out?",
                "You must change your password before using the scheduler.\n"
                "Close anyway and return to the sign in screen?",
                parent=dialog,
            ):
                dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_close)

        card = ctk.CTkFrame(dialog, fg_color=UI_SURFACE, corner_radius=CORNER_RADIUS)
        card.pack(fill="both", expand=True, padx=20, pady=20)
        ctk.CTkLabel(
            card,
            text=f"Welcome, {username}",
            font=font("subheading"),
        ).pack(padx=CARD_PAD, pady=(CARD_PAD, 4))
        ctk.CTkLabel(
            card,
            text="Set a new password before continuing. Use your demo password as the current password.",
            font=font("body"),
            wraplength=360,
            text_color=UI_TEXT_MUTED,
        ).pack(padx=CARD_PAD, pady=(0, 12))

        cur = ctk.CTkEntry(card, height=36, show="•", placeholder_text="Current password")
        cur.pack(fill="x", padx=CARD_PAD, pady=4)
        new1 = ctk.CTkEntry(card, height=36, show="•", placeholder_text="New password")
        new1.pack(fill="x", padx=CARD_PAD, pady=4)
        new2 = ctk.CTkEntry(card, height=36, show="•", placeholder_text="Confirm new password")
        new2.pack(fill="x", padx=CARD_PAD, pady=4)
        err = ctk.CTkLabel(card, text="", font=font("small"), text_color=DODGEVILLE_DANGER)
        err.pack(fill="x", padx=CARD_PAD, pady=(4, 0))

        def submit():
            if new1.get() != new2.get():
                err.configure(text="New passwords do not match.")
                return
            change = change_own_password(
                self.current_user["id"],
                cur.get(),
                new1.get(),
            )
            if not change.get("success"):
                err.configure(text=change.get("message", "Failed"))
                return
            result["ok"] = True
            dialog.destroy()

        ctk.CTkButton(
            card,
            text="Update Password",
            height=38,
            fg_color=DODGEVILLE_ACCENT,
            command=submit,
        ).pack(fill="x", padx=CARD_PAD, pady=(12, CARD_PAD))

        dialog.wait_window()
        return result["ok"]

    def _prompt_setup_wizard(self):
        from config import DATE_INPUT_HINT, ROTATION_PRESETS
        from logic.rotation_config import (
            get_active_rotation_base_date,
            get_active_rotation_cycle_length,
            get_active_rotation_preset_name,
            get_preset_cycle_length,
            save_rotation_settings,
        )
        from ui.helpers import refresh_after_rotation_change
        from validators import format_date

        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Welcome: Department Setup")
        dialog.geometry("500x420")
        dialog.configure(fg_color=UI_BG)
        dialog.transient(self.root)
        dialog.grab_set()

        card = ctk.CTkFrame(dialog, fg_color=UI_SURFACE, corner_radius=CORNER_RADIUS)
        card.pack(fill="both", expand=True, padx=20, pady=20)
        ctk.CTkLabel(
            card,
            text="First-time setup",
            font=font("heading"),
        ).pack(padx=CARD_PAD, pady=(CARD_PAD, 4))
        ctk.CTkLabel(
            card,
            text="Set department name and rotation schedule. Changes apply to scheduling, requests, and payroll.",
            font=font("small"),
            text_color=UI_TEXT_MUTED,
            wraplength=420,
        ).pack(padx=CARD_PAD, pady=(0, 12))

        from logic import get_department_setting

        name_entry = ctk.CTkEntry(card, height=36, placeholder_text="Department name")
        name_entry.pack(fill="x", padx=CARD_PAD, pady=4)
        name_entry.insert(0, get_department_setting("department_name", "Dodgeville Police Department"))

        rot_frame = ctk.CTkFrame(card, fg_color="transparent")
        rot_frame.pack(fill="x", padx=CARD_PAD, pady=(8, 4))
        preset_var = ctk.StringVar(value=get_active_rotation_preset_name())
        ctk.CTkOptionMenu(rot_frame, variable=preset_var, values=list(ROTATION_PRESETS.keys()), width=260).pack(
            side="left", padx=(0, 8)
        )
        cycle_entry = ctk.CTkEntry(rot_frame, height=36, width=60)
        cycle_entry.insert(0, str(get_active_rotation_cycle_length()))
        cycle_entry.pack(side="left", padx=(0, 8))

        def _sync_preset(*_args):
            cycle_entry.delete(0, "end")
            cycle_entry.insert(0, str(get_preset_cycle_length(preset_var.get())))

        preset_var.trace_add("write", _sync_preset)

        base_entry = ctk.CTkEntry(card, height=36, placeholder_text=f"Rotation base date ({DATE_INPUT_HINT})")
        base_entry.pack(fill="x", padx=CARD_PAD, pady=4)
        base_entry.insert(0, format_date(get_active_rotation_base_date()))

        def finish():
            uid = self.current_user.get("id")
            try:
                cycle_len = int(cycle_entry.get().strip())
            except ValueError:
                messagebox.showerror("Setup", "Enter a valid rotation cycle length.", parent=dialog)
                return
            rot_result = save_rotation_settings(
                cycle_length=cycle_len,
                preset=preset_var.get().strip(),
                base_date_text=base_entry.get().strip(),
                user_id=uid,
            )
            if not rot_result.get("success"):
                messagebox.showerror("Setup", rot_result.get("message", "Rotation save failed"), parent=dialog)
                return
            result = complete_initial_setup(
                name_entry.get(),
                actor_user_id=uid,
            )
            if result.get("success"):
                refresh_after_rotation_change(self)
                dialog.destroy()
                self.set_status("Department setup complete")
            else:
                messagebox.showerror("Setup", result.get("message", "Failed"), parent=dialog)

        ctk.CTkButton(
            card,
            text="Complete Setup",
            height=38,
            fg_color=DODGEVILLE_BLUE,
            command=finish,
        ).pack(fill="x", padx=CARD_PAD, pady=(12, CARD_PAD))

        dialog.wait_window()
