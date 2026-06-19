import re
from datetime import date, timedelta
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from drive_loader import get_latest_csv, _download_file
from xrp_styles import PAGE_CSS, section_header, divider_line

# ── Brand colours ─────────────────────────────────────────────────────────────
XERO_BLUE   = "#13B5EA"
XERO_GREEN  = "#00B386"
XERO_PURPLE = "#8B5CF6"
XERO_AMBER  = "#F59E0B"
XERO_RED    = "#EF4444"
XERO_SLATE  = "#64748B"
PALETTE = [XERO_BLUE, XERO_GREEN, XERO_PURPLE, XERO_AMBER, XERO_RED, XERO_SLATE,
           "#06B6D4", "#10B981", "#F97316", "#EC4899"]

GROWTH_TARGET = 7500
FY27_END = date(2027, 3, 31)

# ── Helpers ───────────────────────────────────────────────────────────────────
def safe_int(val) -> Optional[int]:
    if pd.isna(val):
        return None
    try:
        v = int(float(str(val).replace(",", "").strip()))
        return v if v >= 0 else None
    except (ValueError, TypeError):
        return None


def parse_multiselect(val) -> list:
    if pd.isna(val) or str(val).strip() == "":
        return []
    s = str(val).strip().strip('"')
    return [item.strip().strip('"') for item in re.split(r'",\s*"', s) if item.strip().strip('"')]


def strip_ref_quotes(val) -> str:
    if pd.isna(val):
        return ""
    return str(val).strip().strip('"')


def pct(n: int, total: int) -> str:
    return f"{n / total * 100:.1f}%" if total else "—"


ENGAGE_GOAL = 90.0

# ── Channel mapping ──────────────────────────────────────────────────────────
CHANNEL_MAP = {
    "NPSsurvey":            "Email / CRM",
    "EDM":                  "Email / CRM",
    "XeroSurvey":           "Email / CRM",
    "SBnewsletter":         "Email / CRM",
    "PartnerNewsletter":    "Email / CRM",
    "O-EDM20dsurveyGL":     "Email / CRM",
    "IPC":                  "In-Product",
    "sIPC":                 "In-Product",
    "nIPC":                 "In-Product",
    "Xero-Central":         "In-Product",
    "LinkedIn":             "Social / Paid",
    "OSCLinkedin1":         "Social / Paid",
    "PIGSocialAU7":         "Social / Paid",
    "PIGSocialUK3":         "Social / Paid",
    "OLISocialGL10":        "Social / Paid",
    "PLISocialAU8":         "Social / Paid",
    "PLISocialUK4":         "Social / Paid",
    "PIGSocialUS5":         "Social / Paid",
    "websignup":            "Organic / Signup",
    "direct":               "Organic / Signup",
    "SIGNUP_FORM_SIGNUP":   "Organic / Signup",
    "LANDING_PAGE_SIGNUP":  "Organic / Signup",
}
SOCIAL_RE = re.compile(r"social|linkedin|facebook|instagram|twitter", re.I)
EDM_RE    = re.compile(r"^edm$|newsletter|O-EDM", re.I)


def map_channel(ref_codes, legacy, source) -> str:
    for raw in [ref_codes, legacy]:
        v = strip_ref_quotes(raw) if raw is not None else ""
        if not v or v.lower() in ("", "nan"):
            continue
        if v in CHANNEL_MAP:
            return CHANNEL_MAP[v]
        if SOCIAL_RE.search(v):
            return "Social / Paid"
        if EDM_RE.search(v):
            return "Email / CRM"
    src = "" if pd.isna(source) else str(source).strip()
    if src in CHANNEL_MAP:
        return CHANNEL_MAP[src]
    if src == "LIST_UPLOAD":
        return "List Upload / Other"
    return "Unknown"


# ── Target segment classification ────────────────────────────────────────────
def classify_segment(ctype, employees, partners, org_count) -> str:
    smb_types = {"SMB", "Both SMB and AB", "In-house AB"}
    ab_types   = {"AB", "Both SMB and AB"}

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


# ── Revenue band derivation ──────────────────────────────────────────────────
def revenue_label(band, exact) -> str:
    b = "" if pd.isna(band) else str(band).strip()
    if b and b not in ("Prefer not to say",):
        return b
    e = "" if pd.isna(exact) else str(exact).strip()
    if e and e not in ("", "0"):
        return f"Exact: {e}"
    return "Not provided"


