from fastapi import APIRouter, HTTPException, Depends
from celery.result import AsyncResult

from app.core.celery_app import celery_app
from app.ingestion.tasks import ingest_repo_task
from app.api.schemas import IngestRequest, IngestResponse, StatusResponse
from app.api.auth import get_current_user

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
def ingest(request: IngestRequest, current_user: str = Depends(get_current_user)):
    """
    Kicks off ingestion as a background Celery task and returns
    immediately with a job_id. Client polls /status/{job_id} to
    track progress instead of blocking on a slow clone+embed job
    inside an HTTP request.
    """
    task = ingest_repo_task.delay(request.github_url)
    return IngestResponse(job_id=task.id, status="queued")


@router.get("/status/{job_id}", response_model=StatusResponse)
def get_status(job_id: str, current_user: str = Depends(get_current_user)):
    """
    Polls Celery's result backend (Redis) for task state.
    AsyncResult doesn't error on unknown IDs -- it just reports
    PENDING -- so we can't distinguish "still queued" from "never
    existed" here. Acceptable tradeoff for a portfolio project;
    worth noting as a known limitation.
    """
    result = AsyncResult(job_id, app=celery_app)

    response_result = None
    if result.state == "SUCCESS":
        response_result = result.result
    elif result.state == "FAILURE":
        response_result = {"error": str(result.result)}

    return StatusResponse(job_id=job_id, state=result.state, result=response_result)
