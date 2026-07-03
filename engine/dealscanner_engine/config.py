"""Central config: load the .env once from a portable location, expose settings.

Env resolution order: $DEALSCANNER_ENV, the server path, then the repo root — so the
same code runs on the box and on a dev machine with no hardcoded personal paths.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_CANDIDATES = [
    os.environ.get("DEALSCANNER_ENV"),
    "/opt/dealscanner-v2/.env",
    str(Path(__file__).resolve().parents[2] / ".env"),
]
for _p in _CANDIDATES:
    if _p and os.path.exists(_p):
        load_dotenv(_p)
        break


def _emails(raw: str) -> list[str]:
    return [e.strip().lower() for e in raw.split(",") if e.strip()]


def allow_list() -> set[str]:
    """Operators allowed to sign in."""
    return set(_emails(os.environ.get("ALLOW_LIST", "")))


def recipients() -> dict[str, str]:
    """email -> thesis slug for the daily digest.

    Format: DIGEST_RECIPIENTS="a@x.com:water,b@y.com:healthcare".
    Falls back to DIGEST_TO (comma list) all mapped to DEFAULT_THESIS.
    """
    raw = os.environ.get("DIGEST_RECIPIENTS", "").strip()
    out: dict[str, str] = {}
    if raw:
        for pair in raw.split(","):
            if ":" in pair:
                email, slug = pair.split(":", 1)
                if email.strip():
                    out[email.strip().lower()] = slug.strip() or default_thesis()
        return out
    for email in _emails(os.environ.get("DIGEST_TO", "")):
        out[email] = default_thesis()
    return out


def default_thesis() -> str:
    return os.environ.get("DEFAULT_THESIS", "healthcare")


def app_base_url() -> str:
    """Canonical, trusted base URL for links we email (magic links, digests).

    NEVER derive this from a client-supplied Host header — that enables host-header
    poisoning where an operator's login link points at an attacker domain.
    """
    return os.environ.get("APP_BASE_URL", "https://dealscanner.us").rstrip("/")


def trusted_hosts() -> set[str]:
    """Host header values allowed to set the request's own base URL. Anything else
    falls back to APP_BASE_URL. Defaults cover the prod domain; extend via TRUSTED_HOSTS.
    """
    raw = os.environ.get("TRUSTED_HOSTS", "")
    extra = {h.strip().lower() for h in raw.split(",") if h.strip()}
    base = app_base_url().split("://", 1)[-1]
    return {base, f"www.{base}"} | extra
