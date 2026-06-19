import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from drive_loader import get_latest_csv, _download_file
from xrp_styles import PAGE_CSS, section_header, divider_line

# ── Colours ───────────────────────────────────────────────────────────────────
XERO_BLUE   = "#13B5EA"
XERO_GREEN  = "#00B386"
XERO_PURPLE = "#8B5CF6"
XERO_AMBER  = "#F59E0B"
XERO_RED    = "#EF4444"
XERO_SLATE  = "#64748B"
PALETTE     = [XERO_BLUE, XERO_GREEN, XERO_PURPLE, XERO_AMBER, XERO_RED, XERO_SLATE]

REGION_COLOURS = {"AU": XERO_BLUE, "US": XERO_GREEN, "UK": XERO_PURPLE}

# ── Helpers ───────────────────────────────────────────────────────────────────
def safe_int(val):
    if pd.isna(val):
        return None
    try:
        v = int(float(str(val).replace(",", "").strip()))
        return v if v >= 0 else None
    except (ValueError, TypeError):
        return None


def classify_segment(ctype, employees, partners, org_count):
    smb_types = {"SMB", "Both SMB and AB", "In-house AB"}
    ab_types  = {"AB", "Both SMB and AB"}
    if ctype in smb_types and employees is not None:
        if 2 <= employees <= 19:
            return "Small business"
        if 20 <= employees <= 49:
            return "Medium business"
    if ctype in ab_types and org_count is not None and partners is not None:
        if 400 <= org_count <= 2000 and 5 <= partners <= 10:
            return "Midsize practice"
        if 50 <= org_count <= 800 and 1 <= partners <= 5:
            return "Small practice"
    return "Not classified"


AGG_SEG_MAP = {
    "Small practice":   "AB segment",
    "Midsize practice": "AB segment",
    "Small business":   "SB segment",
    "Medium business":  "SB segment",
    "Not classified":   "Not classified",
}

COUNTRY_MAP = {
    "Australia":      "AU",
    "United States":  "US",
    "United Kingdom": "UK",
}

TARGET_SUBS = {
    "AB segment": ["Small practice", "Midsize practice"],
    "SB segment": ["Small business",  "Medium business"],
}

SEG_COLOURS = {
    "Small practice":   XERO_PURPLE,
    "Midsize practice": XERO_AMBER,
    "Small business":   XERO_BLUE,
    "Medium business":  XERO_GREEN,
}


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Loading panel data…")
def load_data(filename, data_bytes) -> pd.DataFrame:
    import io
    df = pd.read_csv(io.BytesIO(data_bytes), low_memory=False)
    df["_segment"]  = df.get("SR Customer Type", "").replace("", "Unknown").fillna("Unknown")
    df["_employees"] = df.get("SR # of Employees", pd.NA).apply(safe_int)
    df["_partners"]  = df.get("SR # of partners",  pd.NA).apply(safe_int)
    df["_org_count"] = df.get("XADE ORG Count",    pd.NA).apply(safe_int)
    df["_target_seg"] = df.apply(
        lambda r: classify_segment(r["_segment"], r["_employees"], r["_partners"], r["_org_count"]),
        axis=1,
    )
    df["_agg_seg"]  = df["_target_seg"].map(AGG_SEG_MAP).fillna("Not classified")
    _ISO_NORM = {
        "AE": "United Arab Emirates", "AU": "Australia",  "BW": "Botswana",
        "CA": "Canada",  "EG": "Egypt",   "ES": "Spain",  "FR": "France",
        "GB": "United Kingdom",  "GH": "Ghana",  "HK": "Hong Kong",
        "ID": "Indonesia", "IE": "Ireland",  "IN": "India",  "JE": "Jersey",
        "JP": "Japan",  "KE": "Kenya",  "MT": "Malta",  "MU": "Mauritius",
        "MW": "Malawi", "MY": "Malaysia", "NG": "Nigeria", "NO": "Norway",
        "NZ": "New Zealand", "PH": "Philippines", "PK": "Pakistan",
        "RW": "Rwanda",  "SG": "Singapore", "UA": "Ukraine",
        "UK": "United Kingdom",  "US": "United States",
        "ZA": "South Africa",  "ZM": "Zambia",
    }
    _xade = (df["XADE User Country"].fillna("").astype(str).str.strip().replace(_ISO_NORM)
             if "XADE User Country" in df.columns else pd.Series("", index=df.index))
    _sr   = df["SR org location"].fillna("").astype(str).str.strip()  if "SR org location"   in df.columns else pd.Series("", index=df.index)
    df["_country"] = _xade.where(_xade != "", _sr).replace("", "Unknown")
    df["_region"]  = df["_country"].replace("Unknown", pd.NA).map(COUNTRY_MAP)
    return df


# ── Load CSV ──────────────────────────────────────────────────────────────────
df_raw = None
file_ref, filename = get_latest_csv()
if file_ref is not None:
    if hasattr(file_ref, "read"):
        _bytes = file_ref.read()
    else:
        with open(file_ref, "rb") as _f:
            _bytes = _f.read()
    df_raw = load_data(filename, _bytes)

