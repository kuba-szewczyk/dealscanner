#!/usr/bin/env bash
# Daily pipeline: scrape (change-detected), enrich, email the digest. The digest email is the
# human heartbeat; healthchecks.io is the machine one. We signal START, then SUCCESS or FAIL, so
# a long-but-successful run (a full sweep can take ~an hour) is NOT mistaken for an outage —
# healthchecks only alarms if the run doesn't COMPLETE, not if it runs long.
set -euo pipefail
cd /opt/dealscanner-v2

# ping the dead-man switch; $1 is the endpoint suffix ("/start", "/fail", or "" for success).
hc() {
    [ -n "${HEALTHCHECK_URL:-}" ] || return 0
    curl -fsS -m 10 --retry 3 "${HEALTHCHECK_URL}${1:-}" >/dev/null 2>&1 || true
}
trap 'hc /fail' ERR
hc /start

DSV2=engine/.venv/bin/dsv2
# scrape-all only pays the LLM for pages whose listings actually changed (fingerprint skip),
# so most days are cheap; enrich fills financials on newly-qualifying deals. Both spend-capped.
$DSV2 scrape-all --fresh --max-usd "${SCRAPE_MAX_USD:-8.00}"
$DSV2 enrich --max-usd "${ENRICH_MAX_USD:-3.00}"
$DSV2 notify

hc   # success
