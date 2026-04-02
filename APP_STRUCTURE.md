# App Structure

Overview of the multi-page Streamlit app and the `app/process_pdf` module. Entry point is `app/main.py`.

---

## Directory Layout

```
app/
├── main.py                       # Entry point, navigation setup (4 pages)
├── app_pages/
│   ├── landing.py                # Home page
│   ├── process_pdf_upload.py     # Upload PDF + run extraction pipeline
│   ├── pdf_library.py            # Browse uploaded PDFs (view PDF or Markdown)
│   └── process_pdf.py            # PDF/Markdown viewer + RAG chat (per-PDF selection)
├── process_pdf/
│   ├── __init__.py
│   ├── extract.py                # pymupdf4llm extraction + GLM-OCR fallback
│   ├── pipeline.py               # End-to-end OCR → RAG generator + Streamlit renderer
│   ├── rag.py                    # Markdown chunking, per-PDF Chroma collections
│   └── agent.py                  # Agentic RAG: Ollama chat + retriever tool
mcp_server/
│   ├── __init__.py
│   └── server.py                 # FastMCP server exposing list_documents + get_document
data/
├── process_pdf/                  # Saved PDFs + extracted markdown (named by PDF stem)
└── process_chroma/               # ChromaDB persistence (one collection per PDF stem)
.mcp.json.example                 # Template MCP config for Claude Code / Cursor
```

---

## Files

### main.py

**Purpose:** Entry point and multi-page navigation.

- `st.set_page_config()` — page title `"PDFDashboardWithMCP"`, icon, layout
- `st.navigation()` — sidebar navigation with four pages:
  - **Home** (`landing.py`) — welcome and instructions
  - **Upload PDF** (`process_pdf_upload.py`) — upload PDF, run extraction pipeline
  - **Library** (`pdf_library.py`) — browse all uploaded PDFs
  - **Chat** (`process_pdf.py`) — view PDF/Markdown, select PDF, chat with RAG agent
- Shared title bar: `{page.icon} {page.title}`

### app_pages/landing.py

**Purpose:** Landing (Home) page.

- Welcome caption
- Info messages pointing users to **Upload PDF** and **Chat**

### app_pages/process_pdf_upload.py

**Purpose:** Upload a PDF and run the full OCR → RAG extraction pipeline.

- File uploader (`st.file_uploader`) — accepts PDF
- On new upload:
  - Derives sanitized stem: `Path(uploaded.name).stem.replace(" ", "_")`
  - Checks for filename collision; appends `_1`, `_2`, … if needed
  - Saves PDF as `data/process_pdf/{stem}.pdf`, markdown as `data/process_pdf/{stem}.md`
  - Calls `render_pipeline(pdf_path, md_path, collection_name=stem)` — shows live `st.status` progress
  - Stores `ocr_vectorstore`, `ocr_agent`, `ocr_active_pdf` in session state
- When no upload: displays the most recently saved PDF in the directory
- Session state keys initialised: `last_process_pdf_key`, `ocr_vectorstore`, `ocr_agent`, `ocr_messages`, `ocr_retrieval_buffer`, `ocr_active_pdf`

### app_pages/pdf_library.py

**Purpose:** Browse all uploaded PDFs without the chat interface.

- Lists all PDF stems from `data/process_pdf/*.pdf` via `st.radio`
- Two-column layout: document list (left) | document viewer (right)
- `st.segmented_control` toggle in the viewer:
  - **PDF** — renders the saved PDF with `st.pdf()`
  - **Markdown** — Preview / Raw Markdown tabs inside a scrollable container
- Read-only; no session state keys; no agent interaction

### app_pages/process_pdf.py

**Purpose:** View the extracted PDF/Markdown and chat with the RAG agent.

