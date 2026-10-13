"""
dashboard.py
A local web dashboard for browsing daily sales reports. Each logged-in
user only ever sees data they've uploaded themselves — there is no
demo/example dataset shown anywhere in this app. A brand-new user with
no uploads yet sees only a prompt to upload their first CSV; reports
only exist once they've generated them from their own data.

Run with:  streamlit run dashboard.py
"""

import hashlib
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from batch_processor import validate_uploaded_data, process_dataset
from pdf_generator import generate_pdf
from auth import create_user, verify_user
from email_sender import send_report_email, is_email_configured
from voice_ui import render_voice_chat

UPLOADS_ROOT = Path("uploads")


def user_folder_name(email: str) -> str:
    """Turns a logged-in user's email into a stable, private folder name
    — the same email always maps to the same folder (so their data
    persists across logins), but the folder name itself doesn't expose
    the email in plain text on disk."""
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()[:16]


def list_user_datasets(email: str):
    """Returns [(display_name, folder_path), ...] for every dataset this
    user has ever uploaded — read fresh from disk each time, so it's
    genuinely tied to their account, not to a browser session that
    disappears on logout or refresh."""
    user_dir = UPLOADS_ROOT / user_folder_name(email)
    if not user_dir.exists():
        return []
    datasets = []
    for folder in sorted(user_dir.iterdir()):
        if folder.is_dir():
            name_file = folder / "_display_name.txt"
            display_name = name_file.read_text().strip() if name_file.exists() else folder.name
            datasets.append((display_name, folder))
    return datasets

st.set_page_config(page_title="Daily Sales Reports", layout="wide")


def _google_auth_available() -> bool:
    """Whether Google sign-in has actually been configured (via
    .streamlit/secrets.toml). If not set up, we hide the button instead
    of showing something that would error when clicked."""
    try:
        return st.user.is_logged_in is not None
    except Exception:
        return False


def _is_logged_in() -> bool:
    """True if the visitor is authenticated via EITHER Google sign-in
    or the manual email/password system."""
    google_logged_in = False
    try:
        google_logged_in = st.user.is_logged_in
    except Exception:
        pass
    return google_logged_in or st.session_state.get("manual_logged_in", False)


def _current_user_email() -> str:
    """Returns the logged-in user's email, regardless of which sign-in
    method they used — so the rest of the app doesn't need to care."""
    try:
        if st.user.is_logged_in:
            return st.user.email
    except Exception:
        pass
    return st.session_state.get("manual_user_email", "")


