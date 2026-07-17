# RepoSage — Phase 2 Project Plan

Tracking doc for turning RepoSage from a working portfolio demo into a genuinely
polished one. Goal: **impressive portfolio project**, not a production SaaS —
scope decisions below reflect that explicitly.

## Phase 1 — Foundation ✅ DONE

- [x] Migrate SQLite → Postgres (Neon, managed, serverless)
- [x] Alembic migrations wired up, verified with a real schema change (`is_active` column)
- [x] Redis-backed agent memory (`RedisSaver`, via Redis Stack), verified surviving container restarts

**Bugs found & fixed along the way** (worth keeping — good interview material):
- `connect_args` computed correctly but never actually passed to `create_engine()` — classic "fix landed next to the bug, not over it"
- Neon silently drops idle connections (serverless) — fixed with `pool_pre_ping=True`
- `RedisSaver` needs RediSearch/RedisJSON modules — plain `redis:7-alpine` doesn't have them, switched to `redis/redis-stack-server`
- `docker compose restart` vs `docker compose build` confusion — restart doesn't pick up code changes, only rebuild does

**Observations parked for Phase 4** (RAG/agent quality):
- Agent conflates near-duplicate entities across README sections (e.g. "RL Portfolio Optimizer" vs "Reinforcement Learning Portfolio Optimizer" counted as two separate projects)
- Agent gives Gemini's generic "I can't recall past conversations" disclaimer even when conversation history is genuinely present in context — a prompting fix, not a memory bug

## Phase 2 — Product feel (next)

- [ ] Streaming chat responses (token-by-token instead of wait-then-dump)
- [ ] "Your repos" dashboard — list previously ingested repos per user, resume chat without re-ingesting
- [ ] Syntax-highlighted code blocks in chat responses
- [ ] Citations in answers — reference which file/chunk an answer came from

## Phase 3 — Security / multi-tenancy

- [ ] Per-user rate limiting / usage quotas (protect Gemini quota + cost)
- [ ] Private repo support via GitHub OAuth

## Phase 4 — Agent / RAG depth

- [ ] Fix the two observed quality issues above
- [ ] Hybrid search (BM25 + vector) instead of pure similarity
- [ ] Additional tools (e.g. summarize recent commits, find tests for a function)
- [ ] Small evaluation harness to actually measure retrieval quality, not just eyeball it

## Phase 5 — Ops maturity

- [ ] Multi-stage frontend Dockerfile (build inside the image, not a manual pre-step)
- [ ] Move off manually-managed EC2 to Render (or similar) for always-on hosting
- [ ] Auto-deploy on merge to `main`

## Infra decisions log

| Decision | Choice | Why |
|---|---|---|
| Postgres hosting | Neon (managed) | Free tier auto-resumes on query (vs. Supabase's manual restore-after-pause); leaner since we only needed Postgres, not bundled auth/storage |
| Vector DB hosting | Self-hosted Chroma (Docker service) | Already working, already debugged a real concurrency bug in it; Chroma Cloud is a low-cost future swap since the code is already abstracted behind `get_vectorstore()` |
| Agent memory | Redis (`RedisSaver`, Redis Stack) | Survives restarts, shareable across replicas; required Redis Stack specifically for RediSearch/RedisJSON modules |
