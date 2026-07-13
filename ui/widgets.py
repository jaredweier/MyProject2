"""UI component library — single design system for the rebuilt app."""

from __future__ import annotations

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
    STATUS_COLORS,
    SUBNAV_HEIGHT,
    UI_ACCENT_GLOW,
    UI_ACCENT_SUBTLE,
    UI_BORDER,
    UI_BORDER_GLOW,
    UI_NAV_ACTIVE,
    UI_SURFACE,
    UI_SURFACE_LIGHT,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    font,
)


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
        super().__init__(parent, text=text, command=command, font=font("body"), **kwargs)


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


class DangerButton(ctk.CTkButton):
    def __init__(self, parent, text, command=None, **kwargs):
        kwargs.setdefault("height", BTN_HEIGHT_PRIMARY)
        kwargs.setdefault("corner_radius", BTN_RADIUS)
        kwargs.setdefault("fg_color", "transparent")
        kwargs.setdefault("hover_color", UI_SURFACE_LIGHT)
        kwargs.setdefault("text_color", DODGEVILLE_DANGER)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", DODGEVILLE_DANGER)
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


class Card(ctk.CTkFrame):
    """Elevated panel. Content goes in `.body` (fills the card)."""

    def __init__(self, parent, *, accent: bool = False, **kwargs):
        kwargs.setdefault("fg_color", UI_SURFACE)
        kwargs.setdefault("corner_radius", CORNER_RADIUS)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", UI_BORDER_GLOW if accent else UI_BORDER)
        super().__init__(parent, **kwargs)
        body_row = 1 if accent else 0
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(body_row, weight=1)
        if accent:
            stripe = ctk.CTkFrame(self, fg_color=UI_ACCENT_GLOW, height=2, corner_radius=0)
            stripe.grid(row=0, column=0, sticky="ew")
            stripe.grid_propagate(False)
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=body_row, column=0, sticky="nsew")
        self.body.grid_columnconfigure(0, weight=1)
        self.body.grid_rowconfigure(0, weight=1)


class SectionHeader(ctk.CTkFrame):
    def __init__(self, parent, title: str, subtitle: str | None = None, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._title_label = ctk.CTkLabel(self, text=title, font=font("heading"), text_color=UI_TEXT_PRIMARY, anchor="w")
        self._title_label.pack(fill="x")
        self._subtitle_label = None
        if subtitle:
            self._subtitle_label = ctk.CTkLabel(
                self, text=subtitle, font=font("small"), text_color=UI_TEXT_MUTED, anchor="w"
            )
            self._subtitle_label.pack(fill="x", pady=(4, 0))

    def configure(self, **kwargs):
        if "title" in kwargs:
            self._title_label.configure(text=kwargs.pop("title"))
        if "subtitle" in kwargs and self._subtitle_label is not None:
            self._subtitle_label.configure(text=kwargs.pop("subtitle"))
        if kwargs:
            super().configure(**kwargs)


class StatCard(ctk.CTkFrame):
    def __init__(self, parent, label, value, accent=DODGEVILLE_ACCENT, clickable=False, badge_style=False, **kwargs):
        kwargs.setdefault("fg_color", UI_SURFACE)
        kwargs.setdefault("corner_radius", CORNER_RADIUS)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", UI_BORDER)
        super().__init__(parent, **kwargs)
        if clickable:
            self.configure(cursor="hand2")
        ctk.CTkFrame(self, fg_color=accent, width=3, corner_radius=0).pack(side="left", fill="y")
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=CARD_PAD, pady=14)
        self.label_label = ctk.CTkLabel(
            inner,
            text=(label or "").upper() if badge_style else label,
            font=font("stat_label"),
            text_color=UI_TEXT_MUTED,
            anchor="w",
        )
        self.label_label.pack(fill="x")
        self.value_label = ctk.CTkLabel(
            inner, text=value, font=font("stat_value"), text_color=UI_TEXT_PRIMARY, anchor="w"
        )
        self.value_label.pack(fill="x", pady=(6, 0))

    def set_value(self, value):
        self.value_label.configure(text=value)

    def set_label(self, label):
        self.label_label.configure(text=label)


class StatusBadge(ctk.CTkLabel):
    def __init__(self, parent, status: str, **kwargs):
        color = STATUS_COLORS.get(status, UI_TEXT_MUTED)
        super().__init__(
            parent,
            text=status,
            font=font("small"),
            text_color="#FFFFFF",
            fg_color=color,
            corner_radius=8,
            **kwargs,
        )