if df_raw is None:
    st.error(
        "No data found. Check that:\n"
        "- GITHUB_TOKEN and GITHUB_REPO are set in Streamlit secrets\n"
        "- The repo contains a file starting with `xero_people_`\n"
        "- The token has Contents: Read-only permission on that repo"
    )
    st.stop()

with st.sidebar:
    st.markdown("## Region Breakdown")
    st.markdown("---")
    if st.button("🔄 Refresh data", use_container_width=True):
        _download_file.clear()
        st.rerun()
    st.caption(f"Data: `{filename}`")
    st.markdown("### Filters")
    show_unclassified = st.checkbox("Include 'Not classified'", value=False)

df = df_raw.copy()

# Region filter — keep AU / US / UK (+ optionally unclassified)
REGIONS = ["AU", "US", "UK"]
df_regions = df[df["_region"].isin(REGIONS)].copy()

total_panel   = len(df)
total_regions = len(df_regions)


# ── Header ────────────────────────────────────────────────────────────────────
st.html(PAGE_CSS)
st.markdown("# AB & SB Segments — AU · US · UK")
st.caption(
    f"Full panel: **{total_panel:,}** members · "
    f"In AU/US/UK: **{total_regions:,}** ({total_regions/total_panel*100:.1f}%)"
)

st.html(divider_line())


# ── Build summary table ───────────────────────────────────────────────────────
def region_summary(agg_label):
    rows = []
    for region in REGIONS:
        mask   = (df_regions["_agg_seg"] == agg_label) & (df_regions["_region"] == region)
        subset = df_regions[mask]
        total_seg_region = mask.sum()
        for sub in TARGET_SUBS[agg_label]:
            n = (subset["_target_seg"] == sub).sum()
            rows.append({"Region": region, "Sub-segment": sub, "Count": n})
        rows.append({"Region": region, "Sub-segment": f"Total {agg_label}", "Count": total_seg_region})
    return pd.DataFrame(rows)


ab_summary = region_summary("AB segment")
sb_summary = region_summary("SB segment")


_DARK_BG   = "#1B2438"
_CARD_BG   = "#252E46"
_TRACK     = "#2D3A55"
_WHITE     = "#FFFFFF"
_MUTED     = "#8A93A8"

def progress_bar(value, maximum, color, label=""):
    pct = value / maximum * 100 if maximum else 0
    fig = go.Figure()
    fig.add_trace(go.Bar(x=[100], y=[""], orientation="h",
                         marker_color=_TRACK, width=0.4, showlegend=False))
    fig.add_trace(go.Bar(x=[pct], y=[""], orientation="h",
                         marker_color=color, width=0.4, showlegend=False,
                         text=f"  {value:,}  ({pct:.1f}%)",
                         textposition="outside",
                         textfont=dict(size=12, color=_WHITE)))
    fig.update_layout(
        barmode="overlay",
        xaxis=dict(range=[0, 130], showgrid=False, zeroline=False,
                   tickvals=[0, 25, 50, 75, 100],
                   ticktext=["0%", "25%", "50%", "75%", "100%"],
                   tickfont=dict(color=_MUTED)),
        yaxis=dict(showticklabels=False),
        height=65, margin=dict(t=20, b=0, l=0, r=100),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=_WHITE),
        title=dict(text=label, font=dict(size=13, color=_WHITE), x=0),
    )
    return fig


# ── Per-region totals for scaling bar charts ──────────────────────────────────
def total_in_seg(agg_label, region):
    return ((df_regions["_agg_seg"] == agg_label) & (df_regions["_region"] == region)).sum()


ab_max = max(total_in_seg("AB segment", r) for r in REGIONS) or 1
sb_max = max(total_in_seg("SB segment", r) for r in REGIONS) or 1


# ── AB SEGMENT ────────────────────────────────────────────────────────────────
st.html(section_header("AB segment  ·  Small practice + Midsize practice"))

ab_cols = st.columns(3)
for col, region in zip(ab_cols, REGIONS):
    mask    = (df_regions["_agg_seg"] == "AB segment") & (df_regions["_region"] == region)
    total_r = mask.sum()
    sp      = ((df_regions["_target_seg"] == "Small practice")   & (df_regions["_region"] == region)).sum()
    mp      = ((df_regions["_target_seg"] == "Midsize practice") & (df_regions["_region"] == region)).sum()
    pct_of_ab = total_r / ab_summary[ab_summary["Sub-segment"] == "Total AB segment"]["Count"].sum() * 100 \
        if ab_summary[ab_summary["Sub-segment"] == "Total AB segment"]["Count"].sum() > 0 else 0

    with col:
        st.html(section_header(region, REGION_COLOURS[region]))
        m1, m2 = st.columns(2)
        m1.metric("Small practice",   f"{sp:,}")
        m2.metric("Midsize practice", f"{mp:,}")
        st.plotly_chart(
            progress_bar(total_r, ab_max, REGION_COLOURS[region],
                         label=f"Total AB — {region}"),
            use_container_width=True, key=f"ab_{region}",
        )

st.html(divider_line())

