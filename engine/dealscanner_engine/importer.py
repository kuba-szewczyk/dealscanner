"""One-time migration: v1 Google Sheet rows -> v2 listings table.

Reuses v1 data (already scraped + scored) so the boards have a real corpus on day one
at ~$0. The Sheet lacks full description text, so full_text is built from the fields it
does have (name + category + one-line take + flags); fresh v2 scrapes will store the
real page text for richer keyword re-match.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from .util import content_hash, normalize_url


def _num(v):
    if v in (None, "", "N/A"):
        return None
    try:
        return float(str(v).replace("$", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def import_rows(conn: sqlite3.Connection, rows: list[dict]) -> dict:
    """rows: dicts keyed by v1 Listings headers. Dedup by normalized_url UNIQUE."""
    inserted = skipped = 0
    for r in rows:
        url = (r.get("listing_url") or "").strip()
        if not url.startswith(("http://", "https://")):
            skipped += 1
            continue
        nurl = normalize_url(url)
        v1tier = (r.get("tier") or "").strip()
        is_sold = 1 if (r.get("status") == "sold" or v1tier.upper() == "SOLD") else 0
        full_text = " | ".join(filter(None, [
            r.get("business_name"), r.get("category"), r.get("claude_take"),
            r.get("positive_flags"), r.get("red_flags"), r.get("broker"),
            r.get("city"), r.get("state"),
        ]))
        chash = content_hash(nurl, full_text)
        try:
            conn.execute(
                """INSERT INTO listings
                   (normalized_url, listing_url, broker, business_name, category,
                    state, city, asking_price, revenue, sde, ebitda, multiple,
                    one_line_take, positive_flags, negative_flags, flag_score,
                    full_text, data_completeness, is_sold, content_hash, first_seen, scored_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (nurl, url, r.get("broker"), r.get("business_name"), r.get("category"),
                 r.get("state"), r.get("city"), _num(r.get("asking_price")),
                 _num(r.get("revenue")), _num(r.get("sde")), _num(r.get("ebitda")),
                 _num(r.get("multiple")), r.get("claude_take"), r.get("positive_flags"),
                 r.get("red_flags"), int(_num(r.get("flag_score")) or 0),
                 full_text, r.get("data_completeness"), is_sold, chash,
                 (r.get("date_added") or "")[:10],
                 datetime.now(timezone.utc).isoformat()),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            skipped += 1  # duplicate normalized_url — dedup by construction
    conn.commit()
    return {"inserted": inserted, "skipped_dupe_or_bad": skipped, "received": len(rows)}
