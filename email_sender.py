"""
email_sender.py
Sends a daily report by email, with the PDF version attached, using
Gmail's SMTP server. The SENDING account is the app's own Gmail
address (configured once via secrets.toml with an App Password) — the
RECIPIENT can be any email address, doesn't need to be Gmail.
"""

import os
import smtplib
from email.message import EmailMessage


def _get_sender_credentials():
    """Reads sender credentials from Streamlit secrets if available,
    otherwise falls back to environment variables."""
    try:
        import streamlit as st
        email_secrets = st.secrets.get("email", {})
        sender = email_secrets.get("sender_address")
        password = email_secrets.get("app_password")
        if sender and password:
            return sender, password
    except Exception:
        pass

    sender = os.environ.get("REPORT_SENDER_EMAIL")
    password = os.environ.get("REPORT_SENDER_APP_PASSWORD")
    return sender, password


def is_email_configured() -> bool:
    sender, password = _get_sender_credentials()
    return bool(sender and password)


def send_report_email(to_email: str, date_label: str, parsed_report: dict,
                       pdf_bytes: bytes, source_label: str = "") -> tuple[bool, str]:
    """
    Sends the report to to_email, with the PDF attached.
    Returns (success, message) — never raises, so a failed send never
    crashes the dashboard.
    """
    sender, app_password = _get_sender_credentials()
    if not sender or not app_password:
        return False, (
            "Email sending isn't configured yet. An [email] section with "
            "sender_address and app_password is needed in secrets.toml."
        )

    msg = EmailMessage()
    msg["Subject"] = f"Daily Sales Report - {date_label}"
    msg["From"] = sender
    msg["To"] = to_email

    revenue_line = f"Total revenue: {parsed_report['revenue']}\n\n" if parsed_report.get("revenue") else ""
    body = (
        f"Your daily sales report for {date_label} is attached as a PDF.\n\n"
        f"{revenue_line}"
        f"Summary:\n{parsed_report.get('summary', '')}\n\n"
        f"--\nSource: {source_label}\n"
        f"This is an automated report."
    )
    msg.set_content(body)

    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=f"sales_report_{date_label.replace(' ', '_').replace(',', '')}.pdf",
    )

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
            server.starttls()
            server.login(sender, app_password)
            server.send_message(msg)
        return True, f"Report emailed to {to_email}."
    except smtplib.SMTPAuthenticationError:
        return False, (
            "Gmail rejected the sender credentials. Double check the app "
            "password in secrets.toml (must be a 16-character App Password, "
            "not your regular Gmail password)."
        )
    except Exception as e:
        return False, f"Failed to send email: {e}"