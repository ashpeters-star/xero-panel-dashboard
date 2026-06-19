from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from drive_loader import get_latest_csv

# ── Palette (matched to slide) ────────────────────────────────────────────────
PAGE_BG      = "#1B2438"
CARD_BG      = "#252E46"
BLUE_CARD    = "#3B6FE0"
DARK_CARD    = "#2D3652"
PURPLE_HDR   = "#6B5AE8"
MUTED        = "#8A93A8"
DIVIDER      = "#2D3A55"
WHITE        = "#FFFFFF"

AB_COLOUR    = BLUE_CARD
SB_COLOUR    = "#2563EB"   # slightly deeper blue
BOTH_COLOUR  = PURPLE_HDR

REGION_COLOURS = {"AU": "#3B6FE0", "US": "#4B8FE8", "UK": "#6B5AE8"}

# ── Segment definitions ───────────────────────────────────────────────────────
AB_TYPES   = {"AB"}
SB_TYPES   = {"SMB", "In-house AB", "Other"}
BOTH_TYPES = {"Both SMB and AB"}
COUNTRY_MAP = {
    "Australia":      "AU",
    "United States":  "US",
    "United Kingdom": "UK",
}
REGIONS = ["AU", "US", "UK"]


# ── Helpers ───────────────────────────────────────────────────────────────────
def safe_int(val):
    if pd.isna(val):
        return None
    try:
        v = int(float(str(val).replace(",", "").strip()))
        return v if v >= 0 else None
    except (ValueError, TypeError):
        return None


# ── Data ──────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Loading…")
def load_data(filename, data_bytes) -> pd.DataFrame:
    import io
    buf = io.BytesIO(data_bytes) if isinstance(data_bytes, bytes) else data_bytes
    df = pd.read_csv(buf, low_memory=False)
    df["_ctype"]  = df.get("SR Customer Type", "").replace("", "Unknown").fillna("Unknown")
    df["_region"] = df.get("SR User Country", "").replace("", pd.NA).map(COUNTRY_MAP)
    df["_ab"]     = df["_ctype"].isin(AB_TYPES)
    df["_sb"]     = df["_ctype"].isin(SB_TYPES)
    df["_both"]   = df["_ctype"].isin(BOTH_TYPES)
    return df


_rk = st.session_state.get("refresh_key", 0)
_file_ref, _filename = get_latest_csv(refresh_key=_rk)
if _file_ref is None:
    st.error("No data found. Add GITHUB_TOKEN and GITHUB_REPO to Streamlit secrets.")
    st.stop()

if hasattr(_file_ref, "read"):
    _data_bytes = _file_ref.read()
else:
    with open(_file_ref, "rb") as _f:
        _data_bytes = _f.read()

df = load_data(_filename, _data_bytes)
df_r        = df[df["_region"].isin(REGIONS)]
total_panel = len(df)
total_ab    = int(df["_ab"].sum())
total_sb    = int(df["_sb"].sum())
total_both  = int(df["_both"].sum())


def n(flag_col, region=None):
    mask = df_r[flag_col]
    if region:
        mask = mask & (df_r["_region"] == region)
    return int(mask.sum())


def pct_str(val, denom, decimals=1):
    return f"{val / denom * 100:.{decimals}f}%" if denom else "—"


# ── Card HTML builders ────────────────────────────────────────────────────────
def blue_card(title, value, subtitle=""):
    return f"""
    <div style="background:{BLUE_CARD}; border-radius:12px; padding:22px 24px;
                min-height:110px; box-sizing:border-box;">
      <div style="font-weight:700; font-size:14px; color:{WHITE}; margin-bottom:6px;">{title}</div>
      <div style="font-weight:800; font-size:40px; color:{WHITE}; line-height:1.1;">{value}</div>
      <div style="font-size:12px; color:rgba(255,255,255,0.65); margin-top:6px;">{subtitle}</div>
    </div>"""


def dark_card(title, value, subtitle="", dim=False):
    bg    = "#232D45" if dim else DARK_CARD
    alpha = "0.4"     if dim else "1"
    val_c = f"rgba(255,255,255,{alpha})"
    return f"""
    <div style="background:{bg}; border-radius:12px; padding:22px 24px;
                min-height:110px; box-sizing:border-box;">
      <div style="font-weight:700; font-size:14px; color:{WHITE}; margin-bottom:6px;">{title}</div>
      <div style="font-weight:800; font-size:40px; color:{val_c}; line-height:1.1;">{value}</div>
      <div style="font-size:12px; color:{MUTED}; margin-top:6px;">{subtitle}</div>
    </div>"""


