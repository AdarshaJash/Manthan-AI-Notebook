import os
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_, text
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.db.session import get_db
from app.models import Chunk, Document, User, Session as AuthSession, ChatMessage
from app.schemas.document import ChatRequest, ChatResponse, DocumentOut
from app.schemas.auth import SignupRequest, LoginRequest, AuthResponse, UserOut
from app.services.auth import _hash_password, authenticate, create_session, get_current_user, _token_hash
from app.services.gemini import GeminiService
from app.services.pdf import PDFProcessor
from app.services.retrieval import Retriever

router = APIRouter()
settings = get_settings()
pdf = PDFProcessor()

@router.get("/health")
def health(): return {"status":"ok","service":"manthan-api"}

@router.post("/auth/signup", response_model=AuthResponse)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    email = req.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "An account with this email already exists.")
    user = User(name=req.name.strip(), email=email, password_hash=_hash_password(req.password), grade=req.grade.strip() or "Student")
    db.add(user); db.commit(); db.refresh(user)
    return {"token": create_session(db, user), "user": user}

@router.post("/auth/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate(db, req.email, req.password)
    return {"token": create_session(db, user), "user": user}

@router.post("/auth/logout")
def logout(current: User = Depends(get_current_user), db: Session = Depends(get_db), credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
    db.query(AuthSession).filter(AuthSession.token_hash == _token_hash(credentials.credentials)).delete(synchronize_session=False)
    db.commit()
    return {"ok": True}

@router.get("/auth/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)): return current

@router.patch("/auth/me", response_model=UserOut)
def update_me(name: str | None = None, grade: str | None = None, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if name is not None: current.name = name.strip()[:120] or current.name
    if grade is not None: current.grade = grade.strip()[:80] or "Student"
    db.commit(); db.refresh(current); return current

@router.get("/documents", response_model=list[DocumentOut])
def documents(current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Claim legacy documents created before accounts existed, once, for the first signed-in owner.
    legacy = db.query(Document).filter(Document.owner_id.is_(None)).all()
    for d in legacy: d.owner_id = current.id
    if legacy: db.commit()
    return db.query(Document).filter(Document.owner_id == current.id).order_by(Document.pinned.desc(), Document.created_at.desc()).all()

@router.patch("/documents/{document_id}", response_model=DocumentOut)
def update_document(document_id, pinned: bool | None = None, archived: bool | None = None, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id, Document.owner_id == current.id).first()
    if not doc: raise HTTPException(404, "Notebook not found.")
    if pinned is not None: doc.pinned = pinned
    if archived is not None: doc.archived = archived
    db.commit(); db.refresh(doc); return doc

@router.delete("/documents/{document_id}")
def delete_document(document_id, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id, Document.owner_id == current.id).first()
    if not doc: raise HTTPException(404, "Notebook not found.")
    path = doc.stored_path
    db.query(ChatMessage).filter(ChatMessage.document_id == doc.id).delete(synchronize_session=False)
    db.query(Chunk).filter(Chunk.document_id == doc.id).delete(synchronize_session=False)
    db.delete(doc); db.commit()
    if path:
        try: os.remove(path)
        except OSError: pass
    return {"ok": True}

@router.get("/documents/{document_id}/messages")
def messages(document_id, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id, Document.owner_id == current.id).first()
    if not doc: raise HTTPException(404, "Notebook not found.")
    rows = db.query(ChatMessage).filter(ChatMessage.document_id == doc.id, ChatMessage.user_id == current.id).order_by(ChatMessage.created_at.asc()).all()
    return [{"role": r.role, "content": r.content, "created_at": r.created_at} for r in rows]

@router.delete("/documents/{document_id}/messages")
def clear_messages(document_id, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id, Document.owner_id == current.id).first()
    if not doc: raise HTTPException(404, "Notebook not found.")
    db.query(ChatMessage).filter(ChatMessage.document_id == doc.id, ChatMessage.user_id == current.id).delete(synchronize_session=False)
    db.commit(); return {"ok": True}

@router.post("/documents/upload", response_model=DocumentOut)
async def upload(file: UploadFile = File(...), current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if file.content_type != "application/pdf": raise HTTPException(400, "Only PDF files are supported.")
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024: raise HTTPException(413, "File too large.")
    doc = Document(filename=file.filename or "document.pdf", stored_path="", owner_id=current.id, status="processing")
    db.add(doc); db.flush()
    path = f"/app/storage/uploads/{doc.id}.pdf"; os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path,"wb") as output: output.write(data)
        doc.stored_path = path
        pages = pdf.extract_pages(path); doc.page_count = len(pages); chunks = pdf.chunk_pages(pages)
        if not chunks:
            doc.status="failed"; db.commit(); raise HTTPException(422,"No readable text was found in this PDF. OCR could not extract text.")
        ai=GeminiService(); embeddings=ai.embed_documents([content for _,_,content in chunks])
        for (page,idx,content),embedding in zip(chunks,embeddings):
            db.add(Chunk(document_id=doc.id,page_number=page,chunk_index=idx,content=content,embedding=embedding))
        doc.status="ready"; db.commit(); db.refresh(doc); return doc
    except HTTPException: raise
    except Exception:
        db.rollback()
        try: db.delete(doc); db.commit()
        except Exception: db.rollback()
        raise

@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == req.document_id, Document.owner_id == current.id).first()
    if not doc or doc.status != "ready": raise HTTPException(404,"Notebook not found or not ready.")
    contexts = Retriever().search(db, doc.id, req.question, settings.retrieval_top_k)
    if not contexts: raise HTTPException(404,"I could not find relevant information in this document.")
    history = req.history
    if not history:
        rows=db.query(ChatMessage).filter(ChatMessage.document_id==doc.id,ChatMessage.user_id==current.id).order_by(ChatMessage.created_at.asc()).limit(20).all()
        history=[{"role":r.role,"content":r.content} for r in rows]
    answer=GeminiService().answer(req.question,contexts,history,{"name":current.name,"grade":current.grade})
    db.add(ChatMessage(document_id=doc.id,user_id=current.id,role="user",content=req.question.strip()))
    db.add(ChatMessage(document_id=doc.id,user_id=current.id,role="assistant",content=answer))
    db.commit()
    return {"answer":answer,"sources":[{"page":p,"text":t[:280],"score":s} for p,t,s in contexts]}
