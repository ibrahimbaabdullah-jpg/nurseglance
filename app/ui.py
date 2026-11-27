"""Shared look for every page (version 1.2): design tokens, the top bar and the footer.

The colors, fonts, radii and spacing follow the design mockup (screenshots in docs/design/):
a white top bar with the NurseGlance mark, a research-prototype pill,
two segmented controls (view and mode) and a primary "Start study mode" button, over
a light grey page of white cards. Streamlit draws the controls, and the CSS below
gives them the mockup's look; the cards themselves are plain HTML.

The fonts (Inter and Space Grotesk, SIL Open Font License) are served from static/,
so a study session sends no request to a font service.
"""
from __future__ import annotations

import base64
import html

import streamlit as st

ACCENT = "#1C5D86"

LOGO = ('<svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">'
        f'<rect x="1" y="1" width="26" height="26" rx="7" fill="{ACCENT}"></rect>'
        '<path d="M6 14c2.2-3.6 5-5.4 8-5.4s5.8 1.8 8 5.4c-2.2 3.6-5 5.4-8 5.4S8.2 17.6 6 14z" fill="none" '
        'stroke="#FFFFFF" stroke-width="1.8" stroke-linejoin="round"></path>'
        '<circle cx="14" cy="14" r="2.4" fill="#FFFFFF"></circle></svg>')

# As an <img>: Streamlit's HTML sanitizer drops some inline SVG.
LOGO_IMG = ('<img src="data:image/svg+xml;base64,' + base64.b64encode(
    LOGO.replace('aria-hidden="true"', 'xmlns="http://www.w3.org/2000/svg"').encode()).decode()
    + '" width="28" height="28" alt="">')

DATA_SOURCE = ("Data source: MIMIC-IV Clinical Database Demo on FHIR v2.1.0 (PhysioNet, ODbL v1.0). De-identified; "
               "dates are shifted into the future. Research prototype: not for clinical use and not clinically "
               "validated.")

