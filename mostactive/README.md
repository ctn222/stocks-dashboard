# Webull Most Active 100 — Daily Movement Dashboard

Interactive dashboard that tracks the daily volume rank of the top 100 stocks
on [Webull's Most Active by Volume](https://www.webull.com/quote/us/actives/volume).

## Files

| File | Purpose |
|---|---|
| `scraper.py` | Fetches today's top 100 from Webull's public quotes API and appends to `data.csv`. Also regenerates `data.js` (a JSON bundle the dashboard loads directly, so the HTML works from `file://` without a server). |
| `data.csv` | Long-format history — one row per (date × rank). Authoritative record. |
| `data.js` | Auto-generated. Read by `dashboard.html`. Do not edit by hand. |
| `dashboard.html` | Self-contained dashboard. Open in any browser. |
| `run_daily.sh` | Weekday cron/launchd entry point. Skips weekends, logs to `logs/`. |
| `com.mostactive.daily.plist` | macOS launchd job, runs `run_daily.sh` at 4:05 PM on weekdays. |
| `serve.py` | Optional local static server (port 8766). |

## Usage

```bash
# One-time install (nothing to install — stdlib only)
python3 scraper.py          # pulls today's snapshot
open dashboard.html         # view the dashboard

# Automate (macOS, launchd — recommended, 4:05 PM every weekday)
cp com.mostactive.daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.mostactive.daily.plist

# Reload after editing the plist
launchctl unload ~/Library/LaunchAgents/com.mostactive.daily.plist
cp com.mostactive.daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.mostactive.daily.plist

# Run now (test it fires correctly)
launchctl start com.mostactive.daily

# Automate (any Unix, cron — alternative)
crontab -e
# Then add:
5 16 * * 1-5  "/Users/cnguyen/Claude/Local Apps/mostactive/run_daily.sh"
```

## Dashboard features

- **Summary tiles** — last updated timestamp, stocks that moved up / down /
  stayed the same / newly entered / dropped, days of history tracked.
- **Notable movements** — top 5 rank gainers, top 5 rank decliners, new
  entries, and symbols that dropped out of the top 100 since the previous
  snapshot.
- **10-day rank trajectory** — full-width D3 line chart. Y-axis is rank 1–100
  with 1 (highest volume) on top. X-axis is the day. Each symbol is drawn as
  its ticker text (no dots) and colored with a stable hue across the window.
  Click a symbol to isolate it; Esc or click empty area to reset. Hover for
  details. Date and movement filters apply on top.
- **Sortable detail table** — Rank No., Symbol, Name, Movement chip
  (▲ green / ▼ red / — grey / ★ NEW), Volume, % Change, Last Price, High,
  Low, % Range, % Turnover, Market Cap. Rows are tinted by movement
  direction. Click any header to sort.

## Notes on the scraper

- No third-party packages; uses only the standard library.
- Calls Webull's `quotes-gw.webullfintech.com/api/wlas/ranking/topActive`
  endpoint directly — same one the website uses, no auth required.
- If the same calendar date is scraped twice, the later run overwrites the
  earlier row — safe to re-run within the day.
- Re-running after market close gives the most stable ranking.

## Field mapping (Webull JSON → CSV)

| CSV column | Webull field | Notes |
|---|---|---|
| `rank` | order in API response | 1 = highest volume |
| `symbol` | `ticker.symbol` | |
| `name` | `ticker.name` | |
| `volume` | `ticker.volume` | shares traded |
| `percent_change` | `ticker.changeRatio × 100` | API returns a decimal |
| `last_price` | `ticker.close` | |
| `high` | `ticker.high` | session high |
| `low` | `ticker.low` | session low |
| `percent_range` | `ticker.vibrateRatio × 100` | (high − low) / prev close |
| `percent_turnover` | `ticker.turnoverRate` | already a percent |
| `market_cap` | `ticker.marketValue` | |
