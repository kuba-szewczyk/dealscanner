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
from dealscanner_engine import db, evaluator, thesis

app = FastAPI(title="DealScanner v2 API", version="2.0.0-dev")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://127.0.0.1:3001"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

ALLOW_LIST = authmod.ALLOW_LIST  # env-driven; see auth.py


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
        host = request.headers.get("host", "localhost:8099")
        scheme = request.headers.get("x-forwarded-proto") or (
            "https" if "sslip.io" in host or "dealscanner.us" in host else "http")
        token = authmod.make_login_token(email)
        link = f"{scheme}://{host}/api/auth/verify?token={token}"
        try:
            authmod.send_magic_link(email, link)
        except Exception as e:
            return {"sent": False, "error": str(e)[:160]}
    return {"sent": True}


@app.get("/auth/verify")
def auth_verify(token: str, request: Request):
    """Validate the link, set a 14-day session cookie, bounce to the board."""
    email = authmod.email_from_login_token(token)
    host = request.headers.get("host", "")
    fwd = request.headers.get("x-forwarded-proto")
    https = fwd == "https" or (not fwd and ("sslip.io" in host or "dealscanner.us" in host))
    base = f"https://{host}" if https else f"http://{host}"
    if not email:
        return RedirectResponse(f"{base}/login?error=expired", status_code=303)
    resp = RedirectResponse(f"{base}/", status_code=303)
    secure = https
    resp.set_cookie("ds_session", authmod.make_session(email), max_age=60 * 60 * 24 * 14,
                    httponly=True, samesite="lax", secure=secure, path="/")
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
    conn.execute(
        "INSERT INTO votes(account_id, listing_id, operator_email, verdict, context_json, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (aid, payload["listing_id"], email, payload["verdict"],
         json.dumps(snapshot), datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    return {"recorded": True, "verdict": payload["verdict"]}


@app.get("/runs")
def runs(limit: int = 10):
    conn = db.connect()
    rows = [dict(r) for r in conn.execute(
        "SELECT kind, started_at, listings_processed, new_count, cost_usd, note "
        "FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
    total = conn.execute("SELECT COALESCE(SUM(cost_usd),0) t FROM runs").fetchone()["t"]
    return {"total_spend_usd": round(total, 4), "runs": rows}


@app.get("/brokers")
def brokers():
    """Per-broker yield + health — surfaces silent scrape failures (the v1 '8 of 20
    brokers returned 0 cards' problem, made visible)."""
    conn = db.connect()
    rows = conn.execute(
        """SELECT broker, COUNT(*) total, MAX(first_seen) last_seen,
                  SUM(CASE WHEN first_seen >= date('now','-30 day') THEN 1 ELSE 0 END) last30
           FROM listings WHERE broker IS NOT NULL GROUP BY broker ORDER BY total DESC"""
    ).fetchall()
    from datetime import date, datetime
    today = date.today()

    def parse_day(s: str):
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%-m/%-d/%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except (ValueError, TypeError):
                continue
        return None

    out = []
    for r in rows:
        last = r["last_seen"] or ""
        d = parse_day(last)
        age = (today - d).days if d else 999
        health = "producing" if age <= 4 else "degraded" if age <= 10 else "silent"
        out.append({"broker": r["broker"], "total": r["total"], "last30": r["last30"],
                    "last_seen": d.isoformat() if d else last, "days_since": age, "health": health})
    return {"brokers": out}


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
