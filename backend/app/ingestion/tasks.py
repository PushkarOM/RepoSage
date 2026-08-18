from celery.exceptions import SoftTimeLimitExceeded

from app.core.celery_app import celery_app
from app.ingestion.pipeline import ingest_repo
from app.ingestion.events import publish_status
from app.core.database import SessionLocal
from app.models.ingested_repo import IngestedRepo
from app.models.user import User


# Hard kill at 15 min, soft-limit (catchable SoftTimeLimitExceeded) at 14.
# Without these, a huge repo can OOM the worker or pin it for hours --
# blocking the worker pool. The DB write + publish_status below make the
# timeout visible to both the polling endpoint and any open SSE stream.
@celery_app.task(
    bind=True,
    name="ingest_repo_task",
    time_limit=900,
    soft_time_limit=840,
)
def ingest_repo_task(self, github_url: str, user_id: int) -> dict:
    job_id = self.request.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        github_token = user.github_access_token if user else None

        # Promote "queued" -> "running" before doing the work so the polling
        # endpoint (and dashboard) can see ingestion has actually started.
        # Without this, the row stays "queued" until either success or failure
        # -- indistinguishable from a stuck task in the eyes of the user.
        db.query(IngestedRepo).filter(IngestedRepo.job_id == job_id).update({"status": "running"})
        db.commit()
        publish_status(job_id, "running", "started")

        result = ingest_repo(github_url, job_id=job_id, github_token=github_token)
        db.query(IngestedRepo).filter(IngestedRepo.job_id == job_id).update({"status": "success"})
        db.commit()
        publish_status(job_id, "success", {"chunks_stored": result.get("chunks_stored")})
        return result
    except SoftTimeLimitExceeded:
        # Catchable timeout -- try to leave a coherent "failed" row +
        # terminal SSE event before the hard kill (60s away).
        db.query(IngestedRepo).filter(IngestedRepo.job_id == job_id).update({"status": "failed"})
        db.commit()
        publish_status(job_id, "failed", "Task exceeded time limit")
        raise
    except Exception as e:
        db.query(IngestedRepo).filter(IngestedRepo.job_id == job_id).update({"status": "failed"})
        db.commit()
        publish_status(job_id, "failed", str(e))
        raise
    finally:
        db.close()
