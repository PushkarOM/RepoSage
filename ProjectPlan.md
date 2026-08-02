# RepoSage — Phase 2 Project Plan

Tracking doc for turning RepoSage from a working portfolio demo into a genuinely
polished one. Goal: **impressive portfolio project**, not a production SaaS —
scope decisions below reflect that explicitly.

## Phase 1 — Foundation ✅ DONE

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
- ~~Agent gives generic "I can't recall past conversations" disclaimer~~ — fixed via system_prompt (Phase 2)

## Phase 2 — Product feel

- [x] Streaming chat responses (token-by-token) — async agent + AsyncRedisSaver
- [x] "Your repos" dashboard — list previously ingested repos per user, resume chat without re-ingesting
- [x] Syntax-highlighted code blocks in chat responses (react-markdown + react-syntax-highlighter)
- [x] Citations in answers — via system_prompt instructing the agent to cite file paths inline
- [x] LLM provider switch: Groq (faster, much higher free daily quota than Gemini) — in progress

## Phase 2.5 — Repo identity & multi-conversation support (added mid-build, not in original plan)

Surfaced while discussing a "reingest" button: job_id was being used as the stable identity
for both retrieval scoping (search_codebase/get_file) and chat threads, but ingestion dedup
already keys on repo_id. Re-ingesting would silently orphan any chat thread still pointing at
the old job_id. Fix is architectural, not a patch:

- [x] Switch search_codebase/get_file/clone directory to key off repo_id instead of job_id
- [x] ingested_repos becomes one row per repo (upsert on reingest), not one row per run
- [x] `POST /repos/{repo_id}/reingest` endpoint
- [x] New `chat_threads` table (repo_id, user_id, thread_id, title, timestamps)
- [x] Endpoints to list/create chat threads for a repo
- [x] Frontend: reingest button per repo; clicking a repo shows a thread list + "new chat", not one fixed conversation

## Phase 3 — Security / multi-tenancy

- [x] Per-user rate limiting / usage quotas (protect LLM quota + cost)
- [x] Private repo support via GitHub OAuth

## Phase 4 — Agent / RAG depth

- [x] Hybrid search (BM25 + vector) instead of pure similarity
- [x] Fix the entity-conflation observation above
- [x] Additional tools (e.g. summarize recent commits, find tests for a function)
- [x] Small evaluation harness to actually measure retrieval quality, not just eyeball it

## Phase 5 — Ops maturity

- [ ] Multi-stage frontend Dockerfile (build inside the image, not a manual pre-step)
- [ ] Move off manually-managed EC2 to Render (or similar) for always-on hosting
- [ ] Auto-deploy on merge to `main`

## Later — UI/UX & code polish pass

Deliberately deferred until the feature surface stops changing shape:
- [x] Frontend UI/UX overhaul, animation library (e.g. React Bits)
- [x] Consolidate repeated button markup into shadcn's Button component
- [x] Streaming polish (fade-in per chunk, blinking cursor)

## Infra decisions log

