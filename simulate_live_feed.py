"""
simulate_live_feed.py

Pretends to be a live company database. Each time the daily pipeline runs,
this reveals the NEXT day of data — exactly like a real database already
having yesterday's transactions sitting in it by morning.

Tracks progress in a small state file (last_processed_date.txt) so it
remembers where it left off between runs, without you manually picking
a date each time.
"""

import pandas as pd
from pathlib import Path

STATE_FILE = Path("last_processed_date.txt")


def get_next_available_date(full_csv="sales_data.csv"):
    """Returns the next date the 'live feed' should reveal, and advances
    the state file so the next call moves forward, not backward."""
    df = pd.read_csv(full_csv, parse_dates=["date"])
    all_dates = sorted(df["date"].unique())

    if STATE_FILE.exists():
        last_date = pd.Timestamp(STATE_FILE.read_text().strip())
        remaining = [d for d in all_dates if pd.Timestamp(d) > last_date]
        if not remaining:
            raise SystemExit(
                f"No new data available — simulated feed exhausted "
                f"(last processed: {last_date.date()})."
            )
        next_date = remaining[0]
    else:
        next_date = all_dates[0]  # first ever run: start from day 1

    next_date = pd.Timestamp(next_date)
    STATE_FILE.write_text(str(next_date.date()))
    return next_date


def get_current_date():
    """Peek at whatever date was most recently pulled (by pipeline.py),
    WITHOUT advancing the feed. Used by anomaly_detection.py so it reports
    on the same day the pipeline just validated — not the next one."""
    if not STATE_FILE.exists():
        raise RuntimeError(
            "No date has been processed yet. Run pipeline.py first so "
            "there's a 'today' to report on."
        )
    return pd.Timestamp(STATE_FILE.read_text().strip())


def reset_feed():
    """Utility for testing: wipes progress so the feed starts over."""
    if STATE_FILE.exists():
        STATE_FILE.unlink()
        print("Feed reset — next run will start from day 1 again.")
    else:
        print("Nothing to reset — feed hasn't started yet.")


if __name__ == "__main__":
    next_date = get_next_available_date()
    print(f"Today's simulated 'new data' date: {next_date.date()}")