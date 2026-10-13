"""
anomaly_tracker.py
Keeps track of which anomalies are NEW today vs ONGOING from previous days,
so a daily report doesn't repeat "Smart Watch is down" 19 days in a row.

Persists state in open_anomalies.json between runs — this is the system's
short-term memory of "what's currently broken."
"""

import json
from pathlib import Path

STATE_FILE = Path("open_anomalies.json")

def _load_state(state_path=None):
    path = state_path or STATE_FILE
    if path.exists():
        return json.loads(path.read_text())
    return {}


def _save_state(state, state_path=None):
    path = state_path or STATE_FILE
    path.write_text(json.dumps(state, indent=2))


def _product_key(region, product):
    return f"product::{region}::{product}"


def _region_key(region):
    return f"region::{region}"


def update_tracker(today, product_anomalies_df, region_anomalies_df, state_path=None):
    """
    today: pd.Timestamp for the day being reported.
    product_anomalies_df / region_anomalies_df: already filtered down to
    just today's rows.
    state_path: optional Path to a dedicated state file. Lets separate
    datasets (e.g. an uploaded file) keep their own independent tracking
    memory instead of sharing/corrupting the default one.

    Returns {"new": [...], "ongoing": [...], "resolved": [...]} and
    persists the updated state to disk.
    """
    state = _load_state(state_path)
    today_str = str(today.date())
    seen_today = set()
    new_findings, ongoing_findings = [], []

    def _handle(key, level, region, product, z_score):
        seen_today.add(key)
        if key in state:
            state[key]["last_seen"] = today_str
            state[key]["days_open"] += 1
            ongoing_findings.append({
                "level": level, "region": region, "product": product,
                "z_score": z_score, "days_open": state[key]["days_open"],
                "first_seen": state[key]["first_seen"],
            })
        else:
            state[key] = {"first_seen": today_str, "last_seen": today_str, "days_open": 1}
            new_findings.append({
                "level": level, "region": region, "product": product,
                "z_score": z_score, "days_open": 1, "first_seen": today_str,
            })

    for _, row in product_anomalies_df.iterrows():
        _handle(_product_key(row["region"], row["product"]), "product",
                row["region"], row["product"], row["z_score"])

    for _, row in region_anomalies_df.iterrows():
        _handle(_region_key(row["region"]), "region",
                row["region"], None, row["z_score"])

    resolved_findings = []
    for key in list(state.keys()):
        if key not in seen_today:
            entry = state.pop(key)
            parts = key.split("::")
            resolved_findings.append({
                "level": parts[0], "region": parts[1],
                "product": parts[2] if len(parts) > 2 else None,
                "days_open": entry["days_open"], "first_seen": entry["first_seen"],
            })

    _save_state(state, state_path)
    return {"new": new_findings, "ongoing": ongoing_findings, "resolved": resolved_findings}


def reset_tracker(state_path=None):
    path = state_path or STATE_FILE
    if path.exists():
        path.unlink()
        print("Tracker reset — all findings will be 'new' again on the next run.")