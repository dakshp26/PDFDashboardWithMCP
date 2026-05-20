<div align="center">
    
# PDF Dashboard With MCP

<p align="center">
  <a href="https://streamlit.io/"><img src="https://img.shields.io/badge/UI-Streamlit-FF4B4B?logo=streamlit&logoColor=white" alt="Streamlit" /></a>
  <a href="https://www.langchain.com/"><img src="https://img.shields.io/badge/LangChain-1C3C3C?logo=langchain&logoColor=white" alt="LangChain" /></a>
  <a href="https://pymupdf.readthedocs.io/"><img src="https://img.shields.io/badge/PDF-PyMuPDF4LLM-094D8E" alt="PyMuPDF4LLM" /></a>
  <a href="https://ollama.com/"><img src="https://img.shields.io/badge/LLM-Ollama-black?logo=ollama&logoColor=white" alt="Ollama" /></a>
  <a href="https://www.trychroma.com/"><img src="https://img.shields.io/badge/vectorstore-Chroma-FF6B35" alt="Chroma" /></a>
  <a href="https://docs.astral.sh/uv/"><img src="https://img.shields.io/badge/package%20manager-uv-DE5FE9" alt="uv" /></a>
  <a href="https://modelcontextprotocol.io/"><img src="https://img.shields.io/badge/MCP-mcp%5Bcli%5D-black" alt="MCP" /></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python 3.11+" />
</p>

Upload PDFs, extract text with PyMuPDF or GLM-OCR (Ollama), and ask questions against the document with a local Ollama model. No API keys.

</div>

## Features

- **PDF extraction**: PyMuPDF for text layers; GLM-OCR when the PDF is scanned or image-only
- **Per-document RAG**: each upload gets its own Chroma collection
- **Local chat**: LangChain agent with inline citations; choose any installed Ollama model from the dropdown
- **Markdown viewer**: read extracted text, preview chunks, download markdown

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Ollama](https://ollama.com/download)

## Setup

**1. Clone the repository**

```powershell
git clone https://github.com/dakshp26/PDFDashboardWithMCP.git
cd PDFDashboardWithMCP
```

**2. Install dependencies**

```powershell
uv sync
```

**3. Pull Ollama models**

```powershell
ollama pull qwen2.5:3b       # chat (or another chat model)
ollama pull nomic-embed-text # embeddings
ollama pull glm-ocr          # OCR for scanned PDFs
```

**4. Run the app**

```powershell
uv run streamlit run app/main.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

## Usage

1. **Upload PDF**: open Upload PDF, select a file, wait for extraction to finish
2. **Chat**: open Chat, pick the PDF and an Ollama model, ask questions

## Project Structure

```
app/
├── main.py                       # Entry point, page navigation
├── app_pages/
│   ├── landing.py                # Home page
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

> [!NOTE]
> File-by-file breakdown, execution order, and data flow: [APP_STRUCTURE.md](APP_STRUCTURE.md).

## Pages

| Page | What it does |
|------|--------------|
| **Home** | Links and setup summary |
| **Upload PDF** | Run extraction (text layer, OCR fallback, chunking, embedding); download markdown |
| **PDF Library** | Open past uploads; view markdown and chunk previews without re-running extraction |
| **Chat** | Query an indexed PDF with citations |

Extraction progress shows in an `st.status` block. After processing, the Chroma collection lives in `data/process_chroma/` and loads on the next run without re-extracting.

## MCP Server

Two tools for MCP clients (Claude Desktop, Cursor, Claude Code):

- **`list_documents`**: indexed document collections
- **`get_document(document, query)`**: semantic search over a collection

<details>
<summary>Claude Desktop</summary>

Add to `claude_desktop_config.json` (Windows: `%APPDATA%\Claude\claude_desktop_config.json`) or use `.mcp.json` in the project root:

```json
{
  "mcpServers": {
    "PDFDashboardWithMCP": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/PDFDashboardWithMCP", "mcp_server/server.py"]
    }
  }
}
```

</details>

<details>
<summary>Cursor</summary>

Add to `.cursor/mcp.json` in the project root or global `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "PDFDashboardWithMCP": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/PDFDashboardWithMCP", "mcp_server/server.py"]
    }
  }
}
```

</details>

<details>
<summary>Claude Code</summary>

Project-scoped `.mcp.json` in the repo root keeps the server tied to this repo:

```json
{
  "mcpServers": {
    "PDFDashboardWithMCP": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/PDFDashboardWithMCP", "mcp_server/server.py"]
    }
  }
}
```

Claude Code reads `.mcp.json` when you open the project.

</details>

Replace `/absolute/path/to/PDFDashboardWithMCP` with your clone path.

> Ollama must be running with `nomic-embed-text` pulled before the MCP server can load collections.

## Tech Stack

| Component | Library |
|-----------|---------|
| UI | Streamlit |
| PDF extraction | langchain-pymupdf4llm, PyMuPDF |
| OCR fallback | Ollama glm-ocr |
| Embeddings | Ollama nomic-embed-text |
| Vector store | Chroma (langchain-chroma) |
| LLM / agent | Ollama chat model (e.g. qwen2.5:3b), LangChain |
| Package manager | uv |
| MCP server | mcp[cli] |
