"use client";
import { useState } from "react";
import { api } from "@/lib/api";

const CAT_CLASS: Record<string, string> = {
  "Healthcare": "c-teal", "Restaurant & Food": "c-pink", "Construction & Trades": "c-amber",
  "Manufacturing": "c-purple", "Retail & E-commerce": "c-rose", "Professional Services": "c-blue",
  "Personal Care & Fitness": "c-green", "Real Estate & Property": "c-slate",
  "Distribution & Wholesale": "c-indigo", "Auto & Transport": "c-orange",
  "Education & Childcare": "c-cyan", "Cleaning & Facilities": "c-lime",
  "Hospitality & Lodging": "c-brown", "Other": "c-gray",
};
const fmtM = (v?: number | null) => (v == null ? "—" : `$${(v / 1e6).toFixed(1)}M`);
function parseDate(s?: string): Date | null {
  if (!s) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
}
const fmtDate = (s?: string) => {
  const d = parseDate(s);
  if (!d) return "—";
  return `${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}-${d.getFullYear()}`;
};

const SORTS: [string, string][] = [
  ["accuracy", "Best match"], ["date_desc", "Newest first"], ["date_asc", "Oldest first"],
  ["revenue", "Revenue (high→low)"], ["ebitda", "EBITDA (high→low)"],
];

export default function Search() {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState("accuracy");
  const [res, setRes] = useState<any[] | null>(null);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(false);

  async function run(query = q, s = sort) {
    if (!query.trim()) { setRes(null); return; }
    setLoading(true);
    const d = await api.search(query.trim(), s);
    setRes(d.results); setCount(d.count); setLoading(false);
  }

  return (
    <main className="wrap">
      <div className="boardhead">
        <h1 className="h1">Search</h1>
        <p className="sub">Free-text search across every listing — name, description, category, broker. Type keywords and sort the results.</p>
        <div className="searchbar">
          <input className="searchinput" placeholder="e.g. HVAC distributor, dental, recurring revenue…"
            value={q} onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()} autoFocus />
          <select className="votedrop" value={sort} onChange={(e) => { setSort(e.target.value); run(q, e.target.value); }}>
            {SORTS.map(([k, lbl]) => <option key={k} value={k}>{lbl}</option>)}
          </select>
          <button className="signin" style={{ marginLeft: 0 }} onClick={() => run()}>Search</button>
        </div>
        {res !== null && <div className="cost" style={{ textAlign: "left" }}><b>{count}</b> result{count === 1 ? "" : "s"}{count > res.length ? ` (showing ${res.length})` : ""}</div>}
      </div>

      {loading && <p className="note">Searching…</p>}
      {res !== null && !loading && res.length === 0 && (
        <div className="panel note">No listings match. Try fewer or different keywords.</div>
      )}

      {res && res.length > 0 && (
        <div className="panel" style={{ padding: 0 }}>
          <table className="dbtable">
            <thead><tr><th>Business</th><th>Broker</th><th className="r">Rev</th><th className="r">EBITDA</th><th className="r">SDE</th><th className="r">Ask</th><th>Scraped</th><th></th></tr></thead>
            <tbody>
              {res.map((r: any) => (
                <tr key={r.id}>
                  <td>
                    <span className="dbname">{r.business_name}</span>
                    {r.category && <span className={`cat ${CAT_CLASS[r.category] || "c-gray"}`}>{r.category}</span>}
                    {(r.city || r.state) && <span className="geo" style={{ marginLeft: 6 }}>{[r.city, r.state].filter(Boolean).join(", ")}</span>}
                  </td>
                  <td className="muted">{r.broker}</td>
                  <td className="r">{fmtM(r.revenue)}</td>
                  <td className="r">{fmtM(r.ebitda)}</td>
                  <td className="r">{fmtM(r.sde)}</td>
                  <td className="r">{fmtM(r.asking_price)}</td>
                  <td className="muted">{fmtDate(r.first_seen)}</td>
                  <td><a className="viewlink" href={r.listing_url} target="_blank" rel="noreferrer">↗</a></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
