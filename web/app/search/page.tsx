"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, safeHref } from "@/lib/api";
import { CAT_CLASS, catShort, fmtM, parseDate } from "@/lib/deal";
import DealCard from "../DealCard";

const LABEL: Record<string, string> = { water: "Water / Wastewater", healthcare: "Healthcare" };
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
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<1 | -1>(1);

  // detail modal
  const [openId, setOpenId] = useState<number | null>(null);
  const [detail, setDetail] = useState<any>(null);
  const [signedIn, setSignedIn] = useState(false);
  const [votes, setVotes] = useState<Record<string, string>>({});   // `${thesis}:${id}` -> verdict
  const modalRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLElement | null>(null);

  // Modal keyboard: ESC to close, focus into the dialog on open, trap Tab, restore focus on close.
  useEffect(() => {
    if (openId == null) return;
    const el = modalRef.current;
    (el?.querySelector<HTMLElement>("[data-autofocus]") || el)?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") { setOpenId(null); return; }
      if (e.key === "Tab" && el) {
        const f = Array.from(el.querySelectorAll<HTMLElement>(
          'button, a[href], input, [tabindex]:not([tabindex="-1"])')).filter((n) => n.offsetParent !== null);
        if (!f.length) return;
        const first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    }
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); triggerRef.current?.focus(); };
  }, [openId]);

  useEffect(() => {
    api.me().then((d) => setSignedIn(!!d.email)).catch(() => setSignedIn(false));
    loadVotes();
  }, []);
  function loadVotes() {
    api.votesList().then((d) => {
      const m: Record<string, string> = {};
      (d.votes || []).forEach((v: any) => { const k = `${v.thesis}:${v.listing_id}`; if (!(k in m)) m[k] = v.verdict; });
      setVotes(m);
    }).catch(() => {});
  }

  useEffect(() => {
    if (openId == null) { setDetail(null); return; }
    setDetail(null);
    api.listing(openId).then(setDetail).catch(() => setDetail(null));
  }, [openId]);

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
  async function vote(v: string) {
    if (openId == null || !detail) return;
    const acct = detail.vote_account || "water";
    const k = `${acct}:${openId}`;
    try {
      const status = votes[k] === v ? await api.unvote(acct, openId) : await api.vote(acct, openId, v);
      if (status === 403) { location.href = "/login"; return; }
      if (status === 200) setVotes((m) => { const n = { ...m }; if (votes[k] === v) delete n[k]; else n[k] = v; return n; });
      else alert("Couldn't record your vote — please try again.");
    } catch {
      alert("Network error — your vote didn't go through. Please try again.");
    }
  }

  const rows = useMemo(() => {
    if (!res) return [];
    if (!sortKey) return res;
    const col = COLS.find((c) => c.key === sortKey)!;
    const arr = [...res];
    arr.sort((a, b) => {
      const va = col.get(a), vb = col.get(b);
      if (col.type === "num") return ((va == null ? -Infinity : va) - (vb == null ? -Infinity : vb)) * sortDir;
      if (col.type === "date") return (((parseDate(va)?.getTime() ?? -Infinity) - (parseDate(vb)?.getTime() ?? -Infinity))) * sortDir;
      return String(va).localeCompare(String(vb)) * sortDir;
    });
    return arr;
  }, [res, sortKey, sortDir]);

  return (
    <main className="wrap">
      <div className="boardhead">
        <h1 className="h1">Search</h1>
        <p className="sub">Search every listing by name, description, category, or broker. Click any column header to sort, or a business name for the full deal card.</p>
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
                    aria-sort={sortKey === c.key ? (sortDir === 1 ? "ascending" : "descending") : "none"}>
                    <button className="sortbtn" onClick={() => clickSort(c.key)}>
                      {c.label}<span className="arrow">{sortKey === c.key ? (sortDir === 1 ? " ▲" : " ▼") : ""}</span>
                    </button>
                  </th>
                ))}
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r: any) => (
                <tr key={r.id}>
                  <td>{r.category && <span className={`cat ${CAT_CLASS[r.category] || "c-gray"}`}>{catShort(r.category)}</span>}</td>
                  <td><button className="linkname capcell wide" title={r.business_name} onClick={(e) => { triggerRef.current = e.currentTarget; setOpenId(r.id); }}>{r.business_name}</button></td>
                  <td className="muted"><span className="capcell loc" title={loc(r)}>{loc(r) || "—"}</span></td>
                  <td className="muted"><span className="capcell narrow" title={r.broker}>{r.broker}</span></td>
                  <td className="r">{fmtM(r.revenue)}</td>
                  <td className="r">{fmtM(r.ebitda)}</td>
                  <td className="r">{fmtM(r.sde)}</td>
                  <td className="r">{fmtM(r.asking_price)}</td>
                  <td className="r muted nowrap">{fmtMD(r.first_seen)}</td>
                  <td><a className="viewlink" href={safeHref(r.listing_url)} target="_blank" rel="noreferrer" aria-label="Open listing">↗</a></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {openId != null && (
        <div className="modal-overlay" onClick={() => setOpenId(null)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Deal details"
            ref={modalRef} tabIndex={-1} onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <span className="matches">
                {detail && (detail.relevant_theses?.length
                  ? <>Matches: {detail.relevant_theses.map((t: string) => LABEL[t] || t).join(", ")}</>
                  : "Not currently matching a thesis")}
              </span>
              <button className="modal-x" data-autofocus onClick={() => setOpenId(null)} aria-label="Close">✕</button>
            </div>
            {!detail ? <p className="note" style={{ padding: 20 }}>Loading…</p> : (
              <DealCard d={detail} signedIn={signedIn} voted={votes[`${detail.vote_account}:${openId}`]} onVote={vote} />
            )}
          </div>
        </div>
      )}
    </main>
  );
}
