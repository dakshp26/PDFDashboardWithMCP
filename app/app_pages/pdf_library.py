"""PDF Library - browse uploaded PDFs."""

from pathlib import Path

import streamlit as st


def _get_ocr_dir() -> Path:
    root = Path(__file__).resolve().parent.parent.parent
    return root / "data" / "process_pdf"


ocr_dir = _get_ocr_dir()
pdf_stems = sorted(p.stem for p in ocr_dir.glob("*.pdf")) if ocr_dir.exists() else []

if not pdf_stems:
    st.info("No PDFs available. Upload a PDF first.")
    st.stop()

col_list, col_view = st.columns([1, 3])

with col_list:
    selected = st.radio(
        "Documents",
        pdf_stems,
        index=0,
        key="library_selected_pdf",
        label_visibility="collapsed",
    )

with col_view:
    view = st.segmented_control(
        "View",
        options=["PDF", "Markdown"],
        default="PDF",
        key="library_view",
    )

    if view == "PDF":
        pdf_path = ocr_dir / f"{selected}.pdf"
        if pdf_path.exists():
            st.pdf(pdf_path.read_bytes(), height=660)
        else:
            st.warning("PDF file not found on disk.")
    else:
        md_path = ocr_dir / f"{selected}.md"
        if md_path.exists():
            md_text = md_path.read_text(encoding="utf-8")
            tab_preview, tab_raw = st.tabs(["Preview", "Raw Markdown"])
            with tab_preview:
                with st.container(height=620):
                    st.markdown(md_text)
            with tab_raw:
                with st.container(height=620):
                    st.code(md_text, language="markdown")
        else:
            st.info("No extracted markdown for this PDF yet.")
