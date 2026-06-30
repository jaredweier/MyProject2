"""
Dodgeville Police Department Scheduler
Centralized configuration, constants, and logging.
"""

import logging
import os
from datetime import date
from typing import Dict, Tuple

# ==================== ROTATION ====================
ROTATION_BASE_DATE: date = date(2026, 6, 28)
ROTATION_CYCLE_LENGTH: int = 14

# ==================== PAY PERIOD ====================
# Biweekly pay periods (independent of the 14-day rotation cycle).
# Anchor period: 22-06-2026 through 05-07-2026 (14 days, inclusive).
# Shift hours count in the period where the shift *starts*, even if it ends
# on the next calendar day (e.g. 19:00 on 05-07 through 06:00 on 06-07).
PAY_PERIOD_BASE_DATE: date = date(2026, 6, 22)
PAY_PERIOD_LENGTH: int = 14

# ==================== SHIFTS ====================
SHIFT_TIMES: Dict[int, Tuple[str, str]] = {
    1: ("06:00", "17:00"),
    2: ("10:00", "21:00"),
    3: ("15:00", "02:00"),
    4: ("19:00", "06:00"),
}

# Officer roster assignment (UI + optional DB NULL = unassigned)
OFFICER_UNASSIGNED_LABEL = "Unassigned"
OFFICER_SQUAD_OPTIONS = [OFFICER_UNASSIGNED_LABEL, "A", "B"]
OFFICER_SHIFT_OPTIONS = [OFFICER_UNASSIGNED_LABEL] + [f"{start} - {end}" for start, end in SHIFT_TIMES.values()]

# Department roster titles (job_title column)
OFFICER_TITLE_OPTIONS = (
    "Officer",
    "Chief",
    "Lieutenant",
    "Sergeant",
    "Investigator",
    "Administrative Assistant",
)
OFFICER_TITLE_ALIASES = {
    "patrol officer": "Officer",
    "police officer": "Officer",
    "chief of police": "Chief",
    "adminstrative assistant": "Administrative Assistant",
}

# Position compensation defaults (payroll section; stored in department_settings JSON)
POSITION_PAY_SETTINGS_KEY = "position_pay_rates"
POSITION_PAY_BASIS_OPTIONS = ("hourly", "monthly", "yearly")
POSITION_PAY_BASIS_LABELS = {
    "hourly": "Hourly",
    "monthly": "Monthly",
    "yearly": "Yearly",
}
DEFAULT_POSITION_PAY_RATES = {
    "Officer": {"amount": 32.0, "pay_basis": "hourly", "is_salary": False},
    "Chief": {"amount": 93600.0, "pay_basis": "yearly", "is_salary": True},
    "Lieutenant": {"amount": 40.0, "pay_basis": "hourly", "is_salary": False},
    "Sergeant": {"amount": 37.5, "pay_basis": "hourly", "is_salary": False},
    "Investigator": {"amount": 34.0, "pay_basis": "hourly", "is_salary": False},
    "Administrative Assistant": {"amount": 52000.0, "pay_basis": "yearly", "is_salary": True},
}

# ==================== BUMPING RULES ====================
BUMP_RULES: Dict[int, Tuple[int, ...]] = {
    1: (2,),
    2: (1, 3),
    3: (2, 4),
    4: (3,),
}

NIGHT_MINIMUM_OFFICERS: int = 2
MIN_REST_HOURS_BETWEEN_SHIFTS: float = 8.0


def is_high_risk_night(target_date) -> bool:
    return target_date.weekday() in [4, 5]


# ==================== COLORS ====================
# Tactical command-center palette — deep navy void, electric cyan HUD, badge gold
DODGEVILLE_BLUE = "#081018"
DODGEVILLE_ACCENT = "#00B4D8"
DODGEVILLE_RED = "#E53935"
DODGEVILLE_GOLD = "#D4AF37"
DODGEVILLE_SUCCESS = "#00C853"
DODGEVILLE_DANGER = DODGEVILLE_RED
DODGEVILLE_WARNING = "#FFAB00"
DODGEVILLE_ORANGE = "#FF8F00"

GANTT_COLORS = {
    "working": "#00C853",
    "off": "#3D4F66",
    "bumped": "#FF8F00",
    "covering": "#D4AF37",
    "swapped": "#7C4DFF",
    "training": "#00BFA5",
    "court": "#AB47BC",
    "leave": "#546E7A",
    "night_window": "#00B4D8",
    "unknown": "#607D8B",
}

# UI theme extensions
UI_BG = "#050A12"
UI_SURFACE = "#0C1624"
UI_SURFACE_LIGHT = "#132238"
UI_BORDER = "#1E3A5F"
UI_TEXT_MUTED = "#7A9CC6"
UI_SIDEBAR = "#060D16"
UI_ACCENT_GLOW = "#00E5FF"

# ==================== DATE FORMATS ====================
# User-facing input/display (DD-MM-YYYY); SQLite storage remains ISO (YYYY-MM-DD).
DATE_DISPLAY_FORMAT = "%d-%m-%Y"
DATETIME_DISPLAY_FORMAT = "%d-%m-%Y %H:%M"
DATE_INPUT_HINT = "DD-MM-YYYY"
DATE_STORAGE_FORMAT = "%Y-%m-%d"

