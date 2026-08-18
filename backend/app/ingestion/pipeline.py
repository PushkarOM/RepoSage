import threading
from langchain_core.documents import Document
from app.ingestion.structure import build_directory_tree
from app.ingestion.clone import clone_repo
from app.ingestion.chunker import load_and_chunk
from app.ingestion.vectorstore import store_documents
from app.ingestion.utils import derive_repo_id


_HEARTBEAT_INTERVAL_SECONDS = 30


def _heartbeat_loop(job_id: str, stop: threading.Event) -> None:
    """
    Publishes a "running" event every 30s so the SSE stream's 90s watchdog
    sees liveness during long ingests. Without this, an in-flight task that
    hasn't reached a terminal state would look indistinguishable from a
    dead worker — and the watchdog would fire prematurely.

    `stop.wait(30)` returns True as soon as the event is set, so the loop
    exits cleanly when `ingest_repo` finishes (either success or failure
    path). Exceptions inside the loop are swallowed — heartbeats are
    best-effort liveness signals, not authoritative state.
    """
    from app.ingestion.events import publish_status
    while not stop.wait(_HEARTBEAT_INTERVAL_SECONDS):
        try:
            publish_status(job_id, "running", "still working")
        except Exception:
            pass


def ingest_repo(github_url: str, job_id: str, github_token: str | None = None) -> dict:
    """
    Full ingestion pipeline: clone -> chunk -> embed -> store.
    Returns a summary dict rather than raising on expected failure
    paths, since this will run inside a Celery task where we want
    structured status info (for /status/{job_id}), not a bare exception
    swallowed by the worker.
    """
    repo_id = derive_repo_id(github_url)
    # Heartbeat thread keeps the SSE watchdog quiet during long ingests.
    # Set `stop` before returning in every code path (success, exception,
    # timeout) — otherwise the thread outlives the task and keeps publishing
    # "running" against a job that has already terminated.
    stop = threading.Event()
    heartbeat = threading.Thread(target=_heartbeat_loop, args=(job_id, stop), daemon=True)
    heartbeat.start()
    try:
        repo_path = clone_repo(github_url, repo_id=repo_id, github_token=github_token)
        docs = load_and_chunk(repo_path)

        tree_text = build_directory_tree(repo_path)
        docs.append(Document(
            page_content=f"Directory structure of this repository:\n\n{tree_text}",
            metadata={"source": "(repository structure)", "type": "structure", "chunk_index": 0},
        ))

        stored_count = store_documents(docs, repo_id=repo_id, job_id=job_id)
        return {"repo_id": repo_id, "job_id": job_id, "chunks_stored": stored_count, "status": "completed"}
    finally:
        stop.set()
        heartbeat.join(timeout=2)
