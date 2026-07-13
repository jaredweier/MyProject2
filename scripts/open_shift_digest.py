"""
Notify officers of open vacancies (in-app digest — vacancy alerter lite).

    python dev.py open-shift-digest
    python dev.py open-shift-digest --dry-run
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def run_open_shift_digest(*, dry_run: bool = False) -> int:
    from logic import create_notification, get_officers_by_seniority, get_open_shifts
    from validators import format_date

    opens = get_open_shifts(status="open", limit=50) or []
    print(f"Open vacancies: {len(opens)}")
    if not opens:
        print("Nothing to notify.")
        return 0

    lines = []
    for sh in opens[:20]:
        lines.append(
            f"- {format_date(sh.get('shift_date'))} {sh.get('shift_start')}-"
            f"{sh.get('shift_end')} squad {sh.get('squad') or 'Any'}"
            f"{(' · ' + sh['notes']) if sh.get('notes') else ''}"
        )
    body = "Open shift vacancies available to claim:\n" + "\n".join(lines)
    body += "\n\nChronos → Open Shifts to claim."
    title = f"{len(opens)} open shift vacancy(ies)"

    officers = [o for o in get_officers_by_seniority() if o.get("active") == 1]
    sent = 0
    for o in officers:
        oid = o["id"]
        if dry_run:
            print(f"  dry-run → {o.get('name')} (id={oid})")
            sent += 1
            continue
        try:
            r = create_notification(oid, "open_shift", title, body[:1800])
            if r.get("success") is False:
                print(f"  fail {oid}: {r.get('message')}")
            else:
                sent += 1
        except Exception as exc:
            print(f"  fail {oid}: {exc}")

    print(f"Digest {'preview' if dry_run else 'sent'}: {sent} officers")
    return 0


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    raise SystemExit(run_open_shift_digest(dry_run=a.dry_run))
