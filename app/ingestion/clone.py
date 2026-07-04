import shutil
from pathlib import Path
from git import Repo
from app.core.config import settings

def clone_repo(github_url: str, job_id: str) -> Path:
    """
    Clones a GitHub repo to a job-specific local directory.
    Using a job_id-scoped path avoids collisions between concurrent
    ingestion jobs (important once this runs as a Celery task).
    """
    dest = Path(settings.clone_dir) / job_id
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    Repo.clone_from(github_url, dest, depth=1)  # shallow clone: don't need full history
    return dest
