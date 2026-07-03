"""Small shared utilities. normalize_url ported verbatim from v1 config.py — it is
the canonical dedup key (now the basis of the listings.normalized_url UNIQUE index)."""
from __future__ import annotations

import hashlib
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

_TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
             "fbclid", "gclid", "ref", "ref_", "sid", "session", "sessionid"}


def normalize_url(url: str) -> str:
    """Canonical form used ONLY for dedup comparison (raw URL is still stored)."""
    u = (url or "").strip()
    try:
        s = urlsplit(u)
    except Exception:
        return u.lower()
    if not s.scheme or not s.netloc:
        return u.lower()
    host = s.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = s.path.rstrip("/")
    q = [(k, v) for k, v in parse_qsl(s.query, keep_blank_values=True)
         if k.lower() not in _TRACKING]
    return urlunsplit((s.scheme.lower(), host, path, urlencode(sorted(q)), ""))


def content_hash(*parts: str) -> str:
    """Stable hash of a listing's scoring-relevant content (drives the score cache)."""
    blob = "\0".join((p or "") for p in parts)
    return hashlib.sha1(blob.encode()).hexdigest()[:20]
