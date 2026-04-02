"""PDFDashboardWithMCP - Streamlit multi-page app."""

import sys
from pathlib import Path

# Add project root so `app` package is found when running app/main.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


import streamlit as st

st.set_page_config(page_title="PDFDashboardWithMCP", page_icon=":rocket:", layout="wide")

# Define navigation (sidebar: click to go to a page)
page = st.navigation([
    st.Page("app_pages/landing.py", title="Home", icon=":material/home:"),
    st.Page("app_pages/process_pdf_upload.py", title="Upload PDF", icon=":material/upload_file:"),
    st.Page("app_pages/pdf_library.py", title="Library", icon=":material/library_books:"),
    st.Page("app_pages/process_pdf.py", title="Chat", icon=":material/chat:"),
], position="sidebar")

# App-level title (shared across pages)
st.title(f"{page.icon} {page.title}")

page.run()
