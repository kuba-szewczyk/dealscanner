import { safeHref } from "@/lib/api";
import { CAT_CLASS, FLAG_LABEL, fmtM, fmtDate } from "@/lib/deal";

type Props = {
  d: any;
  signedIn?: boolean;
  voted?: string;                 // current verdict for this deal, if any
  onVote?: (verdict: string) => void;
};

// The single deal card, shared by the Deals board and the Search detail modal so both
// render identically.
export default function DealCard({ d, signedIn, voted, onVote }: Props) {
  return (
    <article className="deal">
      <div className="content">
        <div className="deal-top">
          {d.tier && <span className={`tierdot ${d.tier}`}>{d.tier}</span>}
          <span className="deal-name">{d.business_name}</span>
        </div>
        <div className="meta">
          {d.category && <span className={`cat ${CAT_CLASS[d.category] || "c-gray"}`}>{d.category}</span>}
          {(d.city || d.state) && <span className="geo">{[d.city, d.state].filter(Boolean).join(", ")}</span>}
          {d.first_seen && <span className="spotted">scraped {fmtDate(d.first_seen)}</span>}
        </div>
        {d.one_line_take && <p className="blurb">{d.one_line_take}</p>}
        {d.matched_keywords && (
          <div className="kw"><b>Keywords:</b> {d.matched_keywords.split(",").map((k: string) => k.trim()).filter(Boolean).join(" · ")}</div>
        )}
        {(d.positive_flags?.length || d.negative_flags?.length) ? (
          <div className="flags">
            {(d.positive_flags || []).map((f: string) => <span key={f} className="gf">✓ {FLAG_LABEL[f] || f}</span>)}
            {(d.negative_flags || []).map((f: string) => <span key={f} className="rf">⚠ {FLAG_LABEL[f] || f}</span>)}
          </div>
        ) : null}
        <div className="dealfoot">
          <span className="broker">{d.broker}</span>
          <a className="viewlink" href={safeHref(d.listing_url)} target="_blank" rel="noreferrer">view listing ↗</a>
        </div>
      </div>
      <div className="fincol num">
        <div className="fin"><span>Rev</span><b>{fmtM(d.revenue)}</b></div>
        <div className="fin"><span>EBITDA</span><b>{fmtM(d.ebitda)}</b></div>
        <div className="fin"><span>SDE</span><b>{fmtM(d.sde)}</b></div>
        <div className="fin"><span>Ask</span><b>{fmtM(d.asking_price)}</b></div>
        <div className="fin"><span>Mult</span><b>{d.multiple ? `${d.multiple}x` : "—"}</b></div>
      </div>
      {signedIn && onVote && (
        <div className="votecol">
          {["yes", "maybe", "no"].map((v) => (
            <button key={v} className={`${v} ${voted === v ? "on" : ""}`} onClick={() => onVote(v)}>{v}</button>
          ))}
        </div>
      )}
    </article>
  );
}
