"use client";
import { useEffect, useMemo, useState } from "react";
import { api, Deal, safeHref } from "@/lib/api";
import DealCard from "./DealCard";

const LABEL: Record<string, string> = { water: "Water / Wastewater", healthcare: "Healthcare" };
const FLAG_LABEL: Record<string, string> = {
  geo_t1: "Tier-1 metro", geo_t2: "Tier-2 state", margin_gt_20: "20%+ EBITDA margin",
  owner_retiring: "Owner retiring", recurring_40: "40%+ recurring",
  low_margin_lt_15: "Low margin (<15%)", overpriced: "Overpriced", franchise_resale: "Franchise resale",
  partial: "Minority / partial sale",
};
const CAT_CLASS: Record<string, string> = {
  "Healthcare": "c-teal", "Restaurant & Food": "c-pink", "Construction & Trades": "c-amber",
  "Manufacturing": "c-purple", "Retail & E-commerce": "c-rose", "Professional Services": "c-blue",
  "Personal Care & Fitness": "c-green", "Real Estate & Property": "c-slate",
  "Distribution & Wholesale": "c-indigo", "Auto & Transport": "c-orange",
  "Education & Childcare": "c-cyan", "Cleaning & Facilities": "c-lime",
  "Hospitality & Lodging": "c-brown", "Services": "c-blue", "Software": "c-purple",
  "E-commerce": "c-rose", "Other": "c-gray",
};
const fmtM = (v?: number | null) => v == null ? "—" : `$${(v / 1e6).toFixed(1)}M`;          // always millions
const money = (v?: number | null) => v == null ? "—" : v >= 1e6 ? `$${(v / 1e6).toFixed(1)}M` : `$${Math.round(v / 1e3)}K`;

