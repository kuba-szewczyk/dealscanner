"""DealScanner v2 API (FastAPI). Thin JSON layer over the engine: the boards apply
each account's CURRENT settings to stored listings, settings are editable live, and
votes persist with a full-context snapshot. (Magic-link auth + broker/log endpoints
land in the next session; allow-list stub included.)"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make the engine importable without installing.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

from fastapi import Body, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

import auth as authmod
from dealscanner_engine import config, db, evaluator, thesis


def _safe_base(request: Request) -> str:
    """Base URL for links/redirects. Trust the request Host ONLY if it is allow-listed
    (preserves the domain + www + configured hosts); otherwise fall back to the
    canonical APP_BASE_URL. Blocks host-header poisoning of emailed magic links."""
    host = request.headers.get("host", "").lower()
    if host in config.trusted_hosts() or host.endswith(".sslip.io"):
        scheme = request.headers.get("x-forwarded-proto") or "https"
        return f"{scheme}://{host}"
    return config.app_base_url()

app = FastAPI(title="DealScanner v2 API", version="2.0.0-dev")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://127.0.0.1:3001"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

ALLOW_LIST = authmod.ALLOW_LIST  # env-driven; see auth.py / config.py


@app.get("/health")
def health():
    return {"ok": True, "db": str(db.DB_PATH)}


@app.get("/accounts")
def accounts():
    conn = db.connect()
    return [dict(r) for r in conn.execute("SELECT slug, name, owner_email FROM accounts").fetchall()]


@app.get("/board")
def get_board(account: str, date: str | None = None, sections: str = "in", limit: int = 100):
    conn = db.connect()
    try:
        settings = thesis.get_settings(conn, account)
    except KeyError:
        raise HTTPException(404, f"unknown account '{account}'")
    rows = evaluator.board(conn, settings, date=date,
                           include_sections=tuple(sections.split(",")), limit=limit)
    # Trim heavy fields for the list view.
    keep = ("id", "broker", "business_name", "category", "state", "city", "asking_price",
            "revenue", "sde", "ebitda", "multiple", "listing_url", "first_seen",
            "tier", "relevance", "fit_score", "matched_keywords", "one_line_take",
            "positive_flags", "negative_flags", "flag_score", "section")
    return {"account": account, "count": len(rows),
            "listings": [{k: r.get(k) for k in keep} for r in rows]}


@app.get("/search")
def search(q: str = "", sort: str = "accuracy", limit: int = 300):
    """Free-text keyword search across every listing (name, take, full text, category, broker).
    All terms must match (AND). sort: accuracy | date_desc | date_asc | revenue | ebitda."""
    conn = db.connect()
    terms = [w for w in q.lower().split() if w]
    if not terms:
        return {"count": 0, "results": []}
    rows = [dict(r) for r in conn.execute(
        "SELECT id, broker, business_name, category, state, city, revenue, ebitda, sde, "
        "asking_price, multiple, listing_url, first_seen, one_line_take, full_text FROM listings")]

    def score(r):
        name = (r["business_name"] or "").lower()
        take = (r["one_line_take"] or "").lower()
        hay = f"{name} {take} {(r['category'] or '').lower()} {(r['broker'] or '').lower()} {(r['full_text'] or '').lower()}"
        s = 0
        for w in terms:
            if w not in hay:
                return -1                              # every term must appear (AND)
            s += name.count(w) * 5 + take.count(w) * 2 + hay.count(w)
        return s

    matched = [(sc, r) for sc, r in ((score(r), r) for r in rows) if sc > 0]
    for _, r in matched:
        r.pop("full_text", None)                       # don't ship the heavy blob
    keyf = {
        "date_desc": (lambda x: x[1]["first_seen"] or "", True),
        "date_asc": (lambda x: x[1]["first_seen"] or "", False),
        "revenue": (lambda x: x[1]["revenue"] or 0, True),
        "ebitda": (lambda x: x[1]["ebitda"] or 0, True),
    }.get(sort)
    if keyf:
        matched.sort(key=keyf[0], reverse=keyf[1])
    else:
        matched.sort(key=lambda x: x[0], reverse=True)   # accuracy
    return {"count": len(matched), "results": [r for _, r in matched[:limit]]}


@app.get("/settings/{account}")
def get_settings(account: str):
    conn = db.connect()
    try:
        return thesis.get_settings(conn, account)
    except KeyError:
        raise HTTPException(404, f"unknown account '{account}'")


@app.put("/settings/{account}")
def put_settings(account: str, settings: dict = Body(...)):
    """Edit the live thesis config. Boards reflect it immediately (instant re-rank)."""
    conn = db.connect()
    try:
        thesis.update_settings(conn, account, settings)
    except KeyError:
        raise HTTPException(404, f"unknown account '{account}'")
    rows = evaluator.board(conn, settings, include_sections=("in",), limit=10000)
    return {"account": account, "saved": True, "board_count_now": len(rows)}


@app.post("/auth/request")
def auth_request(request: Request, payload: dict = Body(...)):
    """Email a magic link to an allow-listed operator. Always returns sent:true
    (never leaks who is on the list)."""
    email = (payload.get("email") or "").strip().lower()
    if email in authmod.ALLOW_LIST:
        token = authmod.make_login_token(email)
        link = f"{_safe_base(request)}/api/auth/verify?token={token}"
        try:
            authmod.send_magic_link(email, link)
        except Exception as e:
            return {"sent": False, "error": str(e)[:160]}
    return {"sent": True}


@app.get("/auth/verify")
def auth_verify(token: str, request: Request):
    """Validate the link, set a 14-day session cookie, bounce to the board."""
    email = authmod.email_from_login_token(token)
    base = _safe_base(request)
    if not email:
        return RedirectResponse(f"{base}/login?error=expired", status_code=303)
    resp = RedirectResponse(f"{base}/", status_code=303)
    resp.set_cookie("ds_session", authmod.make_session(email), max_age=60 * 60 * 24 * 14,
                    httponly=True, samesite="lax", secure=base.startswith("https"), path="/")
    return resp


@app.get("/auth/me")
def auth_me(request: Request):
    return {"email": authmod.email_from_session(request.cookies.get("ds_session"))}


@app.post("/auth/logout")
def auth_logout():
    resp = Response()
    resp.delete_cookie("ds_session", path="/")
    return resp


@app.post("/votes")
def post_vote(request: Request, payload: dict = Body(...)):
    """Persist a yes/no/maybe with a full-context snapshot (future-scorer substrate).
    Operator comes from the session cookie; falls back to body for API testing."""
    email = authmod.email_from_session(request.cookies.get("ds_session")) or payload.get("operator_email")
    if email not in authmod.ALLOW_LIST:
        raise HTTPException(403, "sign in to vote")
    conn = db.connect()
    aid = thesis.account_id_for(conn, payload["account"])
    listing = conn.execute("SELECT * FROM listings WHERE id=?", (payload["listing_id"],)).fetchone()
    if not listing:
        raise HTTPException(404, "unknown listing")
    settings = thesis.get_settings(conn, payload["account"])
    snapshot = {"thesis": payload["account"], "settings_at_vote": settings,
                "evaluation": evaluator.evaluate(dict(listing), settings),
                "listing": {k: listing[k] for k in listing.keys()}}
    # One verdict per operator per deal — re-voting updates, never duplicates.
    conn.execute("DELETE FROM votes WHERE account_id=? AND listing_id=? AND operator_email=?",
                 (aid, payload["listing_id"], email))
    conn.execute(
        "INSERT INTO votes(account_id, listing_id, operator_email, verdict, context_json, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (aid, payload["listing_id"], email, payload["verdict"],
         json.dumps(snapshot), datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    return {"recorded": True, "verdict": payload["verdict"]}


@app.post("/votes/clear")
def votes_clear(request: Request, payload: dict = Body(...)):
    """Remove the signed-in operator's vote on a deal (click the verdict again to unselect)."""
    email = authmod.email_from_session(request.cookies.get("ds_session")) or payload.get("operator_email")
    if email not in authmod.ALLOW_LIST:
        raise HTTPException(403, "sign in to vote")
    conn = db.connect()
    aid = thesis.account_id_for(conn, payload["account"])
    conn.execute("DELETE FROM votes WHERE account_id=? AND listing_id=? AND operator_email=?",
                 (aid, payload["listing_id"], email))
    conn.commit()
    return {"cleared": True}


