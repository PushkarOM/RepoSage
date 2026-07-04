from app.core.celery_app import celery_app
from app.ingestion.pipeline import ingest_repo


@celery_app.task(bind=True, name="ingest_repo_task")
def ingest_repo_task(self, github_url: str) -> dict:
    """
    Celery task wrapper around ingest_repo. Uses the Celery task's own
    id as job_id, so the caller doesn't need to generate one separately
    — task_id IS the job_id, and doubles as the key for polling status.
    """
    job_id = self.request.id
    return ingest_repo(github_url, job_id=job_id)
