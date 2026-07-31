from langchain_core.tools import tool
from app.ingestion.vectorstore import hybrid_search
from langchain.tools import tool, ToolRuntime
from app.agent.context import AgentContext
from app.ingestion.structure import build_directory_tree
from app.ingestion.chunker import IGNORE_DIRS, CODE_EXTENSIONS
from pathlib import Path
from app.core.config import settings
import re
import httpx
import subprocess


# Source-file extensions the new code-search tools should scan. Matches
# CODE_EXTENSIONS in the chunker so behavior is consistent: a file we
# embed for retrieval, we also search for definitions/references in.
_SEARCHABLE_EXTS = tuple(CODE_EXTENSIONS.keys())

# Cap how much content a single tool call returns. The LLM has limited
# context; an unbounded grep result on a large repo would silently
# blow past the model's window. 200 is enough for "give me the picture"
# without dominating the conversation.
_MAX_TOOL_RESULT_LINES = 200


def _safe_repo_path(repo_id: str, path: str) -> tuple[Path, Path]:
    """
    Resolves a user-supplied path against the repo directory and checks
    that it doesn't escape via '..'. Returns (repo_dir, resolved_path)
    so callers can do their own existence checks. Shared between get_file
    and the new file-reading tools -- one place to keep the safety logic
    instead of three near-identical copies.
    """
    repo_dir = (Path(settings.clone_dir) / repo_id).resolve()
    resolved = (repo_dir / path).resolve()
    if not str(resolved).startswith(str(repo_dir)):
        raise ValueError(f"path '{path}' is outside the repository directory")
    return repo_dir, resolved


def _iter_source_files(repo_dir: Path):
    """
    Yields Path objects for every searchable source file under repo_dir,
    skipping the usual ignored directories. Used by find_definition /
    find_references rather than re-implementing the walk in each tool.
    """
    for p in repo_dir.rglob("*"):
        if not p.is_file() or any(part in IGNORE_DIRS for part in p.parts):
            continue
        if p.suffix in _SEARCHABLE_EXTS:
            yield p


@tool
async def search_codebase(repo_id: str, query: str, doc_type: str | None = None) -> str:
    """Search the ingested repository for code or documentation relevant
    to the query. Always use the repo_id given in your context.

    Args:
        repo_id: The ingestion job ID identifying which repo to search.
        query: What to search for.
        doc_type: Optional filter, "code" or "doc".
    """
    # hybrid_search routes trivially-routable queries (exact file paths,
    # very short identifier lookups) to vector-only, and runs fused
    # BM25 + vector with reciprocal rank fusion for everything else.
    results = await hybrid_search(query, k=5, doc_type=doc_type, repo_id=repo_id)
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
    try:
        _, file_path = _safe_repo_path(repo_id, path)
    except ValueError as e:
        return f"Error: {e}"
    if not file_path.is_file():
        return f"Error: {path} not found in repository."
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"Error: {path} is a binary file and cannot be displayed."


@tool
def list_good_first_issues(repo: str, runtime: ToolRuntime[AgentContext]) -> str:
    """List open issues labeled 'good first issue' for a GitHub repo.
    Use this when the user asks about ways to contribute to the project.

    Args:
        repo: The repo in "owner/name" format, e.g. "kennethreitz/samplemod".
    """
    url = f"https://api.github.com/repos/{repo}/issues"
    params = {"labels": "good first issue", "state": "open", "per_page": 10}

    headers = {}
    token = runtime.context.github_token if runtime.context else None
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        response = httpx.get(url, params=params, headers=headers, timeout=10.0)
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            return "GitHub API rate limit hit. Try again later."
        if e.response.status_code == 404:
            return f"Repo '{repo}' not found or not accessible."
        return f"GitHub API error: {e.response.status_code}"
    except httpx.RequestError:
        return "Could not reach GitHub API."

    issues = response.json()
    if not issues:
        return f"No open 'good first issue' items found for {repo}."

    formatted = [f"#{i['number']}: {i['title']} ({i['html_url']})" for i in issues]
    return "\n".join(formatted)


@tool
def get_directory_structure(repo_id: str) -> str:
    """Get the full directory/file structure of the ingested repository.
    Use this when the user asks about the repo's organization, what
    modules/folders exist, or where something might be located -- this
    gives a holistic view that search_codebase (which returns small
    content fragments) can't provide.

    Args:
        repo_id: Identifies which repo's structure to retrieve.
    """
    repo_dir = Path(settings.clone_dir) / repo_id
    if not repo_dir.exists():
        return "Error: repository not found. It may need to be re-ingested."
    return build_directory_tree(repo_dir)


