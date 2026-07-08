"""Officer roster CLI commands."""

from __future__ import annotations

import argparse

from logic import (
    add_custom_officer_title,
    get_builtin_officer_titles,
    get_custom_officer_titles,
    get_officer_title_options,
    get_officers_by_seniority,
    import_roster_from_csv,
)
from logic import add_officer as logic_add_officer
from logic import delete_officer as logic_delete_officer
from logic import update_officer as logic_update_officer
from validators import format_date


def list_officers() -> None:
    officers = get_officers_by_seniority()
    if not officers:
        print("No officers found.")
        return

    from validators import format_officer_title_display

    print(
        f"{'ID':<5} {'Name':<22} {'Title':<22} {'Squad':<6} {'Shift':<15} {'Start':<12} "
        f"{'Phone':<16} {'Email':<24} {'Active':<6}"
    )
    print("-" * 140)
    for o in officers:
        shift = f"{o['shift_start']}-{o['shift_end']}"
        active = "Yes" if o.get("active") == 1 else "No"
        title = format_officer_title_display(o.get("job_title")) or "—"
        print(
            f"{o['id']:<5} {o['name']:<22} {title:<22} {o['squad']:<6} {shift:<15} "
            f"{(format_date(o['start_date']) if o.get('start_date') else '—'):<12} {(o.get('phone') or '—'):<16} "
            f"{(o.get('email') or '—'):<24} {active:<6}"
        )


def _validate_cli_job_title(job_title: str) -> bool:
    from validators import validate_officer_job_title

    if not job_title:
        return True
    check = validate_officer_job_title(job_title)
    if not check.ok:
        print(f"Error: {check.message}")
        return False
    return True


def list_officer_titles_cmd(_args) -> None:
    print("Standard titles:", ", ".join(get_builtin_officer_titles()))
    custom = get_custom_officer_titles()
    if custom:
        print("Custom titles:", ", ".join(custom))
    else:
        print("Custom titles: (none)")
    print("All assignable:", ", ".join(get_officer_title_options()))


def add_officer_title_cmd(args) -> None:
    result = add_custom_officer_title(args.title)
    if result.get("success"):
        print(result.get("message", "Title added"))
    else:
        print(f"Error: {result.get('message', 'Unknown error')}")


def add_officer(args) -> None:
    if args.job_title and not _validate_cli_job_title(args.job_title):
        return
    result = logic_add_officer(
        args.name,
        args.seniority,
        args.squad,
        args.shift_start,
        args.shift_end,
        args.pay_rate,
        start_date=args.start_date,
        email=args.email,
        phone=args.phone,
        address=args.address,
        job_title=args.job_title,
    )
    if result.get("success"):
        print(f"Officer '{args.name}' added successfully (ID: {result['officer_id']})")
    else:
        print(f"Error: {result.get('message', 'Unknown error')}")


def update_officer_cmd(args) -> None:
    if args.job_title and not _validate_cli_job_title(args.job_title):
        return
    fields = {}
    for key in (
        "name",
        "seniority_rank",
        "squad",
        "shift_start",
        "shift_end",
        "pay_rate",
        "start_date",
        "email",
        "phone",
        "address",
        "job_title",
    ):
        cli_key = key if key != "seniority_rank" else "seniority"
        value = getattr(args, cli_key, None)
        if value is not None:
            fields[key] = value
    if args.active is not None:
        fields["active"] = 1 if args.active else 0
    if not fields:
        print("Error: No fields to update")
        return
    result = logic_update_officer(args.officer_id, **fields)
    if result.get("success"):
        print(f"Officer {args.officer_id} updated successfully")
    else:
        print(f"Error: {result.get('message', 'Unknown error')}")


def delete_officer_cmd(args) -> None:
    result = logic_delete_officer(args.officer_id)
    if result.get("success"):
        print(result.get("message", "Officer deleted"))
    else:
        print(f"Error: {result.get('message', 'Unknown error')}")


def import_officers_cmd(args) -> None:
    result = import_roster_from_csv(args.file, update_existing=not args.skip_existing)
    print(result.get("message", "Done"))
    for detail in result.get("error_details", []):
        print(f"  {detail}")


def register_officers_parser(officers_sub: argparse._SubParsersAction) -> None:
    officers_sub.add_parser("list", help="List all officers")

    add = officers_sub.add_parser("add", help="Add new officer")
    add.add_argument("--name", required=True)
    add.add_argument("--seniority", type=int, required=True)
    add.add_argument("--squad", required=True, choices=["A", "B"])
    add.add_argument("--shift-start", required=True)
    add.add_argument("--shift-end", required=True)
    add.add_argument("--pay-rate", type=float, default=30.0)
    add.add_argument("--start-date", help="Employment start date DD-MM-YYYY")
    add.add_argument("--email")
    add.add_argument("--phone")
    add.add_argument("--address")
    add.add_argument("--job-title", help="Roster title (standard or supervisor-added custom)")

    update = officers_sub.add_parser("update", help="Update an officer")
    update.add_argument("officer_id", type=int)
    update.add_argument("--name")
    update.add_argument("--seniority", type=int, dest="seniority")
    update.add_argument("--squad", choices=["A", "B"])
    update.add_argument("--shift-start")
    update.add_argument("--shift-end")
    update.add_argument("--pay-rate", type=float)
    update.add_argument("--start-date")
    update.add_argument("--email")
    update.add_argument("--phone")
    update.add_argument("--address")
    update.add_argument("--job-title", dest="job_title", help="Roster title (standard or custom)")
    update.add_argument("--active", type=int, choices=[0, 1])

    delete = officers_sub.add_parser("delete", help="Delete an officer without scheduling history")
    delete.add_argument("officer_id", type=int)

    titles = officers_sub.add_parser("titles", help="Manage assignable roster titles")
    titles_sub = titles.add_subparsers(dest="titles_action")
    titles_sub.add_parser("list", help="List standard and custom titles")
    titles_add = titles_sub.add_parser("add", help="Add a custom title")
    titles_add.add_argument("title", help="New title name")

    imp = officers_sub.add_parser("import", help="Import roster from CSV (export format)")
    imp.add_argument("--file", required=True, help="Path to roster CSV file")
    imp.add_argument(
        "--skip-existing",
        action="store_true",
        help="Do not update officers matched by ID; only add new rows",
    )


def dispatch_officers(args) -> None:
    if args.action == "list":
        list_officers()
    elif args.action == "add":
        add_officer(args)
    elif args.action == "update":
        update_officer_cmd(args)
    elif args.action == "delete":
        delete_officer_cmd(args)
    elif args.action == "import":
        import_officers_cmd(args)
    elif args.action == "titles":
        if args.titles_action == "list":
            list_officer_titles_cmd(args)
        elif args.titles_action == "add":
            add_officer_title_cmd(args)
