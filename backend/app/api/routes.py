import uuid
import secrets
import httpx

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse, RedirectResponse
from celery.result import AsyncResult
from sqlalchemy import func
from sqlalchemy.orm import Session


from app.models.chat_threads import ChatThread

from app.core.database import get_db
from app.core.celery_app import celery_app
from app.core.rate_limit import rate_limit
from app.core.config import settings
from app.core.security import decode_access_token

from app.ingestion.tasks import ingest_repo_task
from app.ingestion.utils import derive_repo_id

from app.models.ingested_repo import IngestedRepo
from app.models.user import User

from app.agent.agent import chat as agent_chat
from app.agent.agent import chat_stream as agent_chat_stream
from app.agent.agent import generate_title, get_history as agent_get_history

from app.api.auth import get_current_user
from app.api.schemas import IngestRequest, IngestResponse, StatusResponse, RepoListResponse, ChatRequest, ChatResponse, ReingestRequest, ThreadResponse, CreateThreadRequest, AutoTitleRequest, RenameThreadRequest



router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
def ingest(
    request: IngestRequest,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
    _rl: None = Depends(rate_limit("ingest", "rate_limit_ingest_per_day", 86400)),
):

    """
    Kicks off ingestion as a background Celery task and returns
    immediately with a job_id, and records a row so the user can see
    this repo in their dashboard and resume chatting with it later
    without re-ingesting.
    """
    task = ingest_repo_task.delay(request.github_url)
    repo_id = derive_repo_id(request.github_url)
    user = db.query(User).filter(User.username == current_user).first()

    existing = (
        db.query(IngestedRepo)
        .filter(IngestedRepo.user_id == user.id, IngestedRepo.repo_id == repo_id)
        .first()
    )

    if existing and existing.status == "queued":
            raise HTTPException(status_code=409, detail="Ingestion already in progress for this repo")
        
    if existing:
        existing.job_id = task.id
        existing.status = "queued"
        existing.github_url = request.github_url
    else:
        db.add(IngestedRepo(
            user_id=user.id, github_url=request.github_url,
            repo_id=repo_id, job_id=task.id, status="queued",
        ))

    db.commit()
    return IngestResponse(job_id=task.id, repo_id=repo_id, status="queued")

@router.post("/repos/reingest", response_model=IngestResponse)
def reingest(
    request: ReingestRequest, 
    current_user: str = Depends(get_current_user), 
    db: Session = Depends(get_db),
    _rl: None = Depends(rate_limit("ingest", "rate_limit_ingest_per_day", 86400)),
):
    """
    Re-triggers ingestion for a repo already tracked for this user, reusing
    its stored github_url. repo_id comes via the request body rather than
    the URL path, since it contains a "/" and FastAPI's path-parameter
    matching gets ambiguous with a :path-type param followed by more
    segments (here, the trailing action isn't even needed -- but this
    keeps the pattern consistent and avoids the issue entirely).
    """

    
    user = db.query(User).filter(User.username == current_user).first()
    existing = (
        db.query(IngestedRepo)
        .filter(IngestedRepo.user_id == user.id, IngestedRepo.repo_id == request.repo_id)
        .first()
    )

    if existing and existing.status == "queued":
            raise HTTPException(status_code=409, detail="Ingestion already in progress for this repo")
        
    if not existing:
        raise HTTPException(status_code=404, detail="Repo not found")

    task = ingest_repo_task.delay(existing.github_url)
    existing.job_id = task.id
    existing.status = "queued"
    db.commit()

    return IngestResponse(job_id=task.id, repo_id=request.repo_id, status="queued")


@router.get("/repos", response_model=list[RepoListResponse])
def list_repos(
    current_user: str = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == current_user).first()
    repos = (
        db.query(IngestedRepo)
        .filter(IngestedRepo.user_id == user.id)
        .order_by(IngestedRepo.created_at.desc())
        .all()
    )
    return repos