class CoverageBadge(ctk.CTkLabel):
    def __init__(self, parent, text: str, ok: bool = True, **kwargs):
        color = DODGEVILLE_SUCCESS if ok else DODGEVILLE_WARNING
        super().__init__(
            parent,
            text=text,
            font=font("small"),
            text_color="#FFFFFF",
            fg_color=color,
            corner_radius=8,
            **kwargs,
        )


class FormField(ctk.CTkFrame):
    """Labeled control that auto-packs into parent (fill=x). Returns self; use `.widget` for the control."""

    def __init__(
        self, parent, label, widget_factory, *, auto_pack: bool = True, pack_opts: dict | None = None, **kwargs
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        ctk.CTkLabel(self, text=label, font=font("small"), text_color=UI_TEXT_MUTED, anchor="w").pack(
            fill="x", pady=(0, 6)
        )
        self.widget = widget_factory(self)
        self.widget.pack(fill="x")
        if auto_pack:
            opts = {"fill": "x", "pady": (0, 10)}
            if pack_opts:
                opts.update(pack_opts)
            self.pack(**opts)


class NavSectionLabel(ctk.CTkLabel):
    def __init__(self, parent, text, **kwargs):
        super().__init__(
            parent,
            text=(text or "").upper(),
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
        shell = ctk.CTkFrame(
            self, fg_color=UI_SURFACE_LIGHT, corner_radius=BTN_RADIUS, border_width=1, border_color=UI_BORDER
        )
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
                fg_color=DODGEVILLE_ACCENT if active else "transparent",
                hover_color=UI_ACCENT_SUBTLE if active else UI_BORDER,
                text_color="#FFFFFF" if active else UI_TEXT_MUTED,
                command=lambda k=key: self._on_select(k),
            )
            btn.grid(row=0, column=idx, sticky="ew", padx=2)
            self._buttons[key] = btn

    def set_active(self, key: str) -> None:
        for tab_key, btn in self._buttons.items():
            active = tab_key == key
            btn.configure(
                fg_color=DODGEVILLE_ACCENT if active else "transparent",
                hover_color=UI_ACCENT_SUBTLE if active else UI_BORDER,
                text_color="#FFFFFF" if active else UI_TEXT_MUTED,
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
        row = ctk.CTkFrame(
            self, fg_color=UI_SURFACE_LIGHT, corner_radius=BTN_RADIUS, border_width=1, border_color=UI_BORDER
        )
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
                fg_color=DODGEVILLE_ACCENT if active else "transparent",
                hover_color=UI_ACCENT_SUBTLE if active else UI_BORDER,
                text_color="#FFFFFF" if active else UI_TEXT_MUTED,
                command=lambda k=key: self._on_select(k),
            )
            btn.grid(row=0, column=idx, sticky="ew", padx=2)
            self._buttons[key] = btn

    def set_active(self, key: str) -> None:
        for tab_key, btn in self._buttons.items():
            active = tab_key == key
            btn.configure(
                fg_color=DODGEVILLE_ACCENT if active else "transparent",
                hover_color=UI_ACCENT_SUBTLE if active else UI_BORDER,
                text_color="#FFFFFF" if active else UI_TEXT_MUTED,
            )


class NavButton(ctk.CTkFrame):
    def __init__(self, parent, text, icon, command, nav_key: str = "", **kwargs):
        super().__init__(parent, fg_color="transparent", height=40, **kwargs)
        self._base_text = text
        self._command = command
        self._nav_key = nav_key
        self._row = ctk.CTkFrame(self, fg_color="transparent", corner_radius=BTN_RADIUS, cursor="hand2")
        self._row.pack(fill="x", padx=6, pady=1)
        self._row.grid_columnconfigure(2, weight=1)
        self._rail = ctk.CTkFrame(self._row, fg_color="transparent", width=3)
        self._rail.grid(row=0, column=0, sticky="ns", pady=6)
        self._icon_label = ctk.CTkLabel(self._row, text="", width=20)
        self._icon_label.grid(row=0, column=1, padx=(10, 8), pady=9)
        self._label = ctk.CTkLabel(self._row, text=text, font=font("nav"), text_color=UI_TEXT_MUTED, anchor="w")
        self._label.grid(row=0, column=2, sticky="ew", pady=9)
        self._count_label = ctk.CTkLabel(
            self._row,
            text="",
            font=font("small"),
            text_color="#FFFFFF",
            fg_color=DODGEVILLE_ACCENT,
            corner_radius=9,
            width=22,
            height=18,
        )
        self._count_label.grid(row=0, column=3, padx=(4, 10))
        self._count_label.grid_remove()
        for w in (self._row, self._rail, self._icon_label, self._label, self._count_label):
            w.bind("<Button-1>", lambda _e: self._invoke())
        self.set_active(False)

    def _invoke(self):
        if self._command:
            self._command()

    def set_active(self, active: bool):
        if active:
            self._row.configure(fg_color=UI_NAV_ACTIVE)
            self._rail.configure(fg_color=UI_ACCENT_GLOW)
            self._label.configure(text_color=UI_TEXT_PRIMARY)
            color = UI_ACCENT_GLOW
        else:
            self._row.configure(fg_color="transparent")
            self._rail.configure(fg_color="transparent")
            self._label.configure(text_color=UI_TEXT_MUTED)
            color = UI_TEXT_MUTED
        icon_img = render_icon(self._nav_key, size=18, color=color)
        if icon_img:
            self._icon_label.configure(image=icon_img, text="")
        else:
            self._icon_label.configure(image=None, text="·", text_color=color)

    def set_badge(self, count: int = 0):
        if count > 0:
            self._count_label.configure(text=str(count) if count < 100 else "99+")
            self._count_label.grid()
        else:
            self._count_label.grid_remove()


class SearchBar(ctk.CTkEntry):
    def __init__(self, parent, placeholder="Search...", **kwargs):
        kwargs.setdefault("height", 32)
        kwargs.setdefault("corner_radius", BTN_RADIUS)
        kwargs.setdefault("border_color", UI_BORDER)
        kwargs.setdefault("fg_color", UI_SURFACE_LIGHT)
        kwargs.setdefault("text_color", UI_TEXT_PRIMARY)
        super().__init__(parent, placeholder_text=placeholder, **kwargs)


class AlertBanner(ctk.CTkFrame):
    _COLORS = {
        "critical": DODGEVILLE_DANGER,
        "warning": DODGEVILLE_WARNING,
        "info": DODGEVILLE_ACCENT,
        "success": DODGEVILLE_SUCCESS,
    }
    _LABELS = {"critical": "CRITICAL", "warning": "WATCH", "info": "INFO", "success": "CLEAR"}

    def __init__(self, parent, message: str, severity: str = "info", **kwargs):
        color = self._COLORS.get(severity, DODGEVILLE_ACCENT)
        kwargs.setdefault("corner_radius", BTN_RADIUS)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", color)
        kwargs.setdefault("fg_color", UI_SURFACE)
        super().__init__(parent, **kwargs)
        ctk.CTkFrame(self, fg_color=color, width=5, corner_radius=0).pack(side="left", fill="y")
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True, padx=12, pady=10)
        ctk.CTkLabel(
            body, text=self._LABELS.get(severity, "INFO"), font=font("micro"), text_color=color, anchor="w"
        ).pack(fill="x")
        ctk.CTkLabel(
            body, text=message, font=font("body"), text_color=UI_TEXT_PRIMARY, anchor="w", wraplength=720
        ).pack(fill="x", pady=(2, 0))


