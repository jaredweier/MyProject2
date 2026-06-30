"""Reusable UI components."""

import customtkinter as ctk

from ui.theme import (
    BTN_HEIGHT_COMPACT,
    BTN_HEIGHT_PRIMARY,
    BTN_HEIGHT_TOOLBAR,
    BTN_RADIUS,
    CARD_PAD,
    CONTENT_PAD,
    CORNER_RADIUS,
    DODGEVILLE_ACCENT,
    DODGEVILLE_DANGER,
    DODGEVILLE_GOLD,
    DODGEVILLE_SUCCESS,
    DODGEVILLE_WARNING,
    STATUS_COLORS,
    SUBNAV_HEIGHT,
    UI_ACCENT_GLOW,
    UI_BORDER,
    UI_NAV_TEXT,
    UI_SURFACE,
    UI_SURFACE_LIGHT,
    UI_TEXT_MUTED,
    font,
    tactical_stripe,
)


def _card_border_kwargs(kwargs: dict) -> dict:
    out = dict(kwargs)
    out.setdefault("border_width", 1)
    out.setdefault("border_color", UI_BORDER)
    return out


def _hover_accent() -> str:
    return "#0096B8"


class PrimaryButton(ctk.CTkButton):
    def __init__(self, parent, text, command=None, **kwargs):
        kwargs.setdefault("height", BTN_HEIGHT_PRIMARY)
        kwargs.setdefault("corner_radius", BTN_RADIUS)
        kwargs.setdefault("fg_color", DODGEVILLE_ACCENT)
        kwargs.setdefault("hover_color", _hover_accent())
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", UI_ACCENT_GLOW)
        super().__init__(parent, text=text, command=command, font=font("body"), **kwargs)


class SecondaryButton(ctk.CTkButton):
    def __init__(self, parent, text, command=None, **kwargs):
        kwargs.setdefault("height", BTN_HEIGHT_PRIMARY)
        kwargs.setdefault("corner_radius", BTN_RADIUS)
        kwargs.setdefault("fg_color", UI_BORDER)
        kwargs.setdefault("hover_color", DODGEVILLE_ACCENT)
        super().__init__(parent, text=text, command=command, font=font("body"), **kwargs)


class ToolbarButton(ctk.CTkButton):
    def __init__(self, parent, text, command=None, **kwargs):
        kwargs.setdefault("height", BTN_HEIGHT_TOOLBAR)
        kwargs.setdefault("corner_radius", BTN_RADIUS)
        kwargs.setdefault("fg_color", UI_SURFACE)
        kwargs.setdefault("hover_color", UI_BORDER)
        super().__init__(parent, text=text, command=command, font=font("small"), **kwargs)


class CompactButton(ctk.CTkButton):
    def __init__(self, parent, text, command=None, **kwargs):
        kwargs.setdefault("height", BTN_HEIGHT_COMPACT)
        kwargs.setdefault("corner_radius", 6)
        kwargs.setdefault("fg_color", UI_BORDER)
        kwargs.setdefault("hover_color", DODGEVILLE_ACCENT)
        super().__init__(parent, text=text, command=command, font=font("small"), **kwargs)


class StatCard(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        label,
        value,
        accent=DODGEVILLE_ACCENT,
        clickable=False,
        badge_style=False,
        **kwargs,
    ):
        super().__init__(
            parent,
            fg_color=UI_SURFACE,
            corner_radius=CORNER_RADIUS,
            **_card_border_kwargs(kwargs),
        )
        if clickable:
            self.configure(cursor="hand2")
        tactical_stripe(self)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        if badge_style:
            ctk.CTkFrame(body, fg_color=accent, width=3, corner_radius=0).pack(
                side="left",
                fill="y",
                padx=(0, 0),
                pady=0,
            )
            text_col = ctk.CTkFrame(body, fg_color="transparent")
            text_col.pack(side="left", fill="both", expand=True)
        else:
            text_col = body
        self.value_label = ctk.CTkLabel(text_col, text=value, font=font("stat_value"), text_color=accent)
        self.value_label.pack(anchor="w", padx=CARD_PAD, pady=(CARD_PAD, 0))
        from ui.helpers import title_case_ui

        self.label_label = ctk.CTkLabel(
            text_col,
            text=title_case_ui(label),
            font=font("stat_label"),
            text_color=UI_TEXT_MUTED,
        )
        self.label_label.pack(anchor="w", padx=CARD_PAD, pady=(0, CARD_PAD))

    def set_value(self, value):
        self.value_label.configure(text=value)

    def set_label(self, label):
        from ui.helpers import title_case_ui

        self.label_label.configure(text=title_case_ui(label))


