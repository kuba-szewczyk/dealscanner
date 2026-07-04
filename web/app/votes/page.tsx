"use client";
import { useEffect, useMemo, useState } from "react";
import { api, safeHref } from "@/lib/api";

const ORDER = ["yes", "maybe", "no"];
const TITLE: Record<string, string> = { yes: "Yes — chase it", maybe: "Maybe — worth a look", no: "No — pass" };
const LABEL: Record<string, string> = { water: "Water / Wastewater", healthcare: "Healthcare" };
const PERIODS: [string, string][] = [["all", "All time"], ["24h", "24h"], ["7d", "7d"], ["30d", "30d"]];

function withinWindow(iso: string, period: string): boolean {
  if (period === "all") return true;
  const t = Date.parse(iso);
  if (isNaN(t)) return true;
  const days = period === "24h" ? 1 : period === "7d" ? 7 : 30;
  return t >= Date.now() - days * 864e5;
}

export default function Shortlist() {
  const [d, setD] = useState<any>(null);
  const [thesis, setThesis] = useState("water");
  const [period, setPeriod] = useState("all");
  const [drag, setDrag] = useState<any>(null);
  const [over, setOver] = useState<string | null>(null);
  function load() { api.votesList().then(setD); }
  useEffect(() => { load(); }, []);

  async function move(item: any, target: string) {
    if (!item || item.verdict === target) return;
    const code = await api.recategorize(item.thesis, item.listing_id, target);
    if (code === 403) { location.href = "/login"; return; }
    if (code === 200) load();
    else alert("Couldn't move that deal — please try again.");
  }
  async function drop(target: string) {
    setOver(null);
    const item = drag; setDrag(null);
    await move(item, target);
  }

  const votes = useMemo(
    () => (d?.votes || []).filter((x: any) => x.thesis === thesis && withinWindow(x.created_at, period)),
    [d, thesis, period]);

  return (
    <main className="wrap">
      <div className="boardhead">
        <h1 className="h1">Shortlist</h1>
        <p className="sub" style={{ maxWidth: "none" }}>
          Every verdict on {LABEL[thesis]} deals, saved with the deal&apos;s full context at vote time. Drag a deal
          between columns to re-categorize. These votes are the training data for the ranking model.
        </p>
        <div className="filterbar">
          <div className="lens" role="group" aria-label="Thesis">
            {["water", "healthcare"].map((t) => (
              <button key={t} className={t} aria-pressed={thesis === t} onClick={() => setThesis(t)}>
                <span className="dot" />{LABEL[t]}
              </button>
            ))}
          </div>
          <div className="seg" role="group" aria-label="Time window">
            {PERIODS.map(([k, lbl]) => (
              <button key={k} aria-pressed={period === k} onClick={() => setPeriod(k)}>{lbl}</button>
            ))}
          </div>
        </div>
      </div>

      {d && (
        <>
          <div className="bigstat"><b>{votes.length}</b><span>{LABEL[thesis]} deals voted{period === "all" ? "" : " in window"}</span></div>
          {ORDER.map((v) => {
            const items = votes.filter((x: any) => x.verdict === v);
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
                  {items.length === 0 && <p className="note" style={{ margin: 0 }}>Drag a deal here, or use the buttons on each row.</p>}
                  {items.map((x: any) => {
                    const item = { listing_id: x.listing_id, thesis: x.thesis, verdict: v };
                    return (
                    <div className="vrow" key={String(x.listing_id) + x.operator} draggable
                      style={{ cursor: "grab" }}
                      onDragStart={() => setDrag(item)}
                      onDragEnd={() => setOver(null)}>
                      <span aria-hidden style={{ color: "var(--faint)", letterSpacing: "-2px", fontSize: 14 }}>⋮⋮</span>
                      <span className="vname">
                        {x.listing_url ? <a draggable={false} href={safeHref(x.listing_url)} target="_blank" rel="noreferrer">{x.business_name}</a> : x.business_name}
                      </span>
                      <span className="vmeta">{x.operator?.split("@")[0]} · {(x.created_at || "").slice(0, 10)}</span>
                      <span className="vmove" role="group" aria-label="Move this deal">
                        {ORDER.map((t) => (
                          <button key={t} className={`vmovebtn ${t} ${v === t ? "on" : ""}`} disabled={v === t}
                            aria-pressed={v === t} aria-label={`Move to ${t}`} title={`Move to ${t}`}
                            onClick={() => move(item, t)}>{t}</button>
                        ))}
                      </span>
                    </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </>
      )}
    </main>
  );
}
