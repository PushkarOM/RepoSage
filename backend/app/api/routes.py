import uuid
import secrets
import json
import asyncio
import httpx

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session


from app.models.chat_threads import ChatThread

from app.core.database import get_db
from app.core.rate_limit import rate_limit
from app.core.config import settings

from app.ingestion.tasks import ingest_repo_task
from app.ingestion.utils import derive_repo_id

from app.models.ingested_repo import IngestedRepo
from app.models.user import User

from app.agent.agent import chat as agent_chat
from app.agent.agent import chat_stream as agent_chat_stream
from app.agent.agent import generate_title, get_history as agent_get_history

from app.api.auth import get_current_user_from_cookie
from app.api.schemas import IngestRequest, IngestResponse, StatusResponse, RepoListResponse, ChatRequest, ChatResponse, ReingestRequest, ThreadResponse, CreateThreadRequest, AutoTitleRequest, RenameThreadRequest



router = APIRouter()

# SSE stream settles into one of these states and closes. Used by the
# streaming generator so a client connecting just after the task finishes
# still gets the terminal event rather than a half-formed payload.
_TERMINAL_INGEST_STATES = {"success", "failed"}
# If no event for this many seconds, treat the worker as dead. The
# pipeline publishes a heartbeat every 30s (see pipeline._heartbeat_loop),
# so 90s of silence is three missed heartbeats -- not a normal pause.
_SSE_WATCHDOG_SECONDS = 90


def _sse(payload: dict) -> str:
    """Format a dict as one SSE frame. Each frame is "data: <json>\\n\\n"."""
    return f"data: {json.dumps(payload)}\n\n"


@router.post("/ingest", response_model=IngestResponse)
def ingest(
    request: IngestRequest,
    current_user: str = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
    _rl: None = Depends(rate_limit("ingest", "rate_limit_ingest_per_day", 86400)),
):

    """
    Kicks off ingestion as a background Celery task and returns
    immediately with a job_id, and records a row so the user can see
    this repo in their dashboard and resume chatting with it later
    without re-ingesting.
    """
    
    user = db.query(User).filter(User.username == current_user).first()
    task = ingest_repo_task.delay(request.github_url, user.id)
    repo_id = derive_repo_id(request.github_url)

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
    current_user: str = Depends(get_current_user_from_cookie), 
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

    task = ingest_repo_task.delay(existing.github_url, user.id)
    existing.job_id = task.id
    existing.status = "queued"
    db.commit()

    return IngestResponse(job_id=task.id, repo_id=request.repo_id, status="queued")


