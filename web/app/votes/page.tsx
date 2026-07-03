"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const ORDER = ["yes", "maybe", "no"];
const TITLE: Record<string, string> = { yes: "Yes — chase it", maybe: "Maybe — worth a look", no: "No — pass" };

export default function Voting() {
  const [d, setD] = useState<any>(null);
  const [drag, setDrag] = useState<any>(null);
  const [over, setOver] = useState<string | null>(null);
  function load() { api.votesList().then(setD); }
  useEffect(() => { load(); }, []);

  async function drop(target: string) {
    setOver(null);
    const item = drag; setDrag(null);
    if (!item || item.verdict === target) return;
    const code = await api.recategorize(item.thesis, item.listing_id, target);
    if (code === 403) { location.href = "/login"; return; }
    if (code === 200) load();
  }

  return (
    <main className="wrap" style={{ maxWidth: 820 }}>
      <h1 className="h1">Voting</h1>
      <p className="sub" style={{ marginBottom: 16 }}>
        Every verdict you and Alex cast, captured with the full deal context at vote time. Drag a deal between
        sections to re-categorize it — this is the record the future instinct model will learn from.
      </p>

      {d && (
        <>
          <div className="bigstat"><b>{d.total}</b><span>deals voted so far</span></div>
          {ORDER.map((v) => {
            const items = (d.votes || []).filter((x: any) => x.verdict === v);
            return (
              <div key={v} style={{ marginBottom: 22 }}>
                <h2 style={{ display: "flex", alignItems: "center", gap: 8, margin: "0 0 8px", fontSize: 15, fontWeight: 700 }}>
                  <span className={`vchip ${v}`}>{v}</span> {TITLE[v]} <span className="note" style={{ fontWeight: 400 }}>· {items.length}</span>
                </h2>
                <div className="panel" style={{ transition: "border-color .12s, background .12s",
                  ...(over === v ? { borderColor: "var(--blue)", background: "var(--blue-soft)" } : {}) }}
                  onDragOver={(e) => { e.preventDefault(); setOver(v); }}
                  onDragLeave={() => setOver((o) => (o === v ? null : o))}
                  onDrop={() => drop(v)}>
                  {items.length === 0 && <p className="note" style={{ margin: 0 }}>Drag deals here.</p>}
                  {items.map((x: any) => (
                    <div className="vrow" key={String(x.listing_id) + x.operator} draggable
                      style={{ cursor: "grab" }}
                      onDragStart={() => setDrag({ listing_id: x.listing_id, thesis: x.thesis, verdict: v })}
                      onDragEnd={() => setOver(null)}>
                      <span style={{ color: "var(--faint)", letterSpacing: "-2px", fontSize: 14 }}>⋮⋮</span>
                      <span className="vchip" style={{ background: "var(--blue-soft)", color: "var(--blue-ink)" }}>{x.thesis}</span>
                      <span className="vname">
                        {x.listing_url ? <a draggable={false} href={x.listing_url} target="_blank" rel="noreferrer">{x.business_name}</a> : x.business_name}
                      </span>
                      <span className="vmeta">{x.operator?.split("@")[0]} · {(x.created_at || "").slice(0, 10)}</span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </>
      )}
    </main>
  );
}
