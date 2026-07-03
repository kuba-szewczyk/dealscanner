#!/usr/bin/env bash
# Daily pipeline: scrape everything fresh, email the digest, ping the dead-man
# switch. The digest email is the human heartbeat; the healthchecks.io ping is
# the machine one — if either goes quiet, the pipeline didn't run.
set -euo pipefail
cd /opt/dealscanner-v2

DSV2=engine/.venv/bin/dsv2
# Production flow (from the recovered v2.5 cron): scrape every live broker fresh,
# enrich newly-qualifying deals with financials, then email the per-thesis digest.
# Both AI stages are spend-capped; caps are reviewed in deploy/README.md.
$DSV2 scrape-all --fresh --max-usd "${SCRAPE_MAX_USD:-5.00}"
$DSV2 enrich --max-usd "${ENRICH_MAX_USD:-3.00}"
$DSV2 notify

# HEALTHCHECK_URL comes from .env (systemd EnvironmentFile). Optional but wanted:
# v2 died silently for days because nothing alerted on a missed run.
if [ -n "${HEALTHCHECK_URL:-}" ]; then
    curl -fsS -m 10 --retry 3 "$HEALTHCHECK_URL" >/dev/null
fi
