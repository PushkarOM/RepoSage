from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str) -> str:
    """
    Issues a JWT with an expiry claim. subject is the username here --
    in a real multi-user system this would be a user ID.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """
    Returns the subject (username) if the token is valid, else None.
    Callers treat None as unauthorized -- keeps the FastAPI dependency
    that uses this thin and easy to read.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError:
        return None

def hash_password(plain_password: str) -> str:
    if len(plain_password.encode("utf-8")) > 72:
        raise ValueError("Password too long (max 72 bytes)")
    return pwd_context.hash(plain_password)
