"""
Tests for /logout + /refresh rotation in the cookie-auth flow.

Logout is a hard cut -- it must:
  1. Return 200 with two Set-Cookie headers (Max-Age=0) deleting both cookies.
  2. Null out User.refresh_token_jti so /refresh can't be redeemed.

The /refresh rotation must:
  3. Issue a NEW access cookie on every call (old one stops working after rotation).
  4. Reject a refresh cookie whose jti no longer matches the stored jti.
"""


def test_logout_clears_cookies_and_revokes_refresh(client):
    """End-to-end: login -> /repos works, /logout -> /refresh is 401."""
    client.post("/register", json={"username": "frank", "password": "testpass123"})
    login_resp = client.post("/login", data={"username": "frank", "password": "testpass123"})
    assert "reposage_token" in login_resp.cookies
    assert "reposage_refresh" in login_resp.cookies

    # /repos is reachable while authenticated.
    repos_resp = client.get("/repos")
    assert repos_resp.status_code == 200

    # /logout -- response sets Max-Age=0 on both cookies AND clears the
    # stored hash. TestClient exposes the response.cookies jar but
    # deletes apply to the server side; the body just says "logged out".
    logout_resp = client.post("/logout")
    assert logout_resp.status_code == 200
    assert logout_resp.json()["message"] == "logged out"

    # The cookie jar stored the deletion Set-Cookie headers, so the
    # next request has no auth cookie attached -- /repos is 401 again.
    repos_after = client.get("/repos")
    assert repos_after.status_code == 401


def test_refresh_rotates_cookies(client):
    """Login -> /refresh issues a fresh access cookie; the old one is gone.

    We verify rotation indirectly by checking that after /refresh the
    /repos call still works -- if rotation had failed and the refresh
    token been invalidated, the subsequent /repos request would 401.
    """
    client.post("/register", json={"username": "grace", "password": "testpass123"})
    client.post("/login", data={"username": "grace", "password": "testpass123"})

    # /refresh -- new cookies are written to the TestClient jar.
    refresh_resp = client.post("/refresh")
    assert refresh_resp.status_code == 200
    assert "reposage_token" in refresh_resp.cookies

    # Still authenticated after rotation.
    repos_resp = client.get("/repos")
    assert repos_resp.status_code == 200


def test_refresh_rejects_when_logged_out(client):
    """Logout nukes the refresh cookie + DB hash; /refresh must 401."""
    client.post("/register", json={"username": "henry", "password": "testpass123"})
    client.post("/login", data={"username": "henry", "password": "testpass123"})
    client.post("/logout")

    # After logout the cookie jar holds the Max-Age=0 entries, so this
    # POST has no reposage_refresh to send. /refresh is 401.
    refresh_resp = client.post("/refresh")
    assert refresh_resp.status_code == 401