"""Optional AI RE-JUDGE — the cached semantic layer over the instant code re-match.

For a handful of listings, ask Claude (Haiku, cheap) to judge thesis relevance using
the account's CURRENT keywords, catching non-standard wording the literal keyword match
misses. Results are cached by (content_hash, account) so re-runs never double-pay.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from . import db
from .scrape import EXTRACT_MODEL, _cost, _parse_array  # reuse model + pricing + parser
from .thesis import account_id_for, get_settings


def rejudge(account: str, limit: int = 5, max_usd: float = 0.10) -> dict:
    from anthropic import Anthropic
    conn = db.connect()
    aid = account_id_for(conn, account)
    settings = get_settings(conn, account)
    kw = settings.get("keywords", {}).get("tier1", [])[:40]

    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM listings ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]

    todo, cached = [], 0
    for r in rows:
        hit = conn.execute(
            "SELECT result_json FROM score_cache WHERE content_hash=? AND account_id=?",
            (r["content_hash"], aid)).fetchone()
        if hit:
            cached += 1
        else:
            todo.append(r)

    cost = 0.0
    if todo:
        client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        payload = [{"id": r["id"], "text": (r["full_text"] or r["business_name"] or "")[:600]} for r in todo]
        system = (f"You are screening listings for the '{account}' thesis. Relevant keywords/themes: "
                  f"{', '.join(kw)}. For EACH listing return JSON "
                  '{"id":int,"relevance":0-5,"matched":["..."],"rationale":"<12 words"}. '
                  "Relevance 5=clear fit (even via non-standard wording), 0=unrelated. "
                  "Output ONLY a JSON array.")
        resp = client.messages.create(
            model=EXTRACT_MODEL, max_tokens=1500, system=system,
            messages=[{"role": "user", "content": json.dumps(payload)}])
        cost = _cost(EXTRACT_MODEL, resp.usage.input_tokens, resp.usage.output_tokens)
        if cost > max_usd:
            raise SystemExit(f"SPEND CAP hit: re-judge cost ${cost:.4f} > cap ${max_usd}")
        results = {x["id"]: x for x in _parse_array(
            "".join(b.text for b in resp.content if hasattr(b, "text")))}
        now = datetime.now(timezone.utc).isoformat()
        by_id = {r["id"]: r for r in todo}
        for lid, res in results.items():
            r = by_id.get(lid)
            if not r:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO score_cache(content_hash, account_id, result_json, created_at) "
                "VALUES (?,?,?,?)", (r["content_hash"], aid, json.dumps(res), now))
            conn.execute(
                """INSERT OR REPLACE INTO scores(listing_id, account_id, relevance, matched_keywords,
                   section, tier, fit_score, rationale, method, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (lid, aid, res.get("relevance"), ", ".join(res.get("matched", [])),
                 "in" if (res.get("relevance") or 0) >= 2 else "out", None,
                 float(res.get("relevance") or 0) * 2, res.get("rationale"), "ai-rejudge", now))
        conn.execute(
            "INSERT INTO runs(kind, started_at, ended_at, listings_processed, new_count, cost_usd, note) "
            "VALUES ('rejudge',?,?,?,?,?,?)",
            (now, now, len(todo), len(results), cost, f"{account}: {cached} cache hits"))
        conn.commit()
    return {"account": account, "judged_live": len(todo), "cache_hits": cached,
            "cost_usd": round(cost, 4)}
