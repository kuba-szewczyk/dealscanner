"use client";
import { useEffect, useState } from "react";
import { api, safeHref } from "@/lib/api";

const CAT_CLASS: Record<string, string> = {
  "Healthcare": "c-teal", "Restaurant & Food": "c-pink", "Construction & Trades": "c-amber",
  "Manufacturing": "c-purple", "Retail & E-commerce": "c-rose", "Professional Services": "c-blue",
  "Personal Care & Fitness": "c-green", "Real Estate & Property": "c-slate",
  "Distribution & Wholesale": "c-indigo", "Auto & Transport": "c-orange",
  "Education & Childcare": "c-cyan", "Cleaning & Facilities": "c-lime",
  "Hospitality & Lodging": "c-brown", "Services": "c-blue", "Software": "c-purple",
  "E-commerce": "c-rose", "Other": "c-gray",
};
const fmtM = (v?: number | null) => (v == null ? "—" : `$${(v / 1e6).toFixed(1)}M`);

function parseDate(s?: string): Date | null {
  if (!s) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
}
const fmtDate = (s?: string) => {
  const d = parseDate(s);
  if (!d) return "—";
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${mm}-${dd}-${d.getFullYear()}`;
};
const fmtWhen = (s?: string) => {
  if (!s) return "never";
  const d = new Date(s);
  return isNaN(+d) ? "—" : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
};

const WINDOWS: [number, string][] = [[24, "24h"], [168, "7d"], [720, "30d"]];

export default function Activity() {
  const [data, setData] = useState<any>(null);
  const [hours, setHours] = useState(24);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.activity(hours).then((d) => { setData(d); setLoading(false); }).catch(() => setLoading(false));
  }, [hours]);

  const label = WINDOWS.find(([h]) => h === hours)?.[1] ?? "24h";

  return (
    <main className="wrap">
      <div className="boardhead">
        <h1 className="h1">Database</h1>
        <p className="sub">Every scraped listing persists here in SQLite — this is the raw record behind the boards, not a cached view. Confirm exactly what landed, from which broker, and when.</p>

        <div className="statrow">
          <div className="stat"><span>Total listings</span><b>{loading ? "…" : data?.total_listings?.toLocaleString()}</b></div>
          <div className="stat"><span>Net-new · {label}</span><b className="pos">{loading ? "…" : `+${data?.net_new_count ?? 0}`}</b></div>
          <div className="stat"><span>Last scrape</span><b>{loading ? "…" : fmtWhen(data?.last_scrape_at)}</b></div>
          <div className="stat"><span>Engine spend</span><b>{loading ? "…" : `$${data?.scrape_spend_usd?.toFixed(4)}`}</b></div>
        </div>

        <div className="seg" role="group" aria-label="Window">
          {WINDOWS.map(([h, lbl]) => (
            <button key={h} aria-pressed={hours === h} onClick={() => setHours(h)}>{lbl}</button>
          ))}
        </div>
      </div>

      {loading && <p className="note">Reading the database…</p>}

      {!loading && data && (
        <>
          {data.per_broker?.length > 0 && (
            <section>
              <div className="section-head"><h3>Broker yield · last crawl</h3><span className="n">({data.per_broker.length})</span></div>
              <div className="panel">
                <table className="dbtable">
                  <thead><tr><th>Broker</th><th className="r">New</th><th className="r">Seen</th><th className="r">Pages</th><th className="r">Chars fed</th><th>Status</th></tr></thead>
                  <tbody>
                    {data.per_broker.map((b: any, i: number) => (
                      <tr key={i}>
                        <td>{b.broker}</td>
                        <td className="r"><b className={b.new_count > 0 ? "pos" : "muted"}>{b.new_count > 0 ? `+${b.new_count}` : "0"}</b></td>
                        <td className="r">{b.total_count}</td>
                        <td className="r">{b.pages > 1 ? <b>{b.pages}</b> : (b.pages ?? "—")}</td>
                        <td className="r"><span className={b.chars_fed >= 60000 ? "atlimit" : ""} title={b.chars_fed >= 60000 ? "At the 60k feed limit — page is larger than we digest; raise limit or rely on pagination" : ""}>{b.chars_fed ? b.chars_fed.toLocaleString() : "—"}{b.chars_fed >= 60000 ? " ⚠" : ""}</span></td>
                        <td><span className={`pill ${b.status}`}>{b.status}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <section>
            <div className="section-head"><h3>Net-new listings · {label}</h3><span className="n">({data.net_new_count})</span></div>
            {data.net_new.length === 0 ? (
              <div className="panel note">No new listings in this window. Run a crawl, then they'll appear here the moment they hit the database.</div>
            ) : (
              <div className="panel">
                <table className="dbtable">
                  <thead><tr><th>#</th><th>Business</th><th>Broker</th><th className="r">EBITDA</th><th className="r">SDE</th><th className="r">Ask</th><th>Scraped</th><th></th></tr></thead>
                  <tbody>
                    {data.net_new.map((r: any) => (
                      <tr key={r.id}>
                        <td className="muted">{r.id}</td>
                        <td>
                          <span className="dbname">{r.business_name}</span>
                          {r.category && <span className={`cat ${CAT_CLASS[r.category] || "c-gray"}`}>{r.category}</span>}
                          {r.excludable_tags && <span className="extag" title="Tagged as a globally-excludable category (kept, but hidden by theses that exclude it)">⊘ {r.excludable_tags.split(",")[0]}</span>}
                        </td>
                        <td className="muted">{r.broker}</td>
                        <td className="r">{fmtM(r.ebitda)}</td>
                        <td className="r">{fmtM(r.sde)}</td>
                        <td className="r">{fmtM(r.asking_price)}</td>
                        <td className="muted">{fmtDate(r.first_seen)}</td>
                        <td><a className="viewlink" href={safeHref(r.listing_url)} target="_blank" rel="noreferrer">↗</a></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}
