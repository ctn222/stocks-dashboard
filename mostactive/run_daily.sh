#!/usr/bin/env bash
# Daily runner for the Webull Most Active 100 dashboard.
#
# - Skips weekends (US market closed).
# - Runs scraper.py, which appends today's snapshot to data.csv and rewrites data.js.
# - Logs stdout/stderr to logs/run_YYYY-MM-DD.log, rotating automatically by date.
# - Exits non-zero on failure so cron/launchd can surface the error.
#
# Install as a weekday cron job (example: 4:05 PM ET each weekday):
#   crontab -e
#   5 16 * * 1-5  "/Users/cnguyen/Claude/Local Apps/mostactive/run_daily.sh"
#
# Or as a macOS launchd job — see com.mostactive.daily.plist (sibling file).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

mkdir -p logs
TODAY="$(date +%Y-%m-%d)"
LOG="logs/run_${TODAY}.log"
DOW="$(date +%u)"   # 1=Mon … 7=Sun

{
  echo "=========================================="
  echo "Webull Most Active 100 daily run — $(date)"
  echo "=========================================="

  if [[ "$DOW" -ge 6 ]]; then
    echo "Weekend (dow=$DOW). Skipping — US market closed."
    exit 0
  fi

  PY="${PYTHON:-python3}"
  echo "Using: $($PY --version 2>&1) at $(command -v $PY)"

  "$PY" scraper.py
  echo "Done."
} >>"$LOG" 2>&1
