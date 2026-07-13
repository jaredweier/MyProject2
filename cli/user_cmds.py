"""CLI handlers — user cmds."""

from __future__ import annotations

from logic import (
    admin_reset_user_password,
    create_app_user,
    list_all_users,
    set_app_user_active,
    update_app_user,
)


def list_users_cmd(args):
    users = list_all_users(include_inactive=not args.active_only)
    if not users:
        print("No users found.")
        return
    print(f"{'ID':<5} {'Username':<18} {'Role':<16} {'Officer':<22} {'Active':<7} {'MustChg':<8}")
    print("-" * 90)
    for u in users:
        active = "Yes" if u.get("active") == 1 else "No"
        must_chg = "Yes" if u.get("must_change_password") == 1 else "No"
        print(
            f"{u['id']:<5} {u['username']:<18} {u['role']:<16} "
            f"{(u.get('officer_name') or '—'):<22} {active:<7} {must_chg:<8}"
        )


def create_user_cmd(args):
    result = create_app_user(
        args.username,
        args.password,
        args.role,
        officer_id=args.officer_id,
        must_change_password=not args.no_force_change,
    )
    if result.get("success"):
        print(f"User '{args.username}' created (ID: {result['user_id']})")
    else:
        print(f"Error: {result.get('message', 'Unknown error')}")


def update_user_cmd(args):
    if args.clear_officer_link:
        result = update_app_user(args.user_id, clear_officer_link=True)
    else:
        fields = {}
        if args.role is not None:
            fields["role"] = args.role
        if args.officer_id is not None:
            fields["officer_id"] = args.officer_id
        if not fields:
            print("Error: No fields to update")
            return
        result = update_app_user(args.user_id, **fields)
    if result.get("success"):
        print(f"User {args.user_id} updated")
    else:
        print(f"Error: {result.get('message', 'Unknown error')}")


def reset_user_password_cmd(args):
    result = admin_reset_user_password(
        args.user_id,
        args.password,
        must_change_password=not args.no_force_change,
    )
    if result.get("success"):
        print(f"Password reset for user {args.user_id}")
    else:
        print(f"Error: {result.get('message', 'Unknown error')}")


def set_user_active_cmd(args, active: bool):
    result = set_app_user_active(args.user_id, active)
    if result.get("success"):
        print(result.get("message", "Done"))
    else:
        print(f"Error: {result.get('message', 'Unknown error')}")
