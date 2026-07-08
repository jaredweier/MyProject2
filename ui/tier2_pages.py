"""Tier 2 features — callbacks, certifications, fatigue (shift bidding in bid_pages)."""

from __future__ import annotations

from datetime import date
from tkinter import messagebox

import customtkinter as ctk

from logic import (
    assign_officer_certification,
    get_callback_ledger,
    get_fatigue_scoreboard,
    list_certification_types,
    record_callback_event,
    sync_callback_rotation_from_roster,
)
from ui.bid_pages import BidPageMixin
from ui.theme import (
    DODGEVILLE_ACCENT,
    DODGEVILLE_DANGER,
    DODGEVILLE_SUCCESS,
    DODGEVILLE_WARNING,
    UI_SURFACE,
    UI_TEXT_MUTED,
    font,
)
from ui.widgets import SectionHeader
from validators import format_date


class Tier2PageMixin(BidPageMixin):
    def _append_tier2_report_sections(self) -> None:
        if not hasattr(self, "reports_scroll"):
            return
        ledger = get_callback_ledger(limit=15)
        if self.can("callbacks.view"):
            rot_lines = [
                (
                    f"#{r['sort_order']}  {r['officer_name']}  ·  Squad {r.get('squad') or '—'}",
                    UI_TEXT_MUTED,
                )
                for r in ledger.get("rotation", [])[:12]
            ]
            next_c = ledger.get("next_candidate")
            subtitle = f"Next up: {next_c['officer_name']}" if next_c else "Sync roster to build rotation"
            self._render_report_section(
                "Callback Rotation",
                subtitle,
                rot_lines or [("No officers on callback list — use Sync on Availability", DODGEVILLE_WARNING)],
            )
            event_lines = [
                (
                    f"{format_date(e['event_date'])}  ·  {e['officer_name']}  ·  {e['hours']:.1f}h",
                    UI_TEXT_MUTED,
                )
                for e in ledger.get("recent_events", [])[:8]
            ]
            self._render_report_section(
                "Recent Callbacks",
                "Call-in / call-back events",
                event_lines or [("No callback events recorded", DODGEVILLE_SUCCESS)],
            )

        fatigue = get_fatigue_scoreboard(limit=8)
        fatigue_lines = [
            (
                f"{row['officer_name']}  ·  score {row['score']:.0f}/100",
                DODGEVILLE_DANGER
                if row.get("severity") == "critical"
                else DODGEVILLE_WARNING
                if row.get("severity")
                else DODGEVILLE_SUCCESS,
            )
            for row in fatigue.get("officers", [])
        ]
        self._render_report_section(
            "Fatigue Scoreboard",
            f"Threshold {fatigue.get('threshold', 70):.0f}  ·  {fatigue.get('elevated_count', 0)} elevated",
            fatigue_lines or [("No active officers", UI_TEXT_MUTED)],
        )

    def _build_officer_certifications_panel(self, parent) -> None:
        self._officer_certs_frame = ctk.CTkFrame(parent, fg_color=UI_SURFACE, corner_radius=8)
        self._officer_certs_frame.pack(fill="x", pady=(8, 0))
        hdr = ctk.CTkFrame(self._officer_certs_frame, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(10, 4))
        SectionHeader(hdr, "Certifications", "Required for some shift bands").pack(side="left")
        self._officer_certs_list = ctk.CTkFrame(self._officer_certs_frame, fg_color="transparent")
        self._officer_certs_list.pack(fill="x", padx=12, pady=(0, 8))
        if self.can("certifications.manage"):
            add_row = ctk.CTkFrame(self._officer_certs_frame, fg_color="transparent")
            add_row.pack(fill="x", padx=12, pady=(0, 10))
            types = list_certification_types()
            labels = [t["name"] for t in types]
            self._cert_type_map = {t["name"]: t["id"] for t in types}
            self._cert_add_var = ctk.StringVar(value=labels[0] if labels else "")
            ctk.CTkOptionMenu(add_row, variable=self._cert_add_var, values=labels or ["None"], width=180).pack(
                side="left", padx=(0, 6)
            )
            self._cert_expires_entry = ctk.CTkEntry(
                add_row, placeholder_text="Expires (optional)", width=120, height=32
            )
            self._cert_expires_entry.pack(side="left", padx=(0, 6))
            ctk.CTkButton(
                add_row,
                text="Assign",
                width=70,
                height=32,
                fg_color=DODGEVILLE_ACCENT,
                command=self._assign_officer_cert,
            ).pack(side="left")

    def _refresh_officer_certifications(self, officer_id: int) -> None:
        if not hasattr(self, "_officer_certs_list"):
            return
        from logic import get_officer_certifications

        for w in self._officer_certs_list.winfo_children():
            w.destroy()
        certs = get_officer_certifications(officer_id)
        if not certs:
            ctk.CTkLabel(
                self._officer_certs_list,
                text="No certifications on file.",
                font=font("small"),
                text_color=UI_TEXT_MUTED,
            ).pack(anchor="w", pady=4)
            return
        for cert in certs:
            exp = cert.get("expires_date")
            exp_txt = f"  ·  expires {format_date(exp)}" if exp else ""
            ctk.CTkLabel(
                self._officer_certs_list,
                text=f"{cert['cert_name']}{exp_txt}",
                font=font("small"),
                anchor="w",
            ).pack(fill="x", pady=1)

    def _assign_officer_cert(self) -> None:
        oid = getattr(self, "selected_officer_id", None)
        if not oid:
            return
        cert_id = self._cert_type_map.get(self._cert_add_var.get())
        if not cert_id:
            return
        expires = self._cert_expires_entry.get().strip() or None
        uid = self.current_user.get("id") if self.current_user else None
        result = assign_officer_certification(
            oid,
            cert_id,
            expires_date=expires,
            user_id=uid,
        )
        if result.get("success"):
            self._cert_expires_entry.delete(0, "end")
            self._refresh_officer_certifications(oid)
            self.set_status("Certification assigned")
        else:
            messagebox.showerror("Certification", result.get("message"))

    def _record_callback_quick(self) -> None:
        if not self.can("callbacks.manage"):
            return
        ledger = get_callback_ledger()
        next_up = ledger.get("next_candidate")
        if not next_up:
            sync_callback_rotation_from_roster()
            next_up = get_callback_ledger().get("next_candidate")
        if not next_up:
            messagebox.showwarning("Callback", "Callback rotation is empty.")
            return
        uid = self.current_user.get("id") if self.current_user else None
        result = record_callback_event(
            next_up["officer_id"],
            date.today().isoformat(),
            2.0,
            notes="Recorded from Ops Reports",
            user_id=uid,
        )
        if result.get("success"):
            self.refresh_reports()
            self.set_status(f"Callback recorded for {next_up['officer_name']}")
        else:
            messagebox.showerror("Callback", result.get("message"))