@router.get("/repos/{repo_owner}/{repo_name}/threads", response_model=list[ThreadResponse])
def list_threads(
    repo_owner: str, repo_name: str, 
    current_user: str = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    repo_id = f"{repo_owner}/{repo_name}"
    user = db.query(User).filter(User.username == current_user).first()
    return (
        db.query(ChatThread)
        .filter(ChatThread.user_id == user.id, ChatThread.repo_id == repo_id)
        .order_by(ChatThread.last_message_at.desc())
        .all()
    )


@router.post("/threads", response_model=ThreadResponse)
def create_thread(
    request: CreateThreadRequest, 
    current_user: str = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == current_user).first()
    thread = ChatThread(user_id=user.id, repo_id=request.repo_id, thread_id=str(uuid.uuid4()))
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread

@router.post("/threads/{thread_id}/auto-title")
async def auto_title_thread(
    thread_id: str, request: AutoTitleRequest, 
    current_user: str = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    thread = db.query(ChatThread).filter(ChatThread.thread_id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread.title = await generate_title(request.message)
    db.commit()
    return {"title": thread.title}


@router.patch("/threads/{thread_id}")
def rename_thread(
    thread_id: str, request: RenameThreadRequest, 
    current_user: str = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    thread = db.query(ChatThread).filter(ChatThread.thread_id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread.title = request.title
    db.commit()
    return {"title": thread.title}

@router.get("/status/{job_id}", response_model=StatusResponse)
def get_status(
    job_id: str, 
    current_user: str = Depends(get_current_user)
):
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
async def chat_endpoint(
    request: ChatRequest, 
    current_user: str = Depends(get_current_user), 
    db: Session = Depends(get_db),
    _rl: None = Depends(rate_limit("chat", "rate_limit_chat_per_day", 86400)),
):
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
     
    raw_thread_id = request.thread_id or request.repo_id
    thread_id = f"{current_user}:{raw_thread_id}"
    contextualized_message = f"[Repository repo_id: {request.repo_id}]\n{request.message}"
    reply = await agent_chat(contextualized_message, thread_id=thread_id)

    db.query(ChatThread).filter(ChatThread.thread_id == raw_thread_id).update({"last_message_at": func.now()})
    db.commit()

    return ChatResponse(thread_id=raw_thread_id, reply=reply)



@router.post("/chat/stream")
async def chat_stream_endpoint(
    request: ChatRequest, 
    current_user: str = Depends(get_current_user), 
    db: Session = Depends(get_db),
    _rl: None = Depends(rate_limit("chat", "rate_limit_chat_per_day", 86400)),
):
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
    raw_thread_id = request.thread_id or request.repo_id
    thread_id = f"{current_user}:{raw_thread_id}"

    contextualized_message = f"[Repository repo_id: {request.repo_id}]\n{request.message}"
    return StreamingResponse(
        agent_chat_stream(contextualized_message, thread_id=thread_id),
        media_type="text/plain",
    )

@router.get("/threads/{thread_id}/messages")
async def get_thread_messages(thread_id: str, current_user: str = Depends(get_current_user)):
    scoped_thread_id = f"{current_user}:{thread_id}"
    return await agent_get_history(scoped_thread_id)

@router.get("/auth/github/login")
async def github_login(request: Request, token: str):
    """
    Starts the GitHub account-linking flow. Reached via a real browser
    navigation (window.location.href or a clicked link) -- not fetch()/AJAX,
    since it responds with a redirect to a different origin (github.com),
    which fetch() restricts. Testing this via Swagger's "Try it out"
    (which uses fetch() internally) fails for exactly that reason.

    Because it's a full navigation, no Authorization header can be
    attached -- the JWT travels as a query parameter instead, decoded
    manually here rather than via the usual Depends(get_current_user).
    """
    username = decode_access_token(token)
    if username is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    state = secrets.token_urlsafe(32)
    await request.app.state.redis.set(f"oauth_state:{state}", username, ex=600)

    github_url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={settings.github_client_id}"
        f"&redirect_uri={settings.github_redirect_uri}"
        f"&scope=repo"
        f"&state={state}"
    )
    return RedirectResponse(github_url)

@router.get("/auth/github/callback")
async def github_callback(request: Request, code: str, state: str, db: Session = Depends(get_db)):
    stored_username = await request.app.state.redis.get(f"oauth_state:{state}")
    if not stored_username:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    await request.app.state.redis.delete(f"oauth_state:{state}")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="GitHub token exchange failed")

    user = db.query(User).filter(User.username == stored_username).first()
    user.github_access_token = access_token
    db.commit()

    return RedirectResponse(f"{settings.frontend_base_url}/dashboard?github_connected=true")
