#!/usr/bin/env bash
# Daily pipeline: scrape everything fresh, email the digest, ping the dead-man
# switch. The digest email is the human heartbeat; the healthchecks.io ping is
# the machine one — if either goes quiet, the pipeline didn't run.
set -euo pipefail
cd /opt/dealscanner-v2

DSV2=engine/.venv/bin/dsv2
$DSV2 scrape-all --fresh
$DSV2 notify

# HEALTHCHECK_URL comes from .env (systemd EnvironmentFile). Optional but wanted:
# v2 died silently for days because nothing alerted on a missed run.
if [ -n "${HEALTHCHECK_URL:-}" ]; then
    curl -fsS -m 10 --retry 3 "$HEALTHCHECK_URL" >/dev/null
fi