@tool
def find_definition(repo_id: str, symbol: str) -> str:
    """Find where a symbol (function, class, or module-level variable) is
    defined in the repo. Returns up to 10 hits as `path:line: snippet`.

    Use this when the user is reading code and sees a name they don't
    recognize -- "where is X defined?" is the single most common
    navigation question for someone learning a new repo. Pair with
    find_references for the inverse (where is X called from?).

    Args:
        repo_id: Identifies which repo to search.
        symbol: The name to look for. Exact match, no substring search.
    """
    try:
        repo_dir, _ = _safe_repo_path(repo_id, "")
    except ValueError as e:
        return f"Error: {e}"
    pattern = re.compile(rf"^(def|class|async\s+def)\s+{re.escape(symbol)}\b|(^|\n){re.escape(symbol)}\s*[=:]")

    hits = []
    for p in _iter_source_files(repo_dir):
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                rel = p.relative_to(repo_dir)
                hits.append(f"{rel}:{lineno}: {line.rstrip()}")
                if len(hits) >= 10:
                    return "\n".join(hits)

    if not hits:
        return f"No definitions found for '{symbol}'."
    return "\n".join(hits)


@tool
def find_references(repo_id: str, symbol: str) -> str:
    """Find where a symbol is used (called, imported, mentioned) in the
    repo. Returns up to 15 hits as `path:line: snippet`.

    Use this as the follow-up to find_definition -- once you know where
    X is defined, this tells you where it gets used, which is what
    reveals integration points and call patterns.

    Args:
        repo_id: Identifies which repo to search.
        symbol: The name to look for. Whole-word match, no substrings.
    """
    try:
        repo_dir, _ = _safe_repo_path(repo_id, "")
    except ValueError as e:
        return f"Error: {e}"
    pattern = re.compile(rf"\b{re.escape(symbol)}\b")

    hits = []
    for p in _iter_source_files(repo_dir):
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                rel = p.relative_to(repo_dir)
                hits.append(f"{rel}:{lineno}: {line.rstrip()}")
                if len(hits) >= 15:
                    return "\n".join(hits)

    if not hits:
        return f"No references found for '{symbol}'."
    return "\n".join(hits)


@tool
def list_recent_changes(repo_id: str, path: str | None = None, max_count: int = 10) -> str:
    """Show the most recent commits in the repo, optionally filtered to
    a path. Use this when the user asks "what's been worked on lately",
    "when was X last changed", or wants to understand the recency of
    some piece of code.

    Args:
        repo_id: Identifies which repo's git history to read.
        path: Optional subdirectory or file to scope the log to
              (e.g. "backend/app/agent" -- only commits touching that).
        max_count: How many commits to return. Defaults to 10, hard
                   cap at 50 to avoid blowing context.
    """
    max_count = min(max_count, 50)

    try:
        repo_dir, _ = _safe_repo_path(repo_id, "")
    except ValueError as e:
        return f"Error: {e}"

    # Use git CLI rather than GitPython -- faster on shallow clones,
    # and gives us a clean -- separator between commit message and
    # files-changed list without writing our own parser.
    cmd = [
        "git", "-C", str(repo_dir),
        "log", f"--max-count={max_count}",
        "--pretty=format:%h | %ad | %an | %s",
        "--date=short",
        "--name-only",
    ]
    if path:
        cmd.extend(["--", path])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except FileNotFoundError:
        return "Error: git CLI not available in this environment."
    except subprocess.TimeoutExpired:
        return "Error: git log timed out."
    if result.returncode != 0:
        return f"Could not read git log: {result.stderr.strip()}"
    if not result.stdout.strip():
        return "No commits found."
    return result.stdout


@tool
def find_tests_for(repo_id: str, file_path: str) -> str:
    """Find test files that cover a given source file. Returns up to 10
    matching paths. Use this when the user asks about testing coverage,
    or before they change a file ("which tests do I need to run if I
    modify this?").

    The match is heuristic -- we look for both co-located tests
    (test_<basename>.py next to the file) and tests under common test
    directories (tests/, test/, __tests__/). The result is a list of
    paths; use get_file to read any of them.

    Args:
        repo_id: Identifies which repo to search.
        file_path: Path to the source file, e.g. "backend/app/core/rate_limit.py".
    """
    try:
        repo_dir, resolved = _safe_repo_path(repo_id, file_path)
    except ValueError as e:
        return str(e)
    if not resolved.exists():
        return f"File not found: {file_path}"

    basename = resolved.stem  # e.g. "rate_limit" for "rate_limit.py"
    suffixes = ("_test.py", ".test.py", "_spec.py", ".spec.py")
    test_dirs = ("tests", "test", "__tests__")

    candidates = set()

    # Co-located: same directory as the source file
    for s in suffixes:
        candidates.add(resolved.parent / f"test_{basename}{s}")
        candidates.add(resolved.parent / f"{basename}{s}")

    # Tests under standard test directories
    for d in test_dirs:
        for s in suffixes:
            candidates.add(repo_dir / d / f"test_{basename}{s}")

    # Module-name grep: any test file importing this module's path
    # Lets us catch non-standard layouts (e.g. tests organized by feature)
    module_path_parts = resolved.with_suffix("").relative_to(repo_dir).parts
    if module_path_parts:
        # Build a regex matching the various Python import forms that
        # could pull in this module. Three real shapes exist:
        #   from app.core.rate_limit import RateLimiter   (full path import)
        #   from app.core import rate_limit               (submodule as name)
        #   import app.core.rate_limit                    (module import)
        # The full path uses literal dots; the submodule form needs
        # the basename matched as a bare identifier at the end.
        joined = r"\.".join(re.escape(part) for part in module_path_parts)
        basename = re.escape(module_path_parts[-1])
        parent_joined = r"\.".join(re.escape(part) for part in module_path_parts[:-1])
        module_pattern = re.compile(
            rf"(?:import\s+{joined}(?:\.\w+)*"
            rf"|from\s+{joined}\s+import"
            rf"|from\s+{parent_joined}\s+import\s+{basename})"
        )
        for p in _iter_source_files(repo_dir):
            if "test" not in p.name.lower():
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue
            if module_pattern.search(text):
                candidates.add(p)

    found = sorted(c for c in candidates if c.exists())
    if not found:
        return f"No test files found for {file_path}."
    rel = [str(p.relative_to(repo_dir)) for p in found[:10]]
    return "\n".join(rel)


