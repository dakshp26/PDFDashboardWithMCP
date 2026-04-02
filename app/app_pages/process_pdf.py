"""OCR PDF - view PDF/markdown and chat with the document."""

from pathlib import Path

import streamlit as st

from app.process_pdf import get_chunks_from_md, load_ocr_vectorstore_from_persist
from app.process_pdf.agent import build_agent

import ollama


models_available = [model["model"] for model in ollama.list()["models"]]  # could add more models here in the future

def _get_ocr_dir() -> Path:
    root = Path(__file__).resolve().parent.parent.parent
    return root / "data" / "process_pdf"


def _list_saved_pdfs() -> list[str]:
    ocr_dir = _get_ocr_dir()
    if not ocr_dir.exists():
        return []
    return sorted(p.stem for p in ocr_dir.glob("*.pdf"))


def _load_pdf_bytes(stem: str) -> bytes | None:
    path = _get_ocr_dir() / f"{stem}.pdf"
    if not path.exists():
        return None
    try:
        return path.read_bytes()
    except Exception:
        return None


def _load_markdown(stem: str) -> str:
    path = _get_ocr_dir() / f"{stem}.md"
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


@st.dialog("Chunks created from Markdown", width="large")
def show_md_chunks_dialog(stem: str):
    md_path = _get_ocr_dir() / f"{stem}.md"
    if not md_path.exists():
        st.warning("No extracted markdown has been saved yet.")
        return
    try:
        with st.spinner("Loading chunks..."):
            chunks = get_chunks_from_md(md_path)
        st.caption(f"**{len(chunks)}** chunks created from extracted markdown")
        st.divider()
        for i, doc in enumerate(chunks):
            meta = doc.metadata or {}
            section = meta.get("section") or meta.get("title") or meta.get("subsection") or ""
            header = f"Chunk {i + 1}" + (f" - {section}" if section else "")
            with st.expander(header, expanded=(i < 3)):
                st.text(doc.page_content)
        st.divider()
        if st.button("Close", key="close_md_chunks_dialog"):
            st.rerun()
    except Exception as e:
        st.error(f"Failed to load chunks: {e}")


if "ocr_active_pdf" not in st.session_state:
    st.session_state.ocr_active_pdf = None
if "ocr_vectorstore" not in st.session_state:
    st.session_state.ocr_vectorstore = None
if "ocr_agent" not in st.session_state:
    st.session_state.ocr_agent = None
if "ocr_messages" not in st.session_state:
    st.session_state.ocr_messages = []
if "ocr_last_retrieval_sources" not in st.session_state:
    st.session_state.ocr_last_retrieval_sources = []
if "ocr_last_retrieval_chunks" not in st.session_state:
    st.session_state.ocr_last_retrieval_chunks = []
if "ocr_retrieval_buffer" not in st.session_state:
    st.session_state.ocr_retrieval_buffer = []


def _make_on_retrieve(buf: list):
    def _on_retrieve(docs):
        buf.clear()
        buf.extend(docs or [])
    return _on_retrieve


def _process_retrieval_buffer(buf: list) -> tuple[list[str], list[dict]]:
    sources, chunks = [], []
    for d in buf:
        m = d.metadata or {}
        document = m.get("document") or "Document"
        page = m.get("page")
        display_page = page if page is not None else "?"
        sec = m.get("section") or m.get("title") or m.get("subsection") or ""
        src = f"Document {document}, Page {display_page}"
        if sec:
            src += f", {sec}"
        sources.append(src)
        chunks.append({"source": src, "content": d.page_content})
    return list(dict.fromkeys(sources)), chunks


# ── PDF selection ─────────────────────────────────────────────────────────────
pdf_stems = _list_saved_pdfs()

if not pdf_stems:
    st.info("No PDFs available. Upload a PDF first.")
    st.stop()

selected = st.selectbox("Select PDF", pdf_stems, key="ocr_selected_pdf")

# ── Model selection ─────────────────────────────────────────────────────────────
selected_model = st.selectbox("Select Model", models_available, key="ocr_selected_model")

