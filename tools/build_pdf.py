"""Render a Markdown file in docs/ to a print-ready PDF (pandoc + Chromium).

Run: python tools/build_pdf.py docs/protocol.md [--out docs/pdf/protocol.pdf]
       [--title "..."] [--font-size 10]

Needs pandoc on the PATH and Playwright for Python (requirements-analysis.txt).
Images resolve relative to the Markdown file.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

CSS = """
@page { size: Letter; margin: 0.7in 0.75in 0.75in 0.75in; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: "Source Serif 4", "Source Serif Pro", Georgia, "DejaVu Serif", serif;
       font-size: FONTpt; line-height: 1.38; color: #1d1d1f; margin: 0; }
h1 { font-size: 1.55em; line-height: 1.2; margin: 0 0 0.5em; }
h2 { font-size: 1.15em; margin: 1.1em 0 0.35em; break-after: avoid; }
h3 { font-size: 1.0em; margin: 0.9em 0 0.3em; break-after: avoid; }
p, ul, ol { margin: 0 0 0.55em; }
li { margin: 0.12em 0; }
ul, ol { padding-left: 1.3em; }
table { border-collapse: collapse; width: 100%; margin: 0.4em 0 0.8em; font-size: 0.9em; }
tr { break-inside: avoid; }
th, td { border-bottom: 1px solid #c9c9cf; padding: 0.28em 0.45em; text-align: left;
         vertical-align: top; }
th { border-bottom: 1.5px solid #6e6e73; font-weight: 600; }
code { font-family: "DejaVu Sans Mono", Menlo, monospace; font-size: 0.86em; }
img { max-width: 100%; }
figure { margin: 0.5em 0 0.9em; break-inside: avoid; text-align: center; }
figure img { max-height: 4.1in; border: 1px solid #d2d2d7; }
figcaption { font-size: 0.85em; color: #515154; text-align: left; margin-top: 0.3em; }
a { color: #1a5fb4; text-decoration: none; }
strong { font-weight: 650; }
"""


def _figures(body: str) -> str:
    """Turn a paragraph that holds only an image into a figure captioned with its alt text."""
    def repl(m: re.Match) -> str:
        img = m.group(1)
        alt = re.search(r'alt="([^"]*)"', img)
        caption = alt.group(1) if alt else ""
        return f"<figure>{img}<figcaption>{caption}</figcaption></figure>" if caption else m.group(0)
    return re.sub(r"<p>(<img [^>]*?/?>)</p>", repl, body, flags=re.S)


def build(md: Path, out: Path, title: str | None, font_size: float) -> Path:
    md = md.resolve()
    html_body = subprocess.run(
        ["pandoc", str(md), "--from", "gfm", "--to", "html5"],
        check=True, capture_output=True, text=True).stdout
    html_body = _figures(html_body)
    title = title or md.stem.replace("_", " ").title()
    page = (f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<base href='{md.parent.as_uri()}/'><title>{title}</title>"
            f"<style>{CSS.replace('FONT', str(font_size))}</style></head>"
            f"<body>{html_body}</body></html>")
    out.parent.mkdir(parents=True, exist_ok=True)
    footer = ("<div style='font-size:7.5pt;color:#6e6e73;width:100%;padding:0 0.75in;"
              "display:flex;justify-content:space-between;font-family:sans-serif'>"
              f"<span>{title}</span><span><span class='pageNumber'></span> of "
              "<span class='totalPages'></span></span></div>")
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as fh:
        fh.write(page)
        tmp = Path(fh.name)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        tab = browser.new_page()
        tab.goto(tmp.as_uri())
        tab.wait_for_load_state("networkidle")
        tab.pdf(path=str(out), format="Letter", print_background=True,
                display_header_footer=True, header_template="<span></span>",
                footer_template=footer,
                margin={"top": "0.7in", "bottom": "0.75in", "left": "0.75in", "right": "0.75in"})
        browser.close()
    tmp.unlink()
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("markdown", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--title")
    ap.add_argument("--font-size", type=float, default=10.0)
    args = ap.parse_args()
    out = args.out or ROOT / "docs" / "pdf" / f"{args.markdown.stem}.pdf"
    print(build(args.markdown, out, args.title, args.font_size))


if __name__ == "__main__":
    main()