@router.get("/repos", response_model=list[RepoListResponse])
def list_repos(
    current_user: str = Depends(get_current_user_from_cookie), 
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
    current_user: str = Depends(get_current_user_from_cookie), 
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
    current_user: str = Depends(get_current_user_from_cookie), 
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
    current_user: str = Depends(get_current_user_from_cookie), 
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
    current_user: str = Depends(get_current_user_from_cookie), 
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
    current_user: str = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    """
    Reads from the `IngestedRepo` row (DB-as-source-of-truth) rather than
    Celery's result backend. The task writes "queued" -> "running" ->
    "success"/"failed" to the DB on every transition, so polling the DB
    gives the same info as Celery's AsyncResult -- without depending on
    the worker's bookkeeping being correct (e.g. after a worker crash
    leaves the row stuck at "queued").

    Returns state.upper() to preserve the existing StatusResponse contract
    (PENDING/STARTED/SUCCESS/FAILURE), even though the DB stores lowercase.
    """
    repo = (
        db.query(IngestedRepo)
        .filter(IngestedRepo.job_id == job_id)
        .first()
    )
    if not repo:
        return StatusResponse(job_id=job_id, state="UNKNOWN", result=None)
    return StatusResponse(job_id=job_id, state=repo.status.upper(), result=None)


@router.get("/ingest/stream/{job_id}")
async def stream_ingest(
    job_id: str,
    request: Request,
    username: str = Depends(get_current_user_from_cookie),
    db: Session = Depends(get_db),
):
    """
    Server-Sent Events stream for one ingest job. Subscribes to Redis
    pub/sub for live status updates, falling back to the DB on connect
    so a client joining mid-task gets the current state immediately.

    Authorization via the httpOnly `reposage_token` cookie (set on
    `/login`). The frontend opens the stream with `EventSource(url,
    { withCredentials: true })`, which is the same-origin default when
    the Vite proxy routes `/api/*` to the backend.

    Why a watchdog: events are only published on terminal state and on
    30s heartbeats. If neither arrives for 90s, the worker is presumed
    dead -- the stream emits a final "unknown" event with the DB state
    and closes. The frontend then falls back to bounded polling.
    """
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    repo = (
        db.query(IngestedRepo)
        .filter(IngestedRepo.job_id == job_id, IngestedRepo.user_id == user.id)
        .first()
    )
    if not repo:
        raise HTTPException(status_code=404, detail="Job not found")

    # Authorize once, then hand off to the streaming generator. The
    # generator must close its pubsub in `finally` -- leaked pubsubs
    # accumulate in Redis and will eventually exhaust the connection pool.
    async_redis = request.app.state.redis
    pubsub = async_redis.pubsub()

    async def event_stream():
        await pubsub.subscribe(f"ingest:{job_id}")
        try:
            # Initial snapshot -- covers "client connected just after the
            # task finished" and "client connected mid-task" alike.
            db.refresh(repo)
            yield _sse({"job_id": job_id, "state": repo.status})
            if repo.status in _TERMINAL_INGEST_STATES:
                return

            loop = asyncio.get_event_loop()
            last_event_at = loop.time()

            async for message in pubsub.listen():
                if await request.is_disconnected():
                    break
                if message.get("type") != "message":
                    continue
                last_event_at = loop.time()
                try:
                    payload = json.loads(message["data"])
                except (TypeError, ValueError):
                    continue
                yield _sse(payload)
                if payload.get("state") in _TERMINAL_INGEST_STATES:
                    break
                # Watchdog: if no terminal event AND no heartbeat for 90s,
                # the worker is presumed dead. Read the DB one last time
                # and let the frontend decide what to do (retry CTA, error,
                # etc.).
                if loop.time() - last_event_at > _SSE_WATCHDOG_SECONDS:
                    db.refresh(repo)
                    yield _sse({
                        "job_id": job_id,
                        "state": repo.status or "unknown",
                        "detail": "watchdog: no events for 90s",
                    })
                    return
        finally:
            try:
                await pubsub.unsubscribe(f"ingest:{job_id}")
            finally:
                await pubsub.aclose()

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest, 
    current_user: str = Depends(get_current_user_from_cookie), 
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
    user = db.query(User).filter(User.username == current_user).first()
    reply = await agent_chat(contextualized_message, thread_id=thread_id, github_token=user.github_access_token)

    db.query(ChatThread).filter(ChatThread.thread_id == raw_thread_id).update({"last_message_at": func.now()})
    db.commit()

    return ChatResponse(thread_id=raw_thread_id, reply=reply)



@router.post("/chat/stream")
async def chat_stream_endpoint(
    request: ChatRequest, 
    current_user: str = Depends(get_current_user_from_cookie), 
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
    user = db.query(User).filter(User.username == current_user).first()
    return StreamingResponse(
        agent_chat_stream(contextualized_message, thread_id=thread_id, github_token=user.github_access_token),
        media_type="text/plain",
    )

@router.get("/threads/{thread_id}/messages")
async def get_thread_messages(thread_id: str, current_user: str = Depends(get_current_user_from_cookie)):
    scoped_thread_id = f"{current_user}:{thread_id}"
    return await agent_get_history(scoped_thread_id)

@router.get("/auth/github/login")
async def github_login(
    request: Request,
    username: str = Depends(get_current_user_from_cookie),
):
    """
    Starts the GitHub account-linking flow. Reached via a real browser
    navigation (window.location.href or a clicked link) -- not fetch()/AJAX,
    since it responds with a redirect to a different origin (github.com),
    which fetch() restricts. Testing this via Swagger's "Try it out"
    (which uses fetch() internally) fails for exactly that reason.

    The `reposage_token` httpOnly cookie rides on this top-level
    navigation (SameSite=Lax includes top-level navigations in its
    cookie-attach policy). No Authorization header and no query-string
    token needed.
    """
    state = secrets.token_urlsafe(32)
    await request.app.state.redis.set(f"oauth_state:{state}", username, ex=600)

    github_url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={settings.gh_client_id}"
        f"&redirect_uri={settings.gh_redirect_uri}"
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
                "client_id": settings.gh_client_id,
                "client_secret": settings.gh_client_secret,
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

@router.get("/auth/github/status")
def github_status(current_user: str = Depends(get_current_user_from_cookie), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == current_user).first()
    return {"connected": bool(user.github_access_token)}
