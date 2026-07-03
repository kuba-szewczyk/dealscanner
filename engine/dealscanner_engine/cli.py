"""dsv2 CLI — foundation commands for v2.

  dsv2 initdb                 create the SQLite schema
  dsv2 seed                   seed accounts + editable settings from thesis/*.yaml
  dsv2 import-json <file>     migrate v1 Sheet rows (JSON list) into listings
  dsv2 board <account>        apply the account's CURRENT settings -> ranked board
  dsv2 settings <account>     print the account's live settings
  dsv2 scrape-all [--fresh]   scrape every broker (daily pipeline)
  dsv2 notify [--date D]      email the daily digest (doubles as heartbeat)
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


def cmd_scrape_all(args):
    from .pipeline import scrape_all
    for r in scrape_all(max_usd=args.max_usd, fresh=args.fresh):
        print(f"  {r}")


def cmd_notify(args):
    from .pipeline import digest
    print(f"Digest sent via {digest(date=args.date)}")


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
    psa = sub.add_parser("scrape-all"); psa.add_argument("--fresh", action="store_true")
    psa.add_argument("--max-usd", dest="max_usd", type=float, default=0.25); psa.set_defaults(func=cmd_scrape_all)
    pn = sub.add_parser("notify"); pn.add_argument("--date"); pn.set_defaults(func=cmd_notify)
    prj = sub.add_parser("rejudge"); prj.add_argument("account")
    prj.add_argument("--limit", type=int, default=5); prj.add_argument("--max-usd", dest="max_usd", type=float, default=0.10)
    prj.set_defaults(func=cmd_rejudge)
    sub.add_parser("runs").set_defaults(func=cmd_runs)
    sub.add_parser("stats").set_defaults(func=cmd_stats)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