def section_header(label, colour=BLUE_CARD):
    return f"""
    <div style="background:{colour}; border-radius:8px; padding:8px 18px; margin-bottom:14px;
                font-weight:700; font-size:15px; color:{WHITE}; display:block; width:100%;
                box-sizing:border-box;">
      {label}
    </div>"""


def row_label(text):
    return f"""
    <div style="color:{WHITE}; font-weight:700; font-size:15px; padding-top:36px;
                line-height:1.3;">{text}</div>"""


def divider_line():
    return f'<hr style="border:none; border-top:1px solid {DIVIDER}; margin:18px 0;">'


# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
  .block-container {{
    padding-top: 1.8rem !important;
    padding-bottom: 1rem !important;
    max-width: 1200px;
  }}
  .stApp {{ background-color: {PAGE_BG}; }}
</style>
""", unsafe_allow_html=True)


with st.sidebar:
    if st.button("🔄 Refresh data", use_container_width=True):
        st.session_state["refresh_key"] = st.session_state.get("refresh_key", 0) + 1
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(f"""
<div style="margin-bottom:6px;">
  <span style="font-size:26px; font-weight:800; color:{WHITE};">
    XRP Panel Diversity by Region
  </span>
</div>
<div style="font-size:13px; color:{MUTED}; margin-bottom:24px;">
  Last Updated: {date.today().strftime('%-d %B %Y')} &nbsp;·&nbsp;
  Panel total: <strong style="color:{WHITE}">{total_panel:,}</strong>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY ROW  — total AB / SB / Both across all regions
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(section_header("Summary"), unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
c1.markdown(blue_card(
    "AB in panel",
    f"{total_ab:,}",
    f"{pct_str(total_ab, total_panel)} of total panel"
), unsafe_allow_html=True)
c2.markdown(blue_card(
    "SB in panel",
    f"{total_sb:,}",
    f"{pct_str(total_sb, total_panel)} of total panel"
), unsafe_allow_html=True)
c3.markdown(blue_card(
    "Consider themselves both SB and AB",
    f"{total_both:,}",
    f"{pct_str(total_both, total_panel)} of total panel"
), unsafe_allow_html=True)

st.markdown(divider_line(), unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SEGMENT SECTION RENDERER
# ══════════════════════════════════════════════════════════════════════════════
def render_region_section(seg_label, flag_col, hdr_colour, total_n):
    st.markdown(section_header(seg_label, hdr_colour), unsafe_allow_html=True)

    au_col, us_col, uk_col = st.columns(3)

    region_counts = {r: n(flag_col, r) for r in REGIONS}
    for col, region in zip([au_col, us_col, uk_col], REGIONS):
        val = region_counts[region]
        col.markdown(dark_card(
            region,
            f"{val:,}",
            f"{pct_str(val, total_n)} of {seg_label.split('·')[0].strip()} panel"
        ), unsafe_allow_html=True)

    # Other / unknown
    in_regions = sum(region_counts.values())
    outside    = total_n - in_regions
    st.markdown(f"""
    <div style="text-align:right; font-size:12px; color:{MUTED}; margin-top:6px; padding-right:4px;">
      {outside:,} members not in AU / US / UK ({pct_str(outside, total_n)} of {seg_label.split('·')[0].strip()})
    </div>
    """, unsafe_allow_html=True)

    st.markdown(divider_line(), unsafe_allow_html=True)


render_region_section("AB  ·  Accounting & Bookkeeping practices",
                      "_ab",   AB_COLOUR,   total_ab)
render_region_section("SB  ·  Small businesses, In-house ABs & Other",
                      "_sb",   SB_COLOUR,   total_sb)
render_region_section("Consider themselves both SB and AB",
                      "_both", BOTH_COLOUR, total_both)


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY TABLE
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(section_header("Region summary"), unsafe_allow_html=True)

SEGMENTS = [
    ("AB",   "_ab",   total_ab,   AB_COLOUR),
    ("SB",   "_sb",   total_sb,   SB_COLOUR),
    ("Consider themselves both SB and AB", "_both", total_both, BOTH_COLOUR),
]

# Build header row
hdr_cells = "".join(f"""
    <th colspan="2" style="
        background:{colour}; color:{WHITE}; font-weight:700;
        font-size:13px; padding:10px 16px; text-align:center;
        border-radius:6px 6px 0 0; border-right:2px solid {PAGE_BG};">
      {label}
    </th>""" for label, _, _, colour in SEGMENTS)

sub_cells = "".join(f"""
    <th style="background:{DARK_CARD}; color:{MUTED}; font-size:11px;
               font-weight:600; padding:6px 16px; text-align:right;
               border-right:1px solid {DIVIDER};">n</th>
    <th style="background:{DARK_CARD}; color:{MUTED}; font-size:11px;
               font-weight:600; padding:6px 16px; text-align:right;
               border-right:2px solid {PAGE_BG};">% of panel</th>
    """ for _, _, _, _ in SEGMENTS)

# Build data rows
def data_row(region, is_total=False):
    bg      = "#1F2940" if is_total else DARK_CARD
    weight  = "700"     if is_total else "400"
    label   = region
    cells = f"""
    <td style="background:{bg}; color:{WHITE}; font-weight:{weight};
               font-size:13px; padding:10px 16px;
               border-right:2px solid {PAGE_BG}; min-width:80px;">{label}</td>"""
    for _, flag, total_n, _ in SEGMENTS:
        val  = n(flag, region) if region != "Total" else total_n
        pct  = pct_str(val, total_panel)
        cells += f"""
        <td style="background:{bg}; color:{WHITE}; font-weight:{weight};
                   font-size:13px; padding:10px 16px; text-align:right;
                   border-right:1px solid {DIVIDER};">{val:,}</td>
        <td style="background:{bg}; color:{MUTED}; font-weight:{weight};
                   font-size:13px; padding:10px 16px; text-align:right;
                   border-right:2px solid {PAGE_BG};">{pct}</td>"""
    return f"<tr>{cells}</tr>"

rows_html = "".join(data_row(r) for r in REGIONS)
rows_html += data_row("Total", is_total=True)

table_html = f"""
<div style="overflow-x:auto; border-radius:10px; margin-bottom:24px;">
<table style="border-collapse:collapse; width:100%; font-family:sans-serif;">
  <thead>
    <tr>
      <th style="background:{CARD_BG}; padding:10px 16px;
                 border-right:2px solid {PAGE_BG};"></th>
      {hdr_cells}
    </tr>
    <tr>
      <th style="background:{DARK_CARD}; color:{MUTED}; font-size:11px;
                 font-weight:600; padding:6px 16px; text-align:left;
                 border-right:2px solid {PAGE_BG};">Region</th>
      {sub_cells}
    </tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>
</div>
"""
st.html(table_html)


# ══════════════════════════════════════════════════════════════════════════════
# COMBINED CHART
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(section_header("AU · US · UK — AB vs SB vs Both"), unsafe_allow_html=True)

# WCAG AA chart colours (≥3:1 contrast vs CARD_BG #252E46, visually distinct)
# AB  #5B8FF9 blue   L≈0.31  ratio≈4.0:1
# SB  #34D399 green  L≈0.51  ratio≈6.2:1  (distinct from blue for colour-blind users)
# Both #A78BFA violet L≈0.36  ratio≈4.6:1
CHART_COLOURS = {
    "_ab":    "#5B8FF9",
    "_sb":    "#34D399",
    "_both":  "#A78BFA",
}

fig = go.Figure()
for seg, flag, colour in [
    ("AB",   "_ab",   CHART_COLOURS["_ab"]),
    ("SB",   "_sb",   CHART_COLOURS["_sb"]),
    ("Consider themselves both SB and AB", "_both", CHART_COLOURS["_both"]),
]:
    counts = [n(flag, r) for r in REGIONS]
    fig.add_trace(go.Bar(
        name=seg, x=REGIONS, y=counts,
        text=[f"{v:,}" for v in counts],
        textposition="outside",
        textfont=dict(color=WHITE, size=13),
        marker_color=colour,
        width=0.22,
    ))

fig.update_layout(
    barmode="group",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor=CARD_BG,
    font=dict(color=WHITE, size=13),
    height=300,
    margin=dict(t=30, b=10, l=0, r=0),
    xaxis=dict(title=None, tickfont=dict(size=14, color=WHITE),
               showgrid=False, zeroline=False),
    yaxis=dict(showgrid=True, gridcolor=DIVIDER, showticklabels=False,
               title=None, zeroline=False),
    legend=dict(orientation="h", yanchor="bottom", y=1.02,
                xanchor="right", x=1, font=dict(size=12)),
    bargap=0.25,
)
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
