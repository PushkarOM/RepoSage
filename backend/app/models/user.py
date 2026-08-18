from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    github_access_token = Column(String, nullable=True)
    refresh_token_hash = Column(String, nullable=True)
    # Correlates a User row to the ONE refresh JWT currently considered
    # valid. Not a secret itself (the JWT's HMAC signature is what proves
    # authenticity) -- just a fast, plain-string compare target so /refresh
    # can rotate atomically via a single `UPDATE ... WHERE refresh_token_jti
    # = :presented_jti` statement. See app/api/auth.py for why this replaced
    # the old "SELECT, bcrypt-verify, then UPDATE" flow.
    refresh_token_jti = Column(String, nullable=True)
