#!/bin/bash
# Scheduled DealScanner crawl — runs ENTIRELY on the server (no laptop).
# 1) fresh scrape of every live broker (re-fetches pages so NEW listings are found;
#    dedup-by-construction means existing listings are never duplicated),
# 2) enrich any newly-qualifying deals with real financials (idempotent — never re-does one).
# Both are spend-capped. Output appended to a dated log.
cd /opt/dealscanner-v2/engine || exit 1
LOG="/opt/dealscanner-v2/data/cron_$(date +%Y%m%d).log"
{
  echo "===================== $(date) CRAWL START ====================="
  .venv/bin/python -m dealscanner_engine.cli scrape-all --fresh --max-usd 5.00 2>&1 \
      | grep -vE "UserWarning|class Monitor"
  echo "--------------------- $(date) ENRICH ---------------------"
  .venv/bin/python -m dealscanner_engine.cli enrich --max-usd 3.00 2>&1 \
      | grep -vE "UserWarning|class Monitor"
  echo "--------------------- $(date) EMAIL ---------------------"
  .venv/bin/python -m dealscanner_engine.cli notify 2>&1 | grep -vE "UserWarning|class Monitor"
  echo "===================== $(date) CRAWL DONE ====================="
  echo
} >> "$LOG" 2>&1
