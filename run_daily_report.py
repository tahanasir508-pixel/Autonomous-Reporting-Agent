"""
run_daily_report.py
The one script that represents "the whole system." Running this once is
equivalent to what a scheduled job would do every morning:

  1. Pull + validate today's data           (pipeline.py)
  2. Detect anomalies, product + region      (anomaly_detection.py)
  3. Classify new / ongoing / resolved       (anomaly_tracker.py)
  4. Ask the AI to summarize the findings    (ai_interpreter.py)
  5. Save everything to a dated report file  (reports/YYYY-MM-DD.md)

If the AI step fails (no API key, network issue, quota, etc.) the report
is still saved with the raw structured findings — a broken AI call
should never mean losing the day's detection results entirely.
"""

import sys
from pathlib import Path
from datetime import datetime

import pandas as pd

from pipeline import extract_data, validate_data
from simulate_live_feed import get_current_date
from anomaly_detection import detect_anomalies, detect_region_anomalies
from anomaly_tracker import update_tracker

REPORTS_DIR = Path("reports")


def _findings_to_markdown(result: dict) -> str:
    lines = []

    lines.append(f"**New today ({len(result['new'])}):**")
    if result["new"]:
        for f in result["new"]:
            label = f"{f['region']} — {f['product']}" if f["level"] == "product" else f"{f['region']} (region-wide)"
            lines.append(f"- {label}: z-score {f['z_score']:.2f}")
    else:
        lines.append("- (none)")

    lines.append(f"\n**Ongoing ({len(result['ongoing'])}):**")
    if result["ongoing"]:
        for f in result["ongoing"]:
            label = f"{f['region']} — {f['product']}" if f["level"] == "product" else f"{f['region']} (region-wide)"
            lines.append(f"- {label}: ongoing {f['days_open']} day(s), since {f['first_seen']}")
    else:
        lines.append("- (none)")

    lines.append(f"\n**Resolved since yesterday ({len(result['resolved'])}):**")
    if result["resolved"]:
        for f in result["resolved"]:
            label = f"{f['region']} — {f['product']}" if f["product"] else f"{f['region']} (region-wide)"
            lines.append(f"- {label}: was open {f['days_open']} day(s)")
    else:
        lines.append("- (none)")

    return "\n".join(lines)


def run_daily_report():
    print("Step 1/4: Extracting and validating today's data...")
    raw = extract_data()
    clean = validate_data(raw)
    today = get_current_date()

    print("\nStep 2/4: Running anomaly detection (product + region level)...")
    full_history = pd.read_csv("sales_data.csv", parse_dates=["date"])
    product_anomalies = detect_anomalies(full_history)
    todays_product = product_anomalies[product_anomalies["date"] == today]

    region_anomalies = detect_region_anomalies(full_history)
    todays_region = region_anomalies[region_anomalies["date"] == today]

    print("Step 3/4: Classifying new / ongoing / resolved...")
    result = update_tracker(today, todays_product, todays_region)

    print("Step 4/4: Generating AI summary...")
    ai_summary = None
    ai_error = None
    try:
        from ai_interpreter import generate_summary
        ai_summary = generate_summary(str(today.date()), result)
    except Exception as e:
        ai_error = str(e)
        print(f"  WARNING: AI summary failed ({ai_error}). Saving report without it.")

    REPORTS_DIR.mkdir(exist_ok=True)
    report_path = REPORTS_DIR / f"{today.date()}.md"

    parts = [
        f"# Daily Sales Report — {today.date()}",
        f"*Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        "",
        f"**Total revenue today:** {clean['revenue'].sum():,.2f}",
        "",
    ]

    if ai_summary:
        parts += ["## Summary", ai_summary, ""]
    elif ai_error:
        parts += ["## Summary", f"*(AI summary unavailable: {ai_error})*", ""]

    parts += ["## Findings", _findings_to_markdown(result)]

    report_path.write_text("\n".join(parts), encoding="utf-8")

    print(f"\nReport saved: {report_path.resolve()}")
    return report_path


if __name__ == "__main__":
    try:
        run_daily_report()
    except Exception as e:
        print(f"\nDAILY REPORT FAILED: {e}", file=sys.stderr)
        sys.exit(1)