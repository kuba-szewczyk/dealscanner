"""dsv2 CLI — foundation commands for v2.

  dsv2 initdb                 create the SQLite schema
  dsv2 seed                   seed accounts + editable settings from thesis/*.yaml
  dsv2 import-json <file>     migrate v1 Sheet rows (JSON list) into listings
  dsv2 board <account>        apply the account's CURRENT settings -> ranked board
  dsv2 settings <account>     print the account's live settings
  dsv2 stats                  row counts
"""
from __future__ import annotations

import argparse
import json
import sys

from . import db, evaluator, thesis


def _conn():
    return db.connect()


def cmd_initdb(args):
    db.init_db()
    print(f"DB initialized at {db.DB_PATH}")


def cmd_seed(args):
    conn = _conn()
    seeded = thesis.seed_accounts(conn)
    accts = [dict(r) for r in conn.execute("SELECT slug, name FROM accounts").fetchall()]
    print(f"Accounts: {[a['slug'] for a in accts]}  (newly seeded settings: {seeded or 'none'})")


def cmd_import(args):
    conn = _conn()
    with open(args.file) as f:
        rows = json.load(f)
    res = __import__("dealscanner_engine.importer", fromlist=["import_rows"]).import_rows(conn, rows)
    print(f"Import: {res}")
    print(f"Total listings now: {conn.execute('SELECT COUNT(*) c FROM listings').fetchone()['c']}")


def cmd_board(args):
    conn = _conn()
    settings = thesis.get_settings(conn, args.account)
    sections = tuple(args.sections.split(","))
    rows = evaluator.board(conn, settings, date=args.date, include_sections=sections, limit=args.limit)
    print(f"\n{args.account.upper()} board — {len(rows)} listings (sections={sections}, date={args.date or 'all'})\n")
    print(f"{'#':>3} {'fit':>5} {'tier':>4} {'rel':>3}  {'broker':16.16} {'business':40.40}  {'sde/ebitda':>12}  keywords")
    for i, r in enumerate(rows[:args.limit], 1):
        fin = r.get("ebitda") or r.get("sde")
        fins = f"${fin/1e6:.1f}M" if fin else "-"
        print(f"{i:>3} {r['fit_score']:>5} {r['tier']:>4} {r['relevance']:>3}  "
              f"{(r.get('broker') or ''):16.16} {(r.get('business_name') or ''):40.40}  {fins:>12}  "
              f"{(r.get('matched_keywords') or '')[:40]}")


def cmd_settings(args):
    conn = _conn()
    print(json.dumps(thesis.get_settings(conn, args.account), indent=2))


def cmd_scrape(args):
    from .scrape import scrape_broker
    print(f"Scrape: {scrape_broker(args.broker, max_usd=args.max_usd)}")


def cmd_rejudge(args):
    from .rejudge import rejudge
    print(f"Re-judge: {rejudge(args.account, limit=args.limit, max_usd=args.max_usd)}")


def cmd_runs(args):
    conn = _conn()
    print(f"{'kind':8} {'when':20} {'proc':>5} {'new':>5} {'cost':>9}  note")
    for r in conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 15").fetchall():
        print(f"{r['kind']:8} {(r['started_at'] or '')[:19]:20} {r['listings_processed'] or 0:>5} "
              f"{r['new_count'] or 0:>5} ${r['cost_usd'] or 0:>7.4f}  {r['note'] or ''}")
    total = conn.execute("SELECT COALESCE(SUM(cost_usd),0) t FROM runs").fetchone()["t"]
    print(f"\n  TOTAL SPEND TO DATE: ${total:.4f}")


def cmd_stats(args):
    conn = _conn()
    for tbl in ("accounts", "account_settings", "listings", "scores", "votes", "runs"):
        try:
            c = conn.execute(f"SELECT COUNT(*) c FROM {tbl}").fetchone()["c"]
            print(f"  {tbl:18} {c}")
        except Exception as e:
            print(f"  {tbl:18} (n/a: {e})")


def cmd_scrape_all(args):
    from .scrape import scrape_all
    res = scrape_all(max_usd=args.max_usd, limit=args.limit, max_pages=args.max_pages,
                     force=args.force, fresh=args.fresh)
    print(f"Scraped {res['brokers_scraped']} live brokers | +{res['total_new']} new, "
          f"{res['total_refreshed']} refreshed, {res['dead_brokers']} dead, "
          f"{res.get('error_brokers', 0)} errored | ${res['spend_usd']:.4f}"
          f"{'  (STOPPED at cap)' if res['stopped_early'] else ''}")
    for r in res["per_broker"]:
        if r.get("error"):
            print(f"  {r['broker'][:34]:34} ERROR — {r['error']}")
            continue
        if r.get("dead"):
            print(f"  {r['broker'][:34]:34} DEAD — {r['dead']}")
            continue
        flag = " ⚠TRUNCATED" if r.get("out_truncated") else ""
        print(f"  {r['broker'][:34]:34} +{r['inserted']:>3} new  {r['refreshed']:>3} refr  "
              f"{r['cards']:>3} cards  {r['pages']}pg  ${r['cost_usd']:.4f}{flag}")