# Load vectorstore + agent when selection changes
if selected != st.session_state.ocr_active_pdf:
    vs = load_ocr_vectorstore_from_persist(collection_name=selected)
    if vs:
        st.session_state.ocr_vectorstore = vs
        st.session_state.ocr_agent = build_agent(
            vs,
            chat_model=selected_model,
            on_retrieve=_make_on_retrieve(st.session_state.ocr_retrieval_buffer),
        )
        st.session_state.ocr_messages = []
        st.session_state.ocr_active_pdf = selected
    else:
        st.session_state.ocr_agent = None
        st.session_state.ocr_active_pdf = selected

col_doc, col_chat = st.columns([1, 1])

with col_doc:
    view = st.segmented_control(
        "View",
        options=["PDF", "Markdown"],
        default="PDF",
        key="ocr_doc_view",
    )

    if view == "PDF":
        pdf_bytes = _load_pdf_bytes(selected)
        if pdf_bytes:
            st.pdf(pdf_bytes, height=560)
        else:
            st.info("PDF file not found.")
    else:
        md_text = _load_markdown(selected)
        if md_text.strip():
            if st.button(":material/view_list: Show chunks", key="show_md_chunks"):
                show_md_chunks_dialog(selected)
            tab_preview, tab_raw = st.tabs(["Preview", "Raw Markdown"])
            with tab_preview:
                with st.container(height=500):
                    st.markdown(md_text)
            with tab_raw:
                with st.container(height=500):
                    st.code(md_text, language="markdown")
            st.download_button(
                label="Download Markdown",
                data=md_text,
                file_name=f"{selected}.md",
                mime="text/markdown",
            )
        else:
            st.info("No extracted markdown yet.")

with col_chat:
    st.subheader("Chat")
    if not st.session_state.ocr_agent:
        st.info("No indexed collection found for this PDF. Re-upload to process it.")
    else:
        for msg in st.session_state.ocr_messages:
            with st.chat_message(
                msg["role"],
                avatar=(
                    ":material/person:"
                    if msg["role"] == "user"
                    else ":material/smart_toy:"
                ),
            ):
                if msg["role"] == "assistant" and msg.get("chunks"):
                    with st.expander(f":material/database: Retrieved chunks ({len(msg['chunks'])})"):
                        for i, chunk in enumerate(msg["chunks"]):
                            st.caption(f"**{chunk['source']}**")
                            st.text(chunk["content"])
                            if i < len(msg["chunks"]) - 1:
                                st.divider()
                st.write(msg["content"])
                if msg["role"] == "assistant" and msg.get("sources"):
                    st.caption(":material/bookmark: **Sources:** " + " • ".join(msg["sources"]))

        if prompt := st.chat_input("Ask about the OCR PDF", key="ocr_chat_input"):
            st.session_state.ocr_retrieval_buffer.clear()
            st.session_state.ocr_messages.append({"role": "user", "content": prompt})
            with st.chat_message("user", avatar=":material/person:"):
                st.write(prompt)

            with st.chat_message("assistant", avatar=":material/smart_toy:"):
                try:
                    from langchain_core.messages import AIMessage, HumanMessage

                    messages = [
                        HumanMessage(content=m["content"])
                        if m["role"] == "user"
                        else AIMessage(content=m["content"])
                        for m in st.session_state.ocr_messages
                    ]
                    result = st.session_state.ocr_agent.invoke({"messages": messages})
                    response = result["messages"][-1].content
                except Exception as e:
                    response = f"Error: {e}"

                sources, chunks = _process_retrieval_buffer(st.session_state.ocr_retrieval_buffer)
                if chunks:
                    with st.expander(f":material/database: Retrieved chunks ({len(chunks)})"):
                        for i, chunk in enumerate(chunks):
                            st.caption(f"**{chunk['source']}**")
                            st.text(chunk["content"])
                            if i < len(chunks) - 1:
                                st.divider()
                if response.startswith("Error:"):
                    st.error(response)
                else:
                    st.write(response)
                if sources:
                    st.caption(":material/bookmark: **Sources:** " + " • ".join(sources))
                st.session_state.ocr_messages.append(
                    {"role": "assistant", "content": response, "sources": sources, "chunks": chunks}
                )