@tool
def read_file_section(repo_id: str, path: str, start_line: int = 1, end_line: int = 50) -> str:
    """Read a slice of a file by line range, rather than the whole file.
    Use this when the user knows roughly where the interesting part is
    (e.g. "show me the rate_limit function") or when a file is large
    enough that dumping it would dominate context.

    Lines are 1-indexed and inclusive at both ends (matches editor line
    numbers). The result is prefixed with line numbers so the model can
    quote precise locations.

    Args:
        repo_id: Identifies which repo's file to read.
        path: Relative file path within the repo.
        start_line: First line to include (1-indexed).
        end_line: Last line to include (1-indexed, inclusive).
    """
    try:
        _, file_path = _safe_repo_path(repo_id, path)
    except ValueError as e:
        return f"Error: {e}"
    if not file_path.is_file():
        return f"Error: {path} not found in repository."
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"Error: {path} is a binary file and cannot be displayed."

    lines = text.splitlines()
    total = len(lines)

    if start_line < 1 or end_line < start_line:
        return f"Error: invalid line range {start_line}-{end_line}."
    if start_line > total:
        return f"Error: file only has {total} lines; start_line={start_line} is past the end."

    truncated = (end_line - start_line + 1) > _MAX_TOOL_RESULT_LINES
    end_line = min(end_line, start_line + _MAX_TOOL_RESULT_LINES - 1)

    chunk = lines[start_line - 1 : end_line]
    width = len(str(end_line))
    out = [f"{str(i).rjust(width)} | {lines[i - 1]}" for i, _ in enumerate(chunk, start=start_line)]
    if truncated:
        out.append(f"... (truncated; file has {total} lines total)")
    return "\n".join(out)


@tool
def list_dependencies(repo_id: str) -> str:
    """List the third-party packages this repo depends on, ordered by
    how often they're imported. Use this when the user asks "what does
    this project use?" or wants a high-level orientation to the stack.

    Scans Python source files for top-level import statements. Stdlib
    imports are filtered out (heuristic: same-package imports are
    always excluded; anything matching a well-known stdlib module
    name is excluded too). The result is approximate -- no AST, just
    regex on the first 50 lines of each file -- but reliable enough
    for orientation.

    Args:
        repo_id: Identifies which repo to scan.
    """
    # Conservative stdlib subset. Not exhaustive -- Python's stdlib is
    # large -- but covers the modules real codebases actually pull in.
    # Anything we miss just shows up in the result with a slightly
    # inflated count; not a correctness issue, just noise.
    stdlib = {
        "os", "sys", "re", "json", "typing", "pathlib", "datetime",
        "collections", "functools", "itertools", "io", "subprocess",
        "logging", "unittest", "asyncio", "threading", "time", "uuid",
        "hashlib", "copy", "math", "random", "string", "enum", "abc",
        "dataclasses", "contextlib", "warnings", "traceback", "inspect",
        "tempfile", "shutil", "glob", "fnmatch", "csv", "ast", "dis",
    }

    try:
        repo_dir, _ = _safe_repo_path(repo_id, "")
    except ValueError as e:
        return f"Error: {e}"

    counts: dict[str, int] = {}
    import_re = re.compile(r"^(?:from\s+([\w]+)|import\s+([\w]+))", re.MULTILINE)

    for p in _iter_source_files(repo_dir):
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        # Only scan the top of the file -- real imports cluster up there.
        head = "\n".join(text.splitlines()[:50])
        for m in import_re.finditer(head):
            pkg = m.group(1) or m.group(2)
            if pkg in stdlib or pkg.startswith("_"):
                continue
            counts[pkg] = counts.get(pkg, 0) + 1

    if not counts:
        return "No third-party dependencies detected."
    top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:30]
    return "\n".join(f"{name} ({count})" for name, count in top)
