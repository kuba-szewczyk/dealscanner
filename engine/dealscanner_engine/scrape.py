"""Decoupled SCRAPE stage (minimal-spend port of v1 firecrawl+Haiku extraction).

Writes raw, thesis-neutral listings to the DB with real page text in full_text.
Cost is tracked and bounded by a hard in-app spend cap. Firecrawl responses are
disk-cached so re-runs don't re-burn credits. Global pre-filter drops obvious
non-targets before they are stored/scored.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from . import db
from .thesis import load_global_exclusions
from .util import content_hash, normalize_url

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

EXTRACT_MODEL = os.getenv("ANTHROPIC_EXTRACT_MODEL", "claude-haiku-4-5")
# $/million tokens (Haiku 4.5).
PRICE = {"claude-haiku-4-5": (1.00, 5.00), "claude-sonnet-4-5": (3.00, 15.00)}

BROKER_URLS = {
    "lion": ("Lion Business Brokers", "https://lionbusinessbrokers.com/adjusted-ebitda-1m/"),
    "vrtriangle": ("VR Triangle", "https://vrbiztriangle.com/businesses-for-sale/"),
    "bizex": ("BizEx", "https://www.bizex.net/business-for-sale"),
}

_LISTINGS_SYSTEM = """You extract business-for-sale listings from a broker's markdown page.
Return a JSON array. Each item MUST have: listing_url (absolute), business_name,
asking_price (number USD or null), revenue (or null), sde (or null), ebitda (or null),
industry (or null), city (or null), state (US abbr or null), description (one short
sentence), is_sold (bool). Money: "$2.4M"->2400000. Only real listings, no nav/ads.
Output ONLY the JSON array."""

FIRECRAWL_CACHE = Path(__file__).resolve().parents[2] / "data" / ".firecrawl_cache"


def _cost(model: str, intok: int, outtok: int) -> float:
    pin, pout = PRICE.get(model, (1.0, 5.0))
    return intok / 1e6 * pin + outtok / 1e6 * pout


def _firecrawl_md(url: str, fresh: bool = False) -> str:
    FIRECRAWL_CACHE.mkdir(parents=True, exist_ok=True)
    cp = FIRECRAWL_CACHE / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".md")
    if cp.exists() and not fresh:
        return cp.read_text()
    from firecrawl import FirecrawlApp
    app = FirecrawlApp(api_key=os.environ["FIRECRAWL_API_KEY"])
    try:
        doc = app.scrape(url, formats=["markdown"], only_main_content=True, timeout=60000)
    except AttributeError:
        doc = app.scrape_url(url, formats=["markdown"], only_main_content=True)
    md = getattr(doc, "markdown", None) or (doc.get("markdown") if isinstance(doc, dict) else "") or ""
    cp.write_text(md)
    return md


def _parse_array(raw: str) -> list[dict]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        raw = raw[4:] if raw.startswith("json") else raw
    raw = raw.strip()
    try:
        d = json.loads(raw)
        return d if isinstance(d, list) else []
    except json.JSONDecodeError:
        i, j = raw.find("["), raw.rfind("]")
        if 0 <= i < j:
            try:
                return json.loads(raw[i:j + 1])
            except json.JSONDecodeError:
                return []
        return []


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _global_excluded(text: str, excl: dict) -> bool:
    t = text.lower()
    return any(kw.lower() in t for kws in excl.values() for kw in kws)


def scrape_broker(slug: str, max_usd: float = 0.25, fresh: bool = False) -> dict:
    """Fetch one broker index, extract cards (1 Haiku call), global-pre-filter, store.
    Stops if projected/actual spend would exceed max_usd (hard cap)."""
    from anthropic import Anthropic
    name, url = BROKER_URLS[slug]
    conn = db.connect()
    started = datetime.now(timezone.utc).isoformat()
    md = _firecrawl_md(url, fresh=fresh)

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model=EXTRACT_MODEL, max_tokens=8000, system=_LISTINGS_SYSTEM,
        messages=[{"role": "user", "content": f"Broker: {name}\n\nMarkdown:\n{md[:60000]}"}],
    )
    cost = _cost(EXTRACT_MODEL, resp.usage.input_tokens, resp.usage.output_tokens)
    if cost > max_usd:
        raise SystemExit(f"SPEND CAP hit: extraction cost ${cost:.4f} > cap ${max_usd}")
    raw = "".join(b.text for b in resp.content if hasattr(b, "text"))
    cards = _parse_array(raw)

    excl = load_global_exclusions()
    inserted = prefiltered = dupe = 0
    for c in cards:
        u = (c.get("listing_url") or "").strip()
        if not u.startswith(("http", "https")):
            continue
        text = f"{c.get('business_name','')} {c.get('industry','')}"
        if _global_excluded(text, excl):
            prefiltered += 1
            continue
        full_text = " | ".join(filter(None, [c.get("business_name"), c.get("industry"),
                                             c.get("description"), c.get("city"), c.get("state")]))
        nurl = normalize_url(u)
        try:
            conn.execute(
                """INSERT INTO listings(normalized_url, listing_url, broker, business_name,
                   category, state, city, asking_price, revenue, sde, ebitda, one_line_take,
                   full_text, data_completeness, is_sold, content_hash, first_seen)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (nurl, u, name, c.get("business_name"), c.get("industry"), c.get("state"),
                 c.get("city"), _num(c.get("asking_price")), _num(c.get("revenue")),
                 _num(c.get("sde")), _num(c.get("ebitda")), c.get("description"),
                 full_text, "partial", 1 if c.get("is_sold") else 0,
                 content_hash(nurl, full_text), datetime.now(timezone.utc).date().isoformat()),
            )
            inserted += 1
        except Exception:
            dupe += 1
    conn.execute(
        "INSERT INTO runs(kind, started_at, ended_at, listings_processed, new_count, cost_usd, note) "
        "VALUES ('scrape',?,?,?,?,?,?)",
        (started, datetime.now(timezone.utc).isoformat(), len(cards), inserted, cost,
         f"{slug}: {prefiltered} global-prefiltered, {dupe} dupes"),
    )
    conn.commit()
    return {"broker": slug, "cards": len(cards), "inserted": inserted,
            "global_prefiltered": prefiltered, "dupes": dupe, "cost_usd": round(cost, 4)}
