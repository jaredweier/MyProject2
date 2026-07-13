"""Base page — every screen is a full-grid CTkFrame with optional scroll body."""

from __future__ import annotations

import customtkinter as ctk

from ui.theme import CONTENT_PAD, UI_BG, UI_TEXT_MUTED, font
from ui.widgets import Card, SectionHeader


class BasePage(ctk.CTkFrame):
    """Consistent layout: fill parent grid, optional header + scroll body."""

    page_key: str = ""

    def __init__(self, parent, app, **kwargs):
        kwargs.setdefault("fg_color", UI_BG)
        super().__init__(parent, **kwargs)
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._built = False

    def ensure_built(self) -> None:
        if not self._built:
            self.build()
            self._built = True

    def build(self) -> None:
        raise NotImplementedError

    def refresh(self) -> None:
        """Override to reload data when page is shown."""
        return

    def can(self, permission: str) -> bool:
        return self.app.can(permission)

    def is_officer(self) -> bool:
        return self.app._is_officer_role()

    def scroll_body(self) -> ctk.CTkScrollableFrame:
        """Full-page scroll host — use for stacked cards/lists."""
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.grid(row=0, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        return body

    def split_pane(self, left_weight: int = 2, right_weight: int = 3) -> tuple[ctk.CTkFrame, ctk.CTkFrame]:
        """Two-column layout filling the page (form | list)."""
        self.grid_columnconfigure(0, weight=left_weight)
        self.grid_columnconfigure(1, weight=right_weight)
        self.grid_rowconfigure(0, weight=1)
        left = ctk.CTkFrame(self, fg_color="transparent")
        right = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=1)
        return left, right

    def header_card(self, parent, title: str, subtitle: str = "", *, accent: bool = False) -> Card:
        card = Card(parent, accent=accent)
        SectionHeader(card.body, title, subtitle or None).pack(fill="x", padx=CONTENT_PAD, pady=CONTENT_PAD)
        return card

    def muted(self, parent, text: str) -> ctk.CTkLabel:
        return ctk.CTkLabel(parent, text=text, font=font("body"), text_color=UI_TEXT_MUTED, anchor="w")
