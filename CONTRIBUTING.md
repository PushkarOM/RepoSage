# Contributing to RepoSage

Thanks for taking the time to contribute! This document is meant to be
useful whether you're opening your first pull request or your hundredth.
The goal is to get you productive as quickly as possible without you
having to reverse-engineer the project's conventions.

If you just want a quick answer to "how do I run the thing locally,"
[Setup](#setup) below is the only section you need to read. If you want
context on what RepoSage is and how it's organized, see the
[README](README.md) and [ProjectPlan.md](ProjectPlan.md) first.

## Table of contents

- [Code of conduct](#code-of-conduct)
- [What to contribute](#what-to-contribute)
- [Setup](#setup)
- [Project layout](#project-layout)
- [Development workflow](#development-workflow)
- [Code conventions](#code-conventions)
- [Testing](#testing)
- [Adding a new tool to the agent](#adding-a-new-tool-to-the-agent)
- [Adding a new API endpoint](#adding-a-new-api-endpoint)
- [Adding a new frontend page](#adding-a-new-frontend-page)
- [Commit messages and PRs](#commit-messages-and-prs)
- [Reporting bugs](#reporting-bugs)
- [Proposing features](#proposing-features)

## Code of conduct

This project follows the same expectations as the
[Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
In short: be respectful, assume good faith, give people the benefit of
the doubt, and remember there's a real person on the other end of the
internet. If something feels off, open a private issue and we'll talk
before it becomes a problem.

## What to contribute

If you're looking for somewhere to start:

- **Look for issues tagged [`good first issue`](https://github.com/PushkarOM/RepoSage/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).** The contribute section on the live landing page
  pulls the same list of issues and renders them in real time — see
  `frontend/src/pages/Landing.jsx` (`ContributeSection`).
- **The `eval/test_cases.py` file is a great place to contribute.** If
  you have a repo you've ingested and a question you wish the agent
  answered better, add a test case with the query and the file path
  you expected. The eval harness reports MRR / Recall@5 per retriever,
  so you can see your case before/after your change. See
  [Testing](#testing) for how to run it.
- **The chunker and the dedup logic** are the most under-tested parts
  of the ingestion pipeline. `backend/tests/test_chunker.py` covers
  the dedup cases but not the language-aware splitting. If you find a
  file that chunks weirdly, that's a useful issue.
- **Tool coverage.** The agent has 10 tools; each tool's system-prompt
  description is in `backend/app/agent/tools.py`. If you add a tool
  (see [Adding a new tool](#adding-a-new-tool-to-the-agent) below), you
  should also add the description's "when to use" guidance to
  `SYSTEM_PROMPT` in `backend/app/agent/agent.py`.
- **Frontend.** The UI is intentionally restrained (see the design
  notes in `ProjectPlan.md` under the "Polish" section). If you have
  something small to fix — a11y, responsive layout, empty states,
  keyboard nav — those are welcome. Big cosmetic changes should be
  discussed first.

## Setup

You need Python 3.12, Node.js, and Docker. The backend has two
services (Redis Stack and Chroma) that are easier to run via Docker
even if you're doing the rest natively.

### 1. Clone and install

```bash
git clone https://github.com/PushkarOM/RepoSage.git
cd RepoSage
```

### 2. Backend

You need an API key for at least one LLM provider. Gemini has a free
tier; Groq has a more generous free tier and faster inference (which
matters for development iteration). Pick one and add the relevant key
to `backend/.env`:

```bash
cd backend
cp .env.example .env   # if there's no .env.example, create the file by hand
```

Minimum contents of `backend/.env`:

```bash
# Required
GOOGLE_API_KEY=your-gemini-key
JWT_SECRET_KEY=any-random-hex-string        # access tokens (generate with: python -c "import secrets; print(secrets.token_hex(32))")
JWT_REFRESH_SECRET_KEY=any-other-hex-string # refresh tokens — MUST differ from JWT_SECRET_KEY

# Cookie auth -- defaults are dev-friendly. Set COOKIE_SECURE=true in prod.
COOKIE_SECURE=false                         # true in production (HTTPS)
COOKIE_SAMESITE=lax
CORS_ALLOWED_ORIGINS=["http://localhost:5173","http://localhost:8000"]

# Optional — switch the LLM provider to Groq
# LLM_PROVIDER=groq
# GROQ_API_KEY=your-groq-key
# GROQ_MODEL_NAME=llama-3.3-70b-versatile
```

The full list of configurable settings is in
`backend/app/core/config.py` — every value comes from environment
variables (Pydantic Settings) and has a default you can override.

### 3. Run the infra services (Redis Stack + Chroma)

The native path still uses Docker for these two, because the agent
memory and the vector DB are not things you want to install locally:

```bash
docker run -d -p 6379:6379 --name reposage-redis redis/redis-stack-server
docker run -d -p 8001:8000 --name reposage-chroma chromadb/chroma
```

Then in `backend/.env` (or via environment variables):

```bash
REDIS_URL=redis://localhost:6379/0
CHROMA_HOST=localhost
CHROMA_PORT=8001     # 8000 in production (the docker-compose service), 8001 when mapped to host
```

### 4. Install backend dependencies

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 5. Run the migrations

```bash
alembic upgrade head
```

This creates the three tables: `users`, `ingested_repos`, `chat_threads`.

### 6. Start the three backend processes

Each one is a separate process. Open a terminal for each:

```bash
# Terminal 1: API
uvicorn app.main:app --reload

# Terminal 2: Celery worker
celery -A app.core.celery_app worker --loglevel=info --pool=solo
```

The embedding model is preloaded at startup (FastAPI lifespan + Celery
worker_process_init) so the first request isn't 15 seconds slower than
every subsequent one. If your worker seems to be doing nothing for a
while on boot, that's the warmup, not a hang.

### 7. Frontend

```bash
cd frontend
npm install
npm run dev
```

The dev server runs on http://localhost:5173 by default. The Vite
dev server proxies `/api/*` to the FastAPI backend on
`http://localhost:8000` (see `frontend/vite.config.js`) so the browser
sees a single origin. That single-origin setup is required for the
httpOnly auth cookies to ride on every request — `SameSite=Lax` cookies
don't attach on cross-origin POST/PUT/DELETE. CORS is configured with
explicit origins and `allow_credentials=True` in `backend/app/main.py`.

The frontend reads `VITE_API_BASE` from `.env`; it's set to an empty
string in dev so all API URLs are relative (`/api/...`). In production
the same `/api/*` routing happens at the nginx layer.

### 8. Or use Docker Compose for everything

If you don't need hot reload and just want the whole stack:

```bash
docker compose build
docker compose up -d
```

The Compose file builds the frontend inside its own image (multi-stage)
and serves it via nginx on port 80, so you don't need to run `npm run
build` manually. API docs are at <http://localhost:8000/docs>.

There's also a `docker-compose.dev.yml` that bind-mounts the source and
runs uvicorn with `--reload`. Use it when you want fast iteration
without a full rebuild.

## Project layout

```
backend/
├── app/
│   ├── agent/        # agent.py (ReAct + LangGraph), tools.py (10 tools), context.py (tool runtime context)
│   ├── api/          # routes.py (FastAPI router), auth.py (JWT), schemas.py (Pydantic)
│   ├── core/         # config.py, db.py, security.py, celery_app.py, rate_limit.py, llm.py, embeddings.py
│   ├── ingestion/    # clone.py, chunker.py, structure.py, vectorstore.py (hybrid + multi_query), pipeline.py, tasks.py
│   └── models/       # SQLAlchemy ORM (User, IngestedRepo, ChatThread)
├── alembic/          # schema migrations
├── eval/             # offline retrieval benchmark (run_eval.py, test_cases.py)
├── tests/            # pytest suite
└── requirements.txt

frontend/
├── src/
│   ├── components/   # PromptBar, Message, MessageList, ThemeToggle, LogoutButton, ui/button
│   ├── pages/        # Landing, Auth, Dashboard, Ingest, ThreadList, Chat
│   ├── context/      # AuthContext
│   └── lib/          # utils.js (cn), copy.js (TAGLINE, REPO, etc.), useTheme.js, api.js
├── index.html
├── package.json
└── vite.config.js
```

**Where to look for what:**

- Want to change how a tool behaves? → `backend/app/agent/tools.py`
- Want to add a new endpoint? → `backend/app/api/routes.py`
- Want to change what the agent's system prompt says? → `backend/app/agent/agent.py` (`SYSTEM_PROMPT`)
- Want to change how the search works? → `backend/app/ingestion/vectorstore.py` (`hybrid_search`, `multi_search`)
- Want to change the streaming chat UX? → `frontend/src/components/Message.jsx` (typewriter) and `MessageList.jsx` (auto-scroll)
- Want to add a new page? → `frontend/src/pages/`, plus a route in `App.jsx`
- Want to change a token / theme / color? → `frontend/src/index.css` (the `@theme` block)

## Development workflow

1. **Branch off `main`.** Even for one-line fixes, a branch is cheap
   and keeps the working tree clean if you need to context-switch.
2. **Make focused commits.** One logical change per commit, even if a
   PR has multiple commits.
3. **Run the tests locally** before pushing (see
   [Testing](#testing)). CI will catch most things, but a fast local
   loop saves a round trip.
4. **Open a PR against `main`.** CI runs the pytest suite. The
   `eval/` harness is **not** in CI (see [Testing](#testing) for why);
   if your change affects retrieval quality, run it locally and
   include the new numbers in the PR description.
5. **Address review comments** by pushing new commits (don't force-push
   during review unless asked). Squash when the PR is ready to merge.

## Code conventions

### Python (backend)

- **Type hints everywhere.** Public functions should have parameter and
  return annotations. The codebase uses the modern `X | None` syntax
  (Python 3.10+), not `Optional[X]`.
- **Docstrings on public functions** but not on internal helpers. The
  project favors "docstrings say *why*, comments say *how*." If a
  function's name + signature tell you what it does, the docstring
  should explain the non-obvious choice (a heuristic, a tradeoff, a
  bug it works around).
- **`re` patterns as raw strings.** `r"..."` not `"..."`. f-string
  patterns that contain backslashes (`f"\{...}"`) emit
  `SyntaxWarning` — extract the pattern to a raw string first.
- **Don't capture `settings.x` at import time** for things that might
  be monkey-patched in tests. Pass the attribute *name* and do
  `getattr(settings, ...)` fresh. There's a real bug in the git log
  about this — see `ProjectPlan.md`, Phase 3, "Rate limiting."
- **Tools take a `runtime: ToolRuntime[AgentContext]` argument** when
  they need access to per-user state (like the GitHub OAuth token).
  Don't use `contextvar` — LangGraph's ToolNode runs sync tools in a
  background thread pool and `contextvar` doesn't propagate across
  that boundary. See the existing `list_good_first_issues` tool for
  the canonical pattern.
- **Use the `_safe_repo_path` helper** for any tool that resolves a
  user-supplied path against a cloned repo. It checks for `..`
  traversal. New tools that don't use it are a security bug.

### JavaScript / React (frontend)

- **Functional components only.** No class components. Hooks for state
  and effects; refs only when you genuinely need a non-rendering
  reference (like the typewriter queue in `Message.jsx`).
- **Tailwind utility classes, not custom CSS.** New colors go in
  `index.css` under `@theme` and are referenced as `bg-paper` /
  `text-ink` / etc. — the existing tokens. Don't add one-off hex
  values in components; the design system has a restraint principle
  (see `ProjectPlan.md`).
- **Use the `Button` component from `components/ui/button.jsx`.** It
  has CVA variants: `primary`, `ghost`, `link`. Sizes: `default`,
  `sm`, `lg`, `link`. Don't reintroduce hand-rolled `<button>` tags.
- **Co-locate small concerns, lift shared concerns to `lib/`.** If
  something is used in more than one place, it goes in `src/lib/`
  (e.g. `copy.js` for shared copy strings, `api.js` for the auth-aware
  fetch wrapper).
- **The `authFetch` wrapper in `lib/api.js` handles 401s** by
  hard-redirecting to `/login`. It also adds `credentials: "include"`
  on every call so the httpOnly auth cookies ride on the request. Use
  `authFetch` (or any other helper in `lib/api.js`) for every
  authenticated API call — don't use raw `fetch()` for backend calls
  unless you've thought about credentials.
- **The `cn()` helper in `lib/utils.js`** is `twMerge(clsx(...))`. Use
  it for any className that needs conditional classes.

### Imports

- Use the `@/` alias (configured in `jsconfig.json`) for imports
  across the `src/` tree: `import { TAGLINE } from "@/lib/copy"`.
- For imports within the same directory or one level up, use relative
  paths: `import Message from "./Message"`, `import { useAuth } from "../context/AuthContext"`.

## Testing

### Unit tests (pytest)

```bash
cd backend
python -m pytest tests -v
```

The suite covers auth, rate limiting, repo management, and the
chunker. It's run on every push via `.github/workflows/ci.yml`.

When you add a new test:

- Put it in the file that matches the module under test
  (`tests/test_chunker.py` for chunker changes, etc.).
- Use the `conftest.py` fixtures where they fit (e.g. the test
  database session). Add a new fixture there if you need a new shared
  piece of state.
- Don't mock the LLM unless you're explicitly testing prompt behavior.
  Most bugs are in tool implementation, not the model.

### Retrieval eval (manual)

```bash
cd backend
python -m eval.run_eval <repo_id>
```

This compares `vector_only`, `multi_query`, and `hybrid` retrievers
against the curated test cases in `eval/test_cases.py` and prints a
side-by-side report (MRR, Recall@5, avg latency, per-case detail).

It's deliberately **not in CI** because:

- It needs a live Chroma with a real ingested repo
- It makes a real LLM call (for multi_query expansion) which costs API quota
- The headline number drifts run-to-run by a few percent, so a flaky
  CI test would be worse than no test

If your change is in the retrieval path (`vectorstore.py` or
`chunker.py`), run it before and after your change and put the
numbers in the PR description. If you add a new retrieval strategy
(say, a graph-based retriever), add it to the `RETRIEVERS` dict in
`run_eval.py` and it will get scored alongside the existing ones.

### Frontend

The frontend has no test suite today. Manual testing via `npm run dev`
is the convention. If you add tests (e.g. with Vitest), please add a
`test` script to `package.json` so CI can run them.

## Adding a new tool to the agent

This is the most common kind of contribution. The agent currently has
10 tools in `backend/app/agent/tools.py`.

**1. Write the tool.** Use the `@tool` decorator from `langchain_core.tools`:

```python
from langchain_core.tools import tool

@tool
def my_new_tool(repo_id: str, some_arg: str) -> str:
    """Short, one-line description that the LLM will see in the tool list.

    Longer description if needed: explain what the tool does, when to
    use it, and when NOT to use it. The model uses these descriptions
    to decide which tool to call.

    Args:
        repo_id: Identifies which repo to operate on.
        some_arg: What this argument does.
    """
    # ... implementation ...
    return result
```

**2. Add it to the agent's tool list** in `backend/app/agent/agent.py`:

```python
from app.agent.tools import (
    # ... existing tools ...
    my_new_tool,
)

# ...

_agent = create_agent(
    model=_model,
    tools=[
        # ... existing tools ...
        my_new_tool,
    ],
    # ...
)
```

**3. Update the system prompt.** Add a paragraph to `SYSTEM_PROMPT` in
`agent.py` describing when to use your tool. The "Tool selection"
section is the right place. If you don't, the model will have a tool
it doesn't know when to reach for.

**4. If the tool needs per-user state** (like a GitHub token), use the
`runtime: ToolRuntime[AgentContext]` parameter pattern. See
`list_good_first_issues` for the canonical example.

**5. If the tool returns a lot of content,** cap it. The LLM has a
limited context window, and an unbounded grep result will silently
blow past it. The existing `_MAX_TOOL_RESULT_LINES = 200` constant
in `tools.py` is a good pattern to follow.

**6. If the tool reads from the cloned repo directory,** use
`_safe_repo_path(repo_id, path)` to resolve the path. It checks for
`..` traversal so a user can't ask the tool to read arbitrary files
on the host.

**7. Add a test case to `eval/test_cases.py`** if your tool is for
retrieval. Even if the eval harness doesn't test tool *selection* (it
tests retrieval quality, not agent behavior), the query list is a
useful reference for what kinds of questions the agent should be able
to answer.

## Adding a new API endpoint

**1. Define the request and response schemas** in
`backend/app/api/schemas.py` (Pydantic models). Use
`response_model=...` on the route so the OpenAPI docs are accurate.

**2. Add the route to `backend/app/api/routes.py`.** Use the
`router` instance that's already there; don't create a new one unless
the endpoints are clearly a separate resource group.

**3. Require auth** with `Depends(get_current_user_from_cookie)` for everything
except `/register` and `/login`. The `current_user` argument is the
username string; look up the User row via `db.query(User).filter(User.username
== current_user).first()`. Reads from the `reposage_token` cookie.

**4. Add a rate limit** if the endpoint hits an external API or costs
LLM quota: `_rl: None = Depends(rate_limit("ingest", "rate_limit_ingest_per_day", 86400))`.
See the existing `/chat` and `/ingest` routes for the pattern.

**5. Write a test** in `backend/tests/`. The existing `conftest.py`
gives you a test database session. Auth tests use the `client` fixture
plus the registered-user helper to get a JWT.

**6. Wire the frontend.** Add a helper to `frontend/src/lib/api.js` if
the call has any non-trivial shape, then call it from the relevant
page. The page should show a loading state and handle the 401 redirect
(via `authFetch`).

## Adding a new frontend page

**1. Create the page component** in `frontend/src/pages/<Name>.jsx`.
Match the file's imports, class names, and tone to the existing pages.
Use the `Button` component, not a raw `<button>`.

**2. Add the route to `App.jsx`.** Decide whether the page needs auth
(most do — wrap in `<RequireAuth>`). There is exactly one global header
and it renders on every route.

**3. If the page makes authenticated API calls,** use the helpers in
`lib/api.js`. The `authFetch` wrapper handles 401s by hard-redirecting
to `/login`.

**4. If the page has a long-running state** (ingest SSE stream, chat
streaming), follow the existing pattern in `Ingest.jsx` / `Chat.jsx`:
- A `loadingHistory` / busy state with `loading-breathe` class
- An `error` state with `role="alert"` and a clear error message
- A disabled Button while busy, with `aria-busy="true"`
- For ingest specifically: open the SSE stream in `useEffect`, close it
  in the cleanup. EventSource retries forever by default, which is wrong
  for a terminal stream — `streamIngestStatus` already closes on error.

**5. Theme tokens** for any new color go in `frontend/src/index.css`
under `@theme`. Don't introduce one-off hex values in components.

## Commit messages and PRs

There's no enforced convention, but a few patterns work well:

- **Subject line** is a short summary in present tense, capitalized,
  no trailing period. e.g. `Fix dedup race in chunker`, not `fixed it`
  or `Fixing the dedup issue.`
- **Body** (if non-trivial) explains *why* not *what* — the diff
  shows what, the commit message should say "the previous version was
  conflating cross-file references with cross-section duplicates; this
  limits the minhash shingle to within a single file's chunks" rather
  than "changed _dedupe_chunks to take a list of chunks per file."

For PRs:

- **One logical change per PR.** If you have a fix and a refactor,
  two PRs are easier to review and easier to revert.
- **Describe the change in the PR body.** If the change is
  non-obvious, say what you considered and why you went with this
  approach.
- **Reference any related issue** with `Fixes #123` so the issue
  closes when the PR merges.
- **Screenshots** for any visual change. The frontend renders
  differently in dark and light mode, so include both.

## Reporting bugs

Open an issue with:

- **What you did** (the steps to reproduce)
- **What you expected to happen**
- **What actually happened** (include the full error message and
  stack trace if there is one)
- **Your environment** — OS, Python version, Node version, whether
  you ran via Docker Compose or natively
- **The relevant logs** — for backend issues, paste the uvicorn /
  celery worker output. The full traceback is more useful than the
  last line.

If the bug is security-related, **don't open a public issue** — email
the maintainer directly (the address is in the commit history) and
give us a chance to patch it before disclosure.

## Proposing features

Open an issue with:

- **The problem you're trying to solve** ("I want to be able to find
  every issue I asked about a specific file" is better than "add a
  filter for files")
- **Your proposed approach** — if you have one. If you don't, that's
  fine; the discussion is part of the value.
- **Alternative approaches you considered** and why you didn't pick
  them

For larger features (anything that touches the agent's tools, the
retrieval pipeline, or the database schema), the maintainer will
probably want to discuss the design before any code is written. Small
features (a new env var, a new frontend page, a new tool that
implements an obvious gap) can usually go straight to a PR.

## Questions?

If something in this document doesn't match what you find in the
codebase, the code is right and this document is wrong — please open
a PR to fix it. The docs should be kept up to date as the project
evolves.
