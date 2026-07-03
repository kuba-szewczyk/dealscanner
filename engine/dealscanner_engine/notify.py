"""Daily 'deals are ready' email — fired at the end of the crawl.

Per-recipient: each operator gets a digest for THEIR thesis only (see RECIPIENTS), with the
last-24h count + sample deals and a link straight to that thesis's board filtered to 24h.
Sends via the pluggable mailer (Resend if configured, else Gmail)."""
from __future__ import annotations

from datetime import datetime

from . import config, db, evaluator, mailer, thesis

# Who gets which thesis digest — sourced from env (DIGEST_RECIPIENTS), no emails in code.
LABEL = {"water": "Water / Wastewater", "healthcare": "Healthcare"}


def _link(slug: str) -> str:
    return f"https://dealscanner.us/?thesis={slug}&window=24h"


def day_summary(conn) -> dict:
    # "Today's" deals — matches the board's 24h filter (first_seen = today) so the email's
    # counts never disagree with what the link shows.
    new_rows = [dict(r) for r in conn.execute(
        "SELECT * FROM listings WHERE date(first_seen) = date('now')")]
    out: dict = {"total_new": len(new_rows), "theses": {}}
    for slug in ("water", "healthcare"):
        try:
            s = thesis.get_settings(conn, slug)
        except KeyError:
            continue
        q = [(evaluator.evaluate(r, s), r) for r in new_rows]
        q = [(v, r) for v, r in q if v["section"] == "in"]
        q.sort(key=lambda x: x[0]["fit_score"], reverse=True)
        out["theses"][slug] = {"qualifying": len(q),
                               "samples": [r["business_name"] for _, r in q[:4]]}
    out["spend"] = conn.execute(
        "SELECT ROUND(COALESCE(SUM(cost_usd),0),2) FROM runs WHERE date(started_at)=date('now')"
    ).fetchone()[0]
    return out


def _compose(s: dict, slug: str) -> tuple[str, str]:
    name = LABEL.get(slug, slug)
    d = s["theses"].get(slug, {"qualifying": 0, "samples": []})
    n = d["qualifying"]
    samples = "".join(f"<li style='margin:3px 0;color:#475569'>{x}</li>" for x in d["samples"])
    subject = f"DealScanner — {n} new {name} deal{'' if n == 1 else 's'} today ({datetime.now():%b %-d})"
    body = f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:560px;margin:0 auto;color:#1e293b">
  <p style="font-size:15px">Good morning — today's crawl is done and your board is updated.</p>
  <p style="font-size:22px;font-weight:700;margin:6px 0">{n} new {name} deal{'' if n == 1 else 's'}
     <span style="font-size:14px;font-weight:400;color:#64748b">qualifying today</span></p>
  <ul style="margin:6px 0 0 18px;padding:0;font-size:14px">{samples or "<li style=color:#94a3b8>— nothing new clears the thesis today —</li>"}</ul>
  <p style="margin:22px 0">
    <a href="{_link(slug)}" style="background:#2563eb;color:#fff;text-decoration:none;padding:11px 20px;border-radius:8px;font-weight:600;font-size:15px">View today's {name} deals →</a>
  </p>
  <p style="font-size:12px;color:#94a3b8">{s['total_new']} new listings scanned today · engine spend ${s['spend']}</p>
</div>"""
    return subject, body


def notify(to: str | None = None) -> dict:
    """Send the per-thesis digest. to=None -> every operator in RECIPIENTS; to=X -> just X
    (using X's mapped thesis, or healthcare for an unknown test address)."""
    conn = db.connect()
    s = day_summary(conn)
    recipients = config.recipients()
    targets = ({to: recipients.get(to, config.default_thesis())} if to
               else dict(recipients))
    if not targets:
        return {"sent": [], "via": None, "total_new": s["total_new"],
                "warning": "no DIGEST_RECIPIENTS/DIGEST_TO configured"}
    sent = []
    backend = None
    for email, slug in targets.items():
        subject, html = _compose(s, slug)
        backend = mailer.send_email([email], subject, html)
        sent.append({"to": email, "thesis": slug, "qualifying": s["theses"].get(slug, {}).get("qualifying", 0)})
    return {"sent": sent, "via": backend, "total_new": s["total_new"]}
