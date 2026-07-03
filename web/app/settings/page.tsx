"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const LO = 0, HI = 10_000_000, STEP = 100_000;
const fmtUSD = (v: number) =>
  v >= HI ? "No max" : v >= 1e6 ? `$${(v / 1e6).toFixed(v % 1e6 ? 1 : 0)}M` : `$${Math.round(v / 1e3)}K`;

function RangeBand({ min, max, setMin, setMax }: { min: number; max: number; setMin: (v: number) => void; setMax: (v: number) => void }) {
  const pct = (v: number) => (Math.min(Math.max(v, LO), HI) - LO) / (HI - LO) * 100;
  return (
    <>
      <div className="rangewrap">
        <div className="track"><div className="fill" style={{ left: pct(min) + "%", right: (100 - pct(max)) + "%" }} /></div>
        <input type="range" min={LO} max={HI} step={STEP} value={Math.min(min, HI)} aria-label="minimum"
          onChange={(e) => setMin(Math.min(+e.target.value, max - STEP))} style={{ zIndex: 5 }} />
        <input type="range" min={LO} max={HI} step={STEP} value={Math.min(max, HI)} aria-label="maximum"
          onChange={(e) => setMax(Math.max(+e.target.value, min + STEP))} style={{ zIndex: 4 }} />
      </div>
      <div className="rangevals"><span className="pill">{fmtUSD(min)}</span><span className="pill">{fmtUSD(max)}</span></div>
    </>
  );
}

const tin: React.CSSProperties = { width: 60, padding: "4px 7px", margin: "0 4px", display: "inline-block" };

const POS = [
  ["geo_t1", "Tier-1 metro", "Business is in a preferred metro"],
  ["geo_t2", "Preferred state", "Business is in one of your preferred states"],
  ["margin_gt_20", "Strong margin", null],
  ["owner_retiring", "Owner retiring", "Reason for sale is owner retirement"],
  ["recurring_40", "Recurring revenue", null],
];
const NEG = [
  ["low_margin_lt_15", "Low margin", null],
  ["overpriced", "Overpriced", null],
  ["franchise_resale", "Franchise resale", "Listing is a franchise resale"],
  ["partial", "Partial sale", "Minority stake, asset sale, or partial acquisition"],
];

