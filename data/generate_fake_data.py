"""
Synthetic sales data generator for the Autonomous Reporting Agent project.

Produces:
  sales_data.csv           -> date, region, product, units_sold, revenue, transaction_count
  anomaly_ground_truth.json -> exactly what was injected and where, so you can verify
                                your detection code actually finds it later.

Run: python3 generate_fake_data.py
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

SEED = 42
rng = np.random.default_rng(SEED)

N_DAYS = 90
END_DATE = datetime(2026, 9, 4)  # "today"
START_DATE = END_DATE - timedelta(days=N_DAYS - 1)
dates = [START_DATE + timedelta(days=i) for i in range(N_DAYS)]

REGIONS = ["Karachi", "Lahore", "Islamabad"]

# product -> (avg daily units baseline, unit price)
PRODUCTS = {
    "Wireless Earbuds":   (40, 25.0),
    "Smart Watch":        (18, 65.0),
    "Bluetooth Speaker":  (25, 35.0),
    "Phone Case":         (60, 8.0),
    "Power Bank":         (30, 20.0),
    "USB-C Cable":        (70, 5.0),
    "Laptop Stand":       (15, 22.0),
    "Screen Protector":   (55, 4.0),
}

# region -> relative size multiplier (Karachi is the biggest market)
REGION_WEIGHT = {"Karachi": 1.4, "Lahore": 1.1, "Islamabad": 0.8}

rows = []
for d in dates:
    dow = d.weekday()  # 0=Mon ... 5=Fri (PK weekend ~ Fri/Sat), 6=Sun
    weekend_boost = 1.15 if dow in (4, 5) else 1.0  # Fri/Sat busier
    # mild upward trend over the quarter
    trend = 1.0 + 0.15 * (d - START_DATE).days / N_DAYS

    for region in REGIONS:
        for product, (base_units, price) in PRODUCTS.items():
            expected_units = base_units * REGION_WEIGHT[region] * weekend_boost * trend
            noise = rng.normal(1.0, 0.12)  # ~12% day-to-day noise
            units = max(0, expected_units * noise)

            units_sold = int(round(units))
            revenue = round(units_sold * price * rng.normal(1.0, 0.03), 2)
            transaction_count = max(1, int(round(units_sold / rng.uniform(1.3, 2.2)))) if units_sold else 0

            rows.append({
                "date": d.strftime("%Y-%m-%d"),
                "region": region,
                "product": product,
                "units_sold": units_sold,
                "revenue": revenue,
                "transaction_count": transaction_count,
            })

df = pd.DataFrame(rows)
ground_truth = {"seed": SEED, "injected_anomalies": []}

# ---------------------------------------------------------------------------
# ANOMALY 1: Karachi region-wide sales drop (~20%) for 3 consecutive days
# ---------------------------------------------------------------------------
drop_dates = [d.strftime("%Y-%m-%d") for d in dates[-10:-7]]  # 3 days, ~a week before "today"
mask = (df["region"] == "Karachi") & (df["date"].isin(drop_dates))
df.loc[mask, "units_sold"] = (df.loc[mask, "units_sold"] * 0.80).round().astype(int)
df.loc[mask, "revenue"] = (df.loc[mask, "revenue"] * 0.80).round(2)
df.loc[mask, "transaction_count"] = (df.loc[mask, "transaction_count"] * 0.82).round().astype(int)
ground_truth["injected_anomalies"].append({
    "type": "region_wide_drop", "region": "Karachi", "dates": drop_dates,
    "target_magnitude_pct": -20, "note": "region-wide ~20% drop across all products for 3 days"
})

# ---------------------------------------------------------------------------
# ANOMALY 2: One product flatlines (drops near-zero and stays flat) for the
# last 20 days across all regions -> looks like a stockout / discontinuation
# ---------------------------------------------------------------------------
flatline_product = "Smart Watch"
flatline_dates = [d.strftime("%Y-%m-%d") for d in dates[-20:]]
mask = (df["product"] == flatline_product) & (df["date"].isin(flatline_dates))
df.loc[mask, "units_sold"] = 1
df.loc[mask, "revenue"] = (1 * PRODUCTS[flatline_product][1]).__round__(2)
df.loc[mask, "transaction_count"] = 1
ground_truth["injected_anomalies"].append({
    "type": "product_flatline", "product": flatline_product,
    "dates": [flatline_dates[0], flatline_dates[-1]],
    "note": "units_sold/revenue collapse to ~flat near-zero for the last 20 days, all regions"
})

# ---------------------------------------------------------------------------
# ANOMALY 3: A few one-day outlier transaction spikes (e.g. bulk/fraud-like)
# ---------------------------------------------------------------------------
spike_targets = [
    (dates[-15], "Lahore", "USB-C Cable"),
    (dates[-25], "Islamabad", "Phone Case"),
    (dates[-40], "Karachi", "Power Bank"),
]
for d, region, product in spike_targets:
    ds = d.strftime("%Y-%m-%d")
    mask = (df["date"] == ds) & (df["region"] == region) & (df["product"] == product)
    mult = rng.uniform(4.0, 6.0)
    df.loc[mask, "units_sold"] = (df.loc[mask, "units_sold"] * mult).round().astype(int)
    df.loc[mask, "transaction_count"] = (df.loc[mask, "transaction_count"] * mult).round().astype(int)
    df.loc[mask, "revenue"] = (df.loc[mask, "revenue"] * mult).round(2)
    ground_truth["injected_anomalies"].append({
        "type": "transaction_spike", "region": region, "product": product,
        "date": ds, "multiplier": round(float(mult), 2),
        "note": "single-day spike in units/transactions/revenue"
    })

df = df.sort_values(["date", "region", "product"]).reset_index(drop=True)

out_csv = "sales_data.csv"
out_json = "anomaly_ground_truth.json"

df.to_csv(out_csv, index=False)

import json
with open(out_json, "w") as f:
    json.dump(ground_truth, f, indent=2)

print(f"Wrote {len(df)} rows to {out_csv}")
print(f"Wrote ground truth to {out_json}")
print("\nInjected anomalies:")
for a in ground_truth["injected_anomalies"]:
    print(" -", a)
