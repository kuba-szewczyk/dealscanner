"""Detail-page ENRICH stage.

For the RELEVANT set — relevance >= 1 for either thesis, not sold, financials not already
complete, and NOT already enriched — fetch the listing's OWN page and pull richer financials.

Two cost guards make this cheap and safe:
  * Firecrawl is disk-cached (re-fetch = free) and you have ~100k credits of headroom.
  * `enriched_at` is stamped on every listing we touch, so each listing's detail page is
    crawled at most ONCE, EVER. Re-found duplicates on later crawls are never re-enriched.
  * Regex-first: we parse Firecrawl's clean markdown for $ figures for FREE and only fall
    back to a tight Haiku call for the fields still missing — minimising Claude spend.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from . import db, thesis
from .evaluator import _kw_relevance
from .scrape import _cost, _firecrawl_md, EXTRACT_MODEL, is_block_error, looks_dead
from .util import content_hash

# label -> regex of synonyms; first labelled money figure within ~18 chars wins.
_LABELS = {
    "asking_price": r"(?:asking\s+price|list\s+price|sale\s+price|price)",
    "revenue": r"(?:gross\s+revenue|annual\s+revenue|ttm\s+revenue|total\s+revenue|revenue|gross\s+sales|annual\s+sales|sales)",
    "ebitda": r"(?:adjusted\s+ebitda|ebitda)",
    "sde": r"(?:seller'?s?\s+discretionary\s+earnings|discretionary\s+earnings|adjusted\s+cash\s+flow|cash\s+flow|owner\s+benefit|sde)",
}
_MONEY = r"\$?\s*([\d][\d,]*(?:\.\d+)?)\s*(million|thousand|billion|[mkb])?\b"


def _money(num: str, unit: str | None) -> float | None:
    try:
        v = float(num.replace(",", ""))
    except ValueError:
        return None
    u = (unit or "").lower()
    if u in ("m", "million"):
        v *= 1e6
    elif u in ("k", "thousand"):
        v *= 1e3
    elif u in ("b", "billion"):
        v *= 1e9
    return v


def regex_financials(md: str) -> dict:
    """Parse labelled $ figures from clean markdown — FREE. Returns only what it finds."""
    out: dict = {}
    for field, label in _LABELS.items():
        m = re.search(label + r"[^\d$]{0,18}" + _MONEY, md, re.I)
        if m:
            val = _money(m.group(1), m.group(2))
            if val is not None:
                out[field] = val
    return out


_DETAIL_SYSTEM = (
    "Extract these fields for ONE business-for-sale listing from its page markdown, as a "
    "JSON object: asking_price, revenue, ebitda, sde (each USD number or null). "
    'Money: "$2.4M"->2400000. Return ONLY the JSON object.'
)
_FIELDS = ("asking_price", "revenue", "ebitda", "sde")


def _thesis_keywords(conn) -> list[dict]:
    out = []
    for slug in ("water", "healthcare"):
        try:
            out.append(thesis.get_settings(conn, slug).get("keywords", {}))
        except KeyError:
            pass
    return out


def _max_relevance(listing: dict, kwsets: list[dict]) -> int:
    text = " ".join(str(listing.get(f, "") or "") for f in
                    ("business_name", "category", "one_line_take", "full_text"))
    return max((_kw_relevance(text, kw)[0] for kw in kwsets), default=0)


def candidates(conn) -> list[dict]:
    """Relevant & not-yet-enriched listings: relevance>=1 (either thesis), live, incomplete."""
    kwsets = _thesis_keywords(conn)
    rows = conn.execute(
        "SELECT * FROM listings WHERE enriched_at IS NULL AND is_sold=0 "
        "AND (data_completeness IS NULL OR data_completeness != 'full')").fetchall()
    return [dict(r) for r in rows if _max_relevance(dict(r), kwsets) >= 1]


def plan(conn) -> dict:
    """Dry-run: how many would enrich, how many detail pages are already cached (free),
    and the projected NEW Firecrawl credits + a Claude cost range — spend NOTHING."""
    import hashlib
    from .scrape import FIRECRAWL_CACHE
    cands = candidates(conn)
    cached = sum(1 for c in cands if (FIRECRAWL_CACHE /
                 (hashlib.sha1((c["listing_url"] or "").encode()).hexdigest()[:16] + ".md")).exists())
    new_fetches = len(cands) - cached
    return {"candidates": len(cands), "already_cached": cached,
            "new_firecrawl_credits": new_fetches,
            "est_claude_usd_low": round(len(cands) * 0.002, 2),
            "est_claude_usd_high": round(len(cands) * 0.008, 2)}


def enrich(max_usd: float = 1.00, limit: int | None = None) -> dict:
    """Run the enrich stage under a hard Claude spend cap. Each listing is isolated: a
    fetch / LLM / parse error is counted and skipped, never aborting the batch."""
    import os
    from anthropic import Anthropic
    conn = db.connect()
    cands = candidates(conn)
    if limit:
        cands = cands[:limit]
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def now():
        return datetime.now(timezone.utc).isoformat()

    spent = 0.0
    filled = haiku_calls = dead = regex_only = errors = blocked = 0
    for c in cands:
        if spent >= max_usd:
            break
        try:
            md = _firecrawl_md(c["listing_url"])
            if looks_dead(md):
                conn.execute("UPDATE listings SET enriched_at=? WHERE id=?", (now(), c["id"]))
                conn.commit()
                dead += 1
                continue
            fields = regex_financials(md)
            missing = [f for f in _FIELDS if fields.get(f) is None and c.get(f) is None]
            if missing:
                ch = content_hash(c["listing_url"], md)
                cached = conn.execute(
                    "SELECT result_json FROM score_cache WHERE content_hash=? AND account_id=0",
                    (ch,)).fetchone()
                if cached:
                    fields.update({k: v for k, v in json.loads(cached["result_json"]).items()
                                   if v is not None})
                else:
                    resp = client.messages.create(
                        model=EXTRACT_MODEL, max_tokens=400, system=_DETAIL_SYSTEM,
                        messages=[{"role": "user", "content": md[:24000]}])
                    spent += _cost(EXTRACT_MODEL, resp.usage.input_tokens, resp.usage.output_tokens)
                    haiku_calls += 1
                    raw = "".join(b.text for b in resp.content if hasattr(b, "text"))
                    got = {}
                    try:
                        got = json.loads(raw[raw.find("{"):raw.rfind("}") + 1] or "{}")
                    except json.JSONDecodeError:
                        pass
                    conn.execute(
                        "INSERT OR REPLACE INTO score_cache(content_hash, account_id, result_json, created_at) "
                        "VALUES (?,?,?,?)", (ch, 0, json.dumps(got), now()))
                    fields.update({k: got.get(k) for k in _FIELDS if got.get(k) is not None})
            else:
                regex_only += 1
            # 'full' only if there are financials now; else keep 'partial' but still stamp.
            merged = {f: (fields.get(f) if fields.get(f) is not None else c.get(f)) for f in _FIELDS}
            completeness = "full" if any(v is not None for v in merged.values()) else \
                (c.get("data_completeness") or "partial")
            conn.execute(
                """UPDATE listings SET
                     asking_price = COALESCE(asking_price, ?), revenue = COALESCE(revenue, ?),
                     ebitda = COALESCE(ebitda, ?), sde = COALESCE(sde, ?),
                     full_text = substr(COALESCE(full_text,'') || ' | ' || ?, 1, 8000),
                     data_completeness = ?, enriched_at = ?
                   WHERE id = ?""",
                (fields.get("asking_price"), fields.get("revenue"), fields.get("ebitda"),
                 fields.get("sde"), md[:4000], completeness, now(), c["id"]))
            conn.commit()
            if any(fields.get(f) is not None for f in _FIELDS):
                filled += 1
        except Exception as e:
            errors += 1  # one bad listing never aborts the batch
            # If Firecrawl couldn't load the page, leave a persistent mark on the broker.
            if is_block_error(str(e)):
                blocked += 1
                db.record_block(conn, c.get("broker"), str(e))
            # Stamp it so a permanently-unscrapeable page (broker blocks Firecrawl, PDF, dead
            # URL) converges instead of being retried — and re-billed — every single run.
            try:
                conn.execute("UPDATE listings SET enriched_at=? WHERE id=?", (now(), c["id"]))
                conn.commit()
            except Exception:
                pass
            continue

    conn.execute(
        "INSERT INTO runs(kind, started_at, ended_at, listings_processed, new_count, cost_usd, note) "
        "VALUES ('enrich',?,?,?,?,?,?)",
        (now(), now(), len(cands), filled, round(spent, 4),
         f"{filled} filled, {regex_only} regex-only, {haiku_calls} haiku, {dead} dead, "
         f"{errors} errors ({blocked} broker-blocked)"))
    conn.commit()
    return {"processed": len(cands), "filled": filled, "regex_only": regex_only,
            "haiku_calls": haiku_calls, "dead_detail": dead, "errors": errors,
            "broker_blocked": blocked, "spend_usd": round(spent, 4)}
