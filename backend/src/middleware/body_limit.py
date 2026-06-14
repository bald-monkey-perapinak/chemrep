"""
Body size limit middleware — rejects requests with oversized bodies.

Prevents memory exhaustion from large file uploads or malicious payloads.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Default 100MB — generous enough for file uploads
DEFAULT_MAX_BODY_SIZE = 100 * 1024 * 1024


class BodyLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_body_size: int = DEFAULT_MAX_BODY_SIZE):
        super().__init__(app)
        self._max_body_size = max_body_size

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self._max_body_size:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large"},
            )
        return await call_next(request)