- **PDF selectbox** — lists all PDF stems from `data/process_pdf/*.pdf`; switching reloads the matching Chroma collection and rebuilds the agent, clearing chat history
- **Two-column layout:** document viewer | chat
- Document viewer has a `st.segmented_control` toggle:
  - **PDF** — renders saved PDF with `st.pdf()`
  - **Markdown** — scrollable preview + raw tabs; "Show chunks" dialog; Download button
- Chat column: `agent.invoke()` (non-streaming); retrieved chunks expander; source captions
- Session state keys: `ocr_active_pdf`, `ocr_vectorstore`, `ocr_agent`, `ocr_messages`, `ocr_retrieval_buffer`, `ocr_last_retrieval_sources`, `ocr_last_retrieval_chunks`

### process_pdf/extract.py

**Purpose:** Two-stage PDF text extraction.

- `extract_markdown_pages_with_pymupdf4llm(pdf_path)` — uses `PyMuPDF4LLMLoader` (langchain-pymupdf4llm) in `mode="page"`; yields per-page markdown; fast, text-layer only
- `extract_markdown_pages_with_glm_ocr(pdf_path, model, max_pages)` — renders pages to images, sends to `ChatOllama(model="glm-ocr")` via base64; yields per-page markdown; used as fallback when pymupdf4llm produces no output
- `convert_to_base64()` — PIL image → base64 JPEG helper

### process_pdf/pipeline.py

**Purpose:** End-to-end OCR → RAG pipeline with generator-based progress and Streamlit renderer.

- `PipelineStage` dataclass — snapshot after each step (`kind`, `page`, `page_markdown`, `n_chunks`, `vectorstore`, `agent`, `full_markdown`)
- `StageKind` — `"pymupdf_page_extracted"` | `"ocr_fallback"` | `"page_extracted"` | `"chunked"` | `"embedded"` | `"ready"`
- `run_rag_pipeline(pdf_path, md_path, max_pages, on_retrieve, collection_name)` — generator:
  1. pymupdf4llm extraction (yields `pymupdf_page_extracted` per page)
  2. If no pages extracted → yields `ocr_fallback`, then GLM-OCR (yields `page_extracted` per page)
  3. Writes full markdown to `md_path`
  4. Chunks → yields `chunked`
  5. Embeds → Chroma → yields `embedded`
  6. Builds agent → yields `ready`
  - `collection_name` defaults to `Path(pdf_path).stem.replace(" ", "_")`
- `render_pipeline(...)` — drives the generator inside `st.status`; returns `(vectorstore, agent, full_markdown)`

### process_pdf/rag.py

**Purpose:** Chunk extracted markdown and persist to a named Chroma collection.

- `get_chunks_from_md(md_path)` — MarkdownHeader + RecursiveCharacter splitters
- `build_ocr_vectorstore_from_md(md_path, persist_directory, collection_name, ...)` — chunks → Ollama embeddings (`nomic-embed-text`) → Chroma; deletes existing collection of same name before recreating
- `load_ocr_vectorstore_from_persist(persist_directory, collection_name, ...)` — reload named collection if non-empty; returns `None` otherwise
- `list_available_collections(persist_directory)` — returns list of all collection names in the Chroma persist dir via `chromadb.PersistentClient`
- `OCR_COLLECTION_NAME = "process_pdf_rag"` — default fallback; actual collections are named after the PDF stem

### process_pdf/agent.py

**Purpose:** Agentic RAG agent (shared by upload pipeline and chat page).

- `make_retriever_tool(retriever, on_retrieve)` — wraps vectorstore retriever as `search_documents` tool; optional `on_retrieve` callback collects docs for UI display
- `build_agent(vectorstore, chat_model, on_retrieve)` — `ChatOllama(model="qwen2.5:3b")` + search tool; `k=2` retrieval; system prompt for PDF Q&A with inline citations

### mcp_server/server.py

**Purpose:** FastMCP server exposing the vector store to MCP clients (Claude Code, Cursor, etc.).

