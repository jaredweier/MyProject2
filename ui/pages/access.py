"""Access control — user list + basic create."""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from logic import create_app_user, list_login_users
from permissions import USER_ROLES
from ui.pages.base import BasePage
from ui.theme import CARD_PAD, UI_BORDER, UI_SURFACE, UI_TEXT_MUTED, font
from ui.widgets import Card, EmptyState, FormField, PrimaryButton, SectionHeader, StatusBadge


class AccessPage(BasePage):
    page_key = "users"

    def build(self) -> None:
        if not (self.can("users.manage") or self.can("users.edit_role")):
            EmptyState(self, "No access", "User administration requires elevated permission.").grid(
                row=0, column=0, sticky="nsew", padx=24, pady=24
            )
            return
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        left = Card(self)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        SectionHeader(left.body, "Users", "Active logins").pack(fill="x", padx=CARD_PAD, pady=CARD_PAD)
        self._list = ctk.CTkScrollableFrame(left.body, fg_color="transparent")
        self._list.pack(fill="both", expand=True, padx=8, pady=(0, CARD_PAD))

        right = Card(self, accent=True)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        SectionHeader(right.body, "Create user", "Username, password, role").pack(
            fill="x", padx=CARD_PAD, pady=CARD_PAD
        )
        form = ctk.CTkFrame(right.body, fg_color="transparent")
        form.pack(fill="x", padx=CARD_PAD)
        self.u_name = FormField(form, "Username", lambda p: ctk.CTkEntry(p, height=34)).widget
        self.u_pass = FormField(form, "Password", lambda p: ctk.CTkEntry(p, height=34, show="•")).widget
        self.u_role = FormField(
            form,
            "Role",
            lambda p: ctk.CTkComboBox(p, height=34, values=list(USER_ROLES), state="readonly"),
        ).widget
        self.u_role.set("Officer")
        PrimaryButton(right.body, text="Create user", command=self._create).pack(fill="x", padx=CARD_PAD, pady=CARD_PAD)

    def refresh(self) -> None:
        if not (self.can("users.manage") or self.can("users.edit_role")):
            return
        for w in self._list.winfo_children():
            w.destroy()
        users = list_login_users()
        if not users:
            EmptyState(self._list, "No users", "Create a login account.").pack(fill="x", pady=12)
            return
        for u in users:
            row = ctk.CTkFrame(self._list, fg_color=UI_SURFACE, corner_radius=8, border_width=1, border_color=UI_BORDER)
            row.pack(fill="x", pady=3, padx=4)
            inner = ctk.CTkFrame(row, fg_color="transparent")
            inner.pack(fill="x", padx=12, pady=10)
            ctk.CTkLabel(inner, text=u.get("username", ""), font=font("subheading"), anchor="w").pack(side="left")
            StatusBadge(inner, u.get("role") or "Officer").pack(side="right")
            if u.get("officer_name"):
                ctk.CTkLabel(
                    row, text=f"Linked: {u['officer_name']}", font=font("small"), text_color=UI_TEXT_MUTED, anchor="w"
                ).pack(fill="x", padx=12, pady=(0, 8))

    def _create(self):
        if not self.can("users.manage"):
            messagebox.showwarning("Permission", "Only administration can create users.")
            return
        result = create_app_user(
            self.u_name.get().strip(),
            self.u_pass.get(),
            self.u_role.get(),
            actor_user_id=self.app.current_user.get("id") if self.app.current_user else None,
        )
        if result.get("success"):
            self.app.set_status(result.get("message", "User created"), level="success")
            self.u_name.delete(0, "end")
            self.u_pass.delete(0, "end")
            self.refresh()
        else:
            messagebox.showerror("Create user", result.get("message", "Failed"))
