from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.models import user  # noqa: F401
from app.api.routes import router
from app.api.auth import router as auth_router
from app.agent.agent import init_agent, close_agent
import redis.asyncio as redis
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.embeddings import get_embedding_function
    get_embedding_function()

    app.state.redis = redis.from_url(settings.redis_url, decode_responses=True)

    await init_agent()
    yield
    await app.state.redis.aclose()
    await close_agent()


app = FastAPI(title="RepoSage", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(router)


@app.get("/")
def root():
    return {"status": "RepoSage API running"}
