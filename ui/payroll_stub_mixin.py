"""Pay stub preview and PDF export (payroll slice)."""

from __future__ import annotations

from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk

from logic import export_pay_stub_pdf, get_pay_stub_preview
from ui.theme import CARD_PAD, DODGEVILLE_BLUE, DODGEVILLE_GOLD, UI_TEXT_MUTED, font
from validators import format_date


class PayrollStubMixin:
    """Preview and export per-officer pay stubs."""

    def _append_pay_stub_buttons(self, btn_frame) -> None:
        ctk.CTkButton(
            btn_frame,
            text="Pay Stub",
            width=90,
            height=32,
            fg_color=DODGEVILLE_GOLD,
            command=self._preview_payroll_stub,
        ).pack(side="left", padx=(4, 0))
        ctk.CTkButton(
            btn_frame,
            text="Stub PDF",
            width=90,
            height=32,
            fg_color=DODGEVILLE_BLUE,
            command=self._export_payroll_stub,
        ).pack(side="left", padx=(4, 0))

    def _build_pay_stub_preview(self, parent) -> None:
        self.pay_stub_preview = ctk.CTkLabel(
            parent,
            text="",
            font=font("small"),
            text_color=UI_TEXT_MUTED,
            anchor="w",
            wraplength=900,
        )
        self.pay_stub_preview.pack(fill="x", padx=CARD_PAD, pady=(0, 4))

    def _payroll_stub_officer_id(self) -> Optional[int]:
        if self._is_officer_role():
            return self._linked_officer_id()
        officer = self._get_selected_pay_officer() if hasattr(self, "pay_officer") else None
        return officer["id"] if officer else None

    def _preview_payroll_stub(self) -> None:
        oid = self._payroll_stub_officer_id()
        if not oid:
            messagebox.showwarning("Pay Stub", "Select an officer first.")
            return
        p_start, _ = self._payroll_view_period()
        stub = get_pay_stub_preview(oid, p_start)
        if not stub.get("success"):
            if hasattr(self, "pay_stub_preview"):
                self.pay_stub_preview.configure(text=stub.get("message", "Unavailable"))
            return
        o = stub["officer"]
        salary_note = ""
        if stub.get("scheduled_per_period_salary"):
            salary_note = f"  ·  Scheduled salary ${stub['scheduled_per_period_salary']:,.2f}/period"
        if stub.get("monthly_pay"):
            salary_note += f"  (${stub['monthly_pay']:,.0f}/mo)"
        text = (
            f"Pay stub for {o['name']}: {format_date(stub['period_start'])} to {format_date(stub['period_end'])}  ·  "
            f"Base ${stub['hourly_rate']:.2f}/hr{salary_note}  ·  "
            f"Regular {stub['regular_hours']:.1f}h  ·  Other {stub['other_hours']:.1f}h  ·  "
            f"Gross ${stub['gross_pay']:,.2f}"
        )
        if hasattr(self, "pay_stub_preview"):
            self.pay_stub_preview.configure(text=text)
        self.set_status("Pay stub preview updated")

    def _export_payroll_stub(self) -> None:
        oid = self._payroll_stub_officer_id()
        if not oid:
            messagebox.showwarning("Pay Stub", "Select an officer first.")
            return
        p_start, _ = self._payroll_view_period()
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
        )
        result = export_pay_stub_pdf(oid, period_start=p_start, output_path=path or None)
        if result.get("success"):
            messagebox.showinfo("Export", f"Pay stub saved to:\n{result['path']}")
            self.set_status("Pay stub PDF exported")
        else:
            messagebox.showerror("Export Failed", result.get("message", "Export failed"))