# ── Product columns ───────────────────────────────────────────────────────────
PRODUCTS = {
    "XADE ORG uses Stripe":        "Stripe",
    "XADE ORG uses Projects":      "Projects",
    "XADE ORG uses Payroll":       "Payroll",
    "XADE ORG uses Paypal":        "PayPal",
    "XADE ORG uses Hubdoc":        "Hubdoc",
    "XADE ORG uses Expenses":      "Expenses",
    "XADE ORG uses Cardless":      "Cardless",
    "XADE ORG uses Analytics Plus":"Analytics Plus",
    "XADE ORG uses Accounting":    "Accounting",
    "XADE Xero Mobile App User":   "Xero Mobile App",
}


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Loading panel data…")
def load_data(filename, data_bytes) -> pd.DataFrame:
    import io
    df = pd.read_csv(io.BytesIO(data_bytes), low_memory=False)

    for col in ["Import Date", "Qualtrics Contact Signup date",
                "XADE Xero User Signup Date", "XADE Xero ORG Signup date",
                "Last Interview Date", "Last Contact Date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True).dt.tz_localize(None)

    df["_signup_date"] = df.get("Qualtrics Contact Signup date", pd.NaT)
    if "Import Date" in df.columns:
        df.loc[df["_signup_date"].isna(), "_signup_date"] = df.loc[df["_signup_date"].isna(), "Import Date"]

    df["_channel"] = df.apply(
        lambda r: map_channel(
            r.get("All Referral Codes"),
            r.get("Legacy referral source"),
            r.get("Import Source"),
        ),
        axis=1,
    )

    df["_segment"] = df.get("SR Customer Type", "").replace("", "Unknown").fillna("Unknown")
    _xade = df["XADE User Country"].fillna("").astype(str).str.strip() if "XADE User Country" in df.columns else pd.Series("", index=df.index)
    _sr   = df["SR org location"].fillna("").astype(str).str.strip()  if "SR org location"   in df.columns else pd.Series("", index=df.index)
    df["_country"] = _xade.where(_xade != "", _sr).replace("", "Unknown")

    df["_employees"]  = df.get("SR # of Employees", pd.NA).apply(safe_int)
    df["_partners"]   = df.get("SR # of partners",  pd.NA).apply(safe_int)
    df["_org_count"]  = df.get("XADE ORG Count",    pd.NA).apply(safe_int)

    df["_target_seg"] = df.apply(
        lambda r: classify_segment(
            r["_segment"], r["_employees"], r["_partners"], r["_org_count"]
        ),
        axis=1,
    )

    df["_revenue"] = df.apply(
        lambda r: revenue_label(
            r.get("SR Annual revenue bands (estimate)"),
            r.get("SR  Annual revenue (estimate) "),
        ),
        axis=1,
    )

    return df


# ── Sidebar ───────────────────────────────────────────────────────────────────
df_raw: Optional[pd.DataFrame] = None
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
    st.markdown("## Xero Research Panel")
    st.markdown("---")
    st.caption(f"Data: `{filename}`")
    if st.button("🔄 Refresh data", use_container_width=True):
        _download_file.clear()
        st.rerun()

    st.markdown("### Date range")
    all_dates = df_raw["_signup_date"].dropna()
    if all_dates.empty:
        st.warning("No signup dates found in this CSV — date filter disabled.")
        start_date = date(2020, 1, 1)
        end_date   = date.today()
        d_min, d_max = start_date, end_date
    else:
        d_min = all_dates.min().date()
        d_max = all_dates.max().date()
        start_date = st.date_input("From", value=d_min, min_value=d_min, max_value=d_max)
        end_date   = st.date_input("To",   value=d_max, min_value=d_min, max_value=d_max)

    st.markdown("### Target segments")
    st.caption("Small business · Medium business · Small practice · Midsize practice")
    st.caption("Goal: **65%** of panel in any target segment")

    st.markdown("### Geography")
    all_countries = sorted(df_raw["_country"].unique())
    selected_countries = st.multiselect("Filter by country (blank = all)", options=all_countries, default=[])

    manual_completions = int(st.secrets.get("ENGAGEMENT_COMPLETIONS", 1578))

    st.markdown("### Granularity")
    freq_label = st.radio("Sign-up chart", ["Weekly", "Monthly"], index=1, horizontal=True)
    freq_map = {"Weekly": "W", "Monthly": "ME"}


# ── Apply filters ─────────────────────────────────────────────────────────────
df = df_raw.copy()
if df["_signup_date"].notna().any():
    df = df[
        (df["_signup_date"].dt.date >= start_date) &
        (df["_signup_date"].dt.date <= end_date)
    ]
if selected_countries:
    df = df[df["_country"].isin(selected_countries)]

TARGET_SEG_GOAL = 65.0
df["_is_target"] = df["_target_seg"] != "Not classified"

AGG_SEG_MAP = {
    "Small practice":   "AB segment",
    "Midsize practice": "AB segment",
    "Small business":   "SB segment",
    "Medium business":  "SB segment",
    "Not classified":   "Not classified",
}
df["_agg_seg"] = df["_target_seg"].map(AGG_SEG_MAP).fillna("Not classified")

total       = len(df)
active      = (df["Contact Status"] == "FREE_TO_CONTACT").sum()
cooldown    = (df["Contact Status"] == "IN_COOLDOWN").sum()
dnc         = df["Contact Status"].isin(["DO_NOT_CONTACT", "OPTED_OUT"]).sum()
target_n    = df["_is_target"].sum()
target_pc   = target_n / total * 100 if total else 0
target_gap  = target_pc - TARGET_SEG_GOAL


st.html(PAGE_CSS)

# ═══════════════════════════════════════════════════════════════════════════════
# HEADER + KPIs
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("# Xero Research Panel")
st.caption(
    f"Showing **{total:,}** members · signup range "
    f"**{start_date.strftime('%d %b %Y')}** – **{end_date.strftime('%d %b %Y')}** · "
    f"full panel: **{len(df_raw):,}** members"
)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Panel size",          f"{total:,}")
c2.metric("Active (free)",       f"{active:,}",  delta=pct(active, total))
c3.metric("In cooldown",         f"{cooldown:,}", delta=pct(cooldown, total), delta_color="off")
c4.metric("In target segments",  f"{target_pc:.1f}%",
          delta=f"{target_gap:+.1f}pp vs 65% goal",
          delta_color="normal" if target_gap >= 0 else "inverse",
          help="% of panel in Small business, Medium business, Small practice, or Midsize practice")
c5.metric("Opted out / DNC",     f"{dnc:,}",     delta=pct(dnc, total), delta_color="inverse")

st.html(divider_line())


# ═══════════════════════════════════════════════════════════════════════════════
# GROWTH TARGET
# ═══════════════════════════════════════════════════════════════════════════════
st.html(section_header("Panel growth vs FY27 target"))

growth_df = (
    df_raw.dropna(subset=["_signup_date"])
    .set_index("_signup_date")
    .resample("ME")
    .size()
    .reset_index(name="New")
    .rename(columns={"_signup_date": "Date"})
)
growth_df["Cumulative"] = growth_df["New"].cumsum()

days_remaining = max((FY27_END - date.today()).days, 0)
current_total  = len(df_raw)
still_needed   = max(GROWTH_TARGET - current_total, 0)
size_pct       = min(current_total / GROWTH_TARGET * 100, 100)
size_color     = XERO_GREEN if current_total >= GROWTH_TARGET else XERO_BLUE

g1, g2, g3, g4, g5 = st.columns(5)
g1.metric("Current panel", f"{current_total:,}")
g2.metric("FY27 target",   f"{GROWTH_TARGET:,}")
g3.metric("Progress",      f"{size_pct:.1f}% of target",
          delta=f"{current_total:,} of {GROWTH_TARGET:,}", delta_color="off")
g4.metric("Still needed",  f"{still_needed:,}",
          delta=f"{still_needed / days_remaining:.1f}/day needed" if days_remaining else "Target reached!",
          delta_color="inverse" if still_needed > 0 else "normal")
g5.metric("Days to FY27 end", f"{days_remaining:,}",
          help="FY27 ends 31 March 2027")

fig_growth = go.Figure()
fig_growth.add_trace(go.Bar(
    x=growth_df["Date"], y=growth_df["New"],
    name="New sign-ups", marker_color=XERO_BLUE, opacity=0.5,
    yaxis="y2",
))
fig_growth.add_trace(go.Scatter(
    x=growth_df["Date"], y=growth_df["Cumulative"],
    name="Cumulative panel", mode="lines+markers",
    line=dict(color=XERO_GREEN, width=3),
    marker=dict(size=5),
))
fig_growth.add_trace(go.Scatter(
    x=[growth_df["Date"].min(), pd.Timestamp(FY27_END)],
    y=[GROWTH_TARGET, GROWTH_TARGET],
    name=f"Target {GROWTH_TARGET:,}",
    mode="lines",
    line=dict(color=XERO_RED, width=2, dash="dash"),
))
fig_growth.update_layout(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#FFFFFF"),
    height=300,
    margin=dict(t=10, b=0, l=0, r=0),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                font=dict(color="#FFFFFF")),
    xaxis=dict(title=None, tickfont=dict(color="#FFFFFF")),
    yaxis=dict(title="Cumulative members", showgrid=True, gridcolor="#2D3A55",
               tickfont=dict(color="#FFFFFF")),
    yaxis2=dict(title="New sign-ups", overlaying="y", side="right", showgrid=False,
                tickfont=dict(color="#FFFFFF")),
    bargap=0.2,
)
st.plotly_chart(fig_growth, use_container_width=True)

