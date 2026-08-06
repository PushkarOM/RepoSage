# RepoSage — Project Plan

Tracking doc for turning RepoSage from a working portfolio demo into a
genuinely polished one. Goal: **impressive portfolio project**, not a
production SaaS — scope decisions below reflect that explicitly.

This file is the per-phase log. The README is the entry point that
describes what the project *is* today; this file is the per-phase
narrative of how we got here, with the bugs found and lessons learned
along the way.

## Phase status

| Phase | Status | Description |
|---|---|---|
| Phase 1 | ✅ Done | Foundation: Postgres, Alembic, Redis-backed agent memory |
| Phase 2 | ✅ Done | Product feel: streaming, dashboard, syntax highlighting, citations, multi-LLM support |
| Phase 2.5 | ✅ Done | Repo identity & multi-conversation support (mid-build insertion) |
| Phase 3 | ✅ Done | Security / multi-tenancy: rate limiting, GitHub OAuth for private repos |
| Phase 4 | ✅ Done | Agent / RAG depth: hybrid search, dedup, more tools, eval harness |
| Phase 5 | ⏳ Next | Ops maturity: Render + auto-deploy (Dockerfile already shipped) |
| Polish | ✅ Done (initial) | Frontend UX sweep + streaming polish + landing refresh |
| Hardening | ✅ Done (2026-08-03 → 2026-08-04) | Pre-OSS ops/UX: SSE ingest stream, JWT dual-token refresh, slim scrollbar, save/cancel icons, httpOnly-cookie auth migration |

## Phase 1 — Foundation

- [x] Migrate SQLite → Postgres (Neon, managed, serverless)
- [x] Alembic migrations wired up, verified with a real schema change (`is_active` column)
- [x] Redis-backed agent memory (`RedisSaver` → `AsyncRedisSaver`, via Redis Stack), verified surviving container restarts

**Bugs found & fixed along the way** (worth keeping — good interview material):
- `connect_args` computed correctly but never actually passed to `create_engine()`
- Neon silently drops idle connections (serverless) — fixed with `pool_pre_ping=True`
- `RedisSaver` needs RediSearch/RedisJSON modules — switched to `redis/redis-stack-server`
- Sync `RedisSaver` incompatible with `agent.astream()` — required full async rewrite (`AsyncRedisSaver`, `ainvoke`, FastAPI `lifespan` startup)
- `docker compose restart` vs `docker compose build` confusion — restart doesn't pick up code changes

**Observations parked for Phase 4** (RAG/agent quality):
- Agent conflates near-duplicate entities across README sections (double-counted a project listed twice under different headings)
- ~~Agent gives generic "I can't recall past conversations" disclaimer~~ — fixed via system_prompt in Phase 2

## Phase 2 — Product feel

- [x] Streaming chat responses (token-by-token) — async agent + AsyncRedisSaver
- [x] "Your repos" dashboard — list previously ingested repos per user, resume chat without re-ingesting
- [x] Syntax-highlighted code blocks in chat responses (react-markdown + react-syntax-highlighter)
- [x] Citations in answers — via system_prompt instructing the agent to cite file paths inline
- [x] LLM provider switch: Gemini (default) and Groq, pluggable via `LLM_PROVIDER`

**System prompt tuning** found during this phase:
- Tool selection: get_file for "explain this file" vs search_codebase for broad queries
- Shallow answers — forced the agent to walk through actual logic, not paraphrase
- Over-repetitive citation phrasing — let the agent cite naturally, once per claim

**Performance/infra fixes** found during this phase:
- Embedding model singleton (was reloading sentence-transformers weights on every search_codebase call)
- Startup warm-up: FastAPI lifespan + Celery worker_process_init both preload the embedding model before accepting traffic, so the first real request isn't the slow one
- `docker-compose.dev.yml` (bind mount + --reload) for fast local iteration without full rebuilds, kept deliberately separate from what EC2 runs

