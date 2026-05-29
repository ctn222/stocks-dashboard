# Barchart Top 100 — Project Template Description

A complete reference for replicating this project structure for a new **Webull Top Gainers (1M)** tracker.

---

## 1. Project Architecture Overview

A self-contained, **stdlib-only** Python scraper + **single-file HTML dashboard** that tracks daily rank movement of a top-N stock list. No frameworks, no build step, no third-party packages. Runs daily via macOS `launchd` (or cron), persists history to a long-format CSV, and renders an interactive D3 dashboard that works from `file://`.

**Key design principles:**
- **Zero dependencies** — Python stdlib only; D3 loaded from CDN in the browser.
- **File-based** — CSV is the authoritative store; a generated `data.js` bundle lets the HTML run without a web server (avoids CORS on `file://`).
- **Idempotent daily run** — re-running the same day overwrites that day's snapshot.
- **Weekday-only** — skips weekends automatically.
- **Self-documenting logs** — one log file per day under `logs/`.

---

## 2. File Inventory

| File | Purpose |
|---|---|
| `scraper.py` | Fetches the daily list, appends to `data.csv`, regenerates `data.js`. |
| `data.csv` | Long-format history (one row per `date × rank`). Authoritative. |
| `data.js` | Auto-generated JSON bundle. `window.DATA = [...]`. Read by `dashboard.html`. |
| `dashboard.html` | Self-contained dashboard (HTML + CSS + JS in one file). |
| `run_daily.sh` | Cron/launchd entry point. Skips weekends, logs to `logs/`. |
| `com.<project>.daily.plist` | macOS launchd job. |
| `serve.py` | Optional local dev server (the `.claude/launch.json` references it). |
| `.claude/launch.json` | Editor launch config for the dev server. |
| `README.md` | Usage + automation install instructions. |
| `logs/run_YYYY-MM-DD.log` | Per-day run log (auto-rotated by date). |

---

## 3. Scraper (`scraper.py`) — Implementation Pattern

**For the Barchart project**, the scraper:
1. Primes a session at the public page URL to receive `laravel_session` + `XSRF-TOKEN` cookies (uses `http.cookiejar.MozillaCookieJar`).
2. URL-decodes the XSRF token and sends it as the `x-xsrf-token` header on the JSON API call to `core-api/v1/quotes/get`.
3. Parses `payload["data"]` (already ordered by `weightedAlpha desc`, limit 100).
4. Appends today's snapshot to `data.csv`, replacing any existing row with the same `snapshot_date`.
5. Rewrites `data.js` from the full CSV history.

**Key constants:**
```python
PAGE_URL = "https://www.barchart.com/stocks/top-100-stocks"
API_URL  = "https://www.barchart.com/proxies/core-api/v1/quotes/get"
LIST_ID  = "stocks.us.weighted_alpha.advances"
FIELDS   = "symbol,symbolName,lastPrice,percentChange,highPrice1y,weightedAlpha,previousRank,tradeTime"
LIMIT    = 100
UA       = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

CSV_COLUMNS = [
  "snapshot_date", "snapshot_time", "rank", "previous_rank",
  "symbol", "name", "last_price", "percent_change",
  "high_52w", "weighted_alpha",
]
```

**Helper functions:**
- `to_float(val)` / `to_int(val)` — strip `,`, `+`, `%`; return `None` on failure.
- `append_to_csv(rows, snapshot_dt, trade_time)` — reads existing CSV, drops same-date rows, writes back with new rows appended.
- `write_js_bundle()` — reads CSV → emits `data.js` with `window.GENERATED_AT` and `window.DATA`.

### Webull-specific considerations for the new project

Webull's gainers page (`https://www.webull.com/quote/us/gainers/1m`) is **client-side rendered** — a plain `urllib` GET will return mostly empty HTML. Three options, in increasing complexity:

