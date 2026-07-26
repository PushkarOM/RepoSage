from celery import Celery
from app.core.config import settings
from celery.signals import worker_process_init

@worker_process_init.connect
def preload_embedding_model(**kwargs):
    from app.core.embeddings import get_embedding_function
    get_embedding_function()
    
celery_app = Celery(
    "reposage",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.ingestion.tasks"],
)

# task_track_started lets us see "STARTED" state via polling,
# not just PENDING -> SUCCESS/FAILURE. Useful for a real status
# endpoint where the user wants to know ingestion is actually running,
# not just queued.
celery_app.conf.update(
    task_track_started=True,
)
