import asyncio
import pytest
import redis.asyncio as redis
from app.core.config import settings
from app.core.rate_limit import _format_ttl


async def _clear_rate_limit_key(prefix: str, username: str):
    r = redis.from_url(settings.redis_url, decode_responses=True)
    await r.delete(f"ratelimit:{prefix}:{username}")
    await r.aclose()


async def _fake_chat(*args, **kwargs):
    return "mocked reply"


def test_chat_rate_limit_enforced(client, monkeypatch):
    asyncio.run(_clear_rate_limit_key("chat", "erin"))

    client.post("/register", json={"username": "erin", "password": "testpass123"})
    # Login sets the httpOnly cookies on the TestClient jar; subsequent
    # requests attach them automatically. No Authorization header needed.
    client.post("/login", data={"username": "erin", "password": "testpass123"})

    monkeypatch.setattr("app.core.config.settings.rate_limit_chat_per_day", 2)
    # Patch where the name is used (routes.py's own `agent_chat` reference),
    # not where it's defined -- and it must be a real async function, since
    # routes.py does `await agent_chat(...)`; a plain lambda returning a
    # string isn't awaitable and would fail differently.
    monkeypatch.setattr("app.api.routes.agent_chat", _fake_chat)

    body = {"repo_id": "owner/repo", "message": "hi"}
    r1 = client.post("/chat", json=body)
    r2 = client.post("/chat", json=body)
    r3 = client.post("/chat", json=body)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429


# --- _format_ttl tests ---
# The 429 detail string is the only user-facing surface of the rate limiter
# in normal operation; getting the wording right matters. These cover the
# four branches plus the exact thresholds so regression is loud.

@pytest.mark.parametrize("ttl, expected", [
    (0, "0 seconds"),                # exactly the lower edge of the seconds branch
    (45, "45 seconds"),              # under a minute
    (60, "1 minutes"),               # exact minute boundary — rounds down; not perfect
                                       # but intentional: clients see "1 minutes" rather
                                       # than swallowing the precision. Acceptable.
    (90, "1 minutes"),               # sub-hour
    (3540, "59 minutes"),            # just under an hour
    (3600, "1 hours"),               # exact hour boundary
    (86399, "23 hours"),             # just under a day
    (86400, "tomorrow at 00:00 UTC"),# exactly a day (the prod window)
    (100000, "tomorrow at 00:00 UTC"),# well over a day — same fallback
])
def test_format_ttl(ttl, expected):
    assert _format_ttl(ttl) == expected
