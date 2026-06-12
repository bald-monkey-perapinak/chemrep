"""
In-memory sliding window rate limiter middleware for FastAPI.
"""

import time
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 30, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/health"):
            return await call_next(request)

        ip = self._client_ip(request)
        now = time.time()
        cutoff = now - self.window_seconds

        timestamps = self._requests[ip]
        self._requests[ip] = [t for t in timestamps if t > cutoff]

        if len(self._requests[ip]) >= self.max_requests:
            retry_after = int(self._requests[ip][0] - cutoff) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={"Retry-After": str(retry_after)},
            )

        self._requests[ip].append(now)
        return await call_next(request)
