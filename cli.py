#!/usr/bin/env python3
"""
Dodgeville Police Department Scheduler - Admin CLI

Handlers live under cli/*_cmds.py. This module owns argparse + dispatch.
"""

from __future__ import annotations

import argparse

from cli.bid_cmds import (
    assignments_shift_bid_cmd,
    finalize_shift_bid_cmd,
    import_sim_shift_bid_cmd,
    list_shift_bids_cmd,
    participation_shift_bid_cmd,
    post_shift_bid_event_cmd,
    preview_shift_bid_cmd,
    reassign_shift_bid_cmd,
    show_shift_bid_cmd,
    submit_shift_bid_cmd,
)
from cli.callback_cmds import (
    fatigue_report_cmd,
    list_callbacks_cmd,
    next_callback_cmd,
    record_callback_cmd,
)
from cli.export_cmds import (
    export_coverage,
    export_ical_cmd,
    export_pay_period_history_csv_cmd,
    export_payroll,
    export_payroll_csv_cmd,
    export_requests,
    export_requests_csv_cmd,
    export_roster,
    export_schedule,
    export_shift_swaps_csv_cmd,
    export_swaps_pdf_cmd,
    export_timecard_csv_cmd,
    schedule_diff_cmd,
)
from cli.notification_cmds import (
    list_notifications,
    read_all_notifications,
    read_notification,
)
from cli.ops_cmds import (
    add_availability_cmd,
    add_holiday_cmd,
    assign_override_cmd,
    availability_conflicts_cmd,
    backup_create,
    backup_list_cmd,
    backup_restore_cmd,
    delete_availability_cmd,
    delete_holiday_cmd,
    fill_open_shift_cmd,
    get_setting_cmd,
    list_availability,
    list_holidays,
    list_open_shifts,
    post_open_shift,
    rotation_settings_cmd,
    set_setting_cmd,
    staffing_settings_cmd,
)
from cli.payroll_cmds import (
    pay_period_history_cmd,
    pay_period_lock,
    pay_period_status,
    pay_period_unlock,
)
from cli.report_cmds import reports_coverage, reports_labor_compliance, reports_summary
from cli.request_cmds import (
    approve_request,
    list_pending_requests,
    list_requests,
    reject_request,
    submit_request_cmd,
)
from cli.roster_cmds import dispatch_officers, register_officers_parser
from cli.swap_cmds import (
    approve_swap,
    create_swap_cmd,
    list_pending_swaps,
    list_swaps,
    reject_swap,
)
from cli.user_cmds import (
    create_user_cmd,
    list_users_cmd,
    reset_user_password_cmd,
    set_user_active_cmd,
    update_user_cmd,
)
from config import DAY_OFF_REQUEST_TYPES
from logic import (
    bulk_approve_auto_ok_requests,
    bulk_reject_pending_requests,
    export_audit_csv,
    get_audit_log,
    get_current_cycle_window,
    get_overtime_alerts,
    get_schedule_conflicts,
    sync_callback_rotation_from_roster,
)
from permissions import USER_ROLES
from validators import parse_date


