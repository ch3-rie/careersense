from collections import defaultdict, deque
from threading import Lock
from time import time
from typing import Optional

from fastapi import HTTPException, Request, status

from app.config import get_settings


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time()
        with self._lock:
            bucket = self._hits[key]
            cutoff = now - self.window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


login_limiter = SlidingWindowLimiter(limit=12, window_seconds=10 * 60)
register_limiter = SlidingWindowLimiter(limit=6, window_seconds=10 * 60)
password_limiter = SlidingWindowLimiter(limit=8, window_seconds=15 * 60)
forgot_limiter = SlidingWindowLimiter(limit=8, window_seconds=10 * 60)
pin_limiter = SlidingWindowLimiter(limit=20, window_seconds=10 * 60)

_force_enabled: Optional[bool] = None


def set_rate_limit_enabled(enabled: Optional[bool]) -> None:
    global _force_enabled
    _force_enabled = enabled


def client_ip(request: Request) -> str:
    settings = get_settings()
    if settings.trust_x_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()[:120]
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def enforce_rate_limit(request: Request, limiter: SlidingWindowLimiter, bucket: str) -> None:
    enabled = get_settings().rate_limit_enabled if _force_enabled is None else _force_enabled
    if not enabled:
        return
    key = f"{client_ip(request)}:{bucket}"
    if not limiter.allow(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please wait a few minutes and try again.",
        )
