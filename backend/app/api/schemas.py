from pydantic import BaseModel
from datetime import datetime

class IngestRequest(BaseModel):
    github_url: str


class IngestResponse(BaseModel):
    job_id: str
    status: str


class StatusResponse(BaseModel):
    job_id: str
    state: str          # PENDING, STARTED, SUCCESS, FAILURE
    result: dict | None = None

class ChatRequest(BaseModel):
    job_id: str
    message: str
    thread_id: str | None = None


class ChatResponse(BaseModel):
    thread_id: str
    reply: str

class RepoListResponse(BaseModel):
    id: int
    github_url: str
    repo_id: str
    job_id: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True 