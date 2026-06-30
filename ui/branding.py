"""Department name, mission, and tagline for UI surfaces."""

from config import (
    DEFAULT_DEPARTMENT_MISSION,
    DEFAULT_DEPARTMENT_NAME,
    DEFAULT_DEPARTMENT_TAGLINE,
)
from logic import get_department_setting


def get_department_branding() -> dict:
    """Return display strings for department branding."""
    return {
        "name": get_department_setting("department_name", DEFAULT_DEPARTMENT_NAME),
        "mission": get_department_setting("department_mission", DEFAULT_DEPARTMENT_MISSION),
        "tagline": get_department_setting("department_tagline", DEFAULT_DEPARTMENT_TAGLINE),
    }
