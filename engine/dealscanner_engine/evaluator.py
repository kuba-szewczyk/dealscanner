"""The settings-driven evaluator — the spine of v2.

Given an account's CURRENT settings and a thesis-neutral listing, compute relevance,
section, flags, tier and a fit_score, entirely in code over already-stored data.
This is the 'instant code re-match': editing settings re-ranks the whole corpus with
no LLM call and no re-scrape. (The optional AI re-judge is a separate, cached pass.)
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional


def _parse_day(s: Optional[str]) -> Optional[date]:
    """Accept ISO 'YYYY-MM-DD' (with or without time) and v1 'M/D/YYYY'."""
    if not s:
        return None
    s = s.strip()[:10] if "T" not in s else s.split("T", 1)[0]
    try:
        return date.fromisoformat(s)
    except ValueError:
        pass
    try:
        return datetime.strptime(s, "%m/%d/%Y").date()
    except ValueError:
        return None


def match_exclusion_tags(text: str, exclusions: dict[str, list[str]]) -> list[str]:
    """Station 3: tag (don't drop). Return the global non-target CATEGORY names whose
    keywords appear in the listing text, so each thesis can decide whether to hide them."""
    t = (text or "").lower()
    return sorted(cat for cat, kws in exclusions.items()
                  if any(kw.lower() in t for kw in kws))


def classify_staleness(first_seen: Optional[str], last_seen: Optional[str],
                       today: Optional[str] = None, stale_days: int = 30) -> str:
    """new = first discovered today · active = seen within stale_days · stale = older.
    A re-found old listing reads 'active', never 'new' (first_seen is sticky)."""
    today = today or date.today().isoformat()
    td = _parse_day(today)
    ls = _parse_day(last_seen) or _parse_day(first_seen)
    if td and ls and (td - ls).days > stale_days:
        return "stale"
    if first_seen and _parse_day(first_seen) == td:
        return "new"
    return "active"


def _kw_relevance(text: str, kw: dict) -> tuple[int, list[str]]:
    """Graded 1-5 confidence over a keyword set (restores v1's full 1..5 scale).

      5  strong on-thesis: 2+ tier1 hits, or a tier1 hit backed by context
      4  one tier1 hit (clear industry match, no extra corroboration)
      3  tier1 but with a negative caveat, OR two+ tier2 hits backed by context
      2  one tier2 hit backed by context (decent secondary signal)
      1  a tier2 industry word with NO qualifying context (marginal/keep-an-eye)
      0  no industry keyword at all
    """
    t = (text or "").lower()
    tier1 = [k for k in kw.get("tier1", []) if k.lower() in t]
    context_present = any(c.lower() in t for c in kw.get("context", []))
    tier2 = [k for k in kw.get("tier2", []) if k.lower() in t]
    negatives = [k for k in kw.get("negative", []) if k.lower() in t]
    if not tier1 and not tier2:
        return 0, []
    if tier1:
        rel = 5 if (len(tier1) >= 2 or context_present) else 4
        if negatives:
            rel = 3
    else:  # tier2 only
        if context_present:
            rel = 3 if len(tier2) >= 2 else 2
        else:
            rel = 1
        if negatives:
            rel = max(1, rel - 1)
    return rel, (tier1 + tier2)[:5]


_STATE_ABBR = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV", "new hampshire": "NH",
    "new jersey": "NJ", "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD", "tennessee": "TN",
    "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
}


def _norm_state(s: Optional[str]) -> str:
    """Normalize a state field to a 2-letter code. Handles 'CA', 'California', 'ca'."""
    s = (s or "").strip()
    if len(s) == 2:
        return s.upper()
    return _STATE_ABBR.get(s.lower(), "")


def _geo_match(listing: dict, geo: dict) -> bool:
    """True if the listing is in one of the thesis's target metros or states."""
    metros = [m.lower() for m in geo.get("tier1_metros", [])]
    hay = f"{(listing.get('city') or '').lower()} {(listing.get('full_text') or '').lower()}"
    if any(m in hay for m in metros):
        return True
    return _norm_state(listing.get("state")) in set(geo.get("tier2_states", []))


def _size_ok(l: dict, size: dict) -> bool:
    ask, rev, eb, sde = l.get("asking_price"), l.get("revenue"), l.get("ebitda"), l.get("sde")
    floor = size.get("reject_below_ask", 1_000_000)
    if ask is not None and ask < floor:
        return False
    if rev is not None and rev < floor:
        return False
    if eb is not None and size.get("ebitda_min", 0) <= eb <= size.get("ebitda_max", 1e12):
        return True
    if sde is not None and size.get("sde_min", 1e12) <= sde <= size.get("sde_max", 1e15):
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
    if _norm_state(l.get("state")) in geo.get("tier2_states", []):
        pos.append("geo_t2")
    th = settings.get("thresholds", {})
    margin = l.get("ebitda_margin_pct")
    if margin is not None and margin > th.get("margin_good", 20):
        pos.append("margin_gt_20")
    if "retir" in text:
        pos.append("owner_retiring")
    rec = l.get("recurring_pct")
    if rec is not None and rec >= th.get("recurring", 40):
        pos.append("recurring_40")

    if margin is not None and margin < th.get("margin_low", 15):
        neg.append("low_margin_lt_15")
    ask, eb_v, sde_v = l.get("asking_price"), l.get("ebitda"), l.get("sde")
    if ask and eb_v and eb_v > 0 and ask / eb_v > th.get("overprice_ebitda", 6):
        neg.append("overpriced")
    elif ask and sde_v and sde_v > 0 and ask / sde_v > th.get("overprice_sde", 5):
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


# Quick-exclusion keyword sets toggled from Thesis setup. Kept tight on purpose.
_EXCL_KW = {
    "restaurants": ["restaurant", "pizzeria", " cafe", " café", "bistro", "diner", "bakery",
                    "coffee shop", "food truck", "catering", "brewery", "taqueria", "ice cream",
                    "juice bar", "sandwich shop", " deli", "donut", "doughnut", "bar & grill",
                    "bar and grill", "nightclub", "sports bar"],
    "real_estate": ["real estate", "for lease", "property management", "apartment complex",
                    "rental property", "land for sale", "commercial property", "office building",
                    "self storage", "self-storage", "mobile home park", "rv park"],
    "franchise": ["franchise", "franchisee", "franchisor"],
}


def _excluded(text: str, settings: dict) -> bool:
    """Thesis-level keyword exclusions for categories NOT covered by global tags
    (real estate, franchise). Restaurants/consumer junk are handled by excludable_tags."""
    t = text.lower()
    # Hard-exclude terms: a match forces the listing out of the thesis, regardless of any
    # keyword hit. Use for adjacent-but-wrong businesses (e.g. dental/vet for a primary-care
    # thesis) that soft 'negative' keywords only cap rather than remove.
    hard = settings.get("keywords", {}).get("exclude_terms", [])
    if hard and any(k.lower() in t for k in hard):
        return True
    ex = settings.get("exclusions") or {}
    # Both default OFF (real estate also appears in good deals like "practice WITH real estate").
    for key, on in (("real_estate", ex.get("real_estate", False)),
                    ("franchise", ex.get("franchise", False))):
        if on and any(k in t for k in _EXCL_KW[key]):
            return True
    return False


def _excluded_by_tags(listing: dict, settings: dict) -> bool:
    """A thesis hides a listing if any of its stored excludable_tags is in the thesis's
    exclude set. Default (exclude_tags absent) = exclude ALL global non-target tags,
    preserving today's hide-consumer-junk behavior while keeping the rows in the DB."""
    tags = [t.strip() for t in (listing.get("excludable_tags") or "").split(",") if t.strip()]
    if not tags:
        return False
    exclude_set = settings.get("exclude_tags")  # None => all
    return exclude_set is None or any(t in exclude_set for t in tags)


def evaluate(listing: dict, settings: dict, today: Optional[str] = None) -> dict:
    """Pure function: (thesis-neutral listing, current settings) -> per-account verdict."""
    kw = settings.get("keywords", {})
    text = " ".join(str(listing.get(f, "") or "") for f in
                     ("business_name", "category", "one_line_take", "full_text"))
    relevance, matched = _kw_relevance(text, kw)
    pos, neg, flag_score = _flags(listing, settings)
    freshness = classify_staleness(listing.get("first_seen"), listing.get("last_seen"), today)

    if listing.get("is_sold"):
        section = "sold"
    elif _excluded_by_tags(listing, settings) or _excluded(text, settings):
        section = "excluded"
    elif freshness == "stale":
        section = "stale"
    elif not _size_ok(listing, settings.get("size", {})):
        section = "too_small"
    elif relevance >= 2:
        # Optional geo gate: when geo.require is on, a keyword+size match still only
        # qualifies if it is in a target metro/state. Off-geo (and unplaceable) deals
        # are held out of the board — they are the queue the detail-screening pass works.
        geo = settings.get("geo", {})
        if geo.get("require") and not _geo_match(listing, geo):
            section = "off_geo"
        else:
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
        "freshness": freshness,
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
