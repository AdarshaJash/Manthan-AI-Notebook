import hashlib, hmac, os, secrets
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session as DBSession
from app.models import User, Session
from app.db.session import get_db

bearer = HTTPBearer(auto_error=False)
ITERATIONS = 310_000

def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"

def _verify_password(password: str, encoded: str) -> bool:
    try:
        alg, iterations, salt_hex, digest_hex = encoded.split("$")
        if alg != "pbkdf2_sha256": return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(candidate.hex(), digest_hex)
    except Exception:
        return False

def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def create_session(db: DBSession, user: User) -> str:
    token = secrets.token_urlsafe(48)
    db.add(Session(token_hash=_token_hash(token), user_id=user.id))
    db.commit()
    return token

def authenticate(db: DBSession, email: str, password: str):
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user or not _verify_password(password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password.")
    return user

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer), db: DBSession = Depends(get_db)):
    if not credentials:
        raise HTTPException(401, "Sign in required.")
    token = _token_hash(credentials.credentials)
    session = db.query(Session).filter(Session.token_hash == token).first()
    if not session:
        raise HTTPException(401, "Your session has expired. Please sign in again.")
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, "User account not found.")
    return user