def cmd_recent(args):
    """Click-into-the-DB: net-new listings persisted in the last N hours, straight from disk."""
    conn = _conn()
    rows = conn.execute(
        "SELECT id, broker, business_name, ebitda, sde, state, listing_url, first_seen "
        "FROM listings WHERE date(first_seen) >= date('now', ?) ORDER BY id DESC",
        (f"-{args.hours // 24 or 1} day",)).fetchall()
    print(f"NET-NEW listings, last {args.hours}h: {len(rows)} rows\n")
    if args.csv:
        import csv as _csv
        with open(args.csv, "w", newline="") as f:
            w = _csv.writer(f)
            w.writerow(["id", "broker", "business_name", "ebitda", "sde", "state", "url", "first_seen"])
            for r in rows:
                w.writerow([r["id"], r["broker"], r["business_name"], r["ebitda"], r["sde"],
                            r["state"], r["listing_url"], r["first_seen"]])
        print(f"  exported -> {args.csv}")
    for r in rows[:40]:
        fin = r["ebitda"] or r["sde"]
        fins = f"${fin/1e6:.1f}M" if fin else "-"
        print(f"  #{r['id']} [{(r['broker'] or '')[:24]:24}] {(r['business_name'] or '')[:46]:46} {fins:>8}")


def cmd_migrate(args):
    print(f"Migrate: {db.migrate(_conn())}")


def cmd_enrich_plan(args):
    from .enrich import plan
    p = plan(_conn())
    print("ENRICH PLAN (dry run — no spend):")
    print(f"  relevant & not-yet-enriched listings : {p['candidates']}")
    print(f"  detail pages already cached (free)   : {p['already_cached']}")
    print(f"  NEW Firecrawl credits needed         : {p['new_firecrawl_credits']}")
    print(f"  projected Claude cost                : ${p['est_claude_usd_low']} – ${p['est_claude_usd_high']}")


def cmd_enrich(args):
    from .enrich import enrich
    print(f"Enrich: {enrich(max_usd=args.max_usd, limit=args.limit)}")


def cmd_notify(args):
    from .notify import notify
    print(f"Notify: {notify(to=args.to)}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="dsv2")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("initdb").set_defaults(func=cmd_initdb)
    sub.add_parser("seed").set_defaults(func=cmd_seed)
    pi = sub.add_parser("import-json"); pi.add_argument("file"); pi.set_defaults(func=cmd_import)
    pb = sub.add_parser("board")
    pb.add_argument("account"); pb.add_argument("--date"); pb.add_argument("--limit", type=int, default=25)
    pb.add_argument("--sections", default="in"); pb.set_defaults(func=cmd_board)
    ps = sub.add_parser("settings"); ps.add_argument("account"); ps.set_defaults(func=cmd_settings)
    psc = sub.add_parser("scrape"); psc.add_argument("broker")
    psc.add_argument("--max-usd", dest="max_usd", type=float, default=0.25); psc.set_defaults(func=cmd_scrape)
    prj = sub.add_parser("rejudge"); prj.add_argument("account")
    prj.add_argument("--limit", type=int, default=5); prj.add_argument("--max-usd", dest="max_usd", type=float, default=0.10)
    prj.set_defaults(func=cmd_rejudge)
    psa = sub.add_parser("scrape-all")
    psa.add_argument("--max-usd", dest="max_usd", type=float, default=1.00)
    psa.add_argument("--limit", type=int, default=None)
    psa.add_argument("--max-pages", dest="max_pages", type=int, default=3)
    psa.add_argument("--force", action="store_true", help="re-scrape brokers already crawled today")
    psa.add_argument("--fresh", action="store_true", help="re-fetch pages >6h old (for scheduled runs)")
    psa.set_defaults(func=cmd_scrape_all)
    prc = sub.add_parser("recent"); prc.add_argument("--hours", type=int, default=24)
    prc.add_argument("--csv", default=None); prc.set_defaults(func=cmd_recent)
    sub.add_parser("migrate").set_defaults(func=cmd_migrate)
    sub.add_parser("enrich-plan").set_defaults(func=cmd_enrich_plan)
    pen = sub.add_parser("enrich")
    pen.add_argument("--max-usd", dest="max_usd", type=float, default=1.00)
    pen.add_argument("--limit", type=int, default=None)
    pen.set_defaults(func=cmd_enrich)
    pn = sub.add_parser("notify"); pn.add_argument("--to", default=None,
        help="send only to this address (testing); default = operator allow-list")
    pn.set_defaults(func=cmd_notify)
    sub.add_parser("runs").set_defaults(func=cmd_runs)
    sub.add_parser("stats").set_defaults(func=cmd_stats)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
