from langchain_core.tools import tool
from app.ingestion.vectorstore import search
from pathlib import Path
from app.core.config import settings
import httpx


@tool
def search_codebase(job_id: str, query: str, doc_type: str | None = None) -> str:
    """Search the ingested repository for code or documentation relevant
    to the query. Always use the job_id given in your context -- never
    guess or reuse a job_id from a different conversation.

    Args:
        job_id: The ingestion job ID identifying which repo to search.
        query: What to search for, e.g. "how does authentication work".
        doc_type: Optional filter, either "code" or "doc". Leave unset
            to search both.
    """
    results = search(query, k=5, doc_type=doc_type, job_id=job_id)

    if not results:
        return "No relevant results found in the ingested repository."

    formatted = []
    for r in results:
        source = r.metadata.get("source", "unknown")
        formatted.append(f"[{source}]\n{r.page_content}")

    return "\n\n---\n\n".join(formatted)

@tool
def get_file(job_id: str, path: str) -> str:
    """Retrieve the full contents of a specific file from the ingested
    repository. Use this when search_codebase returns a relevant chunk
    but you need to see the complete file for full context.

    Args:
        job_id: The ingestion job ID for the repo (identifies which
            cloned repo directory to read from).
        path: The relative file path within the repo, e.g. "src/main.py".
    """
    repo_dir = Path(settings.clone_dir) / job_id
    file_path = (repo_dir / path).resolve()

    # Prevent path traversal outside the cloned repo directory --
    # without this check, a malicious or malformed path like
    # "../../etc/passwd" could escape clone_dir entirely.
    if not str(file_path).startswith(str(repo_dir.resolve())):
        return "Error: path is outside the repository directory."

    if not file_path.is_file():
        return f"Error: {path} not found in repository."

    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"Error: {path} is a binary file and cannot be displayed."

@tool
def list_good_first_issues(repo: str) -> str:
    """List open issues labeled 'good first issue' for a GitHub repo.
    Use this when the user asks about ways to contribute to the project.

    Args:
        repo: The repo in "owner/name" format, e.g. "kennethreitz/samplemod".
    """
    url = f"https://api.github.com/repos/{repo}/issues"
    params = {"labels": "good first issue", "state": "open", "per_page": 10}

    try:
        response = httpx.get(url, params=params, timeout=10.0)
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            return "GitHub API rate limit hit (60 requests/hour for unauthenticated calls). Try again later."
        return f"GitHub API error: {e.response.status_code}"
    except httpx.RequestError:
        return "Could not reach GitHub API."

    issues = response.json()
    if not issues:
        return f"No open 'good first issue' items found for {repo}."

    formatted = [f"#{i['number']}: {i['title']} ({i['html_url']})" for i in issues]
    return "\n".join(formatted)
