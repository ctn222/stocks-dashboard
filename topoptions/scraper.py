#!/usr/bin/env python3
"""
Scrapes Webull's "Options Total Volume" ranking and stores the top 100
underlyings (by total options volume across all expirations) in a historical
CSV + JSON bundle the dashboard reads.

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
    "https://quotes-gw.webullfintech.com/api/wlas/option/rank/list"
    "?regionId=6&rankType=totalVolume&pageIndex=1&pageSize=100"
)
PAGE_URL = "https://www.webull.com/quote/us/options/total-volume"

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
    "option_volume",
    "open_interest",
    "vol_pc_ratio",
    "oi_pc_ratio",
    "last_price",
    "percent_change",
    "stock_volume",
    "high",
    "low",
    "percent_range",
    "market_cap",
]


def fetch_data() -> tuple[list[dict], str]:
    """Return (rows, latest_update_iso). Rows are ordered by Webull's options total-volume rank."""
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
        v = r.get("values", {}) or {}
        chg = to_float(t.get("changeRatio"))
        vib = to_float(t.get("vibrateRatio"))
        new_records.append(
            {
                "snapshot_date": snapshot_date,
                "snapshot_time": snapshot_time or snapshot_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "rank": idx,
                "symbol": t.get("symbol", ""),
                "name": t.get("name", ""),
                # values.volume = total options volume across all expirations.
                "option_volume": to_int(v.get("volume")) or "",
                # values.position = total open interest across all expirations.
                "open_interest": to_int(v.get("position")) or "",
                # Webull's `volumeCallPutRatio` / `positionCallPutRatio` are misnamed:
                # they actually return puts ÷ calls (matches the website's "P/C Vol" / "P/C OI").
                "vol_pc_ratio": to_float(v.get("volumeCallPutRatio")) if to_float(v.get("volumeCallPutRatio")) is not None else "",
                "oi_pc_ratio": to_float(v.get("positionCallPutRatio")) if to_float(v.get("positionCallPutRatio")) is not None else "",
                "last_price": to_float(t.get("close")) if to_float(t.get("close")) is not None else "",
                # changeRatio comes back as a decimal (e.g. -0.0191 = -1.91%).
                "percent_change": chg * 100 if chg is not None else "",
                "stock_volume": to_int(t.get("volume")) or "",
                "high": to_float(t.get("high")) if to_float(t.get("high")) is not None else "",
                "low": to_float(t.get("low")) if to_float(t.get("low")) is not None else "",
                "percent_range": vib * 100 if vib is not None else "",
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
                        "option_volume": int(row["option_volume"]) if row["option_volume"] else None,
                        "open_interest": int(row["open_interest"]) if row["open_interest"] else None,
                        "vol_pc_ratio": float(row["vol_pc_ratio"]) if row["vol_pc_ratio"] else None,
                        "oi_pc_ratio": float(row["oi_pc_ratio"]) if row["oi_pc_ratio"] else None,
                        "last_price": float(row["last_price"]) if row["last_price"] else None,
                        "percent_change": float(row["percent_change"]) if row["percent_change"] else None,
                        "stock_volume": int(row["stock_volume"]) if row["stock_volume"] else None,
                        "high": float(row["high"]) if row["high"] else None,
                        "low": float(row["low"]) if row["low"] else None,
                        "percent_range": float(row["percent_range"]) if row["percent_range"] else None,
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
