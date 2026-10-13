"""
pipeline.py
Simulates the real daily job: ask the (simulated) live feed what today's
new data is, pull it, validate it. No date is ever picked by hand — the
feed decides what "today" is, exactly like a real database would.
"""

import pandas as pd
from simulate_live_feed import get_next_available_date

REQUIRED_COLUMNS = ["date", "region", "product", "units_sold", "revenue", "transaction_count"]


def extract_data(csv_path: str = "sales_data.csv") -> pd.DataFrame:
    """Pull exactly one day's rows — whichever day the live feed says is
    'new' right now. In production, this function would run a SQL query
    against a real database instead; nothing else in the pipeline changes."""
    target_date = get_next_available_date(csv_path)

    df = pd.read_csv(csv_path, parse_dates=["date"])
    day_df = df[df["date"] == target_date].copy()

    if day_df.empty:
        raise ValueError(f"No rows found for {target_date.date()} in {csv_path}")

    print(f"Extracted {len(day_df)} rows for {target_date.date()}")
    return day_df


def validate_data(df: pd.DataFrame) -> pd.DataFrame:
    issues = []

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        issues.append(f"Missing columns: {missing_cols}")

    if df[REQUIRED_COLUMNS].isnull().any().any():
        bad_cols = df.columns[df.isnull().any()].tolist()
        issues.append(f"Null values found in: {bad_cols}")

    for col in ["units_sold", "revenue", "transaction_count"]:
        if (df[col] < 0).any():
            issues.append(f"Negative values found in '{col}'")

    dupes = df.duplicated(subset=["date", "region", "product"]).sum()
    if dupes > 0:
        issues.append(f"{dupes} duplicate (date, region, product) rows found")

    if issues:
        raise ValueError("Data validation FAILED:\n  - " + "\n  - ".join(issues))

    print("Validation passed: no nulls, no negatives, no duplicates.")
    return df


if __name__ == "__main__":
    raw = extract_data()
    clean = validate_data(raw)

    print("\n--- Sample of validated data ---")
    print(clean.head())
    print(f"\nTotal revenue for the day: {clean['revenue'].sum():.2f}")