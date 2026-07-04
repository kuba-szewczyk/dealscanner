export const metadata = { title: "How it works — DealScanner" };

const STEPS = [
  { n: 1, t: "Brokers", d: "A curated list of 236 business-for-sale brokers is the raw supply. You manage it on the Brokers page — add, archive, or fix a source." },
  { n: 2, t: "Daily scrape", d: "Every morning the engine visits each live broker, reads the new listings, and stores them once (deduped by URL) with their full text and financials." },
  { n: 3, t: "Thesis filter", d: "Your thesis — keywords, size band, geography, exclusions — decides what qualifies. A cheap global filter drops the obvious misses (salons, restaurants) before any AI runs." },
  { n: 4, t: "AI scoring", d: "Where wording is fuzzy, a cheap model reads the listing and judges fit, with a reason. Answers are cached, so the same listing is never paid for twice." },
  { n: 5, t: "Morning briefing", d: "You get one email: the new deals that cleared your thesis in the last 24 hours, linked straight to the board. That email is also the engine's heartbeat." },
  { n: 6, t: "You act", d: "Open the Deals board, skim the qualifying deals, and shortlist the ones worth a call. Everything older is a keyword away on Search." },
];

export default function Help() {
  return (
    <main className="wrap">
      <h1 className="h1">How it works</h1>
      <p className="sub" style={{ maxWidth: "none", marginBottom: 22 }}>
        DealScanner turns 236 scattered broker websites into one short morning briefing of businesses worth buying —
        filtered to your investment thesis. Here is the whole pipeline, end to end.
      </p>

      {/* pipeline */}
      <div className="pipeline">
        {STEPS.map((s, i) => (
          <div key={s.n} className="pstep">
            <div className="pnum">{s.n}</div>
            <div className="pbody"><b>{s.t}</b><span>{s.d}</span></div>
            {i < STEPS.length - 1 && <div className="parrow" aria-hidden>→</div>}
          </div>
        ))}
      </div>

      {/* funnel */}
      <div className="hrow">
        <div className="panel hcard">
          <h2 className="hh2">From noise to a shortlist</h2>
          <p className="note">Most listings are not for you. Each stage narrows the pile so you only ever read the deals that fit — the rest stay searchable but out of your way.</p>
          {(() => {
            const stages = [
              { w: 100, l: "236 brokers scanned", c: "#2563eb" },
              { w: 82, l: "Thousands of listings", c: "#3b82f6" },
              { w: 55, l: "Global filter applied", c: "#60a5fa" },
              { w: 30, l: "Matches your thesis", c: "#38bdf8" },
              { w: 14, l: "A handful qualify / day", c: "#16a34a" },
            ];
            const cx = 84, maxHalf = 74, top = 10, bh = 30;
            return (
              <svg viewBox="0 0 340 170" className="funnelchart" role="img"
                aria-label="Conversion funnel narrowing from 236 brokers to a handful of qualifying deals per day">
                {stages.map((s, i) => {
                  const y0 = top + i * bh, y1 = y0 + bh;
                  const topH = (maxHalf * s.w) / 100;
                  const botFrac = i < stages.length - 1 ? stages[i + 1].w : s.w * 0.5;
                  const botH = (maxHalf * botFrac) / 100;
                  const midY = (y0 + y1) / 2, midH = (topH + botH) / 2;
                  return (
                    <g key={i}>
                      <polygon points={`${cx - topH},${y0} ${cx + topH},${y0} ${cx + botH},${y1} ${cx - botH},${y1}`} fill={s.c} />
                      <line x1={cx + midH} y1={midY} x2="172" y2={midY} stroke="var(--line)" />
                      <text x="176" y={midY + 3} className="fchart-l">{s.l}</text>
                    </g>
                  );
                })}
              </svg>
            );
          })()}
        </div>

        {/* directional learning chart */}
        <div className="panel hcard">
          <h2 className="hh2">Coming soon: your votes sharpen it</h2>
          <p className="note">
            Today a deal either clears the thesis or it doesn&apos;t — a binary keyword-and-size gate. Every
            <b> yes / maybe / no</b> you cast is saved with the deal&apos;s full context. That becomes the training
            set for an <b>instinct model</b> that learns the judgment calls behind your votes — ranking deals the way
            you would, not just matching words.
          </p>
          <svg viewBox="0 0 300 130" className="learnchart" role="img" aria-label="Directional chart: relevance improves as votes accumulate">
            <line x1="34" y1="10" x2="34" y2="108" stroke="var(--line)" />
            <line x1="34" y1="108" x2="292" y2="108" stroke="var(--line)" />
            {/* binary gate: flat */}
            <path d="M34,74 L292,74" fill="none" stroke="var(--faint)" strokeWidth="2" strokeDasharray="4 4" />
            {/* instinct: rising */}
            <path d="M34,88 C110,84 170,50 292,22" fill="none" stroke="var(--good)" strokeWidth="2.5" />
            <text x="40" y="24" className="lc-t" fill="var(--good)">instinct model (learns)</text>
            <text x="150" y="68" className="lc-t" fill="var(--faint)">binary gate (fixed)</text>
            <text x="150" y="124" className="lc-ax">votes collected →</text>
            <text x="10" y="60" className="lc-ax" transform="rotate(-90 10 60)">match quality →</text>
          </svg>
        </div>
      </div>

      <div className="panel" style={{ marginTop: 16 }}>
        <h2 className="hh2">Two principles that keep it cheap and honest</h2>
        <p className="note" style={{ marginBottom: 8 }}>
          <b>The database is the brain.</b> Every listing is stored once, thesis-neutrally. Your settings are a lens
          applied when you read — so changing a keyword re-ranks the whole board instantly and for free, with no re-scrape.
        </p>
        <p className="note" style={{ margin: 0 }}>
          <b>Spend is capped and visible.</b> Only the cheapest model is used, every AI call is metered against a daily
          cap, and the <a href="/spend">Spend</a> page shows exactly what each day cost versus what it found.
        </p>
      </div>
    </main>
  );
}
