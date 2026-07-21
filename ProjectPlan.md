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
- [ ] LLM provider switch: Groq (faster, much higher free daily quota than Gemini) — in progress

## Phase 2.5 — Repo identity & multi-conversation support (added mid-build, not in original plan)

Surfaced while discussing a "reingest" button: job_id was being used as the stable identity
for both retrieval scoping (search_codebase/get_file) and chat threads, but ingestion dedup
already keys on repo_id. Re-ingesting would silently orphan any chat thread still pointing at
the old job_id. Fix is architectural, not a patch:

- [ ] Switch search_codebase/get_file/clone directory to key off repo_id instead of job_id
- [ ] ingested_repos becomes one row per repo (upsert on reingest), not one row per run
- [ ] `POST /repos/{repo_id}/reingest` endpoint
- [ ] New `chat_threads` table (repo_id, user_id, thread_id, title, timestamps)
- [ ] Endpoints to list/create chat threads for a repo
- [ ] Frontend: reingest button per repo; clicking a repo shows a thread list + "new chat", not one fixed conversation

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