1. **Reverse-engineer their internal API** (mirror what we did with Barchart). Open Chrome DevTools → Network → XHR while loading the page. Look for a JSON endpoint like `https://quotes-gw.webullbroadmarket.com/api/bgw/market/topGainers?...` (Webull's actual endpoint pattern). Note the headers it sends — Webull historically requires `app: desktop`, `did: <device-id>`, `t_token`, etc. Once you have the URL + required headers, the rest of the scraper structure is identical to Barchart's.
2. **Use a headless browser** (Playwright). Breaks the "stdlib only" constraint but is the most robust if the API has aggressive bot detection.
3. **Use Apify or a similar scraping service**. Slowest path, but works without API spelunking.

**Recommended:** start with option 1. Webull's API is well-known to be open and JSON-based. Map the fields:

| Your field | Likely Webull JSON key |
|---|---|
| ranking | array index + 1 |
| symbol | `ticker.symbol` or `disSymbol` |
| name | `ticker.name` or `disName` |
| % chg 1M | `change` / `changeRatio` (verify it's the 1M variant) |
| last price | `close` or `price` |
| high | `high` (intraday) — for **1M high** you'll need a separate call |
| low | `low` — same caveat |
| volume | `volume` |
| % range | derived: `(close - low) / (high - low)` (compute in scraper) |
| P/E | `pe` or `peTtm` |
| market cap | `marketValue` or `mktCap` |

**Adjusted CSV columns for the new project:**
```python
CSV_COLUMNS = [
  "snapshot_date", "snapshot_time", "rank", "previous_rank",
  "symbol", "name", "pct_change_1m", "last_price",
  "high", "low", "volume", "pct_range",
  "pe_ratio", "market_cap",
]
```

---

## 4. Daily Runner (`run_daily.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
mkdir -p logs
TODAY="$(date +%Y-%m-%d)"
LOG="logs/run_${TODAY}.log"
DOW="$(date +%u)"   # 1=Mon … 7=Sun
{
  echo "=========================================="
  echo "<Project> daily run — $(date)"
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
```

---

## 5. macOS launchd plist (`com.<project>.daily.plist`)

Schedule: weekday 4:05 PM ET (after market close). Install pattern:
```bash
cp com.<project>.daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.<project>.daily.plist
launchctl start com.<project>.daily   # run now to test
```

The plist uses `<key>StartCalendarInterval</key>` with an **array of dicts**, one per weekday (Mon–Fri = `Weekday` 1–5), each with `Hour=16` `Minute=5`. Set `WorkingDirectory` to the project dir and `StandardOutPath`/`StandardErrorPath` to `logs/launchd.out` / `logs/launchd.err`.

---

## 6. Dashboard (`dashboard.html`) — Feature Inventory

A single self-contained HTML file. Loads `data.js` via `<script src="data.js">` (so `file://` works), then D3 v7 from CDN.

### 6.1 Layout
1. **Header bar** — title, last-updated timestamp, light/dark theme toggle (persists in `localStorage` under a `<project>-theme` key).
2. **Summary tiles row** (5 tiles, all clickable): Moved Up, Moved Down, No Change, New Entries, Dropped — each with a count badge and `data-tile` attribute.
3. **Notable movements panels** (4 columns): Top 5 Gainers, Top 5 Decliners, New to Top 100 (up to 10), Dropped from Top 100 (up to 10). Each list contains clickable `.chip` elements with `data-symbol`.
4. **10-Day Rank Trajectory chart** — full-width D3 line chart with filter bar.
5. **Daily detail table** — sortable, with movement chips (▲/▼/—/★).

### 6.2 Theming
CSS custom properties on `:root` and `[data-theme="dark"]`:
```css
:root {
  --bg: #f7f7f9;
  --panel: #ffffff;
  --text: #1a1a1a;
  --muted: #6b7280;
  --up: #16a34a;
  --down: #dc2626;
  --same: #6b7280;
  --new: #d97706;
  --accent: #2563eb;
  --border: #e5e7eb;
  --chip-bg: #f3f4f6;
}
[data-theme="dark"] {
  --bg: #0b0d12;
  --panel: #151821;
  --text: #e5e7eb;
  /* … */
}
```
Toggle button writes `document.documentElement.dataset.theme = "dark" | "light"` and `localStorage.setItem`.

### 6.3 D3 Chart Implementation
- **Y-axis:** rank, domain `[0.5, 100.5]`, **inverted** (rank 1 on top), gridlines at `[1, 10, 20, …, 100]`.
- **X-axis:** `d3.scalePoint` over the dates in the visible window.
- **Lines:** one path per symbol, drawn through the rank points where it appears. Symbol's ticker is rendered as text at the latest visible point (no dots).
- **Color:** stable hash from `d3.interpolateSinebow` keyed on the **full 10-day window's symbol union** (built once, so colors don't shift when filters narrow the set).
- **Container is responsive:** redraw on `window.resize`, debounced.

### 6.4 Chart Filter Bar
Two `<select>` elements above the chart:
- **Date filter:** `all` (default, full 10-day view) or one specific date (single-day view — collapses chart to that column, shows just the points/labels for that day).
- **Movement filter:** `all` / `up` / `down` / `same` / `new`. Filters which symbols are included in the chart.

`getVisibleDates()` and `classifySymbol(sym, dateValue)` helpers compute the visible set on every render.

### 6.5 Click Interactions (Highlight State Machine)
**State:**
```js
let highlightedSyms = new Set();   // multi-symbol isolation
let activeTile = null;             // currently-active tile id, or null
```

**Behaviors:**
- **Click a chart symbol label** → toggle that single symbol in `highlightedSyms`.
- **Click a `.chip[data-symbol]`** in notable-movements → toggle that symbol; clicking again un-isolates.
- **Click a `.stat[data-tile]`** summary tile → multi-symbol isolation of all symbols in that bucket, **and** snap the date filter to the latest day (or `prevDate` for the Dropped tile, since dropped symbols aren't in today's data). Re-clicking the same tile clears.
- **Esc key** → `clearHighlight()`.
- **Manually changing the date filter** → deactivates `activeTile` (but preserves `highlightedSyms`).

**`applyHighlight()`** is called at the **tail of every `renderChart()`** so isolation survives re-renders triggered by filter changes or window resizes. It reduces opacity of non-highlighted lines to ~0.12 and bolds the highlighted ones.

`TILE_BUCKETS` map (built once per render):
```js
const TILE_BUCKETS = {
  up:      { syms: enriched.filter(r => r.dir === "up").map(r => r.symbol),    date: latestDate },
  down:    { syms: enriched.filter(r => r.dir === "down").map(r => r.symbol),  date: latestDate },
  same:    { syms: enriched.filter(r => r.dir === "same").map(r => r.symbol),  date: latestDate },
  new:     { syms: enriched.filter(r => r.dir === "new").map(r => r.symbol),   date: latestDate },
  dropped: { syms: droppedRows.map(r => r.symbol),                             date: prevDate || latestDate },
};
```

### 6.6 Daily Detail Table
Columns (in order): MOVEMENT chip, WTD ALPHA (or your equivalent metric), RANK, SYMBOL, NAME, PREV RANK, LAST PRICE, 52W HIGH, % FROM HIGH. Click any header to sort. Rows are subtly tinted by movement direction.

Movement chips: `▲ green` (up), `▼ red` (down), `— grey` (same), `★ orange` (new).

### 6.7 Accessibility
All clickable elements get `tabindex="0"`, `role="button"`, and Enter/Space activation. `:focus-visible` outline follows `--accent`.

---

## 7. Translation Plan for the Webull Top Gainers Project

### 7.1 Suggested project name and paths
```
/Users/cnguyen/Claude/Local Apps/webull-gainers-1m/
  scraper.py
  data.csv
  data.js
  dashboard.html
  run_daily.sh
  com.webullgainers.daily.plist
  serve.py
  README.md
  .claude/launch.json
  logs/
```

### 7.2 Schema differences
| Barchart 100 | Webull Gainers 1M |
|---|---|
| `weighted_alpha` | `pct_change_1m` (primary sort) |
| `high_52w` | `high` + `low` (intraday, both stored) |
| (none) | `volume` |
| (none) | `pct_range` (derived: `(close - low)/(high - low)`) |
| (none) | `pe_ratio` |
| (none) | `market_cap` |

### 7.3 Dashboard sections to keep / change
**Keep verbatim** (just relabel):
- Theme toggle, layout shell, log/footer
- 5 summary tiles (Moved Up / Down / Same / New / Dropped)
- Notable movements panels (top 5 gainers, top 5 decliners, new, dropped)
- 10-day rank trajectory chart with filters
- Click-to-isolate state machine (chips + tiles)

**Adjust:**
- Page title, H1, table heading → "Webull Top Gainers (1M) — Daily Movement Dashboard"
- Sort column for "biggest gainers/decliners" → use `pct_change_1m` instead of weighted alpha
- Detail table columns → swap to: MOVEMENT, %ΔΜ (1M %), RANK, SYMBOL, NAME, PREV RANK, LAST PRICE, HIGH, LOW, VOLUME, %RANGE, P/E, MARKET CAP
- Number formatters: market cap as `$X.XXB` / `$XXX.XM`; volume as `1.23M` / `456.7K`; P/E as 2 decimals or "—"; % range as `0–100%`
- 52W-high column and "% from high" derived column → drop (replace with %Range, which is the intraday equivalent)

### 7.4 What to verify before declaring "done"
1. `python3 scraper.py` succeeds; `data.csv` has 100 rows for today; `data.js` is regenerated.
2. Open `dashboard.html` in a browser — chart renders, all 5 tiles clickable, all chips clickable, theme toggle persists.
3. Manually run `./run_daily.sh` — log is written to `logs/run_YYYY-MM-DD.log`, exit code 0.
4. `launchctl load` the plist; `launchctl start <label>` fires it; verify a fresh log appears.
5. Re-run the same day — confirm the existing day's rows are replaced, not duplicated.

### 7.5 Quick-start checklist
- [ ] Copy `barchart100/` → `webull-gainers-1m/`
- [ ] Find the Webull internal JSON endpoint via DevTools (Network tab on `/quote/us/gainers/1m`)
- [ ] Update `scraper.py`: `PAGE_URL`, `API_URL`, request headers, field mapping, `CSV_COLUMNS`
- [ ] Regenerate `data.csv` from a fresh first run (delete the Barchart copy)
- [ ] Update `dashboard.html` table columns + number formatters
- [ ] Rename plist `Label`, `WorkingDirectory`, `StandardOutPath`, `StandardErrorPath`
- [ ] Update `README.md` URLs and project name
- [ ] Update `.claude/launch.json` paths
- [ ] Install plist, run `launchctl start` to verify
- [ ] Open dashboard, click every tile/chip to verify state machine

---

## 8. Known Carry-Over TODOs (from the Barchart project)

Two items from a mid-session request were never finished — worth deciding upfront whether to include them in the new project from the start:

1. **Remove the scroll bar** from the daily detail table (`overflow:auto; max-height: 1000px`).
2. **Add a `% CHANGE` column** to the right of LAST PRICE (today's price vs prior day's price for that symbol — derived per render, not stored in CSV).

For the Webull project, the daily intraday `pct_change_1m` field already covers (2), so you may not need a derived day-over-day column. The scroll-bar question (1) is purely a CSS choice — drop the `max-height` on the table wrapper if you want the page to extend naturally.
