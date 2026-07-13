"""CLI handlers — notification cmds."""

from __future__ import annotations

from logic import (
    get_notifications,
    get_unread_notification_count,
    mark_all_notifications_read,
    mark_notification_read,
    resolve_notification_navigation,
)


def list_notifications(unread_only: bool = False, officer_id: int = None):
    notes = get_notifications(officer_id=officer_id, unread_only=unread_only)
    unread = get_unread_notification_count(officer_id=officer_id)
    if not notes:
        print(f"No notifications ({unread} unread).")
        return

    print(f"Notifications ({unread} unread):")
    print(f"{'ID':<5} {'To':<20} {'Type':<12} {'Title':<24} {'Nav':<14} {'Read':<6}")
    print("-" * 85)
    for n in notes:
        read_flag = "yes" if n.get("is_read") else "no"
        nav = (resolve_notification_navigation(n) or {}).get("page", "—")
        print(
            f"{n['id']:<5} {n.get('recipient_name', ''):<20} {n.get('type', ''):<12} "
            f"{n.get('title', '')[:24]:<24} {nav:<14} {read_flag:<6}"
        )


def read_notification(notification_id: int):
    result = mark_notification_read(notification_id)
    print("Marked read." if result.get("success") else f"Failed: {result.get('message')}")


def read_all_notifications(officer_id: int = None):
    result = mark_all_notifications_read(officer_id=officer_id)
    if result.get("success"):
        print(f"Marked {result.get('updated', 0)} notification(s) read.")
    else:
        print(f"Failed: {result.get('message')}")
