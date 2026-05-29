# Barchart Top 100 — Daily Movement Dashboard

Interactive dashboard that tracks daily rank movement for the top 100 stocks on
[Barchart's Top 100 Stocks](https://www.barchart.com/stocks/top-100-stocks)
(ranked by Weighted Alpha, advances).

## Files

| File | Purpose |
|---|---|
| `scraper.py` | Fetches today's top 100 from Barchart's internal API and appends to `data.csv`. Also regenerates `data.js` (a JSON bundle the dashboard loads directly, so the HTML works from `file://` without a server). |
| `data.csv` | Long-format history — one row per (date × rank). Authoritative record. |
| `data.js` | Auto-generated. Read by `dashboard.html`. Do not edit by hand. |
| `dashboard.html` | Self-contained dashboard. Open in any browser. |
| `run_daily.sh` | Weekday cron/launchd entry point. Skips weekends, logs to `logs/`. |
| `com.barchart100.daily.plist` | macOS launchd job, runs `run_daily.sh` at 4:05 PM on weekdays. |

## Usage

```bash
# One-time install (nothing to install — stdlib only)
python3 scraper.py          # pulls today's snapshot
open dashboard.html         # view the dashboard

# Automate (macOS, launchd — recommended, 4:05 PM every weekday)
cp com.barchart100.daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.barchart100.daily.plist

# Reload after editing the plist
launchctl unload ~/Library/LaunchAgents/com.barchart100.daily.plist
cp com.barchart100.daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.barchart100.daily.plist

# Run now (test it fires correctly)
launchctl start com.barchart100.daily

# Automate (any Unix, cron — alternative)
crontab -e
# Then add:
5 16 * * 1-5  "/Users/cnguyen/Claude/Local Apps/barchart100/run_daily.sh"
```

## Dashboard features

- **Summary tiles** — last updated timestamp, stocks that moved up / down /
  stayed the same / newly entered, days of history tracked.
- **Notable movements** — top 5 gainers, top 5 decliners, new entries, and
  symbols that dropped out of the top 100 since the previous snapshot.
- **10-day rank trajectory** — full-width D3 line chart. Y-axis is rank 1–100
  with 1 on top. Each symbol is drawn as its ticker text (no dots) and colored
  with a stable hue. Click a symbol to isolate it; Esc or click empty area to
  reset. Hover for details.
- **Sortable detail table** — rank, symbol, movement chip (▲ green / ▼ red /
  — grey / ★ new), name, prev rank, last price, 52W high, % from high. Rows
  are tinted by movement direction.

## Notes on the scraper

- No third-party packages; uses only the standard library.
- Calls Barchart's own `core-api/v1/quotes/get` endpoint with the same
  `XSRF-TOKEN` cookie the site uses (primed by fetching the top-100 page once
  per run). No login required.
- If the same calendar date is scraped twice, the later run overwrites the
  earlier row — safe to re-run within the day.
- Re-running after market close gives the most stable ranking.
