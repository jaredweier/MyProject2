"""Login screen for role-based access."""

import customtkinter as ctk

from logic import authenticate_user, list_login_users
from ui.assets import load_logo, load_team_photo
from ui.branding import get_department_branding
from ui.helpers import title_case_ui
from ui.theme import (
    CARD_PAD,
    CORNER_RADIUS,
    DODGEVILLE_BLUE,
    DODGEVILLE_GOLD,
    DODGEVILLE_RED,
    UI_ACCENT_GLOW,
    UI_BG,
    UI_BORDER,
    UI_SURFACE,
    UI_TEXT_LIGHT,
    UI_TEXT_MUTED,
    font,
    tactical_stripe,
)
from ui.widgets import PrimaryButton


class LoginFrame(ctk.CTkFrame):
    def __init__(self, parent, on_success, **kwargs):
        super().__init__(parent, fg_color=UI_BG, **kwargs)
        self.on_success = on_success
        self._brand_images = []
        self._build()

    def _remember(self, image) -> None:
        if image is not None and image not in self._brand_images:
            self._brand_images.append(image)

    def _build(self):
        self.grid_columnconfigure(0, weight=3, minsize=520)
        self.grid_columnconfigure(1, weight=2, minsize=420)
        self.grid_rowconfigure(0, weight=1)

        branding = get_department_branding()

        left = ctk.CTkFrame(self, fg_color=DODGEVILLE_BLUE, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        stripe_host = ctk.CTkFrame(left, fg_color="transparent", height=3)
        stripe_host.grid(row=0, column=0, sticky="ew")
        tactical_stripe(stripe_host)

        photo_panel = ctk.CTkFrame(left, fg_color="transparent")
        photo_panel.grid(row=1, column=0, sticky="nsew", padx=28, pady=(24, 16))
        photo_panel.grid_rowconfigure(0, weight=1)
        photo_panel.grid_columnconfigure(0, weight=1)

        team = load_team_photo((640, 420), cover=True, rounded=True, border=True)
        if team:
            self._remember(team)
            ctk.CTkLabel(photo_panel, text="", image=team).grid(row=0, column=0, sticky="nsew")
        else:
            ctk.CTkLabel(
                photo_panel,
                text="Department team photo not found.\nPlace team_photo.jpg next to the app.",
                font=font("body"),
                text_color=UI_TEXT_MUTED,
                justify="center",
            ).grid(row=0, column=0)

        brand_footer = ctk.CTkFrame(
            left,
            fg_color=UI_SURFACE,
            corner_radius=CORNER_RADIUS,
            border_width=1,
            border_color=UI_BORDER,
        )
        brand_footer.grid(row=2, column=0, sticky="ew", padx=28, pady=(0, 28))
        brand_footer.grid_columnconfigure(1, weight=1)

        logo = load_logo((96, 96))
        if logo:
            self._remember(logo)
            ctk.CTkLabel(brand_footer, text="", image=logo).grid(
                row=0,
                column=0,
                rowspan=2,
                padx=(20, 16),
                pady=20,
                sticky="n",
            )

        ctk.CTkLabel(
            brand_footer,
            text=branding["name"],
            font=font("heading"),
            text_color="#FFFFFF",
            anchor="w",
        ).grid(row=0, column=1, sticky="ew", padx=(0, 20), pady=(20, 4))
        self._login_mission_label = ctk.CTkLabel(
            brand_footer,
            text=title_case_ui(branding["tagline"]),
            font=font("body"),
            text_color=DODGEVILLE_GOLD,
            anchor="w",
            wraplength=420,
        )
        self._login_mission_label.grid(row=1, column=1, sticky="ew", padx=(0, 20), pady=(0, 20))

        right = ctk.CTkFrame(self, fg_color=UI_BG, corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)

        card = ctk.CTkFrame(
            right,
            fg_color=UI_SURFACE,
            corner_radius=CORNER_RADIUS,
            border_width=2,
            border_color=DODGEVILLE_GOLD,
            width=440,
            height=520,
        )
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)
        tactical_stripe(card)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=CARD_PAD + 8, pady=CARD_PAD + 8)

        card_logo = load_logo((72, 72))
        if card_logo:
            self._remember(card_logo)
            ctk.CTkLabel(inner, text="", image=card_logo).pack(pady=(12, 8))

        ctk.CTkLabel(
            inner,
            text="Sign In",
            font=font("heading"),
            text_color=UI_ACCENT_GLOW,
        ).pack(pady=(0, 6))
        ctk.CTkLabel(
            inner,
            text=title_case_ui(branding["tagline"]),
            font=font("body"),
            text_color=UI_TEXT_LIGHT,
            wraplength=360,
        ).pack(pady=(0, 20))

        form = ctk.CTkFrame(inner, fg_color="transparent")
        form.pack(fill="x")

        ctk.CTkLabel(
            form,
            text="Username",
            font=font("body"),
            text_color=UI_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", pady=(0, 6))
        self.username_entry = ctk.CTkEntry(form, height=44, font=font("body"), border_color=UI_BORDER)
        self.username_entry.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            form,
            text="Password",
            font=font("body"),
            text_color=UI_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", pady=(0, 6))
        self.password_entry = ctk.CTkEntry(
            form,
            height=44,
            show="•",
            font=font("body"),
            border_color=UI_BORDER,
        )
        self.password_entry.pack(fill="x", pady=(0, 12))
        self.password_entry.bind("<Return>", lambda e: self._submit())
        self.username_entry.bind("<Return>", lambda e: self._submit())

        self.error_label = ctk.CTkLabel(
            form,
            text="",
            font=font("body"),
            text_color=DODGEVILLE_RED,
            wraplength=360,
        )
        self.error_label.pack(fill="x", pady=(0, 12))

        PrimaryButton(form, text="Sign In", height=44, command=self._submit).pack(fill="x")

        if not list_login_users():
            self.error_label.configure(
                text="No login accounts found. Run from the project folder or contact your administrator.",
            )

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
                text="No accounts are configured. Delete dodgeville_scheduler.db and restart to reseed demo access.",
            )
            return
        result = authenticate_user(username, password)
        if not result.get("success"):
            self.error_label.configure(text=result.get("message", "Sign in failed. Check username and password."))
            return
        self.error_label.configure(text="")
        self.on_success(result["user"])
