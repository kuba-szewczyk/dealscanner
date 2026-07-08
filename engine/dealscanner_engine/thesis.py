"""Thesis configs: load YAML seed defaults, seed editable account_settings rows,
read/update the live per-account settings the boards apply.

YAML files in thesis/ are SEED DEFAULTS ONLY. Once seeded into account_settings,
edits happen in the DB (Settings page / PUT /settings) — that is what makes filters
'expose the latest setup' without code changes.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import yaml

THESIS_DIR = Path(__file__).resolve().parents[2] / "thesis"

# A new thesis starts blank-but-valid: no keywords, a default size band, geo off.
BLANK_SETTINGS = {
    "size": {"ebitda_min": 1000000, "ebitda_max": 5000000, "sde_min": 1500000, "reject_below_ask": 1000000},
    "keywords": {"tier1": [], "tier2": [], "context": [], "negative": [], "exclude_terms": []},
    "geo": {"require": False, "tier1_metros": [], "tier2_states": []},
    "categories": {"exclude": []},
    "flags": {"positive": ["geo_t1", "geo_t2", "margin_gt_20", "owner_retiring", "recurring_40"],
              "negative": ["low_margin_lt_15", "overpriced", "franchise_resale", "partial"]},
    "ranking": {"weights": {"relevance": 2.0, "flag_score": 1.0}},
    "exclusions": {},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(name: str, conn: sqlite3.Connection) -> str:
    """URL-safe, unique slug from a display name. Slugs are stable keys (never renamed)."""
    base = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-") or "thesis"
    slug, n = base, 2
    while conn.execute("SELECT 1 FROM accounts WHERE slug=?", (slug,)).fetchone():
        slug, n = f"{base}-{n}", n + 1
    return slug


def create_account(conn: sqlite3.Connection, name: str, digest_emails: str = "",
                   owner_email: str | None = None) -> str:
    """Create a new thesis (account + blank editable settings). Returns its slug."""
    name = (name or "").strip()
    if not name:
        raise ValueError("thesis name is required")
    slug = slugify(name, conn)
    conn.execute("INSERT INTO accounts(slug, name, digest_emails, owner_email) VALUES (?,?,?,?)",
                 (slug, name, digest_emails, owner_email))
    aid = conn.execute("SELECT id FROM accounts WHERE slug=?", (slug,)).fetchone()["id"]
    conn.execute("INSERT INTO account_settings(account_id, settings_json, updated_at) VALUES (?,?,?)",
                 (aid, json.dumps(BLANK_SETTINGS), _now()))
    conn.commit()
    return slug


def update_account(conn: sqlite3.Connection, slug: str, name: str | None = None,
                   digest_emails: str | None = None) -> None:
    """Rename a thesis and/or set its digest recipients. Slug stays fixed."""
    aid = account_id_for(conn, slug)
    if name is not None and name.strip():
        conn.execute("UPDATE accounts SET name=? WHERE id=?", (name.strip(), aid))
    if digest_emails is not None:
        conn.execute("UPDATE accounts SET digest_emails=? WHERE id=?", (digest_emails.strip(), aid))
    conn.commit()


def list_accounts(conn: sqlite3.Connection, include_archived: bool = False) -> list[dict]:
    """Active theses with display name, digest recipients, owner, and last-edited time.
    Archived theses are excluded unless include_archived=True."""
    where = "" if include_archived else "WHERE COALESCE(a.archived, 0) = 0"
    return [dict(r) for r in conn.execute(
        "SELECT a.slug, a.name, COALESCE(a.digest_emails,'') digest_emails, "
        "COALESCE(a.owner_email,'') owner_email, COALESCE(a.archived,0) archived, "
        "a.archived_at, s.updated_at "
        f"FROM accounts a LEFT JOIN account_settings s ON s.account_id = a.id {where} ORDER BY a.id").fetchall()]


def list_archived(conn: sqlite3.Connection) -> list[dict]:
    """Archived theses only, for the restore list (name, owner, when archived)."""
    return [dict(r) for r in conn.execute(
        "SELECT slug, name, COALESCE(owner_email,'') owner_email, archived_at "
        "FROM accounts WHERE COALESCE(archived,0) = 1 ORDER BY archived_at DESC").fetchall()]


def set_archived(conn: sqlite3.Connection, slug: str, archived: bool) -> None:
    """Soft-archive (or restore) a thesis. Keeps all settings and votes intact."""
    aid = account_id_for(conn, slug)
    conn.execute("UPDATE accounts SET archived=?, archived_at=? WHERE id=?",
                 (1 if archived else 0, _now() if archived else None, aid))
    conn.commit()


def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_global_exclusions() -> dict[str, list[str]]:
    data = load_yaml(THESIS_DIR / "global_exclusions.yaml")
    return data.get("exclude", {})


def seed_accounts(conn: sqlite3.Connection, thesis_dir: Path = THESIS_DIR) -> list[str]:
    """Create accounts + seed their editable settings from thesis/*.yaml.
    Idempotent: existing accounts keep their (possibly user-edited) settings."""
    seeded = []
    for yml in sorted(thesis_dir.glob("*.yaml")):
        if yml.name == "global_exclusions.yaml":
            continue
        cfg = load_yaml(yml)
        slug = cfg["slug"]
        conn.execute(
            "INSERT OR IGNORE INTO accounts(slug, name, owner_email) VALUES (?,?,?)",
            (slug, cfg.get("name", slug), cfg.get("owner_email")),
        )
        row = conn.execute("SELECT id FROM accounts WHERE slug=?", (slug,)).fetchone()
        account_id = row["id"]
        exists = conn.execute(
            "SELECT 1 FROM account_settings WHERE account_id=?", (account_id,)
        ).fetchone()
        if not exists:
            settings = {k: cfg[k] for k in ("size", "keywords", "geo", "categories", "flags", "ranking") if k in cfg}
            conn.execute(
                "INSERT INTO account_settings(account_id, settings_json, updated_at) VALUES (?,?,?)",
                (account_id, json.dumps(settings), _now()),
            )
            seeded.append(slug)
    conn.commit()
    return seeded


def account_id_for(conn: sqlite3.Connection, slug: str) -> int:
    row = conn.execute("SELECT id FROM accounts WHERE slug=?", (slug,)).fetchone()
    if not row:
        raise KeyError(f"Unknown account slug: {slug}")
    return row["id"]


def get_settings(conn: sqlite3.Connection, slug: str) -> dict:
    aid = account_id_for(conn, slug)
    row = conn.execute(
        "SELECT settings_json FROM account_settings WHERE account_id=?", (aid,)
    ).fetchone()
    return json.loads(row["settings_json"]) if row else {}


def update_settings(conn: sqlite3.Connection, slug: str, settings: dict) -> None:
    """Edit the live thesis config. The boards immediately reflect this on next query
    (instant code re-match) — no re-scrape."""
    aid = account_id_for(conn, slug)
    conn.execute(
        "UPDATE account_settings SET settings_json=?, updated_at=? WHERE account_id=?",
        (json.dumps(settings), _now(), aid),
    )
    conn.commit()
