"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const money = (v: number) => `$${(v ?? 0).toFixed(2)}`;
function fmtDay(s: string) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  if (!m) return s;
  const d = new Date(+m[1], +m[2] - 1, +m[3]);
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

type Day = {
  date: string; cost: number; total_new: number;
  model_costs: Record<string, number>; claude_tokens: number; brokers: number; firecrawl_pages: number;
};

// Short label + colour per Claude model, for the cost-mix bar.
const MODEL_META: Record<string, { name: string; c: string }> = {
  "claude-haiku-4-5": { name: "Haiku", c: "#60a5fa" },
  "claude-sonnet-4-5": { name: "Sonnet", c: "#a78bfa" },
  "claude-opus-4-8": { name: "Opus", c: "#f472b6" },
};
const modelMeta = (m: string) => MODEL_META[m] || { name: m.replace("claude-", ""), c: "#94a3b8" };
const fmtTok = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(0)}k` : `${n}`);

export default function Spend() {
  const [summary, setSummary] = useState({ cost_24h: 0, cost_7d: 0, cost_30d: 0 });
  const [daily, setDaily] = useState<Day[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.spend(30).then((d) => { setSummary(d.summary); setDaily(d.daily); setLoading(false); });
  }, []);

  return (
    <main className="wrap">
      <div className="boardhead">
        <h1 className="h1">Spend</h1>
        <p className="sub">What the engine costs versus what it finds — day by day. One shared scrape feeds
          every thesis, so cost, coverage, and usage are the same regardless of which thesis you&apos;re viewing.</p>
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
                <th>Cost by model</th>
                <th className="r">Brokers</th>
                <th className="r">New listings</th>
                <th className="r">Firecrawl</th>
              </tr>
            </thead>
            <tbody>
              {daily.map((d) => {
                const models = Object.entries(d.model_costs || {}).sort((a, b) => b[1] - a[1]);
                const modelTotal = models.reduce((s, [, v]) => s + v, 0);
                return (
                  <tr key={d.date}>
                    <td className="nowrap">{fmtDay(d.date)}</td>
                    <td className="r">{money(d.cost)}</td>
                    <td>
                      {modelTotal > 0 ? (
                        <span className="modelbar" title={models.map(([m, v]) => `${modelMeta(m).name}: ${money(v)}`).join(" · ") + ` · ${fmtTok(d.claude_tokens)} Claude tokens`}>
                          {models.map(([m, v]) => (
                            <span key={m} style={{ width: `${(v / modelTotal) * 100}%`, background: modelMeta(m).c }} />
                          ))}
                        </span>
                      ) : <span className="muted">—</span>}
                    </td>
                    <td className="r">{d.brokers || "—"}</td>
                    <td className="r">{d.total_new}</td>
                    <td className="r muted">{d.firecrawl_pages ? `${d.firecrawl_pages} pg` : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <div className="modellegend">
        {Object.entries(MODEL_META).map(([m, meta]) => (
          <span key={m}><i style={{ background: meta.c }} />{meta.name}</span>
        ))}
        <span className="muted">· “Cost by model” shows what drove each day’s Claude spend; hover for tokens. “Firecrawl” = pages fetched (credits).</span>
      </div>
    </main>
  );
}
