"""The settings-driven evaluator — the spine of v2.

Given an account's CURRENT settings and a thesis-neutral listing, compute relevance,
section, flags, tier and a fit_score, entirely in code over already-stored data.
This is the 'instant code re-match': editing settings re-ranks the whole corpus with
no LLM call and no re-scrape. (The optional AI re-judge is a separate, cached pass.)
"""
from __future__ import annotations

from typing import Optional


def _kw_relevance(text: str, kw: dict) -> tuple[int, list[str]]:
    """Port of v1 water decision logic, generalized over any keyword set.
    Tier1 single match = relevant; Tier2 needs a context word; negatives cap at 3."""
    t = (text or "").lower()
    matched: list[str] = []
    tier1 = [k for k in kw.get("tier1", []) if k.lower() in t]
    context_present = any(c.lower() in t for c in kw.get("context", []))
    tier2 = [k for k in kw.get("tier2", []) if k.lower() in t] if context_present else []
    negatives = [k for k in kw.get("negative", []) if k.lower() in t]
    matched = tier1 + tier2
    if not matched:
        return 0, []
    if tier1:
        rel = 3 if negatives else 5
    else:  # tier2 + context only
        rel = 3
    if negatives and rel > 3:
        rel = 3
    return rel, matched[:5]


def _size_ok(l: dict, size: dict) -> bool:
    ask, rev, eb, sde = l.get("asking_price"), l.get("revenue"), l.get("ebitda"), l.get("sde")
    floor = size.get("reject_below_ask", 1_000_000)
    if ask is not None and ask < floor:
        return False
    if rev is not None and rev < floor:
        return False
    if eb is not None and size.get("ebitda_min", 0) <= eb <= size.get("ebitda_max", 1e12):
        return True
    if sde is not None and sde >= size.get("sde_min", 1e12):
        return True
    if eb is None and sde is None:
        return True  # unknown financials pass the size gate (judged elsewhere)
    return False


def _flags(l: dict, settings: dict) -> tuple[list[str], list[str], int]:
    geo = settings.get("geo", {})
    flagcfg = settings.get("flags", {})
    text = f"{l.get('city','')} {l.get('state','')} {l.get('one_line_take','')} {l.get('full_text','')}".lower()
    pos: list[str] = []
    neg: list[str] = []

    metros = [m.lower() for m in geo.get("tier1_metros", [])]
    if any(m in f"{(l.get('city') or '').lower()} {(l.get('full_text') or '').lower()}" for m in metros):
        pos.append("geo_t1")
    if (l.get("state") or "") in geo.get("tier2_states", []):
        pos.append("geo_t2")
    margin = l.get("ebitda_margin_pct")
    if margin is not None and margin > 20:
        pos.append("margin_gt_20")
    if "retir" in text:
        pos.append("owner_retiring")
    rec = l.get("recurring_pct")
    if rec is not None and rec >= 40:
        pos.append("recurring_40")

    if margin is not None and margin < 15:
        neg.append("low_margin_lt_15")
    mult = l.get("multiple")
    if mult is not None and mult > 6:
        neg.append("overpriced")
    if "franchise" in text:
        neg.append("franchise_resale")
    if "minority" in text or "partial" in text or "asset sale" in text:
        neg.append("partial")

    # Keep only flags the account actually tracks.
    pos = [f for f in pos if f in flagcfg.get("positive", [])]
    allowed_neg = flagcfg.get("negative", [])
    neg = [f for f in neg if f in allowed_neg]
    score = len(pos) + (len(allowed_neg) - len(neg))
    return pos, neg, score


def evaluate(listing: dict, settings: dict) -> dict:
    """Pure function: (thesis-neutral listing, current settings) -> per-account verdict."""
    kw = settings.get("keywords", {})
    text = " ".join(str(listing.get(f, "") or "") for f in
                     ("business_name", "category", "one_line_take", "full_text"))
    relevance, matched = _kw_relevance(text, kw)
    pos, neg, flag_score = _flags(listing, settings)

    if listing.get("is_sold"):
        section = "sold"
    elif not _size_ok(listing, settings.get("size", {})):
        section = "too_small"
    elif relevance >= 2:
        section = "in"
    else:
        section = "out"

    w = settings.get("ranking", {}).get("weights", {"relevance": 2.0, "flag_score": 1.0})
    fit_score = relevance * w.get("relevance", 2.0) + flag_score * w.get("flag_score", 1.0)

    if section == "in" and relevance >= 4 and flag_score >= 6:
        tier = "A"
    elif section == "in":
        tier = "B"
    elif section in ("too_small", "out"):
        tier = "C"
    else:
        tier = section.upper()

    return {
        "relevance": relevance,
        "matched_keywords": ", ".join(matched),
        "section": section,
        "tier": tier,
        "fit_score": round(fit_score, 2),
        "positive_flags": pos,
        "negative_flags": neg,
        "flag_score": flag_score,
    }


def board(conn, account_settings: dict, date: Optional[str] = None,
          include_sections=("in",), limit: int = 500) -> list[dict]:
    """Apply CURRENT settings to stored listings -> ranked board. Instant, $0."""
    sql = "SELECT * FROM listings"
    params: list = []
    if date:
        sql += " WHERE first_seen = ?"
        params.append(date)
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    out = []
    for l in rows:
        v = evaluate(l, account_settings)
        if v["section"] in include_sections:
            out.append({**l, **v})
    out.sort(key=lambda d: d["fit_score"], reverse=True)
    return out[:limit]
