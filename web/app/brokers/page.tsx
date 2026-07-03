"use client";
import { useEffect, useMemo, useState } from "react";
import { api, safeHref } from "@/lib/api";

type Row = { broker: string; url: string; status: string; total: number; last30: number; days_since: number; health: string; week: string[]; block_count?: number; last_blocked_at?: string | null };
const HEALTH_RANK: Record<string, number> = { active: 0, inactive: 1, degraded: 2, pending: 3 };

export default function Brokers() {
  const [live, setLive] = useState<Row[]>([]);
  const [archived, setArchived] = useState<Row[]>([]);
  const [sort, setSort] = useState<{ k: string; dir: number }>({ k: "total", dir: -1 });
  const [name, setName] = useState(""); const [url, setUrl] = useState("");
  const [editMode, setEditMode] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [eName, setEName] = useState(""); const [eUrl, setEUrl] = useState("");

  function load() { api.brokers().then((d) => { setLive(d.brokers); setArchived(d.archived || []); }); }
  useEffect(() => { load(); }, []);

  const sorted = useMemo(() => {
    const r = [...live]; const { k, dir } = sort;
    r.sort((a: any, b: any) => {
      let av = a[k], bv = b[k];
      if (k === "health") { av = HEALTH_RANK[a.health]; bv = HEALTH_RANK[b.health]; }
      if (typeof av === "string") return av.localeCompare(bv) * dir;
      return (av - bv) * dir;
    });
    return r;
  }, [live, sort]);

  const th = (k: string, label: string, cls = "") => (
    <th className={cls} onClick={() => setSort((s) => ({ k, dir: s.k === k ? -s.dir : (k === "broker" ? 1 : -1) }))}>
      {label}{sort.k === k && <span className="arrow"> {sort.dir === 1 ? "▲" : "▼"}</span>}
    </th>
  );
  const seen = (d: number) => d < 0 ? "no data" : d === 0 ? "today" : `${d}d ago`;
  const guard = (code: number) => { if (code === 403) location.href = "/login"; };

  async function addBroker(e: React.FormEvent) {
    e.preventDefault(); if (!name.trim()) return;
    const code = await api.brokerAdd(name.trim(), url.trim()); guard(code);
    if (code === 200) { setName(""); setUrl(""); load(); }
  }
  async function setStatus(broker: string, status: string) {
    const code = await api.brokerStatus(broker, status); guard(code); if (code === 200) load();
  }
  function startEdit(r: Row) { setEditing(r.broker); setEName(r.broker); setEUrl(r.url || ""); }
  async function saveEdit() {
    if (!editing) return;
    const code = await api.brokerEdit(editing, eName.trim(), eUrl.trim());
    if (code === 409) { alert("A broker with that name already exists."); return; }
    guard(code); if (code === 200) { setEditing(null); load(); }
  }

  function NameCell({ r }: { r: Row }) {
    if (editMode && editing === r.broker) {
      return (
        <span className="editcell">
          <input value={eName} onChange={(e) => setEName(e.target.value)} placeholder="Name" />
          <input value={eUrl} onChange={(e) => setEUrl(e.target.value)} placeholder="https://site.com" />
          <button className="miniact" onClick={saveEdit}>Save</button>
          <button className="miniact" onClick={() => setEditing(null)}>✕</button>
        </span>
      );
    }
    return (
      <>
        <span className={`bname ${editMode ? "editable" : ""}`} title={editMode ? "Click to edit" : r.broker}
          onClick={() => editMode && startEdit(r)}>{r.broker}</span>
        {r.url && !editMode && <a className="exticon" href={safeHref(r.url)} target="_blank" rel="noreferrer" title="Open broker site">↗</a>}
        {!!r.block_count && r.block_count > 0 && (
          <span className="blocktag" title={`Firecrawl couldn't load this broker's pages ${r.block_count}× (last ${(r.last_blocked_at || "").slice(0, 10)}). Likely unscrapeable long-term.`}>
            ⛔ blocked ×{r.block_count}
          </span>
        )}
      </>
    );
  }

  const RowEl = (r: Row, isArch = false) => (
    <tr key={r.broker}>
      <td><NameCell r={r} /></td>
      <td><span className={`hdot ${r.health}`}>{r.health}</span></td>
      <td className="num">{r.total}</td>
      <td className="num">{r.last30}</td>
      <td className="num">{seen(r.days_since)}</td>
      <td><span className="strip">{(r.week || []).map((c, i) => {
        const daysAgo = 6 - i;
        const meaning = c === "g" ? "ran — new listings" : c === "x" ? "ran — nothing new"
          : c === "e" ? "scrape error / blocked" : "no scan / not added yet";
        const when = daysAgo === 0 ? "today" : daysAgo === 1 ? "yesterday" : `${daysAgo} days ago`;
        return <i key={i} className={`${c}${i === 6 ? " today" : ""}`} title={`${when}: ${meaning}`} />;
      })}</span></td>
      <td className="num">
        {isArch ? <button className="miniact" onClick={() => setStatus(r.broker, "live")}>Restore</button>
          : <button className="miniact" onClick={() => setStatus(r.broker, "archived")}>Archive</button>}
      </td>
    </tr>
  );

  return (
    <main className="wrap" style={{ maxWidth: 1080 }}>
      <h1 className="h1">Broker quality</h1>
      <p className="sub" style={{ maxWidth: "none", marginBottom: 16 }}>
        Every source we scrape, how much it has produced, and whether it has gone quiet. Add new brokers for the next
        scrape, archive the ones that aren&apos;t earning their keep, and turn on edit mode to fix a name or link.
        Click any column header to sort.
      </p>

      <form className="panel addform" onSubmit={addBroker}>
        <div className="field"><label>Add a broker for the next scrape</label>
          <input type="text" placeholder="Broker name" value={name} onChange={(e) => setName(e.target.value)} /></div>
        <div className="field"><label>&nbsp;</label>
          <input type="text" placeholder="https://broker-site.com/listings" value={url} onChange={(e) => setUrl(e.target.value)} /></div>
        <button className="btn" type="submit">Add</button>
      </form>

      <div className="legend">
        <span><b>Health:</b>&nbsp;
          <b style={{ color: "var(--good)" }}>● active</b> new in last 7d ·
          <b style={{ color: "var(--amber)" }}>● inactive</b> 8–30d ago ·
          <b style={{ color: "var(--red)" }}>● degraded</b> 30d+</span>
        <span><b>7-day activity</b> — left = 7 days ago, right (outlined) = today:&nbsp;
          <i className="lg g" /> ran, new listings ·
          <i className="lg x" /> ran, nothing new ·
          <i className="lg n" /> no scan / not added yet ·
          <i className="lg e" /> scrape error or blocked</span>
        <span><b style={{ color: "#b91c1c" }}>⛔ blocked ×N</b> — the broker&apos;s site returned a bot-block N times, so new
          listings couldn&apos;t be fetched those days. Earlier listings you already have from them are unaffected.</span>
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
        <button className={editMode ? "btn" : "miniact"} onClick={() => { setEditMode(!editMode); setEditing(null); }}>
          {editMode ? "Done editing" : "Edit names & links"}
        </button>
      </div>

      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <table className="table btable">
          <thead><tr>
            {th("broker", "Broker")}{th("health", "Health")}{th("total", "Listings", "num")}
            {th("last30", "30d", "num")}{th("days_since", "Last seen", "num")}
            <th className="striphead">7-day activity <span className="dir">old → today</span></th><th></th>
          </tr></thead>
          <tbody>{sorted.map((r) => RowEl(r))}</tbody>
        </table>
      </div>

      {archived.length > 0 && (<>
        <h2 className="card-title" style={{ marginTop: 30, fontSize: 16 }}>Archived sources <span className="note">({archived.length}) — skipped on scrapes; restore any to go live again</span></h2>
        <div className="panel" style={{ padding: 0, overflow: "hidden", opacity: .85 }}>
          <table className="table btable">
            <thead><tr><th>Broker</th><th>Health</th><th className="num">Listings</th><th className="num">30d</th><th className="num">Last seen</th><th>Last 7 days</th><th></th></tr></thead>
            <tbody>{archived.map((r) => RowEl(r, true))}</tbody>
          </table>
        </div>
      </>)}
    </main>
  );
}