fig_size_prog = go.Figure()
fig_size_prog.add_trace(go.Bar(
    x=[100], y=[""], orientation="h",
    marker_color="#2D3A55", width=0.35, showlegend=False,
))
fig_size_prog.add_trace(go.Bar(
    x=[size_pct], y=[""], orientation="h",
    marker_color=size_color, width=0.35, showlegend=False,
    text=f"  {current_total:,} of {GROWTH_TARGET:,}  ({size_pct:.1f}%)",
    textposition="outside",
    textfont=dict(size=13, color="#FFFFFF"),
))
fig_size_prog.add_vline(
    x=100, line_color=XERO_RED, line_width=2, line_dash="dash",
    annotation_text="7,500 target", annotation_position="top left",
    annotation_font=dict(color=XERO_RED, size=12),
)
fig_size_prog.update_layout(
    barmode="overlay",
    font=dict(color="#FFFFFF"),
    xaxis=dict(range=[0, 130], tickvals=[0, 25, 50, 75, 100],
               ticktext=["0", "1,875", "3,750", "5,625", "7,500"],
               showgrid=False, zeroline=False, tickfont=dict(color="#FFFFFF")),
    yaxis=dict(showticklabels=False),
    height=90,
    margin=dict(t=25, b=5, l=0, r=120),
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig_size_prog, use_container_width=True)

st.html(divider_line())


# ═══════════════════════════════════════════════════════════════════════════════
# SIGN-UP TREND + SEGMENT DOUGHNUT
# ═══════════════════════════════════════════════════════════════════════════════
left, right = st.columns([3, 2])

with left:
    st.html(section_header("New sign-ups over time"))
    freq = freq_map[freq_label]
    trend = (
        df.set_index("_signup_date").resample(freq).size()
        .reset_index(name="Count")
        .rename(columns={"_signup_date": "Date"})
    )
    fig_trend = px.bar(trend, x="Date", y="Count",
                       color_discrete_sequence=[XERO_BLUE],
                       labels={"Count": "Sign-ups", "Date": ""})
    fig_trend.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                            font=dict(color="#FFFFFF"),
                            xaxis=dict(tickfont=dict(color="#FFFFFF")),
                            yaxis=dict(tickfont=dict(color="#FFFFFF"), showgrid=False),
                            margin=dict(t=4, b=0, l=0, r=0), height=290, bargap=0.2)
    st.plotly_chart(fig_trend, use_container_width=True)

