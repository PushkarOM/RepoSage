from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings


def _build_connect_args() -> dict:
    """
    Per-driver connection kwargs. SQLite needs check_same_thread=False so
    FastAPI can serve a single request across threads. Postgres needs an
    explicit connect_timeout so a wedged Neon pooler doesn't leave
    `db.query()` blocked at the TCP handshake for the OS default
    (~2 min on Linux, ~75 s on macOS). The 5 s budget is generous for
    Neon on a healthy day and short enough to surface a real outage
    as a fast 500 instead of an indefinite hang.

    Without connect_timeout, after a `docker compose down/up` (cold
    pool, no cached connections) the first request that touches the DB
    will silently sit forever if Neon's pooler has a transient blip --
    the symptom looks like "the refresh token is invalid" because the
    frontend's loader never resolves.
    """
    if settings.database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {"connect_timeout": 5}


# check_same_thread=False is needed specifically for SQLite + FastAPI,
# since FastAPI can serve a single request across multiple threads
# and SQLite's default driver assumes one thread per connection.
# pool_pre_ping=True issues a cheap "SELECT 1" on checkout so a server-
# killed idle connection is recycled before our query hits it. pool_recycle
# forces connections back through pre-ping after 280 s -- under Neon's
# ~5 min idle-disconnect window, so a pooled connection that survived
# pre_ping can't then be silently severed before the next checkout.
engine = create_engine(
    settings.database_url,
    connect_args=_build_connect_args(),
    pool_pre_ping=True,
    pool_recycle=280,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """
    FastAPI dependency that yields a DB session and guarantees it's
    closed after the request, even if the route raises. Depends(get_db)
    in a route signature is the standard SQLAlchemy+FastAPI pattern.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
