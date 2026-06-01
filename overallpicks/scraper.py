#!/usr/bin/env python3
"""Overall Picks Top 100 — cross-feed aggregator.

This is NOT a web scraper. It reads the latest snapshot from the five sibling
dashboards and computes a single **Conviction Score (0-100)** estimating which
stocks have the strongest confluence of bullish signals (and therefore the
highest probability of continuing higher).

It must run AFTER the five source scrapers each day. The GitHub Actions
workflow runs it last; locally, run it after the others.

Output (same shape as the other dashboards so the UI is identical):
    data.csv  — full daily history of the top-100 picks
    data.js   — window.WEBULL_DATA / window.WEBULL_GENERATED_AT

---------------------------------------------------------------------------
SCORING MODEL  (transparent, rank-percentile based, robust to outliers)
---------------------------------------------------------------------------
Each of the five lists contributes weighted points based on how strong a
stock's signal is *within that list*. A stock only reaches the top of the
Overall Picks if it shows up strong across MULTIPLE lists (confluence) — a
single-list appearance is capped at that list's weight.

    ConvictionScore(sym) = 100 * Σ_{list L present}  weight_L * signal_L(sym)

    signal_L ∈ [0,1] per list:
      52-Week New High (w=0.25, "breakout"):
          0.40*rankPct + 0.35*proximityToHigh + 0.25*pctChangePct
      Top Gainers 1M  (w=0.25, "momentum"):
          0.70*pctChange1M_pct + 0.30*rankPct
      Barchart Top100 (w=0.20, "trend"):
          0.55*weightedAlphaPct + 0.25*pctChangePct + 0.20*rankClimb
      Most Active     (w=0.15, "participation"):
          0.40*turnoverPct + 0.20*volumePct + 0.40*pctChangePct
      Options Vol 100 (w=0.15, "options"):
          0.40*optionVolPct + 0.35*callBias + 0.25*pctChangePct

`rankPct`/`*Pct` are percentile ranks within that list's latest snapshot
(so the scale of each raw metric doesn't matter). Index/ETF tickers that only
appear on the Active/Options lists with neutral signals naturally score low.
"""
from __future__ import annotations

import bisect
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
APPS = HERE.parent
CSV_PATH = HERE / "data.csv"
JS_PATH = HERE / "data.js"

# (folder, short code, weight, component-key)
FEEDS = [
    ("52weeknewhigh", "52WH", 0.25, "breakout"),
    ("topgainers1m",  "1M",   0.25, "momentum"),
    ("barchart100",   "BC",   0.20, "trend"),
    ("mostactive",    "ACT",  0.15, "participation"),
    ("topoptions",    "OPT",  0.15, "options"),
]

OUT_FIELDS = [
    "snapshot_date", "snapshot_time", "rank", "symbol", "name",
    "last_price", "percent_change", "volume", "market_cap",
    "high_52w", "pct_change_1m", "weighted_alpha",
    "score", "breadth", "lists",
    "s_breakout", "s_momentum", "s_trend", "s_participation", "s_options",
]
INT_FIELDS = {"rank", "breadth", "volume", "market_cap"}
FLOAT_FIELDS = {
    "last_price", "percent_change", "high_52w", "pct_change_1m", "weighted_alpha",
    "score", "s_breakout", "s_momentum", "s_trend", "s_participation", "s_options",
}