with right:
    st.html(section_header("Target segment alignment"))
    TARGET_ORDER = ["Small business", "Medium business", "Small practice",
                    "Midsize practice", "Not classified"]
    donut_df = (
        df["_target_seg"].value_counts()
        .reindex(TARGET_ORDER, fill_value=0)
        .rename_axis("Segment").reset_index(name="Count")
    )
    donut_colors = [XERO_BLUE, XERO_GREEN, XERO_PURPLE, XERO_AMBER, XERO_SLATE]
    fig_donut = px.pie(donut_df, values="Count", names="Segment",
                       hole=0.52,
                       color="Segment",
                       color_discrete_map=dict(zip(TARGET_ORDER, donut_colors)))
    fig_donut.update_traces(textposition="inside", textinfo="percent+label", textfont_size=11)

    goal_symbol = "✓" if target_gap >= 0 else "↑"
    centre_color = XERO_GREEN if target_gap >= 0 else XERO_RED
    fig_donut.add_annotation(
        text=f"<b>{target_pc:.0f}%</b><br><span style='color:{centre_color}'>{goal_symbol} goal 65%</span>",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=14, color="#FFFFFF"), xanchor="center",
    )
    fig_donut.update_layout(showlegend=False, font=dict(color="#FFFFFF"),
                            margin=dict(t=4, b=0, l=0, r=0), height=290)
    st.plotly_chart(fig_donut, use_container_width=True)

st.html(divider_line())


# ═══════════════════════════════════════════════════════════════════════════════
# TARGET SEGMENTS
# ═══════════════════════════════════════════════════════════════════════════════
st.html(section_header("Target segment tracking"))
st.caption(
    "Small business: SMB/Both/In-house AB, 2–19 employees · "
    "Medium business: SMB/Both/In-house AB, 20–49 employees · "
    "Small practice: AB/Both, 50–800 org clients, 1–5 partners · "
    "Midsize practice: AB/Both, 400–2,000 org clients, 5–10 partners"
)

TARGET_ORDER = ["Small business", "Medium business", "Small practice", "Midsize practice", "Not classified"]
seg_counts = df["_target_seg"].value_counts().reindex(TARGET_ORDER, fill_value=0).reset_index()
seg_counts.columns = ["Segment", "Count"]
seg_counts["% of panel"] = (seg_counts["Count"] / total * 100).round(1)

t1, t2, t3, t4 = st.columns(4)
for col, label in zip([t1, t2, t3, t4],
                      ["Small business", "Medium business", "Small practice", "Midsize practice"]):
    n = int(seg_counts.loc[seg_counts["Segment"] == label, "Count"].iloc[0])
    col.metric(label, f"{n:,}", delta=pct(n, total), delta_color="off")

st.markdown("##### Growth to 65% target")

needed_now       = max(round(total * 0.65) - target_n, 0)
needed_at_7500   = max(round(GROWTH_TARGET * 0.65) - target_n, 0)

g1, g2, g3 = st.columns(3)
g1.metric(
    "Currently in target segments",
    f"{target_n:,}  ({target_pc:.1f}%)",
    delta=f"{target_gap:+.1f}pp vs 65% goal",
    delta_color="normal" if target_gap >= 0 else "inverse",
)
g2.metric(
    "Still needed — current panel size",
    f"{needed_now:,}" if needed_now > 0 else "Goal reached ✓",
    help=f"Target-segment members needed to reach 65% of the current {total:,}-member panel",
    delta_color="off",
)
g3.metric(
    "Still needed — at 7,500 panel target",
    f"{needed_at_7500:,}" if needed_at_7500 > 0 else "Goal reached ✓",
    help="Target-segment members needed to reach 65% of a 7,500-member panel",
    delta_color="off",
)

fig_prog = go.Figure()
fig_prog.add_trace(go.Bar(
    x=[100], y=[""], orientation="h",
    marker_color="#2D3A55", width=0.35, showlegend=False,
))
bar_color = XERO_GREEN if target_gap >= 0 else XERO_BLUE
fig_prog.add_trace(go.Bar(
    x=[target_pc], y=[""], orientation="h",
    marker_color=bar_color, width=0.35, showlegend=False,
    text=f"  {target_pc:.1f}%", textposition="outside",
    textfont=dict(size=13, color="#FFFFFF"),
))
fig_prog.add_vline(
    x=65, line_color=XERO_RED, line_width=2, line_dash="dash",
    annotation_text="65% goal", annotation_position="top left",
    annotation_font=dict(color=XERO_RED, size=12),
)
fig_prog.update_layout(
    barmode="overlay",
    font=dict(color="#FFFFFF"),
    xaxis=dict(range=[0, 105], ticksuffix="%", showgrid=False, zeroline=False,
               tickfont=dict(color="#FFFFFF")),
    yaxis=dict(showticklabels=False),
    height=90,
    margin=dict(t=25, b=5, l=0, r=60),
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig_prog, use_container_width=True)

fig_tseg = px.bar(
    seg_counts[seg_counts["Segment"] != "Not classified"],
    x="Segment", y="Count",
    text="Count",
    color="Segment",
    color_discrete_sequence=PALETTE,
)
fig_tseg.update_traces(textposition="outside", cliponaxis=False)
fig_tseg.update_layout(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
    font=dict(color="#FFFFFF"),
    xaxis=dict(title=None, tickfont=dict(color="#FFFFFF")),
    yaxis=dict(title=None, showgrid=False, tickfont=dict(color="#FFFFFF")),
    margin=dict(t=10, b=0, l=0, r=0), height=260,
)
st.plotly_chart(fig_tseg, use_container_width=True)

with st.expander("Target segment table"):
    st.dataframe(seg_counts, use_container_width=True, hide_index=True)

st.html(divider_line())


# ═══════════════════════════════════════════════════════════════════════════════
# ENGAGEMENT RATE
# ═══════════════════════════════════════════════════════════════════════════════
st.html(section_header("Engagement rate"))
st.caption("Engagement rate = (Interviews + Surveys completed) ÷ Study invitations sent × 100")

