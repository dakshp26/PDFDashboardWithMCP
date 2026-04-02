"""OCR PDF extraction utilities using pymupdf4llm (LangChain) and Ollama GLM-OCR."""

import base64
from io import BytesIO
from pathlib import Path

from PIL import Image

TEMP_IMG_PATH = Path.cwd() / "temp.png"


def extract_markdown_pages_with_pymupdf4llm(pdf_path: str):
    """Extract markdown from PDF pages using langchain-pymupdf4llm.

    Yields each page's markdown as soon as it is extracted.
    Returns nothing (empty generator) if the document has no extractable text.
    """
    from langchain_pymupdf4llm import PyMuPDF4LLMLoader

    loader = PyMuPDF4LLMLoader(pdf_path, mode="page")
    docs = loader.load()
    for doc in docs:
        text = (doc.page_content or "").strip()
        if text:
            page_num = doc.metadata.get("page", 0) + 1
            yield f"## Page {page_num}\n\n{text}"


def convert_to_base64(pil_image: Image.Image) -> str:
    """
    Convert PIL images to Base64 encoded strings.

    :param pil_image: PIL image
    :return: Base64 string (JPEG format)
    """
    buffered = BytesIO()
    pil_image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def extract_markdown_pages_with_glm_ocr(
    pdf_path: str, model: str = "glm-ocr", max_pages: int = 3
):
    """
    Convert PDF to markdown using Ollama GLM-OCR via LangChain.
    Yields each page's markdown as soon as it is extracted.
    Limits extraction to the first max_pages (default 3).
    """
    import pymupdf
    from langchain_ollama import ChatOllama
    from langchain_core.messages import HumanMessage

    doc = pymupdf.open(pdf_path)
    llm = ChatOllama(model=model, temperature=0)

    try:
        for i, page in enumerate(doc):
            # Limit to first max_pages pages to avoid long processing times on large PDFs (remove this limit if you want to process the entire document)
            if i >= max_pages:
                break
            # Render page to image (~144 dpi)
            mat = pymupdf.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_bytes = pix.tobytes("png")
            pil_image = Image.open(BytesIO(img_bytes)).convert("RGB")
            pil_image.save(TEMP_IMG_PATH, format="PNG")  # overwrite temp.png

            image_b64 = convert_to_base64(pil_image)

            image_part = {
                "type": "image_url",
                "image_url": f"data:image/jpeg;base64,{image_b64}",
            }
            text_part = {
                "type": "text",
                "text": (
                    "Extract all text from this document image as clean Markdown. "
                    "Preserve headings, lists, tables, and structure. "
                    "Output only the extracted text, no preamble or explanation."
                ),
            }
            content_parts = [image_part, text_part]

            msg = HumanMessage(content=content_parts)
            response = llm.invoke([msg])
            text = (response.content or "").strip()
            if text:
                yield f"## Page {i + 1}\n\n{text}"
    finally:
        doc.close()
