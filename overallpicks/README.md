# Overall Picks Top 100

A **synthesis** dashboard. Unlike the other five (each scrapes one source), this
one reads the latest snapshot from all five and computes a single **Conviction
Score (0–100)** ranking which stocks have the strongest confluence of bullish
signals — i.e. the highest probability of continuing higher.

## How the score works (v2 — confluence-weighted, 2026-06)

```
base       = 100 × Σ_{list L the stock is on}  weight_L × signalStrength_L
confluence = 1 + 0.18 × (breadth − 1)             # breadth = # of lists
ConvictionScore = min(100, base × confluence)
```

Each list contributes weighted points scaled by how strong the stock's signal is
*within that list* (measured as a percentile rank, so raw-metric scales don't
matter). The whole base is then multiplied by a **confluence bonus** that grows
with how many lists the stock appears on — so a stock showing strong momentum
across **multiple** live-attention lists is pushed well above one that merely
ranks high on a single list.

| Source list | Signal captured | Weight (v2) | was (v1) |
|---|---|---|---|
| Webull 52-Week New High | breakout: near 52w high, freshness, day strength | **24** | 25 |
| Webull Top Gainers (1M) | sustained 1-month momentum | **24** | 25 |
| Webull Most Active | participation: turnover/volume + up-day | **18** ↑ | 15 |
| Webull Options Total Volume 100 | positioning: call-heavy put/call + option volume | **18** ↑ | 15 |
| Barchart Top 100 | trend: weighted-alpha + rank climb + day strength | **16** ↓ | 20 |

**Confluence multiplier:** breadth 1 → ×1.00, 2 → ×1.18, 3 → ×1.36,
4 → ×1.54, 5 → ×1.72.

**Why v2:** the four live-attention/momentum lists (New High, Gainers, Active,
Options) now carry the bulk of the weight, Barchart is kept only as a slower
trend confirmation, and the confluence multiplier explicitly rewards stocks
that light up across several lists at once.

`breadth` = how many of the five lists the stock is on. Index/ETF tickers (e.g.
SPY) that only show on Active/Options with neutral signals naturally score low.

### Tuning & auditing
All knobs live in the **`TUNABLE KNOBS`** block at the top of `scraper.py`
(`FEEDS` weights, `CONFLUENCE_BONUS`, `SCORE_CAP`, `HISTORY_DAYS_IN_JS`). Every
output row also carries `base_score`, `conf_mult`, and `score_v1` so you can
compare the new ranking against the old one on identical data.

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
