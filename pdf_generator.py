"""
pdf_generator.py
Turns a parsed report (the same dict dashboard.py already produces via
parse_report()) into a formatted PDF. Uses fpdf2, a pure-Python PDF
library with no system-level dependencies — important since this needs
to work reliably on a Windows machine without extra installs.
"""

import re
from fpdf import FPDF


def _sanitize_for_pdf(text: str) -> str:
    """fpdf2's default core fonts (Helvetica etc.) only support Latin-1
    characters. Our reports use typographic characters (em-dashes, curly
    quotes) that aren't in that range, which crashes PDF generation
    entirely if left as-is. Swap them for safe ASCII equivalents."""
    replacements = {
        "\u2014": "-",   # em dash —
        "\u2013": "-",   # en dash –
        "\u2018": "'",   # left single quote '
        "\u2019": "'",   # right single quote '
        "\u201c": '"',   # left double quote "
        "\u201d": '"',   # right double quote "
        "\u2026": "...",  # ellipsis …
        "\u25aa": "-",   # small black square bullet
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)
    return text


def _markdown_to_html(text: str) -> str:
    """Converts the light markdown our reports use (**bold**, "- " bullets,
    blank-line-separated paragraphs) into the small HTML subset fpdf2's
    write_html() understands."""
    text = _sanitize_for_pdf(text)
    lines = text.split("\n")
    html_parts = []
    in_list = False

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            continue

        line_html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)

        if line.startswith("- "):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            html_parts.append(f"<li>{line_html[2:]}</li>")
        else:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f"<p>{line_html}</p>")

    if in_list:
        html_parts.append("</ul>")

    return "\n".join(html_parts)


def generate_pdf(date_label: str, parsed_report: dict, source_label: str = "") -> bytes:
    """
    date_label: display-formatted date, e.g. "August 26, 2026"
    parsed_report: dict with 'summary', 'findings', 'revenue' keys
    source_label: optional, e.g. "Demo Data" or an uploaded dataset name

    Returns the PDF file content as bytes.
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    pdf.set_font("Helvetica", "B", 18)
    pdf.multi_cell(0, 10, _sanitize_for_pdf(f"Daily Sales Report - {date_label}"), new_x="LMARGIN", new_y="NEXT")

    if source_label:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 6, _sanitize_for_pdf(f"Data source: {source_label}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

    pdf.ln(4)

    if parsed_report.get("revenue"):
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, _sanitize_for_pdf(f"Total revenue: {parsed_report['revenue']}"), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, "Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=11)
    pdf.write_html(_markdown_to_html(parsed_report.get("summary", "")))
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, "Findings", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=11)
    pdf.write_html(_markdown_to_html(parsed_report.get("findings", "")))

    return bytes(pdf.output())