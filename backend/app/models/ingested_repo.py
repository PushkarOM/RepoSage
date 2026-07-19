from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base


class IngestedRepo(Base):
    __tablename__ = "ingested_repos"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    github_url = Column(String, nullable=False)
    repo_id = Column(String, nullable=False)  # e.g. "owner/name", from derive_repo_id
    job_id = Column(String, nullable=False, unique=True, index=True)
    status = Column(String, nullable=False, default="queued")  # queued/running/success/failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    