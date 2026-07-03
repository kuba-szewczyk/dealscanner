"""Outbound email for v3: Resend HTTP API first, Gmail SMTP app-password fallback.

Deliberately stdlib-only (urllib + smtplib) — v2's Google-OAuth Gmail sender broke
three times (token expiry/revocation); app passwords and API keys don't. Config via
env / repo-root .env:

  RESEND_API_KEY      primary sender (api.resend.com)
  MAIL_FROM           from-address for Resend (must be a verified domain/sender)
  GMAIL_ADDRESS       fallback: Gmail account
  GMAIL_APP_PASSWORD  fallback: app password (myaccount.google.com/apppasswords)
"""
from __future__ import annotations

import json
import os
import smtplib
import urllib.error
import urllib.request
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Resend's Cloudflare returns 403 "error code: 1010" if no User-Agent is sent.
_UA = "dealscanner-v3-mailer/1.0"


class MailError(RuntimeError):
    pass


def _send_resend(to: list[str], subject: str, text: str) -> None:
    payload = {
        "from": os.environ.get("MAIL_FROM") or os.environ["GMAIL_ADDRESS"],
        "to": to,
        "subject": subject,
        "text": text,
    }
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['RESEND_API_KEY']}",
            "Content-Type": "application/json",
            "User-Agent": _UA,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status >= 300:
            raise MailError(f"resend HTTP {resp.status}")


def _send_gmail_smtp(to: list[str], subject: str, text: str) -> None:
    addr = os.environ["GMAIL_ADDRESS"]
    msg = MIMEText(text, "plain")
    msg["From"] = addr
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(addr, os.environ["GMAIL_APP_PASSWORD"])
        s.sendmail(addr, to, msg.as_string())


def send(to: str | list[str], subject: str, text: str) -> str:
    """Send via Resend, falling back to Gmail SMTP. Returns the method used."""
    recipients = [to] if isinstance(to, str) else list(to)
    errors = []
    if os.environ.get("RESEND_API_KEY"):
        try:
            _send_resend(recipients, subject, text)
            return "resend"
        except (urllib.error.URLError, KeyError, MailError, OSError) as e:
            errors.append(f"resend: {e}")
    if os.environ.get("GMAIL_ADDRESS") and os.environ.get("GMAIL_APP_PASSWORD"):
        try:
            _send_gmail_smtp(recipients, subject, text)
            return "gmail-smtp"
        except (smtplib.SMTPException, OSError) as e:
            errors.append(f"gmail-smtp: {e}")
    raise MailError("all mail methods failed or unconfigured: " + ("; ".join(errors) or
                    "set RESEND_API_KEY or GMAIL_ADDRESS+GMAIL_APP_PASSWORD"))
