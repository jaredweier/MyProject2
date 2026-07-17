"""Notification channel hooks (email/SMS) — config-driven.

In-app notifications remain the primary delivery path. When email/SMS is
enabled in department_settings, hooks queue outbound intent and optionally
attempt SMTP when notify_smtp_host is set. SMS uses Twilio when
notify_twilio_account_sid + auth_token + from are set; otherwise audit-only.
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Dict, List, Optional

# Named templates for open-shift / schedule / callback fills
NOTIFY_TEMPLATES: Dict[str, Dict[str, str]] = {
    "open_shift": {
        "subject": "Open shift available — {date} {start}-{end}",
        "body": ("Open shift posted for {date} {start}-{end}{squad_part}. Claim in Chronos → Open Shifts.{notes_part}"),
    },
    "schedule_published": {
        "subject": "Schedule published — {label}",
        "body": ("Updated duty schedule published ({label}). Review My Schedule in Chronos for changes."),
    },
    "callback_offer": {
        "subject": "OT / callback offer — {date}",
        "body": (
            "You are next on the callback list for {date}. Reply via supervisor or Chronos Callback board. {notes_part}"
        ),
    },
    "leave_decision": {
        "subject": "Time-off {status} — {date}",
        "body": "Your {request_type} request for {date} is {status}.{notes_part}",
    },
    "shift_bid_open": {
        "subject": "Shift bid open — {title}",
        "body": (
            "Bid season open: {title}. Rank your preferred shifts in Chronos Command → Shift Bidding "
            "before {due}.{notes_part}"
        ),
    },
    "shift_bid_award": {
        "subject": "Shift bid award — {title}",
        "body": "Your bid award for {title}: {award_label}.{notes_part}",
    },
    "swap_decision": {
        "subject": "Shift exchange {status}",
        "body": "Shift exchange for {date} is {status}.{notes_part}",
    },
    "court_reminder": {
        "subject": "Court / training — {date}",
        "body": "You have court/training on {date} {start}-{end}.{notes_part}",
    },
    "fatigue_alert": {
        "subject": "Rest / fatigue alert",
        "body": "Scheduling notice: rest or fatigue rule may apply for {date}.{notes_part}",
    },
    "vacancy_blast": {
        "subject": "Vacancy — {date} {start}-{end}",
        "body": (
            "Coverage vacancy {date} {start}-{end}. "
            "Claim in Chronos Command → Open Shifts or reply to your supervisor.{notes_part}"
        ),
    },
    "callout_order": {
        "subject": "Ordered in — {date}",
        "body": (
            "You are ordered in for {date} {start}-{end}. "
            "Reason: {reason}. Confirm with supervisor in Chronos Ops Desk.{notes_part}"
        ),
    },
    "leave_approved": {
        "subject": "Leave approved — {date}",
        "body": "Your leave for {date} was approved.{plan_part}{notes_part}",
    },
    "leave_cover": {
        "subject": "Coverage assignment — {date}",
        "body": "You are covering a shift on {date}.{plan_part}{notes_part}",
    },
    "channel_test": {
        "subject": "Chronos channel test",
        "body": "Test message from Chronos Command outbox proof path.{notes_part}",
    },
}


def format_notify_template(template_key: str, **fields) -> Dict[str, str]:
    """Fill a named template. Missing keys become empty strings."""
    tpl = NOTIFY_TEMPLATES.get(template_key) or {
        "subject": fields.get("subject") or "Chronos notification",
        "body": fields.get("body") or "",
    }
    safe = {k: ("" if v is None else str(v)) for k, v in fields.items()}
    if "squad_part" not in safe:
        sq = safe.get("squad") or ""
        safe["squad_part"] = f" (squad {sq})" if sq else ""
    if "notes_part" not in safe:
        n = (safe.get("notes") or "").strip()
        safe["notes_part"] = f"\n\n{n}" if n else ""
    if "plan_part" not in safe:
        p = (safe.get("plan") or safe.get("plan_text") or "").strip()
        safe["plan_part"] = f" Coverage: {p}." if p else ""
    if "reason" not in safe:
        safe["reason"] = safe.get("request_type") or "coverage"
    if "start" not in safe:
        safe["start"] = ""
    if "end" not in safe:
        safe["end"] = ""
    if "date" not in safe:
        safe["date"] = ""
    try:
        subject = tpl["subject"].format(**safe)
        body = tpl["body"].format(**safe)
    except (KeyError, ValueError):
        subject = tpl.get("subject", "Chronos notification")
        body = tpl.get("body", "")
    return {"subject": subject[:200], "body": body[:4000], "template": template_key}


def _truthy(raw: str) -> bool:
    return (raw or "").strip().lower() in ("1", "true", "yes", "on")


def get_notify_channel_config() -> Dict:
    from logic.operations import get_department_setting

    sid = (get_department_setting("notify_twilio_account_sid", "") or "").strip()
    token = (get_department_setting("notify_twilio_auth_token", "") or "").strip()
    # Env fallback for secrets (preferred in deploy)
    if not sid:
        sid = (os.environ.get("TWILIO_ACCOUNT_SID") or os.environ.get("SCHEDULER_TWILIO_SID") or "").strip()
    if not token:
        token = (os.environ.get("TWILIO_AUTH_TOKEN") or os.environ.get("SCHEDULER_TWILIO_TOKEN") or "").strip()
    sms_from = (get_department_setting("notify_sms_from", "") or "").strip()
    if not sms_from:
        sms_from = (os.environ.get("TWILIO_FROM_NUMBER") or os.environ.get("SCHEDULER_TWILIO_FROM") or "").strip()

    smtp_host = (get_department_setting("notify_smtp_host", "") or "").strip()
    if not smtp_host:
        smtp_host = (os.environ.get("SCHEDULER_SMTP_HOST") or os.environ.get("SMTP_HOST") or "").strip()
    smtp_user = (get_department_setting("notify_smtp_user", "") or "").strip()
    if not smtp_user:
        smtp_user = (os.environ.get("SCHEDULER_SMTP_USER") or os.environ.get("SMTP_USER") or "").strip()
    smtp_password = (get_department_setting("notify_smtp_password", "") or "").strip()
    if not smtp_password:
        smtp_password = (os.environ.get("SCHEDULER_SMTP_PASSWORD") or os.environ.get("SMTP_PASSWORD") or "").strip()
    smtp_port = (get_department_setting("notify_smtp_port", "587") or "587").strip()
    if os.environ.get("SCHEDULER_SMTP_PORT"):
        smtp_port = os.environ.get("SCHEDULER_SMTP_PORT", smtp_port).strip()

    # Delivery sink: file = durable local "sent" proof (dev/demo/CI); none = wait for SMTP/Twilio
    sink = (get_department_setting("notify_delivery_sink", "") or "").strip().lower()
    if not sink:
        sink = (os.environ.get("SCHEDULER_NOTIFY_SINK") or "none").strip().lower()
    if sink not in ("file", "none", "log"):
        sink = "none"

    return {
        "email_enabled": _truthy(get_department_setting("notify_email_enabled", "0")),
        "sms_enabled": _truthy(get_department_setting("notify_sms_enabled", "0")),
        "email_from": (get_department_setting("notify_email_from", "") or "").strip()
        or (os.environ.get("SCHEDULER_EMAIL_FROM") or "").strip(),
        "sms_from": sms_from,
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "smtp_user": smtp_user,
        "smtp_password": smtp_password,
        "smtp_tls": _truthy(get_department_setting("notify_smtp_tls", "1")),
        "twilio_account_sid": sid,
        "twilio_auth_token": token,
        "twilio_ready": bool(sid and token and sms_from),
        "delivery_sink": sink,
        "file_sink_ready": sink in ("file", "log"),
    }


def deliver_via_file_sink(
    *,
    channel: str,
    subject: str,
    body: str,
    recipient: str,
    row_id: Optional[int] = None,
) -> Dict:
    """Durable local delivery — writes message to data/notify_sent/ and returns sent=1.

    Used when notify_delivery_sink=file|log so departments can prove end-to-end
    delivery without Twilio/SMTP (and for CI). Real Twilio/SMTP still preferred in field.
    """
    from datetime import datetime
    from pathlib import Path

    from paths import data_path

    try:
        dest_dir = Path(data_path("notify_sent"))
        dest_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rid = row_id or 0
        path = dest_dir / f"{channel}_{rid}_{stamp}.txt"
        text = (
            f"channel={channel}\n"
            f"to={recipient}\n"
            f"subject={subject}\n"
            f"sent_at={datetime.now().isoformat(timespec='seconds')}\n"
            f"provider=file_sink\n"
            f"---\n"
            f"{body or ''}\n"
        )
        path.write_text(text, encoding="utf-8")
        return {"sent": 1, "error": None, "path": str(path), "provider": "file_sink"}
    except Exception as exc:
        return {"sent": 0, "error": str(exc)[:200], "provider": "file_sink"}


def _officer_contact(officer_ids: Optional[list]) -> Dict[str, List]:
    """Return {emails, phones, officer_rows} for dispatch."""
    empty = {"emails": [], "phones": [], "officers": []}
    if not officer_ids:
        return empty
    try:
        from logic.officers import get_officer_by_id
    except Exception:
        return empty
    emails: List[str] = []
    phones: List[str] = []
    officers: List[Dict] = []
    seen_e: set = set()
    seen_p: set = set()
    for oid in officer_ids:
        try:
            o = get_officer_by_id(int(oid))
        except Exception:
            continue
        if not o:
            continue
        officers.append(o)
        for key in ("email", "contact_email", "notify_email"):
            raw = (o.get(key) or "").strip()
            if raw and "@" in raw:
                el = raw.lower()
                if el not in seen_e:
                    seen_e.add(el)
                    emails.append(raw)
                break
        for key in ("phone", "mobile", "cell", "contact_phone", "notify_sms"):
            raw = (o.get(key) or "").strip()
            digits = "".join(c for c in raw if c.isdigit() or c == "+")
            if len(digits) >= 10:
                if digits not in seen_p:
                    seen_p.add(digits)
                    phones.append(digits if digits.startswith("+") else digits)
                break
    return {"emails": emails, "phones": phones, "officers": officers}


def _officer_emails(officer_ids: Optional[list]) -> List[str]:
    return _officer_contact(officer_ids)["emails"]


def _try_twilio_sms(*, body: str, phones: List[str], cfg: Dict) -> Dict:
    """Best-effort Twilio REST. Never raises. No SDK required (urllib)."""
    if not cfg.get("twilio_ready") or not phones:
        return {"sent": 0, "error": None if cfg.get("twilio_ready") else "twilio_not_configured"}
    sid = cfg.get("twilio_account_sid") or ""
    token = cfg.get("twilio_auth_token") or ""
    from_num = cfg.get("sms_from") or ""
    sent = 0
    last_err = None
    try:
        import base64
        import urllib.error
        import urllib.parse
        import urllib.request

        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
        for phone in phones[:20]:
            to = phone if phone.startswith("+") else f"+1{phone[-10:]}"
            data = urllib.parse.urlencode({"To": to, "From": from_num, "Body": (body or "")[:1500]}).encode()
            req = urllib.request.Request(
                url,
                data=data,
                method="POST",
                headers={
                    "Authorization": f"Basic {auth}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=12) as resp:
                    if 200 <= resp.status < 300:
                        sent += 1
                    else:
                        last_err = f"http_{resp.status}"
            except urllib.error.HTTPError as exc:
                last_err = f"http_{exc.code}"
            except Exception as exc:
                last_err = str(exc)[:120]
    except Exception as exc:
        return {"sent": sent, "error": str(exc)[:200]}
    return {"sent": sent, "error": last_err}


def _try_smtp_send(*, subject: str, body: str, recipients: List[str], cfg: Dict) -> Dict:
    """Best-effort SMTP. Never raises to callers."""
    host = cfg.get("smtp_host") or ""
    if not host or not recipients:
        return {"sent": 0, "error": None if host else "no_smtp_host"}
    try:
        port = int(cfg.get("smtp_port") or 587)
    except (TypeError, ValueError):
        port = 587
    sender = cfg.get("email_from") or cfg.get("smtp_user") or "noreply@localhost"
    msg = EmailMessage()
    msg["Subject"] = subject[:200]
    msg["From"] = sender
    msg["To"] = ", ".join(recipients[:50])
    msg.set_content((body or "")[:4000])
    try:
        if cfg.get("smtp_tls", True):
            with smtplib.SMTP(host, port, timeout=12) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                user = cfg.get("smtp_user") or ""
                pw = cfg.get("smtp_password") or ""
                if user:
                    smtp.login(user, pw)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=12) as smtp:
                user = cfg.get("smtp_user") or ""
                pw = cfg.get("smtp_password") or ""
                if user:
                    smtp.login(user, pw)
                smtp.send_message(msg)
        return {"sent": len(recipients), "error": None}
    except Exception as exc:
        return {"sent": 0, "error": str(exc)[:200]}


def dispatch_channel_hooks(
    *,
    subject: str,
    body: str,
    officer_ids: Optional[list] = None,
    prefer_sms: bool = False,
    user_id: Optional[int] = None,
    template: Optional[str] = None,
    template_fields: Optional[Dict] = None,
) -> Dict:
    """Record external notify intent; send SMTP/Twilio when configured. Never raises.

    Returns {success, email_queued, sms_queued, email_sent, sms_sent, message}.
    Optional *template* + *template_fields* override subject/body via NOTIFY_TEMPLATES.
    """
    if template:
        filled = format_notify_template(template, **(template_fields or {}))
        subject = filled["subject"] or subject
        body = filled["body"] or body

    cfg = get_notify_channel_config()
    email_q = bool(cfg["email_enabled"])
    sms_q = bool(cfg["sms_enabled"])
    if prefer_sms and sms_q:
        pass
    if prefer_sms and not sms_q and email_q:
        email_q = True
    if prefer_sms and sms_q and not cfg["email_enabled"]:
        email_q = False
    if not prefer_sms:
        email_q = bool(cfg["email_enabled"])
        sms_q = bool(cfg["sms_enabled"])

    if not email_q and not sms_q:
        return {
            "success": True,
            "email_queued": False,
            "sms_queued": False,
            "email_sent": 0,
            "sms_sent": 0,
            "message": "In-app only (email/SMS channels off)",
        }

    contacts = _officer_contact(officer_ids)
    recipients = contacts["emails"] if email_q else []
    phones = contacts["phones"] if sms_q else []

    # Durable outbox — always ready; delivery when SMTP/Twilio configured
    outbox_ids: List[int] = []
    try:
        from logic.notify_queue import enqueue_notify

        if email_q:
            if recipients:
                for em in recipients:
                    outbox_ids.append(
                        enqueue_notify(
                            channel="email",
                            subject=subject,
                            body=body,
                            recipient=em,
                            template_key=template,
                            user_id=user_id,
                            meta={"prefer_sms": prefer_sms},
                        )
                    )
            else:
                outbox_ids.append(
                    enqueue_notify(
                        channel="email",
                        subject=subject,
                        body=body,
                        recipient="",
                        template_key=template,
                        user_id=user_id,
                        meta={"note": "no_officer_emails"},
                    )
                )
        if sms_q:
            if phones:
                for ph in phones:
                    outbox_ids.append(
                        enqueue_notify(
                            channel="sms",
                            subject=subject,
                            body=body,
                            recipient=ph,
                            template_key=template,
                            user_id=user_id,
                            meta={"prefer_sms": prefer_sms},
                        )
                    )
            else:
                outbox_ids.append(
                    enqueue_notify(
                        channel="sms",
                        subject=subject,
                        body=body,
                        recipient="",
                        template_key=template,
                        user_id=user_id,
                        meta={"note": "no_officer_phones"},
                    )
                )
    except Exception:
        pass

    smtp_result = {"sent": 0, "error": None}
    if email_q and recipients and cfg.get("smtp_host"):
        smtp_result = _try_smtp_send(subject=subject, body=body, recipients=recipients, cfg=cfg)
    sms_result = {"sent": 0, "error": None}
    if sms_q and phones:
        sms_result = _try_twilio_sms(body=body, phones=phones, cfg=cfg)

    # Best-effort: mark outbox rows sent when immediate delivery succeeded
    try:
        if smtp_result.get("sent") or sms_result.get("sent"):
            from logic.notify_queue import process_notify_outbox

            process_notify_outbox(limit=max(10, len(outbox_ids) or 10))
    except Exception:
        pass

    try:
        from logic.users import log_audit_action

        log_audit_action(
            "notify.channel_hook",
            "notification",
            None,
            user_id,
            (
                f"subject={subject[:80]!r} email={email_q} sms={sms_q} "
                f"tpl={template or '-'} officers={len(officer_ids or [])} "
                f"recipients={len(recipients)} phones={len(phones)} "
                f"outbox={len(outbox_ids)} "
                f"smtp_sent={smtp_result.get('sent')} "
                f"sms_sent={sms_result.get('sent')} "
                f"smtp_err={smtp_result.get('error')!r} "
                f"sms_err={sms_result.get('error')!r}"
            )[:240],
        )
    except Exception:
        pass

    parts = []
    if email_q:
        if smtp_result.get("sent"):
            parts.append(f"email sent to {smtp_result['sent']}")
        elif cfg.get("smtp_host"):
            parts.append(f"email queued (smtp error: {smtp_result.get('error') or 'none'})")
        else:
            parts.append("email queued in outbox (set SMTP host to deliver)")
    if sms_q:
        if sms_result.get("sent"):
            parts.append(f"sms sent to {sms_result['sent']}")
        elif cfg.get("twilio_ready"):
            parts.append(f"sms queued (twilio error: {sms_result.get('error') or 'none'})")
        else:
            parts.append("sms queued in outbox (set Twilio SID/token/from to deliver)")
    return {
        "success": True,
        "email_queued": email_q,
        "sms_queued": sms_q,
        "email_sent": int(smtp_result.get("sent") or 0),
        "sms_sent": int(sms_result.get("sent") or 0),
        "outbox_ids": outbox_ids,
        "message": "; ".join(parts) if parts else "No channels active",
    }


def test_notify_channels(*, user_id: Optional[int] = None) -> Dict:
    """Enqueue a self-test message and report transport readiness (no crash without Twilio)."""
    from logic.notify_queue import prove_notify_paths

    cfg = get_notify_channel_config()
    r = dispatch_channel_hooks(
        subject="Chronos Command channel test",
        body=(
            "Test message from Chronos Command (Weierworks Technologies, LLC). "
            "If you received this, email/SMS transport is live."
        ),
        officer_ids=None,
        user_id=user_id,
        template=None,
    )
    proof = prove_notify_paths(user_id=user_id)
    return {
        "success": True,
        "config": {
            "email_enabled": cfg.get("email_enabled"),
            "sms_enabled": cfg.get("sms_enabled"),
            "smtp_configured": bool(cfg.get("smtp_host")),
            "twilio_ready": bool(cfg.get("twilio_ready")),
            "live_email_capable": proof.get("live_email_capable"),
            "live_sms_capable": proof.get("live_sms_capable"),
            "live_send_proved": proof.get("live_send_proved"),
        },
        "dispatch": r,
        "proof": proof,
        "message": proof.get("message")
        or (
            f"Test queued. Email enabled={cfg.get('email_enabled')} "
            f"SMTP={bool(cfg.get('smtp_host'))} "
            f"SMS enabled={cfg.get('sms_enabled')} "
            f"Twilio ready={cfg.get('twilio_ready')}"
        ),
    }


def dispatch_template(
    template_key: str,
    *,
    officer_ids: Optional[list] = None,
    prefer_sms: bool = False,
    user_id: Optional[int] = None,
    **fields,
) -> Dict:
    """Convenience: named template + channel dispatch."""
    filled = format_notify_template(template_key, **fields)
    return dispatch_channel_hooks(
        subject=filled["subject"],
        body=filled["body"],
        officer_ids=officer_ids,
        prefer_sms=prefer_sms,
        user_id=user_id,
        template=template_key,
        template_fields=fields,
    )
