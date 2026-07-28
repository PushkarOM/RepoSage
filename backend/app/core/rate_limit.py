from fastapi import Depends, HTTPException, Request, status
from app.api.auth import get_current_user
from app.core.config import settings


def rate_limit(key_prefix: str, limit_attr: str, window_seconds: int):
    """
    Enforces getattr(settings, limit_attr) requests per window_seconds,
    per authenticated user, via a Redis fixed-window counter.

    limit_attr is a string naming the Settings field, looked up fresh
    via getattr() on every request -- not a resolved int captured once
    when the route module is imported. Passing the resolved value
    directly (Depends(rate_limit("chat", settings.rate_limit_chat_per_day,
    ...))) captures a disconnected plain int at import time; nothing
    afterward (including a test's monkeypatch) can affect it, since it's
    no longer a live reference to the Settings object at that point.
    """
    async def dependency(request: Request, current_user: str = Depends(get_current_user)):
        limit = getattr(settings, limit_attr)
        r = request.app.state.redis
        key = f"ratelimit:{key_prefix}:{current_user}"
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, window_seconds)
        if count > limit:
            ttl = await r.ttl(key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for this action. Try again in {ttl} seconds.",
            )
    return dependency
