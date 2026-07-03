"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function Settings() {
  const [thesis, setThesis] = useState("water");
  const [settings, setSettings] = useState<any>(null);
  const [tier1, setTier1] = useState("");
  const [states, setStates] = useState("");
  const [sdeMin, setSdeMin] = useState(0);
  const [saved, setSaved] = useState<number | null>(null);

  useEffect(() => {
    api.settings(thesis).then((s) => {
      setSettings(s);
      setTier1((s.keywords?.tier1 || []).join("\n"));
      setStates((s.geo?.tier2_states || []).join(", "));
      setSdeMin(s.size?.sde_min || 0);
      setSaved(null);
    });
  }, [thesis]);

  async function save() {
    const next = structuredClone(settings);
    next.keywords.tier1 = tier1.split("\n").map((x) => x.trim()).filter(Boolean);
    next.geo.tier2_states = states.split(",").map((x) => x.trim().toUpperCase()).filter(Boolean);
    next.size.sde_min = Number(sdeMin) || 0;
    const r = await api.putSettings(thesis, next);
    setSettings(next);
    setSaved(r.board_count_now);
  }

  return (
    <div data-thesis={thesis}>
      <main className="wrap" style={{ maxWidth: 760 }}>
        <h1 className="h1">Thesis setup</h1>
        <p className="note" style={{ marginBottom: 18 }}>
          Everything that decides a deal lives here, not in code. Edit it and the whole corpus
          re-ranks instantly — no re-scraping, no cost. (Fuzzy wording is caught by the optional
          AI re-judge, run from the engine.)
        </p>

        <div className="lens" style={{ marginBottom: 22 }} role="group" aria-label="Thesis">
          {["water", "healthcare"].map((t) => (
            <button key={t} aria-pressed={thesis === t} onClick={() => setThesis(t)}>
              <span className="dot" />{t}
            </button>
          ))}
        </div>

        {settings && (
          <div className="panel">
            <div className="field">
              <label>Relevance keywords — one per line (Tier 1: a single match qualifies a deal)</label>
              <textarea rows={8} value={tier1} onChange={(e) => setTier1(e.target.value)} />
            </div>
            <div className="field">
              <label>Home-turf states (geo bonus)</label>
              <input value={states} onChange={(e) => setStates(e.target.value)} />
            </div>
            <div className="field">
              <label>Minimum SDE (size gate, $)</label>
              <input className="mono" type="number" value={sdeMin} onChange={(e) => setSdeMin(Number(e.target.value))} />
            </div>
            <button className="btn" onClick={save}>Save &amp; re-rank</button>
            {saved !== null && (
              <span style={{ marginLeft: 14 }} className="live">
                re-ranked live · {saved} deals now clear this thesis
              </span>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
