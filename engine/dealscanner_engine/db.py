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
    owner_email TEXT
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
    content_hash      TEXT,
    first_seen        TEXT,                     -- date_added
    scored_at         TEXT                      -- NULL until scored
);
CREATE INDEX IF NOT EXISTS idx_listings_first_seen ON listings(first_seen);
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
    note               TEXT
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
    conn.close()
