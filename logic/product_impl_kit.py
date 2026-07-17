"""Implementation kit — makes Chronos Command purchasable/deployable."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from paths import data_path

SETUP_STEPS: List[Dict[str, str]] = [
    {"id": "brand", "title": "Upload Chronos logo + agency seal", "path": "/media"},
    {"id": "roster", "title": "Import or enter patrol roster", "path": "/roster"},
    {"id": "rotation", "title": "Confirm rotation / shift bands", "path": "/simulator"},
    {"id": "min_staff", "title": "Set min staffing + night minimums", "path": "/simulator"},
    {"id": "flsa", "title": "Configure FLSA §7(k) / dual workforce", "path": "/payroll"},
    {"id": "notify", "title": "Turn on email/SMS channels (optional Twilio)", "path": "/channels"},
    {"id": "users", "title": "Create supervisor/officer accounts", "path": "/access"},
    {"id": "bids", "title": "Draft first shift bid season (if CBA)", "path": "/bidding"},
    {"id": "backup", "title": "Run backup + note data folder", "path": "/security"},
    {"id": "online", "title": "Online host: reverse proxy + TLS + secret", "path": "/deploy"},
]


def get_implementation_kit() -> Dict[str, Any]:
    from logic.hosting import deployment_checklist

    host = deployment_checklist()
    return {
        "success": True,
        "product": "Chronos Command",
        "vendor": "Weierworks Technologies, LLC",
        "modes": [
            {
                "id": "on_prem",
                "name": "Software (on-prem / desktop)",
                "how": "Portable build or python main.py — data stays on agency hardware",
            },
            {
                "id": "online",
                "name": "Online (hosted subscription)",
                "how": "python main.py --web or Docker; TLS reverse proxy; SCHEDULER_STORAGE_SECRET",
            },
        ],
        "setup_steps": SETUP_STEPS,
        "hosting": host,
        "supervisor_day": [
            "Sign in as supervisor",
            "Duty Board: review gaps / open vacancies / leave queue",
            "Time Off: approve with ranked coverage plan",
            "Open Shifts: post vacancy → channel notify",
            "Simulator: Find Best → memo for chief",
            "Payroll: prefill timecards from schedule → lock period",
        ],
    }


def export_implementation_kit() -> Dict[str, Any]:
    kit = get_implementation_kit()
    out = Path(data_path("exports")) / f"chronos_impl_kit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(kit, indent=2, default=str), encoding="utf-8")
    # Human-readable checklist
    md = Path(data_path("exports")) / f"chronos_impl_checklist_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    lines = [
        "# Chronos Command — Implementation checklist",
        "",
        "Vendor: **Weierworks Technologies, LLC**",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Purchase modes",
        "",
    ]
    for m in kit["modes"]:
        lines.append(f"- **{m['name']}**: {m['how']}")
    lines.extend(["", "## Setup steps", ""])
    for i, s in enumerate(kit["setup_steps"], 1):
        lines.append(f"{i}. {s['title']} (`{s['path']}`)")
    lines.extend(["", "## Supervisor day (demo)", ""])
    for s in kit["supervisor_day"]:
        lines.append(f"- {s}")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"success": True, "json_path": str(out), "md_path": str(md), "kit": kit}
