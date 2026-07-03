"""Magic-link auth (passwordless). Hardcoded 2-email allow-list for the week
(Phase-2 = editable list). Tokens are HMAC-signed + time-limited; the session is a
longer-lived signed cookie. Email goes through the engine mailer (Resend / Gmail
SMTP app password — v2's Google-OAuth sender broke 3x and is gone).

Soft gate by design: the board stays public so the demo URL is always shareable;
login just identifies the operator (vote attribution + 'signed in as')."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
from dealscanner_engine import mailer

# Operator allow-list comes from env (comma-separated) so no emails live in code.
ALLOW_LIST = {e.strip().lower() for e in os.environ.get("ALLOW_LIST", "").split(",") if e.strip()}

# Stable secret persisted next to the DB so restarts don't invalidate sessions.
_SECRET_FILE = Path(__file__).resolve().parents[1] / "data" / ".auth_secret"
def _secret() -> bytes:
    if os.getenv("DS_SECRET"):
        return os.getenv("DS_SECRET").encode()
    if not _SECRET_FILE.exists():
        _SECRET_FILE.write_text(secrets.token_hex(32))
    return _SECRET_FILE.read_text().strip().encode()

def _sign(payload: dict, ttl: int) -> str:
    body = {**payload, "exp": int(time.time()) + ttl}
    raw = base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")
    sig = hmac.new(_secret(), raw.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{raw}.{sig}"


def _unsign(token: str) -> dict | None:
    try:
        raw, sig = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(sig, hmac.new(_secret(), raw.encode(), hashlib.sha256).hexdigest()[:32]):
        return None
    pad = "=" * (-len(raw) % 4)
    body = json.loads(base64.urlsafe_b64decode(raw + pad))
    if body.get("exp", 0) < time.time():
        return None
    return body


def make_login_token(email: str) -> str:
    return _sign({"email": email, "kind": "login"}, ttl=900)        # 15 min


def make_session(email: str) -> str:
    return _sign({"email": email, "kind": "session"}, ttl=60 * 60 * 24 * 14)  # 14 days


def email_from_login_token(token: str) -> str | None:
    b = _unsign(token)
    return b["email"] if b and b.get("kind") == "login" else None


def email_from_session(token: str | None) -> str | None:
    if not token:
        return None
    b = _unsign(token)
    return b["email"] if b and b.get("kind") == "session" else None


def send_magic_link(to: str, link: str) -> None:
    body = (f"Hi — here's your sign-in link for the DealScanner desk:\n\n{link}\n\n"
            "It expires in 15 minutes. If you didn't request this, ignore it.")
    mailer.send(to, "Your DealScanner sign-in link", body)
