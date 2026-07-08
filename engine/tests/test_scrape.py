"""Scrape-stage tests: pagination link discovery + upsert (last_seen bump) + tag-not-drop.
The LLM client and Firecrawl fetch are stubbed, so these run offline at $0."""
import sqlite3
import types

import pytest

from dealscanner_engine import db, scrape


# ---- pure pagination discovery ----

def test_find_next_pages_orders_same_domain_unseen():
    md = ("[2](https://b.com/listings?page=2) [3](https://b.com/listings?page=3) "
          "[next](https://other.com/listings?page=2) [1](https://b.com/listings?page=1)")
    out = scrape.find_next_pages(md, "https://b.com/listings", {"https://b.com/listings"})
    assert out == ["https://b.com/listings?page=2", "https://b.com/listings?page=3"]


def test_find_next_pages_path_style_and_dedup():
    md = "[next](https://b.com/page/2/) [again](https://b.com/page/2/)"
    out = scrape.find_next_pages(md, "https://b.com/", set())
    assert out == ["https://b.com/page/2/"]


def test_find_next_pages_none_when_no_pagination():
    assert scrape.find_next_pages("[More Info](https://b.com/listing/abc)", "https://b.com/", set()) == []


# ---- scrape_one: upsert + tagging, with stubs ----

class _Resp:
    def __init__(self, cards):
        self.content = [types.SimpleNamespace(text=__import__("json").dumps(cards))]
        self.usage = types.SimpleNamespace(input_tokens=100, output_tokens=50)
        self.stop_reason = "end_turn"


class _Client:
    def __init__(self, cards):
        self._cards = cards
        self.messages = types.SimpleNamespace(create=lambda **kw: _Resp(self._cards))


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(db.SCHEMA)
    return c


_LIVE_MD = ("# Our Listings\n\nBrowse our businesses for sale below across the region.\n" +
            "\n".join(f"[More Info](https://b.com/listing/{i}) — profitable established company "
                      f"with strong cash flow and loyal customers" for i in range(4)))


def _patch_fetch(monkeypatch, md=_LIVE_MD):
    monkeypatch.setattr(scrape, "_firecrawl_md", lambda url, ttl_hours=None: md)


def test_scrape_one_inserts_then_refreshes_bumping_last_seen(monkeypatch, conn):
    _patch_fetch(monkeypatch)
    card = [{"listing_url": "https://b.com/listing/water-co", "business_name": "Water Co",
             "industry": "Water", "ebitda": 2000000, "is_sold": False}]
    client = _Client(card)

    monkeypatch.setattr(scrape, "_today", lambda: "2026-06-23")
    r1 = scrape.scrape_one("B", "https://b.com/listings", conn, client, {})
    assert r1["inserted"] == 1 and r1["refreshed"] == 0
    row = conn.execute("SELECT first_seen, last_seen FROM listings").fetchone()
    assert row["first_seen"] == "2026-06-23" and row["last_seen"] == "2026-06-23"

    # Same listing re-found 5 days later: refresh, last_seen bumps, first_seen sticky.
    monkeypatch.setattr(scrape, "_today", lambda: "2026-06-28")
    r2 = scrape.scrape_one("B", "https://b.com/listings", conn, client, {})
    assert r2["inserted"] == 0 and r2["refreshed"] == 1
    row = conn.execute("SELECT first_seen, last_seen FROM listings").fetchone()
    assert row["first_seen"] == "2026-06-23" and row["last_seen"] == "2026-06-28"
    assert conn.execute("SELECT COUNT(*) c FROM listings").fetchone()["c"] == 1  # no duplicate


def test_looks_dead_empty_and_blocked():
    assert scrape.looks_dead("") is not None
    assert scrape.looks_dead("Just a moment...") is not None              # Cloudflare stub
    assert scrape.looks_dead("x" * 500) is not None                       # long but no links


def test_is_block_error():
    assert scrape.is_block_error("Failed to scrape. The URL failed to load in the browser")
    assert scrape.is_block_error("returned a file type that Firecrawl cannot read")
    assert scrape.is_block_error("403 Forbidden")
    assert not scrape.is_block_error("read timed out after 60s")


def test_looks_dead_alive_with_links():
    md = ("# Listings page with several businesses for sale across the region this quarter\n" +
          "\n".join(f"[More](https://b.com/listing/{i}) profitable company for sale" for i in range(5)))
    assert scrape.looks_dead(md) is None