def to_float(v):
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if s == "" or s.lower() in ("none", "nan", "null", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def read_latest(feed_id: str):
    """Return (snapshot_date, {symbol: row_dict}) for the most recent snapshot,
    or (None, {}) if the feed has no data."""
    path = APPS / feed_id / "data.csv"
    if not path.exists():
        return None, {}
    rows = []
    try:
        with path.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except OSError:
        return None, {}
    if not rows:
        return None, {}
    latest = max(r.get("snapshot_date", "") for r in rows)
    # Keep the BEST (lowest rank) row per symbol within the latest snapshot.
    best = {}
    for r in rows:
        if r.get("snapshot_date") != latest:
            continue
        sym = (r.get("symbol") or "").strip().upper()
        if not sym:
            continue
        rk = to_float(r.get("rank"))
        if sym not in best:
            best[sym] = r
        else:
            cur = to_float(best[sym].get("rank"))
            if rk is not None and (cur is None or rk < cur):
                best[sym] = r
    return latest, best


def percentiles(values: dict, missing: float = 0.4) -> dict:
    """Map {symbol: value-or-None} -> {symbol: percentile in [0,1]} using
    average-rank for ties. Missing values get a slightly-below-neutral default."""
    out = {}
    present = [(s, v) for s, v in values.items() if v is not None]
    for s, v in values.items():
        if v is None:
            out[s] = missing
    n = len(present)
    if n == 0:
        return out
    if n == 1:
        out[present[0][0]] = 1.0
        return out
    svals = sorted(v for _, v in present)
    denom = n - 1
    for s, v in present:
        lo = bisect.bisect_left(svals, v)
        hi = bisect.bisect_right(svals, v) - 1
        out[s] = ((lo + hi) / 2) / denom
    return out


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def rank_pct(row, n):
    """Top of a list (rank 1) -> 1.0; bottom -> 0.0."""
    rk = to_float(row.get("rank"))
    if rk is None or n <= 1:
        return 0.5
    return clamp(1 - (rk - 1) / (n - 1))


def signal_breakout(latest: dict) -> dict:
    n = len(latest)
    chg = percentiles({s: to_float(r.get("percent_change")) for s, r in latest.items()})
    out = {}
    for s, r in latest.items():
        last = to_float(r.get("last_price"))
        hi = to_float(r.get("high_52w"))
        prox = clamp(last / hi) if (last and hi) else 0.8  # on this list ⇒ at/near a high
        out[s] = clamp(0.40 * rank_pct(r, n) + 0.35 * prox + 0.25 * chg[s])
    return out


def signal_momentum(latest: dict) -> dict:
    n = len(latest)
    m = percentiles({s: to_float(r.get("pct_change_1m")) for s, r in latest.items()})
    out = {}
    for s, r in latest.items():
        out[s] = clamp(0.70 * m[s] + 0.30 * rank_pct(r, n))
    return out


def signal_trend(latest: dict) -> dict:
    wa = percentiles({s: to_float(r.get("weighted_alpha")) for s, r in latest.items()})
    chg = percentiles({s: to_float(r.get("percent_change")) for s, r in latest.items()})
    out = {}
    for s, r in latest.items():
        prev = to_float(r.get("previous_rank"))
        rk = to_float(r.get("rank"))
        climb = clamp(0.5 + (prev - rk) / 200) if (prev and rk) else 0.5
        out[s] = clamp(0.55 * wa[s] + 0.25 * chg[s] + 0.20 * climb)
    return out


def signal_participation(latest: dict) -> dict:
    turn = percentiles({s: to_float(r.get("percent_turnover")) for s, r in latest.items()})
    vol = percentiles({s: to_float(r.get("volume")) for s, r in latest.items()})
    chg = percentiles({s: to_float(r.get("percent_change")) for s, r in latest.items()})
    out = {}
    for s in latest:
        out[s] = clamp(0.40 * turn[s] + 0.20 * vol[s] + 0.40 * chg[s])
    return out


def signal_options(latest: dict) -> dict:
    ovol = percentiles({s: to_float(r.get("option_volume")) for s, r in latest.items()})
    chg = percentiles({s: to_float(r.get("percent_change")) for s, r in latest.items()})
    out = {}
    for s, r in latest.items():
        pcr = to_float(r.get("vol_pc_ratio"))
        call_bias = clamp(1 - pcr / 2) if pcr is not None else 0.5  # <1 put/call ⇒ call-heavy
        out[s] = clamp(0.40 * ovol[s] + 0.35 * call_bias + 0.25 * chg[s])
    return out


SIGNAL_FN = {
    "breakout": signal_breakout,
    "momentum": signal_momentum,
    "trend": signal_trend,
    "participation": signal_participation,
    "options": signal_options,
}


def pick(symbol, field, feed_data, order):
    """First non-empty value of `field` for `symbol` across feeds in `order`."""
    for feed_id in order:
        latest = feed_data[feed_id]
        if symbol in latest:
            v = to_float(latest[symbol].get(field))
            if v is not None:
                return v
    return None


def pick_name(symbol, feed_data, order):
    for feed_id in order:
        latest = feed_data[feed_id]
        if symbol in latest:
            nm = (latest[symbol].get("name") or "").strip()
            if nm:
                return nm
    return symbol


def build_picks(top_n: int = 100):
    feed_data = {}        # feed_id -> {symbol: row}
    feed_signal = {}      # feed_id -> {symbol: signal[0,1]}
    feed_date = {}
    present_feeds = []
    for feed_id, code, weight, comp in FEEDS:
        date, latest = read_latest(feed_id)
        feed_data[feed_id] = latest
        feed_date[feed_id] = date
        if latest:
            feed_signal[feed_id] = SIGNAL_FN[comp](latest)
            present_feeds.append(feed_id)
        else:
            feed_signal[feed_id] = {}
            print(f"  [warn] {feed_id}: no data found", file=sys.stderr)

    if not present_feeds:
        raise SystemExit("[overallpicks] No source data found in any sibling feed. Run the 5 scrapers first.")

    # Priority order for pulling display fields: by feed weight (highest first).
    field_order = [f[0] for f in sorted(FEEDS, key=lambda x: -x[2])]

    universe = set()
    for feed_id in present_feeds:
        universe.update(feed_data[feed_id].keys())

    comp_key = {feed_id: comp for feed_id, _, _, comp in FEEDS}
    weight_of = {feed_id: w for feed_id, _, w, _ in FEEDS}
    code_of = {feed_id: c for feed_id, c, _, _ in FEEDS}

    picks = []
    for sym in universe:
        comps = {"breakout": 0.0, "momentum": 0.0, "trend": 0.0,
                 "participation": 0.0, "options": 0.0}
        lists, score = [], 0.0
        for feed_id in present_feeds:
            if sym in feed_data[feed_id]:
                sig = feed_signal[feed_id].get(sym, 0.0)
                pts = weight_of[feed_id] * sig * 100
                comps[comp_key[feed_id]] = pts
                score += pts
                lists.append(code_of[feed_id])
        picks.append({
            "symbol": sym,
            "name": pick_name(sym, feed_data, field_order),
            "last_price": pick(sym, "last_price", feed_data, field_order),
            "percent_change": pick(sym, "percent_change", feed_data,
                                   [f for f in field_order if f != "barchart100"] + ["barchart100"]),
            "volume": pick(sym, "volume", feed_data, field_order),
            "market_cap": pick(sym, "market_cap", feed_data, field_order),
            "high_52w": pick(sym, "high_52w", feed_data, field_order),
            "pct_change_1m": pick(sym, "pct_change_1m", feed_data, field_order),
            "weighted_alpha": pick(sym, "weighted_alpha", feed_data, field_order),
            "score": round(score, 1),
            "breadth": len(lists),
            "lists": ",".join(lists),
            "s_breakout": round(comps["breakout"], 1),
            "s_momentum": round(comps["momentum"], 1),
            "s_trend": round(comps["trend"], 1),
            "s_participation": round(comps["participation"], 1),
            "s_options": round(comps["options"], 1),
        })

    # Sort by score desc, then breadth desc, then symbol for stability.
    picks.sort(key=lambda p: (-p["score"], -p["breadth"], p["symbol"]))
    picks = picks[:top_n]
    for i, p in enumerate(picks, start=1):
        p["rank"] = i
    return picks, feed_date


def coerce(field, value):
    if value is None or value == "":
        return None
    if field in INT_FIELDS:
        f = to_float(value)
        return int(round(f)) if f is not None else None
    if field in FLOAT_FIELDS:
        return to_float(value)
    return str(value)


def load_history():
    if not CSV_PATH.exists():
        return []
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_outputs(picks, snapshot_date, snapshot_time):
    # Merge: drop any existing rows for today, then append today's picks.
    history = [r for r in load_history() if r.get("snapshot_date") != snapshot_date]
    for p in picks:
        row = {"snapshot_date": snapshot_date, "snapshot_time": snapshot_time}
        for k in OUT_FIELDS:
            if k not in row:
                row[k] = p.get(k)
        history.append(row)
    history.sort(key=lambda r: (r.get("snapshot_date", ""), int(to_float(r.get("rank")) or 0)))

    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        w.writeheader()
        for r in history:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in OUT_FIELDS})

    # data.js — coerce types so the dashboard gets numbers, not strings.
    js_rows = []
    for r in history:
        js_rows.append({k: coerce(k, r.get(k)) for k in OUT_FIELDS})
    gen = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with JS_PATH.open("w", encoding="utf-8") as f:
        f.write("// Auto-generated by scraper.py (Overall Picks aggregator) — do not edit by hand.\n")
        f.write(f'window.WEBULL_GENERATED_AT = "{gen}";\n')
        f.write("window.WEBULL_DATA = ")
        json.dump(js_rows, f, separators=(",", ":"), allow_nan=False)
        f.write(";\n")


def main() -> int:
    now = datetime.now().astimezone()
    snapshot_date = now.strftime("%Y-%m-%d")
    snapshot_time = now.strftime("%Y-%m-%d %H:%M:%S %Z").strip()

    picks, feed_date = build_picks(top_n=100)
    write_outputs(picks, snapshot_date, snapshot_time)

    print(f"[overallpicks] {snapshot_date}: ranked {len(picks)} picks from sources:")
    for feed_id, code, _, _ in FEEDS:
        d = feed_date.get(feed_id)
        print(f"    {code:5} {feed_id:14} latest snapshot: {d or 'MISSING'}")
    print("  Top 10:")
    for p in picks[:10]:
        print(f"    #{p['rank']:<3} {p['symbol']:<6} score={p['score']:>5}  "
              f"[{p['breadth']}/5 {p['lists']}]  {p['name'][:34]}")
    print(f"  Wrote {CSV_PATH.name} ({len(load_history())} total rows) and {JS_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
