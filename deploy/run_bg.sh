#!/bin/bash
# Run a dsv2 engine job FULLY DETACHED from the SSH session.
# Long jobs (scrape-all, enrich) used to drop the SSH connection at the end -> ssh exit 255.
# setsid + nohup + closed stdio detach the job from the session, so SSH returns immediately
# (exit 0) and the job runs to completion regardless of the connection. Poll the log/DB.
#
# Usage:  run_bg.sh enrich --max-usd 7.00
#         run_bg.sh scrape-all --max-usd 4.00
cd /opt/dealscanner-v2/engine || exit 1
TS=$(date +%Y%m%d_%H%M%S)
LOG="/opt/dealscanner-v2/data/job_${1}_${TS}.log"
setsid nohup .venv/bin/python -m dealscanner_engine.cli "$@" > "$LOG" 2>&1 < /dev/null &
PID=$!
echo "started '$*' as PID $PID"
echo "log: $LOG"
