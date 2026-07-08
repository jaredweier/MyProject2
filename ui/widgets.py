"""Reusable UI components — modern law-enforcement design system."""

import customtkinter as ctk

from ui.icons import render_icon
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
    DODGEVILLE_SUCCESS,
    DODGEVILLE_WARNING,
    FONT_FAMILY,
    STATUS_COLORS,
    SUBNAV_HEIGHT,
    UI_ACCENT_SUBTLE,
    UI_BORDER,
    UI_NAV_ACTIVE,
    UI_SURFACE,
    UI_SURFACE_LIGHT,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    font,
)


def _card_border_kwargs(kwargs: dict) -> dict:
    out = dict(kwargs)
    out.setdefault("border_width", 1)
    out.setdefault("border_color", UI_BORDER)
    return out


def _hover_accent() -> str:
    return UI_ACCENT_SUBTLE


class PrimaryButton(ctk.CTkButton):
    def __init__(self, parent, text, command=None, **kwargs):
        kwargs.setdefault("height", BTN_HEIGHT_PRIMARY)
        kwargs.setdefault("corner_radius", BTN_RADIUS)
        kwargs.setdefault("fg_color", DODGEVILLE_ACCENT)
        kwargs.setdefault("hover_color", _hover_accent())
        kwargs.setdefault("text_color", "#FFFFFF")
        kwargs.setdefault("border_width", 0)
        super().__init__(
            parent,
            text=text,
            command=command,
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            **kwargs,
        )


class SecondaryButton(ctk.CTkButton):
    def __init__(self, parent, text, command=None, **kwargs):
        kwargs.setdefault("height", BTN_HEIGHT_PRIMARY)
        kwargs.setdefault("corner_radius", BTN_RADIUS)
        kwargs.setdefault("fg_color", UI_SURFACE_LIGHT)
        kwargs.setdefault("hover_color", UI_BORDER)
        kwargs.setdefault("text_color", UI_TEXT_PRIMARY)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", UI_BORDER)
        super().__init__(parent, text=text, command=command, font=font("body"), **kwargs)


class ToolbarButton(ctk.CTkButton):
    def __init__(self, parent, text, command=None, **kwargs):
        kwargs.setdefault("height", BTN_HEIGHT_TOOLBAR)
        kwargs.setdefault("corner_radius", BTN_RADIUS)
        kwargs.setdefault("fg_color", UI_SURFACE_LIGHT)
        kwargs.setdefault("hover_color", UI_BORDER)
        kwargs.setdefault("text_color", UI_TEXT_PRIMARY)
        kwargs.setdefault("border_width", 0)
        super().__init__(parent, text=text, command=command, font=font("small"), **kwargs)


class CompactButton(ctk.CTkButton):
    def __init__(self, parent, text, command=None, **kwargs):
        kwargs.setdefault("height", BTN_HEIGHT_COMPACT)
        kwargs.setdefault("corner_radius", BTN_RADIUS)
        kwargs.setdefault("fg_color", UI_SURFACE_LIGHT)
        kwargs.setdefault("hover_color", UI_BORDER)
        kwargs.setdefault("text_color", UI_TEXT_PRIMARY)
        kwargs.setdefault("border_width", 0)
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
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=CARD_PAD, pady=14)
        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x")
        self.label_label = ctk.CTkLabel(
            top,
            text=label,
            font=font("stat_label"),
            text_color=UI_TEXT_MUTED,
            anchor="w",
        )
        self.label_label.pack(side="left")
        ctk.CTkFrame(top, fg_color=accent, width=6, height=6, corner_radius=3).pack(side="right")
        self.value_label = ctk.CTkLabel(
            inner,
            text=value,
            font=font("stat_value"),
            text_color=UI_TEXT_PRIMARY,
            anchor="w",
        )
        self.value_label.pack(anchor="w", pady=(8, 0))

    def set_value(self, value):
        self.value_label.configure(text=value)

    def set_label(self, label):
        self.label_label.configure(text=label)


class SectionHeader(ctk.CTkFrame):
    def __init__(self, parent, title, subtitle=None, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._title_label = ctk.CTkLabel(
            self,
            text=title,
            font=font("heading"),
            text_color=UI_TEXT_PRIMARY,
            anchor="w",
        )
        self._title_label.pack(fill="x")
        self._subtitle_label = None
        if subtitle:
            self._subtitle_label = ctk.CTkLabel(
                self,
                text=subtitle,
                font=font("small"),
                text_color=UI_TEXT_MUTED,
                anchor="w",
            )
            self._subtitle_label.pack(fill="x", pady=(4, 0))

    def configure(self, **kwargs):
        title = kwargs.pop("title", None)
        subtitle = kwargs.pop("subtitle", None)
        if title is not None:
            self._title_label.configure(text=title)
        if subtitle is not None and self._subtitle_label is not None:
            self._subtitle_label.configure(text=subtitle)
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
            text_color="#FFFFFF",
            corner_radius=6,
            padx=10,
            pady=4,
            **kwargs,
        )