class SectionHeader(ctk.CTkFrame):
    def __init__(self, parent, title, subtitle=None, **kwargs):
        from ui.helpers import title_case_ui

        super().__init__(parent, fg_color="transparent", **kwargs)
        self._title_label = ctk.CTkLabel(
            self,
            text=title_case_ui(title),
            font=font("heading"),
            anchor="w",
        )
        self._title_label.pack(fill="x")
        ctk.CTkFrame(self, fg_color=DODGEVILLE_ACCENT, height=2, corner_radius=0).pack(
            fill="x",
            pady=(6, 0),
        )
        self._subtitle_label = None
        if subtitle:
            self._subtitle_label = ctk.CTkLabel(
                self,
                text=title_case_ui(subtitle),
                font=font("body"),
                text_color=UI_TEXT_MUTED,
                anchor="w",
            )
            self._subtitle_label.pack(fill="x", pady=(2, 0))

    def configure(self, **kwargs):
        from ui.helpers import title_case_ui

        title = kwargs.pop("title", None)
        subtitle = kwargs.pop("subtitle", None)
        if title is not None:
            self._title_label.configure(text=title_case_ui(title))
        if subtitle is not None and self._subtitle_label is not None:
            self._subtitle_label.configure(text=title_case_ui(subtitle))
        if kwargs:
            super().configure(**kwargs)


class StatusBadge(ctk.CTkLabel):
    def __init__(self, parent, status, **kwargs):
        color = STATUS_COLORS.get(status, UI_TEXT_MUTED)
        super().__init__(
            parent,
            text=status,
            font=font("small"),
            fg_color=color,
            corner_radius=4,
            padx=10,
            pady=4,
            **kwargs,
        )


class CoverageBadge(ctk.CTkLabel):
    """Compact auto/manual coverage indicator (When I Work / Deputy style)."""

    def __init__(self, parent, auto_ok: bool, **kwargs):
        if auto_ok:
            text, color = "Auto OK", DODGEVILLE_SUCCESS
        else:
            text, color = "Needs Review", DODGEVILLE_WARNING
        super().__init__(
            parent,
            text=text,
            font=font("small"),
            fg_color=color,
            corner_radius=20,
            padx=10,
            pady=4,
            **kwargs,
        )


class ExpandableSection(ctk.CTkFrame):
    """Click-to-expand panel for secondary detail (accordion-style)."""

    def __init__(self, parent, title="More Details", start_expanded=False, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._title = title
        self._expanded = start_expanded
        self._toggle_btn = ctk.CTkButton(
            self,
            text=self._toggle_text(),
            anchor="w",
            fg_color="transparent",
            hover_color=UI_BORDER,
            text_color=UI_TEXT_MUTED,
            height=28,
            font=font("small"),
            command=self._toggle,
        )
        self._toggle_btn.pack(fill="x")
        self.body = ctk.CTkFrame(self, fg_color=UI_BORDER, corner_radius=8)
        if start_expanded:
            self.body.pack(fill="x", pady=(4, 0))

    def _toggle_text(self) -> str:
        arrow = "▼" if self._expanded else "▶"
        return f"{arrow}  {self._title}"

    def _toggle(self):
        self._expanded = not self._expanded
        if self._expanded:
            self.body.pack(fill="x", pady=(4, 0))
        else:
            self.body.pack_forget()
        self._toggle_btn.configure(text=self._toggle_text())


class Card(ctk.CTkFrame):
    """Surface card with optional accent stripe. Place content in `.body` (pack or grid)."""

    def __init__(self, parent, accent: bool = True, **kwargs):
        kwargs.setdefault("fg_color", UI_SURFACE)
        kwargs.setdefault("corner_radius", CORNER_RADIUS)
        super().__init__(parent, **_card_border_kwargs(kwargs))
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        row = 0
        if accent:
            stripe_host = ctk.CTkFrame(self, fg_color="transparent")
            stripe_host.grid(row=0, column=0, sticky="ew")
            tactical_stripe(stripe_host)
            row = 1
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=row, column=0, sticky="nsew")


