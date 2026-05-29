# Webull 52 Week New High — Daily Movement Dashboard

Tracks the daily ranking for [Webull 52 Week New High](https://www.webull.com/quote/us/52whl).

## Files

| File | Purpose |
|---|---|
| `scraper.py` | Fetches today's snapshot, appends to `data.csv`, regenerates `data.js`. **You must customize the API_URL and field accessors.** |
| `data.csv` | Long-format history (one row per `date × rank`). |
| `data.js` | Auto-generated JSON bundle read by the dashboard. |
| `dashboard.html` | Self-contained standalone dashboard. |
| `run_daily.sh` | Weekday cron/launchd entry point. |
| `com.52weeknewhigh.daily.plist` | macOS launchd job (4:05 PM weekdays). |
| `serve.py` | Optional dev server on port 8773. |

## First-time setup

1. **Customize the scraper.** Open `scraper.py` and set the `API_URL` and the
   field accessors in `append_to_csv()` to match the JSON returned by the
   data source. Tip: in Chrome on https://www.webull.com/quote/us/52whl, open DevTools → Network → XHR,
   reload, and look for the JSON endpoint the page calls. Copy that URL into
   `API_URL`. If the page is server-side-rendered with no XHR, scrape the
   inline `__initState__` JSON instead (see `52weeknewhigh/scraper.py` for an
   example).
2. **Run once to populate `data.csv` and `data.js`:**
   ```bash
   python3 scraper.py
   ```
3. **Open the standalone dashboard:**
   ```bash
   open dashboard.html
   ```
   Or use the dev server: `python3 serve.py` then visit
   <http://127.0.0.1:8773/dashboard.html>.
4. **The combined "Daily Stocks Data" page** (one level up) already has an
   entry for this project — open `../dashboard.html` to see it alongside the
   others. Tweak the column list / tooltip in `../dashboard.html`'s
   `PROJECT_CONFIGS.52weeknewhigh` block if your fields differ from the
   defaults.

## Automate (macOS)

```bash
cp com.52weeknewhigh.daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.52weeknewhigh.daily.plist
launchctl start com.52weeknewhigh.daily   # one-shot test
```

## Re-running

The same calendar date is overwritten on re-run, so it's safe to scrape
multiple times per day — only the latest snapshot for each date is kept.