ENG_COLS = {
    "invites_all":   "Study invites",
    "invites_yr":    "Study invites last year",
    "invites_30":    "Study invites last 30 days",
    "interviews_all":"Interviews",
    "interviews_yr": "Interviews last year",
    "interviews_30": "Interviews last 30 days",
    "surveys_all":   "Surveys",
    "surveys_yr":    "Surveys last year",
    "surveys_30":    "Surveys last 30 days",
}
eng = {}
for key, col in ENG_COLS.items():
    series = df[col] if col in df.columns else pd.Series(0, index=df.index)
    eng[key] = pd.to_numeric(series, errors="coerce").fillna(0)

def eng_rate(completions, invites):
    total_inv = invites.sum()
    return completions.sum() / total_inv * 100 if total_inv > 0 else 0.0

invites_all_total = eng["invites_all"].sum()
rate_all = manual_completions / invites_all_total * 100 if invites_all_total > 0 else 0.0

time_period_available = eng["invites_yr"].sum() > 0

active_members = ((eng["interviews_all"] + eng["surveys_all"]) > 0).sum()
active_rate    = active_members / total * 100 if total else 0.0

headline_rate = rate_all
engage_gap    = headline_rate - ENGAGE_GOAL
engage_color  = XERO_GREEN if engage_gap >= 0 else XERO_RED

e1, e2, e3, e4 = st.columns(4)
e1.metric("All-time engagement",  f"{rate_all:.1f}%",
          delta=f"{engage_gap:+.1f}pp vs 90% goal",
          delta_color="normal" if engage_gap >= 0 else "inverse",
          help=f"{manual_completions:,} completions ÷ {invites_all_total:,} invitations")
e2.metric("Total invitations",    f"{invites_all_total:,}",
          help="Study invites sent (all time, from Rally CSV)")
e3.metric("Total completions",    f"{manual_completions:,}",
          help="Surveys + screeners + unmoderated tests + interviews (from reports)")
e4.metric("Active members",       f"{active_members:,}  ({active_rate:.1f}%)",
          help="Members with at least one interview or survey recorded in Rally")

if not time_period_available:
    st.info(
        "⚠️ Last 30-day and last 12-month invitation counts are not populated in this "
        "Rally export — time-period engagement rates cannot be calculated. "
        "Check the Rally export settings to include these columns."
    )

bar_fill     = min(headline_rate, 110)
goal_line_x  = ENGAGE_GOAL

fig_eng_prog = go.Figure()
fig_eng_prog.add_trace(go.Bar(
    x=[110], y=[""], orientation="h",
    marker_color="#2D3A55", width=0.35, showlegend=False,
))
fig_eng_prog.add_trace(go.Bar(
    x=[bar_fill], y=[""], orientation="h",
    marker_color=engage_color, width=0.35, showlegend=False,
    text=f"  {headline_rate:.1f}%  ({manual_completions:,} completions, all time)",
    textposition="outside",
    textfont=dict(size=13, color="#FFFFFF"),
))
fig_eng_prog.add_vline(
    x=goal_line_x, line_color=XERO_RED, line_width=2, line_dash="dash",
    annotation_text="90% goal", annotation_position="top left",
    annotation_font=dict(color=XERO_RED, size=12),
)
fig_eng_prog.update_layout(
    barmode="overlay",
    font=dict(color="#FFFFFF"),
    xaxis=dict(range=[0, 125], ticksuffix="%", showgrid=False, zeroline=False,
               tickfont=dict(color="#FFFFFF")),
    yaxis=dict(showticklabels=False),
    height=90,
    margin=dict(t=25, b=5, l=0, r=140),
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
)
st.plotly_chart(fig_eng_prog, use_container_width=True)

st.markdown("##### Participation by segment")
st.markdown("""
<div style="background:#3D2B00; border-left:4px solid #F59E0B; border-radius:6px;
            padding:10px 16px; margin-bottom:12px; font-size:13px; color:#FCD34D;">
  ⚠️ <strong>Work in progress</strong> — segment-level engagement figures are estimated
  and may not be accurate. Treat with caution.
</div>
""", unsafe_allow_html=True)

df["_completions_yr"] = eng["interviews_yr"] + eng["surveys_yr"]
df["_invites_yr"]     = eng["invites_yr"]

def agg_seg_stats(label):
    mask        = df["_agg_seg"] == label
    members     = mask.sum()
    invites     = df.loc[mask, "_invites_yr"].sum()
    seg_invites = eng["invites_all"][mask].sum()
    seg_completions = (
        round(manual_completions * seg_invites / invites_all_total)
        if invites_all_total > 0 else 0
    )
    rate        = seg_completions / seg_invites * 100 if seg_invites > 0 else 0.0
    active_m    = ((eng["interviews_all"] + eng["surveys_all"])[mask] > 0).sum()
    return members, seg_invites, seg_completions, rate, active_m

ab_members, ab_invites, ab_completions, ab_rate, ab_active = agg_seg_stats("AB segment")
sb_members, sb_invites, sb_completions, sb_rate, sb_active = agg_seg_stats("SB segment")

ab_col, sb_col = st.columns(2)

