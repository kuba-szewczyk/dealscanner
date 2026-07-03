# DealScanner

AI-assisted deal sourcing for small-business acquisition. Scrapes broker listings
daily, extracts structured deals with Claude, scores them against editable
investment theses, and emails a morning digest. Live at
[dealscanner.us](https://dealscanner.us).

## How it works

```
Firecrawl (broker pages) → Claude Haiku (extraction) → SQLite (thesis-neutral store)
        → per-account scoring lens → Next.js board + daily email digest
```

- **`engine/`** — Python core (`dsv2` CLI): scraping with a hard per-run spend cap
  and disk-cached fetches, thesis-neutral listing store, instant re-ranking when
  settings change (no re-scrape), daily pipeline.
- **`api/`** — FastAPI layer: boards, live-editable settings, votes with
  full-context snapshots, passwordless magic-link auth (HMAC-signed, allow-listed).
- **`web/`** — Next.js 15 board UI.
- **`thesis/`** — the investment theses as YAML (keywords, size bands, exclusions);
  seeded into the DB, then editable live.
- **`deploy/`** — full production kit: hardening script, systemd units + timer,
  Caddy config, runbook.

## Design decisions

- **The DB is the brain.** Listings are stored once, thesis-neutrally; each
  account's settings are a lens applied at read time. Changing a keyword re-ranks
  the whole board instantly and for free.
- **Dedup by construction** — UNIQUE on normalized URL, not a fragile
  read-before-write pass.
- **Spend caps in-app.** Every AI call is metered; a run aborts before exceeding
  its budget. Total spend is one query away.
- **The digest email is the heartbeat.** It sends even on a zero-listing day, and
  the pipeline pings a dead-man switch — a silent morning means something is wrong,
  and something notices.
- **Ops hardened by lesson.** Key-only SSH, localhost-bound services behind Caddy,
  systemd everywhere, secrets only in a `chmod 600` env file.

## Running it

```bash
cd engine && uv sync --extra api --extra scrape
.venv/bin/dsv2 initdb && .venv/bin/dsv2 seed
.venv/bin/dsv2 scrape-all --fresh && .venv/bin/dsv2 notify
cd ../web && npm ci && npm run dev        # board on :3001
cd ../api && ../engine/.venv/bin/uvicorn main:app --port 8099
```

Config: copy `.env.example` → `.env` and fill in. Production setup: `deploy/README.md`.
