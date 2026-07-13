"""Finance area — Timecards + Payroll (package facade).

Public API (stable):
  render_timecards, render_payroll, render_finance
"""

from __future__ import annotations

from gui.pages.finance.payroll_page import render_payroll
from gui.pages.finance.timecards import render_finance, render_timecards

__all__ = ["render_timecards", "render_payroll", "render_finance"]
