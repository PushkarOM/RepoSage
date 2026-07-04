from fastapi import APIRouter, HTTPException, Depends
from celery.result import AsyncResult

from app.core.celery_app import celery_app
from app.ingestion.tasks import ingest_repo_task
from app.api.schemas import IngestRequest, IngestResponse, StatusResponse
from app.api.auth import get_current_user

from app.agent.agent import chat as agent_chat
from app.api.schemas import ChatRequest, ChatResponse

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

@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest, current_user: str = Depends(get_current_user)):
    """
    Scopes conversation memory by both the requesting user and the
    thread_id/job_id -- without the username prefix, two different
    users chatting about the same job_id would silently share the
    same conversation history, which is a real bug waiting to happen
    the moment this has more than one user.
    """
    raw_thread_id = request.thread_id or request.job_id
    thread_id = f"{current_user}:{raw_thread_id}"

    # Inject job_id into the message so the agent knows which repo's
    # tools to call without the user needing to mention it every turn.
    contextualized_message = f"[Repository job_id: {request.job_id}]\n{request.message}"

    reply = agent_chat(contextualized_message, thread_id=thread_id)
    return ChatResponse(thread_id=raw_thread_id, reply=reply)
