"""SQLite datastore for DealScanner v2.

The DB is the brain: every listing is stored once, thesis-neutrally (full text +
raw signals). Per-account editable settings (account_settings) are the lens; the
boards apply the *current* settings to stored data, so changing a setting re-ranks
without re-scraping. Dedup is a UNIQUE constraint on normalized_url — no fragile
read-everything-first pass (retires v1 failure modes 1 & 6 by construction).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "dealscanner.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id          INTEGER PRIMARY KEY,
    slug        TEXT UNIQUE NOT NULL,          -- 'water', 'healthcare'
    name        TEXT NOT NULL,
    owner_email TEXT,
    digest_emails TEXT,                           -- comma-separated daily-digest recipients
    archived    INTEGER DEFAULT 0,                -- soft-archive: hidden from lenses, digest paused, data kept
    archived_at TEXT
);

-- The live, editable thesis config for an account (keywords, size bands, geo,
-- includes/excludes, flag weights). Seeded from thesis/*.yaml, then editable.
CREATE TABLE IF NOT EXISTS account_settings (
    account_id    INTEGER PRIMARY KEY REFERENCES accounts(id),
    settings_json TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

-- Thesis-NEUTRAL listing store. Holds full_text + raw signals so any account's
-- settings can be re-applied later with no re-scrape.
CREATE TABLE IF NOT EXISTS listings (
    id                INTEGER PRIMARY KEY,
    normalized_url    TEXT UNIQUE NOT NULL,     -- dedup by construction
    listing_url       TEXT NOT NULL,
    broker            TEXT,
    business_name     TEXT,
    category          TEXT,
    state             TEXT,
    city              TEXT,
    asking_price      REAL,
    revenue           REAL,
    sde               REAL,
    ebitda            REAL,
    multiple          REAL,
    ebitda_margin_pct REAL,
    recurring_pct     REAL,
    one_line_take     TEXT,
    positive_flags    TEXT,                     -- comma-separated
    negative_flags    TEXT,                     -- comma-separated
    flag_score        INTEGER,
    full_text         TEXT,                     -- searchable blob for keyword re-match
    data_completeness TEXT,
    is_sold           INTEGER DEFAULT 0,
    excludable_tags   TEXT,                     -- global non-target categories matched (comma-sep); tag, don't drop
    content_hash      TEXT,
    first_seen        TEXT,                     -- date first discovered (STICKY = "scraped" date)
    last_seen         TEXT,                     -- date last seen still listed (bumped on re-find)
    enriched_at       TEXT,                     -- detail page crawled at most ONCE; NULL = not yet
    scored_at         TEXT                      -- NULL until scored
);
CREATE INDEX IF NOT EXISTS idx_listings_first_seen ON listings(first_seen);
CREATE INDEX IF NOT EXISTS idx_listings_last_seen ON listings(last_seen);
CREATE INDEX IF NOT EXISTS idx_listings_broker ON listings(broker);

-- Per-account computed relevance/section/score. Recomputable cheaply:
-- instant code keyword re-match, or a cached AI re-judge.
CREATE TABLE IF NOT EXISTS scores (
    listing_id       INTEGER REFERENCES listings(id),
    account_id       INTEGER REFERENCES accounts(id),
    relevance        INTEGER,                  -- 0-5
    matched_keywords TEXT,
    section          TEXT,                     -- 'in' | 'excluded' | 'too_small' | 'sold'
    tier             TEXT,
    fit_score        REAL,                     -- ranking score
    rationale        TEXT,
    method           TEXT,                     -- 'code-match' | 'ai-rejudge'
    updated_at       TEXT,
    PRIMARY KEY (listing_id, account_id)
);
CREATE INDEX IF NOT EXISTS idx_scores_account ON scores(account_id);

-- Votes persist with a FULL-context snapshot (training substrate for the future
-- learned 'instinct' scorer).
CREATE TABLE IF NOT EXISTS votes (
    id             INTEGER PRIMARY KEY,
    account_id     INTEGER REFERENCES accounts(id),
    listing_id     INTEGER REFERENCES listings(id),
    operator_email TEXT,
    verdict        TEXT,                        -- 'yes' | 'no' | 'maybe'
    context_json   TEXT,                        -- features/score/thesis/rationale at vote time
    created_at     TEXT
);

CREATE TABLE IF NOT EXISTS broker_stats (
    id          INTEGER PRIMARY KEY,
    run_id      INTEGER,
    broker      TEXT,
    status      TEXT,
    new_count   INTEGER,
    total_count INTEGER,
    chars_fed   INTEGER,                    -- markdown chars digested (==60000 = at feed limit)
    pages       INTEGER,                    -- pages crawled (>1 = pagination engaged)
    note        TEXT,
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    id                 INTEGER PRIMARY KEY,
    kind               TEXT,                    -- 'scrape'|'score'|'rejudge'|'migrate'
    started_at         TEXT,
    ended_at           TEXT,
    listings_processed INTEGER,
    new_count          INTEGER,
    cost_usd           REAL DEFAULT 0,
    note               TEXT,
    model              TEXT,                    -- Claude model used (per-model spend breakdown)
    in_tokens          INTEGER,                 -- Claude input tokens
    out_tokens         INTEGER                  -- Claude output tokens
);

-- content-hash -> result so re-runs/re-scores never double-pay.
CREATE TABLE IF NOT EXISTS score_cache (
    content_hash TEXT,
    account_id   INTEGER,
    result_json  TEXT,
    created_at   TEXT,
    PRIMARY KEY (content_hash, account_id)
);

-- Structured, queryable log (replaces v1's two-log-file trap).
CREATE TABLE IF NOT EXISTS logs (
    id         INTEGER PRIMARY KEY,
    ts         TEXT,
    level      TEXT,                            -- INFO|WARN|ERROR
    stage      TEXT,                            -- scrape|extract|score|api|auth
    broker     TEXT,
    message    TEXT,
    duration_ms INTEGER
);

-- Which brokers we keep / archive / have queued. Yield + health are still derived
-- from listings; this just controls what's live vs archived vs pending.
CREATE TABLE IF NOT EXISTS broker_sources (
    id              INTEGER PRIMARY KEY,
    name            TEXT UNIQUE NOT NULL,
    url             TEXT,
    status          TEXT DEFAULT 'live',         -- live | archived | pending
    block_count     INTEGER DEFAULT 0,           -- times Firecrawl was blocked on this broker's pages
    last_blocked_at TEXT,                         -- when last blocked (Firecrawl can't load the page)
    last_block_reason TEXT,
    last_link_hash  TEXT,                         -- fingerprint of the last-extracted page
    last_link_urls  TEXT,                          -- newline-joined normalized listing URLs last seen (new-listing detection)
    last_extracted_at TEXT,                       -- when we last ran the LLM extraction on it
    created_at      TEXT
);
"""


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    conn = connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    migrate(conn)
    conn.close()


