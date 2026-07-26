from pydantic import BaseModel
from datetime import datetime

class IngestRequest(BaseModel):
    github_url: str


class IngestResponse(BaseModel):
    job_id: str
    repo_id: str
    status: str

class StatusResponse(BaseModel):
    job_id: str
    state: str          # PENDING, STARTED, SUCCESS, FAILURE
    result: dict | None = None

class ChatRequest(BaseModel):
    repo_id: str
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

class ReingestRequest(BaseModel):
    repo_id: str

class ThreadResponse(BaseModel):
    id: int
    thread_id: str
    title: str
    created_at: datetime
    last_message_at: datetime

    class Config:
        from_attributes = True


class CreateThreadRequest(BaseModel):
    repo_id: str

class AutoTitleRequest(BaseModel):
    message: str

class RenameThreadRequest(BaseModel):
    title: str