**Frontend UX fixes** found during this phase:
- Real React Router navigation (was a hand-rolled state machine with no real URLs) — browser back/forward and reload now work correctly
- JWT persisted in localStorage via AuthContext (reload no longer forces re-login) — replaced in hardening with httpOnly cookies; documented as the older decision for the historical record
- Loading/busy states for reingest and "new chat" (previously: buttons stayed clickable mid-operation, silent hangs with no feedback)
- Reorganized frontend into `pages/` + `lib/`, removed dead Vite scaffold assets

**Other bugs caught by hands-on use** (not hypothetical edge cases):
- nginx serving the SPA build had no fallback route — reloading on any non-root path (e.g. deep in a chat thread) 404'd. Fixed with `try_files $uri /index.html` in a proper `nginx.conf`.
- 401s (expired/invalid token) failed silently instead of redirecting to login — added a shared `authFetch` wrapper in `api.js` that hard-redirects on 401, applied to every authenticated call.
- Login had no loading state, masking Neon's cold-start latency as a dead, unresponsive button.
- Redis had no persistent volume — chat memory didn't survive `docker compose down` (not just `-v`). Fixed by mounting a named volume at `/data`.
- The repo_id context prefix injected into every message for the agent's benefit was leaking into displayed history text (visible only on reload, since the optimistic first render was clean) — stripped via regex in the display layer only, agent still receives the full prefixed text.
- Frontend never fetched prior messages on mount at all — Chat.jsx started from an empty array every time, regardless of whether Redis had real history. Added `GET /threads/{thread_id}/messages` (via LangGraph's `aget_state`) + load-on-mount in Chat.jsx.

## Phase 2.5 — Repo identity & multi-conversation support

*(added mid-build, not in original plan)*

Surfaced while discussing a "reingest" button: `job_id` was being used as
the stable identity for both retrieval scoping (`search_codebase`/`get_file`)
and chat threads, but ingestion dedup already keys on `repo_id`.
Re-ingesting would silently orphan any chat thread still pointing at the
old `job_id`. Fix is architectural, not a patch:

- [x] Switch `search_codebase` / `get_file` / clone directory to key off `repo_id` instead of `job_id`
- [x] `ingested_repos` becomes one row per repo (upsert on reingest), not one row per run
- [x] `POST /repos/reingest` endpoint
- [x] New `chat_threads` table (`repo_id`, `user_id`, `thread_id`, `title`, timestamps)
- [x] Endpoints to list/create chat threads for a repo
- [x] Frontend: reingest button per repo; clicking a repo shows a thread list + "new chat", not one fixed conversation
- [x] Auto-generated chat titles (short LLM summary of the first message) + manual rename with explicit save/cancel
- [x] Backend guard: 409 if a reingest is requested while one is already queued for the same repo

## Phase 3 — Security / multi-tenancy

- [x] Per-user rate limiting / usage quotas (protect LLM quota + cost)
- [x] Private repo support via GitHub OAuth

**Rate limiting** — hand-rolled Redis fixed-window counter (`INCR+EXPIRE`),
per-user, differentiated limits for chat vs. ingest. Two real bugs found
and fixed:
- `Depends(rate_limit(..., settings.x, ...))` captures a resolved int at
  import time, not a live reference — monkey-patching `Settings` afterward
  had no effect. Fixed by passing the attribute *name* and doing
  `getattr(settings, ...)` fresh per request.
- `chat()`'s retry loop could fall through with `result` unset on a
  non-quota exception, crashing with `UnboundLocalError` instead of
  returning a clean error message.

**Private repo via GitHub OAuth** — account linking (not login) via
state-correlated redirect flow (Redis-backed, since JWT can't survive a
top-level browser navigation to GitHub and back). Token fetched fresh
from Postgres inside the Celery task, never passed through the task
queue.

**Real bug + fix worth remembering** — first attempt used a plain
`contextvar` to give the `list_good_first_issues` tool access to the
user's GitHub token without exposing it to the LLM. This silently
failed — LangGraph's ToolNode runs sync tools in a background thread
pool, and `contextvar` doesn't propagate across that boundary
automatically. Replaced with LangChain's purpose-built mechanism:
`context_schema` + `ToolRuntime[Context]`, passed as an explicit
argument through the whole invocation rather than relying on ambient
thread-local state.

**Other fixes this phase:**
- Renamed `GITHUB_*` env vars to `GH_*` (GitHub Actions rejects `GITHUB_`-prefixed secret/variable names)
- Frontend: GitHub connection status badge + connect button + post-redirect confirmation banner

## Phase 4 — Agent / RAG depth

- [x] Hybrid search (BM25 + vector) instead of pure similarity
- [x] Fix the entity-conflation observation from Phase 1
- [x] Additional tools (find_definition, find_references, list_recent_changes, find_tests_for, read_file_section, list_dependencies)
- [x] Small evaluation harness to actually measure retrieval quality, not just eyeball it

**Eval harness** (`backend/eval/`) — side-by-side comparison of
`vector_only`, `multi_query`, and `hybrid` retrievers with MRR, Recall@5,
avg latency budget (1500ms with `over budget` flag), per-case detail, and
a gitignored JSON artifact for cross-session comparison. Embedding-model
warmup added so cold-start costs (15s+) don't pollute steady-state
latency numbers. Run manually against an already-ingested repo:

```bash
cd backend
python -m eval.run_eval <repo_id>
```

**Hybrid search** (`hybrid_search` in `vectorstore.py`) — BM25 index
built once per repo and cached in-process, fused with vector results via
weighted reciprocal rank fusion (`VECTOR_WEIGHT=1.0`, `BM25_WEIGHT=0.7`).
Cheap routing heuristic skips BM25 for queries with file paths or ≤3
tokens. Hybrid wins on the parked vague-query case ("what is this repo
about" goes from RR=0.5 to RR=1.0).

**Eval results on RepoSage self-ingest** — 13 cases in `eval/test_cases.py`
(the 4 tool-coverage and 1 dedup-invariant cases are mostly documentation
and aren't measured by the retrieval harness). Steady-state ordering:
`vector_only` ≈ `multi_query` on MRR, with `hybrid` slightly behind on
MRR but tied on R@5. `multi_query` is ~25x slower than `vector_only` for
no measured benefit on this benchmark — worth a separate look at
deprecating the LLM-based expansion.

**Tuning attempts** — 1.5:1.0 (vector weighted higher) and 1.0:0.7
(current default, BM25 weighted lower) were both tried and the MRR
ordering stayed the same. Real blocker was `eval/test_cases.py` showing
up as a top hit on every BM25 query (contains literal query strings
verbatim). Structural fix needed (don't index test/eval files in the
BM25 corpus, or strip query strings from chunks) — not a
retriever-weight problem.

**Entity-conflation fix** (`chunker.py`) — per-file 5-shingle minhash
dedup drops near-duplicate chunks before they reach the vector store.
60% shingle overlap threshold catches verbatim and lightly-paraphrased
duplicates while leaving unrelated chunks that share vocabulary alone.
Unit tests verify 4 cases (identical, unrelated, short, paraphrased) —
all pass when run with the function in isolation.

**Additional tools** (`tools.py`) — `find_definition`, `find_references`,
`list_recent_changes`, `find_tests_for`, `read_file_section`,
`list_dependencies`. Extracted `_safe_repo_path` helper used by 3 tools.
System prompt updated to document when to use each. Eval cases added for
tool coverage (documentation only — agentic eval needed to measure tool
selection quality end-to-end).

**Infra bug fixed along the way** — `docker-compose.yml` had
`chroma_data:/chroma/chroma` but `chromadb/chroma:latest` 1.x writes to
`/data`. Volume was silently ignored; every container recreate wiped
the index even though we thought we had persistence. Mount corrected
to `/data`.

**Patterns/lessons learned**:
- Weighted RRF vs. unweighted RRF — the weighting buys nothing on this benchmark; the corpus noise is the problem.
- f-string regex `\.` produces `SyntaxWarning`; raw-string-extract the pattern.
- `_dedupe_chunks` needed to run per-file to avoid conflating cross-file references with cross-section duplicates.

## Polish — UI/UX & streaming

After Phases 1–4 shipped, the surface area stopped changing shape enough
to justify a UI/UX pass. The polish phase happened in several sweeps over
2026-08-01 / 2026-08-02.

**Initial design pass (2026-08-01, one-shot)** — full design system
introduced:
- Two themes (dark primary with denim blue, light paper)
- Fraunces (display) + Inter (body) + JetBrains Mono (mono)
- Custom Tailwind v4 tokens exposed via `@theme` (`bg-paper`,
  `text-ink`, `text-accent`, `bg-elevated`, `text-success`, etc.)
- Prompt-bar as a signature element across every page
- shadcn-style `Button` with CVA variants (`primary` / `ghost` / `sm` /
  `default` / `link`)
- Applied to Landing, Auth, Dashboard, Ingest, ThreadList, Chat, Message

**Subsequent sweeps (same day)** — re-verified finding #21 (CSS token
regression) was already closed; applied ~15 remaining functional-polish
fixes. Deferred decisions kept in place: accent stays blue, Button left
as-is, GitHub badge bug deferred.

**Streaming polish (2026-08-01 → 2026-08-02)** — three production issues
reported right after the third-pass sweep shipped, each fixed in turn:

1. **Tool-call syntax leaking as plain text.** Llama 3.3 70B via Groq
   occasionally emits `<function>search_codebase{...}</function>` as
   prose instead of as a structured tool call, and the markup leaks to
   the user as raw HTML-looking text. Fixed in two layers:
   - Backend `agent.py` — added "Tool calling mechanics" section to
     `SYSTEM_PROMPT` explicitly forbidding text-form tool calls; added
     `_LEAKED_CALL_RE` regex scrubber in `chat_stream()` that strips
     leaked `<function|tool|invoke|action>…</…>` markup from yielded
     text before it reaches the user.
   - Frontend unchanged — scrub happens at the streaming boundary.

2. **Streaming typewriter "rest jumps in" bug.** First 4-5 lines typed
   correctly, then the rest of the response dumped in all at once.
   Several iterations:
   - Per-character `setTimeout` chain → failed
   - Single persistent `setInterval` per Message draining a queue →
     still dumped after 4-5 lines
   - Architecture split: plain text while streaming, swap to
     ReactMarkdown on stream end → no improvement
   - `useLayoutEffect` with no deps array in `MessageList.jsx` →
     improved, but the upstream cause is upstream: typewriter state
     lives inside `Message`, so `MessageList` doesn't re-render on
     every char-drain. An effect keyed on `messages` only fires when
     a new chunk arrives from the server.
   - **Real fix:** `ResizeObserver` on the inner content wrapper in
     `MessageList.jsx`. The observer watches the real DOM node's box
     size and fires on every layout change regardless of which
     component's state triggered it — that's the one thing that's
     actually in sync with what the user sees growing on screen.
     Direct assignment (`el.scrollTop = el.scrollHeight`), not smooth
     scroll, because the observer can fire dozens of times a second
     while typing and stacking smooth-scroll animations causes visible
     stutter. User confirmed: "Works."

3. **Streaming dump fix (2026-08-02)** — the earlier character-rate
   drain approach was set aside in favor of a word-drain with a single
   `setInterval` at 45ms (~22 words/sec), keeping whitespace boundaries
   intact and splitting only very long words (>40 chars) into quarter-
   chunks so they don't sit on the screen for an entire tick. The drain
   rate is now bounded by tick frequency, not by chunk-arrival timing.
   The `ResizeObserver` no-deps fix in MessageList is what makes the
   auto-scroll keep up with the character-by-character growth.

4. **LaTeX rendering in agent responses.** Math like `$O(n \log n)$`
   was showing as raw LaTeX text. Added `remark-math@^6.0.0` +
   `rehype-katex@^7.0.1` + `katex@^0.16.11` and wired into
   `Message.jsx`'s ReactMarkdown. Updated `SYSTEM_PROMPT` to
   encourage math notation. The streaming/not-streaming split
   handles this for free — raw `$...$` is readable while typing via
   `whitespace-pre-wrap`, rendered properly when the stream ends.

**Landing refresh (2026-08-02)** — brought the landing closer to the
intended design:
- New `frontend/src/lib/copy.js` — single source of truth for `TAGLINE`,
  `REPO`, `PORTFOLIO`, `CONTACT`
- Hero tightened: bigger CTA (new `lg` Button size variant), tighter
  spacing; the `TAGLINE` shows in the hero's `$ TAGLINE` eyebrow line, not
  in the global PromptBar (the PromptBar's `default` case intentionally
  returns `""` so the global header stays quiet on `/` while the Landing
  owns its own copy)
- Ghosted REPOSAGE wordmark between hero and how-it-works band —
  faded at 8% opacity, scaled fluidly via `clamp()`
- Horizontal marquee: the wordmark animates left-to-right (28s loop,
  linear, infinite) with two copies inside the track for seamless
  looping. The whole band is `aria-hidden` — pure atmosphere, not content.
  The `prefers-reduced-motion` media query already silences the animation.
- Footer reworked into a 3-column grid: wordmark, quick links
  (github, portfolio, contact), copyright. Container widened to
  `max-w-7xl` to align with the hero.
- The Landing hero renders its own in-page `PromptBar` (the eyebrow line
  `$ TAGLINE`) as a content element, not as a duplicate of the global
  header. There is exactly one global header and it shows on every route.

**Known issue parked** — "Dumpy jump": occasional mid-stream dumps
where the typewriter stalls for a few seconds then a large chunk
appears all at once. Likely a server-side chunking issue (LLM emits a
large delta, the animation queue can only drain as fast as it ticks).
The word-drain at 45ms in (3) reduces but does not eliminate this
behavior; if it becomes a real problem, candidates are: throttle the
typewriter to fixed chars-per-tick with smoothing on the parent
position when the bubble grows faster than the animation.

## Hardening — pre-OSS pass (2026-08-03 → 2026-08-04)

A focused sweep ahead of open-sourcing the repo. Three real problems
were closed in one pass — each was the kind of thing a recruiter or a
contributor would hit in the first five minutes of looking.

### Ingest progress now streams via SSE (was polling)

Three concrete issues with the old `/status/{job_id}` polling pattern:

1. **Polling never stopped on stuck tasks.** If the Celery worker died
   mid-flight (OOM kill, container restart, host reboot) without
   reporting FAILURE, the task sat in PENDING/STARTED forever and the
   user saw an infinite "ingesting" badge.
2. **Large repos could OOM the worker** — `ingest_repo_task` had no
   `time_limit`. A huge repo could pin the worker for hours.
3. **Polling was wasteful** — 1 request every 2s for the entire ingest.

Replaced with:

- **New SSE endpoint** `GET /ingest/stream/{job_id}?token=...` in
  `backend/app/api/routes.py`. Subscribes to Redis pub/sub channel
  `ingest:{job_id}`, sends an immediate DB snapshot on connect, then
  forwards live events. Closes on terminal state, 90s of silence, or
  client disconnect. Token via query string — EventSource can't set
  custom headers, same pattern as `/auth/github/login`.
- **Celery task timeout** — `time_limit=900` / `soft_time_limit=840`.
  `SoftTimeLimitExceeded` caught separately so the DB row goes to
  `failed` and a final SSE event fires before the hard kill.
- **DB-as-source-of-truth** — `/status/{job_id}` rewritten to read from
  `IngestedRepo.status` (lowercase: `queued` / `running` / `success` /
  `failed`), not `celery.result.AsyncResult`. Closes the long-standing
  ambiguity where unknown job IDs and still-queued jobs both reported
  `PENDING`. The task writes `running` at task start — closes the gap
  where a worker crash left the row stuck at `queued` forever.
- **30s heartbeat thread** in `pipeline.ingest_repo()` (`_heartbeat_loop`)
  publishes `running` every 30s, stopped via `threading.Event` on
  every exit path (success / exception / timeout). This is what keeps
  the SSE watchdog from firing during legitimate long ingests — without
  it, 90s of "no events" would always mean "still running" rather than
  "worker dead."
- **`events.publish_status` helper** — sync Redis client in
  `backend/app/ingestion/events.py`, lazy-init on first use, failures
  swallowed (publish is best-effort; the DB row is the truth).

Frontend:

- **`streamIngestStatus(jobId, onEvent)`** in `frontend/src/lib/api.js` —
  EventSource consumer; on stream error, surfaces a final
  `{ state: "error" }` event and closes (no auto-reconnect — wrong for a
  terminal stream).
- **`Ingest.jsx`** — `setTimeout(poll, 2000)` chain replaced with a
  `useEffect` that opens the stream when `jobId` is set and closes on
  unmount.
- **`Dashboard.jsx`** — `pollStatus` capped at 15 polls × 2s = 30s for
  reingests kicked off during the current session. Stopped auto-polling
  rows that were already `queued` on page load — those rows now show
  the existing reingest button as the actionable path (their SSE stream
  is long dead; polling was just hiding that).

Verification: Python AST parses cleanly across all 4 backend files.
`npm run lint` → 12 errors / 3 warnings (matches pre-change baseline,
no new ones). `npm run build` → success.

**Not in scope** — large-repo memory pressure in the embedding
pipeline. That's a separate, structural concern (chunked embedding,
streaming writes) and gets a follow-up GitHub issue.

### JWT dual-token auth with silent refresh

Was a single `access_token` JWT persisted to localStorage with a 60min
TTL. Expired-token UX was: silent 401 → redirect to login → re-type
password. A "remember me" experience was the missing piece for a
real product.

- **Access + refresh tokens** with **separate secrets** and
  **separate TTLs** (60min / 7 days). Both carry a `type` claim
  (`access` / `refresh`) so an access token can't be replayed against
  the refresh endpoint or vice versa.
- **Refresh token rotation** — every `/refresh` call issues a NEW
  refresh token, hashes and persists it on the `users.refresh_token_hash`
  column, invalidating the old one. A leaked refresh token is
  single-use: the legitimate user's next refresh attempt fails,
  surfacing the compromise.
- **bcrypt SHA-256 pre-hash** for refresh tokens. JWT refresh tokens
  routinely run 200-400 bytes, well past bcrypt's 72-byte limit. The
  helper SHA-256s the token first (digest = 64 bytes hex → 32 bytes
  binary), then bcrypts the digest. The full entropy of the original
  token survives inside the bcrypt input.
- **Frontend single-flight refresh** — `authFetch` wraps every
  authenticated call; on 401 it calls `refreshTokens()`. If five
  requests 401 at once, only ONE `/refresh` fires — the rest reuse
  the same in-flight Promise. Avoids the "thundering refresh" race
  where the second refresh fails because the first one rotated the
  token the second one was still holding.
- **LoginGate** for `/login` — silently refreshes and navigates to
  `/dashboard` if the user lands on `/login` with a valid refresh
  token but no access token. Falls through to `<Auth />` only on
  refresh failure.

**Files** — `backend/app/core/config.py` (refresh settings),
`backend/app/core/security.py` (type-claim decoders),
`backend/app/models/user.py` (refresh_token_hash column),
`backend/app/api/auth.py` (`/refresh` route + SHA-256 helpers),
`frontend/src/lib/api.js` (single-flight Promise),
`frontend/src/context/AuthContext.jsx` (both tokens in state),
`frontend/src/App.jsx` (LoginGate).

### Frontend polish: toast sweep, chat redesign, scrollbar, icons

- **Toast sweep** — replaced 8 ad-hoc error/notice patterns across
  `Auth`, `ThreadList`, `Dashboard` with `pushToast({ kind, message })`.
  Login success toast was the most user-visible fix (was missing
  entirely; user reported it). Toast size bumped to `max-w-md`, x
  button hit area enlarged, slide-in animation added (220ms with
  `cubic-bezier(0.16, 1, 0.3, 1)`).
- **`cursor-pointer` on every Button** — added once to the base CVA
  class in `frontend/src/components/ui/button.jsx`; covers all 17 call
  sites. Hovering a button now shows the cursor change that says "yes,
  this is clickable."
- **Save/cancel buttons → Lucide icons** — `ThreadList`'s rename flow
  used `save` / `cancel` text buttons; switched to Lucide `Check` /
  `X` icons with explicit `aria-label`s. Less visual noise; the row
  already has plenty of text.
- **Open-canvas Chat** — removed the wrapping card around the chat
  view; messages now live directly on the page canvas. Input is a
  single floating pill at the bottom (`bg-elevated rounded-xl border
  border-rule focus-within:border-accent/60`). The pattern Claude /
  ChatGPT use — open whitespace, hairline rule that only thickens on
  focus.
- **Slim transparent scrollbar** — global rule on `html`/`body` plus
  an opt-in `.scrollbar-thin` class. The native OS scrollbar is opaque
  and reads as a hard rectangle against the paper background; this
  replaces it with a 6px-wide track that's transparent by default and
  shows a half-muted thumb only on hover. Both webkit and Firefox
  selectors (webdev note: `scrollbar-color: transparent transparent`
  is the Firefox equivalent; there's no separate `-moz-` prefix
  needed in modern Firefox).

### Auth → httpOnly cookies (XSS-immune, CSRF-defended)

Was the deliberate-but-wrong portfolio-scale tradeoff called out in
Phase 2's notes: JWT in `localStorage`, readable by any JS that runs on
the page. A malicious or buggy npm dep, a reflected XSS in a future
chat-rendering library, a `dangerouslySetInnerHTML` mistake — any one
of them would exfiltrate both tokens and own the user. The thing a
security-conscious reviewer flags first.

Migration:

- **Two cookies** — `reposage_token` (60min, access) and
  `reposage_refresh` (7d, refresh) — both `HttpOnly` (JS can't read
  them) + `SameSite=Lax` (CSRF defense: browsers won't send them on
  cross-origin POST/PUT/DELETE) + `Secure` in prod (`COOKIE_SECURE=true`,
  on by default outside dev). `SameSite=Lax` is the entire CSRF
  defense — no separate token needed since the API is JSON over
  POST/GET from a single origin.
- **Same-origin in dev** — Vite proxy for `/api/*` → `http://localhost:8000`
  so the browser sees one origin. Without this, `SameSite=Lax`
  cookies wouldn't ride on cross-origin fetches and we'd have to use
  the `SameSite=None; Secure` combo (which only works over HTTPS and
  opens a larger CSRF surface). In prod the same routing happens at
  the nginx layer.
- **Real `/logout` endpoint** — clears `User.refresh_token_hash` so
  the JWT is unredeemable even if a stale cookie is replayed, AND
  deletes both cookies via `Set-Cookie ... Max-Age=0`. Catches the
  shared-computer logout case that the old client-only logout missed.
- **CORS scoped to explicit origins** — `allow_credentials=True`
  requires a non-wildcard list. `http://localhost:5173` +
  `http://localhost:8000` in dev; the prod origin in prod.
- **`AuthContext` rewritten** — drops `token` / `refreshToken` state
  entirely. The context now exposes `isAuthenticated` + `authChecked`
  + `checkAuth` + `logout`. Auth gating is decided by a silent
  `/refresh` on mount (via a small bootstrap effect in `App.jsx`),
  not by reading localStorage. Removes the pre-step bug where the
  refresh token was being thrown away at login because
  `login(result.access_token)` passed only the access token.
- **SSE + GitHub OAuth switch to cookies** — `EventSource(url,
  { withCredentials: true })` and a top-level navigation to
  `/api/auth/github/login` both ride the cookie automatically now;
  the `?token=` query strings are gone (no tokens in URLs, no tokens
  in nginx access logs).

Real bug found and fixed during the migration — the `/logout` route's
`Depends(get_current_user_from_cookie)` was evaluated at module-load
time, but the function was defined *below* the route in `auth.py`.
On cold start the import cascade (routes.py → rate_limit.py →
auth.py) exploded with `NameError`. Fix: hoist both auth dependencies
to the top of the module, with a comment explaining the load-order
trap. Caught by `pytest tests/test_logout.py` on the first run.

**Files** —
`backend/app/core/config.py` (cookie + CORS settings),
`backend/app/core/security.py` (cookie helpers),
`backend/app/api/auth.py` (rewired `/login` + `/refresh` to set
cookies, new `/logout`, hoisted dependencies),
`backend/app/api/routes.py` (every authenticated route switched to
`get_current_user_from_cookie`; SSE and GitHub OAuth use the cookie
dependency instead of `?token=`),
`backend/app/core/rate_limit.py` (rate-limit dependency switched to
the cookie path too),
`backend/app/main.py` (CORS with explicit origins + `allow_credentials=True`),
`frontend/vite.config.js` (added the `/api/*` proxy),
`frontend/src/lib/api.js` (rewrote `authFetch` + `refreshTokens` to
send `credentials: "include"` and never read localStorage; SSE drops
`?token=`),
`frontend/src/context/AuthContext.jsx` (no more token state),
`frontend/src/App.jsx` (LoginGate + RequireAuth gate on
`isAuthenticated` / `authChecked`; silent `/refresh` on mount),
`frontend/src/pages/Auth.jsx` + every page consumer (drop `useAuth().token`,
all API calls drop the token argument),
`backend/tests/test_auth.py` + `test_protected_routes.py` +
`test_repo_management.py` + `test_rate_limit.py` (drop
`Authorization: Bearer` headers — TestClient attaches cookies from
the jar automatically),
`backend/tests/test_logout.py` (NEW — covers logout, refresh rotation,
and post-logout refresh rejection).

Verification: 34/34 pytest tests pass (31 prior + 3 new logout
tests). `npm run lint` → 12 errors / 0 warnings (matches the prior
baseline). `npm run build` → success.

## Phase 5 — Ops maturity (next)

- [x] Multi-stage frontend Dockerfile (build inside the image, not a manual pre-step) — already shipped with the landing refresh; `frontend/Dockerfile` has a `node:22-alpine` build stage that runs `npm run build`, then a `nginx:alpine` runtime stage that copies the dist into `/usr/share/nginx/html`. No manual pre-step needed.
- [ ] Move off manually-managed EC2 to Render (or similar) for always-on hosting
- [ ] Auto-deploy on merge to `main`

## Future — feature work

- [ ] Per-repo chat shell with resizable thread aside (ChatGPT-style
      layout; would use `react-resizable-panels`)
- [ ] Search/filter inside a repo's thread list
- [ ] Per-token UI polish (smoother mid-stream handling on the
      assistant bubble) — word-drain at 45ms tick in place; the
      "dumpy jump" still surfaces occasionally under large server
      deltas, see the parked issue in the Polish section

## Infra decisions log

| Decision | Choice | Why |
|---|---|---|
| Postgres hosting | Neon (managed) | Free tier auto-resumes on query (vs. Supabase's manual restore-after-pause); leaner since we only needed Postgres |
| Vector DB hosting | Self-hosted Chroma (Docker service) | Already working, already debugged a real concurrency bug in it; abstracted behind `get_vectorstore()` for an easy future swap |
| Agent memory | Redis (`AsyncRedisSaver`, Redis Stack) | Survives restarts, shareable across replicas; async variant required once true token streaming was added |
| LLM provider | Gemini (default) with Groq as alt, pluggable via `LLM_PROVIDER` | Gemini 2.5 Flash-Lite is fine in production with billing enabled; Groq was used heavily during development for higher free-tier quota and lower latency |
| Auth secret naming | `GH_*` (not `GITHUB_*`) | GitHub Actions rejects `GITHUB_`-prefixed secret/variable names |
| Auth token storage | httpOnly cookies (`reposage_token`, `reposage_refresh`) with `SameSite=Lax` | XSS-immune (JS can't read httpOnly); CSRF is the entire defense for the cookie flow since `SameSite=Lax` blocks cross-origin POST/PUT/DELETE. Dev runs same-origin via Vite proxy; prod is same-origin via the nginx edge. Refresh tokens rotate on every use; bcrypt SHA-256 pre-hash to stay under the 72-byte limit. |
| Streaming chat | LangGraph `astream` + `ResizeObserver` auto-scroll on the message content wrapper | Real fix found after several iterations; see the streaming polish section above |
| Tool context | `context_schema` + `ToolRuntime[Context]` | LangChain's purpose-built mechanism; `contextvar` does not work because LangGraph's ToolNode runs sync tools in a background thread pool |