# Additive, idempotent migrations for DBs created before a column existed.
# Safe to run on every startup: ADD COLUMN is a no-op if the column is present.
_ADD_COLUMNS = {
    "listings": {
        "excludable_tags": "TEXT",
        "last_seen": "TEXT",
        "enriched_at": "TEXT",
    },
    "broker_stats": {
        "chars_fed": "INTEGER",   # markdown chars actually digested (==60000 means at the feed limit)
        "pages": "INTEGER",       # pages crawled this scrape (>1 means pagination kicked in)
    },
    "broker_sources": {
        "block_count": "INTEGER DEFAULT 0",   # Firecrawl-blocked pages seen for this broker
        "last_blocked_at": "TEXT",
        "last_block_reason": "TEXT",
        "last_link_hash": "TEXT",             # fingerprint of last-extracted page (skip if unchanged)
        "last_link_urls": "TEXT",             # last-seen normalized listing URLs (skip if no NEW ones)
        "last_extracted_at": "TEXT",
    },
    "runs": {
        "model": "TEXT",          # Claude model for this run (per-model spend breakdown)
        "in_tokens": "INTEGER",   # Claude input tokens
        "out_tokens": "INTEGER",  # Claude output tokens
    },
    "accounts": {
        "digest_emails": "TEXT",  # comma-separated daily-digest recipients for this thesis
        "archived": "INTEGER DEFAULT 0",  # soft-archive flag
        "archived_at": "TEXT",
    },
}


def record_block(conn: sqlite3.Connection, broker: str, reason: str) -> None:
    """Leave a persistent broker-level mark when Firecrawl can't load a broker's pages, so a
    systematically-blocked broker (won't ever scrape) is visible long-term, not silently retried."""
    if not broker:
        return
    import datetime as _dt
    try:
        conn.execute(
            "UPDATE broker_sources SET block_count = COALESCE(block_count,0)+1, "
            "last_blocked_at = ?, last_block_reason = ? WHERE name = ?",
            (_dt.datetime.now(_dt.timezone.utc).isoformat(), (reason or "")[:160], broker))
        conn.commit()
    except Exception:
        pass  # a block-mark is a non-critical side-effect; never let it abort the run


def _iso(s):
    """Normalize 'M/D/YYYY' (v1) -> 'YYYY-MM-DD'. Pass ISO through; leave junk alone."""
    if not s:
        return s
    s = s.strip()
    try:
        import datetime as _dt
        if "/" in s:
            return _dt.datetime.strptime(s[:10], "%m/%d/%Y").date().isoformat()
    except ValueError:
        pass
    return s[:10]


def migrate(conn: sqlite3.Connection) -> dict:
    """Add missing columns, backfill last_seen, normalize mixed date formats to ISO."""
    added = []
    tables = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    for table, cols in _ADD_COLUMNS.items():
        if table not in tables:
            continue
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        for col, decl in cols.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
                added.append(f"{table}.{col}")
    # Backfill last_seen for legacy rows (first_seen is the only date they have).
    conn.execute("UPDATE listings SET last_seen = first_seen WHERE last_seen IS NULL")
    # Normalize any M/D/YYYY dates to ISO so date comparisons are reliable (idempotent).
    normalized = 0
    for r in conn.execute("SELECT id, first_seen, last_seen FROM listings "
                          "WHERE first_seen LIKE '%/%' OR last_seen LIKE '%/%'").fetchall():
        conn.execute("UPDATE listings SET first_seen=?, last_seen=? WHERE id=?",
                     (_iso(r["first_seen"]), _iso(r["last_seen"]), r["id"]))
        normalized += 1
    conn.commit()
    return {"added": added, "dates_normalized": normalized}
