"""In-app notification inbox — embedded on Command Post dashboard."""

from tkinter import messagebox

import customtkinter as ctk

from logic import (
    get_notification_types,
    get_notifications,
    get_officers_by_seniority,
    get_unread_notification_count,
    mark_all_notifications_read,
    mark_notification_read,
    resolve_notification_navigation,
)
from ui.theme import (
    CARD_PAD,
    DODGEVILLE_BLUE,
    UI_BORDER,
    UI_SURFACE_LIGHT,
    UI_TEXT_MUTED,
    font,
)
from ui.widgets import CompactButton, SectionHeader


class NotificationsPageMixin:
    def _build_alerts_inbox(self, host: ctk.CTkFrame) -> None:
        """Build dispatch alerts header, filters, and scrollable list into *host*."""
        hdr = ctk.CTkFrame(host, fg_color="transparent")
        hdr.pack(fill="x", padx=CARD_PAD, pady=(CARD_PAD, 6))
        self.notif_header = SectionHeader(hdr, "Alerts", "Unread: 0")
        self.notif_header.pack(side="left")

        actions = ctk.CTkFrame(hdr, fg_color="transparent")
        actions.pack(side="right")
        if self.can("notifications.manage") or self._is_officer_role():
            CompactButton(
                actions,
                text="Mark All Read",
                width=100,
                command=self._mark_all_notifications_read,
            ).pack(side="right", padx=(6, 0))
        if self.can("reports.export") or self.can("requests.approve"):
            CompactButton(
                actions,
                text="Requests PDF",
                fg_color=DODGEVILLE_BLUE,
                width=100,
                command=self._export_requests_pdf,
            ).pack(side="right", padx=(6, 0))

        filter_row = ctk.CTkFrame(host, fg_color="transparent")
        filter_row.pack(fill="x", padx=CARD_PAD, pady=(0, 6))
        self.notif_read_filter = ctk.CTkComboBox(
            filter_row,
            values=["All", "Unread", "Read"],
            width=96,
            height=30,
            command=lambda _: self.refresh_notifications(),
        )
        self.notif_read_filter.set("All")
        self.notif_read_filter.pack(side="left", padx=(0, 6))
        self.notif_type_filter = ctk.CTkComboBox(
            filter_row,
            values=["All Types"],
            width=130,
            height=30,
            command=lambda _: self.refresh_notifications(),
        )
        self.notif_type_filter.set("All Types")
        self.notif_type_filter.pack(side="left", padx=(0, 6))
        self.notif_officer_filter = ctk.CTkComboBox(
            filter_row,
            values=["All Officers"],
            width=180,
            height=30,
            command=lambda _: self.refresh_notifications(),
        )
        if self.can("notifications.manage"):
            self.notif_officer_filter.pack(side="left")
        self.notif_officer_map = {}

        self.notif_list = ctk.CTkScrollableFrame(host, fg_color="transparent")
        self.notif_list.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._refresh_notification_officer_filter()

    def _build_notifications(self):
        """Legacy page key — alerts live on Command Post; keep frame for tests."""
        page = self.pages["notifications"]
        page.grid_rowconfigure(0, weight=1)
        page.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            page,
            text="Alerts are on Command Post.",
            font=font("body"),
            text_color=UI_TEXT_MUTED,
        ).pack(expand=True)

    def _refresh_notification_officer_filter(self):
        if not hasattr(self, "notif_officer_filter"):
            return
        if self._is_officer_role():
            oid = self._linked_officer_id()
            name = self.current_user.get("officer_name") or "My Notifications"
            self.notif_officer_map = {name: oid} if oid else {}
            return
        officers = get_officers_by_seniority()
        labels = ["All Officers"] + [o["name"] for o in officers]
        self.notif_officer_map = {name: o["id"] for name, o in zip(labels[1:], officers)}
        self.notif_officer_filter.configure(values=labels)
        self.notif_officer_filter.set("All Officers")

    def _mark_all_notifications_read(self):
        if self._is_officer_role():
            officer_id = self._linked_officer_id()
        elif self.can("notifications.manage"):
            filt = self.notif_officer_filter.get()
            officer_id = self.notif_officer_map.get(filt) if filt != "All Officers" else None
        else:
            messagebox.showwarning("Permission", "Cannot mark notifications for other officers.")
            return
        mark_all_notifications_read(officer_id)
        self.refresh_notifications()

    def refresh_notifications(self):
        if not hasattr(self, "notif_list"):
            return
        if self._is_officer_role():
            officer_id = self._linked_officer_id()
        else:
            filt = self.notif_officer_filter.get()
            officer_id = self.notif_officer_map.get(filt) if filt != "All Officers" else None
        type_filt = self.notif_type_filter.get() if hasattr(self, "notif_type_filter") else None
        types = ["All Types"] + get_notification_types()
        if hasattr(self, "notif_type_filter"):
            self.notif_type_filter.configure(values=types)
        read_filt = self.notif_read_filter.get() if hasattr(self, "notif_read_filter") else "All"
        unread_only = read_filt == "Unread"
        notes = get_notifications(
            officer_id=officer_id,
            unread_only=unread_only,
            type_filter=type_filt,
        )
        if read_filt == "Read":
            notes = [n for n in notes if n.get("is_read")]
        unread = get_unread_notification_count(officer_id=officer_id)
        if hasattr(self, "notif_header"):
            self.notif_header.configure(subtitle=f"Unread: {unread}")
        self._update_notification_badge()

        for row in self._notification_row_widgets.values():
            row.destroy()
        self._notification_row_widgets = {}
        for w in self.notif_list.winfo_children():
            w.destroy()

        if not notes:
            ctk.CTkLabel(
                self.notif_list,
                text="No alerts.",
                text_color=UI_TEXT_MUTED,
                font=font("body"),
            ).pack(pady=16)
            return

        for note in notes[:12]:
            row = ctk.CTkFrame(
                self.notif_list,
                fg_color=UI_BORDER if note.get("is_read") else UI_SURFACE_LIGHT,
                corner_radius=8,
            )
            row.pack(fill="x", pady=3, padx=4)
            inner = ctk.CTkFrame(row, fg_color="transparent")
            inner.pack(fill="x", padx=10, pady=8)
            top = ctk.CTkFrame(inner, fg_color="transparent")
            top.pack(fill="x")
            ctk.CTkLabel(
                top,
                text=note["title"],
                font=font("body"),
                anchor="w",
            ).pack(side="left", fill="x", expand=True)
            if not note.get("is_read"):
                CompactButton(
                    top,
                    text="Read",
                    width=56,
                    command=lambda nid=note["id"]: self._mark_notification(nid),
                ).pack(side="right")
            ctk.CTkLabel(
                inner,
                text=note["message"],
                font=font("small"),
                anchor="w",
                wraplength=480,
            ).pack(fill="x", pady=(2, 0))
            meta = f"{note.get('recipient_name', '')}  ·  {note['type']}  ·  {note['created_at']}"
            ctk.CTkLabel(
                inner,
                text=meta,
                font=font("small"),
                text_color=UI_TEXT_MUTED,
                anchor="w",
            ).pack(fill="x")
            row.configure(cursor="hand2")
            row.bind("<Button-1>", lambda e, n=note: self._navigate_from_notification(n))
            self._notification_row_widgets[note["id"]] = row

    def _navigate_from_notification(self, note: dict):
        target = resolve_notification_navigation(note)
        if not target:
            return
        highlight = target.get("highlight")
        related_id = target.get("related_id")
        if highlight == "request":
            self._highlight_request_id = related_id
            self._set_request_view(target.get("request_view", "history"))
            self.req_history_filter.set(target.get("request_filter", "All"))
        elif highlight == "swap":
            self._highlight_swap_id = related_id
            self.swap_filter.set("All")
        elif highlight == "open_shift":
            self._highlight_open_shift_id = related_id
        elif highlight == "shift_bid":
            self._highlight_shift_bid_id = related_id
        elif highlight == "availability":
            self._highlight_availability_id = related_id
        self.show_page(target["page"])
        if not note.get("is_read"):
            mark_notification_read(note["id"])
            self.refresh_notifications()

    def _mark_notification(self, notification_id):
        mark_notification_read(notification_id)
        self.refresh_notifications()
