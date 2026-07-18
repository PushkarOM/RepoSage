from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from celery.result import AsyncResult

from app.core.celery_app import celery_app
from app.ingestion.tasks import ingest_repo_task
from app.api.schemas import IngestRequest, IngestResponse, StatusResponse
from app.api.auth import get_current_user

from app.agent.agent import chat as agent_chat
from app.agent.agent import chat_stream as agent_chat_stream
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
async def chat_endpoint(request: ChatRequest, current_user: str = Depends(get_current_user)):
    """
    Non-streaming chat endpoint -- waits for the full agent response,
    then returns it as one JSON payload. Kept alongside /chat/stream
    deliberately, not leftover dead code: useful for tooling, scripted
    tests, and the retrieval-quality eval harness (see PROJECT_PLAN.md
    Phase 4), where a plain request/response shape is easier to work
    with than reassembling a stream.

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

    reply = await agent_chat(contextualized_message, thread_id=thread_id)
    return ChatResponse(thread_id=raw_thread_id, reply=reply)


@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest, current_user: str = Depends(get_current_user)):
    """
    Streaming counterpart to /chat -- returns a text/plain response whose
    body is delivered incrementally as the agent generates it, rather
    than one payload after the full response is ready. Powers the
    frontend's live-typing chat UI.

    No response_model here (unlike /chat): StreamingResponse's body is
    an async generator of raw text chunks, not a single Pydantic-
    serializable object, so response_model validation doesn't apply.
    Same thread_id scoping and job_id injection as /chat, since both
    endpoints drive the same underlying agent and must produce
    consistent conversation history regardless of which one is used.
    """
    raw_thread_id = request.thread_id or request.job_id
    thread_id = f"{current_user}:{raw_thread_id}"
    contextualized_message = f"[Repository job_id: {request.job_id}]\n{request.message}"

    return StreamingResponse(
        agent_chat_stream(contextualized_message, thread_id=thread_id),
        media_type="text/plain",
    )