class ActionTile(ctk.CTkFrame):
    def __init__(self, parent, title: str, subtitle: str = "", command=None, accent=None, **kwargs):
        accent = accent or DODGEVILLE_ACCENT
        kwargs.setdefault("fg_color", UI_SURFACE_LIGHT)
        kwargs.setdefault("corner_radius", CORNER_RADIUS)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", UI_BORDER)
        kwargs.setdefault("cursor", "hand2")
        super().__init__(parent, **kwargs)
        self._command = command
        ctk.CTkFrame(self, fg_color=accent, width=3, corner_radius=0).pack(side="left", fill="y")
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=10)
        ctk.CTkLabel(inner, text=title, font=font("subheading"), text_color=UI_TEXT_PRIMARY, anchor="w").pack(fill="x")
        if subtitle:
            ctk.CTkLabel(inner, text=subtitle, font=font("small"), text_color=UI_TEXT_MUTED, anchor="w").pack(
                fill="x", pady=(2, 0)
            )
        for w in (self, inner, *inner.winfo_children()):
            w.bind("<Button-1>", lambda _e: self._invoke())

    def _invoke(self):
        if self._command:
            self._command()


class EmptyState(ctk.CTkFrame):
    def __init__(self, parent, title: str, hint: str = "", *, cta_text: str = "", cta_command=None, **kwargs):
        kwargs.setdefault("fg_color", UI_SURFACE)
        kwargs.setdefault("corner_radius", CORNER_RADIUS)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", UI_BORDER)
        super().__init__(parent, **kwargs)
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=CARD_PAD, pady=28)
        ctk.CTkLabel(inner, text=title, font=font("subheading"), text_color=UI_TEXT_PRIMARY).pack()
        if hint:
            ctk.CTkLabel(
                inner, text=hint, font=font("small"), text_color=UI_TEXT_MUTED, wraplength=420, justify="center"
            ).pack(pady=(6, 0))
        if cta_text and cta_command:
            PrimaryButton(inner, text=cta_text, command=cta_command, height=BTN_HEIGHT_TOOLBAR).pack(pady=(14, 0))


