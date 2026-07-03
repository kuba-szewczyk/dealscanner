"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

const LABEL: Record<string, string> = { water: "Water / Wastewater", healthcare: "Healthcare" };
const money = (v: number) => `$${(v ?? 0).toFixed(2)}`;
function fmtDay(s: string) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  if (!m) return s;
  const d = new Date(+m[1], +m[2] - 1, +m[3]);
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

type Day = { date: string; cost: number; relevant: number; irrelevant: number; total_new: number };

export default function Spend() {
  const [thesis, setThesis] = useState("water");
  const [summary, setSummary] = useState({ cost_24h: 0, cost_7d: 0, cost_30d: 0 });
  const [daily, setDaily] = useState<Day[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.spend(thesis, 30).then((d) => { setSummary(d.summary); setDaily(d.daily); setLoading(false); });
  }, [thesis]);

  const maxNew = useMemo(() => Math.max(1, ...daily.map((d) => d.total_new)), [daily]);

  return (
    <main className="wrap">
      <div className="boardhead">
        <h1 className="h1">Spend</h1>
        <p className="sub">What the engine costs versus what it finds — day by day. Costs are shared across theses;
          the relevant / not-relevant split reflects the thesis selected here.</p>
        <div className="lens" role="group" aria-label="Thesis">
          {["water", "healthcare"].map((t) => (
            <button key={t} className={t} aria-pressed={thesis === t} onClick={() => setThesis(t)}>
              <span className="dot" />{LABEL[t]}
            </button>
          ))}
        </div>
      </div>

      <div className="statrow">
        <div className="stat"><span>Last 24 hours</span><b>{money(summary.cost_24h)}</b></div>
        <div className="stat"><span>Last 7 days</span><b>{money(summary.cost_7d)}</b></div>
        <div className="stat"><span>Last 30 days</span><b>{money(summary.cost_30d)}</b></div>
      </div>

      {loading && <p className="note">Loading…</p>}
      {!loading && daily.length === 0 && <div className="panel note">No engine activity in the last 30 days.</div>}

      {!loading && daily.length > 0 && (
        <div className="panel" style={{ padding: 0, overflowX: "auto" }}>
          <table className="dbtable">
            <thead>
              <tr>
                <th>Day</th>
                <th className="r">Cost</th>
                <th className="r">New listings</th>
                <th className="r">Relevant</th>
                <th className="r">Not relevant</th>
                <th>Mix</th>
                <th className="r">Cost / relevant</th>
              </tr>
            </thead>
            <tbody>
              {daily.map((d) => {
                const relPct = d.total_new ? (d.relevant / d.total_new) * 100 : 0;
                const barW = (d.total_new / maxNew) * 100;
                const perRel = d.relevant > 0 ? money(d.cost / d.relevant) : "—";
                return (
                  <tr key={d.date}>
                    <td className="nowrap">{fmtDay(d.date)}</td>
                    <td className="r">{money(d.cost)}</td>
                    <td className="r">{d.total_new}</td>
                    <td className="r"><b style={{ color: "#15803d" }}>{d.relevant}</b></td>
                    <td className="r muted">{d.irrelevant}</td>
                    <td>
                      <span className="mixbar" title={`${d.relevant} relevant / ${d.irrelevant} not relevant`} style={{ width: `${Math.max(barW, 4)}%` }}>
                        <span className="mixrel" style={{ width: `${relPct}%` }} />
                      </span>
                    </td>
                    <td className="r muted">{perRel}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="cost" style={{ textAlign: "left", marginTop: 10 }}>
        Green = deals that clear the {LABEL[thesis]} thesis. “Cost / relevant” is that day’s spend divided by the relevant deals it surfaced.
      </p>
    </main>
  );
}
