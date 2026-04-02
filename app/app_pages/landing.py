"""Landing page."""

import streamlit as st

st.caption("Chat with your documents using a local LLM — no API keys required.")

st.markdown(
    """
**docWebMCP** extracts text from PDFs and lets you ask questions about them using a
local LLM running through [Ollama](https://ollama.com). All processing happens on your machine.
"""
)

st.divider()

st.subheader(":material/upload_file: Step 1 — Upload PDF")
st.markdown(
    """
Go to the **Upload PDF** page and select a PDF file.

- Text-based PDFs are extracted instantly via PyMuPDF.
- Scanned or image-based PDFs automatically fall back to GLM-OCR.
- Once processing completes, the document is chunked, embedded, and saved for future sessions.
"""
)

st.subheader(":material/chat: Step 2 — Chat")
st.markdown(
    """
Go to the **Chat** page to query any previously uploaded PDF.

- Select a document from the dropdown — it loads instantly from the saved index.
- Pick any Ollama model installed on your machine to answer queries.
- Toggle between the original PDF and the extracted Markdown in the viewer.
- Ask questions in the chat; the agent retrieves relevant passages and cites the source page and section.
"""
)

st.divider()

st.subheader(":material/info: Requirements")
st.markdown(
    """
Ollama must be running locally with these models pulled:

| Model | Purpose |
|-------|---------|
| any chat model (e.g. `qwen2.5:3b`) | Chat / agent — pick from the dropdown |
| `nomic-embed-text` | Embeddings |
| `glm-ocr` | OCR fallback for scanned PDFs |

```
ollama pull qwen2.5:3b       # or any other chat model
ollama pull nomic-embed-text
ollama pull glm-ocr
```
"""
)