- Built with `mcp.server.fastmcp.FastMCP` — server name `"docWebMCP"`
- Adds project root to `sys.path` so it can import from `app.process_pdf.rag`
- **`list_documents() → list[str]`** — calls `list_available_collections()`; returns all indexed PDF stems
- **`get_document(document, query) → str`** — loads the named Chroma collection via `load_ocr_vectorstore_from_persist`; runs `similarity_search(query, k=4)`; returns formatted chunks with page number and section header
- Transport: `stdio` (run with `uv run mcp_server/server.py`)
- Config template: `.mcp.json.example` — set `cwd` to project root and register under key `"PDFDashboardWithMCP"`

---

## Execution Order

### Upload PDF page

| Step | Action | Source |
|------|--------|--------|
| 1 | User uploads PDF | process_pdf_upload |
| 2 | Derive unique sanitized stem; check for filename collisions | process_pdf_upload |
| 3 | Save PDF to `data/process_pdf/{stem}.pdf` | process_pdf_upload |
| 4 | **`render_pipeline(pdf_path, md_path, collection_name=stem)`** | pipeline |
| 5 | pymupdf4llm extraction per page (or OCR fallback) | extract |
| 6 | Write full markdown to `data/process_pdf/{stem}.md` | pipeline |
| 7 | Chunk + embed → Chroma collection `{stem}` at `data/process_chroma` | rag |
| 8 | **`build_agent(vectorstore, on_retrieve=...)`** | agent |
| 9 | Store vectorstore, agent, `ocr_active_pdf=stem` in session state | process_pdf_upload |
| 10 | Display uploaded PDF preview | process_pdf_upload |

### Library page

| Step | Action | Source |
|------|--------|--------|
| 1 | List `data/process_pdf/*.pdf` → populate radio list | pdf_library |
| 2 | User selects a document | pdf_library |
| 3 | Render PDF or Markdown view (toggle) | pdf_library |

### Chat page

| Step | Action | Source |
|------|--------|--------|
| 1 | List `data/process_pdf/*.pdf` → populate selectbox | process_pdf |
| 2 | On selection change → **`load_ocr_vectorstore_from_persist(collection_name=stem)`** | rag |
| 3 | **`build_agent(vectorstore, on_retrieve=...)`** | agent |
| 4 | Render PDF viewer or Markdown (toggle) | process_pdf |
| 5 | On user message → **`agent.invoke()`** | process_pdf |
| 6 | Show assistant reply + retrieved chunks expander + source captions | process_pdf |

### MCP client query

| Step | Action | Source |
|------|--------|--------|
| 1 | Client calls `list_documents()` | mcp_server/server |
| 2 | `list_available_collections()` queries Chroma persist dir | rag |
| 3 | Client calls `get_document(document, query)` | mcp_server/server |
| 4 | `load_ocr_vectorstore_from_persist(collection_name)` → `similarity_search(k=4)` | rag |
| 5 | Formatted chunks (page + section) returned as string | mcp_server/server |

---

## Data Flow

```
PDF upload
    → process_pdf.extract (pymupdf4llm first, GLM-OCR fallback) → per-page markdown
    → Written to data/process_pdf/{stem}.md
    → process_pdf.rag.build_ocr_vectorstore_from_md(collection_name=stem)
        → Chroma (data/process_chroma, collection: {stem})
    → process_pdf.agent.build_agent(vectorstore) → LangChain agent

PDF Library page
    → Read-only view of data/process_pdf/{stem}.pdf or {stem}.md

PDF selection (chat page)
    → load_ocr_vectorstore_from_persist(collection_name=stem)
    → build_agent(vectorstore) → LangChain agent
    → User message → agent.invoke() → search_documents tool → retrieved chunks
    → Response + source captions

MCP client (Claude Code / Cursor)
    → mcp_server/server.py (stdio transport)
    → list_documents() → list_available_collections()
    → get_document(document, query) → similarity_search(k=4) → formatted chunks
```
