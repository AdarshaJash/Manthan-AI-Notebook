import time

from google import genai
from google.genai import types
from google.genai.errors import ClientError

from app.core.config import get_settings


class GeminiService:
    def __init__(self):
        settings = get_settings()
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.settings = settings

    def _embed_request(self, contents, task_type):
        last_error = None
        for attempt in range(5):
            try:
                return self.client.models.embed_content(
                    model=self.settings.gemini_embed_model,
                    contents=contents,
                    config=types.EmbedContentConfig(task_type=task_type),
                )
            except ClientError as exc:
                last_error = exc
                if getattr(exc, "status_code", None) != 429 or attempt == 4:
                    raise
                time.sleep(min(2 ** attempt, 16))
        raise last_error

    def embed(self, text: str):
        response = self._embed_request(text, "QUESTION_ANSWERING")
        return response.embeddings[0].values

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = []
        # One request per batch instead of one request per chunk.
        batch_size = max(1, min(self.settings.embedding_batch_size, 32))
        for start in range(0, len(texts), batch_size):
            batch = texts[start:start + batch_size]
            response = self._embed_request(batch, "RETRIEVAL_DOCUMENT")
            values = [item.values for item in response.embeddings]
            if len(values) != len(batch):
                raise RuntimeError(
                    f"Gemini returned {len(values)} embeddings for {len(batch)} chunks."
                )
            embeddings.extend(values)
        return embeddings

    def answer(self, question, contexts, history, learner=None):
        context = "\n\n".join(f"[Page {p}] {t}" for p, t, _ in contexts)
        hist = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in history[-10:])
        learner = learner or {}
        learner_name = learner.get("name", "Student")
        learner_grade = learner.get("grade", "Student")
        prompt = f"""You are Manthan AI Notebook — a free educational AI mentor for students of any class or level.

Your job is to teach, explain, reason, evaluate, summarize, make notes, create study plans, and help the student learn from the uploaded document. Behave like a capable conversational AI tutor, not a rigid search box.

LEARNER PROFILE
- Learner name: {learner_name}
- Class / level: {learner_grade}
- Personalize difficulty and examples to this level when useful. Use the learner name sparingly and naturally; do not repeat it in every answer.

GROUNDING
- Use the supplied document context as the factual source for document-specific claims.
- Do not invent facts, page numbers, names, marks, dates, qualifications, or other details that are absent from the context.
- If a requested fact is not available, say that you cannot find it in the uploaded document.
- You may make clearly labeled inferences or assessments when the user asks for analysis, evaluation, recommendation, comparison, prioritization, or a score.
- For evaluations, judge only what is visible in the document and explain the basis. Do not pretend the assessment is an objective hiring/academic decision.
- If the user asks a general educational question and the document does not contain the answer, explain the concept from general knowledge and clearly label it as general knowledge rather than document-derived.

TEACHING STYLE
- Be conversational, warm, direct, and useful.
- Match the student's level when it is apparent; otherwise explain simply first, then add depth.
- Prefer headings, bullets, short paragraphs, examples, tables, and step-by-step explanations when helpful.
- When asked to summarize, give an actual summary rather than saying that a rubric or explicit instruction is missing.
- When asked to rate/evaluate something, provide a reasoned assessment. A CV, for example, can be rated out of 10 based on evidence in the CV, with strengths, concerns, and a practical verdict.
- When appropriate, end with one short follow-up suggestion such as a quiz, revision notes, or a simpler explanation.

PAGE REFERENCES
- Only cite pages represented in the supplied context.
- If the user asks about a specific page and that page is present, answer from that page.

Conversation:
{hist}

Document context:
{context}

Student's request: {question}

Answer as Manthan AI:"""
        response = self.client.models.generate_content(
            model=self.settings.gemini_chat_model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.35),
        )
        return response.text
