"use client";
import { useEffect, useMemo, useState } from "react";
import { api, Deal } from "@/lib/api";

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
  const [period, setPeriod] = useState("all");           // all | 24h | 7d | 30d | custom
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
  }, []);

  useEffect(() => {
    setLoading(true);
    Promise.all([api.board(thesis), api.runs(), api.votesList(),
                 api.board(thesis, "out,too_small,excluded", 5000)]).then(([b, r, vl, nq]) => {
      setDeals(b.listings); setSpend(r.total_spend_usd); setNonqual(nq.listings);
      const m: Record<number, string> = {};
      (vl.votes || []).forEach((x: any) => { if (x.thesis === thesis && !(x.listing_id in m)) m[x.listing_id] = x.verdict; });
      setVoted(m); setLoading(false);
    });
  }, [thesis]);

  async function cast(d: Deal, verdict: string) {
    if (voted[d.id] === verdict) {
      const status = await api.unvote(thesis, d.id);
      if (status === 200) setVoted((v) => { const n = { ...v }; delete n[d.id]; return n; });
      else if (status === 403) window.location.href = "/login";
      return;
    }
    const status = await api.vote(thesis, d.id, verdict);
    if (status === 200) setVoted((v) => ({ ...v, [d.id]: verdict }));
    else if (status === 403) window.location.href = "/login";
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

  const filtered = useMemo(() => deals.filter((d: any) => {
    const isVoted = d.id in voted;
    if (voteFilter === "voted" && !isVoted) return false;
    if (voteFilter === "unvoted" && isVoted) return false;
    return dateOK(d.first_seen);
  }), [deals, voted, voteFilter, lo, hi]);

  const groups = [5, 4, 3, 2].map((c) => ({ c, items: filtered.filter((d) => d.relevance === c) })).filter((g) => g.items.length);

  // Non-qualifying deals (didn't pass keyword/size/exclusion), grouped by category.
  const nqGroups = useMemo(() => {
    const inWin = nonqual.filter((d: any) => dateOK(d.first_seen));
    const by: Record<string, any[]> = {};
    inWin.forEach((d: any) => { const c = d.category || "Other"; (by[c] ||= []).push(d); });
    return { total: inWin.length, cats: Object.entries(by).sort((a, b) => b[1].length - a[1].length) };
  }, [nonqual, lo, hi]);

  return (
    <main className="wrap">
      <div className="boardhead">
        <h1 className="h1">{LABEL[thesis]} deals</h1>
        <p className="sub">One engine, your thesis. Every deal is scored from the same shared database — switch the lens to see the other thesis re-rank from identical data.</p>
        <div className="toolbar">
          <div className="lens" role="group" aria-label="Thesis">
            {["water", "healthcare"].map((t) => (
              <button key={t} className={t} aria-pressed={thesis === t} onClick={() => setThesis(t)}>
                <span className="dot" />{LABEL[t]}
              </button>
            ))}
          </div>
          <div className="filterbar">
            <select className="votedrop" aria-label="Vote filter" value={voteFilter} onChange={(e) => setVoteFilter(e.target.value)}>
              <option value="all">All deals</option>
              <option value="voted">Voted</option>
              <option value="unvoted">Not voted</option>
            </select>
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
        <div className="cost"><b>{loading ? "…" : filtered.length}</b>{!loading && filtered.length !== deals.length ? ` of ${deals.length}` : ""} qualifying · <b>${spend.toFixed(4)}</b> engine spend</div>
      </div>

      {loading && <p className="note">Loading deals…</p>}
      {!loading && filtered.length === 0 && (
        <div className="panel note">No deals match. Loosen the filters above, or the keywords / size band in Thesis setup.</div>
      )}

      {groups.map((g) => (
        <section key={g.c}>
          <div className="section-head">
            <h3>Confidence {g.c}/5</h3><span className="n">({g.items.length})</span>
          </div>
          {g.items.map((d: any) => (
            <article className="deal" key={d.id}>
              <div className="content">
                <div className="deal-top">
                  <span className={`tierdot ${d.tier}`}>{d.tier}</span>
                  <span className="deal-name">{d.business_name}</span>
                </div>
                <div className="meta">
                  {d.category && <span className={`cat ${CAT_CLASS[d.category] || "c-gray"}`}>{d.category}</span>}
                  {(d.city || d.state) && <span className="geo">{[d.city, d.state].filter(Boolean).join(", ")}</span>}
                  {d.first_seen && <span className="spotted">scraped {fmtDate(d.first_seen)}</span>}
                </div>
                {d.one_line_take && <p className="blurb">{d.one_line_take}</p>}
                {d.matched_keywords && (
                  <div className="kw"><b>Keywords:</b> {d.matched_keywords.split(",").map((k: string) => k.trim()).filter(Boolean).join(" · ")}</div>
                )}
                {(d.positive_flags?.length || d.negative_flags?.length) ? (
                  <div className="flags">
                    {(d.positive_flags || []).map((f: string) => <span key={f} className="gf">✓ {FLAG_LABEL[f] || f}</span>)}
                    {(d.negative_flags || []).map((f: string) => <span key={f} className="rf">⚠ {FLAG_LABEL[f] || f}</span>)}
                  </div>
                ) : null}
                <div className="dealfoot">
                  <span className="broker">{d.broker}</span>
                  <a className="viewlink" href={d.listing_url} target="_blank" rel="noreferrer">view listing ↗</a>
                </div>
              </div>
              <div className="fincol num">
                <div className="fin"><span>Rev</span><b>{fmtM(d.revenue)}</b></div>
                <div className="fin"><span>EBITDA</span><b>{fmtM(d.ebitda)}</b></div>
                <div className="fin"><span>SDE</span><b>{fmtM(d.sde)}</b></div>
                <div className="fin"><span>Ask</span><b>{fmtM(d.asking_price)}</b></div>
                <div className="fin"><span>Mult</span><b>{d.multiple ? `${d.multiple}x` : "—"}</b></div>
              </div>
              <div className="votecol">
                {["yes", "maybe", "no"].map((v) => (
                  <button key={v} className={`${v} ${voted[d.id] === v ? "on" : ""}`} onClick={() => cast(d, v)}>{v}</button>
                ))}
              </div>
            </article>
          ))}
        </section>
      ))}

      {!loading && nqGroups.total > 0 && (
        <section className="nqwrap">
          <div className="nqhead">
            <b>Didn’t qualify</b>
            <span className="n">{nqGroups.total}</span>
            <span className="nqhint">scored from the same scrape but filtered out by keywords, size or exclusions{period !== "all" ? " · this window" : ""} — open a category to see them</span>
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
                          <a href={d.listing_url} target="_blank" rel="noreferrer">{d.broker || "view listing"}</a>
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
