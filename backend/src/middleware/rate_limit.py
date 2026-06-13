"""
In-memory sliding window rate limiter middleware for FastAPI.

Supports per-path limits: auth endpoints get stricter limits.
"""

import time
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


# Path prefix → (max_requests, window_seconds)
PATH_LIMITS: dict[str, tuple[int, int]] = {
    "/api/auth/login":    (5, 60),    # 5 login attempts per minute
    "/api/auth/register": (3, 300),   # 3 registrations per 5 minutes
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 30, window_seconds: int = 60):
        super().__init__(app)
        self.default_max = max_requests
        self.default_window = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

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

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/health"):
            return await call_next(request)

        ip = self._client_ip(request)
        max_req, window = self._get_limits(path)
        now = time.time()
        cutoff = now - window

        key = f"{ip}:{path}"
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