function parseDate(s?: string): Date | null {
  if (!s) return null;
  let m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  if (m) return new Date(+m[1], +m[2] - 1, +m[3]);
  m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})/.exec(s);
  if (m) return new Date(+m[3], +m[1] - 1, +m[2]);
  return null;
}
const fmtDate = (s?: string) => {
  const d = parseDate(s);
  if (!d) return "";
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${mm}-${dd}-${d.getFullYear()}`;
};

export default function Board() {
  const [thesis, setThesis] = useState("water");
  const [deals, setDeals] = useState<Deal[]>([]);
  const [spend, setSpend] = useState(0);
  const [loading, setLoading] = useState(true);
  const [voted, setVoted] = useState<Record<number, string>>({});
  const [voteFilter, setVoteFilter] = useState("all");   // all | voted | unvoted
  const [period, setPeriod] = useState("24h");           // all | 24h | 7d | 30d | custom
  const [signedIn, setSignedIn] = useState(false);       // gate the vote UI on auth
  const [showIntro, setShowIntro] = useState(false);
  useEffect(() => { setShowIntro(typeof window !== "undefined" && localStorage.getItem("ds_intro_hidden") !== "1"); }, []);
  function dismissIntro() { localStorage.setItem("ds_intro_hidden", "1"); setShowIntro(false); }
  const [from, setFrom] = useState(""); const [to, setTo] = useState("");
  const [nonqual, setNonqual] = useState<any[]>([]);     // out / too_small / excluded
  const [openCats, setOpenCats] = useState<Record<string, boolean>>({}); // per-category fold (default collapsed)

  // Deep-link support (used by the daily email): ?window=24h|7d|30d pre-sets the date filter,
  // ?thesis=water|healthcare opens that lens — so the email links straight to deals that exist.
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const w = q.get("window");
    if (w && ["24h", "7d", "30d"].includes(w)) setPeriod(w);
    const t = q.get("thesis");
    if (t && ["water", "healthcare"].includes(t)) setThesis(t);
    api.me().then((d) => setSignedIn(!!d.email)).catch(() => setSignedIn(false));
  }, []);

  const [lastScan, setLastScan] = useState<string | null>(null);
  const [near, setNear] = useState<any[]>([]);   // on-thesis, doesn't clear the bar
  useEffect(() => {
    setLoading(true);
    Promise.all([api.board(thesis), api.runs(), api.votesList(),
                 api.board(thesis, "out,excluded,stale", 5000),
                 api.board(thesis, "near", 300)]).then(([b, r, vl, nq, nr]) => {
      setDeals(b.listings); setSpend(r.total_spend_usd); setNonqual(nq.listings); setNear(nr.listings);
      const scrapes = (r.runs || []).filter((x: any) => x.kind === "scrape");
      setLastScan(scrapes[0]?.started_at || null);
      const m: Record<number, string> = {};
      (vl.votes || []).forEach((x: any) => { if (x.thesis === thesis && !(x.listing_id in m)) m[x.listing_id] = x.verdict; });
      setVoted(m); setLoading(false);
    });
  }, [thesis]);

  async function cast(d: Deal, verdict: string) {
    try {
      if (voted[d.id] === verdict) {
        const status = await api.unvote(thesis, d.id);
        if (status === 200) setVoted((v) => { const n = { ...v }; delete n[d.id]; return n; });
        else if (status === 403) window.location.href = "/login";
        else alert("Couldn't update your vote — please try again.");
        return;
      }
      const status = await api.vote(thesis, d.id, verdict);
      if (status === 200) setVoted((v) => ({ ...v, [d.id]: verdict }));
      else if (status === 403) window.location.href = "/login";
      else alert("Couldn't record your vote — please try again.");
    } catch {
      alert("Network error — your vote didn't go through. Please try again.");
    }
  }

  // Quick-period window (days back from today), or explicit from/to in custom mode.
  const [lo, hi] = useMemo<[Date | null, Date | null]>(() => {
    if (period === "custom") return [parseDate(from), parseDate(to)];
    if (period !== "all") {
      const days = period === "24h" ? 1 : period === "7d" ? 7 : 30;
      const c = new Date(); c.setHours(0, 0, 0, 0); c.setDate(c.getDate() - (days - 1));
      return [c, null];
    }
    return [null, null];
  }, [period, from, to]);
  const dateOK = (s?: string) => {
    const dd = parseDate(s);
    if (lo && dd && dd < lo) return false;
    if (hi && dd && dd > hi) return false;
    return true;
  };

  // The vote filter only applies when signed in — its control is hidden otherwise, so a
  // stale "voted/unvoted" selection must never silently change the logged-out board.
  const effVoteFilter = signedIn ? voteFilter : "all";
  const filtered = useMemo(() => deals.filter((d: any) => {
    const isVoted = d.id in voted;
    if (effVoteFilter === "voted" && !isVoted) return false;
    if (effVoteFilter === "unvoted" && isVoted) return false;
    return dateOK(d.first_seen);
  }), [deals, voted, effVoteFilter, lo, hi]);

  const groups = [5, 4, 3, 2].map((c) => ({ c, items: filtered.filter((d) => d.relevance === c) })).filter((g) => g.items.length);

  // On-thesis but doesn't clear the bar (small / undisclosed financials / off-geo).
  const nearFiltered = useMemo(() => near.filter((d: any) => {
    const isVoted = d.id in voted;
    if (effVoteFilter === "voted" && !isVoted) return false;
    if (effVoteFilter === "unvoted" && isVoted) return false;
    return dateOK(d.first_seen);
  }), [near, voted, effVoteFilter, lo, hi]);

  // Non-qualifying deals (didn't pass keyword/size/exclusion), grouped by category.
  const nqGroups = useMemo(() => {
    const inWin = nonqual.filter((d: any) => dateOK(d.first_seen));
    const by: Record<string, any[]> = {};
    inWin.forEach((d: any) => { const c = d.category || "Other"; (by[c] ||= []).push(d); });
    return { total: inWin.length, cats: Object.entries(by).sort((a, b) => b[1].length - a[1].length) };
  }, [nonqual, lo, hi]);

  return (
    <main className="wrap">
      {showIntro && !signedIn && (
        <div className="intro">
          <span><b>DealScanner</b> aggregates business-for-sale listings from 200+ brokers into one thesis-filtered feed for searchers.
            This is the <b>{LABEL[thesis]}</b> board — new deals that clear that thesis. <a href="/help">How it works →</a></span>
          <button className="intro-x" onClick={dismissIntro} aria-label="Dismiss">✕</button>
        </div>
      )}
      <div className="boardhead">
        <h1 className="h1">{LABEL[thesis]} deals</h1>
        <p className="sub">New businesses that match your acquisition thesis, ranked by fit and refreshed daily. Switch thesis to re-score the same listings.</p>
        <div className="toolbar">
          <div className="lens" role="group" aria-label="Thesis">
            {["water", "healthcare"].map((t) => (
              <button key={t} className={t} aria-pressed={thesis === t} onClick={() => setThesis(t)}>
                <span className="dot" />{LABEL[t]}
              </button>
            ))}
          </div>
          <div className="filterbar">
            {signedIn && (
              <select className="votedrop" aria-label="Vote filter" value={voteFilter} onChange={(e) => setVoteFilter(e.target.value)}>
                <option value="all">All deals</option>
                <option value="voted">Voted</option>
                <option value="unvoted">Not voted</option>
              </select>
            )}
            <div className="seg" role="group" aria-label="Scraped window">
              {[["all", "All time"], ["24h", "24h"], ["7d", "7d"], ["30d", "30d"]].map(([k, lbl]) => (
                <button key={k} aria-pressed={period === k} onClick={() => setPeriod(k)}>{lbl}</button>
              ))}
              <button className="custombtn" aria-pressed={period === "custom"} onClick={() => setPeriod(period === "custom" ? "all" : "custom")}>Custom ▾</button>
            </div>
            {period === "custom" && (
              <div className="daterange">
                <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
                <span>–</span>
                <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
                {(from || to) && <button className="clearbtn" onClick={() => { setFrom(""); setTo(""); }}>×</button>}
              </div>
            )}
          </div>
        </div>
        <div className="cost"><b>{loading ? "…" : filtered.length}</b>{!loading && filtered.length !== deals.length ? ` of ${deals.length}` : ""} qualifying{lastScan ? ` · last scan ${fmtDate(lastScan)}` : ""}</div>
      </div>

      {loading && <p className="note">Loading deals…</p>}
      {!loading && filtered.length === 0 && nearFiltered.length === 0 && (
        <div className="panel note">
          The scan ran{lastScan ? ` (last: ${fmtDate(lastScan)})` : ""} — nothing in the {LABEL[thesis]} category in this window.
          Widen the date range above, or adjust the keywords and size band under Thesis.
        </div>
      )}
      {!loading && filtered.length === 0 && nearFiltered.length > 0 && (
        <div className="panel note">
          No perfect-fit deals in this window, but {nearFiltered.length} on-thesis {nearFiltered.length === 1 ? "deal is" : "deals are"} below —
          worth a look even though the financials or size don’t fully clear the bar.
        </div>
      )}

      {groups.length > 0 && (
        <div className="tierlabel">Qualifying <span>— clears your thesis and size band</span></div>
      )}
      {groups.map((g) => (
        <section key={g.c}>
          <div className="section-head">
            <h3>Confidence {g.c}/5</h3><span className="n">({g.items.length})</span>
          </div>
          {g.items.map((d: any) => (
            <DealCard key={d.id} d={d} signedIn={signedIn} voted={voted[d.id]} onVote={(v) => cast(d, v)} />
          ))}
        </section>
      ))}

      {!loading && nearFiltered.length > 0 && (
        <section>
          <div className="tierlabel">In the {LABEL[thesis]} category <span>— on-thesis, but small, undisclosed financials, or outside the size band</span></div>
          {nearFiltered.map((d: any) => (
            <DealCard key={d.id} d={d} signedIn={signedIn} voted={voted[d.id]} onVote={(v) => cast(d, v)} />
          ))}
        </section>
      )}

      {!loading && nqGroups.total > 0 && (
        <section className="nqwrap">
          <div className="nqhead">
            <b>Out of scope</b>
            <span className="n">{nqGroups.total}</span>
            <span className="nqhint">scraped but not in the {LABEL[thesis]} category — filtered out by keywords or exclusions{period !== "all" ? " · this window" : ""} — open a category to see them</span>
          </div>
          <div className="nqbody">
            {nqGroups.cats.map(([cat, items]) => {
              const open = openCats[cat];
              return (
                <div className="nqcat" key={cat}>
                  <button className="nqcathead" aria-expanded={!!open}
                    onClick={() => setOpenCats((o) => ({ ...o, [cat]: !o[cat] }))}>
                    <span className="chev">{open ? "▾" : "▸"}</span>
                    <span className={`cat ${CAT_CLASS[cat] || "c-gray"}`}>{cat}</span>
                    <span className="n">{items.length}</span>
                  </button>
                  {open && (
                    <ul className="nqlist">
                      {items.map((d: any) => (
                        <li key={d.id}>
                          <span className="nqname">{d.business_name}</span>
                          <span className="nqdash"> — </span>
                          <a href={safeHref(d.listing_url)} target="_blank" rel="noreferrer">{d.broker || "view listing"}</a>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      )}
    </main>
  );
}
