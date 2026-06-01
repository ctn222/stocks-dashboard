# Overall Picks Top 100

A **synthesis** dashboard. Unlike the other five (each scrapes one source), this
one reads the latest snapshot from all five and computes a single **Conviction
Score (0–100)** ranking which stocks have the strongest confluence of bullish
signals — i.e. the highest probability of continuing higher.

## How the score works

```
ConvictionScore(stock) = 100 × Σ_{list L the stock is on}  weight_L × signalStrength_L
```

Each list contributes weighted points scaled by how strong the stock's signal is
*within that list* (measured as a percentile rank, so raw-metric scales don't
matter). A stock only reaches the top by appearing — strongly — on **multiple**
lists (confluence). A single-list appearance is capped at that list's weight.

| Source list | Signal captured | Weight |
|---|---|---|
| Webull 52-Week New High | breakout: near 52w high, freshness, day strength | 25 |
| Webull Top Gainers (1M) | sustained 1-month momentum | 25 |
| Barchart Top 100 | trend: weighted-alpha + rank climb + day strength | 20 |
| Webull Most Active | participation: turnover/volume + up-day | 15 |
| Webull Options Total Volume 100 | positioning: call-heavy put/call + option volume | 15 |

`Signals` (breadth) = how many of the five lists the stock is on. A perfect
**5/5** with maximal signals approaches 100. Index/ETF tickers (e.g. SPY) that
only show on Active/Options with neutral signals naturally score low.

> This is a heuristic momentum/confluence screen, **not** investment advice.

## Run it

```bash
# Must run AFTER the five source scrapers have refreshed today's data.
python3 scraper.py            # writes data.csv (history) + data.js
python3 serve.py              # standalone view at http://127.0.0.1:8775/dashboard.html
```

In the cloud, GitHub Actions runs this **last** in the daily job so it always
reads fresh source data. It appears as the featured first panel in the combined
`dashboard.html`.

## Files
- `scraper.py` — the aggregator (pure stdlib; reads the five sibling `data.csv`s)
- `data.csv` — full daily history of the top-100 picks
- `data.js` — `window.WEBULL_DATA` consumed by the dashboards
- `dashboard.html` — standalone view
- `serve.py` — local static server (port 8775)