| Decision | Choice | Why |
|---|---|---|
| Postgres hosting | Neon (managed) | Free tier auto-resumes on query (vs. Supabase's manual restore-after-pause); leaner since we only needed Postgres |
| Vector DB hosting | Self-hosted Chroma (Docker service) | Already working, already debugged a real concurrency bug in it; abstracted behind `get_vectorstore()` for an easy future swap |
| Agent memory | Redis (`AsyncRedisSaver`, Redis Stack) | Survives restarts, shareable across replicas; async variant required once true token streaming was added |
| LLM provider | Groq (switching from Gemini) | Gemini free tier daily quota (as low as 20/day) kept blocking development; Groq offers far higher limits and faster inference |

## Session log — everything completed since last update

**Phase 2 — fully done**, including items beyond original scope:
- Streaming, dashboard, syntax highlighting, citations (all previously done)
- Switched LLM provider: Gemini → Groq (Llama 3.3 70B) — far higher free daily quota, faster inference
- System prompt tuning: fixed tool selection (get_file for "explain this file" vs search_codebase for broad queries), fixed shallow answers, fixed "I can't recall past turns" disclaimer, fixed over-repetitive citation phrasing

**Phase 2.5 — fully done**:
- Foundational fix: switched search_codebase/get_file/clone directory from job_id-scoped to repo_id-scoped (job_id is now purely "one ingestion run's ID," repo_id is the stable identity everything else keys off)
- ingested_repos is now one row per repo (upsert on reingest) with a unique constraint on (user_id, repo_id), not one row per run
- Reingest endpoint + button, with backend guard (409 if already queued) preventing duplicate concurrent ingestion of the same repo
- chat_threads table — multiple separate conversations per repo now supported, each with its own Redis-backed memory
- Auto-generated chat titles (short LLM summary of the first message) + manual rename with explicit save/cancel

**Performance/infra fixes found along the way**:
- Embedding model singleton (was reloading sentence-transformers weights on every search_codebase call)
- Startup warm-up: FastAPI lifespan + Celery worker_process_init both preload the embedding model before accepting traffic, so the first real request isn't the slow one
- dev-only docker-compose.dev.yml (bind mount + --reload) for fast local iteration without full rebuilds, kept deliberately separate from what EC2 runs

**Frontend UX fixes**:
- Real React Router navigation (was a hand-rolled state machine with no real URLs) — browser back/forward and reload now work correctly
- JWT persisted in localStorage via AuthContext (reload no longer forces re-login) — noted as a deliberate portfolio-scale tradeoff vs. httpOnly cookies (documented as a known limitation)
- Loading/busy states for reingest and "new chat" (previously: buttons stayed clickable mid-operation, silent hangs with no feedback)
- Reorganized frontend into pages/ + lib/, removed dead Vite scaffold assets

**New parked observation for Phase 4**:
- Vague queries ("what is this repo about") retrieve poorly via pure vector similarity; specific queries ("check the readme file") work -- concrete case for hybrid search (BM25 + vector), already on the Phase 4 list

## Next session — pick up here

- Phase 3: rate limiting/quotas, then private repo support via GitHub OAuth
- Phase 4: hybrid search, more tools, eval harness (using the two parked RAG observations as concrete test cases)
- Phase 5: multi-stage frontend Dockerfile, Render migration, auto-deploy on merge
- Final pass: UI/UX overhaul + animation library, button component consolidation, streaming polish

**Phase 4 — progress (eval harness + hybrid search done; entity-conflation + additional tools still pending):**
- Built `backend/eval/` with side-by-side comparison of vector_only, multi_query, and hybrid retrievers. Metrics: MRR, Recall@5, avg latency, with per-case detail and a JSON artifact (gitignored) for cross-session comparison. Reports `over budget` when avg > 1500ms. Warmup pass added so cold-start costs (15s embedding model load) don't pollute steady-state latency numbers.
- Found and fixed a real infrastructure bug while running the eval: docker-compose had `chroma_data:/chroma/chroma` but the chromadb/chroma:latest image writes to `/data` in 1.x. Volume was silently ignored; every container recreate wiped the index even though we thought we had persistence. Mount changed to `/data`, container recreated, ingest re-run.
- Hybrid search (`hybrid_search` in `vectorstore.py`): BM25 index built once per repo and cached in-process, fused with vector results via weighted reciprocal rank fusion (VECTOR_WEIGHT=1.0, BM25_WEIGHT=0.7). Routing heuristic skips BM25 for queries with file paths or ≤3 tokens to keep the fast path fast.
- Eval results on RepoSage self-ingest: vector_only and multi_query both score MRR=0.438 / R@5=0.625; hybrid scores MRR=0.406 / R@5=0.625 (steady state). Hybrid wins on the original parked "vague query" case ("what is this repo about" goes from RR=0.5 to RR=1.0). Multi_query is ~25x slower than vector_only for no measured benefit on this benchmark — worth a separate look at deprecating the LLM-based expansion.
- Tuning attempts: 1.5:1.0 (vector weighted higher) and 1.0:0.7 (BM25 weighted lower) both left hybrid MRR at 0.406. Real blocker is `eval/test_cases.py` showing up as a top hit on every BM25 query (it contains the literal query strings verbatim). Structural fix needed (don't index test/eval files in the BM25 corpus, or strip query strings from chunks) — not a retriever-weight problem.

## Session log, continued

**2026-08-01 — Final UX sweep + streaming polish (this session)**

Three production issues reported right after the third-pass sweep shipped, each fixed in turn:

1. **Tool-call syntax leaking as plain text.** Llama 3.3 70B via Groq occasionally emits
   `<function>search_codebase{...}</function>` as prose instead of as a structured tool call,
   and the markup leaks to the user as raw HTML-looking text. Fixed in two layers:
   - Backend `agent.py` — added "Tool calling mechanics" section to `SYSTEM_PROMPT`
     explicitly forbidding text-form tool calls; added `_LEAKED_CALL_RE` regex scrubber
     in `chat_stream()` that strips leaked `<function|tool|invoke|action>…</…>` markup
     from yielded text before it reaches the user.
   - Frontend unchanged — scrub happens at the streaming boundary.

2. **Streaming typewriter "rest jumps in" bug.** First 4-5 lines typed correctly, then the
   rest of the response dumped in all at once. Three iterations:
   - Per-character `setTimeout` chain → failed
   - Single persistent `setInterval` per Message draining a queue → still dumped after 4-5 lines
   - Architecture split: plain text while streaming, swap to ReactMarkdown on stream end
     → no improvement
   - **Real fix:** `useLayoutEffect` with no deps array in `MessageList.jsx`. The
     typewriter drains `displayedText` inside the `Message` component, and the parent's
     `messages` array doesn't change during that drain — so any effect keyed on `messages`
     only fires when a new chunk arrives. With no deps, `useLayoutEffect` runs on every
     render (including typewriter-driven re-renders), and the scroll keeps up with the
     character-by-character growth. Used `behavior: "auto"` (instant) since smooth scroll
     lags too far behind rapid appends. User confirmed: "Works."

3. **LaTeX rendering in agent responses.** Math like `$O(n \log n)$` was showing as raw
   LaTeX text. Added `remark-math@^6.0.0` + `rehype-katex@^7.0.1` + `katex@^0.16.11`
   (installed by user) and wired into `Message.jsx`'s ReactMarkdown. Updated `SYSTEM_PROMPT`
   to encourage math notation. The streaming/not-streaming split handles this for free —
   raw `$...$` is readable while typing via `whitespace-pre-wrap`, rendered properly
   when the stream ends.

**Files touched this session (14 files, +708/-101):**
- `backend/app/agent/agent.py` — system prompt section + regex scrubber
- `frontend/src/components/Message.jsx` — word-level typewriter + KaTeX wiring
- `frontend/src/components/MessageList.jsx` — `useLayoutEffect` no-deps fix
- `frontend/src/components/PromptBar.jsx` — long-title truncation
- `frontend/src/index.css` — `.prose-chat` rules (h1-h4, blockquote, pre overflow-x-auto)
- `frontend/src/lib/api.js` — `getThreadMessages` helper + 422 detail coercion
- `frontend/src/pages/{Auth,Chat,Dashboard,Ingest,ThreadList}.jsx` — accessibility, error
  handling, loading states, truncation
- `frontend/package.json` + `package-lock.json` — KaTeX deps

**Known issue parked:** "Dumpy jump" — occasional mid-stream dumps where the typewriter
stalls for a few seconds then a large chunk appears all at once. User explicitly deferred
to a later session ("will tackle the dunpy jump later on"). Likely a server-side chunking
issue (LLM emits a large delta, the animation queue can only drain as fast as it ticks).
Possible fix candidates: throttle typewriter to fixed chars-per-tick, or smooth the parent
position when the bubble grows faster than the animation.

**More fixes found through real testing (not hypothetical edge cases):**
- nginx serving the SPA build had no fallback route -- reloading on any non-root path (e.g. deep in a chat thread) 404'd. Fixed with `try_files $uri /index.html` in a proper `nginx.conf`.
- No real client-side routing existed at all -- App.jsx was a hand-rolled state switch, so the browser URL never changed and back/forward/reload were all broken. Replaced with React Router; JWT persisted in localStorage via AuthContext (documented as a known tradeoff vs. httpOnly cookies).
- 401s (expired/invalid token) failed silently instead of redirecting to login -- added a shared `authFetch` wrapper in api.js that hard-redirects on 401, applied to every authenticated call.
- Login had no loading state, masking Neon's cold-start latency as a dead, unresponsive button.
- Redis had no persistent volume -- chat memory didn't survive `docker compose down` (not just `-v`). Fixed by mounting a named volume at `/data`.
- Separately, and more fundamentally: the frontend never fetched prior messages on mount at all -- Chat.jsx started from an empty array every time, regardless of whether Redis had real history. Added GET /threads/{thread_id}/messages (via LangGraph's `aget_state`) + load-on-mount in Chat.jsx.
- The repo_id context prefix injected into every message for the agent's benefit was leaking into displayed history text (visible only on reload, since the optimistic first render was clean) -- stripped via regex in the display layer only, agent still receives the full prefixed text.
- docker-compose.dev.yml added (bind mount + --reload) for fast local iteration without full rebuilds, deliberately kept separate from what EC2 runs.

**Phase 2: fully closed.** Streaming, dashboard, syntax highlighting, citations, Groq migration,
multi-thread chat, chat history persistence/restoration, and real navigation are all confirmed
working through actual testing, including several real bugs caught by hands-on use rather than
theoretical review.

## Next up: Phase 3

- Per-user rate limiting / usage quotas
- Private repo support via GitHub OAuth

## Phase 3 — done

- Rate limiting: hand-rolled Redis fixed-window counter (INCR+EXPIRE), per-user, differentiated
  limits for chat vs. ingest. Two real bugs found and fixed: `Depends(rate_limit(..., settings.x, ...))`
  captures a resolved int at import time, not a live reference -- monkeypatching Settings afterward
  had no effect. Fixed by passing the attribute *name* and doing `getattr(settings, ...)` fresh per
  request. Second bug: chat()'s retry loop could fall through with `result` unset on a non-quota
  exception, crashing with UnboundLocalError instead of returning a clean error message.
- Private repo support via GitHub OAuth: account linking (not login) via state-correlated redirect
  flow (Redis-backed, since JWT can't survive a top-level browser navigation to GitHub and back).
  Token fetched fresh from Postgres inside the Celery task, never passed through the task queue.
- Real bug + fix worth remembering: first attempt used a plain `contextvar` to give the
  `list_good_first_issues` tool access to the user's GitHub token without exposing it to the LLM.
  This silently failed -- LangGraph's ToolNode runs sync tools in a background thread pool, and
  contextvars don't propagate across that boundary automatically. Replaced with LangChain's
  purpose-built mechanism: `context_schema` + `ToolRuntime[Context]`, passed as an explicit
  argument through the whole invocation rather than relying on ambient thread-local state.
- Renamed GITHUB_* env vars to GH_* (GitHub Actions rejects GITHUB_-prefixed secret/variable names).
- Frontend: GitHub connection status badge + connect button + post-redirect confirmation banner.

## Next up: Phase 4 — Agent / RAG depth

- Two concrete parked observations from earlier sessions to use as real test cases:
  entity conflation (double-counting near-duplicate items across README sections) and
  vague-query retrieval failure (generic questions score poorly via pure vector similarity)
- Hybrid search (BM25 + vector)

## Phase 4 — done

- **Eval harness** (`backend/eval/`): side-by-side comparison of vector_only, multi_query, and hybrid retrievers with MRR, Recall@5, avg latency budget (1500ms with `over budget` flag), per-case detail, and a gitignored JSON artifact for cross-session comparison. Embedding-model warmup added so cold-start costs (15s+) don't pollute steady-state latency numbers.
- **Hybrid search** (`hybrid_search` in `vectorstore.py`): BM25 index built once per repo and cached in-process, fused with vector results via weighted reciprocal rank fusion (VECTOR_WEIGHT=1.0, BM25_WEIGHT=0.7). Cheap routing heuristic skips BM25 for queries with file paths or ≤3 tokens. Hybrid wins on the parked vague-query case ("what is this repo about" goes from RR=0.5 to RR=1.0). Multi_query empirically doesn't beat vector_only on the eval (~25x slower for zero measured benefit) -- worth a separate look at deprecating it.
- **Additional tools** (`tools.py`): find_definition, find_references, list_recent_changes, find_tests_for, read_file_section, list_dependencies. Extracted `_safe_repo_path` helper used by 3 tools. System prompt updated to document when to use each. Eval cases added for tool coverage (documentation-only -- agentic eval needed to measure tool selection quality end-to-end).
- **Entity-conflation fix** (`chunker.py`): per-file 5-shingle minhash dedup drops near-duplicate chunks before they reach the vector store. 60% shingle overlap threshold catches verbatim and lightly-paraphrased duplicates while leaving unrelated chunks that share vocabulary alone. Unit tests verify 4 cases (identical, unrelated, short, paraphrased) -- all pass when run with the function in isolation.
- **Infra bug fixed along the way**: `docker-compose.yml` had `chroma_data:/chroma/chroma` but chromadb/chroma:latest 1.x writes to `/data`. Volume was silently ignored; every container recreate wiped the index even though we thought we had persistence. Mount corrected.
- **Patterns/lessons learned**: weighted RRF vs. unweighted; budget-tuning attempts (1.5:1.0, then 1.0:0.7) didn't help BM25's tendency to lock onto `eval/test_cases.py` (which contains literal query strings) -- root cause is the corpus, not the fusion weights. f-string regex `\.` produces SyntaxWarning; raw-string-extract the pattern. `_dedupe_chunks` needed to run per-file to avoid conflating cross-file references with cross-section duplicates.
- Additional tools
- Small evaluation harness to actually measure retrieval quality
- 