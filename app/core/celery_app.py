from celery import Celery

celery_app = Celery(
    "reposage",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
    include=["app.ingestion.tasks"],
)

# task_track_started lets us see "STARTED" state via polling,
# not just PENDING -> SUCCESS/FAILURE. Useful for a real status
# endpoint where the user wants to know ingestion is actually running,
# not just queued.
celery_app.conf.update(
    task_track_started=True,
)
