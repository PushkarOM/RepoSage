import shutil
import stat
from pathlib import Path
from git import Repo
from app.core.config import settings


def _remove_readonly(func, path, exc_info):
    """
    Windows marks files inside .git/ (especially packed objects) as
    read-only. shutil.rmtree can't delete those by default on Windows,
    so this error handler clears the read-only bit and retries the
    delete. No-op safety net on other OSes since this only triggers
    on a PermissionError.
    """
    import os
    os.chmod(path, stat.S_IWRITE)
    func(path)


def clone_repo(github_url: str, job_id: str) -> Path:
    """
    Clones a GitHub repo to a job-specific local directory.
    job_id-scoped path avoids collisions between concurrent
    ingestion jobs once this runs as a Celery task.
    """
    dest = Path(settings.clone_dir) / job_id
    if dest.exists():
        shutil.rmtree(dest, onerror=_remove_readonly)
    dest.mkdir(parents=True, exist_ok=True)

    Repo.clone_from(github_url, dest, depth=1)  # shallow: don't need full history
    return dest
