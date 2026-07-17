"""Fire / EMS / LE rotation presets for multi-agency expansion (Kelly, Pitman, etc.)."""

from __future__ import annotations

from typing import Any, Dict, List

# Patterns are documentation + apply helpers — department still owns active rotation config.
ROTATION_PRESET_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "le_14_ab",
        "name": "LE 14-day A/B squad",
        "segment": "police",
        "cycle_days": 14,
        "description": "Classic patrol: squad A/B on 14-day cycle (Chronos default style).",
        "shift_lengths": [8, 10, 11, 12],
    },
    {
        "id": "le_8h_multiblock",
        "name": "LE 8h multi-block 6-2 / 5-3",
        "segment": "police",
        "cycle_days": 14,
        "description": "8-hour bands with multi-block on/off packs (~2008 annual).",
        "shift_lengths": [8],
        "example_pattern": "6-2,5-3",
    },
    {
        "id": "pitman_2_2_3",
        "name": "Pitman 2-2-3 (12h)",
        "segment": "police",
        "cycle_days": 14,
        "description": "Two on, two off, three on; then reverse — common 12h LE.",
        "shift_lengths": [12],
        "example_pattern": "2-2-3",
    },
    {
        "id": "kelly_24_48",
        "name": "Kelly / 24-on 48-off",
        "segment": "fire",
        "cycle_days": 9,
        "description": "Fire 24-hour duty day then 48 off (adjust to local CBA).",
        "shift_lengths": [24],
        "example_pattern": "1-2",
    },
    {
        "id": "fire_48_96",
        "name": "48/96 fire",
        "segment": "fire",
        "cycle_days": 6,
        "description": "48 hours on, 96 hours off.",
        "shift_lengths": [24],
        "example_pattern": "2-4",
    },
    {
        "id": "ems_12_rotating",
        "name": "EMS 12h rotating",
        "segment": "ems",
        "cycle_days": 14,
        "description": "12-hour EMS with rotating weekends.",
        "shift_lengths": [12],
    },
    {
        "id": "dispatch_8_fixed",
        "name": "Dispatch 8h fixed",
        "segment": "dispatch",
        "cycle_days": 7,
        "description": "Fixed 8h dispatch days with weekend coverage bands.",
        "shift_lengths": [8],
    },
]


def list_rotation_presets(*, segment: str | None = None) -> Dict[str, Any]:
    rows = ROTATION_PRESET_CATALOG
    if segment:
        seg = segment.strip().lower()
        rows = [r for r in rows if r.get("segment") == seg]
    return {"success": True, "presets": list(rows), "count": len(rows)}


def get_rotation_preset(preset_id: str) -> Dict[str, Any]:
    for r in ROTATION_PRESET_CATALOG:
        if r["id"] == preset_id:
            return {"success": True, "preset": r}
    return {"success": False, "message": f"Unknown preset {preset_id}"}


def apply_rotation_preset_metadata(preset_id: str, *, user_id: int | None = None) -> Dict[str, Any]:
    """Store selected preset name in department settings (does not rewrite roster math blindly)."""
    got = get_rotation_preset(preset_id)
    if not got.get("success"):
        return got
    from logic.operations import set_department_setting

    p = got["preset"]
    set_department_setting("rotation_preset_catalog_id", p["id"])
    set_department_setting("rotation_preset_catalog_name", p["name"])
    set_department_setting("rotation_preset_segment", p.get("segment") or "")
    try:
        from logic.users import log_audit_action

        log_audit_action(
            "rotation.preset_selected",
            "department_settings",
            None,
            user_id,
            f"preset={p['id']}",
        )
    except Exception:
        pass
    return {
        "success": True,
        "message": f"Recorded preset {p['name']} — review Simulator/rotation config to apply numbers",
        "preset": p,
    }
