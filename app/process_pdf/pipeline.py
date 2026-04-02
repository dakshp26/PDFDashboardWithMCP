"""End-to-end RAG pipeline: OCR extraction → chunking → embedding → agent.

Two entry points:

* ``run_rag_pipeline`` – plain generator; yields a ``PipelineStage`` after
  each major step so any caller can track progress without coupling to
  Streamlit.

* ``render_pipeline`` – Streamlit wrapper; drives the generator, renders
  each stage inside an ``st.status`` block, then displays the full extracted
  document below.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Generator, Literal

import streamlit as st

from app.process_pdf.agent import build_agent
from app.process_pdf.extract import (
    extract_markdown_pages_with_glm_ocr,
    extract_markdown_pages_with_pymupdf4llm,
)
from app.process_pdf.rag import build_ocr_vectorstore_from_md, get_chunks_from_md

StageKind = Literal["pymupdf_page_extracted", "ocr_fallback", "page_extracted", "chunked", "embedded", "ready"]


@dataclass
class PipelineStage:
    """Snapshot of pipeline state after one step completes.

    Attributes:
        kind:          Which step just finished.
        page:          1-based page number (``page_extracted`` only).
        page_markdown: Raw markdown for the page (``page_extracted`` only).
        n_chunks:      Number of text chunks produced (``chunked`` +).
        vectorstore:   Chroma instance (``embedded`` + ``ready``).
        agent:         LangChain agent (``ready`` only).
        full_markdown: Complete extracted markdown (``ready`` only).
    """

    kind: StageKind
    page: int | None = None
    page_markdown: str | None = None
    n_chunks: int | None = None
    vectorstore: Any = None
    agent: Any = None
    full_markdown: str | None = None


def run_rag_pipeline(
    pdf_path: str | Path,
    md_path: str | Path,
    max_pages: int = 3,
    on_retrieve: Callable[[list], None] | None = None,
    collection_name: str | None = None,
) -> Generator[PipelineStage, None, None]:
    """Generator that drives the full OCR → RAG pipeline.

    Yields one :class:`PipelineStage` per major step.  Callers iterate this
    and act on each stage as it arrives (e.g. update a progress UI).

    Args:
        pdf_path:    Path to the PDF file to process.
        md_path:     Where to persist the extracted markdown.
        max_pages:   Maximum number of pages to OCR (default 3).
        on_retrieve: Optional callback forwarded to the agent; called with
                     the list of retrieved ``Document`` objects on each tool
                     invocation.

    Yields:
        :class:`PipelineStage` instances in order:
        ``pymupdf_page_extracted`` × N (or ``ocr_fallback`` + ``page_extracted`` × N)
        → ``chunked`` → ``embedded`` → ``ready``.
    """
    md_path = Path(md_path)
    if not collection_name:
        collection_name = Path(pdf_path).stem.replace(" ", "_")

    # ── 1a. pymupdf4llm extraction (fast, text-based PDFs) ───────────────
    pages_text: list[str] = []
    for page_md in extract_markdown_pages_with_pymupdf4llm(str(pdf_path)):
        pages_text.append(page_md)
        yield PipelineStage(
            kind="pymupdf_page_extracted",
            page=len(pages_text),
            page_markdown=page_md,
        )

    # ── 1b. OCR fallback if pymupdf4llm produced no content ──────────────
    if not pages_text:
        yield PipelineStage(kind="ocr_fallback")
        for page_md in extract_markdown_pages_with_glm_ocr(str(pdf_path), max_pages=max_pages):
            pages_text.append(page_md)
            yield PipelineStage(
                kind="page_extracted",
                page=len(pages_text),
                page_markdown=page_md,
            )

    full_markdown = "\n\n---\n\n".join(pages_text)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(full_markdown, encoding="utf-8")

    # ── 2. Chunking ───────────────────────────────────────────────────────
    # get_chunks_from_md is fast (pure-Python text splitting) so calling it
    # here for the count and again inside build_ocr_vectorstore_from_md is
    # acceptable.
    chunks = get_chunks_from_md(md_path)
    yield PipelineStage(kind="chunked", n_chunks=len(chunks))

    # ── 3. Embedding + vectorstore ────────────────────────────────────────
    vectorstore = build_ocr_vectorstore_from_md(md_path, collection_name=collection_name, document_name=collection_name)
    yield PipelineStage(kind="embedded", vectorstore=vectorstore, n_chunks=len(chunks))

    # ── 4. Agent ──────────────────────────────────────────────────────────
    agent = build_agent(vectorstore, on_retrieve=on_retrieve)
    yield PipelineStage(
        kind="ready",
        vectorstore=vectorstore,
        agent=agent,
        full_markdown=full_markdown,
        n_chunks=len(chunks),
    )


def render_pipeline(
    pdf_path: str | Path,
    md_path: str | Path,
    max_pages: int = 3,
    on_retrieve: Callable[[list], None] | None = None,
    collection_name: str | None = None,
) -> tuple[Any, Any, str]:
    """Run the pipeline and render live progress in the active Streamlit context.

    Displays an ``st.status`` block that updates after each stage.  Once the
    pipeline finishes the full extracted document is rendered below the
    status block.

    Args:
        pdf_path:    Path to the PDF file to process.
        md_path:     Where to persist the extracted markdown.
        max_pages:   Maximum number of pages to OCR (default 3).
        on_retrieve: Optional callback forwarded to the agent.

    Returns:
        ``(vectorstore, agent, full_markdown)`` — ready to wire into the
        rest of the Streamlit session.
    """
    vectorstore: Any = None
    agent: Any = None
    full_markdown: str = ""

    with st.status("Running RAG pipeline…", expanded=True) as status:
        for stage in run_rag_pipeline(pdf_path, md_path, max_pages=max_pages, on_retrieve=on_retrieve, collection_name=collection_name):
            if stage.kind == "pymupdf_page_extracted":
                st.write(f":material/description: Page {stage.page} extracted (pymupdf4llm)")

            elif stage.kind == "ocr_fallback":
                st.write(":material/warning: No text layer found — falling back to OCR")

            elif stage.kind == "page_extracted":
                st.write(f":material/description: Page {stage.page} extracted (OCR)")

            elif stage.kind == "chunked":
                st.write(f":material/splitscreen: Split into {stage.n_chunks} chunks")

            elif stage.kind == "embedded":
                vectorstore = stage.vectorstore
                st.write(":material/database: Embedded and indexed in vectorstore")

            elif stage.kind == "ready":
                vectorstore = stage.vectorstore
                agent = stage.agent
                full_markdown = stage.full_markdown or ""
                status.update(label="Pipeline complete!", state="complete", expanded=False)


    return vectorstore, agent, full_markdown
