"""CLI handlers — ops cmds."""

from __future__ import annotations

from database import backup_database, list_backup_files
from logic import (
    add_holiday,
    add_officer_availability,
    create_manual_coverage_override,
    create_open_shift,
    delete_holiday,
    delete_officer_availability,
    fill_open_shift,
    get_current_cycle_window,
    get_department_setting,
    get_holidays,
    get_officer_availability,
    get_open_shifts,
    get_schedule_conflicts,
    set_department_setting,
)
from validators import format_date, parse_date


def fill_open_shift_cmd(args):
    result = fill_open_shift(args.shift_id, args.officer_id)
    print("Open shift filled." if result.get("success") else f"Error: {result.get('message')}")


def delete_holiday_cmd(args):
    result = delete_holiday(args.holiday_id)
    print("Holiday deleted." if result.get("success") else f"Error: {result.get('message')}")


def delete_availability_cmd(args):
    result = delete_officer_availability(args.entry_id)
    print("Availability entry deleted." if result.get("success") else f"Error: {result.get('message')}")


def get_setting_cmd(args):
    value = get_department_setting(args.key, "")
    print(value if value else "(not set)")


def set_setting_cmd(args):
    result = set_department_setting(args.key, args.value)
    print("Setting saved." if result.get("success") else f"Error: {result.get('message')}")


def staffing_settings_cmd(args):
    from logic.staffing_config import get_staffing_config, save_staffing_settings

    if args.staffing_action == "show":
        config = get_staffing_config()
        print(f"Shift length: {config['shift_length_hours']} hours")
        print(f"Annual hours target: {config['annual_hours_target']}")
        print(f"Shift count: {config['shift_count']}")
        print(f"Target officers: {config['target_officer_count']} (active roster: {config['active_officer_count']})")
        print(f"Shift starts: {', '.join(config['shift_starts'])}")
        for band in config["shift_times"]:
            print(f"  {band['start']} – {band['end']}")
        return
    if args.staffing_action == "set":
        result = save_staffing_settings(
            shift_length_hours=args.shift_length,
            annual_hours_target=args.annual_hours,
            shift_count=args.shift_count,
            target_officer_count=args.target_officers,
            shift_starts_text=args.shift_starts or "",
        )
        if result.get("success"):
            print(result.get("message", "Staffing saved."))
        else:
            print(f"Error: {result.get('message')}")


def rotation_settings_cmd(args):
    from logic.rotation_config import get_rotation_config, save_rotation_settings

    if args.rotation_action == "show":
        config = get_rotation_config()
        print(f"Preset: {config['preset']}")
        print(f"Cycle length: {config['cycle_length']} days")
        print(f"Base date: {config['base_date']}")
        print(f"Squad A days: {config['squad_a_days']}")
        print(f"Schedule mode: {config.get('rust_schedule_mode')}")
        start, end = get_current_cycle_window()
        print(f"Current cycle: {format_date(start)} – {format_date(end)}")
        return
    if args.rotation_action == "set":
        result = save_rotation_settings(
            cycle_length=args.cycle_length,
            preset=args.preset,
            base_date_text=args.base_date or "",
            squad_a_days_text=args.squad_a_days or "",
        )
        if result.get("success"):
            print(result.get("message", "Rotation saved."))
        else:
            print(f"Error: {result.get('message')}")


def backup_create():
    path = backup_database()
    print(f"Database backed up to: {path}")


def backup_list_cmd():
    files = list_backup_files()
    if not files:
        print("No backup files found.")
        return
    for path in files:
        print(path)


def backup_restore_cmd(path: str):
    from logic import restore_database_from_backup

    result = restore_database_from_backup(path)
    if result.get("success"):
        print(result.get("message", "Restored."))
        print(f"Safety copy: {result.get('safety_backup')}")
    else:
        print(f"Failed: {result.get('message')}")


def list_holidays(args):
    holidays = get_holidays(args.year)
    if not holidays:
        print("No holidays found.")
        return
    for h in holidays:
        paid = "paid" if h.get("is_paid") else "unpaid"
        print(f"{format_date(h['holiday_date']):<12} {h['name']:<24} {paid}")


def add_holiday_cmd(args):
    result = add_holiday(args.name, args.date, is_paid=not args.unpaid)
    if result.get("success"):
        print(f"Holiday added (ID: {result['holiday_id']})")
    else:
        print(f"Error: {result.get('message')}")


def list_open_shifts(args):
    shifts = get_open_shifts(officer_id=args.officer_id)
    if not shifts:
        print("No open shifts.")
        return
    for s in shifts:
        squad = f"Squad {s['squad']} " if s.get("squad") else ""
        print(f"{s['id']:<4} {format_date(s['shift_date']):<12} {squad}{s['shift_start']}-{s['shift_end']}")


def post_open_shift(args):
    result = create_open_shift(args.date, args.shift_start, args.shift_end, squad=args.squad)
    if result.get("success"):
        print(f"Open shift posted (ID: {result['shift_id']})")
    else:
        print(f"Error: {result.get('message')}")


def list_availability(args):
    entries = get_officer_availability(officer_id=args.officer_id)
    if not entries:
        print("No availability entries.")
        return
    for e in entries:
        reason = f"  {e.get('reason')}" if e.get("reason") else ""
        print(f"{e['id']:<4} {e['officer_name']:<22} {format_date(e['unavailable_date']):<12}{reason}")


def add_availability_cmd(args):
    result = add_officer_availability(args.officer_id, args.date, args.reason or "")
    if result.get("success"):
        print(f"Availability recorded (ID: {result['entry_id']})")
        if result.get("warning"):
            print(f"Warning: {result['warning']}")
    else:
        print(f"Error: {result.get('message')}")


def availability_conflicts_cmd(args):
    if args.start and args.end:
        start, end = parse_date(args.start), parse_date(args.end)
    else:
        start, end = get_current_cycle_window()
    data = get_schedule_conflicts(start, end, officer_id=args.officer_id)
    print(f"Conflicts {data['start_date']} – {data['end_date']}: {data['conflict_count']} issue(s)")
    for c in data.get("conflicts", []):
        print(f"  {c['unavailable_date']}  {c['officer_name']}  ({c['schedule_status']})  {c.get('reason') or ''}")


def assign_override_cmd(args):
    result = create_manual_coverage_override(
        args.original_officer_id,
        args.replacement_officer_id,
        args.date,
        reason=args.reason or "Manual Coverage",
    )
    if result.get("success"):
        print(result.get("message", "Coverage assigned"))
    else:
        print(f"Error: {result.get('message', 'Unknown error')}")
