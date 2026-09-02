import re
from sqlalchemy import text
from app.services.gemini import GeminiService

class Retriever:
    def __init__(self):
        self.ai = GeminiService()

    def _page_number(self, question: str):
        m = re.search(r"\bpage\s*(?:no\.?\s*)?(\d+)\b", question.lower())
        return int(m.group(1)) if m else None

    def search(self, db, document_id, question, k):
        page = self._page_number(question)
        if page is not None:
            rows = db.execute(text("""SELECT page_number, content, 1.0 AS score
                FROM chunks WHERE document_id=:doc AND page_number=:page
                ORDER BY chunk_index"""), {"doc": str(document_id), "page": page}).all()
            return [(r.page_number, r.content, float(r.score)) for r in rows[:max(k, 8)]]

        q = question.lower()
        broad = any(term in q for term in (
            "summarize the document", "summary of the document", "whole document",
            "entire document", "make notes", "create notes", "chapter", "table of contents"
        ))
        if broad:
            rows = db.execute(text("""SELECT page_number, content, 1.0 AS score
                FROM chunks WHERE document_id=:doc ORDER BY page_number, chunk_index LIMIT :k"""),
                {"doc": str(document_id), "k": min(max(k * 4, 24), 48)}).all()
            if rows:
                return [(r.page_number, r.content, float(r.score)) for r in rows]

        qvec = self.ai.embed(question)
        stmt = text("""SELECT page_number, content,
            1 - (embedding <=> CAST(:v AS vector)) AS score
            FROM chunks WHERE document_id=:doc
            ORDER BY embedding <=> CAST(:v AS vector) LIMIT :k""")
        rows = db.execute(stmt, {"v": str(qvec), "doc": str(document_id), "k": k}).all()
        return [(r.page_number, r.content, float(r.score)) for r in rows]
