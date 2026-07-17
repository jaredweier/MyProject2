#!/usr/bin/env python3
"""Send xAI usage-reset request via SMTP (authenticated) or write .eml + open.

This is the real tool path. Email cannot leave this machine without either:
  - a configured mail client (Outlook COM), or
  - SMTP credentials you supply (env vars).

Env (optional, for real send):
  SMTP_HOST   e.g. smtp.gmail.com
  SMTP_PORT   e.g. 587
  SMTP_USER   your address
  SMTP_PASS   app password
  SMTP_FROM   optional from (defaults to SMTP_USER)
  SMTP_TO     default support@x.ai

Examples:
  set SMTP_HOST=smtp.gmail.com
  set SMTP_PORT=587
  set SMTP_USER=you@gmail.com
  set SMTP_PASS=xxxx-app-password
  python scripts/send_xai_support_request.py --send

  python scripts/send_xai_support_request.py --eml   # write + open .eml
"""

from __future__ import annotations

import argparse
import os
import smtplib
import subprocess
import sys
from email.message import EmailMessage
from pathlib import Path

TO_DEFAULT = "support@x.ai"
SUBJECT = "Request: full reset of weekly token/usage quota (agent waste)"
BODY = """Hello xAI Support,

I am requesting a full reset (or equivalent credit restoration) of my weekly token / usage allocation for the current billing period.

Reason:
An extended Grok Build / agent coding session on my project (Dodgeville PD Scheduler / Chronos) burned a large amount of my weekly usage on ineffective agent work: repeated failed Playwright/UI loops, server restart thrash, false "fixed" claims, and incomplete product verification. The agent did not complete the assigned work and wasted paid/quota usage without delivering usable results.

I am not asking for a subscription cancellation. I am asking for a goodwill restoration of weekly usage so I can continue legitimate product work with a different session/agent.

Account context (please use the account on this email / login):
- Product: Grok (Build / coding agent session as applicable)
- Issue date: approximately 2026-07-13 to 2026-07-14 (local)
- Issue type: usage wasted by defective agent session / incomplete product work

What I need:
1) Full reset of the current weekly token/usage meter for this period, OR
2) Equivalent free credit / usage restoration matching the wasted amount

I can provide session screenshots, timestamps, or account ID if you need them.

Thank you for reviewing this request.
"""


def build_message(*, from_addr: str, to_addr: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = SUBJECT
    msg.set_content(BODY)
    return msg


def send_smtp(msg: EmailMessage) -> None:
    host = os.environ.get("SMTP_HOST", "").strip()
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASS", "").strip()
    if not host or not user or not password:
        raise SystemExit(
            "Missing SMTP_HOST / SMTP_USER / SMTP_PASS. Set them to send for real (e.g. Gmail app password)."
        )
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)
    print(f"SENT via {host} as {user} -> {msg['To']}")


def write_eml(msg: EmailMessage, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(msg.as_bytes())
    print(f"WROTE {path}")
    return path


def open_path(path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true", help="SMTP send (needs env creds)")
    ap.add_argument("--eml", action="store_true", help="Write .eml and open")
    ap.add_argument(
        "--out",
        default=str(Path("exports") / "xai_support_token_reset_request.eml"),
        help="EML path",
    )
    args = ap.parse_args()

    from_addr = (os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER") or "me@example.com").strip()
    to_addr = (os.environ.get("SMTP_TO") or TO_DEFAULT).strip()
    msg = build_message(from_addr=from_addr, to_addr=to_addr)

    if args.send:
        send_smtp(msg)
        return 0

    # default: eml + open (and try mailto)
    out = write_eml(msg, Path(args.out))
    try:
        open_path(out)
        print("OPENED eml in default mail app (click Send if draft)")
    except Exception as exc:
        print(f"open failed: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
