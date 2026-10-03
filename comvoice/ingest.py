import io
import re
import fitz
from docx import Document


def _clean(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pdf(file_bytes: bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []
    for idx, page in enumerate(doc):
        text = _clean(page.get_text("text"))
        pages.append({
            "page": idx + 1,
            "text": text,
            "source": "pdf"
        })
    return pages


def extract_docx(file_bytes: bytes):
    doc = Document(io.BytesIO(file_bytes))
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [{"page": 1, "text": _clean(text), "source": "docx"}]


def extract_txt(file_bytes: bytes):
    text = file_bytes.decode("utf-8", errors="replace")
    return [{"page": 1, "text": _clean(text), "source": "txt"}]


def extract_document(filename: str, file_bytes: bytes):
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext == "pdf":
        return extract_pdf(file_bytes)
    if ext == "docx":
        return extract_docx(file_bytes)
    if ext == "txt":
        return extract_txt(file_bytes)
    raise ValueError("Unsupported file type")
