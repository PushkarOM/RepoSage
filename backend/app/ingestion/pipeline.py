from app.ingestion.clone import clone_repo
from app.ingestion.chunker import load_and_chunk
from app.ingestion.vectorstore import store_documents
from app.ingestion.utils import derive_repo_id


def ingest_repo(github_url: str, job_id: str, github_token: str | None = None) -> dict:
    """
    Full ingestion pipeline: clone -> chunk -> embed -> store.
    Returns a summary dict rather than raising on expected failure
    paths, since this will run inside a Celery task where we want
    structured status info (for /status/{job_id}), not a bare exception
    swallowed by the worker.
    """
    repo_id = derive_repo_id(github_url)
    repo_path = clone_repo(github_url, repo_id=repo_id, github_token=github_token)
    docs = load_and_chunk(repo_path)
    stored_count = store_documents(docs, repo_id=repo_id, job_id=job_id)

    return {
        "repo_id": repo_id,
        "job_id": job_id,
        "chunks_stored": stored_count,
        "status": "completed",
    }
