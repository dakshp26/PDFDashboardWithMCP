"""OCR page RAG helpers: chunk like RAG page and persist to OCR Chroma."""

import copy
import re
from pathlib import Path

from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

OCR_COLLECTION_NAME = "process_pdf_rag"


def _get_data_root() -> Path:
    root = Path(__file__).resolve().parent.parent.parent
    return root / "data"


def _get_process_chroma_dir() -> Path:
    return _get_data_root() / "process_chroma"


def list_available_collections(persist_directory: Path | str | None = None) -> list[str]:
    """Return names of all collections in the Chroma persist directory."""
    persist_dir = Path(persist_directory) if persist_directory else _get_process_chroma_dir()
    if not persist_dir.exists():
        return []
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(persist_dir))
        return [c.name for c in client.list_collections()]
    except Exception:
        return []


def get_chunks_from_md(
    md_path: str | Path,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    document_name: str | None = None,
) -> list[Document]:
    """
    Load Markdown and split into chunks using the same strategy as RAG chunking.
    No PDF loaders are used.
    """
    path = Path(md_path)
    if not path.exists():
        raise FileNotFoundError(f"Markdown not found: {path}")

    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("Markdown is empty")

    md_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[
            ("#", "title"),
            ("##", "section"),
            ("###", "subsection"),
        ],
    )
    header_splits = md_splitter.split_text(text)

    if not header_splits:
        header_splits = [Document(page_content=text, metadata={})]

    # Enrich metadata: extract page numbers from "## Page N" section headers
    # and propagate document name into every chunk.
    current_page = None
    enriched = []
    for doc in header_splits:
        meta = copy.deepcopy(doc.metadata) if doc.metadata else {}
        section = meta.get("section", "")
        page_match = re.match(r"^Page (\d+)$", section)
        if page_match:
            current_page = int(page_match.group(1))
            del meta["section"]
        if current_page is not None:
            meta["page"] = current_page
        if document_name:
            meta["document"] = document_name
        meta.setdefault("source", str(path))
        enriched.append(Document(page_content=doc.page_content, metadata=meta))
    header_splits = enriched

    splits = []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    for doc in header_splits:
        meta = copy.deepcopy(doc.metadata) if doc.metadata else {}
        for chunk_text in splitter.split_text(doc.page_content):
            if chunk_text and chunk_text.strip():
                splits.append(Document(page_content=chunk_text, metadata=meta))

    return splits


def build_ocr_vectorstore_from_md(
    md_path: str | Path,
    persist_directory: Path | str | None = None,
    collection_name: str = OCR_COLLECTION_NAME,
    document_name: str | None = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    embedding_model: str = "nomic-embed-text",
) -> Chroma:
    """Build OCR page vectorstore from extracted markdown chunks."""
    path = Path(md_path)
    if not path.exists():
        raise FileNotFoundError(f"Markdown not found: {path}")

    persist_dir = Path(persist_directory) if persist_directory else _get_process_chroma_dir()
    persist_dir.mkdir(parents=True, exist_ok=True)

    splits = get_chunks_from_md(path, chunk_size=chunk_size, chunk_overlap=chunk_overlap, document_name=document_name)
    if not splits:
        raise ValueError(
            "Markdown produced no meaningful text chunks."
        )

    embeddings = OllamaEmbeddings(model=embedding_model)
    try:
        test_emb = embeddings.embed_query("test")
        if not test_emb:
            raise ValueError(
                f"Ollama embedding model '{embedding_model}' returned empty embeddings. "
                f"Ensure Ollama is running and the model is pulled: ollama pull {embedding_model}"
            )
    except (ConnectionError, ValueError):
        raise
    except Exception as e:
        raise ConnectionError(
            f"Could not reach Ollama or embedding model '{embedding_model}'. "
            f"Start Ollama and run: ollama pull {embedding_model}"
        ) from e

    try:
        Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=str(persist_dir),
        ).delete_collection()
    except Exception:
        pass

    return Chroma.from_documents(
        documents=splits,
        embedding=embeddings,
        collection_name=collection_name,
        persist_directory=str(persist_dir),
    )


def load_ocr_vectorstore_from_persist(
    persist_directory: Path | str | None = None,
    collection_name: str = OCR_COLLECTION_NAME,
    embedding_model: str = "nomic-embed-text",
) -> Chroma | None:
    """Load OCR page vectorstore from disk if available and non-empty."""
    persist_dir = Path(persist_directory) if persist_directory else _get_process_chroma_dir()
    if not persist_dir.exists():
        return None

    try:
        embeddings = OllamaEmbeddings(model=embedding_model)
        vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=str(persist_dir),
        )
        if vectorstore._collection.count() == 0:
            return None
        return vectorstore
    except Exception:
        return None
