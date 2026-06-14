"""
In-memory sliding window rate limiter middleware for FastAPI.

Supports per-path limits: auth endpoints get stricter limits.
Periodic cleanup prevents unbounded memory growth.
"""

import time
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


# Path prefix → (max_requests, window_seconds)
PATH_LIMITS: dict[str, tuple[int, int]] = {
    "/api/v1/auth/login":    (5, 60),    # 5 login attempts per minute
    "/api/v1/auth/register": (3, 300),   # 3 registrations per 5 minutes
}

# Cleanup interval: purge keys older than this many seconds
_CLEANUP_INTERVAL = 300  # every 5 minutes
_MAX_KEY_AGE = 600       # discard entries older than 10 minutes


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 30, window_seconds: int = 60):
        super().__init__(app)
        self.default_max = max_requests
        self.default_window = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup = time.time()

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _get_limits(self, path: str) -> tuple[int, int]:
        for prefix, limits in PATH_LIMITS.items():
            if path.startswith(prefix):
                return limits
        return self.default_max, self.default_window

    def _get_rate_key(self, request: Request, path: str) -> str:
        """Use teacher_id from JWT if available, else fall back to IP."""
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            try:
                from jose import jwt
                from src.config.jwt import get_jwt_secret, ALGORITHM
                token = auth[7:]
                payload = jwt.decode(token, get_jwt_secret(), algorithms=[ALGORITHM])
                teacher_id = payload.get("sub")
                if teacher_id:
                    return f"t:{teacher_id}:{path}"
            except Exception:
                pass
        ip = self._client_ip(request)
        return f"{ip}:{path}"

    def _maybe_cleanup(self) -> None:
        """Remove stale keys to prevent memory leak."""
        now = time.time()
        if now - self._last_cleanup < _CLEANUP_INTERVAL:
            return
        self._last_cleanup = now
        cutoff = now - _MAX_KEY_AGE
        stale_keys = [
            key for key, timestamps in self._requests.items()
            if not timestamps or timestamps[-1] < cutoff
        ]
        for key in stale_keys:
            del self._requests[key]

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/health"):
            return await call_next(request)

        self._maybe_cleanup()

        max_req, window = self._get_limits(path)
        now = time.time()
        cutoff = now - window

        key = self._get_rate_key(request, path)
        timestamps = self._requests[key]
        self._requests[key] = [t for t in timestamps if t > cutoff]

        if len(self._requests[key]) >= max_req:
            retry_after = int(self._requests[key][0] - cutoff) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={"Retry-After": str(retry_after)},
            )

        self._requests[key].append(now)
        return await call_next(request)
