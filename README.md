# PDFDashboardWithMCP

Upload PDFs, extract their text via OCR, and chat with the document using a local LLM. Everything runs on your machine through [Ollama](https://ollama.com) — no API keys or internet connection required.

## Features

- **PDF extraction** — fast text-layer extraction via PyMuPDF; automatic GLM-OCR fallback for scanned/image-based PDFs
- **Per-document RAG** — each uploaded PDF gets its own Chroma vector collection
- **Local LLM chat** — agentic Q&A with inline citations powered by Ollama; pick any installed Ollama model from the dropdown
- **Markdown viewer** — browse extracted text, preview chunks, and download the markdown

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) — Python package manager
- [Ollama](https://ollama.com/download) — local LLM runtime

## Setup

**1. Install dependencies**

```powershell
uv sync
```

**2. Pull Ollama models**

```powershell
ollama pull qwen2.5:3b       # chat / agent (or any other chat model)
ollama pull nomic-embed-text # embeddings
ollama pull glm-ocr          # OCR fallback (scanned PDFs)
```

**3. Run the app**

```powershell
uv run streamlit run app/main.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

## Usage

1. **Upload PDF** — go to the Upload PDF page, select a PDF, and wait for the extraction pipeline to finish
2. **Chat** — switch to the Chat page, pick your PDF and any installed Ollama model from the dropdowns, and ask questions

## Project Structure

```
app/
├── main.py                       # Entry point, page navigation
├── app_pages/
│   ├── landing.py                # Home / welcome page
│   ├── process_pdf_upload.py     # Upload + pipeline UI
│   ├── pdf_library.py            # Browse uploaded PDFs (read-only viewer)
│   └── process_pdf.py            # Viewer + chat UI
└── process_pdf/
    ├── extract.py                 # PDF → Markdown (pymupdf4llm + GLM-OCR)
    ├── pipeline.py                # Extraction pipeline with live progress
    ├── rag.py                     # Chunking, embeddings, Chroma persistence
    └── agent.py                   # LangChain agent with retriever tool
mcp_server/
└── server.py                     # MCP server (list_documents, get_document)
data/                             # Runtime data (gitignored)
├── process_pdf/                  # Saved PDFs and extracted markdown
└── process_chroma/               # Chroma vector collections (one per PDF)
```

## MCP Server

The included MCP server exposes the vector store to any MCP-compatible client (Claude Desktop, Cursor, etc.) with two tools:

- **`list_documents`** — returns all indexed document collections
- **`get_document(document, query)`** — searches a collection and returns relevant chunks

### Claude Desktop

Add to `claude_desktop_config.json` (usually `%APPDATA%\Claude\claude_desktop_config.json` on Windows OR in .mcp.json within project to keep it limited to a project):

```json
{
  "mcpServers": {
    "PDFDashboardWithMCP": {
      "command": "uv",
      "args": ["run", "mcp_server/server.py"],
      "cwd": "/absolute/path/to/PDFDashboardWithMCP"
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json` in your project root (or the global `~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "PDFDashboardWithMCP": {
      "command": "uv",
      "args": ["run", "mcp_server/server.py"],
      "cwd": "/absolute/path/to/PDFDashboardWithMCP"
    }
  }
}
```

Replace `/absolute/path/to/PDFDashboardWithMCP` with the actual path to your cloned repository.

> Ollama must be running with `nomic-embed-text` pulled for the MCP server to load collections.

## Tech Stack

| Component | Library |
|-----------|---------|
| UI | Streamlit |
| PDF extraction | langchain-pymupdf4llm, PyMuPDF |
| OCR fallback | Ollama glm-ocr |
| Embeddings | Ollama nomic-embed-text |
| Vector store | Chroma (langchain-chroma) |
| LLM / agent | Any Ollama chat model (e.g. qwen2.5:3b), LangChain |
| Package manager | uv |
| MCP server | mcp[cli] |
