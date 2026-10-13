"""
anomaly_detection.py
Two layers of detection, both using the same day-of-week-aware robust
z-score approach:

  - detect_anomalies(df)         -> per (region, product): catches single-item
                                     problems like the Smart Watch flatline or
                                     a one-day transaction spike.
  - detect_region_anomalies(df)  -> per region, summed across ALL products:
                                     catches a broad regional dip (like the
                                     planted Karachi drop) that's too spread
                                     out to show up strongly on any one product.
"""

import numpy as np
import pandas as pd

Z_THRESHOLD = 3.0
DOW_WINDOW = 8
MAD_FLOOR_PCT = 0.05


def _mad(x):
    """Median absolute deviation — like standard deviation, but barely
    affected by one or two extreme outliers sitting in the window."""
    med = np.median(x)
    return np.median(np.abs(x - med))


def _score(df, group_cols, value_col):
    """Shared scoring logic: same-weekday comparison, robust stats, MAD floor.
    Used by both the product-level and region-level detectors below, so the
    two layers stay consistent instead of drifting into different math."""
    df = df.sort_values("date").copy()
    df["dow"] = df["date"].dt.dayofweek
    grp = df.groupby(group_cols)[value_col]

    df["rolling_median"] = grp.transform(lambda x: x.shift(1).rolling(DOW_WINDOW).median())
    df["rolling_mad"] = grp.transform(lambda x: x.shift(1).rolling(DOW_WINDOW).apply(_mad, raw=True))

    mad_floor = MAD_FLOOR_PCT * df["rolling_median"].abs()
    df["rolling_mad_floored"] = df["rolling_mad"].clip(lower=mad_floor)

    df["z_score"] = 0.6745 * (df[value_col] - df["rolling_median"]) / df["rolling_mad_floored"]
    df["z_score"] = df["z_score"].replace([np.inf, -np.inf], None)
    return df


def detect_anomalies(df):
    """Product-level: is THIS product, in THIS region, behaving oddly?"""
    scored = _score(df, ["region", "product", "dow"], "revenue")
    anomalies = scored[scored["z_score"].abs() > Z_THRESHOLD].copy()
    anomalies["z_score"] = anomalies["z_score"].round(2)
    anomalies["rolling_median"] = anomalies["rolling_median"].round(2)
    return anomalies[["date", "region", "product", "revenue", "rolling_median", "z_score"]]


def detect_region_anomalies(df):
    """Region-level: is the WHOLE region behaving oddly, even if no single
    product looks extreme on its own? First sums revenue across all products
    per region/day, then applies the same detection logic to that total."""
    region_daily = df.groupby(["region", "date"], as_index=False)["revenue"].sum()
    scored = _score(region_daily, ["region", "dow"], "revenue")
    anomalies = scored[scored["z_score"].abs() > Z_THRESHOLD].copy()
    anomalies["z_score"] = anomalies["z_score"].round(2)
    anomalies["rolling_median"] = anomalies["rolling_median"].round(2)
    return anomalies[["date", "region", "revenue", "rolling_median", "z_score"]]


if __name__ == "__main__":
    from simulate_live_feed import get_current_date
    from anomaly_tracker import update_tracker

    df = pd.read_csv("sales_data.csv", parse_dates=["date"])
    today = get_current_date()

    product_anomalies = detect_anomalies(df)
    todays_product = product_anomalies[product_anomalies["date"] == today]

    region_anomalies = detect_region_anomalies(df)
    todays_region = region_anomalies[region_anomalies["date"] == today]

    result = update_tracker(today, todays_product, todays_region)

    print(f"=== Daily Anomaly Report for {today.date()} ===\n")

    print(f"NEW today ({len(result['new'])}):")
    if result["new"]:
        for f in result["new"]:
            label = f"{f['region']} — {f['product']}" if f["level"] == "product" else f"{f['region']} (region-wide)"
            print(f"  - {label}: z={f['z_score']:.2f}")
    else:
        print("  (none)")

    print(f"\nONGOING ({len(result['ongoing'])}):")
    if result["ongoing"]:
        for f in result["ongoing"]:
            label = f"{f['region']} — {f['product']}" if f["level"] == "product" else f"{f['region']} (region-wide)"
            print(f"  - {label}: ongoing for {f['days_open']} day(s), since {f['first_seen']}")
    else:
        print("  (none)")

    print(f"\nRESOLVED since yesterday ({len(result['resolved'])}):")
    if result["resolved"]:
        for f in result["resolved"]:
            label = f"{f['region']} — {f['product']}" if f["product"] else f"{f['region']} (region-wide)"
            print(f"  - {label}: was open for {f['days_open']} day(s)")
    else:
        print("  (none)")