for col, label, members, invites, completions, rate, active_m, color in [
    (ab_col, "AB segment  (Small + Midsize practice)", ab_members, ab_invites,
     ab_completions, ab_rate, ab_active, XERO_PURPLE),
    (sb_col, "SB segment  (Small + Medium business)",  sb_members, sb_invites,
     sb_completions, sb_rate, sb_active, XERO_BLUE),
]:
    gap = rate - ENGAGE_GOAL
    bar_color = XERO_GREEN if gap >= 0 else color
    with col:
        st.markdown(f"**{label}**")
        m1, m2, m3 = st.columns(3)
        m1.metric("Members",      f"{members:,}")
        m2.metric("Active",       f"{active_m:,}",
                  delta=f"{active_m/members*100:.1f}%" if members else "—",
                  delta_color="off")
        m3.metric("Engagement",   f"{rate:.1f}%",
                  delta=f"{gap:+.1f}pp vs 90%",
                  delta_color="normal" if gap >= 0 else "inverse")

        fig_ab = go.Figure()
        fig_ab.add_trace(go.Bar(x=[110], y=[""], orientation="h",
                                marker_color="#2D3A55", width=0.3, showlegend=False))
        fig_ab.add_trace(go.Bar(x=[min(rate, 110)], y=[""], orientation="h",
                                marker_color=bar_color, width=0.3, showlegend=False,
                                text=f"  {rate:.1f}%", textposition="outside",
                                textfont=dict(size=12, color="#FFFFFF")))
        fig_ab.add_vline(x=ENGAGE_GOAL, line_color=XERO_RED,
                         line_width=2, line_dash="dash",
                         annotation_text="90%",
                         annotation_position="top left",
                         annotation_font=dict(color=XERO_RED, size=11))
        fig_ab.update_layout(
            barmode="overlay",
            font=dict(color="#FFFFFF"),
            xaxis=dict(range=[0, 125], ticksuffix="%", showgrid=False, zeroline=False,
                       tickfont=dict(color="#FFFFFF")),
            yaxis=dict(showticklabels=False),
            height=75, margin=dict(t=20, b=0, l=0, r=60),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_ab, use_container_width=True)

with st.expander("Engagement by target segment"):
    seg_eng = (
        df.groupby("_target_seg")
        .agg(Invites=("_invites_yr", "sum"), Completions=("_completions_yr", "sum"))
        .reset_index()
        .rename(columns={"_target_seg": "Segment"})
    )
    seg_eng["Engagement rate (%)"] = (
        seg_eng.apply(lambda r: r["Completions"] / r["Invites"] * 100
                      if r["Invites"] > 0 else 0, axis=1)
    ).round(1)
    seg_eng["vs goal"] = (seg_eng["Engagement rate (%)"] - ENGAGE_GOAL).round(1)
    seg_eng = seg_eng.sort_values("Engagement rate (%)", ascending=True)

    fig_seg_eng = px.bar(
        seg_eng, y="Segment", x="Engagement rate (%)",
        orientation="h", text="Engagement rate (%)",
        color="Engagement rate (%)",
        color_continuous_scale=[[0, XERO_RED], [ENGAGE_GOAL/100, XERO_AMBER],
                                 [1.0, XERO_GREEN]],
        range_color=[0, 100],
    )
    fig_seg_eng.add_vline(
        x=ENGAGE_GOAL, line_color=XERO_RED, line_width=2, line_dash="dash",
        annotation_text="90% goal", annotation_position="top right",
        annotation_font=dict(color=XERO_RED, size=11),
    )
    fig_seg_eng.update_traces(texttemplate="%{text:.1f}%", textposition="outside",
                               cliponaxis=False)
    fig_seg_eng.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
        font=dict(color="#FFFFFF"),
        xaxis=dict(range=[0, 115], ticksuffix="%", showgrid=False,
                   tickfont=dict(color="#FFFFFF")),
        yaxis=dict(title=None, tickfont=dict(color="#FFFFFF")),
        coloraxis_showscale=False,
        margin=dict(t=20, b=0, l=0, r=60), height=280,
    )
    st.plotly_chart(fig_seg_eng, use_container_width=True)
    st.dataframe(seg_eng[["Segment","Invites","Completions","Engagement rate (%)","vs goal"]],
                 use_container_width=True, hide_index=True)

st.html(divider_line())


# ═══════════════════════════════════════════════════════════════════════════════
# CHANNEL PERFORMANCE + GEOGRAPHY
# ═══════════════════════════════════════════════════════════════════════════════
left2, right2 = st.columns(2)

with left2:
    st.html(section_header("Growth channel performance"))
    ch_df = (df["_channel"].value_counts()
             .rename_axis("Channel").reset_index(name="Count")
             .sort_values("Count"))
    ch_df["label"] = ch_df.apply(
        lambda r: f"{r['Count']:,}  ({r['Count']/ch_df['Count'].sum()*100:.1f}%)", axis=1)
    fig_ch = px.bar(ch_df, y="Channel", x="Count", orientation="h",
                    text="label", color="Channel", color_discrete_sequence=PALETTE)
    fig_ch.update_traces(textposition="outside", cliponaxis=False)
    fig_ch.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                         font=dict(color="#FFFFFF"),
                         xaxis=dict(title=None, showgrid=False, tickfont=dict(color="#FFFFFF")),
                         yaxis=dict(title=None, tickfont=dict(color="#FFFFFF")),
                         margin=dict(t=4, b=0, l=0, r=90), height=320)
    st.plotly_chart(fig_ch, use_container_width=True)

with right2:
    st.html(section_header("Geography (top 10)"))
    geo_df = (df["_country"].value_counts().head(10)
              .rename_axis("Country").reset_index(name="Count").sort_values("Count"))
    fig_geo = px.bar(geo_df, y="Country", x="Count", orientation="h",
                     text="Count", color_discrete_sequence=[XERO_GREEN])
    fig_geo.update_traces(textposition="outside", cliponaxis=False)
    fig_geo.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                          font=dict(color="#FFFFFF"),
                          xaxis=dict(title=None, showgrid=False, tickfont=dict(color="#FFFFFF")),
                          yaxis=dict(title=None, tickfont=dict(color="#FFFFFF")),
                          margin=dict(t=4, b=0, l=0, r=30), height=320)
    st.plotly_chart(fig_geo, use_container_width=True)

st.html(divider_line())


# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCT USAGE
# ═══════════════════════════════════════════════════════════════════════════════
st.html(section_header("Xero product usage"))
product_counts = {}
for col, label in PRODUCTS.items():
    if col in df.columns:
        product_counts[label] = (df[col] == "Y").sum()

