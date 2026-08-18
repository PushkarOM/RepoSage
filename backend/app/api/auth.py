from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import update
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import (
    verify_password,
    hash_password,
    create_access_token,
    decode_access_token,
    create_refresh_token,
    decode_refresh_token,
    access_cookie_settings,
    refresh_cookie_settings,
    clear_cookie_kwargs,
)
from app.models.user import User

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login", auto_error=False)


class RegisterRequest(BaseModel):
    username: str
    password: str


# ---------------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------------
# Defined up here (before any route decorator references them) because
# Python evaluates `Depends(get_current_user_from_cookie)` at module-load
# time. If the function lived below the @router.post("/logout") call,
# the import of routes.py -- which transitively imports auth.py via
# rate_limit -- would explode with NameError on a cold start.


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """Legacy Authorization-header path. No longer used by any route
    after the cookie migration -- kept around for any future callers
    that explicitly want to authenticate via header (e.g. service-to-
    service, third-party integrations)."""
    username = decode_access_token(token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username


def get_current_user_from_cookie(request: Request) -> str:
    """
    Authorization via the httpOnly `reposage_token` cookie. Mirrors the
    OAuth2 dependency's behavior but reads the cookie instead of the
    Authorization header. Used by every authenticated route after the
    cookie migration lands.

    CSRF defense is `SameSite=Lax` (set by `access_cookie_settings`).
    Browsers don't send Lax cookies on cross-origin POST/PUT/DELETE --
    only on top-level navigations and safe methods. Our entire API is
    JSON over POST/GET from the same origin (Vite proxy in dev, single
    deploy in prod), so no separate CSRF token is needed.
    """
    token = request.cookies.get("reposage_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    username = decode_access_token(token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return username


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

    # Issue both tokens. The jti on the refresh JWT is persisted on the
    # User row -- it's the single source of truth for "which refresh
    # token is currently valid," and is what /refresh's atomic UPDATE
    # compares against (see /refresh below for the full rationale).
    access = create_access_token(subject=user.username)
    refresh, jti = create_refresh_token(subject=user.username)
    user.refresh_token_jti = jti
    db.commit()

    # Tokens ride in httpOnly cookies (XSS-immune). Body is a thin ack
    # so callers know the login succeeded without exposing the JWTs.
    response = JSONResponse({"message": "ok", "username": user.username})
    response.set_cookie(value=access, **access_cookie_settings())
    response.set_cookie(value=refresh, **refresh_cookie_settings())
    return response


@router.post("/refresh")
def refresh(request: Request, db: Session = Depends(get_db)):
    """
    Trades a valid refresh cookie for a new access + refresh pair. The
    refresh token rotates on every call so a leaked token can only be
    redeemed once: the legitimate user's next refresh attempt fails,
    surfacing the compromise.

    Returns 401 on every failure mode (invalid signature, expired, wrong
    type claim, already-rotated/revoked). The frontend treats 401 here as
    "redirect to /login."

    Race-safety: rotation is a single atomic `UPDATE ... WHERE
    refresh_token_jti = :presented_jti`. Of N concurrent requests
    presenting the same starting cookie, exactly one UPDATE matches the
    row and commits; the rest see rowcount=0 and 401 immediately. This
    replaces the old SELECT-then-bcrypt-verify-then-UPDATE flow, which
    had a real gap between the read and the write -- two concurrent
    callers could both verify, both overwrite, and the loser's cookie
    would fail later with no error at issue time. See model/user.py for
    why jti (not a bcrypt hash) is the column of choice here.
    """
    refresh_token = request.cookies.get("reposage_refresh")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh cookie",
        )

    decoded = decode_refresh_token(refresh_token)
    if decoded is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    username, presented_jti = decoded

    new_access = create_access_token(username)
    new_refresh, new_jti = create_refresh_token(username)

    # Atomic compare-and-swap: only rotate if `presented_jti` is STILL the
    # jti on the row right now. This one UPDATE statement is where the
    # race gets closed. If another request already rotated this user's
    # token (concurrently, or just moments ago), rowcount is 0 and we
    # correctly 401 instead of quietly handing out a cookie that doesn't
    # match the DB.
    result = db.execute(
        update(User)
        .where(User.username == username, User.refresh_token_jti == presented_jti)
        .values(refresh_token_jti=new_jti)
    )
    db.commit()

    if result.rowcount != 1:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token already used or revoked",
        )

    response = JSONResponse({"message": "ok"})
    response.set_cookie(value=new_access, **access_cookie_settings())
    response.set_cookie(value=new_refresh, **refresh_cookie_settings())
    return response


@router.post("/logout")
def logout(
    request: Request,
    db: Session = Depends(get_db),
    username: str = Depends(get_current_user_from_cookie),
):
    """
    Logs the user out across every layer:
      1. Clears refresh_token_jti on the User row so the JWT is
         unredeemable even if a stale cookie is replayed.
      2. Returns a response that deletes both auth cookies (Max-Age=0).
    The access-token JWT itself remains valid until its exp claim --
    that's intrinsic to stateless JWTs -- but can't be refreshed from
    this device anymore.
    """
    user = db.query(User).filter(User.username == username).first()
    if user:
        user.refresh_token_jti = None
        db.commit()

    response = JSONResponse({"message": "logged out"})
    response.delete_cookie(**clear_cookie_kwargs("reposage_token"))
    response.delete_cookie(**clear_cookie_kwargs("reposage_refresh"))
    return response
