import asyncio
import pytest
import redis.asyncio as redis
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.core.config import settings



# Redis test helpers
async def _clear_rate_limit_key(prefix: str, username: str):
    r = redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )
    await r.delete(f"ratelimit:{prefix}:{username}")
    await r.aclose()


@pytest.fixture
def clear_rate_limit():
    """
    Clear a user's rate-limit counter before a test that needs a
    deterministic rate-limit state.
    """
    def _clear(prefix: str, username: str):
        asyncio.run(_clear_rate_limit_key(prefix, username))

    return _clear



# Test database
#
# Shared in-memory SQLite allows multiple SQLAlchemy connections to access
# the same database.
#
# This is important for test_refresh_concurrency.py, where multiple
# TestClients make requests concurrently from different threads.
#
# Unlike StaticPool, this does NOT force every thread to share one
# sqlite3.Connection object.
#

TEST_DATABASE_URL = "sqlite:///file:testdb?mode=memory&cache=shared"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "uri": True,
    },
)

TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)



# Database fixtures
@pytest.fixture
def db_session():
    """
    Provides a SQLAlchemy session for tests that need direct DB access.
    """
    db = TestSessionLocal()

    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function", autouse=True)
def setup_database():
    """
    Create all tables before each test and drop them afterward.

    Each test therefore starts with a clean database.
    """
    Base.metadata.create_all(bind=engine)

    yield

    Base.metadata.drop_all(bind=engine)



# FastAPI database dependency override
def override_get_db():
    """
    FastAPI dependency override used by TestClient requests.
    """
    db = TestSessionLocal()

    try:
        yield db
    finally:
        db.close()



# Test client
@pytest.fixture
def client():
    """
    TestClient configured to use the isolated test database.
    """
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()