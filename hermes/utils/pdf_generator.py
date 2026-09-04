"""Tailored resume PDF generation.

Primary: headless Chromium via Playwright (markdown -> styled HTML ->
print-to-PDF). Chromium's renderer is identical to what a human would
print, so output is consistent. Fallback: WeasyPrint (needs system
pango/cairo). Final fallback: keep the HTML and tell the user to print
from a browser — never silently drop the artifact.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger("hermes.pdf")

_CSS = """
@page { size: A4; margin: 16mm 15mm; }
body { font-family: 'Helvetica', 'Arial', sans-serif; font-size: 9.5pt;
       color: #1a1a1a; line-height: 1.42; }
h1 { font-size: 17pt; text-align: center; margin: 0 0 2pt 0;
     letter-spacing: 1pt; text-transform: uppercase; }
h2 { font-size: 11pt; border-bottom: 1.2pt solid #1a1a1a;
     margin: 12pt 0 4pt 0; padding-bottom: 1pt;
     text-transform: uppercase; letter-spacing: 0.5pt; }
h3 { font-size: 10pt; margin: 8pt 0 1pt 0; }
p  { margin: 2pt 0; }
ul { margin: 2pt 0 4pt 0; padding-left: 14pt; }
li { margin: 1.5pt 0; }
.contact { text-align: center; font-size: 8.5pt; margin: 0 0 4pt 0; }
.meta { font-size: 8.5pt; color: #333; font-style: italic; }
a { color: #1a1a1a; text-decoration: none; }
"""


def _md_to_html_headings(body: str) -> str:
    """Minimal markdown->HTML for the subset we generate (no dep on 'markdown')."""
    lines = []
    in_list = False
    for raw in body.splitlines():
        line = raw.rstrip()
        if line.startswith("### "):
            line = f"<h3>{_inline(line[4:])}</h3>"
        elif line.startswith("## "):
            line = f"<h2>{_inline(line[3:])}</h2>"
        elif line.startswith("# "):
            line = f"<h1>{_inline(line[2:])}</h1>"
        elif line.startswith("- "):
            if not in_list:
                line, in_list = "<ul><li>" + _inline(line[2:]) + "</li>", True
            else:
                line = "<li>" + _inline(line[2:]) + "</li>"
        elif not line.strip():
            if in_list:
                line, in_list = "</ul>", False
            else:
                line = ""
        else:
            if in_list:
                # close list before a paragraph
                line = "</ul><p>" + _inline(line) + "</p>"
                in_list = False
            else:
                line = "<p>" + _inline(line) + "</p>"
        lines.append(line)
    if in_list:
        lines.append("</ul>")
    return "\n".join(lines)


def _inline(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1", text)
    return text


def markdown_to_html(markdown_text: str) -> str:
    body = _md_to_html_headings(markdown_text)
    # First line after h1 = contact line
    return f"<html><head><style>{_CSS}</style></head><body>{body}</body></html>"


def generate_pdf(markdown_text: str, output_path: Path) -> Path:
    """Write resume.pdf next to the tailored artifacts. Best-effort chain."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html = markdown_to_html(markdown_text)
    html_path = output_path.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(html_path.resolve().as_uri())
            page.pdf(path=str(output_path), format="A4", print_background=True)
            browser.close()
        logger.debug("PDF via Playwright: %s", output_path)
        return output_path
    except Exception as exc:  # noqa: BLE001
        logger.warning("Playwright PDF failed (%s) — trying WeasyPrint", exc)

    try:
        from weasyprint import HTML

        HTML(string=html).write_pdf(str(output_path))
        logger.debug("PDF via WeasyPrint: %s", output_path)
        return output_path
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "WeasyPrint failed (%s). HTML written to %s — open it in a "
            "browser and print to PDF manually.", exc, html_path
        )
        return html_path
