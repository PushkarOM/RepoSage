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
- [x] LLM provider switch: Groq (faster, much higher free daily quota than Gemini)

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

- [ ] Per-user rate limiting / usage quotas (protect LLM quota + cost)
- [ ] Private repo support via GitHub OAuth

## Phase 4 — Agent / RAG depth

- [ ] Fix the entity-conflation observation above
- [ ] Hybrid search (BM25 + vector) instead of pure similarity
- [ ] Additional tools (e.g. summarize recent commits, find tests for a function)
- [ ] Small evaluation harness to actually measure retrieval quality, not just eyeball it

## Phase 5 — Ops maturity

- [ ] Multi-stage frontend Dockerfile (build inside the image, not a manual pre-step)
- [ ] Move off manually-managed EC2 to Render (or similar) for always-on hosting
- [ ] Auto-deploy on merge to `main`

## Later — UI/UX & code polish pass

Deliberately deferred until the feature surface stops changing shape:
- [ ] Frontend UI/UX overhaul, animation library (e.g. React Bits)
- [ ] Consolidate repeated button markup into shadcn's Button component
- [ ] Streaming polish (fade-in per chunk, blinking cursor)

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

## Session log, continued

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
- 