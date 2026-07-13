"""Extract settings/eligibility validators from validators.py."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "validators.py"
OUT = ROOT / "validators_config.py"

HEADER = '''"""Department settings, bidding eligibility, and certification validators."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

from config import (
    DATE_DISPLAY_FORMAT,
    DATE_INPUT_HINT,
    DATE_STORAGE_FORMAT,
)
from validators import ValidationResult, format_date, normalize_optional_text, parse_date


'''

REEXPORT = """

# Settings / eligibility validators (extracted for module size)
from validators_config import (  # noqa: E402
    validate_staffing_settings,
    validate_rotation_settings,
    parse_bids_due_datetime,
    validate_shift_bid_eligibility,
    can_officer_work_day_band,
    validate_officer_certifications,
)
"""


def main() -> None:
    lines = SRC.read_text(encoding="utf-8").splitlines(keepends=True)
    # 1-indexed: functions from validate_staffing_settings (877) through end
    # Keep validate_setting_key in validators.py (ends ~874)
    start = 877  # validate_staffing_settings
    end = len(lines)  # through EOF
    body = "".join(lines[start - 1 : end])
    OUT.write_text(HEADER + body, encoding="utf-8")
    new_src = "".join(lines[: start - 1]).rstrip() + "\n" + REEXPORT
    SRC.write_text(new_src, encoding="utf-8")
    print(f"validators.py -> {new_src.count(chr(10)) + 1} lines")
    print(f"validators_config.py -> {(HEADER + body).count(chr(10)) + 1} lines")


if __name__ == "__main__":
    main()
