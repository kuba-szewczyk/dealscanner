"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function Brokers() {
  const [rows, setRows] = useState<any[]>([]);
  useEffect(() => { api.brokers().then((d) => setRows(d.brokers)); }, []);
  const silent = rows.filter((r) => r.health === "silent").length;

  return (
    <main className="wrap" style={{ maxWidth: 880 }}>
      <h1 className="h1">Broker quality</h1>
      <p className="note" style={{ marginBottom: 18 }}>
        Every source, how much it has produced, and whether it has gone quiet. A broker that
        silently stops returning listings shows up here as <b>silent</b> instead of disappearing
        unnoticed — the failure that used to hide in a log file.
        {silent > 0 && <> Right now <b>{silent}</b> {silent === 1 ? "source needs" : "sources need"} a look.</>}
      </p>
      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <table className="table">
          <thead>
            <tr><th>Broker</th><th>Health</th><th className="num">Listings kept</th>
              <th className="num">Last 30d</th><th className="num">Last seen</th></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.broker}>
                <td>{r.broker}</td>
                <td><span className={`hdot ${r.health}`}>{r.health}</span></td>
                <td className="num">{r.total}</td>
                <td className="num">{r.last30}</td>
                <td className="num">{r.last_seen || "—"} <span style={{ color: "var(--faint)" }}>({r.days_since}d)</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
