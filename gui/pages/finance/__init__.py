"""Finance area — Timecards + Payroll + Time banks (package facade).

Public API (stable):
  render_timecards, render_payroll, render_finance, render_banks
"""

from __future__ import annotations

from gui.pages.finance.banks import render_banks
from gui.pages.finance.payroll_page import render_payroll
from gui.pages.finance.timecards import render_finance, render_timecards

__all__ = ["render_timecards", "render_payroll", "render_finance", "render_banks"]