CSS = """
<style>
:root {
  --ng-bg:#F3F5F6; --ng-surface:#FFFFFF; --ng-border:#DCE2E6; --ng-divider:#EEF1F3; --ng-track:#EBEFF2;
  --ng-text:#16212B; --ng-text2:#3A4651; --ng-muted:#5A6671; --ng-muted2:#4A5560;
  --ng-accent:#1C5D86; --ng-accent-dark:#123F5C;
  --ng-warn:#A84A0A; --ng-warn-strong:#8A3B06; --ng-warn-bg:#FFF1E3; --ng-warn-bg2:#FFF8F1;
  --ng-warn-border:#F0C9A5; --ng-warn-border2:#F3D3B5;
  --ng-info-bg:#E8F1F7; --ng-info-border:#C7DBE8; --ng-info-border2:#9FBDD2;
  --ng-head:'Space Grotesk', Inter, sans-serif;
}
.stApp {background:var(--ng-bg); color:var(--ng-text); font-variant-numeric:tabular-nums;}
/* Streamlit's own header and page menu give way to the top bar below. */
header[data-testid="stHeader"] {display:none;}
[data-testid="stSidebarCollapseButton"] {display:none;}
[data-testid="stMainBlockContainer"] {padding:0 28px 24px !important; max-width:none;}
section[data-testid="stSidebar"] {background:var(--ng-surface); border-right:1px solid var(--ng-border);
  width:252px !important; min-width:252px !important; max-width:252px !important;}
[data-testid="stSidebarHeader"] {display:none;}
[data-testid="stSidebarUserContent"] {padding:18px 0 24px !important; margin:0 !important;}
[data-testid="stSidebarContent"] {padding-left:16px !important; padding-right:16px !important;}
.st-key-ng-qcard {padding:12px 13px !important;}
section[data-testid="stSidebar"] h3, section[data-testid="stSidebar"] h4 {font-size:17px !important; line-height:1.35;}
/* forms and inputs: white on the grey page, as in the mockup's cards */
[data-testid="stForm"] {background:var(--ng-surface); border:1px solid var(--ng-border) !important; border-radius:12px;
  padding:18px 20px;}
section[data-testid="stSidebar"] [data-testid="stForm"] {padding:0; border:0 !important; background:transparent;}
.stApp [data-testid="stTextInputRootElement"], .stApp [data-testid="stTextAreaRootElement"],
.stApp [data-testid="stNumberInputContainer"] {background:var(--ng-surface) !important;
  border:1px solid var(--ng-border) !important;}
.stApp [data-testid="stTextInputRootElement"]:focus-within, .stApp [data-testid="stTextAreaRootElement"]:focus-within,
.stApp [data-testid="stNumberInputContainer"]:focus-within {border-color:var(--ng-accent) !important;}
.stApp [data-testid="stNumberInputContainer"] *, .stApp [data-testid="stTextInputRootElement"] input,
.stApp [data-testid="stTextAreaRootElement"] textarea {background-color:transparent;}
a {color:var(--ng-accent);} a:hover {color:var(--ng-accent-dark);}

/* ---- top bar: full width, white, under it a hairline ---- */
.st-key-ng-topbar, .st-key-ng-vnbar {margin:0 -28px; width:calc(100% + 56px) !important; max-width:none !important;
  box-sizing:border-box;}
.st-key-ng-topbar {padding:14px 28px;
  background:var(--ng-surface); border-bottom:1px solid var(--ng-border); gap:14px 20px !important; min-height:60px;}
.ng-brand {display:flex; align-items:center; gap:10px; flex-wrap:wrap;}
.ng-brand-name {font-family:var(--ng-head); font-size:20px; font-weight:700; letter-spacing:-0.01em;
  color:var(--ng-text); margin-right:10px;}
.ng-proto {font-size:12px; font-weight:600; color:var(--ng-warn-strong); background:var(--ng-warn-bg);
  border:1px solid var(--ng-warn-border2); padding:5px 10px; border-radius:999px; white-space:nowrap;}
.ng-topnote {font-size:14px; color:var(--ng-text2); white-space:nowrap;}
.ng-topnote b {font-weight:600; color:var(--ng-text);}

/* segmented controls: grey track, the chosen option a white raised pill */
.st-key-ng-topbar [data-testid="stButtonGroup"], .st-key-ng-ctx [data-testid="stButtonGroup"],
.ng-seg [data-testid="stButtonGroup"] {
  background:var(--ng-track); border-radius:9px; padding:3px; gap:2px;}
.st-key-ng-topbar [data-testid="stButtonGroup"] button, .st-key-ng-ctx [data-testid="stButtonGroup"] button {
  min-height:38px; padding:0 14px; border:0 !important; border-radius:7px !important; background:transparent;
  color:var(--ng-muted2); font-size:14px; font-weight:500; box-shadow:none; margin:0 !important;}
.st-key-ng-topbar [data-testid="stButtonGroup"] button p, .st-key-ng-ctx [data-testid="stButtonGroup"] button p {
  font-size:14px; font-weight:inherit;}
.st-key-ng-topbar [data-testid="stButtonGroup"] button[aria-checked="true"],
.st-key-ng-ctx [data-testid="stButtonGroup"] button[aria-checked="true"] {
  background:var(--ng-surface) !important; color:var(--ng-text) !important; font-weight:600;
  box-shadow:0 1px 2px rgba(22,33,43,0.12);}
.st-key-ng-topbar [data-testid="stButtonGroup"] button:hover, .st-key-ng-ctx [data-testid="stButtonGroup"] button:hover {
  color:var(--ng-text);}
.st-key-ng-topbar button[kind="primary"] {min-height:44px; padding:0 18px; border:0; border-radius:9px;
  background:var(--ng-accent); font-size:14px; font-weight:600;}
.st-key-ng-topbar button[kind="primary"]:hover {background:var(--ng-accent-dark);}
.st-key-ng-topbar button[kind="primary"] p {font-size:14px; font-weight:600;}

/* ---- main column: centered, like the mockup's 1520 px page ---- */
.st-key-ng-main {max-width:1520px; margin:0 auto; padding-top:12px; gap:12px !important;}
.st-key-ng-ctx {gap:10px 16px !important;}
.ng-ctx-label {font-size:12px; font-weight:600; letter-spacing:.06em; text-transform:uppercase;
  color:var(--ng-muted);}
.ng-foot {margin:4px 0 0; font-size:12px; color:var(--ng-muted);}
.ng-foot a {color:var(--ng-muted); text-decoration:underline;}

/* cards made of Streamlit containers (border=True) */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {}
div[class*="st-key-ng-card"] {background:var(--ng-surface); border:1px solid var(--ng-border) !important;
  border-radius:12px !important; padding:16px 18px !important;}
h1, h2, h3, h4 {font-family:var(--ng-head) !important; letter-spacing:-0.01em;}

/* the tabbed view's chart tabs: a radio group drawn as an EHR tab strip */
.st-key-ng-tabbar {border-bottom:1px solid var(--ng-border); margin:-6px -18px 6px; padding:0 18px;
  width:auto !important; max-width:none !important; align-self:stretch;}
.st-key-ng-tabbar [data-testid="stRadioGroup"] {gap:2px; flex-wrap:wrap;}
.st-key-ng-tabbar [data-testid="stRadioGroup"] > div {margin:0 !important;}
.st-key-ng-tabbar [data-testid="stRadioOption"] {padding:9px 14px 10px; margin:0 0 -1px !important;
  border-bottom:2px solid transparent; cursor:pointer;}
.st-key-ng-tabbar [data-testid="stRadioOption"] > div > div:first-child {display:none;}
.st-key-ng-tabbar [data-testid="stRadioOption"] p {font-size:14px; font-weight:500; color:var(--ng-muted2);}
.st-key-ng-tabbar [data-testid="stRadioOption"]:hover p {color:var(--ng-text);}
.st-key-ng-tabbar [data-testid="stRadioOption"][data-selected="true"] {border-bottom-color:var(--ng-accent);}
.st-key-ng-tabbar [data-testid="stRadioOption"][data-selected="true"] p {color:var(--ng-text); font-weight:600;}
.st-key-ng-tabbar [data-testid="stRadioOption"]:has(input:focus-visible) {outline:2px solid var(--ng-accent);
  outline-offset:-2px; border-radius:6px 6px 0 0;}
div[class*="st-key-ng-card"] h3, div[class*="st-key-ng-card"] h4 {font-size:16px !important; font-weight:600;}
</style>
"""


def svg_img(svg: str, cls: str = "", alt: str = "") -> str:
    """An inline SVG as an <img>, since st.html's sanitizer removes <svg> elements."""
    if "xmlns=" not in svg:
        svg = svg.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1)
    w = svg.split('width="', 1)[1].split('"', 1)[0] if 'width="' in svg else ""
    h = svg.split('height="', 1)[1].split('"', 1)[0] if 'height="' in svg else ""
    size = (f' width="{w}"' if w else "") + (f' height="{h}"' if h else "")
    klass = f' class="{cls}"' if cls else ""
    return (f'<img{klass}{size} alt="{html.escape(alt)}" src="data:image/svg+xml;base64,'
            f'{base64.b64encode(svg.encode()).decode()}">')


def inject() -> None:
    st.html(CSS)


def brand(note: str = "") -> str:
    extra = f'<span class="ng-topnote">{note}</span>' if note else ""
    return (f'<div class="ng-brand">{LOGO_IMG}<span class="ng-brand-name">NurseGlance</span>'
            f'<span class="ng-proto">Research prototype · not for clinical use</span>{extra}</div>')


def footer(extra: str = "") -> None:
    st.html(f'<p class="ng-foot">{html.escape(DATA_SOURCE)}{extra}</p>')
