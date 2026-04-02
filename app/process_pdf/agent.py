"""Agentic RAG: Ollama chat + retriever tool."""

from typing import Any, Callable

from langchain.agents import create_agent
from langchain_ollama import ChatOllama
from langchain_core.vectorstores import VectorStore
from langchain_core.tools import tool


def _format_source(doc) -> str:
    """Format document metadata as source label (document name, page, section)."""
    meta = doc.metadata or {}
    document = meta.get("document") or "Document"
    page = meta.get("page")
    display_page = page if page is not None else "?"
    section = meta.get("section") or meta.get("title") or meta.get("subsection")
    label = f"Document {document}, Page {display_page}"
    if section:
        label += f", {section}"
    return label


def make_retriever_tool(retriever, on_retrieve: Callable[[list], None] | None = None):
    """Create a search tool from a retriever. Optional callback receives retrieved docs for UI display."""

    @tool
    def search_documents(query: str) -> str:
        """Search the uploaded PDF for relevant information. Use when the user asks about content."""
        docs = retriever.invoke(query)
        if not docs:
            return "No relevant content found."
        if on_retrieve:
            on_retrieve(docs)
        parts = []
        for d in docs:
            src = _format_source(d)
            parts.append(f"[Source: {src}]\n{d.page_content}")
        return "\n\n---\n\n".join(parts)

    return search_documents


def build_agent(
    vectorstore: VectorStore,
    chat_model: str = "qwen2.5:3b",
    on_retrieve: Callable[[list], None] | None = None,
) -> Any:
    """
    Build agentic RAG agent: Ollama chat with retriever tool.
    The agent decides when to search documents vs answer directly.
    on_retrieve: optional callback when docs are retrieved, for UI to display sources.
    """
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
    search_tool = make_retriever_tool(retriever, on_retrieve=on_retrieve)

    model = ChatOllama(model=chat_model, temperature=0.1)
    agent = create_agent(
        model,
        tools=[search_tool],
        system_prompt=(
            "You answer questions about the user's uploaded PDF. You must use the search tool to find relevant passages before responding. "
            "Only use information from the document search response. Include concise inline citations in the answer body (e.g. '(Page 3, Introduction)') "
            "and also include a separate 'Sources' section at the end listing page number and section."
        ),
    )
    return agent
