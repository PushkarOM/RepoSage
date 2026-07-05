from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings



# check_same_thread=False is needed specifically for SQLite + FastAPI,
# since FastAPI can serve a single request across multiple threads
# and SQLite's default driver assumes one thread per connection.
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})

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
