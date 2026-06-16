"""Shared dark-theme palette, CSS, and HTML helpers for XRP dashboard pages."""

PAGE_BG    = "#1B2438"
CARD_BG    = "#252E46"
BLUE_HDR   = "#3B6FE0"
DARK_CARD  = "#2D3652"
PURPLE_HDR = "#6B5AE8"
MUTED      = "#8A93A8"
DIVIDER    = "#2D3A55"
WHITE      = "#FFFFFF"

PAGE_CSS = f"""<style>
  .block-container {{
    padding-top: 1.8rem !important;
    padding-bottom: 1rem !important;
    max-width: 1200px;
  }}
  .stApp {{ background-color: {PAGE_BG}; }}
</style>"""


def section_header(label, colour=BLUE_HDR):
    return (
        f'<div style="background:{colour}; border-radius:8px; padding:8px 18px;'
        f' margin-bottom:14px; font-weight:700; font-size:15px; color:{WHITE};'
        f' display:block; width:100%; box-sizing:border-box;">{label}</div>'
    )


def divider_line():
    return f'<hr style="border:none; border-top:1px solid {DIVIDER}; margin:18px 0;">'
