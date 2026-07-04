from pydantic import BaseModel


class IngestRequest(BaseModel):
    github_url: str


class IngestResponse(BaseModel):
    job_id: str
    status: str


class StatusResponse(BaseModel):
    job_id: str
    state: str          # PENDING, STARTED, SUCCESS, FAILURE
    result: dict | None = None