def _login_screen():
    st.title("Daily Sales Reports")
    st.subheader("Please log in to continue")

    if _google_auth_available():
        st.button("Log in with Google", on_click=st.login, type="primary")
        st.markdown("---")
        st.caption("Or use an email/password account:")

    tab_login, tab_signup = st.tabs(["Log in", "Sign up"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in")
            if submitted:
                ok, msg = verify_user(email, password)
                if ok:
                    st.session_state.manual_logged_in = True
                    st.session_state.manual_user_email = email.strip().lower()
                    st.rerun()
                else:
                    st.error(msg)

    with tab_signup:
        with st.form("signup_form"):
            new_email = st.text_input("Email", key="signup_email")
            new_password = st.text_input("Password (min 8 characters)", type="password", key="signup_pw")
            confirm_password = st.text_input("Confirm password", type="password", key="signup_pw2")
            submitted = st.form_submit_button("Create account")
            if submitted:
                if new_password != confirm_password:
                    st.error("Passwords don't match.")
                else:
                    ok, msg = create_user(new_email, new_password)
                    if ok:
                        st.success(f"{msg} You can now log in from the 'Log in' tab.")
                    else:
                        st.error(msg)

    st.stop()


if not _is_logged_in():
    _login_screen()

user_email = _current_user_email()


def slugify(name: str) -> str:
    """Turns a filename like 'Q3 Sales (final).csv' into a safe folder
    name like 'q3_sales_final' — avoids path issues from arbitrary
    uploaded filenames."""
    stem = Path(name).stem
    return re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_") or "dataset"


def format_date_label(date_str):
    """Turns '2026-08-26' into 'August 26, 2026' for display only —
    the underlying value used for file lookups stays as-is."""
    return pd.Timestamp(date_str).strftime("%B %d, %Y")


def list_report_dates(reports_dir: Path):
    if not reports_dir.exists():
        return []
    return sorted(p.stem for p in reports_dir.glob("*.md"))


def load_report(reports_dir: Path, date_str: str):
    return (reports_dir / f"{date_str}.md").read_text(encoding="utf-8")


def parse_report(text: str):
    summary_match = re.search(r"## Summary\n(.*?)(?=\n## |\Z)", text, re.DOTALL)
    findings_match = re.search(r"## Findings\n(.*)", text, re.DOTALL)
    revenue_match = re.search(r"\*\*Total revenue today:\*\*\s*([\d,.]+)", text)

    return {
        "summary": summary_match.group(1).strip() if summary_match else "(no summary found)",
        "findings": findings_match.group(1).strip() if findings_match else "(no findings found)",
        "revenue": revenue_match.group(1) if revenue_match else None,
    }


def load_open_anomalies(tracker_state: Path):
    if not tracker_state.exists():
        return {}
    return json.loads(tracker_state.read_text())


def load_revenue_trend(sales_csv: Path, up_to_date: str):
    df = pd.read_csv(sales_csv, parse_dates=["date"])
    daily = df.groupby("date", as_index=False)["revenue"].sum()
    daily = daily[daily["date"] <= pd.Timestamp(up_to_date)]
    return daily


# =======================================================================
# Sidebar: choose which of THIS user's own datasets to view
# =======================================================================
st.sidebar.title("Daily Sales Reports")

st.sidebar.caption(f"Logged in as: {user_email}")


def _logout():
    try:
        if st.user.is_logged_in:
            st.logout()
            return
    except Exception:
        pass
    st.session_state.manual_logged_in = False
    st.session_state.manual_user_email = ""


st.sidebar.button("Log out", on_click=_logout)
st.sidebar.markdown("---")

# Read fresh from THIS user's own persistent folder on disk each time —
# scoped by their account (email), never a browser session. There is no
# demo/example data anywhere in this app — only data this account has
# uploaded and generated itself.
my_datasets = list_user_datasets(user_email)
my_dataset_names = [name for name, _ in my_datasets]

if my_dataset_names:
    source = st.sidebar.selectbox("Data source", options=my_dataset_names, index=0)
    dataset_dir = dict(my_datasets)[source]
    reports_dir = dataset_dir / "reports"
    sales_csv = dataset_dir / "sales_data.csv"
    tracker_state = dataset_dir / "open_anomalies.json"

st.sidebar.markdown("---")

# =======================================================================
# Sidebar: upload a new dataset
# =======================================================================
with st.sidebar.expander("📤 Upload your own data", expanded=not my_dataset_names):
    st.caption(
        "CSV with columns: date, region, product, units_sold, revenue, "
        "transaction_count. Roughly 60-90+ days works best — the detector "
        "needs several weeks of history to know what 'normal' looks like."
    )
    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

    if uploaded_file is not None:
        try:
            upload_df = pd.read_csv(uploaded_file, parse_dates=["date"])
        except Exception as e:
            st.error(f"Couldn't read this file as a CSV: {e}")
            upload_df = None

        if upload_df is not None:
            issues = validate_uploaded_data(upload_df)
            blocking_issues = [i for i in issues if "Only" not in i]
            warnings_only = [i for i in issues if "Only" in i]

            for w in warnings_only:
                st.warning(w)

            if blocking_issues:
                for issue in blocking_issues:
                    st.error(issue)
            else:
                st.success(f"Looks good — {upload_df['date'].nunique()} day(s), "
                           f"{upload_df['region'].nunique()} region(s), "
                           f"{upload_df['product'].nunique()} product(s).")

                dataset_name = st.text_input(
                    "Name this dataset", value=slugify(uploaded_file.name)
                )
                ai_for_all = st.checkbox(
                    "Generate an AI summary for every day (slower, uses more API calls — "
                    "by default only the most recent day gets one)",
                    value=False,
                )

                if st.button("Generate reports", type="primary"):
                    user_dir = UPLOADS_ROOT / user_folder_name(user_email)
                    dataset_dir = user_dir / slugify(dataset_name)
                    dataset_dir.mkdir(parents=True, exist_ok=True)
                    (dataset_dir / "_display_name.txt").write_text(dataset_name)
                    upload_df.to_csv(dataset_dir / "sales_data.csv", index=False)

                    progress_bar = st.progress(0.0, text="Starting...")

                    def _on_progress(i, total, date_str):
                        progress_bar.progress(i / total, text=f"Processing {date_str} ({i}/{total})")

                    with st.spinner("Running detection across the full dataset..."):
                        written = process_dataset(
                            upload_df, dataset_dir,
                            generate_ai_for_all=ai_for_all,
                            progress_callback=_on_progress,
                        )

                    progress_bar.progress(1.0, text="Done!")
                    st.success(f"Generated {len(written)} reports for '{dataset_name}'. "
                               f"Select it from 'Data source' above to browse them.")

                    # If the most recent report is for TODAY's real date,
                    # automatically email it to the account's own address
                    # — no separate action needed, since we already know
                    # who's logged in.
                    last_report_path = written[-1]
                    last_date_str = last_report_path.stem
                    if last_date_str == str(date.today()) and is_email_configured():
                        last_report_text = last_report_path.read_text(encoding="utf-8")
                        last_parsed = parse_report(last_report_text)
                        last_pdf_bytes = generate_pdf(
                            format_date_label(last_date_str), last_parsed, source_label=dataset_name
                        )
                        sent_ok, sent_msg = send_report_email(
                            user_email, format_date_label(last_date_str), last_parsed,
                            last_pdf_bytes, source_label=dataset_name,
                        )
                        if sent_ok:
                            st.success(f"📧 {sent_msg}")
                        else:
                            st.warning(f"Report generated, but emailing it failed: {sent_msg}")

                    st.rerun()

st.sidebar.markdown("---")

# =======================================================================
# Gate: a user with no uploaded data yet sees ONLY this prompt — nothing
# else on the page renders. There is no fallback content and no way to
# preview anything until they've generated their first report.
# =======================================================================
if not my_dataset_names:
    st.title("Welcome to Daily Sales Reports")
    st.info(
        "👋 You haven't generated any reports yet. Use the "
        "**'📤 Upload your own data'** section in the sidebar to upload "
        "a CSV and generate your first report."
    )
    st.stop()

# =======================================================================
# Report date picker
# =======================================================================
dates = list_report_dates(reports_dir)

if not dates:
    st.warning(
        f"No reports found for '{source}' yet. Try uploading data and "
        f"clicking 'Generate reports' in the sidebar again."
    )
    st.stop()

today_str = str(date.today())
is_today_available = today_str in dates
default_index = dates.index(today_str) if is_today_available else len(dates) - 1

selected_date = st.sidebar.selectbox(
    "Select a report date",
    options=dates,
    index=default_index,
    format_func=format_date_label,
)

st.sidebar.caption(
    f"{len(dates)} report(s) available: "
    f"{format_date_label(dates[0])} → {format_date_label(dates[-1])}"
)
if not is_today_available:
    st.sidebar.caption(
        f"ℹ️ No report for today ({format_date_label(today_str)}) yet — "
        f"showing the most recent one available instead."
    )

# =======================================================================
# Main panel
# =======================================================================
st.title(f"Daily Sales Report — {format_date_label(selected_date)}")
st.caption(f"Data source: {source}")

report_text = load_report(reports_dir, selected_date)
parsed = parse_report(report_text)

pdf_bytes = generate_pdf(format_date_label(selected_date), parsed, source_label=source)

col_pdf, col_email = st.columns([1, 1])
with col_pdf:
    st.download_button(
        label="📄 Download as PDF",
        data=pdf_bytes,
        file_name=f"sales_report_{selected_date}.pdf",
        mime="application/pdf",
    )
with col_email:
    if is_email_configured():
        if st.button("📧 Email this report to me"):
            sent_ok, sent_msg = send_report_email(
                user_email, format_date_label(selected_date), parsed, pdf_bytes, source_label=source
            )
            if sent_ok:
                st.success(sent_msg)
            else:
                st.error(sent_msg)
    else:
        st.caption("Email sending not configured yet.")

col1, col2 = st.columns([1, 2])

with col1:
    if parsed["revenue"]:
        st.metric("Total revenue", f"{parsed['revenue']}")

with col2:
    st.subheader("Summary")
    st.markdown(parsed["summary"])

st.markdown("---")
st.subheader("Findings")
st.markdown(parsed["findings"])

st.markdown("---")
st.subheader("Revenue trend")
trend = load_revenue_trend(sales_csv, selected_date)
st.line_chart(trend.set_index("date")["revenue"])

st.markdown("---")
st.subheader("Currently open anomalies (latest state)")
open_state = load_open_anomalies(tracker_state)

if open_state:
    rows = []
    for key, info in open_state.items():
        parts = key.split("::")
        level = parts[0]
        label = f"{parts[1]} — {parts[2]}" if level == "product" else f"{parts[1]} (region-wide)"
        rows.append({
            "Finding": label,
            "Days open": info["days_open"],
            "First seen": info["first_seen"],
        })
    st.dataframe(pd.DataFrame(rows).sort_values("Days open", ascending=False), width="stretch")
else:
    st.success("No anomalies currently open.")