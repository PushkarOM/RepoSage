from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.core.database import Base


class IngestedRepo(Base):
    __tablename__ = "ingested_repos"
    __table_args__ = (UniqueConstraint("user_id", "repo_id", name="uq_user_repo"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    github_url = Column(String, nullable=False)
    repo_id = Column(String, nullable=False, index=True)
    job_id = Column(String, nullable=False)  # latest run's job_id -- no longer globally unique
    status = Column(String, nullable=False, default="queued")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