prod_df = (pd.DataFrame(product_counts.items(), columns=["Product", "Count"])
           .sort_values("Count", ascending=True))
prod_df["% of panel"] = (prod_df["Count"] / total * 100).round(1)
prod_df["label"] = prod_df.apply(
    lambda r: f"{r['Count']:,}  ({r['% of panel']}%)", axis=1)

fig_prod = px.bar(prod_df, y="Product", x="Count", orientation="h",
                  text="label", color_discrete_sequence=[XERO_PURPLE])
fig_prod.update_traces(textposition="outside", cliponaxis=False)
fig_prod.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                       font=dict(color="#FFFFFF"),
                       xaxis=dict(title=None, showgrid=False, tickfont=dict(color="#FFFFFF")),
                       yaxis=dict(title=None, tickfont=dict(color="#FFFFFF")),
                       margin=dict(t=4, b=0, l=0, r=100), height=360)
st.plotly_chart(fig_prod, use_container_width=True)

st.html(divider_line())


# ═══════════════════════════════════════════════════════════════════════════════
# PANEL DIVERSITY
# ═══════════════════════════════════════════════════════════════════════════════
st.html(section_header("Panel diversity"))

d1, d2, d3 = st.columns(3)

with d1:
    BANDS = {
        "Sole trader": "XADE Employee band soletrader",
        "2–4":         "XADE Employee band 2-4",
        "5–9":         "XADE Employee band 5-9",
        "10–19":       "XADE Employee band 10-19",
        "20–49":       "XADE Employee band 20-49",
        "50+":         "XADE Employee band 50 plus",
    }
    order = ["Sole trader", "2–4", "5–9", "10–19", "20–49", "50+"]
    band_df = pd.DataFrame(
        [(b, (df.get(c, pd.Series(dtype=str)) == "Y").sum()) for b, c in BANDS.items()],
        columns=["Band", "Count"]
    )
    band_df["Band"] = pd.Categorical(band_df["Band"], categories=order, ordered=True)
    band_df = band_df.sort_values("Band")
    fig_band = px.bar(band_df, x="Band", y="Count", text="Count",
                      color_discrete_sequence=[XERO_BLUE], title="Employee band")
    fig_band.update_traces(textposition="outside", cliponaxis=False)
    fig_band.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
                           font=dict(color="#FFFFFF"),
                           xaxis=dict(title=None, tickfont=dict(color="#FFFFFF")),
                           yaxis=dict(title=None, showgrid=False, tickfont=dict(color="#FFFFFF")),
                           margin=dict(t=40, b=0, l=0, r=0), height=270,
                           title_font_size=14)
    st.plotly_chart(fig_band, use_container_width=True)

with d2:
    nps_df = (
        df["XADE NPS Segmentation"]
        .replace({"": "Unknown", "Not available": "Unknown"})
        .fillna("Unknown").value_counts()
        .rename_axis("NPS").reset_index(name="Count")
    )
    fig_nps = px.pie(nps_df, values="Count", names="NPS", hole=0.35,
                     color_discrete_sequence=PALETTE, title="NPS segmentation")
    fig_nps.update_layout(margin=dict(t=40, b=0, l=0, r=0), height=270,
                          font=dict(color="#FFFFFF"),
                          legend=dict(orientation="h", yanchor="bottom", y=-0.3,
                                      xanchor="center", x=0.5, font=dict(color="#FFFFFF")),
                          title_font_size=14)
    st.plotly_chart(fig_nps, use_container_width=True)

with d3:
    role_df = (
        df["SR Role"].replace("", "Unknown").fillna("Unknown")
        .value_counts().head(6)
        .rename_axis("Role").reset_index(name="Count").sort_values("Count")
    )
    fig_role = px.bar(role_df, y="Role", x="Count", orientation="h",
                      text="Count", color_discrete_sequence=[XERO_PURPLE], title="Participant role")
    fig_role.update_traces(textposition="outside", cliponaxis=False)
    fig_role.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
                           font=dict(color="#FFFFFF"),
                           xaxis=dict(title=None, showgrid=False, tickfont=dict(color="#FFFFFF")),
                           yaxis=dict(title=None, tickfont=dict(color="#FFFFFF")),
                           margin=dict(t=40, b=0, l=0, r=30), height=270,
                           title_font_size=14)
    st.plotly_chart(fig_role, use_container_width=True)

st.html(divider_line())


# ═══════════════════════════════════════════════════════════════════════════════
# PANELIST PROFILE
# ═══════════════════════════════════════════════════════════════════════════════
st.html(section_header("Panelist profile"))

tab_usage, tab_research, tab_software, tab_access, tab_revenue = st.tabs([
    "Xero usage", "Research participation", "Accounting software",
    "Accessibility", "Revenue"
])

def simple_bar(series: pd.Series, title: str, color: str, height: int = 320,
               parse_multi: bool = False, top_n: int = 10):
    if parse_multi:
        exploded = series.apply(parse_multiselect).explode()
        exploded = exploded[exploded.notna() & (exploded != "")]
        counts = exploded.value_counts().head(top_n)
    else:
        counts = (series.replace("", "Unknown").fillna("Unknown")
                  .value_counts().head(top_n))
    df_plot = counts.rename_axis("Value").reset_index(name="Count").sort_values("Count")
    df_plot["label"] = df_plot["Count"].apply(lambda n: f"{n:,}  ({n/total*100:.1f}%)")
    fig = px.bar(df_plot, y="Value", x="Count", orientation="h",
                 text="label", color_discrete_sequence=[color])
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
                      font=dict(color="#FFFFFF"),
                      xaxis=dict(title=None, showgrid=False, tickfont=dict(color="#FFFFFF")),
                      yaxis=dict(title=None, tickfont=dict(color="#FFFFFF")),
                      margin=dict(t=10, b=0, l=0, r=100), height=height)
    return fig

