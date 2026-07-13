"""Modular page controllers for the rebuilt UI."""

from ui.pages.access import AccessPage
from ui.pages.dashboard import DashboardPage
from ui.pages.finance import BankedTimePage, PayrollPage, TimecardPage
from ui.pages.leave import RequestsPage, SwapsPage
from ui.pages.operations import AvailabilityPage, ReportsPage
from ui.pages.roster import RosterPage
from ui.pages.schedules import LiveSchedulePage, OriginalSchedulePage, TimelinePage
from ui.pages.simulator import SimulatorPage

PAGE_CLASSES = {
    "dashboard": DashboardPage,
    "base_schedule": OriginalSchedulePage,
    "live_schedule": LiveSchedulePage,
    "timeline": TimelinePage,
    "requests": RequestsPage,
    "swaps": SwapsPage,
    "officers": RosterPage,
    "timecard": TimecardPage,
    "banked_time": BankedTimePage,
    "payroll": PayrollPage,
    "reports": ReportsPage,
    "availability": AvailabilityPage,
    "simulator": SimulatorPage,
    "users": AccessPage,
    "notifications": DashboardPage,  # alerts live on dashboard
}

__all__ = ["PAGE_CLASSES"]
