from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    filename: str
    page_count: int
    status: str
    pinned: bool = False
    archived: bool = False
    created_at: datetime

class Source(BaseModel):
    page: int
    text: str
    score: float

class ChatRequest(BaseModel):
    document_id: UUID
    question: str = Field(min_length=1, max_length=8000)
    history: list[dict[str, str]] = []

class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