class FormField(ctk.CTkFrame):
    def __init__(self, parent, label, widget_factory, **kwargs):
        from ui.helpers import title_case_ui

        super().__init__(parent, fg_color="transparent", **kwargs)
        ctk.CTkLabel(
            self,
            text=title_case_ui(label),
            font=font("small"),
            text_color=UI_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", pady=(0, 4))
        self.widget = widget_factory(self)
        self.widget.pack(fill="x")


class NavSectionLabel(ctk.CTkLabel):
    """Sidebar group heading — visual hierarchy / proximity grouping."""

    def __init__(self, parent, text, **kwargs):
        super().__init__(
            parent,
            text=text.upper(),
            font=font("nav_section"),
            text_color=DODGEVILLE_GOLD,
            anchor="w",
            **kwargs,
        )


class SegmentBar(ctk.CTkFrame):
    """Compact pill segment control for in-page view switching."""

    def __init__(self, parent, on_select, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._on_select = on_select
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._inner: ctk.CTkFrame | None = None

    def set_segments(self, segments: list[tuple[str, str]], active_key: str) -> None:
        from ui.helpers import title_case_ui

        for child in self.winfo_children():
            child.destroy()
        self._buttons.clear()
        if not segments:
            return
        shell = ctk.CTkFrame(self, fg_color=UI_BORDER, corner_radius=BTN_RADIUS)
        shell.pack(fill="x")
        self._inner = ctk.CTkFrame(shell, fg_color=UI_SURFACE, corner_radius=BTN_RADIUS)
        self._inner.pack(fill="x", padx=2, pady=2)
        for idx, (key, label) in enumerate(segments):
            self._inner.grid_columnconfigure(idx, weight=1)
            btn = ctk.CTkButton(
                self._inner,
                text=title_case_ui(label),
                height=30,
                corner_radius=BTN_RADIUS,
                font=font("small"),
                fg_color=DODGEVILLE_ACCENT if key == active_key else "transparent",
                hover_color=UI_SURFACE_LIGHT,
                text_color="#FFFFFF" if key == active_key else UI_NAV_TEXT,
                command=lambda k=key: self._on_select(k),
            )
            btn.grid(row=0, column=idx, sticky="ew", padx=2)
            self._buttons[key] = btn

    def set_active(self, key: str) -> None:
        for tab_key, btn in self._buttons.items():
            active = tab_key == key
            btn.configure(
                fg_color=DODGEVILLE_ACCENT if active else "transparent",
                text_color="#FFFFFF" if active else UI_NAV_TEXT,
            )


class SubNavBar(ctk.CTkFrame):
    """Horizontal tab strip for consolidated hub pages."""

    def __init__(self, parent, on_select, **kwargs):
        super().__init__(parent, fg_color="transparent", height=SUBNAV_HEIGHT, **kwargs)
        self._on_select = on_select
        self._buttons: dict[str, ctk.CTkButton] = {}
        self.grid_columnconfigure(0, weight=1)

    def set_tabs(self, tabs: list[tuple[str, str]], active_key: str) -> None:
        from ui.helpers import title_case_ui

        for child in self.winfo_children():
            child.destroy()
        self._buttons.clear()
        if not tabs:
            return
        row = ctk.CTkFrame(self, fg_color=UI_BORDER, corner_radius=BTN_RADIUS)
        row.pack(fill="x", padx=CONTENT_PAD, pady=(0, 8))
        inner = ctk.CTkFrame(row, fg_color=UI_SURFACE, corner_radius=BTN_RADIUS)
        inner.pack(fill="x", padx=2, pady=2)
        for idx, (key, label) in enumerate(tabs):
            inner.grid_columnconfigure(idx, weight=1)
            btn = ctk.CTkButton(
                inner,
                text=title_case_ui(label),
                height=30,
                corner_radius=BTN_RADIUS,
                font=font("small"),
                fg_color=DODGEVILLE_ACCENT if key == active_key else "transparent",
                hover_color=UI_SURFACE_LIGHT,
                text_color="#FFFFFF" if key == active_key else UI_NAV_TEXT,
                command=lambda k=key: self._on_select(k),
            )
            btn.grid(row=0, column=idx, sticky="ew", padx=2)
            self._buttons[key] = btn

    def set_active(self, key: str) -> None:
        for tab_key, btn in self._buttons.items():
            active = tab_key == key
            btn.configure(
                fg_color=DODGEVILLE_ACCENT if active else "transparent",
                text_color="#FFFFFF" if active else UI_NAV_TEXT,
            )


class NavButton(ctk.CTkButton):
    def __init__(self, parent, text, icon, command, **kwargs):
        self._base_text = text
        super().__init__(
            parent,
            text=f"  {icon}  {text}",
            anchor="w",
            height=38,
            corner_radius=BTN_RADIUS,
            font=font("nav"),
            fg_color="transparent",
            hover_color=UI_SURFACE_LIGHT,
            text_color=UI_NAV_TEXT,
            border_width=0,
            command=command,
            **kwargs,
        )
        self._active = False
        self._icon = icon

    def set_active(self, active: bool):
        self._active = active
        if active:
            self.configure(
                fg_color=UI_SURFACE_LIGHT,
                border_width=2,
                border_color=DODGEVILLE_GOLD,
                text_color=UI_ACCENT_GLOW,
            )
        else:
            self.configure(
                fg_color="transparent",
                border_width=0,
                text_color=UI_NAV_TEXT,
            )

    def set_badge(self, count: int = 0):
        label = self._base_text
        if count > 0:
            label = f"{self._base_text}  ({count})"
        self.configure(text=f"  {self._icon}  {label}")


class SearchBar(ctk.CTkEntry):
    def __init__(self, parent, placeholder="Search...", **kwargs):
        super().__init__(
            parent,
            placeholder_text=placeholder,
            height=36,
            corner_radius=8,
            border_color=UI_BORDER,
            **kwargs,
        )


class AlertBanner(ctk.CTkFrame):
    """Inline alert strip for dashboard and reports (Deputy / When I Work style)."""

    _COLORS = {
        "critical": DODGEVILLE_DANGER,
        "warning": DODGEVILLE_WARNING,
        "info": DODGEVILLE_ACCENT,
        "success": DODGEVILLE_SUCCESS,
    }

    def __init__(self, parent, message: str, severity: str = "info", **kwargs):
        color = self._COLORS.get(severity, DODGEVILLE_ACCENT)
        kwargs.setdefault("corner_radius", BTN_RADIUS)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", UI_ACCENT_GLOW if severity == "info" else color)
        super().__init__(parent, fg_color=color, **kwargs)
        ctk.CTkLabel(
            self,
            text=message,
            font=font("body"),
            text_color="#FFFFFF",
            anchor="w",
        ).pack(fill="x", padx=14, pady=10)


class MetricRow(ctk.CTkFrame):
    """Horizontal metric chips for analytics sections."""

    def __init__(self, parent, metrics: list, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        for label, value, accent in metrics:
            chip = ctk.CTkFrame(
                self, fg_color=UI_SURFACE, corner_radius=BTN_RADIUS, border_width=1, border_color=UI_BORDER
            )
            chip.pack(side="left", padx=(0, 8), pady=2)
            ctk.CTkLabel(
                chip,
                text=str(value),
                font=font("subheading"),
                text_color=accent,
            ).pack(padx=14, pady=(10, 0))
            ctk.CTkLabel(
                chip,
                text=label,
                font=font("small"),
                text_color=UI_TEXT_MUTED,
            ).pack(padx=14, pady=(0, 10))
