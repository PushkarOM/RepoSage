from langchain_core.tools import tool
from app.ingestion.vectorstore import search
from pathlib import Path
from app.core.config import settings
import httpx


@tool
def search_codebase(repo_id: str, query: str, doc_type: str | None = None) -> str:
    """Search the ingested repository for code or documentation relevant
    to the query. Always use the repo_id given in your context.

    Args:
        repo_id: Identifies which repo to search (e.g. "owner/name").
        query: What to search for.
        doc_type: Optional filter, "code" or "doc".
    """
    results = search(query, k=5, doc_type=doc_type, repo_id=repo_id)
    if not results:
        return "No relevant results found in the ingested repository."
    formatted = [f"[{r.metadata.get('source', 'unknown')}]\n{r.page_content}" for r in results]
    return "\n\n---\n\n".join(formatted)


@tool
def get_file(repo_id: str, path: str) -> str:
    """Retrieve the full contents of a specific file from the ingested
    repository.

    Args:
        repo_id: Identifies which repo's clone directory to read from.
        path: The relative file path within the repo.
    """
    repo_dir = Path(settings.clone_dir) / repo_id
    file_path = (repo_dir / path).resolve()

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
