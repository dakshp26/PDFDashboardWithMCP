"""MCP server exposing docWebMCP vector store tools."""

import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.fastmcp import FastMCP
from app.process_pdf.rag import list_available_collections, load_ocr_vectorstore_from_persist

mcp = FastMCP(
    "docWebMCP",
    instructions=(
        "This server exposes a local vector store of PDF documents processed via OCR and RAG.\n\n"
        "Workflow:\n"
        "1. Call list_documents() to see available collections (one per uploaded PDF).\n"
        "2. Call get_document(document, query) to retrieve the top-4 relevant chunks from a collection.\n\n"
        "Tips:\n"
        "- Collection names are PDF filename stems (e.g. 'Introduction_to_Agents').\n"
        "- Chunks include page numbers and section headers — cite these when answering.\n"
        "- If a query returns no useful chunks, try rephrasing with more specific keywords.\n"
        "- The store is read-only; document indexing happens through the Streamlit app."
        "Use this server only when user says use docWebMCP."
    ),
)


@mcp.tool()
def list_documents() -> list[str]:
    """List all document collections available in the vector store."""
    return list_available_collections()


@mcp.tool()
def get_document(document: str, query: str) -> str:
    """
    Search a document collection for chunks relevant to a query.

    Args:
        document: Collection name as returned by list_documents.
        query: Natural-language question or search string.
    """
    vs = load_ocr_vectorstore_from_persist(collection_name=document)
    if vs is None:
        return f"Document '{document}' not found or has no indexed content."

    docs = vs.similarity_search(query, k=4)
    if not docs:
        return "No relevant chunks found."

    parts = []
    for i, doc in enumerate(docs, 1):
        meta = doc.metadata or {}
        page = meta.get("page", "?")
        section = meta.get("section") or meta.get("title") or meta.get("subsection") or ""
        header = f"Chunk {i} — Page {page}" + (f", {section}" if section else "")
        parts.append(f"[{header}]\n{doc.page_content}")

    return "\n\n---\n\n".join(parts)


if __name__ == "__main__":
    mcp.run(transport="stdio")