export default function Settings() {
  const [thesis, setThesis] = useState("water");
  const [s, setS] = useState<any>(null);
  const [saved, setSaved] = useState<number | null>(null);
  const [tier1, setTier1] = useState(""); const [tier2, setTier2] = useState("");
  const [context, setContext] = useState(""); const [negative, setNegative] = useState("");
  const [states, setStates] = useState(""); const [metros, setMetros] = useState("");
  const [ebMin, setEbMin] = useState(1000000); const [ebMax, setEbMax] = useState(5000000);
  const [sdeMin, setSdeMin] = useState(1500000); const [sdeMax, setSdeMax] = useState(1e12);
  const [pos, setPos] = useState<string[]>([]); const [neg, setNeg] = useState<string[]>([]);
  const [exRest, setExRest] = useState(true); const [exRE, setExRE] = useState(false); const [exFr, setExFr] = useState(false);
  // editable thresholds
  const [tMarginGood, setTMarginGood] = useState(20); const [tRecurring, setTRecurring] = useState(40);
  const [tMarginLow, setTMarginLow] = useState(15); const [tOverEb, setTOverEb] = useState(6); const [tOverSde, setTOverSde] = useState(5);

  useEffect(() => {
    api.settings(thesis).then((d) => {
      setS(d); setSaved(null);
      setTier1((d.keywords?.tier1 || []).join("\n")); setTier2((d.keywords?.tier2 || []).join("\n"));
      setContext((d.keywords?.context || []).join(", ")); setNegative((d.keywords?.negative || []).join("\n"));
      setStates((d.geo?.tier2_states || []).join(", ")); setMetros((d.geo?.tier1_metros || []).join(", "));
      setEbMin(d.size?.ebitda_min || 1000000); setEbMax(Math.min(d.size?.ebitda_max || 5000000, HI));
      setSdeMin(d.size?.sde_min || 1500000); setSdeMax(d.size?.sde_max && d.size.sde_max < HI ? d.size.sde_max : HI);
      setPos(d.flags?.positive || []); setNeg(d.flags?.negative || []);
      setExRest(d.exclusions ? !!d.exclusions.restaurants : true);
      setExRE(d.exclusions ? !!d.exclusions.real_estate : false);
      setExFr(d.exclusions ? !!d.exclusions.franchise : false);
      const t = d.thresholds || {};
      setTMarginGood(t.margin_good ?? 20); setTRecurring(t.recurring ?? 40);
      setTMarginLow(t.margin_low ?? 15); setTOverEb(t.overprice_ebitda ?? 6); setTOverSde(t.overprice_sde ?? 5);
    });
  }, [thesis]);

  const lines = (t: string) => t.split("\n").map((x) => x.trim()).filter(Boolean);
  const csv = (t: string) => t.split(",").map((x) => x.trim()).filter(Boolean);
  const toggle = (arr: string[], set: any, k: string) => set(arr.includes(k) ? arr.filter((x) => x !== k) : [...arr, k]);

  async function save() {
    const next = structuredClone(s);
    next.keywords = { tier1: lines(tier1), tier2: lines(tier2), context: csv(context), negative: lines(negative) };
    next.geo = { tier1_metros: csv(metros), tier2_states: csv(states).map((x) => x.toUpperCase()) };
    next.size = { ...next.size, ebitda_min: +ebMin, ebitda_max: ebMax >= HI ? 1e12 : +ebMax, sde_min: +sdeMin, sde_max: sdeMax >= HI ? 1e12 : +sdeMax };
    next.flags = { positive: pos, negative: neg };
    next.exclusions = { restaurants: exRest, real_estate: exRE, franchise: exFr };
    next.thresholds = { margin_good: +tMarginGood, recurring: +tRecurring, margin_low: +tMarginLow, overprice_ebitda: +tOverEb, overprice_sde: +tOverSde };
    const r = await api.putSettings(thesis, next);
    setS(next); setSaved(r.board_count_now);
  }

  return (
    <main className="wrap" style={{ maxWidth: 820 }}>
      <h1 className="h1">Thesis</h1>
      <p className="sub" style={{ marginBottom: 16 }}>Define what qualifies: keywords, size band, geography, and flags. Changes re-rank every listing instantly — no re-scrape, no cost.</p>
      <div className="lens" style={{ marginBottom: 20 }} role="group" aria-label="Thesis">
        {["water", "healthcare"].map((t) => (
          <button key={t} className={t} aria-pressed={thesis === t} onClick={() => setThesis(t)}><span className="dot" />{t === "water" ? "Water" : "Healthcare"}</button>
        ))}
      </div>

      {s && (<>
        <div className="panel">
          <p className="card-title">Quick exclusions</p>
          <p className="card-note">Drop whole categories before anything else is scored.</p>
          <label className="check"><input type="checkbox" checked={exRest} onChange={() => setExRest(!exRest)} />
            <span>Exclude restaurants, bars &amp; food service <span className="def">pizzerias, cafés, catering, breweries…</span></span></label>
          <label className="check"><input type="checkbox" checked={exRE} onChange={() => setExRE(!exRE)} />
            <span>Exclude real estate <span className="def">property listings, land, leasing</span></span></label>
          <label className="check"><input type="checkbox" checked={exFr} onChange={() => setExFr(!exFr)} />
            <span>Exclude franchises <span className="def">franchise / franchisee / franchisor listings</span></span></label>
        </div>

        <div className="panel">
          <p className="card-title">Size gate</p>
          <p className="card-note">A deal qualifies if its EBITDA <b>or</b> SDE falls inside the band. Drag either handle.</p>
          <div className="grid2" style={{ gap: 28 }}>
            <div className="field" style={{ marginBottom: 0 }}><label>EBITDA band</label>
              <RangeBand min={ebMin} max={ebMax} setMin={setEbMin} setMax={setEbMax} />
            </div>
            <div className="field" style={{ marginBottom: 0 }}><label>SDE band</label>
              <RangeBand min={sdeMin} max={sdeMax} setMin={setSdeMin} setMax={setSdeMax} />
            </div>
          </div>
        </div>

        <div className="panel">
          <p className="card-title">Relevance keywords</p>
          <div className="logicbox" style={{ marginTop: 0, marginBottom: 16 }}>
            <b>How keyword filtering works</b>
            <ol>
              <li><b>Tier 1</b> — a single match qualifies a deal as relevant on its own.</li>
              <li><b>Tier 2</b> — counts only when a <b>context word</b> also appears (e.g. “equipment rental” counts only alongside “water”).</li>
              <li><b>Negative keywords</b> — when present alongside a match, they cap the confidence (mixed business).</li>
              <li>No qualifying match → the deal is not relevant for this thesis.</li>
            </ol>
          </div>
          <div className="grid2">
            <div className="field"><label>Tier 1 keywords <span className="hint">(one per line)</span></label><textarea rows={8} value={tier1} onChange={(e) => setTier1(e.target.value)} /></div>
            <div className="field"><label>Tier 2 keywords <span className="hint">(one per line)</span></label><textarea rows={8} value={tier2} onChange={(e) => setTier2(e.target.value)} /></div>
          </div>
          <div className="field"><label>Context words <span className="hint">(comma-separated)</span></label><input type="text" value={context} onChange={(e) => setContext(e.target.value)} /></div>
          <div className="field" style={{ marginBottom: 0 }}><label>Negative keywords <span className="hint">(one per line)</span></label><textarea rows={4} value={negative} onChange={(e) => setNegative(e.target.value)} /></div>
        </div>

        <div className="panel">
          <p className="card-title">Geography</p>
          <div className="field"><label>Preferred metros <span className="hint">(comma-separated, +1 green flag)</span></label><input type="text" value={metros} onChange={(e) => setMetros(e.target.value)} /></div>
          <div className="field"><label>Preferred states <span className="hint">(comma-separated, +1 green flag)</span></label><input type="text" value={states} onChange={(e) => setStates(e.target.value)} /></div>
        </div>

        <div className="grid2">
          <div className="panel">
            <p className="card-title">Green flags</p>
            <p className="card-note">Each present flag adds to a deal's score.</p>
            {POS.map(([k, name]) => (
              <label className="check" key={k}><input type="checkbox" checked={pos.includes(k as string)} onChange={() => toggle(pos, setPos, k as string)} />
                <span>{name}
                  {k === "margin_gt_20" && <span className="def">EBITDA margin above <input type="number" style={tin} value={tMarginGood} onChange={(e) => setTMarginGood(+e.target.value)} />%</span>}
                  {k === "recurring_40" && <span className="def"><input type="number" style={tin} value={tRecurring} onChange={(e) => setTRecurring(+e.target.value)} />%+ of revenue recurring</span>}
                </span></label>
            ))}
          </div>
          <div className="panel">
            <p className="card-title">Red flags</p>
            <p className="card-note">Each absent flag adds to the score; present ones warn.</p>
            {NEG.map(([k, name]) => (
              <label className="check" key={k}><input type="checkbox" checked={neg.includes(k as string)} onChange={() => toggle(neg, setNeg, k as string)} />
                <span>{name}
                  {k === "low_margin_lt_15" && <span className="def">EBITDA margin under <input type="number" style={tin} value={tMarginLow} onChange={(e) => setTMarginLow(+e.target.value)} />%</span>}
                  {k === "overpriced" && <span className="def">Above <input type="number" style={tin} value={tOverEb} onChange={(e) => setTOverEb(+e.target.value)} />× EBITDA &nbsp;or&nbsp; <input type="number" style={tin} value={tOverSde} onChange={(e) => setTOverSde(+e.target.value)} />× SDE</span>}
                </span></label>
            ))}
          </div>
        </div>

        <button className="btn" onClick={save}>Save &amp; re-rank</button>
        {saved !== null && <span style={{ marginLeft: 14 }} className="live">re-ranked live · {saved} deals now clear this thesis</span>}
      </>)}
    </main>
  );
}
