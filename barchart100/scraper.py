#!/usr/bin/env python3
"""
Scrapes Barchart Top 100 Stocks (Weighted Alpha Advances) and stores the full
top 100 in a historical CSV + JSON bundle the dashboard reads.

Run: python3 scraper.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
import urllib.parse
from datetime import datetime
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from urllib.request import Request, build_opener, HTTPCookieProcessor

HERE = Path(__file__).resolve().parent
CSV_PATH = HERE / "data.csv"
JS_PATH = HERE / "data.js"

PAGE_URL = "https://www.barchart.com/stocks/top-100-stocks"
API_URL = "https://www.barchart.com/proxies/core-api/v1/quotes/get"
LIST_ID = "stocks.us.weighted_alpha.advances"
FIELDS = "symbol,symbolName,lastPrice,percentChange,highPrice1y,weightedAlpha,previousRank,tradeTime"
LIMIT = 100

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

CSV_COLUMNS = [
    "snapshot_date",
    "snapshot_time",
    "rank",
    "previous_rank",
    "symbol",
    "name",
    "last_price",
    "percent_change",
    "high_52w",
    "weighted_alpha",
]


def fetch_data() -> tuple[list[dict], str]:
    """Return (rows, trade_time_string). Rows are already ordered by rank."""
    jar = MozillaCookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))
    opener.addheaders = [
        ("User-Agent", UA),
        ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
        ("Accept-Language", "en-US,en;q=0.9"),
    ]

    # Prime the session — establishes laravel_session + XSRF-TOKEN cookies.
    with opener.open(PAGE_URL, timeout=30) as resp:
        resp.read()

    xsrf = next((c.value for c in jar if c.name == "XSRF-TOKEN"), None)
    if not xsrf:
        raise RuntimeError("Did not receive XSRF-TOKEN cookie from Barchart.")
    xsrf_decoded = urllib.parse.unquote(xsrf)

    qs = urllib.parse.urlencode(
        {
            "lists": LIST_ID,
            "fields": FIELDS,
            "orderBy": "weightedAlpha",
            "orderDir": "desc",
            "limit": LIMIT,
        }
    )
    req = Request(
        f"{API_URL}?{qs}",
        headers={
            "User-Agent": UA,
            "Accept": "application/json",
            "Referer": PAGE_URL,
            "x-xsrf-token": xsrf_decoded,
        },
    )
    with opener.open(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    rows = payload.get("data") or []
    if not rows:
        raise RuntimeError(f"Empty payload from Barchart API: {payload}")

    trade_time = rows[0].get("tradeTime", "")
    return rows, trade_time


def to_float(val) -> float | None:
    if val in (None, "", "N/A"):
        return None
    try:
        return float(str(val).replace(",", "").replace("+", "").replace("%", ""))
    except ValueError:
        return None


def to_int(val) -> int | None:
    f = to_float(val)
    return int(f) if f is not None else None


def append_to_csv(rows: list[dict], snapshot_dt: datetime, trade_time: str) -> int:
    """Append today's snapshot; replace any existing snapshot for the same date."""
    snapshot_date = snapshot_dt.strftime("%Y-%m-%d")
    existing: list[dict] = []
    if CSV_PATH.exists():
        with CSV_PATH.open(newline="", encoding="utf-8") as f:
            existing = [r for r in csv.DictReader(f) if r["snapshot_date"] != snapshot_date]

    new_records = []
    for idx, r in enumerate(rows, start=1):
        new_records.append(
            {
                "snapshot_date": snapshot_date,
                "snapshot_time": trade_time or snapshot_dt.strftime("%H:%M ET"),
                "rank": idx,
                "previous_rank": to_int(r.get("previousRank")) or "",
                "symbol": r.get("symbol", ""),
                "name": r.get("symbolName", ""),
                "last_price": to_float(r.get("lastPrice")) or "",
                "percent_change": to_float(r.get("percentChange")) if to_float(r.get("percentChange")) is not None else "",
                "high_52w": to_float(r.get("highPrice1y")) or "",
                "weighted_alpha": to_float(r.get("weightedAlpha")) or "",
            }
        )

    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        w.writerows(existing + new_records)
    return len(new_records)


def write_js_bundle() -> None:
    """Serialize the full CSV history to data.js so the HTML can load it via file://."""
    history: list[dict] = []
    if CSV_PATH.exists():
        with CSV_PATH.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                history.append(
                    {
                        "snapshot_date": row["snapshot_date"],
                        "snapshot_time": row["snapshot_time"],
                        "rank": int(row["rank"]),
                        "previous_rank": int(row["previous_rank"]) if row["previous_rank"] else None,
                        "symbol": row["symbol"],
                        "name": row["name"],
                        "last_price": float(row["last_price"]) if row["last_price"] else None,
                        "percent_change": float(row["percent_change"]) if row.get("percent_change") not in (None, "") else None,
                        "high_52w": float(row["high_52w"]) if row["high_52w"] else None,
                        "weighted_alpha": float(row["weighted_alpha"]) if row["weighted_alpha"] else None,
                    }
                )

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z").strip()
    body = (
        "// Auto-generated by scraper.py — do not edit by hand.\n"
        f"window.BARCHART_GENERATED_AT = {json.dumps(generated_at)};\n"
        f"window.BARCHART_DATA = {json.dumps(history, separators=(',', ':'))};\n"
    )
    JS_PATH.write_text(body, encoding="utf-8")


def main() -> int:
    try:
        rows, trade_time = fetch_data()
    except Exception as e:
        print(f"[scraper] ERROR fetching Barchart: {e}", file=sys.stderr)
        return 1

    count = append_to_csv(rows, datetime.now(), trade_time)
    write_js_bundle()
    print(f"[scraper] Wrote {count} rows for {datetime.now():%Y-%m-%d} "
          f"(trade time {trade_time}) → {CSV_PATH.name}, {JS_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
