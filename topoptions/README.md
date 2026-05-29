# Webull Options Total Volume 100 — Daily Movement Dashboard

Interactive dashboard that tracks the daily rank of the top 100 underlyings on
[Webull's Options Total Volume](https://www.webull.com/quote/us/options/total-volume) —
ranked by total options volume across all expiration dates traded in the
current session.

## Files

| File | Purpose |
|---|---|
| `scraper.py` | Fetches today's top 100 from Webull's public options-ranking API and appends to `data.csv`. Also regenerates `data.js` (a JSON bundle the dashboard loads directly, so the HTML works from `file://` without a server). |
| `data.csv` | Long-format history — one row per (date × rank). Authoritative record. |
| `data.js` | Auto-generated. Read by `dashboard.html`. Do not edit by hand. |
| `dashboard.html` | Self-contained dashboard. Open in any browser. |
| `run_daily.sh` | Weekday cron/launchd entry point. Skips weekends, logs to `logs/`. |
| `com.topoptions.daily.plist` | macOS launchd job, runs `run_daily.sh` at 4:05 PM on weekdays. |
| `serve.py` | Optional local static server (port 8767). |

## Usage

```bash
# One-time install (nothing to install — stdlib only)
python3 scraper.py          # pulls today's snapshot
open dashboard.html         # view the dashboard

# Automate (macOS, launchd — recommended, 4:05 PM every weekday)
cp com.topoptions.daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.topoptions.daily.plist

# Reload after editing the plist
launchctl unload ~/Library/LaunchAgents/com.topoptions.daily.plist
cp com.topoptions.daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.topoptions.daily.plist

# Run now (test it fires correctly)
launchctl start com.topoptions.daily

# Automate (any Unix, cron — alternative)
crontab -e
# Then add:
5 16 * * 1-5  "/Users/cnguyen/Claude/Local Apps/topoptions/run_daily.sh"
```

## Dashboard features

- **Summary tiles** — last updated timestamp, symbols that moved up / down /
  stayed the same / newly entered / dropped, days of history tracked.
- **Notable movements** — top 5 rank gainers, top 5 rank decliners, new
  entries, and symbols that dropped out of the top 100 since the previous
  snapshot.
- **10-day rank trajectory** — full-width D3 line chart. Y-axis is rank 1–100
  with 1 (highest options volume) on top. X-axis is the day. Each symbol is
  drawn as its ticker text (no dots) and colored with a stable hue across the
  window. Click a symbol to isolate it; Esc or click empty area to reset.
  Hover for details. Date and movement filters apply on top.
- **Sortable detail table** — Rank No., Symbol, Name, Movement chip
  (▲ green / ▼ red / — grey / ★ NEW), Options Volume, Open Interest, P/C Vol
  (put/call volume ratio — green when calls dominate, red when puts dominate),
  P/C OI (put/call open-interest ratio), Last Price, % Change, Stock Volume,
  High, Low, % Range, Market Cap. Rows are tinted by movement direction.
  Click any header to sort.

## Notes on the scraper

- No third-party packages; uses only the standard library.
- Calls Webull's `quotes-gw.webullfintech.com/api/wlas/option/rank/list`
  endpoint directly — same one the website uses, no auth required.
- If the same calendar date is scraped twice, the later run overwrites the
  earlier row — safe to re-run within the day.
- Re-running after market close gives the most stable ranking.

## Field mapping (Webull JSON → CSV)

The API returns a `data[]` array, each element a `{ticker, values}` object.
`ticker` is the underlying's quote; `values` is the aggregated options data
across all expirations.

| CSV column | Webull field | Notes |
|---|---|---|
| `rank` | order in API response | 1 = highest options total volume |
| `symbol` | `ticker.symbol` | underlying ticker |
| `name` | `ticker.name` | |
| `option_volume` | `values.volume` | total options contracts traded today |
| `open_interest` | `values.position` | total open interest across expirations |
| `vol_pc_ratio` | `values.volumeCallPutRatio` | puts÷calls on today's volume — **the API field is misnamed**; the value matches Webull's website "P/C Vol Ratio" |
| `oi_pc_ratio` | `values.positionCallPutRatio` | puts÷calls on open interest — same misnomer; matches "P/C Open Int Ratio" on the site |
| `last_price` | `ticker.close` | underlying last price |
| `percent_change` | `ticker.changeRatio × 100` | API returns a decimal |
| `stock_volume` | `ticker.volume` | shares of the underlying traded |
| `high` | `ticker.high` | session high (underlying) |
| `low` | `ticker.low` | session low (underlying) |
| `percent_range` | `ticker.vibrateRatio × 100` | (high − low) / prev close |
| `market_cap` | `ticker.marketValue` | blank for indexes / ETFs |
