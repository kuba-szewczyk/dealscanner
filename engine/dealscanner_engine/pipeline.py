"""Daily pipeline: scrape every broker, then email the digest.

The digest is ALWAYS sent — even with zero new listings — because that email is
the dead-man's heartbeat: no morning email means the pipeline did not run (the
exact v2 failure mode that went unnoticed).
"""
from __future__ import annotations

import os
import traceback
from datetime import datetime, timezone

from . import db, evaluator, mailer, thesis
from .scrape import BROKER_URLS, scrape_broker

DIGEST_TO = [a.strip() for a in os.environ.get("DIGEST_TO", "").split(",") if a.strip()]


def scrape_all(max_usd: float = 0.25, fresh: bool = False) -> list[dict]:
    """Scrape every broker; one broker failing never kills the run."""
    results = []
    for slug in BROKER_URLS:
        try:
            results.append(scrape_broker(slug, max_usd=max_usd, fresh=fresh))
        except Exception as e:
            results.append({"broker": slug, "error": f"{type(e).__name__}: {e}"})
            conn = db.connect()
            conn.execute(
                "INSERT INTO logs(ts, level, stage, broker, message) VALUES (?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), "ERROR", "scrape", slug,
                 traceback.format_exc()[-2000:]))
            conn.commit()
    return results


def digest(date: str | None = None) -> str:
    """Compose the daily digest and send it. Returns the mail method used."""
    if not DIGEST_TO:
        raise RuntimeError("DIGEST_TO is not set — no one to send the digest to")
    date = date or datetime.now(timezone.utc).date().isoformat()
    conn = db.connect()
    accounts = [dict(r) for r in conn.execute("SELECT id, slug, name FROM accounts").fetchall()]

    sections, counts = [], []
    for acct in accounts:
        settings = thesis.get_settings(conn, acct["slug"])
        rows = evaluator.board(conn, settings, date=date, include_sections=("in",), limit=15)
        counts.append(f"{len(rows)} {acct['slug']}")
        lines = [f"== {acct['name']} — {len(rows)} new =="]
        for r in rows:
            fin = r.get("ebitda") or r.get("sde")
            fins = f"${fin / 1e6:.1f}M" if fin else "?"
            lines.append(f"  [{r['fit_score']:>3}] {r.get('business_name') or '(unnamed)'} "
                         f"({r.get('state') or '?'}, {fins}) — {r.get('listing_url')}")
        sections.append("\n".join(lines))

    run = conn.execute(
        "SELECT COUNT(*) n, COALESCE(SUM(cost_usd),0) c FROM runs "
        "WHERE kind='scrape' AND started_at >= ?", (date,)).fetchone()
    body = (f"DealScanner digest for {date}\n\n" + "\n\n".join(sections) +
            f"\n\n--\n{run['n']} scrape runs today, ${run['c']:.4f} spent. "
            f"This email doubles as the it-ran heartbeat.")
    subject = f"DealScanner {date}: " + ", ".join(counts) + " new"
    return mailer.send(DIGEST_TO, subject, body)
