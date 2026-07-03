"""Phase-2 engine tests: exclusion tagging, staleness, tag-aware evaluate, migration."""
import sqlite3
from dealscanner_engine import db, evaluator


# ---- Station 3: match_exclusion_tags (tag, don't drop) ----

EXCL = {
    "Restaurant_Food": ["restaurant", "pizzeria", "bakery"],
    "Personal_Care": ["hair salon", "massage"],
}


def test_match_tags_returns_category_names():
    assert evaluator.match_exclusion_tags("Joe's Pizzeria & Bakery", EXCL) == ["Restaurant_Food"]


def test_match_tags_multiple_categories_sorted():
    tags = evaluator.match_exclusion_tags("Restaurant with attached hair salon", EXCL)
    assert tags == ["Personal_Care", "Restaurant_Food"]


def test_match_tags_none_when_clean():
    assert evaluator.match_exclusion_tags("Municipal water treatment operator", EXCL) == []


# ---- graded 1-5 confidence ----

KW = {"tier1": ["water treatment", "wastewater"], "tier2": ["pump", "filtration"],
      "context": ["municipal", "industrial"], "negative": ["franchise"]}


def _rel(text):
    return evaluator._kw_relevance(text, KW)[0]


def test_relevance_5_two_tier1_or_tier1_plus_context():
    assert _rel("water treatment and wastewater plant") == 5
    assert _rel("municipal water treatment operator") == 5


def test_relevance_4_single_tier1():
    assert _rel("regional water treatment company") == 4


def test_relevance_3_tier1_with_negative():
    assert _rel("water treatment franchise resale") == 3


def test_relevance_3_two_tier2_with_context():
    assert _rel("industrial pump and filtration supplier") == 3


def test_relevance_2_one_tier2_with_context():
    assert _rel("industrial pump distributor") == 2


def test_relevance_1_tier2_without_context():
    assert _rel("pool pump retailer") == 1


def test_relevance_0_no_industry_keyword():
    assert _rel("a generic holding company") == 0


# ---- Task 3: classify_staleness ----

def test_fresh_is_new():
    assert evaluator.classify_staleness("2026-06-23", "2026-06-23", "2026-06-23") == "new"


def test_recent_but_not_today_is_active():
    assert evaluator.classify_staleness("2026-06-01", "2026-06-20", "2026-06-23") == "active"


def test_not_seen_30d_is_stale():
    assert evaluator.classify_staleness("2026-01-01", "2026-05-01", "2026-06-23") == "stale"


def test_stale_boundary_exactly_30_is_active():
    # 30 days since last_seen is still active; 31+ is stale.
    assert evaluator.classify_staleness("2026-01-01", "2026-05-24", "2026-06-23") == "active"


# ---- tag-aware evaluate ----

def _settings(**over):
    s = {"keywords": {"tier1": ["water"]}, "size": {}, "flags": {}, "ranking": {}}
    s.update(over)
    return s


def test_evaluate_excludes_listing_with_excluded_tag_by_default():
    l = {"business_name": "Joe's Diner", "excludable_tags": "Restaurant_Food", "is_sold": 0}
    assert evaluator.evaluate(l, _settings())["section"] == "excluded"


def test_evaluate_keeps_tagged_listing_when_thesis_opts_in():
    # A thesis whose exclude_tags omits Restaurant_Food should NOT hide it.
    l = {"business_name": "Water plant near a restaurant", "excludable_tags": "Restaurant_Food",
         "is_sold": 0, "full_text": "water"}
    v = evaluator.evaluate(l, _settings(exclude_tags=["Personal_Care"]))
    assert v["section"] != "excluded"


def test_evaluate_stale_section():
    l = {"business_name": "water co", "full_text": "water", "is_sold": 0,
         "first_seen": "2026-01-01", "last_seen": "2026-02-01"}
    v = evaluator.evaluate(l, _settings(), today="2026-06-23")
    assert v["section"] == "stale"
    assert v["freshness"] == "stale"


# ---- migration is idempotent + backfills ----

def test_migrate_adds_columns_and_backfills():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # legacy table missing the new columns
    conn.executescript("""CREATE TABLE listings (id INTEGER PRIMARY KEY, normalized_url TEXT,
        first_seen TEXT);""")
    conn.execute("INSERT INTO listings(normalized_url, first_seen) VALUES ('u','2026-06-01')")
    conn.commit()
    r1 = db.migrate(conn)
    assert "listings.last_seen" in r1["added"] and "listings.excludable_tags" in r1["added"]
    assert conn.execute("SELECT last_seen FROM listings").fetchone()["last_seen"] == "2026-06-01"
    # second run is a no-op
    assert db.migrate(conn)["added"] == []


def test_record_block_marks_broker():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(db.SCHEMA)
    conn.execute("INSERT INTO broker_sources(name, status) VALUES ('Sunbelt TX', 'live')")
    conn.commit()
    db.record_block(conn, "Sunbelt TX", "Failed to load in the browser")
    db.record_block(conn, "Sunbelt TX", "Failed to load in the browser")
    r = conn.execute("SELECT block_count, last_blocked_at, last_block_reason FROM broker_sources").fetchone()
    assert r["block_count"] == 2 and r["last_blocked_at"] and "browser" in r["last_block_reason"]
    db.record_block(conn, None, "x")          # no broker -> no-op, no crash


def test_migrate_normalizes_legacy_dates_to_iso():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(db.SCHEMA)
    conn.execute("INSERT INTO listings(normalized_url, listing_url, first_seen) "
                 "VALUES ('u','http://u','6/17/2026')")
    db.migrate(conn)
    row = conn.execute("SELECT first_seen, last_seen FROM listings").fetchone()
    assert row["first_seen"] == "2026-06-17" and row["last_seen"] == "2026-06-17"


# ---- optional geo gate (concierge / rich-metro theses) ----

def _geo_settings(require):
    return {
        "keywords": {"tier1": ["concierge medicine"], "context": [], "tier2": [], "negative": []},
        "size": {}, "flags": {"positive": [], "negative": []},
        "geo": {"require": require, "tier1_metros": ["new york", "miami"], "tier2_states": ["CA", "MA"]},
    }

def _listing(state, city="", ft=""):
    return {"business_name": "A concierge medicine practice", "state": state, "city": city, "full_text": ft}

def test_geo_gate_off_qualifies_anywhere():
    v = evaluator.evaluate(_listing("OH"), _geo_settings(False))
    assert v["section"] == "in"

def test_geo_gate_on_allows_target_state_fullname():
    v = evaluator.evaluate(_listing("California"), _geo_settings(True))  # normalized to CA
    assert v["section"] == "in"

def test_geo_gate_on_allows_metro_in_text():
    v = evaluator.evaluate(_listing("", city="Miami"), _geo_settings(True))
    assert v["section"] == "in"

def test_geo_gate_on_holds_out_offgeo_and_unknown():
    assert evaluator.evaluate(_listing("OH"), _geo_settings(True))["section"] == "off_geo"
    assert evaluator.evaluate(_listing(""), _geo_settings(True))["section"] == "off_geo"

def test_norm_state():
    assert evaluator._norm_state("California") == "CA"
    assert evaluator._norm_state("ca") == "CA"
    assert evaluator._norm_state("NY") == "NY"
    assert evaluator._norm_state("Remote") == ""