# Grouped bar: AB sub-segments by region
ab_plot = ab_summary[~ab_summary["Sub-segment"].str.startswith("Total")]
fig_ab = px.bar(
    ab_plot, x="Region", y="Count", color="Sub-segment", barmode="group",
    color_discrete_map=SEG_COLOURS,
    text="Count",
    category_orders={"Region": REGIONS},
)
fig_ab.update_traces(textposition="outside", cliponaxis=False,
                     textfont=dict(color=_WHITE))
fig_ab.update_layout(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color=_WHITE),
    height=320, margin=dict(t=10, b=0, l=0, r=0),
    xaxis_title=None, yaxis_title=None,
    xaxis=dict(tickfont=dict(color=_WHITE)),
    yaxis=dict(showgrid=False, tickfont=dict(color=_WHITE)),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                font=dict(color=_WHITE)),
)
st.plotly_chart(fig_ab, use_container_width=True)

st.html(divider_line())


# ── SB SEGMENT ────────────────────────────────────────────────────────────────
st.html(section_header("SB segment  ·  Small business + Medium business"))

sb_cols = st.columns(3)
for col, region in zip(sb_cols, REGIONS):
    mask    = (df_regions["_agg_seg"] == "SB segment") & (df_regions["_region"] == region)
    total_r = mask.sum()
    smb     = ((df_regions["_target_seg"] == "Small business")  & (df_regions["_region"] == region)).sum()
    med     = ((df_regions["_target_seg"] == "Medium business") & (df_regions["_region"] == region)).sum()

    with col:
        st.html(section_header(region, REGION_COLOURS[region]))
        m1, m2 = st.columns(2)
        m1.metric("Small business",  f"{smb:,}")
        m2.metric("Medium business", f"{med:,}")
        st.plotly_chart(
            progress_bar(total_r, sb_max, REGION_COLOURS[region],
                         label=f"Total SB — {region}"),
            use_container_width=True, key=f"sb_{region}",
        )

st.html(divider_line())

# Grouped bar: SB sub-segments by region
sb_plot = sb_summary[~sb_summary["Sub-segment"].str.startswith("Total")]
fig_sb = px.bar(
    sb_plot, x="Region", y="Count", color="Sub-segment", barmode="group",
    color_discrete_map=SEG_COLOURS,
    text="Count",
    category_orders={"Region": REGIONS},
)
fig_sb.update_traces(textposition="outside", cliponaxis=False,
                     textfont=dict(color=_WHITE))
fig_sb.update_layout(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color=_WHITE),
    height=320, margin=dict(t=10, b=0, l=0, r=0),
    xaxis_title=None, yaxis_title=None,
    xaxis=dict(tickfont=dict(color=_WHITE)),
    yaxis=dict(showgrid=False, tickfont=dict(color=_WHITE)),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                font=dict(color=_WHITE)),
)
st.plotly_chart(fig_sb, use_container_width=True)

st.html(divider_line())


# ── COMBINED OVERVIEW ─────────────────────────────────────────────────────────
st.html(section_header("AB vs SB — combined overview"))

overview_rows = []
for region in REGIONS:
    for agg in ["AB segment", "SB segment"]:
        n = ((df_regions["_agg_seg"] == agg) & (df_regions["_region"] == region)).sum()
        overview_rows.append({"Region": region, "Segment": agg, "Count": n})

overview_df = pd.DataFrame(overview_rows)
overview_df["% of region total"] = overview_df.apply(
    lambda r: r["Count"] /
              overview_df[overview_df["Region"] == r["Region"]]["Count"].sum() * 100
    if overview_df[overview_df["Region"] == r["Region"]]["Count"].sum() > 0 else 0,
    axis=1,
).round(1)

fig_ov = px.bar(
    overview_df, x="Region", y="Count",
    color="Segment", barmode="group",
    text="Count",
    color_discrete_map={"AB segment": XERO_PURPLE, "SB segment": XERO_BLUE},
    category_orders={"Region": REGIONS},
)
fig_ov.update_traces(textposition="outside", cliponaxis=False,
                     textfont=dict(color=_WHITE))
fig_ov.update_layout(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color=_WHITE),
    height=340, margin=dict(t=10, b=0, l=0, r=0),
    xaxis_title=None, yaxis_title=None,
    xaxis=dict(tickfont=dict(color=_WHITE)),
    yaxis=dict(showgrid=False, tickfont=dict(color=_WHITE)),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                font=dict(color=_WHITE)),
)
st.plotly_chart(fig_ov, use_container_width=True)

with st.expander("Full breakdown table"):
    tbl_rows = []
    for region in REGIONS:
        for sub in ["Small practice", "Midsize practice", "Small business", "Medium business"]:
            agg = AGG_SEG_MAP.get(sub, "")
            n   = ((df_regions["_target_seg"] == sub) & (df_regions["_region"] == region)).sum()
            tbl_rows.append({"Region": region, "Segment": agg, "Sub-segment": sub, "Count": n})
    tbl = pd.DataFrame(tbl_rows)
    tbl["% of panel"] = (tbl["Count"] / total_panel * 100).round(1)
    st.dataframe(tbl, use_container_width=True, hide_index=True)