def test_scrape_one_skips_extraction_on_dead_page(monkeypatch, conn):
    monkeypatch.setattr(scrape, "_firecrawl_md", lambda url, ttl_hours=None: "Just a moment...")  # blocked
    monkeypatch.setattr(scrape, "_today", lambda: "2026-06-23")

    class _Boom:  # must never be called on a dead page
        messages = types.SimpleNamespace(create=lambda **kw: (_ for _ in ()).throw(AssertionError("paid!")))
    r = scrape.scrape_one("DeadCo", "https://dead.com/x", conn, _Boom(), {})
    assert r["dead"] and r["cost_usd"] == 0.0 and r["cards"] == 0
    assert conn.execute("SELECT status FROM broker_stats").fetchone()["status"] == "dead"
    assert conn.execute("SELECT COUNT(*) c FROM listings").fetchone()["c"] == 0


def test_run_brokers_isolates_failures(monkeypatch, conn):
    """One broker raising (e.g. a Firecrawl timeout) must NOT abort the batch."""
    def fake_one(name, url, c, client, excl, max_pages=3, ttl_hours=None):
        if name == "Bad":
            raise RuntimeError("Request Timeout")
        return {"broker": name, "cards": 1, "inserted": 1, "refreshed": 0, "pages": 1,
                "chars_fed": 500, "cost_usd": 0.01}
    monkeypatch.setattr(scrape, "scrape_one", fake_one)
    spent, results = scrape._run_brokers(
        [("A", "u"), ("Bad", "u"), ("C", "u")], conn, None, {}, max_usd=1.0, max_pages=1)
    assert [r["broker"] for r in results] == ["A", "Bad", "C"]      # all three handled
    assert results[1]["error"] and results[1]["inserted"] == 0       # Bad logged, not fatal
    assert spent == 0.02                                             # A + C still counted
    assert conn.execute("SELECT status FROM broker_stats WHERE broker='Bad'").fetchone()["status"] == "error"


def test_scrape_one_tags_restaurant_not_dropped(monkeypatch, conn):
    _patch_fetch(monkeypatch)
    card = [{"listing_url": "https://b.com/listing/joes", "business_name": "Joe's Pizzeria",
             "industry": "Restaurant", "is_sold": False}]
    excl = {"Restaurant_Food": ["pizzeria", "restaurant"]}
    r = scrape.scrape_one("B", "https://b.com/listings", conn, _Client(card), excl)
    assert r["inserted"] == 1 and r["tagged"] == 1            # stored, not dropped
    assert conn.execute("SELECT excludable_tags FROM listings").fetchone()[0] == "Restaurant_Food"


# ---- least-recently-scraped ordering (fair rotation under a spend cap) ----

def test_live_brokers_orders_never_scraped_first_then_oldest(conn):
    for n in ("Alpha", "Bravo", "Charlie"):
        conn.execute("INSERT INTO broker_sources(name, url, status) VALUES (?,?, 'live')",
                     (n, f"https://{n.lower()}.com/listings"))
    # Bravo scraped recently, Charlie scraped long ago, Alpha never scraped.
    conn.execute("INSERT INTO broker_stats(broker, created_at) VALUES ('Bravo', '2026-06-25T10:00:00')")
    conn.execute("INSERT INTO broker_stats(broker, created_at) VALUES ('Charlie', '2026-06-01T10:00:00')")
    conn.commit()
    order = [name for name, _ in scrape.live_brokers(conn)]
    # never-scraped first, then oldest-scraped, most-recent last
    assert order == ["Alpha", "Charlie", "Bravo"]


def test_live_brokers_excludes_dead_and_empty_url(conn):
    conn.execute("INSERT INTO broker_sources(name, url, status) VALUES ('Live','https://x.com/','live')")
    conn.execute("INSERT INTO broker_sources(name, url, status) VALUES ('Dead','https://y.com/','dead')")
    conn.execute("INSERT INTO broker_sources(name, url, status) VALUES ('NoUrl','','live')")
    conn.commit()
    assert [n for n, _ in scrape.live_brokers(conn)] == ["Live"]


# ---- change-detection: skip the LLM call on unchanged pages ----

_P4 = ("# Businesses for sale across the region this quarter\n" +
       "\n".join(f"[More](https://b.com/listing/{i}) profitable company with strong cash flow" for i in range(4)))
_P5 = ("# Businesses for sale across the region this quarter\n" +
       "\n".join(f"[More](https://b.com/listing/{i}) profitable company with strong cash flow" for i in range(5)))


