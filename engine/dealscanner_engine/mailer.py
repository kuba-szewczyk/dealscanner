"""One place to send email, with a pluggable backend so delivery is reliable and not
tied to a personal inbox.

Picks the backend from env (no code change to switch):
  * RESEND_API_KEY set  -> Resend transactional API, from MAIL_FROM (e.g. deals@dealscanner.us).
                           Reliable, domain-authenticated, off the personal inbox. RECOMMENDED.
  * else                -> Gmail SMTP + App Password (GMAIL_ADDRESS / GMAIL_APP_PASSWORD).
                           Works out of the box but uses a personal Gmail.
"""
from __future__ import annotations

import json
import os
import smtplib
import ssl
import urllib.error
import urllib.request
from email.mime.text import MIMEText


def send_email(recipients: list[str], subject: str, html: str) -> str:
    """Send an HTML email. Returns the backend used. Raises on failure."""
    if os.getenv("RESEND_API_KEY"):
        _send_resend(recipients, subject, html)
        return "resend"
    _send_gmail(recipients, subject, html)
    return "gmail"


def _send_resend(recipients: list[str], subject: str, html: str) -> None:
    key = os.environ["RESEND_API_KEY"]
    sender = os.getenv("MAIL_FROM", "DealScanner <deals@dealscanner.us>")
    payload = json.dumps({"from": sender, "to": recipients, "subject": subject, "html": html}).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails", data=payload,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": "DealScanner-mailer/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Resend {e.code}: {e.read().decode()[:300]}") from None


def _send_gmail(recipients: list[str], subject: str, html: str) -> None:
    sender = os.environ["GMAIL_ADDRESS"]
    pw = os.environ["GMAIL_APP_PASSWORD"]
    msg = MIMEText(html, "html")
    msg["from"] = sender
    msg["to"] = ", ".join(recipients)
    msg["subject"] = subject
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(sender, pw)
        smtp.send_message(msg)
