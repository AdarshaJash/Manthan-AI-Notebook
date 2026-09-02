from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.core.config import get_settings
from app.db.session import Base, engine
from app.models import Document, Chunk, User, ChatMessage
from app.api.routes import router

settings = get_settings()
Base.metadata.create_all(bind=engine)
with engine.begin() as conn:
    conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS pinned BOOLEAN NOT NULL DEFAULT FALSE"))
    conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE"))
    conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS owner_id UUID"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_owner_id ON documents(owner_id)"))

app = FastAPI(title="MANTHAN API", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router, prefix="/api")
