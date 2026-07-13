"""Login — split brand panel + secure access form."""

from __future__ import annotations

import customtkinter as ctk

from logic import authenticate_user
from ui.assets import load_logo_safe, load_team_photo
from ui.branding import get_department_branding
from ui.theme import (
    BTN_RADIUS,
    CARD_PAD,
    CORNER_RADIUS,
    DODGEVILLE_DANGER,
    UI_ACCENT_GLOW,
    UI_BG,
    UI_BORDER_GLOW,
    UI_SIDEBAR,
    UI_SURFACE,
    UI_SURFACE_LIGHT,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    font,
    micro_label,
)
from ui.widgets import PrimaryButton

_LOGIN_ENTRY_HEIGHT = 44


class LoginFrame(ctk.CTkFrame):
    def __init__(self, parent, on_success, **kwargs):
        super().__init__(parent, fg_color=UI_BG, **kwargs)
        self.on_success = on_success
        self._brand_images = []
        self._photo_label = None
        self._logo_label = None
        self._build()
        self.after_idle(self._paint_brand_images)
        self.after(180, self._repaint_brand_images_once)

    def _remember(self, image) -> None:
        if image is None:
            return
        if image not in self._brand_images:
            self._brand_images.append(image)

    def _paint_brand_images(self) -> None:
        if not self.winfo_exists():
            return
        try:
            if self._photo_label is not None and self._photo_label.winfo_exists():
                team = load_team_photo((520, 360), cover=True, rounded=False, border=False)
                if team:
                    self._remember(team)
                    self._photo_label.configure(image=team, text="")
                else:
                    self._photo_label.configure(
                        text="Place team_photo.jpg in the project folder.",
                        font=font("body"),
                        text_color=UI_TEXT_MUTED,
                        image=None,
                    )
            if self._logo_label is not None and self._logo_label.winfo_exists():
                logo = load_logo_safe((48, 48), initials="PD")
                if logo:
                    self._remember(logo)
                    self._logo_label.configure(image=logo, text="")
        except Exception:
            return

    def _repaint_brand_images_once(self) -> None:
        if getattr(self, "_brand_repaint_done", False):
            return
        self._brand_repaint_done = True
        if self.winfo_exists():
            self._paint_brand_images()

    def _build(self):
        self.grid_columnconfigure(0, weight=13, uniform="login")
        self.grid_columnconfigure(1, weight=7, uniform="login")
        self.grid_rowconfigure(0, weight=1)
        branding = get_department_branding()

        left = ctk.CTkFrame(self, fg_color=UI_SIDEBAR, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)
        self._photo_label = ctk.CTkLabel(left, text="", fg_color=UI_SIDEBAR, corner_radius=0)
        self._photo_label.grid(row=0, column=0, sticky="nsew")

        brand_strip = ctk.CTkFrame(left, fg_color=UI_SURFACE, corner_radius=0, height=140)
        brand_strip.grid(row=1, column=0, sticky="ew")
        brand_strip.grid_propagate(False)
        ctk.CTkFrame(brand_strip, fg_color=UI_ACCENT_GLOW, height=2, corner_radius=0).pack(fill="x")
        strip = ctk.CTkFrame(brand_strip, fg_color="transparent")
        strip.pack(fill="both", expand=True, padx=32, pady=18)
        strip.grid_columnconfigure(1, weight=1)
        self._logo_label = ctk.CTkLabel(strip, text="", width=52, height=52)
        self._logo_label.grid(row=0, column=0, rowspan=3, padx=(0, 14), sticky="n")
        micro_label(strip, "Authorized personnel only").grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(strip, text=branding["name"], font=font("heading"), text_color=UI_TEXT_PRIMARY, anchor="w").grid(
            row=1, column=1, sticky="ew", pady=(2, 0)
        )
        ctk.CTkLabel(
            strip, text=branding["tagline"], font=font("small"), text_color=UI_TEXT_MUTED, anchor="w", wraplength=420
        ).grid(row=2, column=1, sticky="ew", pady=(4, 0))

        right = ctk.CTkFrame(self, fg_color=UI_BG, corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew")
        ctk.CTkFrame(right, fg_color=UI_ACCENT_GLOW, width=3, corner_radius=0).place(relx=0, rely=0, relheight=1)
        form_outer = ctk.CTkFrame(right, fg_color="transparent")
        form_outer.place(relx=0.5, rely=0.5, anchor="center")
        micro_label(form_outer, "Secure access").pack(anchor="w", pady=(0, 8))
        ctk.CTkLabel(form_outer, text="Sign in", font=font("display"), text_color=UI_TEXT_PRIMARY, anchor="w").pack(
            anchor="w", pady=(0, 6)
        )
        ctk.CTkLabel(
            form_outer,
            text="Enterprise duty scheduling, coverage, and payroll.",
            font=font("body"),
            text_color=UI_TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w", pady=(0, 22))

        card = ctk.CTkFrame(
            form_outer,
            fg_color=UI_SURFACE,
            corner_radius=CORNER_RADIUS,
            border_width=1,
            border_color=UI_BORDER_GLOW,
            width=400,
        )
        card.pack(fill="x")
        card.grid_propagate(True)
        ctk.CTkFrame(card, fg_color=UI_ACCENT_GLOW, height=2, corner_radius=0).pack(fill="x")
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=CARD_PAD + 8, pady=CARD_PAD + 4)
        # Keep a readable minimum form width without collapsing height
        try:
            card.configure(width=400)
        except Exception:
            pass

        ctk.CTkLabel(inner, text="Username", font=font("small"), text_color=UI_TEXT_MUTED, anchor="w").pack(
            fill="x", pady=(0, 6)
        )
        self.username_entry = ctk.CTkEntry(
            inner,
            height=_LOGIN_ENTRY_HEIGHT,
            font=font("body"),
            border_color=UI_BORDER_GLOW,
            fg_color=UI_SURFACE_LIGHT,
            text_color=UI_TEXT_PRIMARY,
            placeholder_text="Username",
            corner_radius=BTN_RADIUS,
        )
        self.username_entry.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(inner, text="Password", font=font("small"), text_color=UI_TEXT_MUTED, anchor="w").pack(
            fill="x", pady=(0, 6)
        )
        self.password_entry = ctk.CTkEntry(
            inner,
            show="•",
            height=_LOGIN_ENTRY_HEIGHT,
            font=font("body"),
            border_color=UI_BORDER_GLOW,
            fg_color=UI_SURFACE_LIGHT,
            text_color=UI_TEXT_PRIMARY,
            placeholder_text="Password",
            corner_radius=BTN_RADIUS,
        )
        self.password_entry.pack(fill="x", pady=(0, 10))
        self.error_label = ctk.CTkLabel(inner, text="", font=font("small"), text_color=DODGEVILLE_DANGER, anchor="w")
        self.error_label.pack(fill="x", pady=(0, 10))
        PrimaryButton(inner, text="Sign in", command=self._submit).pack(fill="x")
        self.username_entry.bind("<Return>", lambda _e: self._submit())
        self.password_entry.bind("<Return>", lambda _e: self._submit())
        self.after(50, lambda: self.username_entry.focus_set())

    def _submit(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        auth = authenticate_user(username, password)
        if not auth.get("success"):
            self.error_label.configure(text=auth.get("message", "Invalid credentials"))
            return
        self.error_label.configure(text="")
        self.on_success(auth["user"])
