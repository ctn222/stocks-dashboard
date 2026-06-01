#!/usr/bin/env bash
# Daily runner for the Overall Picks Top 100 aggregator.
#
# IMPORTANT: this must run AFTER the five source scrapers (52weeknewhigh,
# topgainers1m, barchart100, mostactive, topoptions) have refreshed their data,
# because it reads their latest snapshots. In the cloud, the GitHub Actions
# workflow runs it last. Locally, run it after the others.
#
# - Skips weekends (US market closed).
# - Logs to logs/run_YYYY-MM-DD.log.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

mkdir -p logs
TODAY="$(date +%Y-%m-%d)"
LOG="logs/run_${TODAY}.log"
DOW="$(date +%u)"   # 1=Mon … 7=Sun

{
  echo "=========================================="
  echo "Overall Picks Top 100 daily run — $(date)"
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
