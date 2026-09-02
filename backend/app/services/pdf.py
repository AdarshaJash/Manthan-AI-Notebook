import io

import fitz
import pytesseract
from PIL import Image


class PDFProcessor:
    def extract_pages(self, path: str):
        doc = fitz.open(path)
        pages = []
        try:
            for i, page in enumerate(doc):
                text = page.get_text("text").strip()
                if not text:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    image = Image.open(io.BytesIO(pix.tobytes("png")))
                    text = pytesseract.image_to_string(image, lang="eng").strip()
                pages.append((i + 1, text))
        finally:
            doc.close()
        return pages

    def chunk_pages(self, pages, chunk_size=1400, overlap=180):
        out = []
        idx = 0
        for page_no, text in pages:
            text = " ".join(text.split())
            if not text:
                continue
            start = 0
            while start < len(text):
                end = min(len(text), start + chunk_size)
                out.append((page_no, idx, text[start:end]))
                idx += 1
                if end == len(text):
                    break
                start = max(0, end - overlap)
        return out
