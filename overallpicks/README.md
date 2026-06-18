# Overall Picks Top 100

A **synthesis** dashboard. Unlike the other five (each scrapes one source), this
one reads the latest snapshot from all five and computes a single **Conviction
Score (0–100)** ranking which stocks have the strongest confluence of bullish
signals — i.e. the highest probability of continuing higher.

## How the score works (v3 — options-led, 2026-06)

```
base       = 100 × Σ_{list L present}  weight_L × signalStrength_L   (decayed credit)
confluence = 1 + 0.18 × (effBreadth − 1)        # soft breadth incl. decayed lists
kicker     = flow × fresh                        # targeted options-led bonuses
ConvictionScore = min(100, base × confluence × kicker)
```

Each list contributes weighted points scaled by how strong the stock's signal is
*within that list* (percentile rank, so raw-metric scales don't matter). The base
is multiplied by a **confluence bonus** (more lists → higher) and then by two
**targeted kickers**.

| Source list | Signal captured | Weight (v3) | v2 |
|---|---|---|---|
| Webull Options Total Volume 100 | **bullish/bearish positioning (P/C Vol + P/C OI) + option volume** | **24** ↑ | 18 |
| Webull 52-Week New High | breakout: near 52w high, freshness, day strength | **22** | 24 |
| Webull Top Gainers (1M) | sustained 1-month momentum | **22** | 24 |
| Webull Most Active | participation: turnover/volume + up-day | **18** | 18 |
| Barchart Top 100 | trend: weighted-alpha + rank climb + day strength | **14** | 16 |

**Options signal** now leads with directionality: `0.30·optionVol + 0.45·bias +
0.25·dayChange`, where `bias` blends **P/C Vol (0.6)** and **P/C OI (0.4)** — a
call-heavy name scores high, a put-heavy one is discounted.

**Confluence multiplier:** effBreadth 1 → ×1.00 … 5 → ×1.72 (uses the decayed
"soft" breadth so a one-day list drop doesn't whipsaw the score).

**Kickers (options-led):**
- **Flow ×1.15** — on the **Options *and* Most-Active** lists *and* bullishly
  positioned (`opt_bias ≥ 0.55`). Options flow meeting real trading volume.
- **Fresh ×1.15** — appearing for the **first time today on 3+ lists at once**
  (`new_count ≥ 3`) — the multi-list breakouts where options-led moves start.
  The two stack (e.g. a fresh, bullish OPT+ACT name ⇒ ×1.32).

`breadth`/`lists` stay factual (lists present today); a recently-dropped list
shows as a dashed `~CODE` **consolidating** badge carrying decayed credit. The
OPT badge is tinted **green (bullish) / red (bearish)** by its P/C read.

### Tuning & auditing
All knobs live in the **`TUNABLE KNOBS`** block at the top of `scraper.py`
(`FEEDS` weights, `CONFLUENCE_BONUS`, `MEMBERSHIP_DECAY`/`WINDOW`, `FLOW_BONUS`,
`FRESH_BONUS`/`FRESH_MIN_LISTS`, `SCORE_CAP`, `HISTORY_DAYS_IN_JS`). Every output
row carries audit columns `base_score`, `conf_mult`, `score_v1`, `eff_breadth`,
`opt_bias`, `new_count`, `kicker`, and `carried_lists`. After changing a knob,
run `python3 scraper.py --backfill` to restate the whole history consistently.

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
