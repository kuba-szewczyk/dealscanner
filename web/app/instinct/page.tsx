"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function Instinct() {
  const [d, setD] = useState<any>(null);
  useEffect(() => { api.instinct().then(setD); }, []);
  const pct = d ? Math.min(100, Math.round((d.total_votes / d.target) * 100)) : 0;

  return (
    <main className="wrap" style={{ maxWidth: 720 }}>
      <h1 className="h1">Instinct model</h1>
      <span className="live">collecting data</span>
      <p className="note" style={{ margin: "16px 0 24px" }}>
        The hard filters decide what <i>qualifies</i>. The instinct model will one day decide what
        <i> you&apos;d actually chase</i> — learning each operator&apos;s taste from their own verdicts.
        It isn&apos;t built yet, on purpose: it needs real labeled examples first. Every vote you cast
        is being saved with the full context of the deal, so the day there&apos;s enough, the model
        trains on your judgment, not a guess.
      </p>

      {d && (
        <div className="panel">
          <div className="bigstat">
            <b>{d.total_votes}</b>
            <span>verdicts captured · target ~{d.target} before training</span>
          </div>
          <div className="progress"><i style={{ width: `${pct}%` }} /></div>
          <div className="note mono" style={{ fontSize: 11 }}>{pct}% of the way to a first trainable set</div>
          <div className="vsplit">
            <div><b style={{ color: "var(--good)" }}>{d.by_verdict.yes || 0}</b><span className="note">yes</span></div>
            <div><b style={{ color: "var(--warn)" }}>{d.by_verdict.maybe || 0}</b><span className="note">maybe</span></div>
            <div><b style={{ color: "var(--bad)" }}>{d.by_verdict.no || 0}</b><span className="note">no</span></div>
          </div>
        </div>
      )}
    </main>
  );
}
