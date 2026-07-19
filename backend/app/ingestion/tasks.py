from app.core.celery_app import celery_app
from app.ingestion.pipeline import ingest_repo
from app.core.database import SessionLocal
from app.models.ingested_repo import IngestedRepo


@celery_app.task(bind=True, name="ingest_repo_task")
def ingest_repo_task(self, github_url: str) -> dict:
    job_id = self.request.id
    db = SessionLocal()
    try:
        result = ingest_repo(github_url, job_id=job_id)
        db.query(IngestedRepo).filter(IngestedRepo.job_id == job_id).update({"status": "success"})
        db.commit()
        return result
    except Exception:
        db.query(IngestedRepo).filter(IngestedRepo.job_id == job_id).update({"status": "failed"})
        db.commit()
        raise
    finally:
        db.close()