with tab_usage:
    freq_order = ["Daily", "2-3 times a week", "Once a week",
                  "Once a month", "Once every 3 months",
                  "Once every 6 months or less", "Never; I don't use Xero"]
    usage_df = (
        df["SR Frequency of use"].replace("", "Unknown").fillna("Unknown")
        .value_counts()
        .reindex(freq_order + ["Unknown"], fill_value=0)
        .reset_index()
    )
    usage_df.columns = ["Frequency", "Count"]
    usage_df = usage_df[usage_df["Count"] > 0]
    usage_df["Frequency"] = pd.Categorical(usage_df["Frequency"],
                                           categories=list(reversed(freq_order + ["Unknown"])),
                                           ordered=True)
    usage_df = usage_df.sort_values("Frequency")
    usage_df["label"] = usage_df["Count"].apply(lambda n: f"{n:,}  ({n/total*100:.1f}%)")
    fig_usage = px.bar(usage_df, y="Frequency", x="Count", orientation="h",
                       text="label", color_discrete_sequence=[XERO_BLUE])
    fig_usage.update_traces(textposition="outside", cliponaxis=False)
    fig_usage.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
                            font=dict(color="#FFFFFF"),
                            xaxis=dict(title=None, showgrid=False, tickfont=dict(color="#FFFFFF")),
                            yaxis=dict(title=None, tickfont=dict(color="#FFFFFF")),
                            margin=dict(t=10, b=0, l=0, r=100), height=320)
    st.plotly_chart(fig_usage, use_container_width=True)

with tab_research:
    st.plotly_chart(
        simple_bar(df["SR Research participation"], "Research participation",
                   XERO_GREEN, height=340, parse_multi=True),
        use_container_width=True,
    )

with tab_software:
    st.plotly_chart(
        simple_bar(df["SR Accounting Software"], "Accounting software",
                   XERO_AMBER, height=300, parse_multi=True),
        use_container_width=True,
    )

with tab_access:
    access_df = df["SR Accessibility needs"].apply(parse_multiselect).explode()
    access_df = access_df[access_df.notna() & (access_df != "") & (access_df != "None of the above")]
    acc_counts = access_df.value_counts().reset_index()
    acc_counts.columns = ["Need", "Count"]
    acc_counts = acc_counts.sort_values("Count")
    acc_counts["label"] = acc_counts["Count"].apply(lambda n: f"{n:,}  ({n/total*100:.1f}%)")

    none_n = (df["SR Accessibility needs"].apply(parse_multiselect)
              .apply(lambda x: "None of the above" in x)).sum()
    st.metric("No accessibility needs ('None of the above')",
              f"{none_n:,}", delta=pct(int(none_n), total), delta_color="off")

    if not acc_counts.empty:
        fig_acc = px.bar(acc_counts, y="Need", x="Count", orientation="h",
                         text="label", color_discrete_sequence=[XERO_SLATE])
        fig_acc.update_traces(textposition="outside", cliponaxis=False)
        fig_acc.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
                              font=dict(color="#FFFFFF"),
                              xaxis=dict(title=None, showgrid=False, tickfont=dict(color="#FFFFFF")),
                              yaxis=dict(title=None, tickfont=dict(color="#FFFFFF")),
                              margin=dict(t=10, b=0, l=0, r=100), height=300)
        st.plotly_chart(fig_acc, use_container_width=True)

with tab_revenue:
    rev_df = (
        df["_revenue"]
        .value_counts()
        .rename_axis("Band").reset_index(name="Count")
        .sort_values("Count", ascending=True)
    )
    rev_df["label"] = rev_df["Count"].apply(lambda n: f"{n:,}  ({n/total*100:.1f}%)")
    fig_rev = px.bar(rev_df.head(20), y="Band", x="Count", orientation="h",
                     text="label", color_discrete_sequence=[XERO_AMBER])
    fig_rev.update_traces(textposition="outside", cliponaxis=False)
    fig_rev.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
                          margin=dict(t=10, b=0, l=0, r=100), height=480,
                          xaxis_title=None, yaxis_title=None, xaxis=dict(showgrid=False))
    st.plotly_chart(fig_rev, use_container_width=True)

st.html(divider_line())


# ═══════════════════════════════════════════════════════════════════════════════
# EXPANDABLE DETAIL TABLES
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("Raw channel / referral source breakdown"):
    raw_ch = pd.concat([
        df["All Referral Codes"].apply(strip_ref_quotes),
        df["Legacy referral source"].fillna(""),
    ], axis=1)
    raw_ch.columns = ["All Referral Codes", "Legacy referral source"]
    raw_ch["Channel group"] = df["_channel"]
    combo = (raw_ch.apply(
        lambda r: r["All Referral Codes"] or r["Legacy referral source"] or "Unknown", axis=1)
        .value_counts().rename_axis("Source").reset_index(name="Count"))
    combo["Channel group"] = combo["Source"].apply(lambda s: map_channel(s, "", ""))
    st.dataframe(combo, use_container_width=True, hide_index=True)

with st.expander("Target segment breakdown table"):
    seg_tbl = (df["_target_seg"].value_counts()
               .rename_axis("Segment").reset_index(name="Count"))
    seg_tbl["% of panel"] = (seg_tbl["Count"] / total * 100).round(1)
    seg_tbl["In target?"] = (seg_tbl["Segment"] != "Not classified").map({True: "✓", False: ""})
    st.dataframe(seg_tbl, use_container_width=True, hide_index=True)