@app.get("/runs")
def runs(limit: int = 10):
    conn = db.connect()
    rows = [dict(r) for r in conn.execute(
        "SELECT kind, started_at, listings_processed, new_count, cost_usd, note "
        "FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
    total = conn.execute("SELECT COALESCE(SUM(cost_usd),0) t FROM runs").fetchone()["t"]
    return {"total_spend_usd": round(total, 4), "runs": rows}


@app.get("/activity")
def activity(hours: int = 24):
    """Click-into-the-DB: proof that scraped rows persist. Returns the total corpus size,
    net-new listings in the window (straight from the listings table), and per-broker yield
    from the latest scrape run."""
    conn = db.connect()
    days = max(1, hours // 24)
    total = conn.execute("SELECT COUNT(*) c FROM listings").fetchone()["c"]
    new_rows = [dict(r) for r in conn.execute(
        "SELECT id, broker, business_name, category, state, ebitda, sde, asking_price, "
        "listing_url, first_seen, excludable_tags "
        "FROM listings WHERE date(first_seen) >= date('now', ?) ORDER BY id DESC",
        (f"-{days} day",)).fetchall()]
    # Per-broker yield from the most recent crawl DAY (handles batches of any size).
    latest_day = conn.execute(
        "SELECT date(MAX(created_at)) d FROM broker_stats").fetchone()["d"]
    per_broker = []
    if latest_day is not None:
        per_broker = [dict(r) for r in conn.execute(
            "SELECT broker, new_count, total_count, chars_fed, pages, status, created_at "
            "FROM broker_stats WHERE date(created_at)=? "
            "ORDER BY (status='dead') ASC, new_count DESC, total_count DESC", (latest_day,)).fetchall()]
    last_scrape = conn.execute(
        "SELECT MAX(started_at) s FROM runs WHERE kind='scrape'").fetchone()["s"]
    scrape_spend = conn.execute(
        "SELECT COALESCE(SUM(cost_usd),0) t FROM runs WHERE kind='scrape'").fetchone()["t"]
    return {"total_listings": total, "window_hours": hours, "net_new_count": len(new_rows),
            "net_new": new_rows, "per_broker": per_broker,
            "last_scrape_at": last_scrape, "scrape_spend_usd": round(scrape_spend, 4)}


def _parse_day(s: str):
    from datetime import datetime
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%-m/%-d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def _broker_site(url: str):
    from urllib.parse import urlsplit
    try:
        s = urlsplit(url or "")
        return f"{s.scheme}://{s.netloc}" if s.scheme and s.netloc else None
    except Exception:
        return None


def _seed_broker_sources(conn):
    """Ensure every broker seen in listings has a source row. Auto-discovered brokers are
    seeded 'pending' (homepage-only URL) — they only become 'live'/scraped once promoted
    with a confirmed listings-index URL, so they never silently enter the scrape set."""
    existing = {r["name"] for r in conn.execute("SELECT name FROM broker_sources").fetchall()}
    for r in conn.execute("SELECT broker, MIN(listing_url) url FROM listings WHERE broker IS NOT NULL GROUP BY broker").fetchall():
        if r["broker"] not in existing:
            conn.execute("INSERT OR IGNORE INTO broker_sources(name, url, status, created_at) VALUES (?,?,?,?)",
                         (r["broker"], _broker_site(r["url"]), "pending", datetime.now(timezone.utc).isoformat()))
    conn.commit()


def _signed_in(request: Request) -> bool:
    return authmod.email_from_session(request.cookies.get("ds_session")) in authmod.ALLOW_LIST


@app.get("/brokers")
def brokers():
    """Per-broker yield + health + 7-day strip, split into live vs archived sources."""
    from datetime import date, timedelta
    conn = db.connect()
    _seed_broker_sources(conn)
    today = date.today()
    week_days = [today - timedelta(days=n) for n in range(6, -1, -1)]

    yld = {r["broker"]: r for r in conn.execute(
        """SELECT broker, COUNT(*) total, MAX(first_seen) maxd, MIN(first_seen) mind,
                  SUM(CASE WHEN first_seen >= date('now','-30 day') THEN 1 ELSE 0 END) last30
           FROM listings WHERE broker IS NOT NULL GROUP BY broker""").fetchall()}
    counts: dict = {}
    for lr in conn.execute("SELECT broker, first_seen FROM listings WHERE broker IS NOT NULL").fetchall():
        d = _parse_day(lr["first_seen"] or "")
        if d and (today - d).days <= 6:
            counts[(lr["broker"], d)] = counts.get((lr["broker"], d), 0) + 1
    errs = set()
    for er in conn.execute("SELECT broker, ts FROM logs WHERE level='ERROR'").fetchall():
        d = _parse_day((er["ts"] or "")[:10])
        if d:
            errs.add((er["broker"], d))

    live, archived = [], []
    for src in conn.execute(
            "SELECT name, url, status, COALESCE(block_count,0) block_count, last_blocked_at "
            "FROM broker_sources").fetchall():
        name = src["name"]
        y = yld.get(name)
        total = y["total"] if y else 0
        maxd = _parse_day(y["maxd"]) if y and y["maxd"] else None
        mind = _parse_day(y["mind"]) if y and y["mind"] else None
        age = (today - maxd).days if maxd else None
        if not total:
            health = "pending"
        elif age is not None and age <= 7:
            health = "active"
        elif age is not None and age <= 30:
            health = "inactive"
        else:
            health = "degraded"
        week = []
        for day in week_days:
            if (name, day) in errs:
                week.append("e")
            elif counts.get((name, day), 0):
                week.append("g")
            elif (mind and day < mind) or not total:
                week.append("n")        # no data / not enough history yet (black)
            else:
                week.append("x")        # tracked, no new listing (gray)
        rec = {"broker": name, "url": src["url"], "status": src["status"], "total": total,
               "last30": (y["last30"] if y else 0), "days_since": age if age is not None else -1,
               "health": health, "week": week,
               "block_count": src["block_count"], "last_blocked_at": src["last_blocked_at"]}
        (archived if src["status"] == "archived" else live).append(rec)
    live.sort(key=lambda x: x["total"], reverse=True)
    archived.sort(key=lambda x: x["broker"].lower())
    return {"brokers": live, "archived": archived}


@app.post("/brokers/add")
def broker_add(request: Request, payload: dict = Body(...)):
    if not _signed_in(request):
        raise HTTPException(403, "sign in to manage brokers")
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name required")
    conn = db.connect()
    conn.execute("INSERT OR IGNORE INTO broker_sources(name, url, status, created_at) VALUES (?,?,?,?)",
                 (name, (payload.get("url") or "").strip(), "pending", datetime.now(timezone.utc).isoformat()))
    conn.commit()
    return {"added": True}


@app.post("/brokers/status")
def broker_status(request: Request, payload: dict = Body(...)):
    if not _signed_in(request):
        raise HTTPException(403, "sign in to manage brokers")
    if payload.get("status") not in ("live", "archived"):
        raise HTTPException(400, "bad status")
    conn = db.connect()
    conn.execute("UPDATE broker_sources SET status=? WHERE name=?", (payload["status"], payload.get("name")))
    conn.commit()
    return {"ok": True}


@app.post("/brokers/edit")
def broker_edit(request: Request, payload: dict = Body(...)):
    """Edit a broker's display name and site URL. Renaming cascades to its listings
    so yield/health stay attached."""
    if not _signed_in(request):
        raise HTTPException(403, "sign in to manage brokers")
    old = (payload.get("name") or "").strip()
    new = (payload.get("new_name") or old).strip()
    url = (payload.get("url") or "").strip()
    if not old or not new:
        raise HTTPException(400, "name required")
    conn = db.connect()
    if new != old:
        if conn.execute("SELECT 1 FROM broker_sources WHERE name=?", (new,)).fetchone():
            raise HTTPException(409, "a broker with that name already exists")
        conn.execute("UPDATE listings SET broker=? WHERE broker=?", (new, old))
    conn.execute("UPDATE broker_sources SET name=?, url=? WHERE name=?", (new, url, old))
    conn.commit()
    return {"ok": True}


@app.get("/votes/list")
def votes_list():
    """Every captured verdict with deal context — the running shortlist + training substrate."""
    conn = db.connect()
    rows = conn.execute(
        """SELECT v.verdict, v.listing_id, v.operator_email operator, v.created_at, a.slug thesis,
                  l.business_name, l.listing_url
           FROM votes v JOIN accounts a ON a.id = v.account_id
           LEFT JOIN listings l ON l.id = v.listing_id
           ORDER BY v.id DESC""").fetchall()
    votes = [dict(r) for r in rows]
    return {"total": len(votes), "votes": votes}


@app.post("/votes/recategorize")
def votes_recategorize(request: Request, payload: dict = Body(...)):
    """Move a voted deal to a different verdict (drag-and-drop between sections)."""
    if not _signed_in(request):
        raise HTTPException(403, "sign in to vote")
    if payload.get("verdict") not in ("yes", "maybe", "no"):
        raise HTTPException(400, "bad verdict")
    conn = db.connect()
    aid = thesis.account_id_for(conn, payload["account"])
    conn.execute("UPDATE votes SET verdict=? WHERE account_id=? AND listing_id=?",
                 (payload["verdict"], aid, payload["listing_id"]))
    conn.commit()
    return {"ok": True}


@app.get("/logs")
def logs():
    """Single queryable activity + cost ledger (replaces v1's two-log-file trap)."""
    conn = db.connect()
    runs = [dict(r) for r in conn.execute(
        "SELECT kind, started_at, listings_processed, new_count, cost_usd, note "
        "FROM runs ORDER BY id DESC LIMIT 50").fetchall()]
    events = [dict(r) for r in conn.execute(
        "SELECT ts, level, stage, broker, message FROM logs ORDER BY id DESC LIMIT 50").fetchall()]
    total = conn.execute("SELECT COALESCE(SUM(cost_usd),0) t FROM runs").fetchone()["t"]
    return {"total_spend_usd": round(total, 4), "runs": runs, "events": events}


@app.get("/instinct")
def instinct():
    """Vote-capture progress for the future learned scorer (data collection underway)."""
    conn = db.connect()
    by = {r["verdict"]: r["c"] for r in conn.execute(
        "SELECT verdict, COUNT(*) c FROM votes GROUP BY verdict").fetchall()}
    total = sum(by.values())
    return {"total_votes": total, "by_verdict": by,
            "target": 200, "ready": total >= 200}


@app.get("/stats")
def stats():
    conn = db.connect()
    return {t: conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
            for t in ("accounts", "listings", "scores", "votes", "runs")}
