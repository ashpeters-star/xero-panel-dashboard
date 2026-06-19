import streamlit as st

st.set_page_config(
    page_title="Xero Research Panel",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Password gate ─────────────────────────────────────────────────────────────
def check_password():
    if st.session_state.get("authenticated"):
        return True

    st.markdown("""
    <style>
      .block-container { max-width: 420px; padding-top: 8rem; }
      .stApp { background-color: #1B2438; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="text-align:center; margin-bottom:32px;">
      <div style="font-size:32px; font-weight:800; color:#FFFFFF;">
        Xero Research Panel
      </div>
      <div style="font-size:14px; color:#8A93A8; margin-top:6px;">
        Enter your password to continue
      </div>
    </div>
    """, unsafe_allow_html=True)

    password = st.text_input("Password", type="password", label_visibility="collapsed",
                             placeholder="Enter password")

    if st.button("Continue", use_container_width=True, type="primary"):
        if password == st.secrets.get("APP_PASSWORD", ""):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password. Please try again.")

    return False


if not check_password():
    st.stop()

# ── App pages ─────────────────────────────────────────────────────────────────
pg = st.navigation([
    st.Page("pages/overview.py",
            title="Panel diversity, growth & engagement",
            icon="📊"),
    st.Page("pages/2_Region_Breakdown.py",
            title="Region Breakdown",
            icon="🌏"),
    st.Page("pages/3_Stakeholder_View.py",
            title="Panel diversity by 3x3",
            icon="📋"),
])
pg.run()
