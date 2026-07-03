# Detail screening plan — rich context on the deals that matter, cheaply

## The problem
Today a listing is judged almost entirely on its **list-card** text (name, category, a
line of description) plus whatever financials the card exposed. That is fine for the
obvious calls, but it fails on the **contentious middle**: a listing that *might* fit —
a "specialty clinic," a practice with no stated location, a tier-2 keyword with no
context — currently either (a) qualifies on thin evidence, or (b) silently fails to
qualify and is never seen. Both are bad. The operator gets no way to **vote** on the
deals where a human judgment call is exactly what's needed.

The fix is a **tiered screen** that spends detail-fetch budget only where it changes a
decision, and returns enough structured context to vote on the unclear ones.

## Principle: spend tokens where they change a decision
Every new listing lands in one of three buckets after the free, code-only evaluator runs:

| Bucket | Definition (code, $0) | Action |
|---|---|---|
| **Clear yes** | tier-1 keyword + in-metro + size OK | Enrich financials + one-line brief for the board/email. |
| **Clear no** | no keyword, or excluded, or known off-metro with no signal | Drop. **No spend, ever.** |
| **Contentious** | tier-2-only / relevance 1–2, OR qualifying keyword but **unknown location or financials**, OR `off_geo` with unplaceable location, OR a negative-flag caveat | **This is where the money goes.** Fetch detail, build a brief, route to *Needs review* so a human votes. |

The geo gate added for the concierge thesis already produces two of these signals
(`off_geo`, unplaceable location). The contentious bucket is the union of the borderline
cases — precisely the deals that "no info → don't qualify" throws away today.

## The screen, in tiers (cheapest first)

**Tier 0 — List extraction** *(exists)*
The daily scrape pulls list cards: one Haiku call per broker index page, Firecrawl-cached.
~$0.02/broker. Nothing changes here.

**Tier 1 — Code triage** *(exists, free)*
The evaluator sorts every new listing into the three buckets above. No tokens.

**Tier 2 — Detail page** *(extend the current enrich stage)*
Fetch the listing's **own** page (Firecrawl, disk-cached, once-ever via `enriched_at`).
Then two passes:
- **2a. Regex financials** *(exists, free)* — parse the clean markdown for labelled $ figures.
- **2b. Structured brief** *(new, one cheap Haiku call)* — from the main content
  (truncated to ~6–8k chars) return a tight JSON:
  ```
  { what_it_does, services[], customer_mix, recurring_revenue_signal,
    location_confirmed, thesis_fit_reason, contention_reason,
    confidence: 0-1 }
  ```
  `max_tokens` ~600, cheapest model, strict schema. This is the "double-click" context
  a card is missing today — and the evidence to vote on a contentious deal.

  Run 2b for **clear-yes** (so the board/email deal cards are rich) and for **contentious**
  (so they can be judged). Never for clear-no.

**Tier 3 — One subpage hop** *(new, rare, capped)*
Only when the detail page is **thin** (`looks_dead`/low chars) **and** the deal is
contentious **and** high-potential (qualifying keyword + target metro). Follow at most
1 linked "about/services" subpage, same-domain only, then re-run 2b. Most deals never
reach here; this is the escape hatch for the few worth extra spend.

## What the operator sees
- **Clear-yes** deals show their brief inline on the board card and in the digest.
- **Contentious** deals surface in a new **"Needs review"** section (or the existing
  non-qualifying pile, tagged `contentious`) with the brief + `contention_reason` +
  `confidence`. The operator votes yes/maybe/no **with context**, instead of the deal
  vanishing. Those votes become the ranking-model training set — closing the loop.

## Token / cost controls (why this stays cheap)
- **Triage gate**: clear-no never costs a token; spend concentrates on the small
  contentious + qualifying set (tens of deals/day, not thousands).
- **Regex-first** financials; Haiku only fills the gaps.
- **Cache everything**: Firecrawl markdown on disk, Haiku briefs keyed by `content_hash`;
  `enriched_at` guarantees each page is screened at most once, ever.
- **Bounded input**: send main-content markdown truncated, not the whole page; tight JSON
  schema; low `max_tokens`.
- **Per-stage $ caps** (already in `scrape-all`/`enrich`): a daily screen cap (e.g. $3)
  plus a separate Tier-3 sub-cap so subpage hops can't run away.
- **Model tiering**: Haiku for 2b by default; optionally escalate *only* a contentious
  deal with `confidence < 0.4` to a stronger model — the one place a better model earns
  its cost.

## Rollout
1. Add the `contentious` classification to the evaluator (derive from section + relevance
   + unknown-location/financials). No new scrape.
2. Extend `enrich` → `screen`: keep 2a, add the 2b structured brief; store `brief_json`,
   `thesis_fit_reason`, `confidence`, `contentious` columns.
3. Board: render the brief on cards; add the **Needs review** section fed by `contentious`.
4. Daily pipeline: `scrape-all → screen → notify`, screen capped (~$3/day) on the
   qualifying + contentious set only.
5. Backfill the existing ~3,000 unenriched listings at a nightly cap, contentious-first.

## Rough cost
Steady state: ~10–50 new qualifying+contentious deals/day × ~$0.005 per brief ≈ **cents
a day**. The one-time backlog is a few dollars total, spread over nights, contentious-first
so the highest-value context lands first.
