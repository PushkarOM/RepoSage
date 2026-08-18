"""
Regression test for the concurrent-/refresh race condition.

Two requests presenting the SAME (pre-rotation) refresh cookie at the same
time used to BOTH get a 200 -- the old flow read the row, bcrypt-verified,
then wrote a new hash, with a real gap between the read and the write.
Whichever write landed second silently won, and the other caller walked
away with a Set-Cookie for a token that no longer matched the DB. The
failure only surfaced later, on that caller's next refresh attempt, as an
unexplained "Invalid refresh token" -- which is exactly the bug report
this test guards against regressing to.

The fix makes rotation a single atomic `UPDATE ... WHERE refresh_token_jti
= :presented_jti` (see app/api/auth.py). Of N concurrent callers presenting
the same starting cookie, exactly one should get a 200; the rest should
get an immediate 401, not a false 200 that breaks later.

DB setup (intentionally NOT the global in-memory StaticPool):

The default `conftest.py` uses an in-memory SQLite + StaticPool, which
shares ONE connection across the process. That's fine for the 34+
ordinary tests where each test runs sequentially on a single thread --
but it cannot model real concurrency: SQLAlchemy's session stashes
thread-local cursor state, so the second thread to grab that single
connection hits `sqlite3.InterfaceError: bad parameter or other API
misuse`. To genuinely simulate 5 concurrent /refresh requests, this
test stands up its own file-backed SQLite DB with a default connection
pool (one connection per request, more like the real Postgres setup),
spawns the TestClient inside each worker thread, and tears it all down
in `finally`. The lifecycle is local to this test on purpose -- the
rest of the suite keeps its fast in-memory setup.
"""
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.main import app


def test_concurrent_refresh_with_same_cookie_has_exactly_one_winner(clear_rate_limit):
    # Start from a clean slate on the rate-limit Redis too, otherwise a
    # counter that survived an earlier run can 429 ivy before the test
    # even gets to /refresh.
    clear_rate_limit("ingest", "ivy")

    fd, db_path = tempfile.mkstemp(prefix="reposage_concurrency_", suffix=".db")
    os.close(fd)

    # File-backed SQLite on a per-thread connection pool is the closest
    # SQLite analogue to production Postgres for this test. Without this,
    # all 5 threads share one connection under StaticPool and the test
    # becomes a structural probe of SQLite's threading instead of the
    # race we're trying to exercise.
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def _override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = _override_get_db

    try:
        # Register + login MUST happen against the same temp DB the
        # concurrent /refresh requests will hit. Each thread then spins
        # up its own TestClient(app) over that shared DB.
        with TestClient(app) as setup_client:
            setup_client.post(
                "/register",
                json={"username": "ivy", "password": "testpass123"},
            )
            setup_client.post("/login", data={"username": "ivy", "password": "testpass123"})
            starting_cookies = dict(setup_client.cookies)

        def fire_refresh(_):
            c = TestClient(app)
            for k, v in starting_cookies.items():
                c.cookies.set(k, v)
            return c.post("/refresh")

        with ThreadPoolExecutor(max_workers=5) as pool:
            responses = list(pool.map(fire_refresh, range(5)))

        statuses = [r.status_code for r in responses]
        assert statuses.count(200) == 1, (
            f"expected exactly one winning /refresh, got statuses={statuses}"
        )
        assert statuses.count(401) == 4, (
            f"expected the other 4 to be rejected immediately, got statuses={statuses}"
        )
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        if os.path.exists(db_path):
            os.unlink(db_path)
