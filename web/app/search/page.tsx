"use client";
import { useMemo, useState } from "react";
import { api, safeHref } from "@/lib/api";

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
// Year dropped — every listing is the current year.
const fmtMD = (s?: string) => {
  const d = parseDate(s);
  return d ? `${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}` : "—";
};
const loc = (r: any) => [r.city, r.state].filter(Boolean).join(", ");

type SortType = "text" | "num" | "date";
const COLS: { key: string; label: string; type: SortType; align?: "r"; get: (r: any) => any }[] = [
  { key: "category", label: "Category", type: "text", get: (r) => r.category || "" },
  { key: "business_name", label: "Business", type: "text", get: (r) => r.business_name || "" },
  { key: "location", label: "Location", type: "text", get: (r) => loc(r) },
  { key: "broker", label: "Broker", type: "text", get: (r) => r.broker || "" },
  { key: "revenue", label: "Rev", type: "num", align: "r", get: (r) => r.revenue },
  { key: "ebitda", label: "EBITDA", type: "num", align: "r", get: (r) => r.ebitda },
  { key: "sde", label: "SDE", type: "num", align: "r", get: (r) => r.sde },
  { key: "asking_price", label: "Ask", type: "num", align: "r", get: (r) => r.asking_price },
  { key: "first_seen", label: "Scraped", type: "date", align: "r", get: (r) => r.first_seen },
];

export default function Search() {
  const [q, setQ] = useState("");
  const [res, setRes] = useState<any[] | null>(null);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [sortKey, setSortKey] = useState<string | null>(null);  // null = server "best match" order
  const [sortDir, setSortDir] = useState<1 | -1>(1);

  async function run(query = q) {
    if (!query.trim()) { setRes(null); return; }
    setLoading(true);
    const d = await api.search(query.trim(), "accuracy");
    setRes(d.results); setCount(d.count); setSortKey(null); setLoading(false);
  }

  function clickSort(key: string) {
    if (sortKey === key) setSortDir((d) => (d === 1 ? -1 : 1));
    else { setSortKey(key); setSortDir(1); }
  }

  const rows = useMemo(() => {
    if (!res) return [];
    if (!sortKey) return res;
    const col = COLS.find((c) => c.key === sortKey)!;
    const arr = [...res];
    arr.sort((a, b) => {
      const va = col.get(a), vb = col.get(b);
      if (col.type === "num") {
        const na = va == null ? -Infinity : va, nb = vb == null ? -Infinity : vb;
        return (na - nb) * sortDir;
      }
      if (col.type === "date") {
        const da = parseDate(va)?.getTime() ?? -Infinity, db = parseDate(vb)?.getTime() ?? -Infinity;
        return (da - db) * sortDir;
      }
      return String(va).localeCompare(String(vb)) * sortDir;
    });
    return arr;
  }, [res, sortKey, sortDir]);

  return (
    <main className="wrap">
      <div className="boardhead">
        <h1 className="h1">Search</h1>
        <p className="sub">Search every listing by name, description, category, or broker. Click any column header to sort.</p>
        <div className="searchbar">
          <input className="searchinput" placeholder="e.g. HVAC distributor, dental, recurring revenue…"
            value={q} onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()} autoFocus />
          <button className="signin" style={{ marginLeft: 0 }} onClick={() => run()}>Search</button>
        </div>
        {res !== null && <div className="cost" style={{ textAlign: "left" }}><b>{count}</b> result{count === 1 ? "" : "s"}{count > res.length ? ` (showing ${res.length})` : ""}</div>}
      </div>

      {loading && <p className="note">Searching…</p>}
      {res !== null && !loading && res.length === 0 && (
        <div className="panel note">No listings match. Try fewer or different keywords.</div>
      )}

      {res && res.length > 0 && (
        <div className="panel" style={{ padding: 0, overflowX: "auto" }}>
          <table className="dbtable sortable">
            <thead>
              <tr>
                {COLS.map((c) => (
                  <th key={c.key} className={`${c.align === "r" ? "r " : ""}sorth${sortKey === c.key ? " on" : ""}`}
                    onClick={() => clickSort(c.key)} title="Click to sort">
                    {c.label}<span className="arrow">{sortKey === c.key ? (sortDir === 1 ? " ▲" : " ▼") : ""}</span>
                  </th>
                ))}
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r: any) => (
                <tr key={r.id}>
                  <td>{r.category && <span className={`cat ${CAT_CLASS[r.category] || "c-gray"}`}>{r.category}</span>}</td>
                  <td><span className="capcell wide" title={r.business_name}>{r.business_name}</span></td>
                  <td className="muted"><span className="capcell narrow" title={loc(r)}>{loc(r) || "—"}</span></td>
                  <td className="muted"><span className="capcell narrow" title={r.broker}>{r.broker}</span></td>
                  <td className="r">{fmtM(r.revenue)}</td>
                  <td className="r">{fmtM(r.ebitda)}</td>
                  <td className="r">{fmtM(r.sde)}</td>
                  <td className="r">{fmtM(r.asking_price)}</td>
                  <td className="r muted nowrap">{fmtMD(r.first_seen)}</td>
                  <td><a className="viewlink" href={safeHref(r.listing_url)} target="_blank" rel="noreferrer">↗</a></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
