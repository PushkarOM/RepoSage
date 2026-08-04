from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
import bcrypt
import hashlib

from app.core.database import get_db
from app.core.security import (
    verify_password,
    hash_password,
    create_access_token,
    decode_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from app.models.user import User

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


def _hash_refresh_token(token: str) -> str:
    """
    bcrypt refuses inputs > 72 bytes, but a JWT-encoded refresh token
    routinely runs 200-400 bytes. Hash the JWT with SHA-256 first to
    reduce it to a fixed 64-byte digest (well within bcrypt's limit),
    then bcrypt that. This preserves the full entropy of the original
    token while staying inside bcrypt's constraints.
    """
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return bcrypt.hashpw(digest, bcrypt.gensalt()).decode("utf-8")


def _verify_refresh_token(token: str, stored_hash: str) -> bool:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    try:
        return bcrypt.checkpw(digest, stored_hash.encode("utf-8"))
    except ValueError:
        return False


class RegisterRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == request.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")

    user = User(username=request.username, hashed_password=hash_password(request.password))
    db.add(user)
    db.commit()
    return {"message": "User created"}


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Issue both tokens, hash and persist the refresh token. The hash is
    # what survives a DB compromise -- the raw token never lands on disk.
    access = create_access_token(subject=user.username)
    refresh = create_refresh_token(subject=user.username)
    user.refresh_token_hash = _hash_refresh_token(refresh)
    db.commit()

    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
    }


@router.post("/refresh")
def refresh(request: RefreshRequest, db: Session = Depends(get_db)):
    """
    Trades a valid refresh token for a new access + refresh pair. The
    refresh token rotates on every call so a leaked token can only be
    redeemed once: the legitimate user's next refresh attempt fails,
    surfacing the compromise.

    Returns 401 on every failure mode (invalid signature, expired, wrong
    type claim, revoked, hash mismatch). The frontend treats 401 here as
    "redirect to /login."
    """
    username = decode_refresh_token(request.refresh_token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = db.query(User).filter(User.username == username).first()
    if not user or not user.refresh_token_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")

    if not _verify_refresh_token(request.refresh_token, user.refresh_token_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    # Rotate: a new refresh token supersedes the old one. The old hash is
    # overwritten -- replay attempts against it will now fail.
    new_access = create_access_token(username)
    new_refresh = create_refresh_token(username)
    user.refresh_token_hash = _hash_refresh_token(new_refresh)
    db.commit()

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    username = decode_access_token(token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username
