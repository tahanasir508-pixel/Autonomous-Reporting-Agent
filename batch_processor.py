"""
batch_processor.py
Runs the SAME detection logic used for the live daily job, but replayed
across an entire uploaded dataset at once — one report per day, in order.

This reuses detect_anomalies / detect_region_anomalies / update_tracker
unchanged; the only difference from the live system is that we loop
through all dates in one pass instead of waiting for tomorrow.

Each dataset gets its own isolated tracker state and reports folder, so
uploading a new file never corrupts the demo data's history (or another
uploaded dataset's history).
"""

from pathlib import Path

import pandas as pd

from anomaly_detection import detect_anomalies, detect_region_anomalies
from anomaly_tracker import update_tracker

REQUIRED_COLUMNS = ["date", "region", "product", "units_sold", "revenue", "transaction_count"]


def validate_uploaded_data(df: pd.DataFrame) -> list[str]:
    """Returns a list of problems found (empty list = valid). Mirrors the
    same checks pipeline.py already does for the live daily job."""
    issues = []

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        issues.append(f"Missing required columns: {missing_cols}")
        return issues  # can't check further without the right columns

    if df[REQUIRED_COLUMNS].isnull().any().any():
        bad_cols = df.columns[df.isnull().any()].tolist()
        issues.append(f"Null values found in: {bad_cols}")

    for col in ["units_sold", "revenue", "transaction_count"]:
        if (df[col] < 0).any():
            issues.append(f"Negative values found in '{col}'")

    dupes = df.duplicated(subset=["date", "region", "product"]).sum()
    if dupes > 0:
        issues.append(f"{dupes} duplicate (date, region, product) rows found")

    n_days = df["date"].nunique()
    if n_days < 14:
        issues.append(
            f"Only {n_days} distinct day(s) of data found. The detector needs "
            f"several weeks of history to compute reliable baselines — results "
            f"on a short file will be mostly 'not enough history yet.'"
        )

    return issues


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


def process_dataset(df: pd.DataFrame, output_dir: Path, generate_ai_for_all=False,
                     progress_callback=None):
    """
    Replays detection + tracking across every day in df, saving one
    report per day into output_dir/reports/.

    generate_ai_for_all: if False (default), only the LAST day gets an
    AI-written summary — historical backfill days get the structured
    findings only. This keeps a 90-day upload from firing off 90 AI API
    calls by default.

    progress_callback: optional function(current_index, total, date_str)
    called after each day, so a UI can show a progress bar.

    Returns a list of the report file paths written, in date order.
    """
    output_dir = Path(output_dir)
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    state_path = output_dir / "open_anomalies.json"

    if state_path.exists():
        state_path.unlink()  # fresh tracking history for this run

    all_dates = sorted(df["date"].unique())
    product_anomalies = detect_anomalies(df)
    region_anomalies = detect_region_anomalies(df)

    written_paths = []

    for i, day in enumerate(all_dates):
        day = pd.Timestamp(day)
        day_df = df[df["date"] == day]
        todays_product = product_anomalies[product_anomalies["date"] == day]
        todays_region = region_anomalies[region_anomalies["date"] == day]

        result = update_tracker(day, todays_product, todays_region, state_path=state_path)

        is_last_day = (i == len(all_dates) - 1)
        ai_summary, ai_error = None, None
        if generate_ai_for_all or is_last_day:
            try:
                from ai_interpreter import generate_summary
                ai_summary = generate_summary(str(day.date()), result)
            except Exception as e:
                ai_error = str(e)

        parts = [
            f"# Daily Sales Report — {day.date()}",
            "",
            f"**Total revenue today:** {day_df['revenue'].sum():,.2f}",
            "",
        ]
        if ai_summary:
            parts += ["## Summary", ai_summary, ""]
        elif ai_error:
            parts += ["## Summary", f"*(AI summary unavailable: {ai_error})*", ""]
        elif not generate_ai_for_all and not is_last_day:
            parts += ["## Summary", "*(AI summary skipped for historical backfill day — only the most recent day gets a written summary by default.)*", ""]

        parts += ["## Findings", _findings_to_markdown(result)]

        report_path = reports_dir / f"{day.date()}.md"
        report_path.write_text("\n".join(parts), encoding="utf-8")
        written_paths.append(report_path)

        if progress_callback:
            progress_callback(i + 1, len(all_dates), str(day.date()))

    return written_paths