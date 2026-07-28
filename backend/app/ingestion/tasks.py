from app.core.celery_app import celery_app
from app.ingestion.pipeline import ingest_repo
from app.core.database import SessionLocal
from app.models.ingested_repo import IngestedRepo
from app.models.user import User


@celery_app.task(bind=True, name="ingest_repo_task")
def ingest_repo_task(self, github_url: str, user_id: int) -> dict:
    job_id = self.request.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        github_token = user.github_access_token if user else None

        result = ingest_repo(github_url, job_id=job_id, github_token=github_token)
        db.query(IngestedRepo).filter(IngestedRepo.job_id == job_id).update({"status": "success"})
        db.commit()
        return result
    except Exception:
        db.query(IngestedRepo).filter(IngestedRepo.job_id == job_id).update({"status": "failed"})
        db.commit()
        raise
    finally:
        db.close()