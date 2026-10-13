"""
ai_interpreter.py
Takes the structured findings from anomaly_tracker.update_tracker() and
asks Gemini to write a short, readable summary — the AI only ever sees
PRE-COMPUTED findings (numbers we already calculated), never raw
transaction data. This means every claim in the summary traces back to
a real statistic, not something the model guessed.
"""

import os
from google import genai

MODEL = "gemini-3.6-flash"


def _format_findings(result: dict) -> str:
    """Turn the new/ongoing/resolved lists into a compact text block
    the model can read — this is the ONLY data the AI ever sees."""
    lines = []

    if result["new"]:
        lines.append("NEW TODAY:")
        for f in result["new"]:
            label = f"{f['region']} — {f['product']}" if f["level"] == "product" else f"{f['region']} (region-wide)"
            lines.append(f"  - {label}: z-score {f['z_score']:.2f}")

    if result["ongoing"]:
        lines.append("\nONGOING:")
        for f in result["ongoing"]:
            label = f"{f['region']} — {f['product']}" if f["level"] == "product" else f"{f['region']} (region-wide)"
            lines.append(f"  - {label}: ongoing {f['days_open']} day(s), first seen {f['first_seen']}")

    if result["resolved"]:
        lines.append("\nRESOLVED:")
        for f in result["resolved"]:
            label = f"{f['region']} — {f['product']}" if f["product"] else f"{f['region']} (region-wide)"
            lines.append(f"  - {label}: was open {f['days_open']} day(s)")

    if not lines:
        lines.append("No anomalies found today. Everything within normal range.")

    return "\n".join(lines)


def generate_summary(today, result: dict) -> str:
    """Calls Gemini with the structured findings and returns a short
    plain-English summary suitable for a morning report."""
    findings_text = _format_findings(result)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Run:\n"
            '  $env:GEMINI_API_KEY = "your-key-here"\n'
            "in this terminal session before running this script."
        )

    client = genai.Client(api_key=api_key)

    prompt = f"""You are writing a short daily sales report summary for a business manager.
Below are today's ({today}) pre-computed statistical findings from an automated
anomaly detection system. Do not invent any numbers not present below.

{findings_text}

Write a summary with:
1. A one-sentence headline capturing the most important thing today.
2. 2-4 sentences of plain-English explanation of the findings above.
3. If anything has been ongoing 5+ days, explicitly call it out as needing attention.
4. If there's nothing anomalous, say so briefly and confidently — don't invent concerns.

Keep it under 120 words total. Write for a manager reading this in 30 seconds, not a data analyst."""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
    )

    return response.text


if __name__ == "__main__":
    # A quick standalone test using a hand-built example of what
    # update_tracker() actually returns, based on a real run (Aug 26)
    # from earlier in this project — so you can test this file works
    # BEFORE wiring it into the full daily pipeline.
    sample_result = {
        "new": [
            {"level": "region", "region": "Karachi", "product": None, "z_score": -3.09, "days_open": 1, "first_seen": "2026-08-26"},
        ],
        "ongoing": [
            {"level": "product", "region": "Karachi", "product": "Smart Watch", "z_score": -6.44, "days_open": 11, "first_seen": "2026-08-16"},
            {"level": "product", "region": "Lahore", "product": "Smart Watch", "z_score": -7.25, "days_open": 11, "first_seen": "2026-08-16"},
            {"level": "product", "region": "Islamabad", "product": "Smart Watch", "z_score": -3.44, "days_open": 11, "first_seen": "2026-08-16"},
        ],
        "resolved": [
            {"level": "product", "region": "Islamabad", "product": "Bluetooth Speaker", "days_open": 1, "first_seen": "2026-08-25"},
        ],
    }

    summary = generate_summary("2026-08-26", sample_result)
    print("=== AI-Generated Summary ===\n")
    print(summary)