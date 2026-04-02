"""PDF Upload - upload a PDF and run the extraction pipeline."""

import hashlib
import re
from pathlib import Path

import streamlit as st

from app.process_pdf import load_ocr_vectorstore_from_persist, render_pipeline
from app.process_pdf.agent import build_agent


def _get_ocr_dir() -> Path:
    root = Path(__file__).resolve().parent.parent.parent
    return root / "data" / "process_pdf"


def _make_on_retrieve(buf: list):
    def _on_retrieve(docs):
        buf.clear()
        buf.extend(docs or [])
    return _on_retrieve


if "last_process_pdf_key" not in st.session_state:
    st.session_state.last_process_pdf_key = None
if "ocr_vectorstore" not in st.session_state:
    st.session_state.ocr_vectorstore = None
if "ocr_agent" not in st.session_state:
    st.session_state.ocr_agent = None
if "ocr_messages" not in st.session_state:
    st.session_state.ocr_messages = []
if "ocr_retrieval_buffer" not in st.session_state:
    st.session_state.ocr_retrieval_buffer = []
if "ocr_active_pdf" not in st.session_state:
    st.session_state.ocr_active_pdf = None

st.caption(
    "Upload a PDF to extract text as Markdown. "
    "Saved files go to `data/process_pdf`, chunks to `data/process_chroma`."
)

uploaded = st.file_uploader("Upload PDF", type=["pdf"], key="process_pdf_upload")

if uploaded:
    pdf_bytes = uploaded.read()
    pdf_key = hashlib.sha256(pdf_bytes).hexdigest()

    base_stem = re.sub(r"[^a-zA-Z0-9,\-]", "_", Path(uploaded.name).stem)
    suffix = Path(uploaded.name).suffix
    ocr_dir = _get_ocr_dir()

    stem = base_stem
    pdf_path = ocr_dir / f"{stem}{suffix}"
    counter = 1
    while pdf_path.exists():
        stem = f"{base_stem}_{counter}"
        pdf_path = ocr_dir / f"{stem}{suffix}"
        counter += 1

    md_path = ocr_dir / f"{stem}.md"

    if st.session_state.last_process_pdf_key != pdf_key:
        _get_ocr_dir().mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(pdf_bytes)
        try:
            vectorstore, agent, md_text = render_pipeline(
                pdf_path,
                md_path,
                on_retrieve=_make_on_retrieve(st.session_state.ocr_retrieval_buffer),
                collection_name=stem,
            )
            if not md_text.strip():
                st.warning(
                    "No text could be extracted. Ensure Ollama is running and glm-ocr is pulled: "
                    "`ollama pull glm-ocr`"
                )
            else:
                st.session_state.ocr_vectorstore = vectorstore
                st.session_state.ocr_agent = agent
                st.session_state.ocr_messages = []
                st.session_state.last_process_pdf_key = pdf_key
                st.session_state.ocr_active_pdf = stem
                st.success(f"**{stem}** processed successfully. Head to the Chat page to query it.")
        except Exception as e:
            st.error(
                f"Error: {e}\n\nEnsure Ollama is running and you have pulled glm-ocr: "
                "`ollama pull glm-ocr`"
            )
    else:
        st.success(f"**{st.session_state.ocr_active_pdf}** is ready. Head to the Chat page to query it.")
else:
    st.info("Upload a PDF to get started.")
