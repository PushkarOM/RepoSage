from urllib.parse import urlparse


def derive_repo_id(github_url: str) -> str:
    """
    Derives a stable identifier from a GitHub URL, e.g.
    https://github.com/kennethreitz/samplemod.git -> kennethreitz/samplemod

    This is separate from job_id (which is per-run, used for the temp
    clone directory). repo_id is what we dedupe on: re-ingesting the
    same repo replaces its old chunks instead of duplicating them.
    """
    path = urlparse(github_url).path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return path
