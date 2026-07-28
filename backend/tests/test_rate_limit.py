import asyncio
import redis.asyncio as redis
from app.core.config import settings


async def _clear_rate_limit_key(prefix: str, username: str):
    r = redis.from_url(settings.redis_url, decode_responses=True)
    await r.delete(f"ratelimit:{prefix}:{username}")
    await r.aclose()


async def _fake_chat(*args, **kwargs):
    return "mocked reply"


def test_chat_rate_limit_enforced(client, monkeypatch):
    asyncio.run(_clear_rate_limit_key("chat", "erin"))

    client.post("/register", json={"username": "erin", "password": "testpass123"})
    login_resp = client.post("/login", data={"username": "erin", "password": "testpass123"})
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    monkeypatch.setattr("app.core.config.settings.rate_limit_chat_per_day", 2)
    # Patch where the name is used (routes.py's own `agent_chat` reference),
    # not where it's defined -- and it must be a real async function, since
    # routes.py does `await agent_chat(...)`; a plain lambda returning a
    # string isn't awaitable and would fail differently.
    monkeypatch.setattr("app.api.routes.agent_chat", _fake_chat)

    body = {"repo_id": "owner/repo", "message": "hi"}
    r1 = client.post("/chat", json=body, headers=headers)
    r2 = client.post("/chat", json=body, headers=headers)
    r3 = client.post("/chat", json=body, headers=headers)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