def main():
    parser = argparse.ArgumentParser(description="Dodgeville PD Scheduler Admin CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Officers
    officers = subparsers.add_parser("officers", help="Manage officers")
    officers_sub = officers.add_subparsers(dest="action")
    register_officers_parser(officers_sub)

    # Requests
    requests = subparsers.add_parser("requests", help="Manage day-off requests")
    requests_sub = requests.add_subparsers(dest="action")
    requests_sub.add_parser("pending", help="List pending requests")
    req_list = requests_sub.add_parser("list", help="List requests with optional filters")
    req_list.add_argument("--status", help="Filter by status (or 'all')")
    req_list.add_argument("--from", dest="from_date", help="Start date DD-MM-YYYY")
    req_list.add_argument("--to", dest="to_date", help="End date DD-MM-YYYY")

    requests_sub.add_parser("bulk-approve", help="Approve all auto-OK pending requests")
    bulk_reject = requests_sub.add_parser("bulk-reject", help="Reject all standard pending requests")
    bulk_reject.add_argument("--notes", default="Bulk rejected", help="Admin notes on rejections")

    approve = requests_sub.add_parser("approve", help="Approve a request")
    approve.add_argument("request_id", type=int)

    reject = requests_sub.add_parser("reject", help="Reject a request")
    reject.add_argument("request_id", type=int)

    req_submit = requests_sub.add_parser("submit", help="Submit a day-off request")
    req_submit.add_argument("--officer-id", type=int, required=True)
    req_submit.add_argument("--date", required=True, help="DD-MM-YYYY")
    req_submit.add_argument("--type", required=True, choices=list(DAY_OFF_REQUEST_TYPES))
    req_submit.add_argument("--notes", default="")

    # Swaps
    swaps = subparsers.add_parser("swaps", help="Manage shift swap requests")
    swaps_sub = swaps.add_subparsers(dest="action")
    swaps_sub.add_parser("pending", help="List pending swaps")
    swap_list = swaps_sub.add_parser("list", help="List swaps with optional filters")
    swap_list.add_argument("--status", help="Filter: pending, Approved, Rejected, or all")
    swap_list.add_argument("--from", dest="from_date", help="Start date DD-MM-YYYY")
    swap_list.add_argument("--to", dest="to_date", help="End date DD-MM-YYYY")

    swap_approve = swaps_sub.add_parser("approve", help="Approve a swap")
    swap_approve.add_argument("swap_id", type=int)

    swap_reject = swaps_sub.add_parser("reject", help="Reject a swap")
    swap_reject.add_argument("swap_id", type=int)

    swap_create = swaps_sub.add_parser("create", help="Create a shift swap request")
    swap_create.add_argument("--officer1-id", type=int, required=True)
    swap_create.add_argument("--officer2-id", type=int, required=True)
    swap_create.add_argument("--date", required=True, help="DD-MM-YYYY")

    # Notifications
    notifications = subparsers.add_parser("notifications", help="View notifications")
    notif_sub = notifications.add_subparsers(dest="action")
    notif_list = notif_sub.add_parser("list", help="List notifications")
    notif_list.add_argument("--unread", action="store_true")
    notif_list.add_argument("--officer-id", type=int)

    notif_read = notif_sub.add_parser("read", help="Mark one notification read")
    notif_read.add_argument("notification_id", type=int)

    notif_read_all = notif_sub.add_parser("read-all", help="Mark all notifications read")
    notif_read_all.add_argument("--officer-id", type=int)

    # Exports
    exports = subparsers.add_parser("export", help="Export PDF reports")
    export_sub = exports.add_subparsers(dest="action")

    exp_schedule = export_sub.add_parser("schedule", help="Export schedule PDF")
    exp_schedule.add_argument("--start", help="Start date DD-MM-YYYY")
    exp_schedule.add_argument("--end", help="End date DD-MM-YYYY")
    exp_schedule.add_argument("--officer-id", type=int, help="Limit to one officer")
    exp_schedule.add_argument("--output", help="Output file path")

    exp_payroll = export_sub.add_parser("payroll", help="Export payroll PDF")
    exp_payroll.add_argument("--officer-id", type=int)
    exp_payroll.add_argument("--period-start", help="Pay period start DD-MM-YYYY")
    exp_payroll.add_argument("--output", help="Output file path")

    exp_coverage = export_sub.add_parser("coverage", help="Export coverage report PDF")
    exp_coverage.add_argument("--start", help="Start date DD-MM-YYYY")
    exp_coverage.add_argument("--end", help="End date DD-MM-YYYY")
    exp_coverage.add_argument("--output", help="Output file path")

    exp_requests = export_sub.add_parser("requests", help="Export day-off requests PDF")
    exp_requests.add_argument("--status", help="Filter by status")
    exp_requests.add_argument("--from", dest="from_date", help="Start date DD-MM-YYYY")
    exp_requests.add_argument("--to", dest="to_date", help="End date DD-MM-YYYY")
    exp_requests.add_argument("--officer-id", type=int, help="Limit to one officer's requests")
    exp_requests.add_argument("--output", help="Output file path")

    exp_swaps = export_sub.add_parser("swaps", help="Export shift swap requests PDF")
    exp_swaps.add_argument("--status", help="Filter: pending, Approved, Rejected, or all")
    exp_swaps.add_argument("--from", dest="from_date", help="Start date DD-MM-YYYY")
    exp_swaps.add_argument("--to", dest="to_date", help="End date DD-MM-YYYY")
    exp_swaps.add_argument("--officer-id", type=int)
    exp_swaps.add_argument("--output", help="Output file path")

    exp_ical = export_sub.add_parser("ical", help="Export officer schedule as iCal (.ics)")
    exp_ical.add_argument("--officer-id", type=int, required=True)
    exp_ical.add_argument("--start", help="Start date DD-MM-YYYY")
    exp_ical.add_argument("--end", help="End date DD-MM-YYYY")
    exp_ical.add_argument("--output", help="Output file path")

    # Users
    users = subparsers.add_parser("users", help="Manage application login accounts")
    users_sub = users.add_subparsers(dest="action")
    users_list = users_sub.add_parser("list", help="List app users")
    users_list.add_argument(
        "--active-only",
        action="store_true",
        help="Hide deactivated accounts",
    )
    users_create = users_sub.add_parser("create", help="Create a login account")
    users_create.add_argument("--username", required=True)
    users_create.add_argument("--password", required=True)
    users_create.add_argument("--role", required=True, choices=list(USER_ROLES))
    users_create.add_argument("--officer-id", type=int, help="Link to officer record")
    users_create.add_argument(
        "--no-force-change",
        action="store_true",
        help="Do not require password change on first login",
    )
    users_update = users_sub.add_parser("update", help="Update role or officer link")
    users_update.add_argument("user_id", type=int)
    users_update.add_argument("--role", choices=list(USER_ROLES))
    users_update.add_argument("--officer-id", type=int)
    users_update.add_argument(
        "--clear-officer-link",
        action="store_true",
        help="Remove officer link",
    )
    users_reset = users_sub.add_parser("reset-password", help="Reset user password")
    users_reset.add_argument("user_id", type=int)
    users_reset.add_argument("--password", required=True)
    users_reset.add_argument("--no-force-change", action="store_true")
    users_deact = users_sub.add_parser("deactivate", help="Deactivate a user")
    users_deact.add_argument("user_id", type=int)
    users_act = users_sub.add_parser("activate", help="Reactivate a user")
    users_act.add_argument("user_id", type=int)

    # Manual overrides
    overrides = subparsers.add_parser("overrides", help="Schedule coverage overrides")
    ov_sub = overrides.add_subparsers(dest="action")
    ov_assign = ov_sub.add_parser("assign", help="Assign manual coverage for a shift")
    ov_assign.add_argument("--original-officer-id", type=int, required=True)
    ov_assign.add_argument("--replacement-officer-id", type=int, required=True)
    ov_assign.add_argument("--date", required=True, help="Override date DD-MM-YYYY")
    ov_assign.add_argument("--reason", default="Manual Coverage")

    # Holidays
    holidays = subparsers.add_parser("holidays", help="Manage department holidays")
    hol_sub = holidays.add_subparsers(dest="action")
    hol_list = hol_sub.add_parser("list", help="List holidays")
    hol_list.add_argument("--year", type=int)
    hol_add = hol_sub.add_parser("add", help="Add a holiday")
    hol_add.add_argument("--name", required=True)
    hol_add.add_argument("--date", required=True, help="DD-MM-YYYY")
    hol_add.add_argument("--unpaid", action="store_true")
    hol_del = hol_sub.add_parser("delete", help="Delete a holiday")
    hol_del.add_argument("holiday_id", type=int)

    settings = subparsers.add_parser("settings", help="Department settings")
    set_sub = settings.add_subparsers(dest="action")
    set_get = set_sub.add_parser("get", help="Get a setting value")
    set_get.add_argument("key")
    set_set = set_sub.add_parser("set", help="Set a setting value")
    set_set.add_argument("key")
    set_set.add_argument("value")
    set_rot = set_sub.add_parser("rotation", help="Show or update rotation schedule")
    rot_sub = set_rot.add_subparsers(dest="rotation_action")
    rot_sub.add_parser("show", help="Show active rotation configuration")
    rot_set = rot_sub.add_parser("set", help="Save rotation schedule (applies department-wide)")
    rot_set.add_argument("--cycle-length", type=int, required=True, help="7–28 days")
    rot_set.add_argument("--preset", required=True, help="Rotation preset name")
    rot_set.add_argument("--base-date", default="", help="Cycle anchor DD-MM-YYYY (optional)")
    rot_set.add_argument("--squad-a-days", default="", help="Optional Squad A on-duty days")
    set_staff = set_sub.add_parser("staffing", help="Show or update shift and staffing configuration")
    staff_sub = set_staff.add_subparsers(dest="staffing_action")
    staff_sub.add_parser("show", help="Show active staffing configuration")
    staff_set = staff_sub.add_parser("set", help="Save staffing configuration")
    staff_set.add_argument("--shift-length", type=float, required=True, help="Hours per shift")
    staff_set.add_argument("--annual-hours", type=float, required=True, help="Department annual hours target")
    staff_set.add_argument("--shift-count", type=int, required=True, help="Number of shift bands")
    staff_set.add_argument("--target-officers", type=int, required=True, help="Target roster size")
    staff_set.add_argument("--shift-starts", default="", help="Comma-separated HH:MM start times")

    # Reports
    reports = subparsers.add_parser("reports", help="Analytics and summaries")
    rep_sub = reports.add_subparsers(dest="action")
    rep_sum = rep_sub.add_parser("summary", help="Dashboard-style summary")
    rep_sum.add_argument("--officer-id", type=int, help="Officer-scoped summary")
    rep_cov = rep_sub.add_parser("coverage", help="Coverage report for date range")
    rep_cov.add_argument("--start", help="DD-MM-YYYY")
    rep_cov.add_argument("--end", help="DD-MM-YYYY")
    rep_ot = rep_sub.add_parser("overtime", help="Overtime alerts for current period")
    rep_ot.add_argument("--officer-id", type=int, help="Limit to one officer")
    rep_conf = rep_sub.add_parser("conflicts", help="Availability vs schedule conflicts")
    rep_conf.add_argument("--start", help="DD-MM-YYYY")
    rep_conf.add_argument("--end", help="DD-MM-YYYY")
    rep_conf.add_argument("--officer-id", type=int, help="Limit to one officer")
    rep_lc = rep_sub.add_parser("labor-compliance", help="FLSA §207(k), comp cap, consecutive-day alerts")
    rep_lc.add_argument("--officer-id", type=int, help="Limit to one officer")

    # Schedule diff
    sched_diff = subparsers.add_parser("schedule-diff", help="Compare base vs updated schedule")
    sched_diff.add_argument("--year", type=int, help="Year (default: current)")
    sched_diff.add_argument("--month", type=int, help="Month 1-12 (default: current)")
    sched_diff.add_argument("--output", help="Export diff to CSV instead of printing")
    sched_diff.add_argument("--officer-id", type=int, help="Limit to one officer's changes")
    sched_diff.add_argument("--limit", type=int, default=50, help="Max rows when printing")

    # CSV exports
    csv_export = subparsers.add_parser("csv", help="Export CSV data")
    csv_sub = csv_export.add_subparsers(dest="action")
    csv_roster = csv_sub.add_parser("roster", help="Export officer roster")
    csv_roster.add_argument("--output", help="Output file path")
    csv_pay = csv_sub.add_parser("payroll", help="Export payroll for pay period")
    csv_pay.add_argument("--period-start", help="Pay period start DD-MM-YYYY")
    csv_pay.add_argument("--officer-id", type=int, help="Limit to one officer")
    csv_pay.add_argument("--output", help="Output file path")
    csv_req = csv_sub.add_parser("requests", help="Export day-off requests")
    csv_req.add_argument("--status", help="Filter by status (or 'all')")
    csv_req.add_argument("--from", dest="from_date", help="Start date DD-MM-YYYY")
    csv_req.add_argument("--to", dest="to_date", help="End date DD-MM-YYYY")
    csv_req.add_argument("--output", help="Output file path")
    csv_req.add_argument("--officer-id", type=int, help="Limit to one officer's requests")
    csv_swaps = csv_sub.add_parser("swaps", help="Export shift swap requests")
    csv_swaps.add_argument("--status", help="Filter: pending, Approved, Rejected, or all")
    csv_swaps.add_argument("--from", dest="from_date", help="Start date DD-MM-YYYY")
    csv_swaps.add_argument("--to", dest="to_date", help="End date DD-MM-YYYY")
    csv_swaps.add_argument("--officer-id", type=int, help="Limit to swaps involving officer")
    csv_swaps.add_argument("--output", help="Output file path")
    csv_tc = csv_sub.add_parser("timecard", help="Export timecard entries for pay period")
    csv_tc.add_argument("--period-start", help="Pay period start DD-MM-YYYY")
    csv_tc.add_argument("--officer-id", type=int, help="Limit to one officer")
    csv_tc.add_argument("--output", help="Output file path")
    csv_hist = csv_sub.add_parser("pay-history", help="Export pay period history summary")
    csv_hist.add_argument("--limit", type=int, default=12)
    csv_hist.add_argument("--officer-id", type=int)
    csv_hist.add_argument("--output", help="Output file path")

    # Pay period
    pay_period = subparsers.add_parser("pay-period", help="Lock/unlock current pay period")
    pp_sub = pay_period.add_subparsers(dest="action")
    pp_sub.add_parser("status", help="Show lock status")
    pp_sub.add_parser("lock", help="Lock current pay period")
    pp_sub.add_parser("unlock", help="Unlock pay period")
    pp_hist = pp_sub.add_parser("history", help="List recent pay periods")
    pp_hist.add_argument("--limit", type=int, default=6)

    # Availability
    availability = subparsers.add_parser("availability", help="Officer blackout dates")
    avail_sub = availability.add_subparsers(dest="action")
    avail_list = avail_sub.add_parser("list", help="List availability entries")
    avail_list.add_argument("--officer-id", type=int)
    avail_add = avail_sub.add_parser("add", help="Add blackout date")
    avail_add.add_argument("--officer-id", type=int, required=True)
    avail_add.add_argument("--date", required=True, help="DD-MM-YYYY")
    avail_add.add_argument("--reason", default="")
    avail_conf = avail_sub.add_parser("conflicts", help="Show schedule conflicts")
    avail_conf.add_argument("--officer-id", type=int)
    avail_conf.add_argument("--start", help="DD-MM-YYYY")
    avail_conf.add_argument("--end", help="DD-MM-YYYY")
    avail_del = avail_sub.add_parser("delete", help="Delete an availability entry")
    avail_del.add_argument("entry_id", type=int)

    # Open shifts
    open_shifts = subparsers.add_parser("open-shifts", help="Manage open shifts")
    os_sub = open_shifts.add_subparsers(dest="action")
    os_list = os_sub.add_parser("list", help="List open shifts")
    os_list.add_argument("--officer-id", type=int, help="Filter to shifts claimable by officer")
    os_post = os_sub.add_parser("post", help="Post an open shift")
    os_post.add_argument("--date", required=True)
    os_post.add_argument("--shift-start", required=True)
    os_post.add_argument("--shift-end", required=True)
    os_post.add_argument("--squad", choices=["A", "B"])
    os_fill = os_sub.add_parser("fill", help="Assign an officer to an open shift")
    os_fill.add_argument("shift_id", type=int)
    os_fill.add_argument("--officer-id", type=int, required=True)

    shift_bids = subparsers.add_parser("shift-bids", help="Shift bid events")
    sb_sub = shift_bids.add_subparsers(dest="action")
    sb_list = sb_sub.add_parser("list", help="List bid events")
    sb_list.add_argument("--officer-id", type=int)
    sb_post = sb_sub.add_parser("post", help="Create a bid event (draft)")
    sb_post.add_argument("--title", default="Shift Bid")
    sb_post.add_argument("--number-of-shifts", default="")
    sb_post.add_argument("--shift-length", default="")
    sb_post.add_argument("--rotation", default="")
    sb_post.add_argument("--shift-start-times", default="")
    sb_post.add_argument("--shifts-begin", default="")
    sb_post.add_argument("--bids-due-by", default="")
    sb_post.add_argument("--squad", choices=["A", "B"])
    sb_post.add_argument("--notes", default="")
    sb_post.add_argument("--publish", action="store_true", help="Publish immediately to officers")
    sb_submit = sb_sub.add_parser("submit", help="Submit ranked preferences")
    sb_submit.add_argument("event_id", type=int)
    sb_submit.add_argument("--officer-id", type=int, required=True)
    sb_submit.add_argument(
        "--rankings",
        nargs="+",
        required=True,
        help="Preference list as option_id:rank (e.g. 3:1 5:2)",
    )
    sb_finalize = sb_sub.add_parser("finalize", help="Finalize awards by seniority")
    sb_finalize.add_argument("event_id", type=int)
    sb_show = sb_sub.add_parser("show", help="Show bid event details")
    sb_show.add_argument("event_id", type=int)
    sb_reassign = sb_sub.add_parser("reassign", help="Manually change assignment on a finalized event")
    sb_reassign.add_argument("event_id", type=int)
    sb_reassign.add_argument("option_id", type=int)
    sb_reassign.add_argument("--officer-id", type=int, help="Officer to assign (omit with --clear)")
    sb_reassign.add_argument("--clear", action="store_true", help="Remove assignment from this shift")
    sb_preview = sb_sub.add_parser("preview", help="Preview seniority awards without finalizing")
    sb_preview.add_argument("event_id", type=int)
    sb_part = sb_sub.add_parser("participation", help="Participation report for a bid event")
    sb_part.add_argument("event_id", type=int)
    sb_assign = sb_sub.add_parser("assignments", help="Bulk update finalized assignments")
    sb_assign.add_argument("event_id", type=int)
    sb_assign.add_argument(
        "assignments",
        nargs="+",
        help="option_id:officer_id pairs (use none to unassign)",
    )
    sb_import = sb_sub.add_parser("import-sim", help="Create bid from simulator or saved scenario")
    sb_import.add_argument("--scenario-id", type=int, help="Saved simulator scenario ID")
    sb_import.add_argument("--rotation", default="4-on-4-off")
    sb_import.add_argument("--officers", type=int, default=8)
    sb_import.add_argument("--shift-length", type=float, default=10.0)
    sb_import.add_argument("--annual-hours", type=float, default=2080.0)
    sb_import.add_argument("--shift-starts", default="06:00,16:00")
    sb_import.add_argument("--title", default="")
    sb_import.add_argument("--squad", choices=["A", "B"])
    sb_import.add_argument("--shifts-begin", default="")
    sb_import.add_argument("--bids-due-by", default="")
    sb_import.add_argument("--publish", action="store_true")

    callbacks = subparsers.add_parser("callbacks", help="Call-back rotation and events")
    cb_sub = callbacks.add_subparsers(dest="action")
    cb_sub.add_parser("list", help="List callback rotation")
    cb_sub.add_parser("sync", help="Sync rotation from active roster")
    cb_sub.add_parser("next", help="Show next callback candidate")
    cb_record = cb_sub.add_parser("record", help="Record a callback event")
    cb_record.add_argument("--officer-id", type=int, required=True)
    cb_record.add_argument("--date", required=True)
    cb_record.add_argument("--hours", type=float, required=True)
    cb_record.add_argument("--notes", default="")

    subparsers.add_parser("fatigue", help="Fatigue scoreboard report")

    # Audit
    audit = subparsers.add_parser("audit-log", help="View or export audit log")
    audit_sub = audit.add_subparsers(dest="action")
    audit_list = audit_sub.add_parser("list", help="List recent audit entries")
    audit_list.add_argument("--limit", type=int, default=25)
    audit_list.add_argument("--action", help="Filter by action substring")
    audit_export = audit_sub.add_parser("export", help="Export audit log CSV")
    audit_export.add_argument("--output", help="Output file path")
    audit_export.add_argument("--limit", type=int, default=500)
    audit_export.add_argument("--action", help="Filter by action substring")

    # Backup
    backup = subparsers.add_parser("backup", help="Backup, list, or restore the database")
    backup_sub = backup.add_subparsers(dest="action")
    backup_sub.add_parser("create", help="Create a new backup (default)")
    backup_sub.add_parser("list", help="List backup files (newest first)")
    backup_restore = backup_sub.add_parser("restore", help="Restore from a backup file")
    backup_restore.add_argument("path", help="Path to a .db backup file")

    args = parser.parse_args()

    if args.command == "officers":
        dispatch_officers(args)
    elif args.command == "requests":
        if args.action == "pending":
            list_pending_requests()
        elif args.action == "list":
            list_requests(args)
        elif args.action == "bulk-approve":
            result = bulk_approve_auto_ok_requests()
            print(result.get("message", "Done"))
            for err in result.get("failed", []):
                print(f"  Failed: {err}")
        elif args.action == "bulk-reject":
            result = bulk_reject_pending_requests(admin_notes=args.notes)
            print(result.get("message", "Done"))
            for err in result.get("failed", []):
                print(f"  Failed: {err}")
        elif args.action == "approve":
            approve_request(args.request_id)
        elif args.action == "reject":
            reject_request(args.request_id)
        elif args.action == "submit":
            submit_request_cmd(args)
    elif args.command == "swaps":
        if args.action == "pending":
            list_pending_swaps()
        elif args.action == "list":
            list_swaps(args)
        elif args.action == "approve":
            approve_swap(args.swap_id)
        elif args.action == "reject":
            reject_swap(args.swap_id)
        elif args.action == "create":
            create_swap_cmd(args)
    elif args.command == "notifications":
        if args.action == "list":
            list_notifications(unread_only=args.unread, officer_id=args.officer_id)
        elif args.action == "read":
            read_notification(args.notification_id)
        elif args.action == "read-all":
            read_all_notifications(officer_id=args.officer_id)
    elif args.command == "export":
        if args.action == "schedule":
            export_schedule(args)
        elif args.action == "coverage":
            export_coverage(args)
        elif args.action == "payroll":
            export_payroll(args)
        elif args.action == "requests":
            export_requests(args)
        elif args.action == "swaps":
            export_swaps_pdf_cmd(args)
        elif args.action == "ical":
            export_ical_cmd(args)
    elif args.command == "users":
        if args.action == "list":
            list_users_cmd(args)
        elif args.action == "create":
            create_user_cmd(args)
        elif args.action == "update":
            update_user_cmd(args)
        elif args.action == "reset-password":
            reset_user_password_cmd(args)
        elif args.action == "deactivate":
            set_user_active_cmd(args, active=False)
        elif args.action == "activate":
            set_user_active_cmd(args, active=True)
    elif args.command == "overrides":
        if args.action == "assign":
            assign_override_cmd(args)
    elif args.command == "holidays":
        if args.action == "list":
            list_holidays(args)
        elif args.action == "add":
            add_holiday_cmd(args)
        elif args.action == "delete":
            delete_holiday_cmd(args)
    elif args.command == "settings":
        if args.action == "get":
            get_setting_cmd(args)
        elif args.action == "set":
            set_setting_cmd(args)
        elif args.action == "rotation":
            rotation_settings_cmd(args)
        elif args.action == "staffing":
            staffing_settings_cmd(args)
    elif args.command == "reports":
        if args.action == "summary":
            reports_summary(args)
        elif args.action == "coverage":
            reports_coverage(args)
        elif args.action == "overtime":
            data = get_overtime_alerts(officer_id=args.officer_id)
            for a in data.get("alerts", []):
                print(f"{a['officer_name']:<22} {a['hours']:.1f}h  ({a['severity']})")
        elif args.action == "conflicts":
            if args.start and args.end:
                start, end = parse_date(args.start), parse_date(args.end)
            else:
                start, end = get_current_cycle_window()
            data = get_schedule_conflicts(start, end, officer_id=args.officer_id)
            print(f"Conflicts {data['start_date']} – {data['end_date']}: {data['conflict_count']} issue(s)")
            for c in data.get("conflicts", []):
                print(
                    f"  {c['unavailable_date']}  {c['officer_name']}  ({c['schedule_status']})  {c.get('reason') or ''}"
                )
        elif args.action == "labor-compliance":
            reports_labor_compliance(args)
    elif args.command == "schedule-diff":
        schedule_diff_cmd(args)
    elif args.command == "csv":
        if args.action == "roster":
            export_roster(args)
        elif args.action == "payroll":
            export_payroll_csv_cmd(args)
        elif args.action == "requests":
            export_requests_csv_cmd(args)
        elif args.action == "swaps":
            export_shift_swaps_csv_cmd(args)
        elif args.action == "timecard":
            export_timecard_csv_cmd(args)
        elif args.action == "pay-history":
            export_pay_period_history_csv_cmd(args)
    elif args.command == "pay-period":
        if args.action == "status":
            pay_period_status(args)
        elif args.action == "lock":
            pay_period_lock(args)
        elif args.action == "unlock":
            pay_period_unlock(args)
        elif args.action == "history":
            pay_period_history_cmd(args)
    elif args.command == "availability":
        if args.action == "list":
            list_availability(args)
        elif args.action == "add":
            add_availability_cmd(args)
        elif args.action == "conflicts":
            availability_conflicts_cmd(args)
        elif args.action == "delete":
            delete_availability_cmd(args)
    elif args.command == "open-shifts":
        if args.action == "list":
            list_open_shifts(args)
        elif args.action == "post":
            post_open_shift(args)
        elif args.action == "fill":
            fill_open_shift_cmd(args)
    elif args.command == "shift-bids":
        if args.action == "list":
            list_shift_bids_cmd(args)
        elif args.action == "post":
            post_shift_bid_event_cmd(args)
        elif args.action == "submit":
            submit_shift_bid_cmd(args)
        elif args.action == "finalize":
            finalize_shift_bid_cmd(args)
        elif args.action == "show":
            show_shift_bid_cmd(args)
        elif args.action == "reassign":
            reassign_shift_bid_cmd(args)
        elif args.action == "preview":
            preview_shift_bid_cmd(args)
        elif args.action == "participation":
            participation_shift_bid_cmd(args)
        elif args.action == "assignments":
            assignments_shift_bid_cmd(args)
        elif args.action == "import-sim":
            import_sim_shift_bid_cmd(args)
    elif args.command == "callbacks":
        if args.action == "list":
            list_callbacks_cmd(args)
        elif args.action == "sync":
            result = sync_callback_rotation_from_roster()
            print(result.get("message", "Done"))
        elif args.action == "next":
            next_callback_cmd(args)
        elif args.action == "record":
            record_callback_cmd(args)
    elif args.command == "fatigue":
        fatigue_report_cmd(args)
    elif args.command == "audit-log":
        if args.action == "list":
            for row in get_audit_log(args.limit, action_filter=args.action):
                print(
                    f"{row['created_at'][:19]}  {row['action']:<24}  {row.get('username') or '—'}  {row.get('details') or ''}"
                )
        elif args.action == "export":
            result = export_audit_csv(args.output, args.limit, action_filter=args.action)
            if result.get("success"):
                print(f"Audit CSV: {result['path']} ({result['count']} rows)")
            else:
                print(f"Failed: {result.get('message')}")
    elif args.command == "backup":
        action = args.action or "create"
        if action == "list":
            backup_list_cmd()
        elif action == "restore":
            backup_restore_cmd(args.path)
        else:
            backup_create()
    else:
        parser.print_help()


if __name__ == "__main__":
    from scripts.startup_gates import auto_before_cli

    gate_code = auto_before_cli()
    if gate_code != 0:
        from scripts.fix_hint import run_fix_hint

        run_fix_hint(run_audit=True)
        raise SystemExit(gate_code)
    main()
