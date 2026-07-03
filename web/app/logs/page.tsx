"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function Logs() {
  const [d, setD] = useState<any>(null);
  useEffect(() => { api.logs().then(setD); }, []);

  return (
    <main className="wrap" style={{ maxWidth: 900 }}>
      <h1 className="h1">Engine log</h1>
      <p className="sub" style={{ marginBottom: 18 }}>
        A raw record of every engine run — what ran, what it produced, and what it cost.
        For the day-by-day cost view, see Spend.
      </p>

      {d && (
        <>
          <div className="bigstat"><b>${d.total_spend_usd.toFixed(4)}</b><span>total engine spend, all time</span></div>
          <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
            <table className="table">
              <thead><tr><th>Stage</th><th>When</th><th>Detail</th><th className="num">Cost</th></tr></thead>
              <tbody>
                {d.runs.map((r: any, i: number) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 600, textTransform: "capitalize" }}>{r.kind}</td>
                    <td className="num">{(r.started_at || "").slice(0, 19).replace("T", " ")}</td>
                    <td className="note">{r.listings_processed ?? 0} processed · {r.new_count ?? 0} new{r.note ? ` · ${r.note}` : ""}</td>
                    <td className="num">${(r.cost_usd ?? 0).toFixed(4)}</td>
                  </tr>
                ))}
                {d.runs.length === 0 && <tr><td colSpan={4} className="note">No runs recorded yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </>
      )}
    </main>
  );
}
