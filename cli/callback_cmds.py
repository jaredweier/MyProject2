"""CLI handlers — callback cmds."""

from __future__ import annotations

from logic import (
    get_callback_rotation,
    get_fatigue_scoreboard,
    get_next_callback_candidate,
    record_callback_event,
)


def list_callbacks_cmd(_args):
    rotation = get_callback_rotation()
    if not rotation:
        print("Callback rotation empty. Run: python cli.py callbacks sync")
        return
    for row in rotation:
        print(f"#{row['sort_order']:<3} {row['officer_name']:<22} Squad {row.get('squad') or '—'}")


def next_callback_cmd(_args):
    result = get_next_callback_candidate()
    cand = result.get("candidate")
    if not cand:
        print("No callback candidate (sync rotation first).")
        return
    print(f"Next: {cand['officer_name']} (ID {cand['officer_id']})")


def record_callback_cmd(args):
    result = record_callback_event(args.officer_id, args.date, args.hours, notes=args.notes or "")
    if result.get("success"):
        print(f"Callback recorded (ID: {result['event_id']})")
    else:
        print(f"Error: {result.get('message')}")


def fatigue_report_cmd(_args):
    board = get_fatigue_scoreboard(limit=15)
    print(f"Fatigue threshold: {board.get('threshold', 70):.0f}")
    for row in board.get("officers", []):
        flag = row.get("severity") or "ok"
        print(f"{row['officer_name']:<22} {row['score']:5.1f}  [{flag}]")
