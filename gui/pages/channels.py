"""Notify channels admin — email/SMS outbox, Twilio/SMTP ready paths."""

from __future__ import annotations

from nicegui import ui

from gui import session
from gui.shell import layout, page_header, panel
from logic import (
    get_notify_channel_config,
    list_notify_outbox,
    notify_outbox_stats,
    process_notify_outbox,
    prove_notify_paths,
    save_notify_settings,
    test_notify_channels,
)
from logic.product_complete_pack import live_notify_send_test


def render_channels() -> None:
    def body() -> None:
        if not (
            session.can("admin.settings")
            or session.can("settings.manage")
            or session.can("notifications.manage")
            or session.can("users.manage")
        ):
            page_header("Notify channels", "Permission required", kicker="Chronos Command")
            ui.html(
                '<div class="alert alert-warn">Supervisor/admin access required for channel settings.</div>',
                sanitize=False,
            )
            return

        page_header(
            "Notify channels",
            "Email + SMS outbox · SMTP · Twilio-ready (creds optional until you enable live send)",
            kicker="Chronos Command · Weierworks",
        )

        cfg = get_notify_channel_config()
        stats = notify_outbox_stats()
        by = stats.get("by_status") or {}
        with ui.element("div").classes("kpi-row q-mb-md"):
            ui.html(
                f'<div class="kpi g"><div class="kpi-l">Outbox total</div>'
                f'<div class="kpi-v">{stats.get("total", 0)}</div></div>'
                f'<div class="kpi"><div class="kpi-l">Queued</div>'
                f'<div class="kpi-v">{by.get("queued", 0)}</div></div>'
                f'<div class="kpi"><div class="kpi-l">Sent</div>'
                f'<div class="kpi-v">{by.get("sent", 0)}</div></div>'
                f'<div class="kpi"><div class="kpi-l">Failed</div>'
                f'<div class="kpi-v">{by.get("failed", 0)}</div></div>'
                f'<div class="kpi"><div class="kpi-l">Twilio ready</div>'
                f'<div class="kpi-v">{"YES" if cfg.get("twilio_ready") else "NO"}</div></div>'
                f'<div class="kpi"><div class="kpi-l">SMTP ready</div>'
                f'<div class="kpi-v">{"YES" if cfg.get("smtp_ready") or cfg.get("email_enabled") else "NO"}</div></div>',
                sanitize=False,
            )
        # Proof strip — last outbox rows (honest: queued ≠ delivered)
        with panel("Outbox proof strip (last sends)", glow=True):

            def run_proof():
                r = prove_notify_paths(user_id=(session.current_user() or {}).get("id"))
                ui.notify(
                    r.get("message") or "Proof done",
                    type="positive" if r.get("success") else "warning",
                )
                # Force reload to show new rows
                ui.navigate.to("/channels")

            ui.button("Run outbox proof (enqueue + process)", on_click=run_proof).classes("btn-primary").props(
                "no-caps unelevated dense"
            )
            ui.label(
                f"Live capable: email={'YES' if cfg.get('smtp_host') and cfg.get('email_enabled') else 'NO'} · "
                f"SMS={'YES' if cfg.get('twilio_ready') and cfg.get('sms_enabled') else 'NO'} · "
                f"queued≠sent without transport."
            ).classes("text-xs q-mb-sm").style("color: var(--dim)")
            rows = list_notify_outbox(limit=12) or []
            if isinstance(rows, dict):
                rows = rows.get("rows") or rows.get("items") or []
            if not rows:
                ui.label("Outbox empty — run proof or approve leave / callout to enqueue.").classes(
                    "text-xs text-gray-500"
                )
            for row in rows[:12]:
                if not isinstance(row, dict):
                    continue
                st = row.get("status") or "?"
                ui.label(
                    f"#{row.get('id')} · {row.get('channel')} · {st} · "
                    f"{(row.get('subject') or '')[:40]} · {(row.get('last_error') or '')[:40]}"
                ).classes("text-xs")
            ui.label(
                "Honest: SMS/email live only after real Twilio/SMTP send. Outbox path is proved without faking."
            ).classes("text-xs q-mt-sm").style("color: var(--dim)")

        with panel("Live send test (real recipient)", glow=True):
            ui.label(
                "Enter a real email and/or E.164 phone. Marks sent only if SMTP/Twilio succeeds — no fake delivery."
            ).classes("text-xs q-mb-sm").style("color: var(--dim)")
            live_email = ui.input("Test email (optional)").classes("w-full")
            live_phone = ui.input("Test SMS E.164 (optional, e.g. +16085551212)").classes("w-full")

            def run_live():
                uid = (session.current_user() or {}).get("id")
                r = live_notify_send_test(
                    email=(live_email.value or "").strip(),
                    phone=(live_phone.value or "").strip(),
                    user_id=uid,
                )
                ui.notify(
                    r.get("message") or "Done",
                    type="positive" if r.get("live_send_proved") else "info",
                    multi_line=True,
                )
                ui.navigate.to("/channels")

            ui.button("Send live test (real transport)", on_click=run_live).classes("btn-primary").props(
                "no-caps unelevated dense"
            )

        with panel("Transport settings", glow=True):
            email_on = ui.switch("Email channel enabled", value=bool(cfg.get("email_enabled")))
            sms_on = ui.switch("SMS channel enabled", value=bool(cfg.get("sms_enabled")))
            email_from = ui.input("From email", value=cfg.get("email_from") or "").classes("w-full")
            smtp_host = ui.input("SMTP host", value=cfg.get("smtp_host") or "").classes("w-full")
            smtp_port = ui.input("SMTP port", value=str(cfg.get("smtp_port") or "587")).classes("w-full")
            smtp_user = ui.input("SMTP user", value=cfg.get("smtp_user") or "").classes("w-full")
            smtp_pass = ui.input("SMTP password", value=cfg.get("smtp_password") or "", password=True).classes("w-full")
            sms_from = ui.input(
                "SMS from (Twilio number E.164)",
                value=cfg.get("sms_from") or "",
            ).classes("w-full")
            tw_sid = ui.input(
                "Twilio Account SID (or set TWILIO_ACCOUNT_SID env)",
                value=cfg.get("twilio_account_sid") or "",
            ).classes("w-full")
            tw_tok = ui.input(
                "Twilio Auth Token (or set TWILIO_AUTH_TOKEN env)",
                value="",
                password=True,
            ).classes("w-full")
            ui.label(
                "Leave Twilio blank until you decide — messages still queue in the outbox. "
                "File sink writes durable copies under data/notify_sent/ and marks sent (lab/CI)."
            ).classes("text-xs q-mb-sm").style("color: var(--dim)")
            sink_opts = ["none", "file", "log"]
            sink_val = (cfg.get("delivery_sink") or "none").lower()
            if sink_val not in sink_opts:
                sink_val = "none"
            sink = ui.select(sink_opts, value=sink_val, label="Delivery sink (file = local sent proof)").classes(
                "w-full"
            )

            def save():
                payload = {
                    "notify_email_enabled": "1" if email_on.value else "0",
                    "notify_sms_enabled": "1" if sms_on.value else "0",
                    "notify_email_from": email_from.value or "",
                    "notify_smtp_host": smtp_host.value or "",
                    "notify_smtp_port": smtp_port.value or "587",
                    "notify_smtp_user": smtp_user.value or "",
                    "notify_smtp_password": smtp_pass.value or "",
                    "notify_sms_from": sms_from.value or "",
                    "notify_twilio_account_sid": tw_sid.value or "",
                    "notify_delivery_sink": sink.value or "none",
                }
                if (tw_tok.value or "").strip():
                    payload["notify_twilio_auth_token"] = tw_tok.value.strip()
                uid = (session.current_user() or {}).get("id")
                r = save_notify_settings(payload, user_id=uid)
                ui.notify(r.get("message", "Saved"), type="positive" if r.get("success") else "negative")

            with ui.row().classes("gap-2 q-mt-sm flex-wrap"):
                ui.button("Save settings", on_click=save).classes("btn-primary").props("no-caps unelevated")

                def test():
                    uid = (session.current_user() or {}).get("id")
                    r = test_notify_channels(user_id=uid)
                    ui.notify(r.get("message", "Test done"), type="info", multi_line=True)

                def process():
                    r = process_notify_outbox(limit=50)
                    ui.notify(r.get("message", "Processed"), type="positive" if r.get("success") else "warning")

                ui.button("Send test to outbox", on_click=test).classes("btn-ghost").props("no-caps outline")
                ui.button("Process outbox now", on_click=process).classes("btn-ghost").props("no-caps outline")

        with panel("Outbox log (latest)"):
            rows = list_notify_outbox(limit=40)
            if not rows:
                ui.label("No outbound messages yet.").classes("text-sm").style("color: var(--dim)")
            else:
                for row in rows:
                    with ui.element("div").classes("data-row"):
                        ui.label(
                            f"#{row.get('id')} · {row.get('channel')} · {row.get('status')} · "
                            f"{(row.get('recipient') or '—')[:40]}"
                        ).classes("text-sm font-semibold")
                        ui.label(f"{(row.get('subject') or '')[:80]} · err={row.get('last_error') or '—'}").classes(
                            "text-xs"
                        ).style("color: var(--dim)")

    layout("channels", body)
