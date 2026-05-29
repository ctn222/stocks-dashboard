#!/usr/bin/env python3
"""
Scrapes Webull's "Top Gainers (1 Month)" ranking and stores the top 100
in a historical CSV + JSON bundle the dashboard reads.

Source: https://www.webull.com/quote/us/gainers/1m

Run: python3 scraper.py
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
CSV_PATH = HERE / "data.csv"
JS_PATH = HERE / "data.js"

API_URL = (
    "https://quotes-gw.webullfintech.com/api/wlas/ranking/topGainers"
    "?regionId=6&rankType=1m&pageIndex=1&pageSize=100"
)
PAGE_URL = "https://www.webull.com/quote/us/gainers/1m"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

CSV_COLUMNS = [
    "snapshot_date",
    "snapshot_time",
    "rank",
    "symbol",
    "name",
    "pct_change_1m",
    "last_price",
    "high",
    "low",
    "volume",
    "pct_range",
    "pe_ratio",
    "market_cap",
]


def fetch_data() -> tuple[list[dict], str]:
    """Return (rows, latest_update_iso). Rows are ordered by Webull's 1-month gainers rank."""
    req = Request(
        API_URL,
        headers={
            "User-Agent": UA,
            "Accept": "application/json",
            "Origin": "https://www.webull.com",
            "Referer": PAGE_URL,
        },
    )
    with urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    rows = payload.get("data") or []
    if not rows:
        raise RuntimeError(f"Empty payload from Webull API: {payload}")

    ts_ms = payload.get("latestUpdateTime")
    if ts_ms:
        latest = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        latest_iso = latest.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    else:
        latest_iso = ""
    return rows, latest_iso


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


def append_to_csv(rows: list[dict], snapshot_dt: datetime, snapshot_time: str) -> int:
    """Append today's snapshot; replace any existing snapshot for the same date."""
    snapshot_date = snapshot_dt.strftime("%Y-%m-%d")
    existing: list[dict] = []
    if CSV_PATH.exists():
        with CSV_PATH.open(newline="", encoding="utf-8") as f:
            existing = [r for r in csv.DictReader(f) if r["snapshot_date"] != snapshot_date]

    new_records = []
    for idx, r in enumerate(rows[:100], start=1):
        t = r.get("ticker", {}) or {}
        # changeRatio on the topGainers/1m endpoint is the 1-month return as a
        # decimal multiplier (e.g. 14.7106 = +1471.06% over the past month).
        chg = to_float(t.get("changeRatio"))
        # vibrateRatio is the intraday range as a decimal of prev close.
        vib = to_float(t.get("vibrateRatio"))
        new_records.append(
            {
                "snapshot_date": snapshot_date,
                "snapshot_time": snapshot_time or snapshot_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "rank": idx,
                "symbol": t.get("symbol", ""),
                "name": t.get("name", ""),
                "pct_change_1m": chg * 100 if chg is not None else "",
                "last_price": to_float(t.get("close")) if to_float(t.get("close")) is not None else "",
                "high": to_float(t.get("high")) if to_float(t.get("high")) is not None else "",
                "low": to_float(t.get("low")) if to_float(t.get("low")) is not None else "",
                "volume": to_int(t.get("volume")) or "",
                "pct_range": vib * 100 if vib is not None else "",
                "pe_ratio": to_float(t.get("peTtm")) if to_float(t.get("peTtm")) is not None else "",
                "market_cap": to_int(t.get("marketValue")) or "",
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
                        "symbol": row["symbol"],
                        "name": row["name"],
                        "pct_change_1m": float(row["pct_change_1m"]) if row["pct_change_1m"] else None,
                        "last_price": float(row["last_price"]) if row["last_price"] else None,
                        "high": float(row["high"]) if row["high"] else None,
                        "low": float(row["low"]) if row["low"] else None,
                        "volume": int(row["volume"]) if row["volume"] else None,
                        "pct_range": float(row["pct_range"]) if row["pct_range"] else None,
                        "pe_ratio": float(row["pe_ratio"]) if row["pe_ratio"] else None,
                        "market_cap": int(row["market_cap"]) if row["market_cap"] else None,
                    }
                )

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z").strip()
    body = (
        "// Auto-generated by scraper.py — do not edit by hand.\n"
        f"window.WEBULL_GENERATED_AT = {json.dumps(generated_at)};\n"
        f"window.WEBULL_DATA = {json.dumps(history, separators=(',', ':'))};\n"
    )
    JS_PATH.write_text(body, encoding="utf-8")


def main() -> int:
    try:
        rows, latest_iso = fetch_data()
    except Exception as e:
        print(f"[scraper] ERROR fetching Webull: {e}", file=sys.stderr)
        return 1

    count = append_to_csv(rows, datetime.now(), latest_iso)
    write_js_bundle()
    print(
        f"[scraper] Wrote {count} rows for {datetime.now():%Y-%m-%d} "
        f"(latest update {latest_iso}) → {CSV_PATH.name}, {JS_PATH.name}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
