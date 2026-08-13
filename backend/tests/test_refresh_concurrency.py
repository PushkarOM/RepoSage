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
"""
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import app


def test_concurrent_refresh_with_same_cookie_has_exactly_one_winner(client):
    client.post("/register", json={"username": "ivy", "password": "testpass123"})
    client.post("/login", data={"username": "ivy", "password": "testpass123"})
    starting_cookies = dict(client.cookies)

    # Each thread gets its own TestClient (its own connection) but starts
    # from the SAME pre-rotation cookies -- simulating two tabs (or a
    # frontend bug) both presenting the same refresh token at once. The
    # `client` fixture already wired up the test DB override on `app`
    # before this test ran, and that override is a module-level dict
    # entry on the shared `app` object, so every TestClient(app) we spin
    # up here inherits it automatically.
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
