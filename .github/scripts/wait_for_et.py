#!/usr/bin/env python3
"""Sleep until the next scheduled Eastern-time target, then exit.

WHY THIS EXISTS
---------------
GitHub's `schedule:` trigger is best-effort. Measured on this repo across 12
consecutive scheduled runs, jobs started 43-70 minutes AFTER their cron time,
so a cron set for the market close was really firing around 6 PM ET.

The fix is to stop asking cron to be punctual. The workflow is scheduled to
*start early* (~75 min before the target), and this script holds the job until
the exact Eastern wall-clock moment. Waiting inside an already-running job is
precise, and it also handles daylight saving properly — the target is defined
in America/New_York, not UTC, so no seasonal cron edits are ever needed.

Public repos get unlimited free Actions minutes, so the idle wait costs nothing.

Usage:
    python3 wait_for_et.py                 # wait, then exit 0
    python3 wait_for_et.py --dry-run       # print the plan, don't sleep
    python3 wait_for_et.py --now "..."     # simulate a start time (testing)
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Eastern wall-clock targets, Mon-Fri: ~15 min after the 9:30 open and ~15 min
# after the 4:00 close.
TARGETS = [(9, 45), (16, 15)]

# If the job started so late that a target already passed by more than this,
# don't wait for it — scrape immediately with whatever is current.
GRACE_MIN = 30

# Safety cap so a misconfigured cron can never park a runner for hours.
MAX_WAIT_MIN = 150


def pick_target(now: dt.datetime) -> tuple[dt.datetime | None, str]:
    """Choose which target this run is for.

    Returns (target_datetime_or_None, human_reason). None means "run now".
    """
    if now.weekday() > 4:  # Sat/Sun — the crons are Mon-Fri, but be safe.
        return None, "weekend; running immediately"

    candidates = [
        now.replace(hour=hh, minute=mm, second=0, microsecond=0) for hh, mm in TARGETS
    ]

    # 1. A target that just passed — the job was queued for it but GitHub started
    #    us late. Scrape right now rather than skipping the slot entirely.
    just_passed = [
        t for t in candidates if 0 <= (now - t).total_seconds() <= GRACE_MIN * 60
    ]
    if just_passed:
        t = max(just_passed)
        late_min = (now - t).total_seconds() / 60
        return None, (
            f"target {t:%H:%M} ET passed {late_min:.0f} min ago "
            f"(within {GRACE_MIN}m grace); running immediately"
        )

    # 2. Normal case: we started early, so hold until the next target.
    upcoming = sorted(t for t in candidates if t > now)
    if upcoming:
        target = upcoming[0]
        wait_min = (target - now).total_seconds() / 60
        if wait_min <= MAX_WAIT_MIN:
            return target, f"waiting {wait_min:.1f} min for {target:%H:%M} ET"
        return None, (
            f"next target {target:%H:%M} ET is {wait_min:.0f} min away "
            f"(> {MAX_WAIT_MIN}m cap); running immediately"
        )

    return None, "no target left today; running immediately"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--now", help="ISO timestamp to simulate (assumed ET if naive)")
    args = ap.parse_args()

    if args.now:
        now = dt.datetime.fromisoformat(args.now)
        now = now.replace(tzinfo=ET) if now.tzinfo is None else now.astimezone(ET)
    else:
        now = dt.datetime.now(ET)

    target, reason = pick_target(now)
    print(f"[wait] now       : {now:%Y-%m-%d %H:%M:%S %Z}")
    print(f"[wait] decision  : {reason}")

    if target is None:
        return 0

    if args.dry_run:
        print(f"[wait] (dry run) would sleep until {target:%Y-%m-%d %H:%M:%S %Z}")
        return 0

    # Sleep in chunks so the log shows progress and the job never looks hung.
    while True:
        remaining = (target - dt.datetime.now(ET)).total_seconds()
        if remaining <= 0:
            break
        chunk = min(remaining, 300)
        print(f"[wait] {remaining/60:6.1f} min remaining…", flush=True)
        time.sleep(chunk)

    print(f"[wait] target reached: {dt.datetime.now(ET):%Y-%m-%d %H:%M:%S %Z}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
