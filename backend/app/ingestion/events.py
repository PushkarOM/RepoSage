"""
Pub/sub helpers for ingest status events.

Celery tasks are synchronous, so this module uses a sync Redis client rather
than the async one that lives on `app.state.redis`. The two clients share
`settings.redis_url`, which in docker-compose points at the `redis` service.
The SSE endpoint (`/ingest/stream/{job_id}`) subscribes via the async client;
the Celery task publishes via this sync client. Redis doesn't care which side
of the connection opened the channel — pub/sub is one-to-many, and any
subscriber attached to `ingest:{job_id}` receives everything published.

Why a separate file: keeps `tasks.py` focused on the pipeline orchestration;
event publishing is its own concern, mirroring the existing split between
`pipeline.py`, `chunker.py`, etc.
"""

import json
import redis as redis_sync

from app.core.config import settings


# Module-level sync client — one per Celery worker process. Lazy-init on first
# publish so importing this module from a non-task context (e.g. tests) doesn't
# open a Redis connection that nobody will use.
_sync_redis = None


def _get_sync_redis():
    global _sync_redis
    if _sync_redis is None:
        _sync_redis = redis_sync.from_url(settings.redis_url)
    return _sync_redis


def publish_status(job_id: str, state: str, detail: str | None = None, **extra) -> None:
    """
    Broadcast a status event for one ingest job to all SSE subscribers.

    The SSE endpoint subscribes to `ingest:{job_id}`; any subscriber receives
    the JSON payload. Failures here are deliberately swallowed — pub/sub is
    best-effort (no subscribers still counts as success in Redis), and a
    publish failure must never bring down the Celery task it's wrapped
    around. The DB write is the source of truth; the event is just a hint.
    """
    payload = {"job_id": job_id, "state": state, "detail": detail, **extra}
    try:
        _get_sync_redis().publish(f"ingest:{job_id}", json.dumps(payload))
    except Exception:
        # Logging-only — see docstring.
        pass
