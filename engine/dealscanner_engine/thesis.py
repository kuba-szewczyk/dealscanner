"""Thesis configs: load YAML seed defaults, seed editable account_settings rows,
read/update the live per-account settings the boards apply.

YAML files in thesis/ are SEED DEFAULTS ONLY. Once seeded into account_settings,
edits happen in the DB (Settings page / PUT /settings) — that is what makes filters
'expose the latest setup' without code changes.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import yaml

THESIS_DIR = Path(__file__).resolve().parents[2] / "thesis"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
