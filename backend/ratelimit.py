"""
Simple in-memory rate limiter — no external dependencies.
Uses a sliding window counter per IP address.
Not shared across multiple workers, but fine for single-process deployments (Railway, Render).
"""
import time
from collections import defaultdict
from threading import Lock
from fastapi import Request, HTTPException

_store: dict[str, list[float]] = defaultdict(list)
_lock = Lock()


def _check(key: str, max_calls: int, window_seconds: int) -> None:
    now = time.monotonic()
    cutoff = now - window_seconds
    with _lock:
        timestamps = _store[key]
        # Drop timestamps outside the window
        _store[key] = [t for t in timestamps if t > cutoff]
        if len(_store[key]) >= max_calls:
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Please wait a moment and try again.",
                headers={"Retry-After": str(window_seconds)},
            )
        _store[key].append(now)


def rate_limit(max_calls: int, window_seconds: int = 60):
    """
    FastAPI dependency. Usage:
        @app.post("/endpoint")
        async def handler(request: Request, _=Depends(rate_limit(10, 60))):
    """
    def dependency(request: Request):
        ip = request.client.host if request.client else "unknown"
        key = f"{ip}:{request.url.path}"
        _check(key, max_calls, window_seconds)
    return dependency
