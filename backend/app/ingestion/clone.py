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


def clone_repo(github_url: str, repo_id: str, github_token: str | None = None) -> Path:
    """
    Clones into a repo_id-scoped directory. If github_token is provided,
    it's injected into the clone URL for authenticated access to private
    repos -- GitHub accepts a token as the HTTPS username with any/no
    password. Falls back to a plain unauthenticated clone for public repos.
    """
    dest = Path(settings.clone_dir) / repo_id
    if dest.exists():
        shutil.rmtree(dest, onerror=_remove_readonly)
    dest.mkdir(parents=True, exist_ok=True)

    clone_url = github_url
    if github_token and github_url.startswith("https://"):
        clone_url = github_url.replace("https://", f"https://{github_token}@")

    Repo.clone_from(clone_url, dest, depth=1)
    return dest

