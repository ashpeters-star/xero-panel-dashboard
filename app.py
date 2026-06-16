import streamlit as st

st.set_page_config(
    page_title="Xero Research Panel",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
