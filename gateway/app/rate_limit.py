from fastapi import HTTPException

from app.redis_client import client as redis_client

# Fixed-window counter per app key: simple, easy to reason about, and this
# project's scale doesn't need a more precise sliding-window algorithm.
LIMIT = 30
WINDOW_SECONDS = 60


def check_rate_limit(app_id: str) -> None:
    key = f"ratelimit:{app_id}"
    count = redis_client.incr(key)
    if count == 1:
        redis_client.expire(key, WINDOW_SECONDS)

    if count > LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"rate limit exceeded: {LIMIT} requests per {WINDOW_SECONDS}s for app '{app_id}'",
        )