def test_page_fingerprint_ignores_volatile_text_and_catches_new_links():
    a = _P4 + "\nposted 3 days ago"
    b = _P4 + "\nposted 9 days ago · 402 views · sponsored"
    assert scrape._page_fingerprint(a, "https://b.com/l") == scrape._page_fingerprint(b, "https://b.com/l")
    assert scrape._page_fingerprint(_P5, "https://b.com/l") != scrape._page_fingerprint(_P4, "https://b.com/l")
    assert scrape._page_fingerprint("no links here at all", "https://b.com/l") is None


def test_scrape_one_skips_llm_when_page_unchanged(monkeypatch, conn):
    conn.execute("INSERT INTO broker_sources(name, url, status) VALUES ('B','https://b.com/listings','live')")
    conn.commit()
    card = [{"listing_url": "https://b.com/listing/0", "business_name": "Water Co", "industry": "Water"}]
    client = _Client(card)
    _patch_fetch(monkeypatch, md=_P4)
    monkeypatch.setattr(scrape, "_today", lambda: "2026-06-23")
    r1 = scrape.scrape_one("B", "https://b.com/listings", conn, client, {})
    assert not r1.get("unchanged") and r1["cost_usd"] > 0
    assert conn.execute("SELECT last_link_hash FROM broker_sources WHERE name='B'").fetchone()["last_link_hash"]

    # identical page next day -> skip the LLM call, but keep listings fresh
    monkeypatch.setattr(scrape, "_today", lambda: "2026-06-24")
    r2 = scrape.scrape_one("B", "https://b.com/listings", conn, client, {})
    assert r2.get("unchanged") is True and r2["cost_usd"] == 0.0
    assert conn.execute("SELECT last_seen FROM listings LIMIT 1").fetchone()["last_seen"] == "2026-06-24"


def test_scrape_one_reextracts_when_links_change(monkeypatch, conn):
    conn.execute("INSERT INTO broker_sources(name, url, status) VALUES ('B','https://b.com/listings','live')")
    conn.commit()
    client = _Client([{"listing_url": "https://b.com/listing/0", "business_name": "X", "industry": "Water"}])
    monkeypatch.setattr(scrape, "_today", lambda: "2026-06-23")
    _patch_fetch(monkeypatch, md=_P4)
    scrape.scrape_one("B", "https://b.com/listings", conn, client, {})
    # a new listing link appears -> fingerprint changes -> must re-extract, not skip
    _patch_fetch(monkeypatch, md=_P5)
    r = scrape.scrape_one("B", "https://b.com/listings", conn, client, {})
    assert not r.get("unchanged")


def test_scrape_one_skips_when_listing_removed_but_none_new(monkeypatch, conn):
    """The key win: a page that only LOST a listing (or reordered) has no NEW url, so we skip
    the LLM. The old byte-identical fingerprint would have wastefully re-extracted it."""
    conn.execute("INSERT INTO broker_sources(name, url, status) VALUES ('B','https://b.com/listings','live')")
    conn.commit()
    client = _Client([{"listing_url": "https://b.com/listing/0", "business_name": "X", "industry": "Water"}])
    monkeypatch.setattr(scrape, "_today", lambda: "2026-06-23")
    _patch_fetch(monkeypatch, md=_P5)                         # day 1: listings 0..4, full extract
    r1 = scrape.scrape_one("B", "https://b.com/listings", conn, client, {})
    assert not r1.get("unchanged")
    _patch_fetch(monkeypatch, md=_P4)                         # day 2: listing 4 gone, nothing new
    monkeypatch.setattr(scrape, "_today", lambda: "2026-06-24")
    r2 = scrape.scrape_one("B", "https://b.com/listings", conn, client, {})
    assert r2.get("unchanged") is True and r2["cost_usd"] == 0.0


def test_bump_present_only_bumps_still_listed(conn):
    for u in ("https://b.com/listing/0", "https://b.com/listing/gone"):
        conn.execute("INSERT INTO listings(normalized_url, listing_url, broker, is_sold, last_seen) "
                     "VALUES (?,?, 'B', 0, '2026-06-01')", (scrape.normalize_url(u), u))
    conn.commit()
    n = scrape._bump_present(conn, "B", {scrape.normalize_url("https://b.com/listing/0")}, "2026-06-24")
    assert n == 1
    seen = {r["listing_url"]: r["last_seen"] for r in
            conn.execute("SELECT listing_url, last_seen FROM listings")}
    assert seen["https://b.com/listing/0"] == "2026-06-24"    # still listed -> fresh
    assert seen["https://b.com/listing/gone"] == "2026-06-01"  # dropped off -> ages out
