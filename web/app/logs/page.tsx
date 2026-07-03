"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function Logs() {
  const [data, setData] = useState<any>(null);
  useEffect(() => { api.logs().then(setData); }, []);

  return (
    <main className="wrap" style={{ maxWidth: 880 }}>
      <h1 className="h1">Activity &amp; cost</h1>
      <p className="note" style={{ marginBottom: 18 }}>
        One ledger for everything the engine has done — what ran, what it produced, and what it
        cost. No hunting through log files; the spend is a number you can read.
      </p>

      {data && (
        <>
          <div className="bigstat">
            <b>${data.total_spend_usd.toFixed(4)}</b>
            <span>total engine spend, all time</span>
          </div>
          <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
            <div className="ledger" style={{ fontWeight: 600 }}>
              <div className="k">Stage</div><div className="k">When</div>
              <div className="k">Detail</div><div className="k c" style={{ textAlign: "right" }}>Cost</div>
            </div>
            {data.runs.map((r: any, i: number) => (
              <div className="ledger" key={i}>
                <div className="k">{r.kind}</div>
                <div className="mono" style={{ fontSize: 11 }}>{(r.started_at || "").slice(0, 19).replace("T", " ")}</div>
                <div className="note" style={{ fontSize: 12 }}>
                  {r.listings_processed ?? 0} processed · {r.new_count ?? 0} new{r.note ? ` · ${r.note}` : ""}
                </div>
                <div className="c">${(r.cost_usd ?? 0).toFixed(4)}</div>
              </div>
            ))}
            {data.runs.length === 0 && <div style={{ padding: 16 }} className="note">No runs recorded yet.</div>}
          </div>
        </>
      )}
    </main>
  );
}
