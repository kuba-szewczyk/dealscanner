"use client";
import { useEffect, useState } from "react";
import { api, Deal } from "@/lib/api";

const LABEL: Record<string, string> = { water: "Water / Wastewater", healthcare: "Healthcare Services" };

const money = (v?: number) =>
  v == null ? "—" : v >= 1e6 ? `$${(v / 1e6).toFixed(1)}M` : `$${Math.round(v / 1e3)}K`;

export default function Board() {
  const [thesis, setThesis] = useState("water");
  const [deals, setDeals] = useState<Deal[]>([]);
  const [spend, setSpend] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState<number | null>(null);
  const [voted, setVoted] = useState<Record<number, string>>({});

  useEffect(() => {
    setLoading(true);
    Promise.all([api.board(thesis), api.runs()]).then(([b, r]) => {
      setDeals(b.listings);
      setSpend(r.total_spend_usd);
      setLoading(false);
    });
  }, [thesis]);

  async function cast(d: Deal, verdict: string) {
    const status = await api.vote(thesis, d.id, verdict);
    if (status === 200) setVoted((v) => ({ ...v, [d.id]: verdict }));
    else if (status === 403) window.location.href = "/login";
  }

  return (
    <div data-thesis={thesis}>
      <div className="desk">
        <div className="desk-inner">
          <div className="lens" role="group" aria-label="Thesis lens">
            {["water", "healthcare"].map((t) => (
              <button key={t} aria-pressed={thesis === t} onClick={() => setThesis(t)}>
                <span className="dot" />{t}
              </button>
            ))}
          </div>
          <div className="spacer" />
          <div className="cost">
            <b>${spend.toFixed(4)}</b> engine spend to date<br />
            same corpus · re-ranked live in the browser
          </div>
        </div>
      </div>

      <main className="wrap">
        <div className="boardhead">
          <div className="thesis-name">
            Today&apos;s <span className="accent">{LABEL[thesis].split(" ")[0]}</span> deals
          </div>
          <span className="count-pill">{loading ? "…" : `${deals.length} ranked`}</span>
          <div className="sub">
            One engine, your thesis. These are scored from the same shared database —
            switch the lens to see {thesis === "water" ? "the healthcare" : "Alex's water"} world re-rank from identical data.
          </div>
        </div>

        {loading && <p className="note">Loading the desk…</p>}
        {!loading && deals.length === 0 && (
          <div className="panel note">No deals clear this thesis yet. Loosen the keywords or size band in Thesis setup.</div>
        )}

        {deals.map((d, i) => (
          <div key={d.id}>
            <article className="deal">
              <div className="rail">
                <div className="rank mono">#{String(i + 1).padStart(2, "0")}</div>
                <div className="fit">{d.fit_score}<small>fit</small></div>
                <div className={`tierbadge tier-${d.tier}`}>{d.tier}</div>
              </div>
              <div className="body">
                <h2 className="name">{d.business_name}</h2>
                <div className="meta">
                  <b>{d.broker}</b>{d.city || d.state ? ` · ${[d.city, d.state].filter(Boolean).join(", ")}` : ""}
                  {d.category ? ` · ${d.category}` : ""}
                </div>
                {d.one_line_take && <p className="take">{d.one_line_take}</p>}
                <div className="chips">
                  {(d.matched_keywords || "").split(",").map((k) => k.trim()).filter(Boolean).slice(0, 4)
                    .map((k) => <span key={k} className="chip">{k}</span>)}
                  {(d.positive_flags || []).map((f) => <span key={f} className="flag pos">+ {f.replace(/_/g, " ")}</span>)}
                  {(d.negative_flags || []).map((f) => <span key={f} className="flag neg">– {f.replace(/_/g, " ")}</span>)}
                  <button className="flag" style={{ cursor: "pointer", background: "transparent" }}
                    onClick={() => setOpen(open === d.id ? null : d.id)} aria-expanded={open === d.id}>
                    {open === d.id ? "hide why" : "why it scored"}
                  </button>
                </div>
                {open === d.id && (
                  <div className="panel" style={{ marginTop: 10, padding: 12 }}>
                    <div className="note mono" style={{ fontSize: 12 }}>
                      relevance {d.relevance}/5 · flag_score {d.flag_score}/9 · fit = relevance×2 + flags<br />
                      matched: {d.matched_keywords || "—"}<br />
                      <a href={d.listing_url} target="_blank" rel="noreferrer" style={{ color: "var(--accent-ink)" }}>
                        open listing ↗
                      </a>
                    </div>
                  </div>
                )}
              </div>
              <div className="side">
                <div className="fin"><span>SDE</span><b>{money(d.sde)}</b></div>
                <div className="fin"><span>EBITDA</span><b>{money(d.ebitda)}</b></div>
                <div className="fin"><span>Revenue</span><b>{money(d.revenue)}</b></div>
                <div className="fin"><span>Multiple</span><b>{d.multiple ? `${d.multiple}x` : "—"}</b></div>
                <div className="votes">
                  {["yes", "maybe", "no"].map((v) => (
                    <button key={v} className={`${v} ${voted[d.id] === v ? "on" : ""}`} onClick={() => cast(d, v)}>{v}</button>
                  ))}
                </div>
                {voted[d.id] && <div className="voted">recorded · {voted[d.id]} ✓</div>}
              </div>
            </article>
          </div>
        ))}
      </main>
    </div>
  );
}