class CoverageBadge(ctk.CTkLabel):
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
            text_color="#FFFFFF",
            corner_radius=20,
            padx=10,
            pady=4,
            **kwargs,
        )


class ExpandableSection(ctk.CTkFrame):
    def __init__(self, parent, title="More Details", start_expanded=False, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._title = title
        self._expanded = start_expanded
        self._toggle_btn = ctk.CTkButton(
            self,
            text=self._toggle_text(),
            anchor="w",
            fg_color="transparent",
            hover_color=UI_SURFACE_LIGHT,
            text_color=UI_TEXT_MUTED,
            height=28,
            font=font("small"),
            command=self._toggle,
        )
        self._toggle_btn.pack(fill="x")
        self.body = ctk.CTkFrame(self, fg_color=UI_SURFACE_LIGHT, corner_radius=BTN_RADIUS)
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
    """Elevated surface card. Place content in `.body`."""

    def __init__(self, parent, accent: bool = False, **kwargs):
        kwargs.setdefault("fg_color", UI_SURFACE)
        kwargs.setdefault("corner_radius", CORNER_RADIUS)
        super().__init__(parent, **_card_border_kwargs(kwargs))
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=0, column=0, sticky="nsew")


class FormField(ctk.CTkFrame):
    def __init__(self, parent, label, widget_factory, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        ctk.CTkLabel(
            self,
            text=label,
            font=font("small"),
            text_color=UI_TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", pady=(0, 6))
        self.widget = widget_factory(self)
        self.widget.pack(fill="x")


class NavSectionLabel(ctk.CTkLabel):
    def __init__(self, parent, text, **kwargs):
        super().__init__(
            parent,
            text=text,
            font=font("nav_section"),
            text_color=UI_TEXT_MUTED,
            anchor="w",
            **kwargs,
        )


class SegmentBar(ctk.CTkFrame):
    def __init__(self, parent, on_select, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._on_select = on_select
        self._buttons: dict[str, ctk.CTkButton] = {}

    def set_segments(self, segments: list[tuple[str, str]], active_key: str) -> None:
        for child in self.winfo_children():
            child.destroy()
        self._buttons.clear()
        if not segments:
            return
        shell = ctk.CTkFrame(self, fg_color=UI_SURFACE_LIGHT, corner_radius=BTN_RADIUS)
        shell.pack(fill="x")
        inner = ctk.CTkFrame(shell, fg_color="transparent")
        inner.pack(fill="x", padx=3, pady=3)
        for idx, (key, label) in enumerate(segments):
            inner.grid_columnconfigure(idx, weight=1)
            active = key == active_key
            btn = ctk.CTkButton(
                inner,
                text=label,
                height=30,
                corner_radius=BTN_RADIUS,
                font=font("small"),
                fg_color=UI_NAV_ACTIVE if active else "transparent",
                hover_color=UI_BORDER,
                text_color=UI_TEXT_PRIMARY if active else UI_TEXT_MUTED,
                command=lambda k=key: self._on_select(k),
            )
            btn.grid(row=0, column=idx, sticky="ew", padx=2)
            self._buttons[key] = btn

    def set_active(self, key: str) -> None:
        for tab_key, btn in self._buttons.items():
            active = tab_key == key
            btn.configure(
                fg_color=UI_NAV_ACTIVE if active else "transparent",
                text_color=UI_TEXT_PRIMARY if active else UI_TEXT_MUTED,
            )


class SubNavBar(ctk.CTkFrame):
    def __init__(self, parent, on_select, **kwargs):
        super().__init__(parent, fg_color="transparent", height=SUBNAV_HEIGHT, **kwargs)
        self._on_select = on_select
        self._buttons: dict[str, ctk.CTkButton] = {}
        self.grid_columnconfigure(0, weight=1)

    def set_tabs(self, tabs: list[tuple[str, str]], active_key: str) -> None:
        for child in self.winfo_children():
            child.destroy()
        self._buttons.clear()
        if not tabs:
            return
        row = ctk.CTkFrame(self, fg_color=UI_SURFACE_LIGHT, corner_radius=BTN_RADIUS)
        row.pack(fill="x", padx=CONTENT_PAD, pady=(0, 10))
        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="x", padx=3, pady=3)
        for idx, (key, label) in enumerate(tabs):
            inner.grid_columnconfigure(idx, weight=1)
            active = key == active_key
            btn = ctk.CTkButton(
                inner,
                text=label,
                height=30,
                corner_radius=BTN_RADIUS,
                font=font("small"),
                fg_color=UI_NAV_ACTIVE if active else "transparent",
                hover_color=UI_BORDER,
                text_color=UI_TEXT_PRIMARY if active else UI_TEXT_MUTED,
                command=lambda k=key: self._on_select(k),
            )
            btn.grid(row=0, column=idx, sticky="ew", padx=2)
            self._buttons[key] = btn

    def set_active(self, key: str) -> None:
        for tab_key, btn in self._buttons.items():
            active = tab_key == key
            btn.configure(
                fg_color=UI_NAV_ACTIVE if active else "transparent",
                text_color=UI_TEXT_PRIMARY if active else UI_TEXT_MUTED,
            )


class NavButton(ctk.CTkFrame):
    """Sidebar row with stroke icon + label."""

    def __init__(self, parent, text, icon, command, nav_key: str = "", **kwargs):
        super().__init__(parent, fg_color="transparent", height=36, **kwargs)
        self._base_text = text
        self._command = command
        self._active = False
        self._nav_key = nav_key

        self._row = ctk.CTkFrame(self, fg_color="transparent", corner_radius=BTN_RADIUS, cursor="hand2")
        self._row.pack(fill="x", padx=4, pady=1)
        self._row.bind("<Button-1>", lambda _e: self._invoke())
        self._row.grid_columnconfigure(1, weight=1)

        self._icon_label = ctk.CTkLabel(self._row, text="", width=20)
        self._icon_label.grid(row=0, column=0, padx=(10, 8), pady=8)
        self._icon_label.bind("<Button-1>", lambda _e: self._invoke())

        self._label = ctk.CTkLabel(
            self._row,
            text=text,
            font=font("nav"),
            text_color=UI_TEXT_MUTED,
            anchor="w",
        )
        self._label.grid(row=0, column=1, sticky="ew", pady=8)
        self._label.bind("<Button-1>", lambda _e: self._invoke())

        self._count_label = ctk.CTkLabel(
            self._row,
            text="",
            font=font("small"),
            text_color="#FFFFFF",
            fg_color=DODGEVILLE_ACCENT,
            corner_radius=8,
            width=20,
            height=18,
        )
        self._count_label.grid(row=0, column=2, padx=(4, 10))
        self._count_label.grid_remove()
        self._count_label.bind("<Button-1>", lambda _e: self._invoke())

        self._set_icon(active=False)

    def _invoke(self) -> None:
        if self._command:
            self._command()

    def _set_icon(self, *, active: bool) -> None:
        color = DODGEVILLE_ACCENT if active else UI_TEXT_MUTED
        icon_img = render_icon(self._nav_key, size=18, color=color)
        if icon_img:
            self._icon_label.configure(image=icon_img)
        else:
            self._icon_label.configure(image=None, text="·", text_color=color)

    def set_active(self, active: bool):
        self._active = active
        if active:
            self._row.configure(fg_color=UI_NAV_ACTIVE)
            self._label.configure(text_color=UI_TEXT_PRIMARY, font=font("nav"))
        else:
            self._row.configure(fg_color="transparent")
            self._label.configure(text_color=UI_TEXT_MUTED, font=font("nav"))
        self._set_icon(active=active)

    def set_badge(self, count: int = 0):
        if count > 0:
            self._count_label.configure(text=str(count) if count < 100 else "99+")
            self._count_label.grid()
        else:
            self._count_label.grid_remove()
        self._label.configure(text=self._base_text)


class SearchBar(ctk.CTkEntry):
    def __init__(self, parent, placeholder="Search...", **kwargs):
        super().__init__(
            parent,
            placeholder_text=placeholder,
            height=36,
            corner_radius=BTN_RADIUS,
            border_color=UI_BORDER,
            fg_color=UI_SURFACE_LIGHT,
            text_color=UI_TEXT_PRIMARY,
            **kwargs,
        )


class AlertBanner(ctk.CTkFrame):
    _COLORS = {
        "critical": DODGEVILLE_DANGER,
        "warning": DODGEVILLE_WARNING,
        "info": DODGEVILLE_ACCENT,
        "success": DODGEVILLE_SUCCESS,
    }

    def __init__(self, parent, message: str, severity: str = "info", **kwargs):
        color = self._COLORS.get(severity, DODGEVILLE_ACCENT)
        kwargs.setdefault("corner_radius", BTN_RADIUS)
        kwargs.setdefault("border_width", 0)
        super().__init__(parent, fg_color=UI_SURFACE, **kwargs)
        bar = ctk.CTkFrame(self, fg_color=color, width=4, corner_radius=2)
        bar.pack(side="left", fill="y")
        ctk.CTkLabel(
            self,
            text=message,
            font=font("body"),
            text_color=UI_TEXT_PRIMARY,
            anchor="w",
        ).pack(side="left", fill="x", expand=True, padx=14, pady=12)


class MetricRow(ctk.CTkFrame):
    def __init__(self, parent, metrics: list, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        for label, value, accent in metrics:
            chip = ctk.CTkFrame(
                self, fg_color=UI_SURFACE, corner_radius=BTN_RADIUS, border_width=1, border_color=UI_BORDER
            )
            chip.pack(side="left", padx=(0, 10), pady=2)
            ctk.CTkLabel(
                chip,
                text=str(value),
                font=font("subheading"),
                text_color=accent,
            ).pack(padx=16, pady=(10, 0))
            ctk.CTkLabel(
                chip,
                text=label,
                font=font("small"),
                text_color=UI_TEXT_MUTED,
            ).pack(padx=16, pady=(0, 10))
