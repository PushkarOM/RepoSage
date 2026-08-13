from datetime import datetime, timedelta, timezone
import uuid
import bcrypt
from jose import jwt, JWTError
from app.core.config import settings



def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(subject: str) -> str:
    """
    Issues a JWT with an expiry claim. subject is the username here --
    in a real multi-user system this would be a user ID.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """
    Returns the subject (username) if the token is valid AND was issued as
    an access token, else None. The `type` check rejects refresh tokens
    being replayed against access-token endpoints.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "access":
            return None
        return payload.get("sub")
    except JWTError:
        return None


def create_refresh_token(subject: str) -> tuple[str, str]:
    """
    Long-lived JWT used solely to mint new access tokens. Signed with a
    separate secret and carries `type: refresh` so the decoder can reject
    confusion attacks (a refresh token presented where an access token is
    expected, and vice versa).

    Also carries a `jti` (JWT ID) -- a random, non-secret correlation id.
    Returns (token, jti) so the caller can persist the jti on the User row
    as the single source of truth for "which refresh token is currently
    valid." See app/api/auth.py's /refresh for why rotation is keyed off
    this instead of a bcrypt hash comparison.
    """
    jti = uuid.uuid4().hex
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_refresh_expire_minutes)
    payload = {"sub": subject, "exp": expire, "type": "refresh", "jti": jti}
    token = jwt.encode(payload, settings.jwt_refresh_secret_key, algorithm=settings.jwt_algorithm)
    return token, jti


def decode_refresh_token(token: str) -> tuple[str, str] | None:
    """
    Returns (subject, jti) if the token is a valid, well-formed refresh
    token. Mirrors decode_access_token's `type` check. Does NOT by itself
    prove the token is still the "current" one for that user -- the caller
    still has to check jti against the User row (see /refresh).
    """
    try:
        payload = jwt.decode(token, settings.jwt_refresh_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "refresh":
            return None
        jti = payload.get("jti")
        sub = payload.get("sub")
        if not jti or not sub:
            return None
        return sub, jti
    except JWTError:
        return None

def hash_password(plain_password: str) -> str:
    if len(plain_password.encode("utf-8")) > 72:
        raise ValueError("Password too long (max 72 bytes)")
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------
# All keys + flags come from settings so dev (Secure=False) and prod
# (Secure=True via env) share the same code path. Starlette's
# `set_cookie` / `delete_cookie` accept these as kwargs.


def _base_cookie_kwargs() -> dict:
    """Settings that go on every Set-Cookie and Delete-Cookie."""
    return {
        "secure": settings.cookie_secure,
        "httponly": True,
        "samesite": settings.cookie_samesite,
        "path": settings.cookie_path,
        "domain": settings.cookie_domain,
    }


def access_cookie_settings() -> dict:
    """Settings for the access-token cookie (short TTL)."""
    return {
        **_base_cookie_kwargs(),
        "key": "reposage_token",
        "max_age": settings.jwt_expire_minutes * 60,
    }


def refresh_cookie_settings() -> dict:
    """Settings for the refresh-token cookie (long TTL)."""
    return {
        **_base_cookie_kwargs(),
        "key": "reposage_refresh",
        "max_age": settings.jwt_refresh_expire_minutes * 60,
    }


def clear_cookie_kwargs(key: str) -> dict:
    """Settings that delete a cookie (Max-Age=0). Key is passed in so the
    same helper handles both reposage_token and reposage_refresh."""
    return {**_base_cookie_kwargs(), "key": key}
