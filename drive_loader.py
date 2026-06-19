"""
CSV loader for the XRP dashboard.

File listing: always fetched fresh from GitHub (tiny JSON call).
File download: cached by filename — only re-downloads when a new file appears.

This means the dashboard always detects new files on every page load,
with no manual refresh needed.
"""

import glob
import io
import os

import requests
import streamlit as st

CSV_PREFIX = "xero_people_"


def _list_github_files(token, repo, folder):
    """Always runs fresh — returns sorted list of CSV filenames in the repo."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    folder_path = folder.strip("/")
    url = f"https://api.github.com/repos/{repo}/contents/{folder_path}"
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    files = [
        f for f in resp.json()
        if f["name"].startswith(CSV_PREFIX) and f["name"].endswith(".csv")
    ]
    return sorted(files, key=lambda f: f["name"], reverse=True)


@st.cache_data(show_spinner="Downloading latest export from GitHub…")
def _download_file(token, download_url, filename):
    """Cached by filename — only re-downloads when a new file is uploaded."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    dl = requests.get(download_url, headers=headers, timeout=60)
    dl.raise_for_status()
    return dl.content


def get_latest_csv(refresh_key=0):
    """Return (file_ref, filename) for the latest xero_people CSV."""
    token = st.secrets.get("GITHUB_TOKEN")
    repo  = st.secrets.get("GITHUB_REPO")
    if token and repo:
        folder = st.secrets.get("GITHUB_FOLDER", "")
        try:
            files = _list_github_files(token, repo, folder)
            if not files:
                st.warning("No xero_people_*.csv files found in the GitHub repo.")
            else:
                latest  = files[0]
                content = _download_file(token, latest["download_url"], latest["name"])
                return io.BytesIO(content), latest["name"]
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
    hits = (
        glob.glob(os.path.expanduser("~/Downloads/xero_people_*.csv"))
        + glob.glob(os.path.expanduser("~/Desktop/xero_people_*.csv"))
    )
    if hits:
        path = max(hits, key=os.path.getmtime)
        return path, os.path.basename(path)
    return None, None
