"""Login screen — enterprise split layout with department branding."""

import customtkinter as ctk

from logic import authenticate_user, list_login_users
from ui.assets import load_logo, load_team_photo
from ui.branding import get_department_branding
from ui.theme import (
    BTN_RADIUS,
    CARD_PAD,
    CORNER_RADIUS,
    DODGEVILLE_RED,
    UI_BG,
    UI_BORDER,
    UI_SURFACE,
    UI_SURFACE_LIGHT,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    font,
)
from ui.widgets import PrimaryButton

_LOGIN_ENTRY_HEIGHT = 44


class LoginFrame(ctk.CTkFrame):
    def __init__(self, parent, on_success, **kwargs):
        super().__init__(parent, fg_color=UI_BG, **kwargs)
        self.on_success = on_success
        self._brand_images = []
        self._photo_label = None
        self._build()
        self.after_idle(self._paint_brand_images)

    def _remember(self, image) -> None:
        if image is None:
            return
        if image not in self._brand_images:
            self._brand_images.append(image)
        top = self.winfo_toplevel()
        bucket = getattr(top, "_brand_images", None)
        if bucket is None:
            top._brand_images = []
            bucket = top._brand_images
        if image not in bucket:
            bucket.append(image)

    def _paint_brand_images(self) -> None:
        """Load images after the window is mapped — avoids blank CTkImage on first paint."""
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
        if hasattr(self, "_logo_label") and self._logo_label.winfo_exists():
            logo = load_logo((48, 48))
            if logo:
                self._remember(logo)
                self._logo_label.configure(image=logo, text="")

    def _build(self):
        self.grid_columnconfigure(0, weight=13, uniform="login")
        self.grid_columnconfigure(1, weight=7, uniform="login")
        self.grid_rowconfigure(0, weight=1)

        branding = get_department_branding()

        left = ctk.CTkFrame(self, fg_color="#06080C", corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)

        self._photo_label = ctk.CTkLabel(
            left,
            text="",
            fg_color="#06080C",
            corner_radius=0,
        )
        self._photo_label.grid(row=0, column=0, sticky="nsew")

        brand_strip = ctk.CTkFrame(left, fg_color=UI_SURFACE, corner_radius=0, height=132)
        brand_strip.grid(row=1, column=0, sticky="ew")
        brand_strip.grid_propagate(False)
        strip_inner = ctk.CTkFrame(brand_strip, fg_color="transparent")
        strip_inner.pack(fill="both", expand=True, padx=32, pady=20)
        strip_inner.grid_columnconfigure(1, weight=1)

        self._logo_label = ctk.CTkLabel(strip_inner, text="", width=48, height=48)
        self._logo_label.grid(row=0, column=0, rowspan=2, padx=(0, 14), sticky="n")
        ctk.CTkLabel(
            strip_inner,
            text=branding["name"],
            font=font("heading"),
            text_color=UI_TEXT_PRIMARY,
            anchor="w",
        ).grid(row=0, column=1, sticky="ew")
        self._login_mission_label = ctk.CTkLabel(
            strip_inner,
            text=branding["tagline"],
            font=font("small"),
            text_color=UI_TEXT_MUTED,
            anchor="w",
            wraplength=420,
        )
        self._login_mission_label.grid(row=1, column=1, sticky="ew", pady=(4, 0))

        right = ctk.CTkFrame(self, fg_color=UI_BG, corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)

        form_outer = ctk.CTkFrame(right, fg_color="transparent")
        form_outer.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            form_outer,
            text="Sign in",
            font=font("display"),
            text_color=UI_TEXT_PRIMARY,
            anchor="w",
        ).pack(anchor="w", pady=(0, 6))
        ctk.CTkLabel(
            form_outer,
            text="Dodgeville PD duty scheduling and payroll.",
            font=font("body"),
            text_color=UI_TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w", pady=(0, 24))

        card = ctk.CTkFrame(
            form_outer,
            fg_color=UI_SURFACE,
            corner_radius=CORNER_RADIUS,
            border_width=1,
            border_color=UI_BORDER,
            width=400,
        )
        card.pack()
        card.pack_propagate(False)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=CARD_PAD, pady=CARD_PAD)

        ctk.CTkLabel(inner, text="Username", font=font("small"), text_color=UI_TEXT_MUTED, anchor="w").pack(
            fill="x", pady=(0, 6)
        )
        self.username_entry = ctk.CTkEntry(
            inner,
            height=_LOGIN_ENTRY_HEIGHT,
            font=font("body"),
            border_color=UI_BORDER,
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
            border_color=UI_BORDER,
            fg_color=UI_SURFACE_LIGHT,
            text_color=UI_TEXT_PRIMARY,
            placeholder_text="Password",
            corner_radius=BTN_RADIUS,
        )
        self.password_entry.pack(fill="x", pady=(0, 10))
        self.password_entry.bind("<Return>", lambda e: self._submit())
        self.username_entry.bind("<Return>", lambda e: self._submit())

        self.error_label = ctk.CTkLabel(
            inner,
            text="",
            font=font("small"),
            text_color=DODGEVILLE_RED,
            wraplength=320,
            justify="left",
        )
        self.error_label.pack(fill="x", pady=(0, 12))

        PrimaryButton(inner, text="Sign in", height=44, command=self._submit).pack(fill="x")

        if not list_login_users():
            self.error_label.configure(
                text="No login accounts found. Run from the project folder or contact your administrator.",
            )
        self.after(200, lambda: self.username_entry.focus())

    def _submit(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        if not username:
            self.error_label.configure(text="Enter your username.")
            return
        if not password:
            self.error_label.configure(text="Enter your password.")
            return
        if not list_login_users():
            self.error_label.configure(
                text="No accounts configured. Delete dodgeville_scheduler.db and restart to reseed demo access.",
            )
            return
        result = authenticate_user(username, password)
        if not result.get("success"):
            self.error_label.configure(text=result.get("message", "Sign in failed. Check username and password."))
            return
        self.error_label.configure(text="")
        self.on_success(result["user"])