class StatusLegend(ctk.CTkFrame):
    def __init__(self, parent, items: list[tuple[str, str]], **kwargs):
        kwargs.setdefault("fg_color", UI_SURFACE_LIGHT)
        kwargs.setdefault("corner_radius", BTN_RADIUS)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", UI_BORDER)
        super().__init__(parent, **kwargs)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=8)
        for label, color in items:
            chip = ctk.CTkFrame(row, fg_color=UI_SURFACE, corner_radius=12, border_width=1, border_color=UI_BORDER)
            chip.pack(side="left", padx=(0, 8))
            ctk.CTkFrame(chip, fg_color=color, width=8, height=8, corner_radius=4).pack(
                side="left", padx=(8, 4), pady=6
            )
            ctk.CTkLabel(chip, text=label, font=font("small"), text_color=UI_TEXT_MUTED).pack(side="left", padx=(0, 10))


class ToastHost(ctk.CTkFrame):
    _LEVEL_BORDER = {
        "info": DODGEVILLE_ACCENT,
        "success": DODGEVILLE_SUCCESS,
        "warning": DODGEVILLE_WARNING,
        "error": DODGEVILLE_DANGER,
    }

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=UI_SURFACE,
            corner_radius=CORNER_RADIUS,
            border_width=1,
            border_color=UI_BORDER,
            **kwargs,
        )
        self._after_id = None
        self._bar = ctk.CTkFrame(self, fg_color=DODGEVILLE_ACCENT, width=4, corner_radius=2)
        self._bar.pack(side="left", fill="y", padx=(8, 0), pady=8)
        self._label = ctk.CTkLabel(
            self, text="", font=font("small"), text_color=UI_TEXT_PRIMARY, anchor="w", wraplength=360
        )
        self._label.pack(side="left", fill="both", expand=True, padx=12, pady=12)
        self.place_forget()

    def show(self, message: str, *, level: str = "info", ms: int = 3200) -> None:
        text = (message or "").strip()
        if not text:
            return
        color = self._LEVEL_BORDER.get(level, DODGEVILLE_ACCENT)
        self._bar.configure(fg_color=color)
        self.configure(border_color=color)
        self._label.configure(text=text)
        self.lift()
        self.place(relx=1.0, rely=1.0, x=-20, y=-44, anchor="se")
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = self.after(ms, self.hide)

    def hide(self) -> None:
        self._after_id = None
        self.place_forget()


class ExpandableSection(ctk.CTkFrame):
    def __init__(self, parent, title: str, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._open = True
        self._toggle_btn = ctk.CTkButton(
            self,
            text=self._toggle_text(title),
            fg_color="transparent",
            hover_color=UI_SURFACE_LIGHT,
            text_color=UI_TEXT_PRIMARY,
            anchor="w",
            command=self._toggle,
        )
        self._toggle_btn.pack(fill="x")
        self.body = ctk.CTkFrame(self, fg_color=UI_SURFACE_LIGHT, corner_radius=BTN_RADIUS)
        self.body.pack(fill="x", pady=(4, 0))
        self._title = title

    def _toggle_text(self, title=None):
        t = title or getattr(self, "_title", "")
        return f"{'▾' if self._open else '▸'}  {t}"

    def _toggle(self):
        self._open = not self._open
        self._toggle_btn.configure(text=self._toggle_text())
        if self._open:
            self.body.pack(fill="x", pady=(4, 0))
        else:
            self.body.pack_forget()


class MetricRow(ctk.CTkFrame):
    def __init__(self, parent, metrics: list, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        for label, value, accent in metrics:
            chip = ctk.CTkFrame(
                self, fg_color=UI_SURFACE, corner_radius=BTN_RADIUS, border_width=1, border_color=UI_BORDER
            )
            chip.pack(side="left", padx=(0, 10), pady=2)
            ctk.CTkLabel(chip, text=str(value), font=font("subheading"), text_color=accent).pack(padx=16, pady=(10, 0))
            ctk.CTkLabel(chip, text=label, font=font("small"), text_color=UI_TEXT_MUTED).pack(padx=16, pady=(0, 10))
