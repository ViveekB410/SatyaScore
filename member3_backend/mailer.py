"""
Sends the password-reset email (Python standard library only: smtplib over TLS).

Configuration, read from the server's environment when an email is sent (never logged or stored):
  SATYASCORE_SMTP_HOST      e.g. smtp.gmail.com
  SATYASCORE_SMTP_PORT      587 (STARTTLS, default) or 465 (TLS from the start)
  SATYASCORE_SMTP_USER      the sending account, e.g. satyascore.app@gmail.com
  SATYASCORE_SMTP_PASSWORD  its password; for Gmail an "App password" (needs 2-step verification)
  SATYASCORE_SMTP_FROM      optional sender address shown to the user (default: SATYASCORE_SMTP_USER)

Without SATYASCORE_SMTP_HOST the code is printed to the server console instead (local demo mode: whoever can
read that console is the administrator anyway).
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


def configured() -> bool:
    return bool(os.environ.get("SATYASCORE_SMTP_HOST") and os.environ.get("SATYASCORE_SMTP_USER")
                and os.environ.get("SATYASCORE_SMTP_PASSWORD"))


def reset_message(to: str, code: str, minutes: int, sender: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = f"Your Satya-Score password reset code: {code}"
    msg["From"] = f"Satya-Score <{sender}>"
    msg["To"] = to
    msg.set_content(
        f"Your password reset code is:\n\n    {code}\n\n"
        f"Enter it on the Reset password page within {minutes} minutes. It works once.\n\n"
        "If you did not ask to reset your password, ignore this email; your password stays the same.\n\n"
        "Satya-Score")
    return msg


def send_reset_code(to: str, code: str, minutes: int) -> None:
    """Email the code, or print it to the server console when no mail server is configured.
    Raises on a mail-server error (the caller logs it; the user sees the same answer either way)."""
    if not configured():
        print(f"[auth] email not configured: reset code for {to} is {code} (valid {minutes} minutes)", flush=True)
        return
    host = os.environ["SATYASCORE_SMTP_HOST"]
    port = int(os.environ.get("SATYASCORE_SMTP_PORT", "587"))
    user, password = os.environ["SATYASCORE_SMTP_USER"], os.environ["SATYASCORE_SMTP_PASSWORD"]
    msg = reset_message(to, code, minutes, os.environ.get("SATYASCORE_SMTP_FROM") or user)
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as s:
            s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as s:
            s.starttls(context=context)
            s.login(user, password)
            s.send_message(msg)
