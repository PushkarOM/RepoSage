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


def clone_repo(github_url: str, repo_id: str) -> Path:
    """
    Clones into a repo_id-scoped directory (e.g. "owner/name"), not a
    job_id-scoped one. This is deliberate: repo_id is stable across
    re-ingestions of the same repo, so re-running ingestion naturally
    overwrites the same directory instead of accumulating a new one
    per run -- this is also what makes a future "reingest" feature safe.
    """
    dest = Path(settings.clone_dir) / repo_id
    if dest.exists():
        shutil.rmtree(dest, onerror=_remove_readonly)
    dest.mkdir(parents=True, exist_ok=True)

    Repo.clone_from(github_url, dest, depth=1)
    return dest