# ==================== DEPARTMENT BRANDING ====================
DEFAULT_DEPARTMENT_NAME = "Dodgeville Police Department"
DEFAULT_DEPARTMENT_MISSION = "To protect and serve, in partnership with our community, through integrity and compassion"
DEFAULT_DEPARTMENT_TAGLINE = "Wisconsin's Oldest Courthouse · Est. 1859"

# ==================== DEV AUTO-LOGIN ====================
# Production default: login required. For local UI testing set SCHEDULER_AUTO_LOGIN=1.
AUTO_LOGIN_ENABLED = os.environ.get("SCHEDULER_AUTO_LOGIN", "0").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
AUTO_LOGIN_USERNAME = os.environ.get("SCHEDULER_AUTO_LOGIN_USER", "admin").strip() or "admin"
AUTO_LOGIN_SKIP_PASSWORD_CHANGE = True

# ==================== DAY-OFF REQUESTS ====================
DAY_OFF_REQUEST_TYPES = (
    "Vacation",
    "Sick",
    "Personal",
    "Comp Time",
    "Bereavement",
    "Training",
    "Court",
)

REQUEST_TYPE_SCHEDULE_STATUS = {
    "Training": "training",
    "Court": "court",
    "Vacation": "leave",
    "Sick": "leave",
    "Personal": "leave",
    "Comp Time": "leave",
    "Bereavement": "leave",
}

# ==================== REQUEST STATUS ====================
REQUEST_STATUS = {
    "pending": "Pending",
    "approved": "Approved",
    "rejected": "Rejected",
    "pending_manual": "Pending Manual Review",
}

TIMECARD_REGULAR_TYPE = "Regular Hours"

PAYROLL_ENTRY_TYPES = [
    "Overtime Earned",
    "Comp Earned",
    "Comp Taken",
    "Holiday Pay",
    "Holiday Overtime",
    "Holiday Comp Earned",
    "Holiday Overtime Comp Earned",
    "Sick Time Used",
    "Bereavement",
    "Training",
    "Unpaid",
    "Float Holiday Taken",
    "Holiday Taken",
]

TIMECARD_ENTRY_TYPES = [TIMECARD_REGULAR_TYPE] + PAYROLL_ENTRY_TYPES

SCHEDULE_SNAPSHOT_TYPES = ("base", "updated")

SNAPSHOT_STATUSES = (
    "working",
    "off",
    "bumped",
    "covering",
    "swapped",
    "leave",
    "training",
    "court",
)

SIMULATOR_ROTATION_TYPES = [
    "2-2-3 (Dodgeville 14-day)",
    "4-on-4-off",
    "Panama 12-hour",
    "Continental 7-day",
    "Equal split (custom cycle)",
]

DEFAULT_ANNUAL_HOURS = 2080.0
DEFAULT_OVERTIME_MULTIPLIER = 1.5

# FLSA hours watch (weekly OT + pay-period cap warnings)
FLSA_WEEKLY_THRESHOLD = 40.0
FLSA_HOURS_WARN_PCT = 0.9

ROTATION_PRESETS = {
    "2-2-3 (Dodgeville 14-day)": {
        "cycle_length": 14,
        "squads": 2,
        "squad_a_days": {1, 2, 5, 6, 7, 10, 11},
    },
    "4-on-4-off": {
        "cycle_length": 8,
        "squads": 2,
        "squad_patterns": {"A": [1, 1, 1, 1, 0, 0, 0, 0], "B": [0, 0, 0, 0, 1, 1, 1, 1]},
    },
    "Panama 12-hour": {
        "cycle_length": 14,
        "squads": 2,
        "squad_a_days": {1, 2, 3, 4, 5, 6, 7},
    },
    "Continental 7-day": {
        "cycle_length": 7,
        "squads": 1,
        "squad_patterns": {"A": [1, 1, 1, 0, 0, 1, 1]},
    },
    "Equal split (custom cycle)": {
        "cycle_length": 14,
        "squads": 2,
        "work_days_per_cycle": 7,
    },
}

# Time bank accrual (per SCHEDULING_RULES.txt)
SICK_MONTHLY_ACCRUAL_HOURS = 8.0
FLOAT_HOLIDAY_ANNUAL_HOURS = 24.0  # 3 x 8 hours
HOLIDAY_ANNUAL_HOURS = 80.0  # 10 x 8 hours

# ==================== LOGGING ====================
LOG_LEVEL = "INFO"
LOG_FILE = "dodgeville_scheduler.log"
_logging_configured = False


def configure_logging() -> logging.Logger:
    """Configure file/console logging once (call from app entry, not on import)."""
    global _logging_configured
    log = logging.getLogger("DodgevilleScheduler")
    if _logging_configured:
        return log
    if not os.path.exists("logs"):
        os.makedirs("logs")
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(f"logs/{LOG_FILE}"),
            logging.StreamHandler(),
        ],
    )
    _logging_configured = True
    return log


logger = logging.getLogger("DodgevilleScheduler")
