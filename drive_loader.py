"""
CSV loader for the XRP dashboard.

On Streamlit Cloud: fetches the latest xero_people_*.csv from a private
GitHub repo using a personal access token stored in Streamlit secrets.

Locally: auto-detects the latest xero_people_*.csv in ~/Downloads or ~/Desktop.
"""

import glob
import io
import os

import requests
import streamlit as st

CSV_PREFIX = "xero_people_"


@st.cache_data(ttl=300, show_spinner="Fetching latest export from GitHub…")
def _fetch_from_github(token, repo, folder):
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    # List files in the repo folder
    folder_path = folder.strip("/")
    url = f"https://api.github.com/repos/{repo}/contents/{folder_path}"
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()

    files = [
        f for f in resp.json()
        if f["name"].startswith(CSV_PREFIX) and f["name"].endswith(".csv")
    ]
    if not files:
        return None, None

    # Filenames are timestamped so alphabetical sort = chronological
    latest = sorted(files, key=lambda f: f["name"], reverse=True)[0]

    dl = requests.get(latest["download_url"], headers=headers, timeout=60)
    dl.raise_for_status()
    return io.BytesIO(dl.content), latest["name"]


def get_latest_csv():
    """Return (file_ref, filename) for the latest xero_people CSV.

    Tries GitHub first (if GITHUB_TOKEN + GITHUB_REPO are in Streamlit secrets),
    then falls back to local files for development.
    """
    token = st.secrets.get("GITHUB_TOKEN")
    repo  = st.secrets.get("GITHUB_REPO")
    if token and repo:
        folder = st.secrets.get("GITHUB_FOLDER", "")
        try:
            buf, name = _fetch_from_github(token, repo, folder)
            if buf is not None:
                return buf, name
            st.warning("No xero_people_*.csv files found in the GitHub repo.")
        except Exception as e:
            st.warning(f"GitHub fetch failed ({e}); falling back to local files.")

    # Local dev fallback
    hits = (
        glob.glob(os.path.expanduser("~/Downloads/xero_people_*.csv"))
        + glob.glob(os.path.expanduser("~/Desktop/xero_people_*.csv"))
    )
    if hits:
        path = max(hits, key=os.path.getmtime)
        return path, os.path.basename(path)

    return None, None


def get_local_csv():
    """Local-only fallback (used as uploader alternative on sidebar pages)."""
    hits = (
        glob.glob(os.path.expanduser("~/Downloads/xero_people_*.csv"))
        + glob.glob(os.path.expanduser("~/Desktop/xero_people_*.csv"))
    )
    if hits:
        path = max(hits, key=os.path.getmtime)
        return path, os.path.basename(path)
    return None, None
