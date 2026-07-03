"""Decoupled SCRAPE stage (firecrawl + Haiku extraction).

Reads the LIVE broker set from broker_sources (Station 1), follows numbered
pagination up to a budget (Station 2), TAGS global non-targets instead of dropping
them (Station 3), and UPSERTS — first_seen stays sticky while last_seen bumps on
every re-find, so a re-found listing never masquerades as new (Station 4). Per-broker
yield + truncation are recorded to broker_stats so broker effectiveness is trackable.

Firecrawl markdown is disk-cached, so re-runs and retrospective re-extraction are free.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from . import config  # noqa: F401  (loads .env on import)
from . import db
from .categorize import canonical_category
from .evaluator import match_exclusion_tags
from .thesis import load_global_exclusions
from .util import content_hash, normalize_url

EXTRACT_MODEL = os.getenv("ANTHROPIC_EXTRACT_MODEL", "claude-haiku-4-5")
# $/million tokens (Haiku 4.5).
PRICE = {"claude-haiku-4-5": (1.00, 5.00), "claude-sonnet-4-5": (3.00, 15.00)}
CHAR_FEED = 60000          # max markdown chars fed to the extractor in one call
PAGE_BUDGET = 55000        # stop adding pages once combined markdown reaches this
MAX_PAGES = 3              # hard cap on pages followed per broker

# Back-compat slugs for the CLI `scrape <slug>` (tests + manual runs). The real
# source of brokers is the broker_sources table (see scrape_all).
BROKER_URLS = {
    "lion": ("Lion Business Brokers", "https://lionbusinessbrokers.com/adjusted-ebitda-1m/"),
    "vrtriangle": ("VR Triangle", "https://vrbiztriangle.com/businesses-for-sale/"),
    "bizex": ("BizEx", "https://www.bizex.net/business-for-sale"),
    "viking": ("Viking Mergers", "https://www.vikingmergers.com/businesses-for-sale/"),
    "veld": ("The Veld Group", "https://theveldgroup.com/main-street-businesses-for-sale/"),
    "ibex": ("IBEX Business Exchange", "https://www.ibexbeyond.com/buy-a-business/"),
}

_LISTINGS_SYSTEM = """You extract business-for-sale listings from a broker's markdown page.
Return a JSON array. Each item MUST have: listing_url (absolute), business_name,
asking_price (number USD or null), revenue (or null), sde (or null), ebitda (or null),
industry (or null), city (or null), state (US abbr or null), description (one short
sentence), is_sold (bool). Money: "$2.4M"->2400000. Only real listings, no nav/ads.
Output ONLY the JSON array."""

FIRECRAWL_CACHE = Path(__file__).resolve().parents[2] / "data" / ".firecrawl_cache"
_LINK_RE = re.compile(r"\(([^)\s]+)\)")
_PAGE_NUM_RE = re.compile(r"(?:[?&](?:page|paged|pg)=|/page/)(\d+)")


MIN_PAGE_CHARS = 250   # below this a page is empty / a blocked challenge / a redirect stub
MIN_LINKS = 3          # a real listings index has several links; fewer => dead/blocked


_BLOCK_SIGNALS = ("failed to load in the browser", "file type that firecrawl", "403",
                  "forbidden", "access denied", "blocked", "captcha", "cloudflare")


def is_block_error(msg: str) -> bool:
    """True if a Firecrawl failure means the broker's page is unscrapeable (blocked/JS-walled/
    wrong file type) rather than a transient blip — used to mark the broker long-term."""
    m = (msg or "").lower()
    return any(s in m for s in _BLOCK_SIGNALS)


def looks_dead(md: str) -> str | None:
    """Return a reason string if the fetched page is empty/blocked/contentless, else None.
    Used to SKIP the paid extraction call on dead broker URLs (money-saver on wide crawls)."""
    s = (md or "").strip()
    if len(s) < MIN_PAGE_CHARS:
        return f"empty/blocked ({len(s)} chars)"
    if len(set(re.findall(r"https?://[^\s)\"']+", md))) < MIN_LINKS:
        return "no listing links"
    return None


def _cost(model: str, intok: int, outtok: int) -> float:
    pin, pout = PRICE.get(model, (1.0, 5.0))
    return intok / 1e6 * pin + outtok / 1e6 * pout


def _firecrawl_md(url: str, ttl_hours: float | None = None) -> str:
    """Fetch one URL -> markdown, disk-cached by URL hash.
    ttl_hours=None -> use cache forever (cheap re-runs / enrich). A scheduled scrape passes a
    TTL so STALE pages are re-fetched — otherwise a recurring run reads yesterday's cached page
    and finds zero new listings forever."""
    import time
    FIRECRAWL_CACHE.mkdir(parents=True, exist_ok=True)
    cp = FIRECRAWL_CACHE / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".md")
    if cp.exists():
        fresh = ttl_hours is None or (time.time() - cp.stat().st_mtime) / 3600 < ttl_hours
        if fresh:
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


def find_next_pages(md: str, base_url: str, fetched: set[str]) -> list[str]:
    """Pure: return same-domain numbered pagination URLs found in markdown, not yet
    fetched, ordered by page number. Only follows links that actually exist on the page."""
    host = urlparse(base_url).netloc
    out: list[tuple[int, str]] = []
    for u in _LINK_RE.findall(md):
        if not u.startswith("http") or u in fetched or urlparse(u).netloc != host:
            continue
        m = _PAGE_NUM_RE.search(u)
        if m and int(m.group(1)) >= 2:
            out.append((int(m.group(1)), u))
    out.sort()
    seen = set()
    return [u for _, u in out if not (u in seen or seen.add(u))]


def _gather_pages(url: str, max_pages: int = MAX_PAGES, ttl_hours: float | None = None) -> tuple[str, dict]:
    """Fetch page 1, then follow numbered pagination links until the combined markdown
    reaches PAGE_BUDGET chars, MAX_PAGES is hit, or no further page link exists."""
    md = _firecrawl_md(url, ttl_hours)
    pages = [md]
    fetched = {url}
    total = len(md)
    while len(pages) < max_pages and total < PAGE_BUDGET:
        nxt = [u for u in find_next_pages(pages[-1], url, fetched)]
        if not nxt:
            break
        nu = nxt[0]
        fetched.add(nu)
        try:
            page_md = _firecrawl_md(nu, ttl_hours)  # a slow extra page must not lose page 1
        except Exception:
            break
        if not page_md.strip():
            break
        pages.append(page_md)
        total += len(page_md)
    combined = "\n\n".join(pages)
    return combined, {"pages": len(pages), "raw_chars": total}


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


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def scrape_one(name: str, url: str, conn, client, excl: dict,
               max_pages: int = MAX_PAGES, ttl_hours: float | None = None) -> dict:
    """Scrape a single broker index (with pagination) -> upsert listings. One Haiku call."""
    started = datetime.now(timezone.utc).isoformat()
    md, pginfo = _gather_pages(url, max_pages=max_pages, ttl_hours=ttl_hours)

    # Money guard: don't pay to extract a dead/blocked/empty page.
    dead = looks_dead(md)
    if dead:
        note = f"{name}: DEAD — {dead}, pages={pginfo['pages']}"
        cur = conn.execute(
            "INSERT INTO runs(kind, started_at, ended_at, listings_processed, new_count, cost_usd, note) "
            "VALUES ('scrape',?,?,?,?,?,?)",
            (started, datetime.now(timezone.utc).isoformat(), 0, 0, 0.0, note))
        conn.execute(
            "INSERT INTO broker_stats(run_id, broker, status, new_count, total_count, chars_fed, "
            "pages, note, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (cur.lastrowid, name, "dead", 0, 0, min(len(md), CHAR_FEED), pginfo["pages"], note,
             datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return {"broker": name, "cards": 0, "inserted": 0, "refreshed": 0, "tagged": 0,
                "pages": pginfo["pages"], "chars_fed": min(len(md), CHAR_FEED),
                "out_truncated": False, "cost_usd": 0.0, "dead": dead}

    resp = client.messages.create(
        model=EXTRACT_MODEL, max_tokens=16000, system=_LISTINGS_SYSTEM,
        messages=[{"role": "user", "content": f"Broker: {name}\n\nMarkdown:\n{md[:CHAR_FEED]}"}],
    )
    cost = _cost(EXTRACT_MODEL, resp.usage.input_tokens, resp.usage.output_tokens)
    out_truncated = resp.stop_reason == "max_tokens"   # lost listings — never silent
    in_truncated = len(md) > CHAR_FEED
    raw = "".join(b.text for b in resp.content if hasattr(b, "text"))
    cards = _parse_array(raw)

    today = _today()
    inserted = refreshed = tagged = 0
    for c in cards:
        u = (c.get("listing_url") or "").strip()
        if not u.startswith(("http", "https")):
            continue
        full_text = " | ".join(filter(None, [c.get("business_name"), c.get("industry"),
                                             c.get("description"), c.get("city"), c.get("state")]))
        # Derive a real category from text; fall back to the raw industry if unclassifiable.
        # Map to a consolidated display bucket (keeps to ~14 categories, no raw-industry leakage).
        category = canonical_category(c.get("industry"), c.get("business_name"),
                                      c.get("industry"), c.get("description"))
        tags = match_exclusion_tags(f"{c.get('business_name','')} {c.get('industry','')} "
                                    f"{c.get('description','')}", excl)
        if tags:
            tagged += 1
        nurl = normalize_url(u)
        existed = conn.execute(
            "SELECT 1 FROM listings WHERE normalized_url=?", (nurl,)).fetchone() is not None
        # Upsert: first_seen + scored_at are sticky; last_seen bumps; refresh sold/financials.
        conn.execute(
            """INSERT INTO listings(normalized_url, listing_url, broker, business_name,
               category, state, city, asking_price, revenue, sde, ebitda, one_line_take,
               full_text, data_completeness, is_sold, excludable_tags, content_hash,
               first_seen, last_seen)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(normalized_url) DO UPDATE SET
                 last_seen=excluded.last_seen,
                 is_sold=excluded.is_sold,
                 asking_price=COALESCE(excluded.asking_price, listings.asking_price),
                 revenue=COALESCE(excluded.revenue, listings.revenue),
                 ebitda=COALESCE(excluded.ebitda, listings.ebitda),
                 sde=COALESCE(excluded.sde, listings.sde),
                 excludable_tags=excluded.excludable_tags""",
            (nurl, u, name, c.get("business_name"), category, c.get("state"),
             c.get("city"), _num(c.get("asking_price")), _num(c.get("revenue")),
             _num(c.get("sde")), _num(c.get("ebitda")), c.get("description"),
             full_text, "partial", 1 if c.get("is_sold") else 0, ",".join(tags),
             content_hash(nurl, full_text), today, today),
        )
        if existed:
            refreshed += 1
        else:
            inserted += 1

    chars_fed = min(len(md), CHAR_FEED)   # what the model actually digested; ==60000 => at limit
    trunc = (" OUTPUT-TRUNCATED" if out_truncated else "") + (" INPUT>60k" if in_truncated else "")
    note = (f"{name}: {tagged} tagged, {refreshed} refreshed, "
            f"pages={pginfo['pages']}, fed={chars_fed}c (raw {pginfo['raw_chars']}c){trunc}")
    cur = conn.execute(
        "INSERT INTO runs(kind, started_at, ended_at, listings_processed, new_count, cost_usd, note) "
        "VALUES ('scrape',?,?,?,?,?,?)",
        (started, datetime.now(timezone.utc).isoformat(), len(cards), inserted, cost, note),
    )
    run_id = cur.lastrowid
    status = "new" if inserted else ("active" if cards else "silent")
    conn.execute(
        "INSERT INTO broker_stats(run_id, broker, status, new_count, total_count, chars_fed, "
        "pages, note, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (run_id, name, status, inserted, len(cards), chars_fed, pginfo["pages"], note,
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    return {"broker": name, "cards": len(cards), "inserted": inserted, "refreshed": refreshed,
            "tagged": tagged, "pages": pginfo["pages"], "chars_fed": chars_fed,
            "out_truncated": out_truncated, "cost_usd": round(cost, 4)}


def scrape_broker(slug: str, max_usd: float = 0.25, max_pages: int = MAX_PAGES) -> dict:
    """CLI helper: scrape one back-compat slug from BROKER_URLS."""
    from anthropic import Anthropic
    name, url = BROKER_URLS[slug]
    conn = db.connect()
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    res = scrape_one(name, url, conn, client, load_global_exclusions(), max_pages=max_pages)
    if res["cost_usd"] > max_usd:
        res["note"] = f"WARNING: single-broker cost ${res['cost_usd']} exceeded cap ${max_usd}"
    return res


def live_brokers(conn) -> list[tuple[str, str]]:
    """Station 1: the LIVE broker set the scraper crawls = broker_sources(status='live').

    Ordered least-recently-scraped first (brokers never scraped come first), so if a
    per-run spend cap truncates the batch, the UNSCRAPED tail is picked up on the next
    run instead of the same alphabetical tail being starved every day. This lets the
    daily cap stay modest while still covering every broker over a rolling window.
    """
    return [(r["name"], r["url"]) for r in conn.execute(
        "SELECT s.name, s.url FROM broker_sources s "
        "LEFT JOIN (SELECT broker, MAX(created_at) last_at FROM broker_stats GROUP BY broker) b "
        "  ON b.broker = s.name "
        "WHERE s.status='live' AND s.url IS NOT NULL AND s.url != '' "
        "ORDER BY b.last_at IS NOT NULL, b.last_at, s.name").fetchall()]


def _record_error(conn, name: str, msg: str) -> None:
    """Persist a per-broker failure so one bad broker is logged, not fatal."""
    now = datetime.now(timezone.utc).isoformat()
    note = f"{name}: ERROR — {msg[:160]}"
    cur = conn.execute(
        "INSERT INTO runs(kind, started_at, ended_at, listings_processed, new_count, cost_usd, note) "
        "VALUES ('scrape',?,?,?,?,?,?)", (now, now, 0, 0, 0.0, note))
    conn.execute(
        "INSERT INTO broker_stats(run_id, broker, status, new_count, total_count, chars_fed, "
        "pages, note, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (cur.lastrowid, name, "error", 0, 0, 0, 0, note, now))
    conn.commit()


def _run_brokers(brokers, conn, client, excl, max_usd, max_pages, ttl_hours=None) -> tuple[float, list]:
    """Crawl a list of brokers with a shared spend cap. Each broker is isolated: a fetch
    timeout / network error / bad response is logged and skipped — never aborts the batch."""
    spent = 0.0
    results = []
    for name, url in brokers:
        if spent >= max_usd:
            break
        try:
            r = scrape_one(name, url, conn, client, excl, max_pages=max_pages, ttl_hours=ttl_hours)
        except Exception as e:
            _record_error(conn, name, f"{type(e).__name__}: {e}")
            if is_block_error(str(e)):
                db.record_block(conn, name, f"{type(e).__name__}: {e}")
            results.append({"broker": name, "cards": 0, "inserted": 0, "refreshed": 0,
                            "pages": 0, "chars_fed": 0, "cost_usd": 0.0, "error": str(e)[:160]})
            continue
        spent += r["cost_usd"]
        results.append(r)
    return spent, results


def scrape_all(max_usd: float = 1.00, limit: int | None = None,
               max_pages: int = MAX_PAGES, force: bool = False, fresh: bool = False) -> dict:
    """Scrape every LIVE broker, sharing one cumulative spend cap. One broker's failure is
    isolated (logged, skipped). Skips brokers crawled in the last 12h unless force=True (guards
    against accidental double-runs, while letting a daily 7am job + an off-cycle catch-up both
    proceed). fresh=True re-fetches pages older than 6h (REQUIRED for scheduled runs to see new
    listings, instead of re-reading stale cache)."""
    from anthropic import Anthropic
    conn = db.connect()
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    excl = load_global_exclusions()
    brokers = live_brokers(conn)
    if not force:
        done = {r["broker"] for r in conn.execute(
            "SELECT DISTINCT broker FROM broker_stats WHERE created_at >= datetime('now','-12 hours')")}
        brokers = [(n, u) for n, u in brokers if n not in done]
    if limit:
        brokers = brokers[:limit]
    spent, results = _run_brokers(brokers, conn, client, excl, max_usd, max_pages,
                                  ttl_hours=6 if fresh else None)
    return {"brokers_scraped": len(results), "total_new": sum(r["inserted"] for r in results),
            "total_refreshed": sum(r["refreshed"] for r in results),
            "dead_brokers": sum(1 for r in results if r.get("dead")),
            "error_brokers": sum(1 for r in results if r.get("error")),
            "spend_usd": round(spent, 4), "stopped_early": spent >= max_usd and len(results) < len(brokers),
            "per_broker": results}
